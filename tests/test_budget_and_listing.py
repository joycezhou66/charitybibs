"""Spend metering, graceful stop on budget or credit, and 'listed, not yet read' rows."""
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline import extract as extract_mod
from pipeline.diff import diff, render
from pipeline.run import LISTED_ONLY, listed_only
from pipeline.schema import Charity, Dataset, EXTRACTION_TOOL

ROOT = Path(__file__).resolve().parent.parent
RACE = "test-budget"


class MeteredClient:
    """Fake API: returns a valid tool call with token usage, or raises a billing error."""

    def __init__(self, fail_after: int | None = None, billing_error: bool = False):
        self.calls, self.fail_after, self.billing_error = 0, fail_after, billing_error
        self.messages = self

    def create(self, **kw):
        self.calls += 1
        if self.billing_error:
            raise RuntimeError("Your credit balance is too low to access the Anthropic API.")
        block = SimpleNamespace(type="tool_use", name=EXTRACTION_TOOL["name"],
                                input={"status": "unknown", "minimum": None, "support": {}, "shortfall_published": False,
                                       "injury_published": False, "deferral_published": False, "flags": []})
        return SimpleNamespace(content=[block], usage=SimpleNamespace(input_tokens=20_000, output_tokens=1_000))


@pytest.fixture
def cache_dir():
    d = ROOT / ".cache" / RACE
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    for cid in ("a", "b", "c"):
        (d / f"{cid}.json").write_text(json.dumps({"id": cid, "name": cid.upper(),
                                                   "pages": [{"url": f"https://{cid}.org", "text": "x", "fetched": "2026-09-30"}], "errors": []}))
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_price_uses_model_table_and_conservative_fallback():
    assert extract_mod.price("claude-sonnet-5", 1_000_000, 0) == 2.0
    assert extract_mod.price("claude-opus-5", 0, 1_000_000) == 25.0
    assert extract_mod.price("some-future-model", 1_000_000, 0) == extract_mod.FALLBACK_PRICE[0]


def test_extraction_stops_at_budget_and_keeps_what_was_done(cache_dir):
    # Each call costs 20k in + 1k out on sonnet-5 = $0.05. Budget $0.06 → 2 charities, then stop.
    fc = MeteredClient()
    s = extract_mod.run(RACE, "Test Race", order=["a", "b", "c"], client=fc, model="claude-sonnet-5", budget_usd=0.06)
    assert s["extracted"] == ["a", "b"] and s["stopped"].startswith("budget")
    spend = json.loads((cache_dir / "spend.json").read_text())
    assert spend["total_usd"] == pytest.approx(0.10, abs=1e-6) and spend["stopped"].startswith("budget")
    assert (cache_dir / "extracted" / "a.json").exists() and not (cache_dir / "extracted" / "c.json").exists()
    assert "_usage" not in json.loads((cache_dir / "extracted" / "a.json").read_text())


def test_out_of_credit_stops_cleanly_without_crashing(cache_dir):
    s = extract_mod.run(RACE, "Test Race", order=["a", "b"], client=MeteredClient(billing_error=True), model="claude-sonnet-5")
    assert s["extracted"] == [] and s["stopped"] == "API account out of credit"
    assert not (cache_dir / "extracted" / "a.json").exists()


def test_extraction_follows_seed_order_and_skips_fresh_outputs(cache_dir):
    fc = MeteredClient()
    s = extract_mod.run(RACE, "Test Race", order=["c", "a", "b"], client=fc, model="claude-sonnet-5")
    assert s["extracted"] == ["c", "a", "b"]
    s2 = extract_mod.run(RACE, "Test Race", order=["c", "a", "b"], client=fc, model="claude-sonnet-5")
    assert s2["extracted"] == [] and s2["skipped"] == ["c", "a", "b"] and fc.calls == 3
    # a fresher crawl of one charity invalidates only that extraction
    d = json.loads((cache_dir / "a.json").read_text()); d["pages"][0]["fetched"] = "2026-10-01"
    (cache_dir / "a.json").write_text(json.dumps(d))
    s3 = extract_mod.run(RACE, "Test Race", order=["c", "a", "b"], client=fc, model="claude-sonnet-5")
    assert s3["extracted"] == ["a"] and fc.calls == 4
    assert "_source_fetched" in json.loads((cache_dir / "extracted" / "a.json").read_text())


