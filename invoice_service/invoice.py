"""Invoice service: a downstream consumer of the shop's order summary."""

VAT_RATE = 0.2


def invoice_total(summary: dict) -> float:
    return round(summary["total"] * (1 + VAT_RATE), 2)
