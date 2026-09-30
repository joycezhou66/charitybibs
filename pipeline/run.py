"""CLI.

  python -m pipeline.run crawl   --race nyc-2026 [--only tfk,bird]
  python -m pipeline.run extract --race nyc-2026 [--only ...]       (needs ANTHROPIC_API_KEY)
  python -m pipeline.run verify  --race nyc-2026                      → .cache/<race>/candidate.json
  python -m pipeline.run diff    --race nyc-2026                      → .cache/<race>/changes.md
  python -m pipeline.run promote --race nyc-2026                      candidate → data/races/<race>.json
  python -m pipeline.run prune   --race nyc-2026                      drop published rows no longer in the seed list
  python -m pipeline.run build   --race nyc-2026                      → site/index.html
  python -m pipeline.run refresh --race nyc-2026 [--scope all|core]   crawl+extract+verify+diff (what the Action runs)
  python -m pipeline.run stats   --race nyc-2026

`refresh` works through the seed list in chunks: crawl a chunk, extract it, check the
spend meter, continue. When the budget (CB_BUDGET_USD) or the account's credit runs
out, it stops crawling too, so no time is spent fetching pages we cannot afford to read.
Every seed charity that was not read this run is still carried into the candidate: with
its previous verified record if it has one, otherwise as a "listed, not yet read" row.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date
from pathlib import Path

import yaml

from . import build as build_mod
from . import crawl as crawl_mod
from . import diff as diff_mod
from . import extract as extract_mod
from .schema import Charity, Dataset
from .verify import verify

ROOT = Path(__file__).resolve().parent.parent
CHUNK = 10
LISTED_ONLY = "listed only: pages not yet read"


def seeds(race: str) -> dict:
    return yaml.safe_load((ROOT / "data/seeds" / f"{race}.yaml").read_text())


def race_name(race: str) -> str:
    return seeds(race)["race_name"]


def listed_only(seed: dict, today: str, fallback_url: str = "") -> Charity:
    """A row for a charity we know exists (from the official list) but have not read.
    With no website of its own, it links to the official list it came from."""
    return Charity(
        id=seed["id"], name=seed["name"], cause=seed.get("cause"), focus=seed.get("focus"),
        level=seed.get("level"), url=seed["urls"][0] if seed.get("urls") else fallback_url,
        verified=today, flags=[LISTED_ONLY],
    ).compute_scores()


def scope_ids(race: str, scope: str) -> set[str] | None:
    """`all` → every seed. `core` → charities we have actually read before and that are
    not closed, i.e. the ones whose status or terms can still change for a runner."""
    if scope == "all":
        return None
    existing = {c.id: c for c in build_mod.load(race).charities}
    return {cid for cid, c in existing.items() if LISTED_ONLY not in c.flags and c.status != "closed"}


def cmd_verify(race: str) -> Dataset:
    cache_dir = ROOT / ".cache" / race
    sd = seeds(race)
    seed_by_id = {s["id"]: s for s in sd["charities"]}
    existing = {c.id: c for c in build_mod.load(race).charities}
    today = date.today().isoformat()
    out = []
    for f in sorted((cache_dir / "extracted").glob("*.json")):
        raw = json.loads(f.read_text())
        cache = json.loads((cache_dir / f"{f.stem}.json").read_text())
        ch = verify(raw, cache, existing.get(f.stem))
        s = seed_by_id.get(f.stem, {})
        ch.cause = ch.cause or s.get("cause")
        ch.focus = ch.focus or s.get("focus")
        ch.level = ch.level or s.get("level")
        out.append(ch)
    # Carry forward charities that were not re-read this run, untouched, as long as they
    # are still on the seed list; a charity removed from the seeds drops out (the diff says so).
    seen = {c.id for c in out}
    out += [c for cid, c in existing.items() if cid not in seen and cid in seed_by_id]
    seen |= set(existing)
    # Seed charities never read: list them so the site is complete, marked as unread.
    fallback = sd.get("official_list", "")
    out += [listed_only(s, today, fallback) for s in sd["charities"] if s["id"] not in seen]
    order = [s["id"] for s in sd["charities"]]
    out.sort(key=lambda c: order.index(c.id) if c.id in order else 999)
    ds = Dataset(refreshed=today, charities=out)
    (cache_dir / "candidate.json").write_text(ds.model_dump_json(indent=1))
    return ds


def cmd_diff(race: str) -> str:
    cache_dir = ROOT / ".cache" / race
    new = Dataset.model_validate_json((cache_dir / "candidate.json").read_text())
    old = build_mod.load(race)
    spend = None
    if (cache_dir / "spend.json").exists():
        spend = json.loads((cache_dir / "spend.json").read_text())
    md = diff_mod.render(diff_mod.diff(old, new), race, spend=spend)
    (cache_dir / "changes.md").write_text(md)
    return md


def time_limit_min() -> float | None:
    """CB_TIME_LIMIT_MIN: stop starting new chunks after this many minutes so the run
    always reaches verify/diff/promote before the Action's job timeout kills it."""
    v = os.environ.get("CB_TIME_LIMIT_MIN", "").strip()
    return float(v) if v else None


