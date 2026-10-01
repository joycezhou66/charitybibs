"""Turn cached page text into a structured record with a forced tool call.

The model is required to answer through `record_charity_program`, whose input schema
is in schema.py, so the output is always well-formed JSON. Hallucination is handled
downstream: verify.py drops any field whose quote is not found in the fetched text.

Spend control: every call's token usage is priced and accumulated in
.cache/<race>/spend.json. Extraction stops cleanly when CB_BUDGET_USD is reached or
when the API reports the account is out of credit. Everything extracted up to that
point is kept; the rest of the seed list is carried as "listed, not yet read".
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from .schema import EXTRACTION_TOOL

DEFAULT_MODEL = os.environ.get("CB_MODEL", "claude-sonnet-5")
MAX_CHARS_PER_PAGE = 24_000

# USD per million tokens (input, output). Unknown models fall back to the Opus rate
# so the budget stop errs on the side of spending less, never more.
PRICES = {
    "claude-sonnet-5": (2.0, 10.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
FALLBACK_PRICE = (5.0, 25.0)


def price(model: str, input_tokens: int, output_tokens: int) -> float:
    pin, pout = PRICES.get(model, FALLBACK_PRICE)
    return input_tokens / 1e6 * pin + output_tokens / 1e6 * pout


class OutOfCredit(Exception):
    """The API refused the call because the account cannot pay for it."""


def is_billing_error(e: Exception) -> bool:
    msg = str(e).lower()
    return any(k in msg for k in ("credit balance", "insufficient credit", "billing", "out of credit", "payment"))


SYSTEM = """You extract facts about a marathon charity's runner program from the charity's own web pages.

Rules:
- Report only what the pages say. If a fact is not stated, use null. Never infer, estimate, or assume.
- Every non-null factual field must be accompanied by a VERBATIM quote copied exactly from the page text (same words, same punctuation) and the URL of the page it came from. Fields without an exact quote will be discarded.
- Support fields are true only if the charity says it provides that thing; false only if it explicitly says it does not; otherwise null.
- "shortfall" means what happens if the runner does not raise the minimum. "free_exit_date" is the last date a runner can withdraw without owing the minimum. "charge_schedule" is when money is actually taken (deposits, milestones, final charge).
- The fundraising minimum is the entry-level minimum for a guaranteed charity bib for THIS race and year. Put other tiers and own-bib prices in minimum_note.
- When several tiers are listed, the minimum is the LOWEST tier that includes the race entry (words like "we provide the race entry", "guaranteed entry", "charity entry"). A "fundraiser only" / "own entry" / "already have a bib" tier is never the minimum. A team-wide goal, a total the team hopes to raise, or a number for a different race or year is not the minimum: use null and explain in minimum_note.
- If pages reference a prior year, an old deadline, or contradict each other, say so in flags.
- Prefer the charity's marathon page, FAQ, application, and any runner agreement over press releases."""


def _pages_block(cache: dict) -> str:
    parts = []
    for p in cache["pages"]:
        text = p["text"][:MAX_CHARS_PER_PAGE]
        parts.append(f"<page url=\"{p['url']}\" fetched=\"{p['fetched']}\">\n{text}\n</page>")
    return "\n\n".join(parts)


def extract_one(cache: dict, race_name: str, client=None, model: str = DEFAULT_MODEL) -> dict:
    """Return the raw tool input from the model for one charity.

    The returned dict carries a private `_usage` entry {input_tokens, output_tokens, model}
    so callers can meter spend; verify.py ignores it.
    """
    if client is None:
        import anthropic

        client = anthropic.Anthropic()
    user = (
        f"Race: {race_name}\nCharity: {cache['name']} (id: {cache['id']})\n\n"
        f"Pages fetched from the charity's site:\n\n{_pages_block(cache)}\n\n"
        "Record the program using the tool."
    )
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=4000,
            system=SYSTEM,
            tools=[EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": EXTRACTION_TOOL["name"]},
            messages=[{"role": "user", "content": user}],
        )
    except Exception as e:  # noqa: BLE001 — classify, then re-raise
        if is_billing_error(e):
            raise OutOfCredit(str(e)) from e
        raise
    usage = getattr(resp, "usage", None)
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            raw = dict(block.input)
            raw["_usage"] = {
                "model": model,
                "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
                "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
            }
            return raw
    raise RuntimeError(f"no tool_use block for {cache['id']}")


