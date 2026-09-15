"""End-to-end crawl → verify against a local fixture site (no network, no API key).

Proves: Playwright fetch, same-site hop following, PDF text extraction, robots.txt,
and that verify() accepts quotes drawn from a hopped page and a PDF.
"""
import http.server, json, socketserver, threading
from pathlib import Path

import pytest

from pipeline.crawl import crawl_charity, Robots, UA
from pipeline.verify import verify

FIX = Path(__file__).parent / "fixtures" / "site"


@pytest.fixture(scope="module")
def server():
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(FIX), **k)
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True); t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.mark.asyncio
async def test_crawl_follows_hops_reads_pdf_and_verifies(server):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(user_agent=UA)
        result = await crawl_charity(ctx, Robots(), {"id": "fx", "name": "Team Fixture", "urls": [f"{server}/run.html"]})
        await browser.close()
    urls = [pg["url"] for pg in result["pages"]]
    assert f"{server}/run.html" in urls and f"{server}/faq.html" in urls and f"{server}/agreement.pdf" in urls
    assert not any("other-site.example" in u for u in urls)  # off-site hop ignored
    assert result["errors"] == []

    raw = {
        "status": "closed", "status_quote": "Applications are now closed for 2026.",
        "minimum": 4000, "minimum_quote": "Fundraising minimum: $4,000 per runner.", "minimum_source": urls[0], "minimum_note": "",
        "support": {"coaching": True, "group_runs": True, "fundraising_page": True},
        "support_notes": "coach, group runs, page",
        "support_quote": "Runners receive a personal fundraising page, weekly group runs in Central Park, and a dedicated coach.",
        "shortfall_published": True, "shortfall_text": "Card charged Nov 1.",
        "shortfall_quote": "the remaining balance will be charged to the credit card on file", "shortfall_source": f"{server}/faq.html",
        "free_exit_date": "2026-07-15", "free_exit_quote": "Withdraw in writing before July 15, 2026 and the minimum is waived.",
        "injury_published": False, "deferral_published": False, "flags": [],
    }
    c = verify(raw, result, existing=None, verified_on="2026-09-14")
    assert c.min == 4000 and c.status == "closed" and c.supportScore == 3
    assert c.shortfall.pub and c.freeExit == "2026-07-15"   # quote from FAQ hop and from the PDF both verified
    assert c.termsScore == 2 and not any(f.startswith("unverified") for f in c.flags)
