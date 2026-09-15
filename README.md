# charitybibs.com

Compare NYC Marathon charity bib programs by the support each charity gives you to raise the minimum, whether they're still taking runners, and whether they publish the terms of the commitment — every field read from the charity's own page and linked back to it.

**Live:** https://charitybibs.com · **Case study:** https://joycezhou.me/charitybibs · **Data:** [`data/races/nyc-2026.json`](data/races/nyc-2026.json) (CC BY 4.0)

## How it stays current

A weekly GitHub Action re-reads every charity's pages, extracts the same fixed set of fields, **discards any field whose supporting quote can't be found verbatim in the fetched page**, diffs the result against what's published, and opens a pull request listing only what changed. A human merges. Nothing reaches the site without that review.

```
data/seeds/<race>.yaml            charity name + starting URLs (hand-maintained once a year)
        │
        ▼
pipeline/crawl.py                 Playwright · follows apply/FAQ/agreement/PDF links · respects robots.txt
        │   .cache/<race>/<id>.json  (page text + URLs)
        ▼
pipeline/extract.py               Claude, forced tool call against pipeline/schema.py → structured record
        │   .cache/<race>/extracted/<id>.json
        ▼
pipeline/verify.py                every fact needs a verbatim quote found in the fetched text (normalised, ≥0.92 fuzzy)
        │   fields that fail are dropped and flagged, never guessed
        ▼
pipeline/diff.py                  field-level diff vs data/races/<race>.json → changes.md
        │
        ▼
.github/workflows/refresh.yml     opens a PR with changes.md as the body   ──►  human review  ──►  merge
        │
        ▼
pipeline/build.py                 template.html + data → site/index.html (scores recomputed from raw fields)
```

Why the verify step exists: an LLM reading 27 pages will occasionally misread one. It cannot pass a number through this pipeline that it did not find on the page, because the quote it supplies is string-matched against the text we downloaded. "Not published" is a first-class value; an estimate is not.

## Run it

```bash
pip install -r requirements.txt && python -m playwright install chromium
export ANTHROPIC_API_KEY=...            # only needed for `extract` / `refresh`
export CB_MODEL=claude-sonnet-4-5       # or newer

python -m pipeline.run crawl   --race nyc-2026 --only bird,nami   # fetch pages → .cache/
python -m pipeline.run extract --race nyc-2026 --only bird,nami   # model → structured JSON
python -m pipeline.run verify  --race nyc-2026                     # provenance check → candidate.json
python -m pipeline.run diff    --race nyc-2026                     # → changes.md (what the PR shows)
python -m pipeline.run promote --race nyc-2026                     # candidate → data/races/
python -m pipeline.run build   --race nyc-2026                     # → site/index.html
python -m pipeline.run stats   --race nyc-2026
pytest -q                                                          # 17 tests, incl. a real headless crawl of a fixture site
```

`refresh` runs crawl → extract → verify → diff in one go; that is what the Action calls.

## Deploy the site

`site/` is static. Cloudflare Pages, output directory `site`, no build command. `site/_headers` sets CSP and the usual security headers. Add the domain, forward `hello@charitybibs.com` via Cloudflare Email Routing, add the site to Plausible (tag already in the template), submit `sitemap.xml` in Search Console.

Repository secrets for the Action: `ANTHROPIC_API_KEY`. Optional variable: `CB_MODEL`.

## Adding a race

1. `data/seeds/<race>.yaml` — `race`, `race_name`, and a `charities:` list of `{id, name, urls}` from the race's official partner page.
2. `data/races/<race>.json` — start with `{"refreshed": "...", "charities": []}`.
3. Run `refresh`, review the PR, merge, `build`.

The schema is race-agnostic. NYRR-specific bits (Silver/Bronze levels, bus and Charity Village) are just fields that stay null elsewhere. Boston and Chicago have the same shape — official list, guaranteed entry, USD — and are the intended next two. London and Berlin route through Realbuzz and would need a different seed strategy.

## Data rules

- Every non-null fact links to the page it was read from and carries the date it was read.
- A field with no verifiable quote is "not published," never an estimate.
- Support fields are `true` only when the charity says it; `null` means not mentioned, `false` means the charity says it does not provide it.
- `cause` and `focus` are the one hand-curated pair — a category from `CAUSES` in `pipeline/schema.py` and a one-line description. They are not extracted or quote-verified and are carried through re-verification unchanged.
- Corrections from charities go live within 48 hours and are logged in [`CHANGELOG.md`](CHANGELOG.md).
- Not affiliated with NYRR or any charity. Not legal advice.

## Layout

```
site/          template.html (edit this), index.html (built), robots.txt, sitemap.xml, _headers
data/seeds/    one YAML per race — what to crawl
data/races/    one JSON per race — what's published
pipeline/      schema · crawl · extract · verify · diff · build · run
tests/         unit tests + a Playwright integration test against tests/fixtures/site
.github/       ci.yml (tests + build on every push) · refresh.yml (Mondays 06:00 UTC → PR)
```

## What it is not

Not a marketplace, not a fundraising tool, not a referral business. The research behind that scoping is in the [PRD](docs/PRD.md).
