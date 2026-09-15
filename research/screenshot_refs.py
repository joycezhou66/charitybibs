"""Screenshot marathon charity-partner pages for design research.

Run from the repo root on a machine with normal internet access:

    source .venv/bin/activate
    python research/screenshot_refs.py

Writes research/refs/<name>.png (full page, 1280px wide, capped at 6000px tall) and
research/refs/summary.md with each page's final URL, title, and any filter/search
controls found (select options, search boxes, buttons with filter-ish text).
Failures are recorded, not fatal.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path(__file__).resolve().parent / "refs"

PAGES = [
    ("nyrr-haku", "https://events.hakuapp.com/events/c2b58e81f40eb6b89afd/charity_partners"),
    ("nyrr-run-with-charity", "https://www.nyrr.org/run/run-with-charity"),
    ("boston-baa", "https://www.baa.org/races/boston-marathon/charity/"),
    ("chicago", "https://www.chicagomarathon.com/runner-information/charity-program/"),
    ("london-tcs", "https://www.tcslondonmarathon.com/enter/how-to-enter/charity-entry"),
    ("london-realbuzz", "https://www.realbuzz.com/charity-places/"),
    ("berlin", "https://www.bmw-berlin-marathon.com/en/registration/charity/"),
    ("tokyo", "https://www.marathon.tokyo/en/participants/charity/"),
    ("marine-corps", "https://www.marinemarathon.com/marine-corps-marathon/charity-partners/"),
    ("los-angeles", "https://www.lamarathon.com/charity"),
    ("houston", "https://www.chevronhoustonmarathon.com/run-for-a-reason/"),
    ("philadelphia", "https://www.philadelphiamarathon.com/charity-program"),
    ("twin-cities", "https://www.tcmevents.org/charity"),
    ("honolulu", "https://www.honolulumarathon.org/key-information/official-charity-partners"),
    ("rundisney", "https://www.rundisney.com/events/disneyworld/disneyworld-marathon-weekend/charity/"),
    ("big-sur", "https://www.bigsurmarathon.org/charity/"),
    ("rock-n-roll", "https://www.runrocknroll.com/charity"),
    ("sydney", "https://www.sydneymarathon.com/charity"),
]

FILTERISH = re.compile(r"filter|sort|search|cause|category|minimum|all charities|show", re.I)


async def capture(page, name: str, url: str) -> str:
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(2500)
        # dismiss the most common cookie banners
        for sel in ("button:has-text('Accept')", "button:has-text('I agree')", "button:has-text('OK')", "button:has-text('Got it')"):
            try:
                await page.locator(sel).first.click(timeout=800)
                break
            except Exception:
                pass
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1200)
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(500)
        h = await page.evaluate("Math.min(document.documentElement.scrollHeight, 6000)")
        await page.set_viewport_size({"width": 1280, "height": int(h)})
        await page.screenshot(path=str(OUT / f"{name}.png"), full_page=False)
        title = await page.title()
        controls = await page.evaluate(
            """() => {
              const out = [];
              for (const s of document.querySelectorAll('select')) {
                const opts = [...s.options].map(o => o.textContent.trim()).filter(Boolean).slice(0, 12);
                out.push('select: ' + opts.join(' | '));
              }
              for (const i of document.querySelectorAll('input[type=search], input[placeholder*="earch" i]')) out.push('search box: ' + (i.placeholder || ''));
              for (const b of document.querySelectorAll('button, [role=tab], a')) {
                const t = (b.textContent || '').trim();
                if (t && t.length < 40 && /filter|sort|cause|category|all charities|a-z|alphabet/i.test(t)) out.push('control: ' + t);
              }
              return [...new Set(out)].slice(0, 30);
            }"""
        )
        n_links = await page.evaluate("document.querySelectorAll('a[href]').length")
        n_imgs = await page.evaluate("document.querySelectorAll('img').length")
        lines = [f"## {name}", f"- URL: {page.url}", f"- Title: {title}", f"- Links: {n_links}, images: {n_imgs}"]
        lines += [f"- {c}" for c in controls] or ["- (no filter/search controls detected)"]
        return "\n".join(lines) + "\n"
    except Exception as e:  # noqa: BLE001
        return f"## {name}\n- URL: {url}\n- FAILED: {type(e).__name__}: {str(e)[:200]}\n"


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = ["# Marathon charity-list pages, captured for design research", ""]
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900}, user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"))
        for name, url in PAGES:
            page = await ctx.new_page()
            print(f"{name:22s} {url}")
            summary.append(await capture(page, name, url))
            await page.close()
        await browser.close()
    (OUT / "summary.md").write_text("\n".join(summary))
    print(f"\nwrote {OUT}/summary.md and {len(PAGES)} screenshots")


if __name__ == "__main__":
    asyncio.run(main())
