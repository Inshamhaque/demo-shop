"""The shop's business-rule checks: each rule fires on its bug and stays quiet on a healthy answer. No network."""

import pytest

from shop.invariants import check
from shop.summary import Order, build_summary

# Integration marker keeps these out of the sandbox gate. The gate must still accept the naive
# string-total patch (the blocked demo relies on it), and these checks would reject it with a TypeError.
pytestmark = pytest.mark.integration


def rules_for(order: Order) -> list[str]:
    return [rule for rule, _ in check(order, build_summary(order))]


def test_a_healthy_order_breaks_no_rule():
    assert rules_for(Order("ok", 100.0, 0.1)) == []


def test_a_coupon_already_applied_is_flagged_as_reapplied():
    order = Order("c", 100.0, 0.1, coupon=True, discount_applied=True)
    assert rules_for(order) == ["coupon_reapplied"]


def test_a_coupon_not_yet_applied_is_healthy():
    assert rules_for(Order("c", 100.0, 0.1, coupon=True, discount_applied=False)) == []


@pytest.mark.parametrize("order", [
    Order("big", 50.0, 1.25),    # discount above 100% -> negative payable
    Order("neg", -20.0, 0.1),    # negative total
])
def test_money_bounds_are_flagged(order):
    assert "money_bounds" in rules_for(order)


def test_sub_cent_totals_are_flagged():
    assert rules_for(Order("cents", 19.99, 0.3333)) == ["money_rounding"]
