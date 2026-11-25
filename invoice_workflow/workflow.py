"""Processes a folder of PDF invoices: extract, check, decide, report, notify."""

import csv
import json
import logging
from decimal import Decimal
from pathlib import Path

import httpx
from pypdf import PdfReader

from . import extract_rules
from .checks import check, decide
from .extract_llm import LlmError, LlmExtractor
from .models import Decision, ProcessedInvoice

log = logging.getLogger(__name__)


def pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


class InvoiceWorkflow:
    def __init__(self, approval_limit: Decimal, llm: LlmExtractor | None = None,
                 teams_webhook_url: str | None = None, http: httpx.Client | None = None):
        self.approval_limit = approval_limit
        self._llm = llm
        self._webhook = teams_webhook_url
        self._http = http or httpx.Client(timeout=15)
        self._seen: set[tuple[str, str]] = set()

    def process_text(self, name: str, text: str) -> ProcessedInvoice:
        extracted_by = "rules"
        invoice = None
        if self._llm is not None:
            try:
                invoice = self._llm.extract(text)
                extracted_by = "llm"
            except LlmError as error:
                log.warning("%s: LLM extraction failed, using rules: %s", name, error)
        if invoice is None:
            invoice = extract_rules.extract(text)

        issues = check(invoice, self.approval_limit, self._seen)
        decision = decide(invoice, issues, self.approval_limit)
        return ProcessedInvoice(file=name, invoice=invoice, extracted_by=extracted_by,
                                issues=issues, decision=decision)

    def process_folder(self, folder: Path) -> list[ProcessedInvoice]:
        results = []
        for path in sorted(folder.glob("*.pdf")):
            try:
                text = pdf_text(path)
            except Exception as error:  # a broken PDF must not stop the batch
                log.error("%s: could not read PDF: %s", path.name, error)
                continue
            results.append(self.process_text(path.name, text))
        return results

    def notify(self, results: list[ProcessedInvoice]) -> bool:
        """Posts a short summary to a Microsoft Teams channel through an incoming webhook."""
        if not self._webhook:
            return False
        needs_attention = [r for r in results if r.decision != Decision.AUTO_APPROVE]
        lines = [f"Invoices processed: {len(results)}, need attention: {len(needs_attention)}"]
        lines += [f"- {r.file}: {r.decision.value} ({'; '.join(r.issues) or 'above approval limit'})"
                  for r in needs_attention]
        try:
            response = self._http.post(self._webhook, json={"text": "\n".join(lines)})
            return response.status_code < 300
        except httpx.HTTPError as error:
            log.error("Teams notification failed: %s", error)
            return False


def write_reports(results: list[ProcessedInvoice], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, csv_path = out_dir / "results.json", out_dir / "results.csv"

    json_path.write_text(json.dumps([r.model_dump(mode="json") for r in results], indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file", "decision", "supplier", "invoice_number", "invoice_date",
                         "gross_amount", "po_number", "extracted_by", "issues"])
        for r in results:
            i = r.invoice
            writer.writerow([r.file, r.decision.value, i.supplier, i.invoice_number, i.invoice_date,
                             i.gross_amount, i.po_number, r.extracted_by, "; ".join(r.issues)])
    return json_path, csv_path
