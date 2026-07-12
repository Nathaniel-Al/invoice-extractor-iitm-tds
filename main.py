from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dateutil import parser
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Invoice(BaseModel):
    invoice_text: str

def parse_money(s):
    if s is None:
        return None
    return float(s.replace(",", ""))

@app.post("/extract")
def extract(data: Invoice):

    text = data.invoice_text

    result = {
        "invoice_no": None,
        "date": None,
        "vendor": None,
        "amount": None,
        "tax": None,
        "currency": None
    }

    # Invoice Number
    m = re.search(
        r"Invoice\s*(?:No|Number|#)?\s*[:#]?\s*([A-Za-z0-9\-]+)",
        text,
        re.I,
    )
    if m:
        result["invoice_no"] = m.group(1)

    # Vendor
    m = re.search(r"(Vendor|Seller)\s*:\s*(.+)", text, re.I)
    if m:
        result["vendor"] = m.group(2).strip()

    # Date
    m = re.search(r"Date\s*:\s*(.+)", text)
    if m:
        try:
            result["date"] = parser.parse(
                m.group(1)
            ).strftime("%Y-%m-%d")
        except:
            pass

    # Subtotal
    m = re.search(
        r"Subtotal.*?(Rs\.?|INR|USD)\s*([\d,]+\.\d+)",
        text,
        re.I,
    )
    if m:
        result["amount"] = parse_money(m.group(2))

    # Tax
    m = re.search(
        r"(GST|VAT).*?(Rs\.?|INR|USD)\s*([\d,]+\.\d+)",
        text,
        re.I,
    )
    if m:
        result["tax"] = parse_money(m.group(3))

    # Currency
    if "USD" in text:
        result["currency"] = "USD"
    elif "INR" in text or "Rs." in text:
        result["currency"] = "INR"

    return result
