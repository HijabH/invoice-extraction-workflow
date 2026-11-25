"""Extracts invoice fields with an LLM through the Anthropic Messages API.

The model must return JSON matching the Invoice model. Amounts are returned as strings
and parsed in code, so the model never does arithmetic that we rely on.
"""

import json
import logging

import httpx
from pydantic import ValidationError

from .models import Invoice

log = logging.getLogger(__name__)

API_URL = "https://api.anthropic.com/v1/messages"

SYSTEM_PROMPT = """You extract data from supplier invoices (German or English).
Reply with one JSON object and nothing else, with these keys (use null when a value is not on the invoice):
  "supplier", "invoice_number", "invoice_date" (YYYY-MM-DD), "due_date" (YYYY-MM-DD),
  "currency" (ISO code), "net_amount", "vat_amount", "gross_amount" (numbers as strings with a dot, e.g. "1234.56"),
  "vat_rate" (percent as a string, e.g. "19"), "po_number", "iban"
Copy values exactly as printed. Never calculate or guess a missing value."""


class LlmError(Exception):
    pass


class LlmExtractor:
    def __init__(self, api_key: str, model: str, client: httpx.Client | None = None, timeout: float = 30.0):
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.Client(timeout=timeout)

    def extract(self, text: str) -> Invoice:
        payload = {
            "model": self._model,
            "max_tokens": 600,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": text[:20_000]}],
        }
        headers = {"x-api-key": self._api_key, "anthropic-version": "2023-06-01",
                   "content-type": "application/json"}
        try:
            response = self._client.post(API_URL, json=payload, headers=headers)
        except httpx.HTTPError as error:
            raise LlmError(f"request failed: {error}") from error
        if response.status_code != 200:
            raise LlmError(f"API error HTTP {response.status_code}")
        return parse_response(response.json())


def parse_response(data: dict) -> Invoice:
    try:
        text = "".join(b["text"] for b in data["content"] if b.get("type") == "text")
    except (KeyError, TypeError) as error:
        raise LlmError(f"unexpected response shape: {error}") from error

    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise LlmError("no JSON object in the answer")
    try:
        return Invoice.model_validate(json.loads(text[start:end + 1]))
    except (json.JSONDecodeError, ValidationError) as error:
        raise LlmError(f"answer did not match the invoice format: {error}") from error
