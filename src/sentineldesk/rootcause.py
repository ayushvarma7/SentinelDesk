"""Track A owns this file. Root-cause grouping, following the ITIL model:

    many Incidents  ->  one Problem (the root cause)  ->  fixed by one or more Changes

Two things per Incident/Problem ticket:
  1. Live grouping: compare with recent live issues; a group of >= ROOT_CAUSE_MIN_GROUP similar issues
     inside ROOT_CAUSE_WINDOW_MIN minutes suggests raising a Problem record (e.g. three different
     "Outlook not receiving mail" tickets).
  2. Known history: the closest historical Problem and Change tickets in the KB, i.e. the probable
     root cause and how it was fixed before.

Uses the same e5 query vectors as the classifier (artifacts/kb_query_embeddings.npy), so nothing
is encoded twice. The dataset has no explicit Incident->Problem links, so thresholds are calibrated
from similarity distributions (see config.py), not from labelled groups.
"""
from __future__ import annotations

import itertools
import time
from collections import deque
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from . import config
from .schema import Precedent, RootCause


# --- known history in the KB -------------------------------------------------------
@lru_cache(maxsize=1)
def _kb_index():
    from .data import load_kb
    kb = load_kb()
    E = np.load(config.KB_QUERY_EMB_PATH)
    ids = np.load(config.KB_QUERY_EMB_PATH.with_name("kb_query_ids.npy"))
    if not np.array_equal(ids, kb["ticket_id"].to_numpy(dtype=str)):
        raise RuntimeError("kb_query_embeddings.npy does not match load_kb(); rerun scripts/train_classifier.py")
    by_type = {t: np.where(kb["type"].to_numpy() == t)[0] for t in ("Problem", "Change")}
    return kb, E, by_type


def _precedent(kb, j: int, score: float) -> Precedent:
    r = kb.iloc[j]
    return Precedent(ticket_id=r["ticket_id"], score=score, subject=r["subject"] or "",
                     body_snippet=str(r["body"])[:200], answer=str(r["answer"]),
                     language=r["language"], queue=r["queue"])


def known_links(qvec: np.ndarray) -> tuple[Precedent | None, Precedent | None]:
    """(closest KB Problem, closest KB Change), each None if below ROOT_CAUSE_LINK_MIN_SIM or no KB."""
    try:
        kb, E, by_type = _kb_index()
    except FileNotFoundError:
        return None, None
    out = []
    for t in ("Problem", "Change"):
        rows = by_type[t]
        s = E[rows] @ np.asarray(qvec, np.float32)
        k = int(s.argmax())
        out.append(_precedent(kb, int(rows[k]), float(s[k])) if s[k] >= config.ROOT_CAUSE_LINK_MIN_SIM else None)
    return out[0], out[1]


# --- live grouping -----------------------------------------------------------------
@dataclass
class _Live:
    ticket_id: str
    vec: np.ndarray
    ts: float
    gid: int


class IncidentGrouper:
    """Single-linkage grouping of recent live issues; groups merge when a new ticket links them."""

    def __init__(self, sim: float = config.ROOT_CAUSE_GROUP_SIM,
                 window_min: float = config.ROOT_CAUSE_WINDOW_MIN,
                 min_group: int = config.ROOT_CAUSE_MIN_GROUP):
        self.sim, self.window_s, self.min_group = sim, window_min * 60, min_group
        self.recent: deque[_Live] = deque()
        self._ids = itertools.count(1)
        self._gids = itertools.count(1)

    def reset(self) -> None:
        self.recent.clear()

    def add(self, vec: np.ndarray, now: float | None = None, ticket_id: str | None = None) -> list[str]:
        """Register a live issue; return the ids of its group (including itself), oldest first."""
        now = time.time() if now is None else now
        while self.recent and now - self.recent[0].ts > self.window_s:
            self.recent.popleft()
        vec = np.asarray(vec, np.float32)
        linked = {r.gid for r in self.recent if float(r.vec @ vec) >= self.sim}
        gid = min(linked) if linked else next(self._gids)
        for r in self.recent:                      # merge every group this ticket bridges
            if r.gid in linked:
                r.gid = gid
        tid = ticket_id or f"LIVE-{next(self._ids):04d}"
        self.recent.append(_Live(tid, vec, now, gid))
        return [r.ticket_id for r in self.recent if r.gid == gid]


GROUPER = IncidentGrouper()


def analyze(qvec: np.ndarray, text: str, now: float | None = None) -> RootCause:
    """Root-cause view for one Incident/Problem ticket: live group + closest known Problem/Change."""
    # too little text ("help", emoji) to say anything about root cause: not grouped
    group = GROUPER.add(qvec, now=now) if len(text.split()) >= config.ROOT_CAUSE_MIN_WORDS else []
    problem, change = known_links(qvec)
    return RootCause(group_ticket_ids=group, suggest_problem=len(group) >= GROUPER.min_group,
                     known_problem=problem, known_change=change)
