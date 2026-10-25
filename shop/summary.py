"""Order summary for shop-api. The invoice service reads this output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Order:
    order_id: str
    total: Optional[float]     # None when the cart has no priced items yet
    discount: Optional[float]  # fraction off, e.g. 0.1; None when the field is missing
    coupon: bool = False
    discount_applied: bool = False


def build_summary(order: Order) -> dict:
    total = (order.total or 0) * (1 - (order.discount or 0))
    if order.coupon:
        total = total * (1 - order.discount)
    return {"order_id": order.order_id, "total": total, "currency": "GBP"}