def cmd_refresh(race: str, only: set[str] | None, scope: str, limit_min: float | None = None) -> None:
    ids = [s["id"] for s in seeds(race)["charities"]]
    allowed = only if only is not None else scope_ids(race, scope)
    if allowed is not None:
        ids = [i for i in ids if i in allowed]
    rn = race_name(race)
    limit = limit_min if limit_min is not None else time_limit_min()
    t0 = time.monotonic()
    print(f"refresh {race}: {len(ids)} charities, scope={scope}, chunk={CHUNK}, time limit={limit or 'none'} min", flush=True)
    done = 0
    for i in range(0, len(ids), CHUNK):
        elapsed = (time.monotonic() - t0) / 60
        if limit is not None and elapsed >= limit:
            print(f"time limit of {limit:.0f} min reached after {done} charities; the rest stay listed as not yet read")
            break
        chunk = ids[i:i + CHUNK]
        crawl_mod.run(race, set(chunk))
        summary = extract_mod.run(race, rn, set(chunk), order=chunk)
        done += len(summary["extracted"]) + len(summary["skipped"])
        if summary["stopped"]:
            print(f"stopped after {done} charities: {summary['stopped']}")
            break
    cmd_verify(race)
    print(cmd_diff(race))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["crawl", "extract", "verify", "diff", "promote", "prune", "build", "refresh", "stats"])
    ap.add_argument("--race", default="nyc-2026")
    ap.add_argument("--only", default=None, help="comma-separated charity ids")
    ap.add_argument("--scope", default="all", choices=["all", "core"], help="refresh: which charities to re-read")
    a = ap.parse_args()
    only = set(a.only.split(",")) if a.only else None

    if a.cmd == "crawl":
        crawl_mod.run(a.race, only)
    elif a.cmd == "extract":
        order = [s["id"] for s in seeds(a.race)["charities"]]
        extract_mod.run(a.race, race_name(a.race), only, order=order)
    elif a.cmd == "verify":
        ds = cmd_verify(a.race); print(f"candidate: {len(ds.charities)} charities")
    elif a.cmd == "diff":
        print(cmd_diff(a.race))
    elif a.cmd == "prune":
        ds = build_mod.load(a.race)
        keep = {s["id"] for s in seeds(a.race)["charities"]}
        dropped = [c.id for c in ds.charities if c.id not in keep]
        ds.charities = [c for c in ds.charities if c.id in keep]
        build_mod.save(a.race, ds); print(f"pruned {len(dropped)} rows not in the seed list: {dropped}")
    elif a.cmd == "promote":
        cand = ROOT / ".cache" / a.race / "candidate.json"
        build_mod.save(a.race, Dataset.model_validate_json(cand.read_text())); print("promoted")
    elif a.cmd == "build":
        print("built", build_mod.build(a.race))
    elif a.cmd == "refresh":
        cmd_refresh(a.race, only, a.scope)
    elif a.cmd == "stats":
        print(json.dumps(build_mod.stats(a.race), indent=1))


if __name__ == "__main__":
    main()
