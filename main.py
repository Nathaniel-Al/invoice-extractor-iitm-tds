import json
import os

from dateutil import parser
from dotenv import load_dotenv
import httpx

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "openai/gpt-oss-120b:free"
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"status": "running"}


class InvoiceRequest(BaseModel):
    invoice_text: str


def normalize_date(date_str):

    if date_str is None:
        return None

    try:
        return parser.parse(date_str).strftime("%Y-%m-%d")
    except:
        return None


def normalize_number(value):

    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    value = (
        str(value)
        .replace(",", "")
        .replace("₹", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .replace("INR", "")
        .replace("$", "")
        .replace("USD", "")
        .strip()
    )

    try:
        return float(value)
    except:
        return None


SYSTEM_PROMPT = """
You are a deterministic invoice information extraction engine.

Your task is to extract information exactly as written.

Return ONLY valid JSON.

Do NOT use markdown.

Do NOT wrap JSON inside ```.

Never explain.

Never summarize.

Never invent values.

Return this exact schema:

{
"invoice_no": null,
"date": null,
"vendor": null,
"amount": null,
"tax": null,
"currency": null
}

Rules:

invoice_no:
- Extract the primary invoice identifier.
- It may be labelled:
  Invoice No
  Invoice Number
  Invoice #
  Inv No
  Bill No
  Reference No
  Document Number
- It may also appear WITHOUT any label.
- Examples:
  INV-2026-0041
  IR-2001
  DELTA-112
  A-445
  INV/2025/19

Do NOT confuse invoice numbers with:
GSTIN
PAN
Order Number
Purchase Order
Customer ID
Phone numbers

date:
Return YYYY-MM-DD.

amount:
Subtotal BEFORE tax.

tax:
Tax amount only.

currency:
ISO code when possible.
Otherwise:
INR
USD
EUR
GBP

Return every key.

Missing values must be null.
"""

async def extract_llm(invoice_text):

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": invoice_text,
            },
        ],
        "temperature": 0,
        "top_p": 0.1,
        "response_format": {
            "type": "json_object"
        },
    }

    async with httpx.AsyncClient(timeout=90) as client:

        r = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://invoice-extractor-iitm-tds.onrender.com",
                "X-Title": "Invoice Extractor IITM",
            },
            json=payload,
        )

    r.raise_for_status()

    data = r.json()

    text = data["choices"][0]["message"]["content"]

    text = text.replace("```json", "")
    text = text.replace("```", "")
    text = text.strip()

    obj = json.loads(text)

    result = {
        "invoice_no": obj.get("invoice_no"),
        "date": normalize_date(obj.get("date")),
        "vendor": obj.get("vendor"),
        "amount": normalize_number(obj.get("amount")),
        "tax": normalize_number(obj.get("tax")),
        "currency": obj.get("currency"),
    }

    return result


@app.post("/extract")
async def extract(req: InvoiceRequest):

    try:

        return await extract_llm(req.invoice_text)

    except Exception:

        return {
            "invoice_no": None,
            "date": None,
            "vendor": None,
            "amount": None,
            "tax": None,
            "currency": None,
        }
