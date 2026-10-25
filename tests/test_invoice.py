from invoice_service.invoice import invoice_total


def test_invoice_adds_vat():
    assert invoice_total({"total": 100.0}) == 120.0
