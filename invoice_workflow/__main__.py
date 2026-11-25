"""Command line entry point.

python -m invoice_workflow samples/invoices --out results
"""

import argparse
import logging
import os
import sys
from decimal import Decimal
from pathlib import Path

from .extract_llm import LlmExtractor
from .models import Decision
from .workflow import InvoiceWorkflow, write_reports


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Extract, check and route PDF invoices.")
    parser.add_argument("folder", type=Path, help="folder with PDF invoices")
    parser.add_argument("--out", type=Path, default=Path("results"), help="where to write results.csv and results.json")
    parser.add_argument("--limit", type=Decimal, default=Decimal(os.getenv("APPROVAL_LIMIT", "1000")),
                        help="highest gross amount that can be approved automatically (default 1000)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=os.getenv("LOG_LEVEL", "WARNING"), format="%(levelname)s %(message)s")

    if not args.folder.is_dir():
        print(f"Folder not found: {args.folder}")
        return 2

    api_key = os.getenv("ANTHROPIC_API_KEY")
    llm = LlmExtractor(api_key, os.getenv("EXTRACT_MODEL", "claude-haiku-5-5")) if api_key else None
    workflow = InvoiceWorkflow(args.limit, llm=llm, teams_webhook_url=os.getenv("TEAMS_WEBHOOK_URL"))

    results = workflow.process_folder(args.folder)
    for r in results:
        print(f"{r.decision.value:<13} {r.file:<34} {r.invoice.gross_amount or '-':>10}  {'; '.join(r.issues)}")

    json_path, csv_path = write_reports(results, args.out)
    counts = {d.value: sum(r.decision == d for r in results) for d in Decision}
    print(f"\n{len(results)} invoices: {counts}")
    print(f"Reports: {csv_path}, {json_path}")
    if workflow.notify(results):
        print("Summary posted to Microsoft Teams.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
