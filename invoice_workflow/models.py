"""Invoice data and the result of processing one invoice."""

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class Invoice(BaseModel):
    supplier: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    currency: str = "EUR"
    net_amount: Decimal | None = None
    vat_amount: Decimal | None = None
    gross_amount: Decimal | None = None
    vat_rate: Decimal | None = Field(default=None, description="percent, e.g. 19")
    po_number: str | None = None
    iban: str | None = None


class Decision(str, Enum):
    AUTO_APPROVE = "auto_approve"
    REVIEW = "review"
    REJECT = "reject"


class ProcessedInvoice(BaseModel):
    file: str
    invoice: Invoice
    extracted_by: str  # "llm" or "rules"
    issues: list[str]
    decision: Decision
