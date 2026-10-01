"""Fetch each charity's marathon pages and cache the visible text.

- Headless Chromium via Playwright, so client-rendered pages (Classy, DonorDrive) work.
- Follows up to MAX_HOPS same-site links whose text or href looks like an application,
  FAQ, agreement, commitment, or PDF. PDFs are extracted with pdfplumber.
- Respects robots.txt, identifies itself, and waits between requests.
- Writes one JSON per charity to .cache/<race>/<id>.json:
  {"id", "pages": [{"url", "text", "fetched"}], "errors": [...]}
"""
from __future__ import annotations

import asyncio
import io
import json
import re
import time
import urllib.robotparser as robotparser
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml

UA = "charitybibs-bot/1.0 (+https://charitybibs.com; hello@charitybibs.com)"
HOP_PATTERN = re.compile(
    r"(apply|application|register|registration|faq|agreement|commitment|terms|"
    r"fundrais|pledge|policy|runner|marathon|\.pdf)", re.I
)
MAX_HOPS = 4
DELAY_S = 1.5
PAGE_TIMEOUT_MS = 30_000


def _same_site(a: str, b: str) -> bool:
    ha, hb = urlparse(a).netloc.lower(), urlparse(b).netloc.lower()
    strip = lambda h: h[4:] if h.startswith("www.") else h
    return strip(ha) == strip(hb)


ROBOTS_TIMEOUT_S = 10
CHARITY_TIMEOUT_S = 240      # hard cap per charity, all pages included
PDF_MAX_BYTES = 20_000_000
PDF_PARSE_TIMEOUT_S = 90


class Robots:
    def __init__(self) -> None:
        self._cache: dict[str, robotparser.RobotFileParser] = {}

    def allowed(self, url: str) -> bool:
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._cache:
            rp = robotparser.RobotFileParser()
            try:
                import urllib.request
                req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=ROBOTS_TIMEOUT_S) as r:  # noqa: S310 — http(s) only
                    rp.parse(r.read().decode("utf-8", "ignore").splitlines())
            except Exception:  # unreadable or slow robots → treat as allowed
                rp = None  # type: ignore[assignment]
            self._cache[base] = rp  # type: ignore[assignment]
        rp = self._cache[base]
        return True if rp is None else rp.can_fetch(UA, url)


def pdf_text(data: bytes) -> str:
    import pdfplumber

    if len(data) > PDF_MAX_BYTES:
        raise ValueError(f"PDF too large to parse ({len(data)} bytes)")
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


async def pdf_text_async(data: bytes) -> str:
    """Parse in a worker thread with a deadline, so one broken PDF cannot stall the run."""
    loop = asyncio.get_running_loop()
    return await asyncio.wait_for(loop.run_in_executor(None, pdf_text, data), PDF_PARSE_TIMEOUT_S)


async def fetch_page(context, url: str) -> tuple[str, list[str]]:
    """Return (visible text, candidate hop links)."""
    if url.lower().endswith(".pdf"):
        resp = await context.request.get(url, timeout=PAGE_TIMEOUT_MS)
        return await pdf_text_async(await resp.body()), []
    page = await context.new_page()
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
        ctype = (resp.headers.get("content-type", "") if resp else "")
        if "pdf" in ctype:
            return await pdf_text_async(await resp.body()), []
        await page.wait_for_timeout(1200)  # let client-rendered content settle
        text = await page.evaluate("document.body ? document.body.innerText : ''")
        links = await page.evaluate(
            "Array.from(document.querySelectorAll('a[href]')).map(a=>[a.href,a.innerText||''])"
        )
        hops = [
            urljoin(url, h) for h, t in links
            if HOP_PATTERN.search(h or "") or HOP_PATTERN.search(t or "")
        ]
        return text, hops
    finally:
        await page.close()


async def crawl_charity(context, robots: Robots, charity: dict, acc: dict | None = None) -> dict:
    seen: set[str] = set()
    queue: list[str] = list(charity["urls"])
    acc = acc if acc is not None else {"pages": [], "errors": []}
    pages, errors = acc["pages"], acc["errors"]
    while queue and len(pages) < len(charity["urls"]) + MAX_HOPS:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        if not robots.allowed(url):
            errors.append({"url": url, "error": "disallowed by robots.txt"})
            continue
        try:
            text, hops = await fetch_page(context, url)
            pages.append({"url": url, "text": text, "fetched": date.today().isoformat()})
            for h in hops:
                if h not in seen and (_same_site(url, h) or h.lower().endswith(".pdf")):
                    queue.append(h)
        except Exception as e:  # noqa: BLE001 — record and move on
            errors.append({"url": url, "error": str(e)[:300]})
        await asyncio.sleep(DELAY_S)
    return {"id": charity["id"], "name": charity["name"], "pages": pages, "errors": errors}


def _fresh(path: Path, max_age_days: int | None = None) -> bool:
    """True if this charity's cached pages were fetched within CB_CACHE_MAX_AGE_DAYS (default 3),
    so an interrupted run can resume without re-crawling; a weekly run still refetches."""
    import os
    days = max_age_days if max_age_days is not None else int(os.environ.get("CB_CACHE_MAX_AGE_DAYS", "3") or 3)
    try:
        d = json.loads(path.read_text())
        if not d.get("pages"):
            return False
        newest = max(date.fromisoformat(p["fetched"]) for p in d["pages"])
        return (date.today() - newest).days < days
    except Exception:  # noqa: BLE001 — unreadable cache → refetch
        return False


async def crawl_race(seed_path: Path, cache_dir: Path, only: set[str] | None = None) -> None:
    from playwright.async_api import async_playwright

    seeds = yaml.safe_load(seed_path.read_text())
    cache_dir.mkdir(parents=True, exist_ok=True)
    robots = Robots()
    async with async_playwright() as p:
        import os
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        launch_kw = {"proxy": {"server": proxy}} if proxy else {}
        browser = await p.chromium.launch(**launch_kw)
        # CB_DEV_INSECURE=1 is for local runs behind an intercepting corporate/sandbox proxy only.
        context = await browser.new_context(user_agent=UA, ignore_https_errors=os.environ.get("CB_DEV_INSECURE") == "1")
        for ch in seeds["charities"]:
            if only and ch["id"] not in only:
                continue
            out = cache_dir / f"{ch['id']}.json"
            if out.exists() and _fresh(out):
                print(f"  {ch['id']:10} cached pages are recent, skipped", flush=True)
                continue
            t0 = time.time()
            acc: dict = {"pages": [], "errors": []}
            try:
                result = await asyncio.wait_for(crawl_charity(context, robots, ch, acc), CHARITY_TIMEOUT_S)
            except asyncio.TimeoutError:
                acc["errors"].append({"url": ch["urls"][0] if ch.get("urls") else "", "error": f"charity crawl exceeded {CHARITY_TIMEOUT_S}s; kept {len(acc['pages'])} pages"})
                result = {"id": ch["id"], "name": ch["name"], "pages": acc["pages"], "errors": acc["errors"]}
                for pg in list(context.pages):
                    try:
                        await pg.close()
                    except Exception:  # noqa: BLE001
                        pass
            (cache_dir / f"{ch['id']}.json").write_text(json.dumps(result, indent=1))
            print(f"  {ch['id']:10} {len(result['pages'])} pages, {len(result['errors'])} errors, {time.time()-t0:.0f}s", flush=True)
        await browser.close()


def run(race: str, only: set[str] | None = None) -> None:
    root = Path(__file__).resolve().parent.parent
    asyncio.run(crawl_race(root / "data/seeds" / f"{race}.yaml", root / ".cache" / race, only))
