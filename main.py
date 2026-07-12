from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dateutil import parser
import re

app = FastAPI(title="Invoice Extractor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok"}


class Invoice(BaseModel):
    invoice_text: str


def parse_amount(value):
    if value is None:
        return None
    value = value.replace(",", "").replace(" ", "")
    try:
        return float(value)
    except:
        return None


def search_patterns(text, patterns):
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m
    return None


@app.post("/extract")
def extract(data: Invoice):

    text = data.invoice_text

    result = {
        "invoice_no": None,
        "date": None,
        "vendor": None,
        "amount": None,
        "tax": None,
        "currency": None,
    }

    # -------------------------
    # Invoice Number
    # -------------------------
    invoice_patterns = [
        r"Invoice\s*(?:No|Number|#|ID)?\s*[:#-]?\s*([A-Za-z0-9\-\/]+)",
        r"Inv\s*No\.?\s*[:#-]?\s*([A-Za-z0-9\-\/]+)",
        r"Invoice#\s*([A-Za-z0-9\-\/]+)",
    ]

    m = search_patterns(text, invoice_patterns)
    if m:
        result["invoice_no"] = m.group(1).strip()

    # -------------------------
    # Vendor
    # -------------------------
    vendor_patterns = [
        r"Vendor\s*:\s*(.+)",
        r"Seller\s*:\s*(.+)",
        r"Supplier\s*:\s*(.+)",
        r"From\s*:\s*(.+)",
    ]

    m = search_patterns(text, vendor_patterns)
    if m:
        result["vendor"] = m.group(1).strip()

    # -------------------------
    # Date
    # -------------------------
    m = re.search(r"Date\s*[:\-]?\s*(.+)", text, re.IGNORECASE)
    if m:
        try:
            result["date"] = parser.parse(
                m.group(1).strip(), dayfirst=True
            ).strftime("%Y-%m-%d")
        except:
            pass

    # -------------------------
    # Currency
    # -------------------------
    if re.search(r"\bINR\b|₹|Rs\.?", text, re.I):
        result["currency"] = "INR"
    elif re.search(r"\bUSD\b|\$", text):
        result["currency"] = "USD"
    elif re.search(r"\bEUR\b|€", text):
        result["currency"] = "EUR"

    money = r"(?:Rs\.?|₹|INR|USD|\$|EUR|€)?\s*([\d,]+(?:\.\d+)?)"

    # -------------------------
    # Amount (Subtotal BEFORE tax)
    # -------------------------
    amount_patterns = [
        rf"Sub\s*Total\s*:?\s*{money}",
        rf"Subtotal\s*:?\s*{money}",
        rf"Amount\s*Before\s*Tax\s*:?\s*{money}",
        rf"Net\s*Amount\s*:?\s*{money}",
        rf"Taxable\s*Amount\s*:?\s*{money}",
        rf"Before\s*Tax\s*:?\s*{money}",
    ]

    for pattern in amount_patterns:
        m = re.search(pattern, text, re.I)
        if m:
            result["amount"] = parse_amount(m.group(1))
            break

    # -------------------------
    # Tax
    # -------------------------
    tax_patterns = [
        rf"GST(?:\s*\(\d+%?\))?\s*:?\s*{money}",
        rf"VAT(?:\s*\(\d+%?\))?\s*:?\s*{money}",
        rf"CGST\s*:?\s*{money}",
        rf"SGST\s*:?\s*{money}",
        rf"IGST\s*:?\s*{money}",
        rf"Tax\s*:?\s*{money}",
    ]

    total_tax = 0.0
    found_tax = False

    for pattern in tax_patterns:
        for m in re.finditer(pattern, text, re.I):
            value = parse_amount(m.group(1))
            if value is not None:
                total_tax += value
                found_tax = True

    if found_tax:
        result["tax"] = round(total_tax, 2)

    return result
