"""Enforce provenance: a claimed fact survives only if its quote appears in the fetched text.

This is the step that makes LLM extraction publishable. The model may misread a page;
it cannot invent a number that passes here, because the quote it supplies must be found
(after whitespace/punctuation normalisation, or at ≥ FUZZY_MIN similarity over a sliding
window) in the text we actually downloaded.

Input: raw tool output from extract.py + the crawl cache. Output: a `Charity` record.
"""
from __future__ import annotations

import difflib
import re
from datetime import date

from .schema import Charity, Sourced, Support, SUPPORT_KEYS

FUZZY_MIN = 0.92

_norm_map = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", " ": " ",
})


def normalize(s: str) -> str:
    s = (s or "").translate(_norm_map).lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def quote_found(quote: str | None, corpus: str) -> bool:
    if not quote:
        return False
    q, c = normalize(quote), normalize(corpus)
    if len(q) < 8:
        return False
    if q in c:
        return True
    # sliding-window fuzzy match for minor OCR/markup differences
    w = len(q)
    step = max(1, w // 4)
    best = 0.0
    for i in range(0, max(1, len(c) - w + 1), step):
        r = difflib.SequenceMatcher(None, q, c[i:i + w]).ratio()
        if r > best:
            best = r
            if best >= FUZZY_MIN:
                return True
    return False


def _corpus(cache: dict) -> str:
    return "\n".join(p["text"] for p in cache["pages"])


def _sourced(pub: bool, text: str | None, quote: str | None, source: str | None,
             corpus: str, field: str, flags: list[str], method: str = "page") -> Sourced:
    if not pub:
        return Sourced()
    if quote_found(quote, corpus):
        return Sourced(pub=True, text=text or "", quote=quote, source=source, method=method)
    flags.append(f"unverified: {field} (quote not found in fetched pages) — dropped")
    return Sourced()


def verify(raw: dict, cache: dict, existing: Charity | None, verified_on: str | None = None) -> Charity:
    corpus = _corpus(cache)
    flags: list[str] = list(raw.get("flags") or [])
    urls = [p["url"] for p in cache["pages"]]
    today = verified_on or date.today().isoformat()

    def keep(value, quote, field):
        """Return value if its quote verifies, else None (and flag)."""
        if value is None:
            return None
        if quote_found(quote, corpus):
            return value
        flags.append(f"unverified: {field} — dropped")
        return None

    minimum = keep(raw.get("minimum"), raw.get("minimum_quote"), "minimum")
    fee = keep(raw.get("fee_amount"), raw.get("fee_quote"), "fee")
    deadline = keep(raw.get("deadline"), raw.get("deadline_quote"), "deadline")
    free_exit = keep(raw.get("free_exit_date"), raw.get("free_exit_quote"), "free_exit_date")
    charge = keep(raw.get("charge_schedule"), raw.get("charge_schedule_quote"), "charge_schedule")
    status = raw.get("status") or "unknown"
    if status != "unknown" and not quote_found(raw.get("status_quote"), corpus):
        flags.append("unverified: status — set to unknown")
        status = "unknown"

    sup_raw = raw.get("support") or {}
    support = Support(**{k: sup_raw.get(k) for k, _ in SUPPORT_KEYS})
    support_quote = raw.get("support_quote")
    if any(getattr(support, k) is True for k, _ in SUPPORT_KEYS) and not quote_found(support_quote, corpus):
        # Support claims need at least one verifiable sentence behind them.
        flags.append("unverified: support quote not found — support fields cleared")
        support = Support()
        support_quote = None

    shortfall = _sourced(bool(raw.get("shortfall_published")), raw.get("shortfall_text"),
                         raw.get("shortfall_quote"), raw.get("shortfall_source"), corpus, "shortfall", flags)
    injury = _sourced(bool(raw.get("injury_published")), raw.get("injury_text"),
                      raw.get("injury_quote"), raw.get("injury_source"), corpus, "injury", flags)
    deferral = _sourced(bool(raw.get("deferral_published")), raw.get("deferral_text"),
                        raw.get("deferral_quote"), raw.get("deferral_source"), corpus, "deferral", flags)

    ch = Charity(
        id=cache["id"], name=cache["name"],
        cause=(existing.cause if existing else None), focus=(existing.focus if existing else None),
        level=raw.get("level"), platform=raw.get("platform"), status=status, spots=raw.get("spots"),
        min=minimum, minNote=raw.get("minimum_note") or "", minSource=raw.get("minimum_source") or (urls[0] if urls else None),
        minQuote=raw.get("minimum_quote") if minimum is not None else None,
        fee=fee, feeLabel=raw.get("fee_label"), feeCreditable=raw.get("fee_counts_toward_minimum") if fee else None,
        regSeparate=raw.get("registration_separate") if quote_found(raw.get("registration_quote"), corpus) else None,
        deadline=deadline,
        support=support, supportNotes=raw.get("support_notes") or "", supportQuote=support_quote,
        supportSource=raw.get("support_source") or (urls[0] if urls else None),
        shortfall=shortfall, chargeSchedule=charge, freeExit=free_exit,
        freeExitQuote=raw.get("free_exit_quote") if free_exit else None,
        injury=injury, deferral=deferral,
        url=(existing.url if existing else (urls[0] if urls else "")),
        verified=today, flags=flags,
    ).compute_scores()

    # Never let a failed crawl silently blank a previously-verified minimum.
    if ch.min is None and existing and existing.min is not None:
        ch.min, ch.minNote, ch.minSource = existing.min, existing.minNote, existing.minSource
        ch.flags.append(f"minimum carried over from {existing.verified}; not re-verified this run")
    return ch
