"""Regular-expression extraction for invoices with standard German or English labels.

This is the fallback when no LLM is configured or the LLM fails. It only works for
invoices that use common labels; the LLM handles unusual layouts.
"""

import re

from .models import Invoice
from .parsing import parse_amount, parse_date

_AMOUNT = r"(?:EUR|€)?\s*(-?[\d.,]+\d)"
_DATE = r"(\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})"


def _find(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def extract(text: str) -> Invoice:
    supplier = _find([r"^(?:From|Von|Lieferant|Supplier)\s*:\s*(.+)$"], text)
    if supplier is None:
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), None)
        supplier = first_line

    vat_rate = _find([r"(?:VAT|MwSt\.?|USt\.?|Umsatzsteuer)\s*\(?(\d{1,2}(?:[.,]\d+)?)\s*%"], text)

    return Invoice(
        supplier=supplier,
        invoice_number=_find([r"(?:Invoice\s*(?:No\.?|Number|#)|Rechnungs?\s*(?:nummer|nr\.?))\s*:?\s*([A-Z0-9][A-Z0-9/\-]*)"], text),
        invoice_date=parse_date(_find([rf"(?:Invoice\s*date|Rechnungsdatum|Datum)\s*:?\s*{_DATE}"], text)),
        due_date=parse_date(_find([rf"(?:Due\s*date|Payable\s*by|F[äa]llig(?:keitsdatum|\s*am)?|Zahlbar\s*bis)\s*:?\s*{_DATE}"], text)),
        currency="EUR",
        net_amount=parse_amount(_find([rf"(?:Net\s*(?:amount|total)?|Netto(?:betrag)?|Zwischensumme)\s*:?\s*{_AMOUNT}"], text)),
        vat_amount=parse_amount(_find([rf"(?:VAT|MwSt\.?|USt\.?|Umsatzsteuer)[^\n:]*:\s*{_AMOUNT}"], text)),
        gross_amount=parse_amount(_find([rf"(?:Total\s*(?:amount|due)?|Gesamt(?:betrag)?|Brutto(?:betrag)?|Rechnungsbetrag)\s*:?\s*{_AMOUNT}"], text)),
        vat_rate=parse_amount(vat_rate) if vat_rate else None,
        po_number=_find([r"\b(?:PO\s*(?:No\.?|Number)?|Purchase\s*order(?:\s*(?:No\.?|Number))?|Bestellnummer|Bestell-Nr\.?)\s*:\s*([A-Z0-9][A-Z0-9\-]*)"], text),
        iban=_find([r"IBAN\s*:?\s*([A-Z]{2}\d{2}(?:\s?[A-Z0-9]{2,4}){3,8})"], text),
    )
