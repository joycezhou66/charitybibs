# CLAUDE.md — charitybibs.com

Read this before doing anything. It is the handoff from the session that built this repo.

## What this is

A static comparison site for NYC Marathon charity bib programs (27 charities, 2026), plus a weekly pipeline that re-reads each charity's pages, extracts a fixed set of fields, drops any field whose quote can't be found in the fetched page, diffs, and opens a PR. The owner is Joyce Zhou (joycezhou66). It is her portfolio project for APM applications; the resume links the live site only, and the PRD is hosted on joycezhou.me.

- `README.md` — architecture, how to run, how to deploy. Accurate.
- `docs/PRD.md` — the spec, including what changed across v1→v3 and why. Accurate.
- `CHANGELOG.md` — data corrections. Append to it whenever data changes.
- `site/template.html` — edit this, never `site/index.html` (built).
- `site/about.html` — the "How it works" page (what a bib is, the four questions, sources, data, contact). Plain static file, edit directly.
- `data/races/nyc-2026.json` — the published data. `python -m pipeline.run build --race nyc-2026` regenerates the site.

## Hard rules

1. **Never add Claude attribution.** No `Co-Authored-By: Claude` trailers, no "Generated with Claude Code" lines in commits, PR bodies, or files. `.claude/settings.json` disables the trailer; do not re-enable it. Commits are authored by Joyce (`joycezhou66 <jezhou@usc.edu>`) only.
2. **Never estimate a number.** Every factual field on the site must have a verbatim quote from the charity's page that `pipeline/verify.py` can find. "Not published" is a valid value. Do not "fill in" missing terms.
3. **Do not change the product's shape** without being asked: three questions (cause → help wanted → how soon) → ranked shortlist with reasons → full list below → question-led fine print under every charity. The identity (white, cool gray scale, one navy, Instrument Sans, sentence case throughout) is specified in `docs/design-brief.md`; the redesign history in `docs/PRD.md` §9 explains why it looks the way it does.
4. **Do not post anywhere as anyone other than Joyce.** No fake accounts, no astroturfing. Launch posts are in `docs/growth-kit.md` if present, all written to be posted as her.
5. **Keep it plain.** Site copy is for any age: no "shortfall", "deferral", "commitment", "disclosed". Say "if you don't raise it all", "move to next year", "they don't say".

## State as of hand-off (Sept 14, 2026)

- Site built and verified: 17 tests pass, renders at 390 / 1100 / 1280 / 1440 with no horizontal overflow.
- **The live crawler has never run.** The build environment blocked the charity domains. The first real run is `python -m pipeline.run refresh --race nyc-2026` with `ANTHROPIC_API_KEY` set, or the GitHub Action. Expect some fields to be flagged `unverified` on the first run; that is the pipeline working. Review `.cache/nyc-2026/changes.md` before promoting.
- `CB_MODEL` defaults to `claude-sonnet-4-5`; bump to whatever is current.
- Data caveats still open (see `site/README.md` if present, else README "Before launch"): NYRR entry fees ($255/$315) are cited from charity pages, not nyrr.org; Northwell, Michael J. Fox, HSS, Catholic Charities NY, Team Reeve have no readable minimum yet; Ulman's page is stale; BCH's FAQ still shows a 2025 deadline.

## Deploy checklist (what Claude Code can do vs. what Joyce must do)

Claude Code can, if `gh` and `wrangler` are logged in:
- `git init`, first commit, `gh repo create joycezhou66/charitybibs --public --source=. --push`
- `gh secret set ANTHROPIC_API_KEY` (Joyce pastes the key when prompted; never paste it into chat or a file)
- `wrangler pages project create charitybibs --production-branch main` then `wrangler pages deploy site --project-name charitybibs`
- `gh workflow run weekly-refresh.yml` and `gh run watch` for the first real pipeline run
- Verify CI is green: `gh run list --workflow ci.yml`

Joyce must do herself (browser, her accounts):
- Buy `charitybibs.com` (Porkbun or Cloudflare Registrar). Confirm it is actually free first.
- Cloudflare dashboard → Pages project → Custom domains → add `charitybibs.com` and `www`.
- Cloudflare → Email Routing → `hello@charitybibs.com` → her Gmail.
- plausible.io → add site `charitybibs.com` → goals: outbound links, `Cause`, `Sort`.
- Google Search Console → add property → submit `https://charitybibs.com/sitemap.xml`.
- Host `docs/PRD.md` at `joycezhou.me/charitybibs` (the site's About links there).

## Conventions

- Python 3.11+, `pytest -q` must pass before any commit that touches `pipeline/` or `data/`.
- After any change to `site/template.html` or `data/`, run `python -m pipeline.run build --race nyc-2026` and commit the rebuilt `site/index.html` too.
- Keep `site/sitemap.xml` `<lastmod>` current (build does this).
- Adding a race: copy the pattern in README "Adding a race". Boston and Chicago are next; London/Berlin are not (Realbuzz-mediated, different seed strategy).
