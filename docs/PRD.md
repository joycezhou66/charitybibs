# charitybibs.com — Product Requirements, v3

**Author:** Joyce Zhou · **Status:** Shipped (v1 live), pipeline in weekly operation · **Scope:** TCS New York City Marathon · **Updated:** September 14, 2026

This document is the spec behind [charitybibs.com](https://charitybibs.com). It supersedes v1 (entry-route discovery) and v2 (cost transparency). §9 records what changed between versions and why — that history is the most useful part of the document for anyone evaluating the product judgment behind it.

---

## 1. Problem

**A NYC Marathon charity bib is a $3,000–$10,000 fundraising commitment, backed by a credit card the runner hands over at acceptance, and the two things that determine whether a runner will succeed at it — the support the charity provides and the terms of the commitment — are not published where the runner is choosing.**

The charity's page advertises one number: the minimum. It usually does not say whether there is a coach, a team, or a fundraising lead. It usually does not say what happens if the runner falls short, when the card is charged, or whether injury releases them. Those answers live on other pages, in PDFs, or in an agreement shown after applying.

Evidence, from reading all 27 partner programs surveyed:

| | Count | What it means |
|---|---|---|
| Minimums within $3,000–$5,000 | 22 of 27 | Price is not the differentiator |
| Support score (coach, group runs, fundraising help, events, gear, logistics) | 0 to 8 of 10 | Support is the differentiator, and it's invisible until you dig |
| Still accepting runners, mid-September | 7 open · 9 waitlist · 7 closed · 4 unknown | Without status, half the links are dead ends |
| Publish what happens on a shortfall | 12 of 27 | Every one that does: balance charged to the card |
| Publish a free-withdrawal date | 3 of 27 | All three have passed for 2026 |
| Publish none of the four terms | 15 of 27 | Terms arrive after you apply |

The runner-side cost is people who don't sign up because they're not sure they can raise the money, and people who sign up with the wrong charity for them and stall. The charity-side cost is real and contractual: each charity prepays NYRR $600–$1,040 per entry and NYRR states there are no refunds for entries that go unfilled.

## 2. Who it's for

**The hesitant runner.** Has a bib route (charity) and a number in front of them, and one question: *can I actually do this?* Needs to know which charity will help them raise it and whether that charity is still taking people.

**Not the target:** experienced charity runners with an existing team; charities as customers (see §8).

## 3. What we built

A single page that asks the runner's question and answers it. Three questions a first-time reader can answer without learning any vocabulary — *What do you want to run for?* (a cause), *What help do you want?* (people to train with, help asking for money, both, or just the spot), *How soon do you need a spot?* (now, waitlist is fine, or show everyone) — then a ranked shortlist of the three closest fits, each with the reason it fits written from the data: what it gives you that you asked for, what it doesn't say, whether it's taking runners, the amount and due date, and how much of the fine print it answers. The rest of the field stays one click away ("Also fits", "Everyone else"), and every charity, shortlisted or not, opens the same question-led fine print (*How much do I raise? What do they give me? Are they still taking runners? What if I don't raise it all? What if I get hurt? Can I move to next year? Until when can I back out free?*). Answers are kept in the URL so a shortlist can be shared. Explanations (what a bib is, the four questions, where the numbers come from, data and contact) live on a separate "How it works" page so the main page is questions and results only. The visual identity comes from a race bib (see `docs/design-brief.md`): paper white, ink, one print orange, condensed numerals for the amount.

Fields:

- **Cause** — a category (11 across the 27) and a one-line description of what the charity does, with a cause filter. This is the first thing a runner chooses on and the one field that is hand-curated rather than extracted; the methodology says so.
- **Support you get** — ten chips (coaching, group runs, training plan, fundraising help, team events, gear, fundraising page, bus to start, Charity Village, hotel/travel), lit only when the charity states it. Score 0–10.
- **Application status** pill and a *still taking runners* filter.
- **Terms** — shortfall policy, charge timing, free-exit date, injury policy, deferral — shown in the detail panel as plain-language answers with the exact clause quoted and linked; "They don't say. Ask before you sign up." when unpublished. The 0–4 disclosure score is kept in the data and the weekly diff, not on the page.
- **Cost receipt** in the detail panel: minimum + NYRR entry + any fee that doesn't count, labeled as the most you could be out if you raised nothing.
- Every field carries the date it was last read and links to the page it came from. "Not published" is a value; nothing is estimated.

