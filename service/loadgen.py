"""Sends a mix of good and bad orders to the running demo shop, so monitoring has traffic and errors.

Run from demo-shop/ while the service is up:
    python -m service.loadgen --url http://127.0.0.1:8100 --count 40
"""

from __future__ import annotations

import argparse
import json
import random
import urllib.error
import urllib.request


def make_order(index: int, bad_rate: float, rng: random.Random) -> dict:
    if rng.random() < bad_rate:
        # Missing discount: the loud bug crashes the shop.
        return {"order_id": f"bad-{index}", "total": 50.0, "discount": None, "coupon": False, "discount_applied": False}
    return {"order_id": f"ok-{index}", "total": 100.0, "discount": 0.1, "coupon": False, "discount_applied": False}


def send(url: str, order: dict, timeout: float = 5.0) -> int:
    request = urllib.request.Request(
        f"{url}/summary",
        data=json.dumps(order).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def main() -> int:
    parser = argparse.ArgumentParser(description="Send demo orders to the shop service.")
    parser.add_argument("--url", default="http://127.0.0.1:8100")
    parser.add_argument("--count", type=int, default=40)
    parser.add_argument("--bad-rate", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    statuses = [send(args.url, make_order(i, args.bad_rate, rng)) for i in range(args.count)]
    print(f"sent {len(statuses)} orders: {statuses.count(200)} ok, {statuses.count(500)} failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
