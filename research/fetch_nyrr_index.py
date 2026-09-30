"""Capture NYRR's official charity index so the full seed list can be built from it.

nyrr.org blocks automated fetching from cloud hosts, so run this on a normal laptop with
a visible browser window (it opens one; leave it alone until it finishes):

    source .venv/bin/activate
    python research/fetch_nyrr_index.py

Writes research/nyrr-index/:
  page-N.html      full HTML after each expansion step (for building the parser)
  final.png        screenshot of the fully expanded page
  links.json       every link on the final page with its text and nearest container text
  notes.md         page title, final URL, iframes, and any filter controls found

It does not need to understand the page. It just gets all of it onto disk.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from playwright.async_api import async_playwright

START = "https://events.nyrr.org/events/9c9d0a40e9f5586e44e0/charity_partners"
OUT = Path(__file__).resolve().parent / "nyrr-index"
MORE = re.compile(r"load more|show more|see more|view more|next|more charities", re.I)
MAX_STEPS = 80


async def dismiss_banners(page) -> None:
    for sel in ("button:has-text('Accept')", "button:has-text('I agree')", "button:has-text('Got it')", "button:has-text('OK')"):
        try:
            await page.locator(sel).first.click(timeout=800)
            return
        except Exception:
            pass


async def expand(page, step: int) -> bool:
    """Scroll to the bottom and click one 'load more / next' control if there is one."""
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(1500)
    before = await page.evaluate("document.body.innerText.length")
    buttons = page.locator("button, a[role=button], a")
    n = await buttons.count()
    for i in range(n):
        b = buttons.nth(i)
        try:
            t = (await b.inner_text(timeout=300)).strip()
        except Exception:
            continue
        if MORE.search(t) and len(t) < 40 and await b.is_visible():
            try:
                await b.click(timeout=2000)
                await page.wait_for_timeout(2500)
                after = await page.evaluate("document.body.innerText.length")
                print(f"  step {step}: clicked '{t}' ({before} -> {after} chars)")
                return after != before
            except Exception:
                continue
    return False


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await ctx.new_page()
        print(f"opening {START}")
        await page.goto(START, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(4000)
        await dismiss_banners(page)
        (OUT / "page-0.html").write_text(await page.content())
        for step in range(1, MAX_STEPS + 1):
            grew = await expand(page, step)
            (OUT / f"page-{step}.html").write_text(await page.content())
            if not grew:
                # scroll once more in case content is lazy-loaded without a button
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
                if not await expand(page, step):
                    break
        h = await page.evaluate("Math.min(document.documentElement.scrollHeight, 20000)")
        await page.set_viewport_size({"width": 1280, "height": int(h)})
        await page.screenshot(path=str(OUT / "final.png"))
        links = await page.evaluate(
            """() => Array.from(document.querySelectorAll('a[href]')).map(a => {
                 const box = a.closest('li, article, .card, [class*=card], [class*=item], [class*=charity], div');
                 return {href: a.href, text: (a.innerText || '').trim().slice(0, 120),
                         context: box ? (box.innerText || '').trim().slice(0, 400) : ''};
               })"""
        )
        (OUT / "links.json").write_text(json.dumps(links, indent=1))
        controls = await page.evaluate(
            """() => {
              const out = [];
              for (const s of document.querySelectorAll('select')) out.push('select: ' + [...s.options].map(o => o.textContent.trim()).filter(Boolean).slice(0, 40).join(' | '));
              for (const i of document.querySelectorAll('input')) out.push('input[' + (i.type||'text') + ']: ' + (i.placeholder || i.name || ''));
              for (const l of document.querySelectorAll('label')) { const t = (l.innerText||'').trim(); if (t && t.length < 60) out.push('label: ' + t); }
              return [...new Set(out)].slice(0, 200);
            }"""
        )
        iframes = await page.evaluate("Array.from(document.querySelectorAll('iframe')).map(f => f.src)")
        notes = [f"# NYRR charity index capture", f"- Final URL: {page.url}", f"- Title: {await page.title()}",
                 f"- Links captured: {len(links)}", f"- Iframes: {iframes}", "", "## Controls"] + [f"- {c}" for c in controls]
        (OUT / "notes.md").write_text("\n".join(notes) + "\n")
        print(f"\nwrote {OUT} ({len(links)} links). Now: git add research/nyrr-index && git commit -m 'Capture NYRR charity index' && git push")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