class Spend:
    """Running total for one race, persisted to .cache/<race>/spend.json."""

    def __init__(self, path: Path, budget_usd: float | None):
        self.path = path
        self.budget = budget_usd
        self.data = {"date": date.today().isoformat(), "budget_usd": budget_usd, "total_usd": 0.0,
                     "charities": {}, "stopped": None}
        if path.exists():
            try:
                old = json.loads(path.read_text())
                if old.get("date") == self.data["date"]:
                    self.data = old
                    self.data["budget_usd"] = budget_usd
            except Exception:  # noqa: BLE001 — a corrupt meter must not block a run
                pass

    def add(self, cid: str, usage: dict) -> float:
        cost = price(usage["model"], usage["input_tokens"], usage["output_tokens"])
        self.data["charities"][cid] = {**usage, "usd": round(cost, 4)}
        self.data["total_usd"] = round(sum(c["usd"] for c in self.data["charities"].values()), 4)
        self.save()
        return cost

    def exhausted(self) -> bool:
        return self.budget is not None and self.data["total_usd"] >= self.budget

    def stop(self, reason: str) -> None:
        self.data["stopped"] = reason
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=1))


def budget_from_env() -> float | None:
    v = os.environ.get("CB_BUDGET_USD", "").strip()
    return float(v) if v else None


def force_from_env() -> set[str]:
    v = os.environ.get("CB_FORCE", "").strip()
    return {x.strip() for x in v.split(",") if x.strip()} if v else set()


def run(race: str, race_name: str, only: set[str] | None = None, order: list[str] | None = None,
        client=None, model: str = DEFAULT_MODEL, budget_usd: float | None = None,
        force: set[str] | None = None) -> dict:
    """Extract every crawled charity, in `order` if given, until done or the budget stops us.

    Returns a summary {"extracted": [...], "skipped": [...], "stopped": reason|None}.
    """
    root = Path(__file__).resolve().parent.parent
    cache_dir, out_dir = root / ".cache" / race, root / ".cache" / race / "extracted"
    out_dir.mkdir(parents=True, exist_ok=True)
    spend = Spend(cache_dir / "spend.json", budget_usd if budget_usd is not None else budget_from_env())
    files = {f.stem: f for f in cache_dir.glob("*.json") if f.stem != "spend" and f.stem != "candidate"}
    ids = [i for i in (order or []) if i in files] + sorted(i for i in files if i not in set(order or []))
    force = force if force is not None else force_from_env()
    summary: dict = {"extracted": [], "skipped": [], "stopped": None}
    if spend.data.get("stopped"):
        summary["stopped"] = spend.data["stopped"]
        print(f"  extraction already stopped today: {spend.data['stopped']}")
        return summary
    for cid in ids:
        if only and cid not in only:
            continue
        f = files[cid]
        out = out_dir / f"{cid}.json"
        cache = json.loads(f.read_text())
        fetched = max((p.get("fetched") or "" for p in cache.get("pages") or []), default="")
        if out.exists() and cid not in force:
            try:
                if json.loads(out.read_text()).get("_source_fetched") == fetched:
                    summary["skipped"].append(cid)
                    continue
            except Exception:  # noqa: BLE001 — unreadable output → re-extract
                pass
        if not cache["pages"]:
            print(f"  {cid:10} skipped (no pages fetched)")
            summary["skipped"].append(cid)
            continue
        if spend.exhausted():
            spend.stop(f"budget of ${spend.budget:.2f} reached")
            summary["stopped"] = spend.data["stopped"]
            print(f"  stopping: {summary['stopped']}")
            break
        try:
            raw = extract_one(cache, race_name, client=client, model=model)
        except OutOfCredit as e:
            spend.stop("API account out of credit")
            summary["stopped"] = spend.data["stopped"]
            print(f"  stopping: out of credit ({str(e)[:120]})")
            break
        usage = raw.pop("_usage", None)
        cost = spend.add(cid, usage) if usage else 0.0
        raw["_source_fetched"] = fetched
        out.write_text(json.dumps(raw, indent=1))
        summary["extracted"].append(cid)
        print(f"  {cid:10} extracted  ${cost:.3f}  (run total ${spend.data['total_usd']:.2f})", flush=True)
    return summary
