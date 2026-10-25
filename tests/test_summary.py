from shop.summary import Order, build_summary


def test_summary_keeps_order_id_and_currency():
    summary = build_summary(Order("o1", 100.0, 0.0))
    assert summary["order_id"] == "o1"
    assert summary["currency"] == "GBP"


def test_plain_order_has_a_total():
    assert build_summary(Order("o2", 40.0, 0.0))["total"]
