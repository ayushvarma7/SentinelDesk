"""Pure text helpers. No pandas, no models — safe to import from anywhere."""
from __future__ import annotations


def build_text(subject: str | None, body: str | None) -> str:
    """The one place ticket text is assembled.

    14% of tickets have no subject (16% of English ones), so this must never
    assume either field is present.
    """
    return f"{(subject or '').strip()}\n{(body or '').strip()}".strip()
