"""Sends a mix of good and bad orders to the running demo shop, so monitoring has traffic and errors.

Run from demo-shop/ while the service is up:
    python -m service.loadgen --url http://127.0.0.1:8100 --count 40 --rule-rate 0.2
"""

from __future__ import annotations

import argparse
import json
import random
import time
import urllib.error
import urllib.request
from pathlib import Path


# Inputs that break the business rules in shop/invariants.py. The buggy shop answers them wrongly without crashing.
RULE_BREAKERS = [
    # coupon already applied: the silent bug discounts it a second time
    {"total": 100.0, "discount": 0.1, "coupon": True, "discount_applied": True},
    # discount above 100%: the financial bug produces a negative payable amount
    {"total": 50.0, "discount": 1.25, "coupon": False, "discount_applied": False},
    # negative order total: the financial bug produces a negative payable amount
    {"total": -20.0, "discount": 0.1, "coupon": False, "discount_applied": False},
    # fractional result: the financial bug leaves sub-cent values
    {"total": 19.99, "discount": 0.3333, "coupon": False, "discount_applied": False},
]


def make_order(index: int, bad_rate: float, rng: random.Random, rule_rate: float = 0.0) -> dict:
    roll = rng.random()
    if roll < bad_rate:
        # Missing discount: the loud bug crashes the shop.
        return {"order_id": f"bad-{index}", "total": 50.0, "discount": None, "coupon": False, "discount_applied": False}
    if roll < bad_rate + rule_rate:
        breaker = RULE_BREAKERS[index % len(RULE_BREAKERS)]
        return {"order_id": f"rule-{index}", **breaker}
    return {"order_id": f"ok-{index}", "total": 100.0, "discount": 0.1, "coupon": False, "discount_applied": False}


# Categories of the live bug mix, in the order they are checked. Each maps to the inputs that trigger one bug.
MIX_CATEGORIES = ("crash", "coupon", "money")
MIX_BREAKERS = {
    "crash": [None],  # None means "missing discount", built by make_order
    "coupon": RULE_BREAKERS[:1],
    "money": RULE_BREAKERS[1:],
}


def load_mix(path: Path) -> dict[str, float]:
    """Read bug_mix.json: a share (0 to 1) for each category. A missing key means 0, which turns that bug off."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    mix = {name: float(raw.get(name, 0.0)) for name in MIX_CATEGORIES}
    if any(share < 0 for share in mix.values()) or sum(mix.values()) > 1:
        raise ValueError("bug mix shares must be >= 0 and add up to at most 1")
    return mix


def make_mix_order(index: int, mix: dict[str, float], rng: random.Random) -> dict:
    """One order drawn from the live mix. Shares that add up to less than 1 leave the rest as good orders."""
    roll = rng.random()
    cumulative = 0.0
    for name in MIX_CATEGORIES:
        cumulative += mix.get(name, 0.0)
        if roll < cumulative:
            if name == "crash":
                return {"order_id": f"bad-{index}", "total": 50.0, "discount": None, "coupon": False, "discount_applied": False}
            breakers = MIX_BREAKERS[name]
            return {"order_id": f"{name}-{index}", **breakers[index % len(breakers)]}
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
    parser.add_argument("--bad-rate", type=float, default=0.3, help="share of orders that crash the shop")
    parser.add_argument("--rule-rate", type=float, default=0.0, help="share of orders that break a business rule")
    parser.add_argument("--interval", type=float, default=0.0, help="seconds to wait between orders; 0 sends as fast as possible")
    parser.add_argument("--mix-file", type=Path, default=None, help="bug_mix.json: live shares per bug; overrides --bad-rate and --rule-rate")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    mix = load_mix(args.mix_file) if args.mix_file else None
    statuses = []
    for i in range(args.count):
        order = make_mix_order(i, mix, rng) if mix is not None else make_order(i, args.bad_rate, rng, args.rule_rate)
        statuses.append(send(args.url, order))
        if args.interval > 0:
            time.sleep(args.interval)
    print(f"sent {len(statuses)} orders: {statuses.count(200)} ok, {statuses.count(500)} failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
