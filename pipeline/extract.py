"""Turn cached page text into a structured record with a forced tool call.

The model is required to answer through `record_charity_program`, whose input schema
is in schema.py, so the output is always well-formed JSON. Hallucination is handled
downstream: verify.py drops any field whose quote is not found in the fetched text.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .schema import EXTRACTION_TOOL

DEFAULT_MODEL = os.environ.get("CB_MODEL", "claude-sonnet-4-5")
MAX_CHARS_PER_PAGE = 24_000

SYSTEM = """You extract facts about a marathon charity's runner program from the charity's own web pages.

Rules:
- Report only what the pages say. If a fact is not stated, use null. Never infer, estimate, or assume.
- Every non-null factual field must be accompanied by a VERBATIM quote copied exactly from the page text (same words, same punctuation) and the URL of the page it came from. Fields without an exact quote will be discarded.
- Support fields are true only if the charity says it provides that thing; false only if it explicitly says it does not; otherwise null.
- "shortfall" means what happens if the runner does not raise the minimum. "free_exit_date" is the last date a runner can withdraw without owing the minimum. "charge_schedule" is when money is actually taken (deposits, milestones, final charge).
- The fundraising minimum is the entry-level minimum for a guaranteed charity bib for THIS race and year. Put other tiers and own-bib prices in minimum_note.
- If pages reference a prior year, an old deadline, or contradict each other, say so in flags.
- Prefer the charity's marathon page, FAQ, application, and any runner agreement over press releases."""


def _pages_block(cache: dict) -> str:
    parts = []
    for p in cache["pages"]:
        text = p["text"][:MAX_CHARS_PER_PAGE]
        parts.append(f"<page url=\"{p['url']}\" fetched=\"{p['fetched']}\">\n{text}\n</page>")
    return "\n\n".join(parts)


def extract_one(cache: dict, race_name: str, client=None, model: str = DEFAULT_MODEL) -> dict:
    """Return the raw tool input from the model for one charity."""
    if client is None:
        import anthropic

        client = anthropic.Anthropic()
    user = (
        f"Race: {race_name}\nCharity: {cache['name']} (id: {cache['id']})\n\n"
        f"Pages fetched from the charity's site:\n\n{_pages_block(cache)}\n\n"
        "Record the program using the tool."
    )
    resp = client.messages.create(
        model=model,
        max_tokens=4000,
        system=SYSTEM,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": EXTRACTION_TOOL["name"]},
        messages=[{"role": "user", "content": user}],
    )
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            return dict(block.input)
    raise RuntimeError(f"no tool_use block for {cache['id']}")


def run(race: str, race_name: str, only: set[str] | None = None) -> None:
    root = Path(__file__).resolve().parent.parent
    cache_dir, out_dir = root / ".cache" / race, root / ".cache" / race / "extracted"
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in sorted(cache_dir.glob("*.json")):
        cid = f.stem
        if only and cid not in only:
            continue
        cache = json.loads(f.read_text())
        if not cache["pages"]:
            print(f"  {cid:10} skipped (no pages fetched)")
            continue
        raw = extract_one(cache, race_name)
        (out_dir / f"{cid}.json").write_text(json.dumps(raw, indent=1))
        print(f"  {cid:10} extracted")
