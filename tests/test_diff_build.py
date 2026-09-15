import json
import re
from pathlib import Path

from pipeline import build as build_mod
from pipeline.diff import diff, render
from pipeline.schema import Charity, Dataset, Sourced, Support

ROOT = Path(__file__).resolve().parent.parent


def _c(**kw) -> Charity:
    base = dict(id="a", name="A", url="https://a.org", verified="2026-09-14")
    base.update(kw)
    return Charity(**base).compute_scores()


def test_published_dataset_validates_and_scores_are_consistent():
    ds = build_mod.load("nyc-2026")
    assert len(ds.charities) >= 20
    for c in ds.charities:
        s, t = c.supportScore, c.termsScore
        c.compute_scores()
        assert (s, t) == (c.supportScore, c.termsScore), f"{c.id} scores drifted from raw fields"
        assert c.url.startswith("http")
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", c.verified)
        if c.shortfall.pub:
            assert c.shortfall.quote, f"{c.id}: published shortfall without a quote"


def test_diff_detects_change_new_removed_and_unverified():
    old = Dataset(refreshed="2026-09-07", charities=[_c(id="a", min=3000), _c(id="b", name="B", min=5000)])
    new = Dataset(refreshed="2026-09-14", charities=[
        _c(id="a", min=3500, status="open", flags=["unverified: fee — dropped"]),
        _c(id="c", name="C", min=4000),
    ])
    d = diff(old, new)
    assert ("min", 3000, 3500) in d["changes"]["a"]
    assert ("status", "unknown", "open") in d["changes"]["a"]
    assert d["changes"]["c"][0][0] == "(new charity)"
    assert d["removed"] == ["b"]
    assert "a" in d["unverified"]
    md = render(d, "nyc-2026")
    assert "| A | `min` | 3000 | 3500 |" in md and "removed from seed list" in md and "Dropped as unverifiable" in md


def test_diff_no_changes():
    ds = Dataset(refreshed="x", charities=[_c(min=3000)])
    md = render(diff(ds, ds), "nyc-2026")
    assert "No field changes" in md


def test_build_renders_template_with_data(tmp_path):
    out = build_mod.build("nyc-2026", out=tmp_path / "index.html")
    html = out.read_text()
    assert "__DATA__" not in html
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    data = json.loads(m.group(1))
    assert len(data["charities"]) == len(build_mod.load("nyc-2026").charities)
    assert "<title>Charity Bibs</title>" in html


def test_terms_score_counts_four_things():
    c = _c(shortfall=Sourced(pub=True, text="x", quote="q"), chargeSchedule="May 15", injury=Sourced(pub=True, text="y", quote="q"), deferral=Sourced())
    assert c.termsScore == 3
    c2 = _c(freeExit="2026-07-15")
    assert c2.termsScore == 1


def test_support_score_counts_only_true():
    c = _c(support=Support(coaching=True, group_runs=False, gear=None, bus_to_start=True))
    assert c.supportScore == 2
