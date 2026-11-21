"""Mask PII before any text leaves the machine for an external LLM API."""
from __future__ import annotations

import re

PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "ip": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b"),
    "card": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    "phone": re.compile(r"(?<!\d)(?:\+\d{1,3}[ -]?)?(?:\(\d{2,4}\)[ -]?)?\d{3,4}[ -]?\d{3,4}(?!\d)"),
    "account": re.compile(r"\b(?:acct|account|konto|kundennummer)[ #:]*([A-Z0-9-]{5,})\b", re.I),
}

# Order matters: email before phone, or the digits inside an address get eaten.
ORDER = ["email", "iban", "card", "ip", "account", "phone"]


def mask(text: str) -> tuple[str, dict[str, int]]:
    """Return (masked_text, {kind: count}). Counts only non-zero kinds."""
    counts: dict[str, int] = {}
    out = text
    for kind in ORDER:
        out, n = PATTERNS[kind].subn(f"[{kind.upper()}_REDACTED]", out)
        if n:
            counts[kind] = n
    return out, counts
