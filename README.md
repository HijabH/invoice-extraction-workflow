# Invoice Extraction Workflow

![tests](https://github.com/HijabH/invoice-extraction-workflow/actions/workflows/ci.yml/badge.svg)

A Python workflow that reads supplier invoices from PDF files, extracts the key fields with a large language model, checks them against business rules and routes each invoice: **approve automatically**, **send to review** or **reject**. Results go to CSV and JSON for import into an ERP or accounting system, and a summary can be posted to a Microsoft Teams channel.

Manual invoice entry is a classic automation case: it is repetitive, but mistakes cost money. This project shows how to let an LLM do the reading while keeping the decisions in code that can be tested and audited.

## What it does

- **Reads PDF invoices** in German or English
- **Extracts** supplier, invoice number, dates, net, VAT and gross amounts, VAT rate, purchase order number and IBAN, with an LLM or with regular expressions as a fallback
- **Checks every invoice**, whatever extracted it:
  - required fields are present
  - net + VAT equals gross (to the cent)
  - the VAT rate is a German rate (19%, 7% or 0%)
  - the due date is not before the invoice date
  - a purchase order number exists above the approval limit
  - the IBAN check digits are correct
  - the same supplier and invoice number have not been processed before
- **Decides**: correct invoices up to the approval limit are approved automatically, larger or problematic ones go to review, duplicates are rejected
- **Reports** to `results.csv` and `results.json`, and posts a summary to Microsoft Teams through an incoming webhook

```text
PDF ──> text ──> LLM (strict JSON) ──> business checks ──> decision ──> CSV / JSON / Teams
                   │ fails                ^
                   └──> regex rules ──────┘
```

## Quick start

```bash
pip install -r requirements-dev.txt

python -m invoice_workflow samples/invoices --out results
```

```text
auto_approve  01_small_office_supplies.pdf           476.00
review        02_inverter_parts_with_po.pdf         9817.50
review        03_wrong_total.pdf                     783.50  net 650.00 + VAT 123.50 does not equal gross 783.50
review        04_large_without_po.pdf               3689.00  no purchase order number for an amount above 1000
reject        05_duplicate_of_01.pdf                 476.00  duplicate: this supplier and invoice number were already processed
auto_approve  06_books_reduced_vat.pdf               160.50

6 invoices: {'auto_approve': 2, 'review': 3, 'reject': 1}
```

The sample invoices in `samples/invoices` are fictional and created by `samples/generate_samples.py`.

### Optional settings

See `.env.example`:

| Variable | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | Use an LLM for extraction (without it, regular expressions are used) |
| `EXTRACT_MODEL` | Model name, default `claude-haiku-5-5` |
| `APPROVAL_LIMIT` | Highest gross amount approved automatically, default 1000 |
| `TEAMS_WEBHOOK_URL` | Microsoft Teams incoming webhook for the summary |

## Design choices

- **The LLM reads, the code decides.** The model only copies values from the invoice; it is told never to calculate. All checks and the decision are plain Python with tests.
- **Strict output format.** The LLM answer must match the `Invoice` model, or it is rejected and the regex fallback is used.
- **Money as `Decimal`**, never floating point.
- **A broken PDF does not stop the batch**; it is logged and skipped.

## Tests

```bash
pytest
```

31 tests cover amount and date parsing, the IBAN check, regex extraction for German and English invoices, every business check, the decision rules, LLM parsing and fallback, the Teams notification and an end-to-end run over the sample PDFs. The LLM and the webhook are replaced with `httpx.MockTransport`. GitHub Actions runs the tests on every push.

## Possible next steps

- Match invoices against open purchase orders from the ERP through its API
- Read invoices straight from a shared mailbox with the Microsoft Graph API
- Support ZUGFeRD / XRechnung e-invoices, which carry the data as XML

## License

[MIT](LICENSE)