def test_crawl_cache_freshness_window(tmp_path):
    from datetime import date, timedelta
    from pipeline.crawl import _fresh
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"pages": [{"fetched": date.today().isoformat()}]}))
    assert _fresh(p, 3)
    p.write_text(json.dumps({"pages": [{"fetched": (date.today() - timedelta(days=5)).isoformat()}]}))
    assert not _fresh(p, 3)
    p.write_text(json.dumps({"pages": []}))
    assert not _fresh(p, 3)


def test_listed_only_row_is_valid_and_flagged():
    c = listed_only({"id": "z", "name": "Zeta Fund", "cause": "Cancer", "urls": ["https://zeta.org/run"]}, "2026-09-30")
    assert c.min is None and c.status == "unknown" and c.supportScore == 0 and c.termsScore == 0
    assert c.cause == "Cancer" and c.url == "https://zeta.org/run" and LISTED_ONLY in c.flags
    d = listed_only({"id": "y", "name": "Y", "urls": [], "level": "Bronze"}, "2026-09-30", fallback_url="https://list.example/")
    assert d.url == "https://list.example/" and d.level == "Bronze"


def test_diff_collapses_new_charities_and_reports_unread():
    old = Dataset(refreshed="2026-09-14", charities=[Charity(id="a", name="A", url="https://a.org", verified="2026-09-14", min=3000)])
    new = Dataset(refreshed="2026-09-30", charities=[
        Charity(id="a", name="A", url="https://a.org", verified="2026-09-30", min=3500),
        Charity(id="b", name="B", url="https://b.org", verified="2026-09-30", min=4000),
        Charity(id="z", name="Z", url="https://z.org", verified="2026-09-30", flags=[LISTED_ONLY]),
    ])
    d = diff(old, new)
    assert d["unread"] == ["z"]
    md = render(d, "nyc-2026", spend={"total_usd": 1.2345, "charities": {"a": {}, "b": {}}, "stopped": "budget of $1.20 reached"})
    assert "API spend this run: **$1.23** across 2 charities (budget of $1.20 reached)" in md
    assert "**1 charities changed**, 2 added" in md
    assert "| A | `min` | 3000 | 3500 |" in md
    assert "<details><summary>2 charities added" in md and "- Z (not yet read)" in md and "- B\n" in md
    assert "**1 charities are listed but not yet read.**" in md


def test_refresh_stops_starting_chunks_after_time_limit(monkeypatch):
    from pipeline import run as run_mod
    calls = []
    monkeypatch.setattr(run_mod.crawl_mod, "run", lambda race, only: calls.append(("crawl", sorted(only))))
    monkeypatch.setattr(run_mod.extract_mod, "run", lambda race, rn, only, order=None: (calls.append(("extract", sorted(only))) or {"extracted": list(only), "skipped": [], "stopped": None}))
    monkeypatch.setattr(run_mod, "seeds", lambda race: {"race_name": "T", "charities": [{"id": f"c{i}", "name": f"C{i}", "urls": []} for i in range(25)]})
    monkeypatch.setattr(run_mod, "cmd_verify", lambda race: calls.append(("verify", [])))
    monkeypatch.setattr(run_mod, "cmd_diff", lambda race: "diff")
    clock = iter([0.0, 0.0, 0.0, 1000.0, 1000.0])  # first chunk starts at 0s, second at 0s, third sees 1000s elapsed
    monkeypatch.setattr(run_mod.time, "monotonic", lambda: next(clock, 1000.0))
    run_mod.cmd_refresh("t", None, "all", limit_min=10)
    kinds = [k for k, _ in calls]
    assert kinds.count("crawl") == 2 and kinds.count("extract") == 2 and kinds[-1] == "verify"


