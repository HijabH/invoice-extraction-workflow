import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from invoice_workflow.checks import check, decide
from invoice_workflow.extract_llm import LlmError, LlmExtractor, parse_response
from invoice_workflow.models import Decision, Invoice
from invoice_workflow.workflow import InvoiceWorkflow, write_reports

LIMIT = Decimal("1000")
SAMPLES = Path(__file__).parent.parent / "samples" / "invoices"


def good_invoice(**changes) -> Invoice:
    data = dict(supplier="Papierwerk Muster GmbH", invoice_number="PW-1", invoice_date=date(2026, 11, 3),
                due_date=date(2026, 12, 3), net_amount=Decimal("400.00"), vat_amount=Decimal("76.00"),
                gross_amount=Decimal("476.00"), vat_rate=Decimal("19"))
    data.update(changes)
    return Invoice(**data)


# --- checks and decisions ----------------------------------------------------

def test_a_correct_small_invoice_is_approved_automatically():
    inv = good_invoice()
    issues = check(inv, LIMIT, set())
    assert issues == []
    assert decide(inv, issues, LIMIT) == Decision.AUTO_APPROVE


def test_a_correct_large_invoice_still_goes_to_review():
    inv = good_invoice(net_amount=Decimal("1000"), vat_amount=Decimal("190"), gross_amount=Decimal("1190"),
                       po_number="PO-1")
    issues = check(inv, LIMIT, set())
    assert issues == []
    assert decide(inv, issues, LIMIT) == Decision.REVIEW


def test_finds_wrong_totals_and_unusual_vat():
    issues = check(good_invoice(vat_amount=Decimal("50.00")), LIMIT, set())
    assert any("does not equal gross" in i for i in issues)
    assert any("unusual VAT rate" in i for i in issues)


def test_allows_a_cent_of_rounding():
    assert check(good_invoice(gross_amount=Decimal("476.01")), LIMIT, set()) == []


def test_reports_missing_fields_and_bad_dates():
    issues = check(good_invoice(invoice_number=None, due_date=date(2026, 10, 1)), LIMIT, set())
    assert "missing invoice number" in issues
    assert "due date is before the invoice date" in issues


def test_requires_a_po_above_the_limit():
    inv = good_invoice(net_amount=Decimal("2000"), vat_amount=Decimal("380"), gross_amount=Decimal("2380"))
    assert any("no purchase order" in i for i in check(inv, LIMIT, set()))


def test_rejects_wrong_iban():
    assert "IBAN check digits are wrong" in check(good_invoice(iban="DE88 3704 0044 0532 0130 00"), LIMIT, set())


def test_rejects_duplicates_ignoring_case():
    seen: set = set()
    check(good_invoice(), LIMIT, seen)
    second = good_invoice(supplier="PAPIERWERK MUSTER GMBH", invoice_number="pw-1")
    issues = check(second, LIMIT, seen)
    assert decide(second, issues, LIMIT) == Decision.REJECT


# --- LLM extraction ----------------------------------------------------------

def llm_with(handler) -> LlmExtractor:
    return LlmExtractor("key", "model", client=httpx.Client(transport=httpx.MockTransport(handler)))


def answer(obj) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(obj) if not isinstance(obj, str) else obj}]}


def test_parses_an_llm_answer():
    inv = parse_response(answer({"supplier": "ACME", "invoice_number": "A-1", "invoice_date": "2026-11-03",
                                 "gross_amount": "119.00", "net_amount": "100.00", "vat_amount": "19.00"}))
    assert inv.gross_amount == Decimal("119.00")
    assert inv.invoice_date == date(2026, 11, 3)


def test_rejects_an_llm_answer_that_is_not_json():
    with pytest.raises(LlmError):
        parse_response(answer("The total is 119 euros."))


def test_uses_the_llm_when_it_works():
    llm = llm_with(lambda r: httpx.Response(200, json=answer({
        "supplier": "ACME", "invoice_number": "A-1", "invoice_date": "2026-11-03",
        "net_amount": "100.00", "vat_amount": "19.00", "gross_amount": "119.00"})))
    result = InvoiceWorkflow(LIMIT, llm=llm).process_text("a.pdf", "anything")
    assert result.extracted_by == "llm"
    assert result.decision == Decision.AUTO_APPROVE


def test_falls_back_to_rules_when_the_llm_fails():
    llm = llm_with(lambda r: httpx.Response(503))
    text = "Supplier: ACME\nInvoice No: A-1\nInvoice date: 2026-11-03\nNet amount: 100.00\nVAT 19%: 19.00\nTotal amount: 119.00"
    result = InvoiceWorkflow(LIMIT, llm=llm).process_text("a.pdf", text)
    assert result.extracted_by == "rules"
    assert result.invoice.invoice_number == "A-1"


# --- end to end on the sample PDFs --------------------------------------------

def test_sample_invoices_get_the_expected_decisions(tmp_path):
    results = InvoiceWorkflow(LIMIT).process_folder(SAMPLES)

    decisions = {r.file: r.decision for r in results}
    assert decisions == {
        "01_small_office_supplies.pdf": Decision.AUTO_APPROVE,
        "02_inverter_parts_with_po.pdf": Decision.REVIEW,
        "03_wrong_total.pdf": Decision.REVIEW,
        "04_large_without_po.pdf": Decision.REVIEW,
        "05_duplicate_of_01.pdf": Decision.REJECT,
        "06_books_reduced_vat.pdf": Decision.AUTO_APPROVE,
    }

    json_path, csv_path = write_reports(results, tmp_path)
    assert len(json.loads(json_path.read_text())) == 6
    assert csv_path.read_text().splitlines()[0].startswith("file,decision,supplier")


def test_posts_a_summary_to_teams():
    posted = []

    def handler(request: httpx.Request) -> httpx.Response:
        posted.append(json.loads(request.content))
        return httpx.Response(200)

    workflow = InvoiceWorkflow(LIMIT, teams_webhook_url="https://example.webhook.office.com/x",
                               http=httpx.Client(transport=httpx.MockTransport(handler)))
    results = workflow.process_folder(SAMPLES)

    assert workflow.notify(results) is True
    assert "need attention: 4" in posted[0]["text"]
