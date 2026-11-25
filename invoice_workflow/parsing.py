"""Helpers for amounts and dates written in German or English style."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def parse_amount(text: str | None) -> Decimal | None:
    """Parses '1.234,56', '1,234.56', '1234.56', '1234,56' and '€ 1.234,56' into Decimal('1234.56')."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d,.\-]", "", text)
    if not cleaned or not re.search(r"\d", cleaned):
        return None

    last_comma, last_dot = cleaned.rfind(","), cleaned.rfind(".")
    if last_comma > last_dot:
        # German style: dots group thousands, comma is the decimal separator
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")

    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


_DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d %B %Y", "%B %d, %Y")


def parse_date(text: str | None) -> date | None:
    if not text:
        return None
    text = text.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def iban_is_valid(iban: str) -> bool:
    """Checks the ISO 13616 mod-97 check digits."""
    compact = iban.replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", compact):
        return False
    rearranged = compact[4:] + compact[:4]
    digits = "".join(str(int(ch, 36)) for ch in rearranged)
    return int(digits) % 97 == 1
