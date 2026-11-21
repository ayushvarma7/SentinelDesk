"""Track C owns this file.

Ask Claude for structured JSON, then VERIFY it in code. The prompt is not the
guarantee: every cited id must be in the retrieved set, and any number attached
to a currency symbol, % or time unit that appears in no precedent is flagged.
"""
from __future__ import annotations

from .schema import Precedent


def draft(text: str, language: str, precedents: list[Precedent]) -> dict:
    """Return {"draft": str, "cited_ticket_ids": [...], "unverified_claims": [...]}."""
    raise NotImplementedError("Track C")


def verify_citations(draft_text: str, cited: list[str],
                     precedents: list[Precedent]) -> tuple[list[str], list[str]]:
    """Return (valid_citations, unverified_claims). Pure function, unit-testable."""
    raise NotImplementedError("Track C")
