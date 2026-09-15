"""Render site/index.html from site/template.html + data/races/<race>.json.

Scores are recomputed here from the raw fields, so they can never drift from the data.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from .schema import Dataset

ROOT = Path(__file__).resolve().parent.parent


def load(race: str) -> Dataset:
    return Dataset.model_validate_json((ROOT / "data/races" / f"{race}.json").read_text())


def save(race: str, ds: Dataset) -> None:
    for c in ds.charities:
        c.compute_scores()
    (ROOT / "data/races" / f"{race}.json").write_text(ds.model_dump_json(indent=1))


def build(race: str, out: Path | None = None) -> Path:
    ds = load(race)
    for c in ds.charities:
        c.compute_scores()
    template = (ROOT / "site/template.html").read_text()
    if "__DATA__" not in template:
        raise RuntimeError("template.html has no __DATA__ placeholder")
    html = template.replace("__DATA__", ds.model_dump_json())
    out = out or ROOT / "site/index.html"
    out.write_text(html)
    sm = ROOT / "site/sitemap.xml"
    if sm.exists():
        sm.write_text(re.sub(r"<lastmod>[^<]*</lastmod>", f"<lastmod>{date.today().isoformat()}</lastmod>", sm.read_text()))
    return out


def stats(race: str) -> dict:
    ds = load(race)
    cs = ds.charities
    return {
        "charities": len(cs),
        "open": sum(c.status == "open" for c in cs),
        "coaching": sum(c.support.coaching is True for c in cs),
        "shortfall_published": sum(c.shortfall.pub for c in cs),
        "free_exit_published": sum(bool(c.freeExit) for c in cs),
        "min_range": (min(c.min for c in cs if c.min), max(c.min for c in cs if c.min)),
        "support_scores": sorted(c.supportScore for c in cs),
    }
