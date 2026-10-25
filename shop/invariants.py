"""Business rules the shop must always keep. The shop checks each answer and reports a broken rule as a canary.

A broken rule does not stop the response, because a silent bug returns a wrong answer with no error.
The shop logs the rule so monitoring can see it. Each rule maps to the kind of incident it should start.
"""

from __future__ import annotations

from typing import Optional

from shop.summary import Order

TOLERANCE = 1e-9

# rule name -> incident kind (the names match IncidentKind values)
RULE_KINDS = {
    "coupon_reapplied": "silent",
    "money_bounds": "financial",
    "money_rounding": "financial",
}


def check(order: Order, summary: dict) -> list[tuple[str, str]]:
    """Return (rule, detail) for every rule the answer breaks. An empty list means the answer is healthy."""
    violations: list[tuple[str, str]] = []
    total = summary["total"]

    if order.discount is not None and not 0 <= order.discount <= 1:
        violations.append(("money_bounds", f"discount {order.discount} is outside 0..1"))
    if total < 0:
        violations.append(("money_bounds", f"payable total {total} is negative"))
    if abs(total - round(total, 2)) > TOLERANCE:
        violations.append(("money_rounding", f"total {total} is not rounded to cents"))

    # A coupon that is already applied must not be applied again: one discount only.
    if order.coupon and order.discount_applied and order.total is not None and order.discount is not None:
        expected = order.total * (1 - order.discount)
        if abs(total - expected) > TOLERANCE:
            violations.append(("coupon_reapplied", f"total {total}, expected {round(expected, 2)} with one discount"))
    return violations


def kind_for(rule: str) -> Optional[str]:
    return RULE_KINDS.get(rule)
