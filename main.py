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
    "google/gemma-4-26b-a4b-it:free"
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
You are an invoice extraction engine.

Extract ONLY these fields.

Return STRICT JSON.

No markdown.

No explanation.

Schema:

{
"invoice_no": string|null,
"date": string|null,
"vendor": string|null,
"amount": number|null,
"tax": number|null,
"currency": string|null
}

Rules:

amount = subtotal BEFORE tax

tax = tax amount only

date = YYYY-MM-DD

Always output every key.

If missing use null.
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
            },
            json=payload,
        )

    r.raise_for_status()

    data = r.json()

    text = data["choices"][0]["message"]["content"]

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
