"""Retry the NYRR contact cards that timed out during the index capture.

Run on the laptop after fetch_nyrr_index.py:

    source .venv/bin/activate
    python research/fetch_nyrr_contacts.py

Reads research/nyrr-index/charities.json, re-fetches every entry whose contact_html
starts with FAILED (slowly, with backoff), and writes the file back. Safe to re-run.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "https://events.nyrr.org"
START = "https://events.nyrr.org/events/9c9d0a40e9f5586e44e0/charity_partners"
PATH = Path(__file__).resolve().parent / "nyrr-index" / "charities.json"


async def main() -> None:
    items = json.loads(PATH.read_text())
    todo = [c for c in items if not c.get("contact_html") or str(c["contact_html"]).startswith("FAILED")]
    print(f"{len(todo)} of {len(items)} contact cards to fetch")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()
        await page.goto(START, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        delay, done = 1.0, 0
        for i, c in enumerate(todo):
            for attempt in range(4):
                try:
                    r = await page.request.get(BASE + c["contact_url"], timeout=45000)
                    html = await r.text()
                    if r.status != 200 or "charity-name" not in html:
                        raise RuntimeError(f"status {r.status}")
                    c["contact_html"] = html
                    m = re.search(r'href="(https?://[^"]+)"[^>]*class="[^"]*website-text', html)
                    c["website"] = m.group(1) if m else None
                    done += 1
                    delay = max(1.0, delay * 0.9)
                    break
                except Exception as e:  # noqa: BLE001
                    delay = min(30.0, delay * 2)
                    print(f"  {c['name'][:30]:30} attempt {attempt + 1} failed ({str(e)[:60]}); waiting {delay:.0f}s")
                    await page.wait_for_timeout(int(delay * 1000))
            await page.wait_for_timeout(int(delay * 1000))
            if i % 20 == 19:
                PATH.write_text(json.dumps(items, indent=1))
                print(f"  {i + 1}/{len(todo)} ({done} fetched)")
        await browser.close()
    PATH.write_text(json.dumps(items, indent=1))
    still = sum(1 for c in items if str(c.get("contact_html", "")).startswith("FAILED"))
    print(f"done: {done} fetched, {still} still failing. Now: git add research/nyrr-index && git commit -m 'Fill NYRR contact cards' && git push origin claude/charitybibs-deploy-uz9t8q")


if __name__ == "__main__":
    asyncio.run(main())
