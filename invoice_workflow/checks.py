"""Business checks and the approval decision.

The rules are the same whether the data came from the LLM or the regex fallback,
so a wrong extraction is caught here instead of being paid.
"""

from decimal import Decimal

from .models import Decision, Invoice
from .parsing import iban_is_valid

ALLOWED_VAT_RATES = {Decimal("0"), Decimal("7"), Decimal("19")}  # German rates
TOLERANCE = Decimal("0.02")

REQUIRED = {
    "supplier": "supplier",
    "invoice_number": "invoice number",
    "invoice_date": "invoice date",
    "net_amount": "net amount",
    "vat_amount": "VAT amount",
    "gross_amount": "gross amount",
}


def check(invoice: Invoice, approval_limit: Decimal, seen: set[tuple[str, str]]) -> list[str]:
    """Returns a list of problems. An empty list means the invoice passed every check."""
    issues = [f"missing {label}" for field, label in REQUIRED.items() if getattr(invoice, field) in (None, "")]

    net, vat, gross = invoice.net_amount, invoice.vat_amount, invoice.gross_amount
    if net is not None and vat is not None and gross is not None:
        if abs(net + vat - gross) > TOLERANCE:
            issues.append(f"net {net} + VAT {vat} does not equal gross {gross}")
        if net > 0:
            rate = (vat / net * 100).quantize(Decimal("1"))
            if rate not in ALLOWED_VAT_RATES:
                issues.append(f"unusual VAT rate of about {rate}%")

    if invoice.invoice_date and invoice.due_date and invoice.due_date < invoice.invoice_date:
        issues.append("due date is before the invoice date")

    if gross is not None and gross > approval_limit and not invoice.po_number:
        issues.append(f"no purchase order number for an amount above {approval_limit}")

    if invoice.iban and not iban_is_valid(invoice.iban):
        issues.append("IBAN check digits are wrong")

    if invoice.supplier and invoice.invoice_number:
        key = (invoice.supplier.strip().lower(), invoice.invoice_number.strip().lower())
        if key in seen:
            issues.append("duplicate: this supplier and invoice number were already processed")
        seen.add(key)

    return issues


def decide(invoice: Invoice, issues: list[str], approval_limit: Decimal) -> Decision:
    if any(i.startswith("duplicate") for i in issues):
        return Decision.REJECT
    if issues:
        return Decision.REVIEW
    if invoice.gross_amount is not None and invoice.gross_amount > approval_limit:
        return Decision.REVIEW  # correct, but large amounts need a person's sign-off
    return Decision.AUTO_APPROVE
