import json
import random
import threading
import urllib.error
import urllib.request

import pytest

from service.loadgen import make_order, send
from service.server import make_server

# Service tests check behaviour over HTTP. The sandbox gate runs only unit tests (-m "not integration").
pytestmark = pytest.mark.integration


def start(tmp_path):
    server = make_server(0, tmp_path / "shop.log")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    return server, url


def test_good_order_returns_a_summary(tmp_path):
    server, url = start(tmp_path)
    try:
        body = json.loads(urllib.request.urlopen(urllib.request.Request(
            f"{url}/summary",
            data=json.dumps({"order_id": "o1", "total": 100.0, "discount": 0.1}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )).read())
        assert body["order_id"] == "o1"
        assert body["total"] == 90.0
    finally:
        server.shutdown()


def test_bad_order_logs_a_json_error_with_relative_stack(tmp_path):
    server, url = start(tmp_path)
    try:
        # A non-numeric total fails in both the buggy and the patched code, so this test survives the loud patch.
        assert send(url, {"order_id": "bad", "total": "abc", "discount": 0.1}) == 500
        record = json.loads((tmp_path / "shop.log").read_text(encoding="utf-8").splitlines()[0])
        assert record["level"] == "ERROR"
        assert record["error_type"] == "TypeError"
        assert 'File "shop/summary.py"' in record["stack_trace"]
        assert "\\" not in record["stack_trace"]  # paths are relative and use forward slashes
    finally:
        server.shutdown()


def test_metrics_count_requests_errors_and_histogram(tmp_path):
    server, url = start(tmp_path)
    try:
        send(url, {"order_id": "ok", "total": 10.0, "discount": 0.0})
        send(url, {"order_id": "bad", "total": "abc", "discount": 0.1})
        text = urllib.request.urlopen(f"{url}/metrics").read().decode()
        assert "shop_requests_total 2" in text
        assert "shop_errors_total 1" in text
        assert 'shop_request_duration_seconds_bucket{le="+Inf"} 2' in text
        assert "shop_request_duration_seconds_count 2" in text
    finally:
        server.shutdown()


def test_unknown_path_is_404(tmp_path):
    server, url = start(tmp_path)
    try:
        try:
            urllib.request.urlopen(f"{url}/nope")
            raise AssertionError("expected 404")
        except urllib.error.HTTPError as error:
            assert error.code == 404
    finally:
        server.shutdown()


def test_loadgen_makes_bad_orders_on_request():
    rng = random.Random(1)
    orders = [make_order(i, bad_rate=1.0, rng=rng) for i in range(3)]
    assert all(order["discount"] is None for order in orders)
