from datetime import date
from decimal import Decimal

import pytest

from invoice_workflow import extract_rules
from invoice_workflow.parsing import iban_is_valid, parse_amount, parse_date


@pytest.mark.parametrize("text, expected", [
    ("1.234,56", "1234.56"),
    ("1,234.56", "1234.56"),
    ("1234,5", "1234.50"),
    ("€ 476,00", "476.00"),
    ("EUR 9,817.50", "9817.50"),
    ("400", "400.00"),
])
def test_parses_german_and_english_amounts(text, expected):
    assert parse_amount(text) == Decimal(expected)


@pytest.mark.parametrize("text", [None, "", "abc", "EUR"])
def test_unparseable_amounts_return_none(text):
    assert parse_amount(text) is None


@pytest.mark.parametrize("text", ["03.11.2026", "2026-11-03", "03/11/2026"])
def test_parses_dates(text):
    assert parse_date(text) == date(2026, 11, 3)


def test_iban_check_digits():
    assert iban_is_valid("DE89 3704 0044 0532 0130 00")
    assert not iban_is_valid("DE88 3704 0044 0532 0130 00")
    assert not iban_is_valid("not an iban")


GERMAN = """Papierwerk Muster GmbH
Rechnung
Rechnungsnummer: PW-2026-0412
Rechnungsdatum: 03.11.2026
Zahlbar bis: 03.12.2026
Nettobetrag: 400,00 EUR
MwSt 19%: 76,00 EUR
Gesamtbetrag: 476,00 EUR
IBAN: DE89 3704 0044 0532 0130 00"""

ENGLISH = """Supplier: Example Power Components Ltd
INVOICE
Invoice No: EPC-88231
Invoice date: 2026-11-05
Due date: 2026-12-05
PO Number: PO-45017
Net amount: 8,250.00
VAT 19%: 1,567.50
Total amount: 9,817.50"""


def test_extracts_a_german_invoice():
    inv = extract_rules.extract(GERMAN)
    assert inv.supplier == "Papierwerk Muster GmbH"
    assert inv.invoice_number == "PW-2026-0412"
    assert inv.invoice_date == date(2026, 11, 3)
    assert inv.due_date == date(2026, 12, 3)
    assert (inv.net_amount, inv.vat_amount, inv.gross_amount) == (Decimal("400.00"), Decimal("76.00"), Decimal("476.00"))
    assert inv.vat_rate == Decimal("19.00")
    assert inv.iban == "DE89 3704 0044 0532 0130 00"
    assert inv.po_number is None


def test_extracts_an_english_invoice():
    inv = extract_rules.extract(ENGLISH)
    assert inv.supplier == "Example Power Components Ltd"
    assert inv.invoice_number == "EPC-88231"
    assert inv.gross_amount == Decimal("9817.50")
    assert inv.po_number == "PO-45017"


def test_po_is_not_read_from_words_that_start_with_po():
    # regression test: "Power" in the supplier name was once read as PO number "wer"
    inv = extract_rules.extract("Supplier: Example Power Components Ltd\nInvoice No: X-1\nTotal amount: 10.00")
    assert inv.po_number is None