def test_pdf_size_guard():
    from pipeline.crawl import pdf_text, PDF_MAX_BYTES
    with pytest.raises(ValueError):
        pdf_text(b"%PDF-" + b"0" * (PDF_MAX_BYTES + 1))


def test_charity_crawl_hard_cap_keeps_pages_fetched_so_far(monkeypatch, tmp_path):
    import asyncio
    from pipeline import crawl as crawl_mod

    async def slow_fetch(context, url):
        if url.endswith("/fast"):
            return "fast page text", ["https://x.org/slow"]
        await asyncio.sleep(10)
        return "never", []
    monkeypatch.setattr(crawl_mod, "fetch_page", slow_fetch)
    monkeypatch.setattr(crawl_mod, "CHARITY_TIMEOUT_S", 1)
    monkeypatch.setattr(crawl_mod, "DELAY_S", 0)
    monkeypatch.setattr(crawl_mod.Robots, "allowed", lambda self, url: True)

    class Ctx:
        pages = []

    async def run():
        acc = {"pages": [], "errors": []}
        try:
            await asyncio.wait_for(crawl_mod.crawl_charity(Ctx(), crawl_mod.Robots(), {"id": "x", "name": "X", "urls": ["https://x.org/fast"]}, acc), crawl_mod.CHARITY_TIMEOUT_S)
        except asyncio.TimeoutError:
            return acc
        return None
    acc = asyncio.run(run())
    assert acc is not None and len(acc["pages"]) == 1 and acc["pages"][0]["text"] == "fast page text"


def test_seed_builder_is_idempotent(tmp_path, monkeypatch):
    from pipeline import seeds_from_index as sb
    cap = [{"key": "k9", "name": "Beta Inc", "blurb": "", "tier": "BRONZE", "categories": [],
            "contact_html": '<span class="charity-name">Beta Inc</span>'},   # NYRR duplicate of k2, must not become a second row
           {"key": "k1", "name": "Alpha Fund", "blurb": "Alpha helps.", "tier": "BRONZE", "categories": ["Youth"],
            "contact_html": '<span class="charity-name">Alpha Fund</span><a href="https://alpha.org/run" class="website-text">x</a>'},
           {"key": "k2", "name": "Beta Inc", "blurb": "", "tier": "SILVER", "categories": ["Research"],
            "contact_html": '<span class="charity-name">Beta Inc</span>'}]
    capture = tmp_path / "charities.json"; capture.write_text(json.dumps(cap))
    seeds = tmp_path / "seeds.yaml"
    seeds.write_text("race: t\nrace_name: T\ncharities:\n- id: alpha\n  name: Alpha Fund (old name)\n  urls: [https://alpha.org/marathon]\n")
    monkeypatch.setattr(sb, "CAPTURE", capture); monkeypatch.setattr(sb, "SEEDS", seeds)
    r1 = sb.build(); r2 = sb.build(); r3 = sb.build()
    import yaml
    ids = [s["id"] for s in yaml.safe_load(seeds.read_text())["charities"]]
    assert r1["new"] == 1 and r2["new"] == 0 and r3["new"] == 0
    assert len(ids) == len(set(ids)) == 2 and ids[0] == "alpha"


def test_force_re_extracts_a_cached_charity(cache_dir):
    fc = MeteredClient()
    extract_mod.run(RACE, "Test Race", order=["a", "b"], client=fc, model="claude-sonnet-5")
    s = extract_mod.run(RACE, "Test Race", order=["a", "b"], client=fc, model="claude-sonnet-5", force={"b"})
    assert s["extracted"] == ["b"] and s["skipped"] == ["a"] and fc.calls == 3
