"""The demo shop as a running HTTP service, so real monitoring has something to watch.

Endpoints:
  POST /summary   body: an order as JSON. Returns the summary, or 500 with the error when the code fails.
  GET  /metrics   Prometheus text format: request, error and latency histogram counters.

Every failure is written as one JSON line to logs/shop.log, with the stack trace using paths relative
to the demo shop (for example File "shop/summary.py"), so the cause classifier can read it.

Run from demo-shop/:  python -m service.server --port 8100
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEMO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEMO_ROOT))

from shop.invariants import check  # noqa: E402
from shop.logfile import DEFAULT_BACKUPS, DEFAULT_MAX_BYTES, append_line  # noqa: E402
from shop.summary import Order, build_summary  # noqa: E402

SERVICE = "shop-api"
BUCKETS = [0.01, 0.05, 0.1, 0.25, 0.5, 1.0]
DEFAULT_LOG = DEMO_ROOT / "logs" / "shop.log"


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.requests = 0
        self.errors = 0
        self.bucket_counts = [0] * (len(BUCKETS) + 1)  # last one is +Inf
        self.duration_sum = 0.0
        self.duration_count = 0

    def observe(self, seconds: float, failed: bool) -> None:
        with self._lock:
            self.requests += 1
            self.errors += int(failed)
            self.duration_sum += seconds
            self.duration_count += 1
            for index, bound in enumerate(BUCKETS):
                if seconds <= bound:
                    self.bucket_counts[index] += 1
            self.bucket_counts[-1] += 1

    def render(self) -> str:
        with self._lock:
            lines = [
                "# TYPE shop_requests_total counter",
                f"shop_requests_total {self.requests}",
                "# TYPE shop_errors_total counter",
                f"shop_errors_total {self.errors}",
                "# TYPE shop_request_duration_seconds histogram",
            ]
            for bound, count in zip(BUCKETS, self.bucket_counts):
                lines.append(f'shop_request_duration_seconds_bucket{{le="{bound}"}} {count}')
            lines.append(f'shop_request_duration_seconds_bucket{{le="+Inf"}} {self.bucket_counts[-1]}')
            lines.append(f"shop_request_duration_seconds_sum {self.duration_sum:.6f}")
            lines.append(f"shop_request_duration_seconds_count {self.duration_count}")
            return "\n".join(lines) + "\n"


def relative_stack(exc: BaseException) -> str:
    frames = []
    for frame in traceback.extract_tb(exc.__traceback__):
        try:
            name = Path(frame.filename).resolve().relative_to(DEMO_ROOT).as_posix()
        except ValueError:
            name = frame.filename
        frames.append(f'  File "{name}", line {frame.lineno}, in {frame.name}')
    return "\n".join([f"{type(exc).__name__}: {exc}", *frames])


class ShopHandler(BaseHTTPRequestHandler):
    metrics: Metrics
    log_path: Path
    log_lock: threading.Lock
    log_max_bytes: int
    log_backups: int

    def log_message(self, format, *args):  # keep the console quiet; the JSON log is the record
        return

    def _send(self, status: int, body: str, content_type: str = "application/json") -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _write_log(self, record: dict) -> None:
        with self.log_lock:
            append_line(self.log_path, json.dumps(record) + "\n", self.log_max_bytes, self.log_backups)

    def do_GET(self) -> None:
        if self.path == "/metrics":
            self._send(200, self.metrics.render(), "text/plain; version=0.0.4")
        else:
            self._send(404, json.dumps({"detail": "not found"}))

    def do_POST(self) -> None:
        if self.path != "/summary":
            self._send(404, json.dumps({"detail": "not found"}))
            return
        started = time.monotonic()
        failed = False
        try:
            length = int(self.headers.get("Content-Length", "0"))
            order = Order(**json.loads(self.rfile.read(length) or b"{}"))
            summary = build_summary(order)
            for rule, detail in check(order, summary):
                # A broken business rule is not a crash, so the answer still goes out. It is logged as a canary.
                self._write_log({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "level": "ERROR",
                    "service": SERVICE,
                    "message": f"canary: {rule} rule broken for order {order.order_id}: {detail}",
                    "error_type": "InvariantViolation",
                    "rule": rule,
                    "stack_trace": "",
                })
            self._send(200, json.dumps(summary))
        except Exception as exc:  # the shop must answer every request, even when its own code fails
            failed = True
            self._write_log({
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": "ERROR",
                "service": SERVICE,
                "message": f"order failed: {type(exc).__name__}: {exc}",
                "error_type": type(exc).__name__,
                "stack_trace": relative_stack(exc),
            })
            self._send(500, json.dumps({"detail": f"{type(exc).__name__}: {exc}"}))
        finally:
            self.metrics.observe(time.monotonic() - started, failed)


def make_server(port: int = 0, log_path: Path = DEFAULT_LOG, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    handler = type("BoundShopHandler", (ShopHandler,), {
        "metrics": Metrics(),
        "log_path": log_path,
        "log_lock": threading.Lock(),
        "log_max_bytes": int(os.environ.get("SHOP_LOG_MAX_BYTES", DEFAULT_MAX_BYTES)),
        "log_backups": int(os.environ.get("SHOP_LOG_BACKUPS", DEFAULT_BACKUPS)),
    })
    # 0.0.0.0 inside the Docker image, so the published port is reachable from the host.
    return ThreadingHTTPServer((host, port), handler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the demo shop as an HTTP service.")
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    server = make_server(args.port, args.log, args.host)
    print(f"demo shop listening on http://127.0.0.1:{args.port} (logs: {args.log})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
