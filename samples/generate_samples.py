"""Generates the fictional sample invoices in samples/invoices.

python samples/generate_samples.py
All companies, numbers and bank details are made up. The IBAN is the standard German test IBAN.
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = Path(__file__).parent / "invoices"

TEST_IBAN = "DE89 3704 0044 0532 0130 00"

INVOICES = {
    "01_small_office_supplies.pdf": [
        "Papierwerk Muster GmbH", "Industriestrasse 5, 09111 Chemnitz", "",
        "Rechnung", "Rechnungsnummer: PW-2026-0412", "Rechnungsdatum: 03.11.2026",
        "Zahlbar bis: 03.12.2026", "", "Kopierpapier A4, 40 Pakete",
        "Nettobetrag: 400,00 EUR", "MwSt 19%: 76,00 EUR", "Gesamtbetrag: 476,00 EUR",
        "", f"IBAN: {TEST_IBAN}",
    ],
    "02_inverter_parts_with_po.pdf": [
        "Supplier: Example Power Components Ltd", "", "INVOICE",
        "Invoice No: EPC-88231", "Invoice date: 2026-11-05", "Due date: 2026-12-05",
        "PO Number: PO-45017", "", "Inverter control boards, 25 pcs",
        "Net amount: 8,250.00", "VAT 19%: 1,567.50", "Total amount: 9,817.50",
        "", f"IBAN: {TEST_IBAN}",
    ],
    "03_wrong_total.pdf": [
        "Kabel und Stecker Beispiel KG", "", "Rechnung",
        "Rechnungsnummer: KS-1187", "Rechnungsdatum: 06.11.2026", "Zahlbar bis: 20.11.2026",
        "", "Solarkabel 6 mm2, 500 m",
        "Nettobetrag: 650,00 EUR", "MwSt 19%: 123,50 EUR", "Gesamtbetrag: 783,50 EUR",
    ],
    "04_large_without_po.pdf": [
        "Supplier: Sample Logistics GmbH", "", "INVOICE",
        "Invoice No: SL-2026-311", "Invoice date: 2026-11-07", "Due date: 2026-11-21",
        "", "Freight Rotterdam - Duisburg, 2 containers",
        "Net amount: 3,100.00", "VAT 19%: 589.00", "Total amount: 3,689.00",
    ],
    "05_duplicate_of_01.pdf": [
        "Papierwerk Muster GmbH", "Industriestrasse 5, 09111 Chemnitz", "",
        "Rechnung", "Rechnungsnummer: PW-2026-0412", "Rechnungsdatum: 03.11.2026",
        "Zahlbar bis: 03.12.2026", "", "Kopierpapier A4, 40 Pakete",
        "Nettobetrag: 400,00 EUR", "MwSt 19%: 76,00 EUR", "Gesamtbetrag: 476,00 EUR",
    ],
    "06_books_reduced_vat.pdf": [
        "Fachbuchhandlung Beispiel", "", "Rechnung",
        "Rechnungsnummer: FB-5521", "Rechnungsdatum: 10.11.2026", "Zahlbar bis: 24.11.2026",
        "", "Fachbuecher Photovoltaik, 3 Stueck",
        "Nettobetrag: 150,00 EUR", "MwSt 7%: 10,50 EUR", "Gesamtbetrag: 160,50 EUR",
    ],
}


def write(name: str, lines: list[str]) -> None:
    c = canvas.Canvas(str(OUT / name), pagesize=A4)
    y = 800
    for line in lines:
        c.setFont("Helvetica-Bold" if line in ("Rechnung", "INVOICE") else "Helvetica", 11)
        c.drawString(60, y, line)
        y -= 18
    c.save()


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, lines in INVOICES.items():
        write(name, lines)
    print(f"Wrote {len(INVOICES)} invoices to {OUT}")
