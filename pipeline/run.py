"""CLI.

  python -m pipeline.run crawl   --race nyc-2026 [--only tfk,bird]
  python -m pipeline.run extract --race nyc-2026 [--only ...]       (needs ANTHROPIC_API_KEY)
  python -m pipeline.run verify  --race nyc-2026                      → .cache/<race>/candidate.json
  python -m pipeline.run diff    --race nyc-2026                      → .cache/<race>/changes.md
  python -m pipeline.run promote --race nyc-2026                      candidate → data/races/<race>.json
  python -m pipeline.run build   --race nyc-2026                      → site/index.html
  python -m pipeline.run refresh --race nyc-2026                      crawl+extract+verify+diff (what the Action runs)
  python -m pipeline.run stats   --race nyc-2026
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from . import build as build_mod
from . import crawl as crawl_mod
from . import diff as diff_mod
from . import extract as extract_mod
from .schema import Dataset
from .verify import verify

ROOT = Path(__file__).resolve().parent.parent


def race_name(race: str) -> str:
    return yaml.safe_load((ROOT / "data/seeds" / f"{race}.yaml").read_text())["race_name"]


def cmd_verify(race: str) -> Dataset:
    cache_dir = ROOT / ".cache" / race
    existing = {c.id: c for c in build_mod.load(race).charities}
    out = []
    for f in sorted((cache_dir / "extracted").glob("*.json")):
        raw = json.loads(f.read_text())
        cache = json.loads((cache_dir / f"{f.stem}.json").read_text())
        out.append(verify(raw, cache, existing.get(f.stem)))
    # Carry forward charities that were not re-crawled this run, untouched.
    seen = {c.id for c in out}
    out += [c for cid, c in existing.items() if cid not in seen]
    order = [c["id"] for c in yaml.safe_load((ROOT / "data/seeds" / f"{race}.yaml").read_text())["charities"]]
    out.sort(key=lambda c: order.index(c.id) if c.id in order else 999)
    from datetime import date
    ds = Dataset(refreshed=date.today().isoformat(), charities=out)
    (cache_dir / "candidate.json").write_text(ds.model_dump_json(indent=1))
    return ds


def cmd_diff(race: str) -> str:
    cache_dir = ROOT / ".cache" / race
    new = Dataset.model_validate_json((cache_dir / "candidate.json").read_text())
    old = build_mod.load(race)
    md = diff_mod.render(diff_mod.diff(old, new), race)
    (cache_dir / "changes.md").write_text(md)
    return md


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["crawl", "extract", "verify", "diff", "promote", "build", "refresh", "stats"])
    ap.add_argument("--race", default="nyc-2026")
    ap.add_argument("--only", default=None, help="comma-separated charity ids")
    a = ap.parse_args()
    only = set(a.only.split(",")) if a.only else None

    if a.cmd == "crawl":
        crawl_mod.run(a.race, only)
    elif a.cmd == "extract":
        extract_mod.run(a.race, race_name(a.race), only)
    elif a.cmd == "verify":
        ds = cmd_verify(a.race); print(f"candidate: {len(ds.charities)} charities")
    elif a.cmd == "diff":
        print(cmd_diff(a.race))
    elif a.cmd == "promote":
        cand = ROOT / ".cache" / a.race / "candidate.json"
        build_mod.save(a.race, Dataset.model_validate_json(cand.read_text())); print("promoted")
    elif a.cmd == "build":
        print("built", build_mod.build(a.race))
    elif a.cmd == "refresh":
        crawl_mod.run(a.race, only)
        extract_mod.run(a.race, race_name(a.race), only)
        cmd_verify(a.race)
        print(cmd_diff(a.race))
    elif a.cmd == "stats":
        print(json.dumps(build_mod.stats(a.race), indent=1))


if __name__ == "__main__":
    main()
