"""Capture NYRR's official charity partner list (hosted on Haku) to build the full seed list.

Run on a laptop with a visible browser window (the site blocks cloud hosts):

    source .venv/bin/activate
    python research/fetch_nyrr_index.py

Writes research/nyrr-index/:
  charities.json   one entry per charity: key, name, blurb, tier, status badge, logo, categories, website, contact html
  responses/       raw HTML fragments the page fetched while paging (for debugging)
  final.png        screenshot
  notes.md         counts and anything that failed

How the page works (from the first capture): 24 cards per page, 28 pages, loaded on scroll
inside a fixed-height box; each card links to a contact modal that holds the website;
the sidebar has Gold/Silver/Bronze tier headers in the list and 13 category filters.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from playwright.async_api import async_playwright

START = "https://events.nyrr.org/events/9c9d0a40e9f5586e44e0/charity_partners"
OUT = Path(__file__).resolve().parent / "nyrr-index"
CARD = ".beneficiary-block"
CATEGORIES = ["Advocacy", "Animal Rights/Welfare", "Arts & Culture", "Education", "Emergency Relief", "Environment",
              "Faith Based/Religion", "Healthcare/Medicine", "International", "Military/Veteran Services", "Research",
              "Social Service", "Sports", "Youth", "Other"]

JS_SCROLLER = """() => {
  const card = document.querySelector('%s'); if (!card) return null;
  let el = card.parentElement;
  while (el && el !== document.body) {
    const s = getComputedStyle(el);
    if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 10) { el.setAttribute('data-cb-scroller','1'); return el.className; }
    el = el.parentElement;
  }
  return null;
}""" % CARD

JS_CARDS = """() => {
  const tierOf = (node) => {
    let n = node;
    while (n) {
      let p = n.previousElementSibling;
      while (p) { const t = (p.innerText||'').trim().split('\\n')[0].trim(); if (/^(gold|silver|bronze)$/i.test(t)) return t; p = p.previousElementSibling; }
      n = n.parentElement;
      if (!n || n === document.body) break;
    }
    return null;
  };
  return Array.from(document.querySelectorAll('%s')).map(b => {
    const a = b.querySelector('a[data-url]');
    const url = a ? a.getAttribute('data-url') : '';
    const key = (url.match(/beneficiary_key=([a-f0-9]+)/) || [])[1] || null;
    const name = (b.querySelector('.cp-list-text') || {}).innerText || '';
    const tip = b.querySelector('[data-original-title]');
    const blurb = tip ? (tip.getAttribute('data-original-title') || tip.getAttribute('title') || '') : '';
    const badge = (b.querySelector('.no-spots-text') || {}).innerText || '';
    const img = b.querySelector('img'); const logo = img ? img.src : '';
    return {key, name: name.trim(), blurb: blurb.trim(), badge: badge.trim(), logo, contact_url: url, tier: tierOf(b)};
  });
}""" % CARD


async def scroll_all(page, label: str, expected: int | None = None) -> int:
    """Scroll the inner list box until no new cards appear. Returns the card count."""
    cls = await page.evaluate(JS_SCROLLER)
    stale, last = 0, -1
    for i in range(400):
        n = await page.evaluate(f"document.querySelectorAll('{CARD}').length")
        if n == last:
            stale += 1
            if stale >= 4:
                break
        else:
            stale, last = 0, n
        if expected and n >= expected:
            break
        if cls is not None:
            await page.evaluate("() => { const el = document.querySelector('[data-cb-scroller]'); el.scrollTop = el.scrollHeight; }")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1200)
        if i % 10 == 9:
            print(f"    {label}: {n} cards so far (scroller: {cls!r})")
    n = await page.evaluate(f"document.querySelectorAll('{CARD}').length")
    print(f"  {label}: {n} cards")
    return n


async def click_text(page, text: str) -> bool:
    loc = page.locator(f"text={text}").first
    try:
        await loc.click(timeout=3000)
        await page.wait_for_timeout(2000)
        return True
    except Exception:
        return False


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "responses").mkdir(exist_ok=True)
    notes: list[str] = ["# NYRR charity index capture (v2)", ""]
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()
        n_resp = 0

        async def on_response(resp):
            nonlocal n_resp
            if "beneficiaries_search" in resp.url or "beneficiary" in resp.url:
                try:
                    body = await resp.text()
                    n_resp += 1
                    (OUT / "responses" / f"{n_resp:04d}.txt").write_text(f"{resp.url}\n\n{body}")
                except Exception:
                    pass
        page.on("response", on_response)

        print(f"opening {START}")
        await page.goto(START, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(4000)
        total_pages = await page.evaluate("(document.getElementById('pagination_data')||{}).getAttribute ? document.getElementById('pagination_data').getAttribute('data-total-pages') : null")
        per_page = await page.evaluate(f"document.querySelectorAll('{CARD}').length")
        expected = int(total_pages) * per_page if total_pages else None
        print(f"pages: {total_pages}, per page: {per_page}, expecting about {expected}")
        notes.append(f"- pages reported: {total_pages}, per page: {per_page}")

        # 1. all charities, all tiers
        await scroll_all(page, "all charities", expected)
        cards = await page.evaluate(JS_CARDS)
        by_key = {c["key"]: c for c in cards if c["key"]}
        print(f"  unique charities: {len(by_key)}")
        notes.append(f"- unique charities captured: {len(by_key)}")
        for c in by_key.values():
            c["categories"] = []

        # 2. categories: click each filter, scroll, record which keys appear, clear
        for cat in CATEGORIES:
            if not await click_text(page, cat):
                print(f"  category '{cat}': not found on page, skipped")
                continue
            n = await scroll_all(page, f"category {cat}")
            keys = [c["key"] for c in await page.evaluate(JS_CARDS) if c["key"]]
            for k in keys:
                if k in by_key:
                    by_key[k]["categories"].append(cat)
                else:
                    c = next(x for x in await page.evaluate(JS_CARDS) if x["key"] == k)
                    c["categories"] = [cat]; by_key[k] = c
            notes.append(f"- {cat}: {len(keys)} charities")
            # clear the filter: click it again, else use CLEAR FILTERS
            if not await click_text(page, cat):
                await click_text(page, "CLEAR FILTERS")
            await page.wait_for_timeout(1500)

        # 3. contact cards → website
        print("fetching contact cards for the website links...")
        base = "https://events.nyrr.org"
        for i, (k, c) in enumerate(by_key.items()):
            try:
                r = await page.request.get(base + c["contact_url"], timeout=20000)
                html = await r.text()
                c["contact_html"] = html
                links = re.findall(r'href="(https?://[^"]+)"', html)
                ext = [u for u in links if "nyrr.org" not in u and "hakuapp" not in u and "google" not in u
                       and not re.search(r"facebook|twitter|instagram|linkedin|youtube|tiktok", u)]
                c["website"] = ext[0] if ext else None
                m = re.search(r"<h\d[^>]*>([^<]{3,120})</h\d>", html)
                c["full_name"] = re.sub(r"\s+", " ", m.group(1)).strip() if m else None
            except Exception as e:  # noqa: BLE001
                c["website"], c["full_name"], c["contact_html"] = None, None, f"FAILED {e}"
            if i % 25 == 0:
                print(f"    {i}/{len(by_key)}")
            await page.wait_for_timeout(300)

        (OUT / "charities.json").write_text(json.dumps(list(by_key.values()), indent=1))
        await page.screenshot(path=str(OUT / "final.png"))
        with_site = sum(1 for c in by_key.values() if c.get("website"))
        with_cat = sum(1 for c in by_key.values() if c.get("categories"))
        notes += [f"- with website: {with_site}", f"- with at least one category: {with_cat}",
                  f"- tiers: {json.dumps({t: sum(1 for c in by_key.values() if c.get('tier') == t) for t in ('Gold', 'Silver', 'Bronze', None)})}"]
        (OUT / "notes.md").write_text("\n".join(notes) + "\n")
        print("\n".join(notes))
        print(f"\nwrote {OUT}/charities.json. Now: git add research/nyrr-index && git commit -m 'Capture NYRR charity index' && git push origin claude/charitybibs-deploy-uz9t8q")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