Copy is written to help someone commit, not to warn them off: *find a cause you'd be proud to raise for, pick for the support, check it's open, read the terms.*

## 4. Goals and how they're measured

| Goal | Metric | Target | Status |
|---|---|---|---|
| Runner can identify the best-supported open program in under a minute | Median time to first outbound charity click | < 60s | Instrumented (Plausible), read at 30 days |
| People act on it | Outbound charity clicks / sessions | ≥ 8% | Read at 30 days and again after the March 2027 drawing |
| Data stays trustworthy without manual re-reading | % of published fields with a verified quote; correction turnaround | 100%; < 48h | Enforced by pipeline; logged in CHANGELOG |
| The comparison is honest about what varies | Spread of support scores across charities with similar minimums | Documented | 0–8 across the $3,000–$5,000 band |

## 5. Requirements

### Shipped (P0)

- **R0 Cause.** Curated category + one-line focus per charity; cause filter. Not quote-verified; carried through re-verification unchanged.
- **R1 Support model.** Ten boolean-or-null fields per charity; `true` requires a verbatim quote from the charity. Score computed, never hand-entered.
- **R2 Status.** open / waitlist / closed / unknown, with quote; drives the pill and filter.
- **R3 Terms.** Shortfall, charge schedule, free-exit date, injury, deferral — each with quote + source or "not published."
- **R4 Provenance surface.** Per-field last-verified date; per-row source link; site-wide "data last refreshed"; correction path on every row; unaffiliated / not-legal-advice statement.
- **R5 Navigation.** Three questions (cause with counts per cause · help wanted · how soon), each answer collapsing to one line with a *Change* control; a ranked shortlist with per-charity reasons; one sort on the remaining list (most help · lowest amount · still taking runners · clearest fine print · name). Answers persist in the URL hash. Keyboard: arrow keys within a question, Tab between; an answered question folds only when focus leaves it. Phone: same single column.
- **R6 Cost receipt** in the expanded row: minimum + NYRR entry (per NYRR's rule that runners pay registration) + fees the charity says do not count. Labeled as the maximum if you raised nothing.
- **R7 Weekly verified refresh.** Crawl → extract → verify (quote must be found in fetched text) → diff → pull request. Human merge is the only path to publish. See the [README](../README.md).

### Next (P1)

- **R8** Boston and Chicago. Same schema; new seed lists; separate pages under `/boston`, `/chicago`.
- **R9** Charity self-service correction form (currently email).
- **R10** "Tell me when 2027 programs open" email capture.
- **R11** Per-charity commitment timeline (application → acceptance → deposit → free-exit → deadline → charge) as a visual, once enough charities publish dates to make it meaningful.

### Not building (see §8)

Marketplace or referral matching · fundraising tools · runner–charity messaging · bib resale · lottery odds · live slot inventory.

## 6. Acceptance criteria (selected)

- Given a charity states "coaches and group runs," when the row renders, then Coaching and Group runs chips are lit and the quote is visible in the expanded row with a link.
- Given a charity's page says nothing about injury, then the Injury row reads "Not published. Ask before you sign," and the terms score does not count it.
- Given the weekly run finds a changed minimum, then the PR body lists the charity, field, old value, new value, and the site is unchanged until merge.
- Given the extractor supplies a minimum whose quote is not in the fetched text, then the field is dropped, a flag is recorded, and the previously published minimum is carried forward with a "not re-verified" flag.
- Given a deadline before January 1 of the current season, then it renders as "not published" rather than a stale date.

## 7. Risks

| Risk | Mitigation |
|---|---|
| A charity's page is stale (prior-year text still up) | Extractor flags prior-year references; deadlines before the season render as not published; reviewer sees flags in the PR |
| Terms live only behind the application form | Stays "not published." The four-questions card tells runners exactly what to ask. Coverage of hidden terms is a partnership problem, not a scraping one |
| Charity asks to be delisted because its row is unflattering | Policy, decided in advance: rows reflect published terms; if the published page changes, the row changes within a week. Removal on request is not offered |
| NYRR's partner list blocks bots | Seed list is hand-refreshed once a year when the list is published (Jan–Feb) |
| Extraction model misreads a page | Every field is quote-verified against the fetched text; nothing unverifiable is published |

## 8. Why there is no business here, and why that's fine

Researched before scoping and worth stating plainly.

- Runner referral to charities already has a published clearing price: TimeOutdoors charges £250/year + **£25 per confirmed fundraiser**. Realbuzz has run outsourced runner recruitment for 20 years across 5,000+ charities. Run For Charity sells inventory-risk transfer to 800+ organisers.
- Referred runners are adversely selected: cause affinity predicts fundraising, and a runner choosing a charity to get a bib has none. Charities report runners who raise nothing at £400 sunk per place. That caps the price of a referral near zero.
- The programs with money (Dana-Farber ~$16,600 raised per runner; Fred's Team ~$8,300) are oversubscribed and need nothing. The programs that can't fill 3–15 bibs can't fund software.
- Small charities explicitly asked for a runner-matching marketplace in 2011. What emerged was ad-supported directories and services businesses.

So: no marketplace, no referral fee, no SaaS. The product is a public utility with a verified dataset, maintained at near-zero cost by the pipeline. Its value is to runners directly, and — if charities notice their "terms disclosed" score — to the norm of publishing terms up front.

## 9. What changed, and why

**v1 (Sept 13): entry-route discovery.** "240,000 people were rejected from the drawing; help them find charity bibs." Dropped because Marathon Ballot already lists ~190 charities across seven Majors. Discovery was solved well enough; building it again would have been a narrower copy.

**v2 (Sept 13): cost transparency.** "A charity bib is a financial liability with hidden fees; show the true cost." Hypothesis: sorting by total exposure would materially reorder the field. **Pre-registered kill criterion: under 10% rank change kills the thesis.** Result at n=27: 6 of 27 rows moved, mostly by one place. Exposure was the headline minimum plus a near-constant $315. The kill criterion fired.

**v3 (Sept 14): support and access.** What actually varied between charities was not the price — it was support (0–8 of 10), whether the program was still open (7 of 27), and whether the terms were published (12 of 27). And the barrier to committing was never hidden cost; it was fear of not raising the money. The page's job changed from warning to enabling. Injury policy was de-weighted after checking the base rate: in a 735-runner NYC cohort, 40% were injured in training but 4.1% were too injured to race.

**v3.1 (Sept 14): from list to answer.** Same data, same three decisions, different shape. The v3 page still opened on a table of 27 rows, which put the work of ranking on the reader. After a design pass against every other marathon's charity page (all logo grids, name lists, or hero photos; `research/refs/`), the page was rebuilt to ask the three questions first and return a shortlist with reasons, keeping the full list one click below. Cost-neutral to the pipeline: the template changed, nothing in `pipeline/` or `data/` did.

The cost research wasn't wasted: the shortfall clauses, charge schedules, and the "terms in the agreement after you apply" finding are the transparency layer under the support sort, and the four-questions card comes directly from it.

## 10. Timeline

| | |
|---|---|
| Sept 13–14, 2026 | Research (27 charities, 4 agent passes), PRD v1→v3, site built and rebuilt, pipeline written and tested |
| Late Sept | Domain, Cloudflare Pages, Plausible, Search Console. Launch on r/RunNYC and club Discords as the author |
| Oct–Feb | Weekly refresh PRs. Charity correction outreach. Boston + Chicago seeds |
| Late Feb 2027 | Full re-verification for the 2027 season |
| Early March 2027 | NYC drawing results — the traffic spike the domain has been aged for |

---

*Sources for every number in this document are in the dataset (`data/races/nyc-2026.json`), where each field links to the page it was read from.*
