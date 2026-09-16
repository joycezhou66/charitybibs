# charitybibs.com — Design brief

**Author:** Joyce Zhou · **Date:** September 14, 2026 · **Status:** Draft for approval

## The user's job

A runner who didn't get in through the drawing. They have found out that a charity bib is a guaranteed spot, they have a number in front of them, $3,000 to $10,000, and they are hesitant. Their question is not "which charities exist." It is **"can I actually do this, and which charity will help me?"** They will succeed if they pick a cause their friends will give to and a charity that helps them ask. The page's job is to get them to commit, with their eyes open, not to warn them off.

## The three decisions the page must help them make

1. **What do I run for?** A cause they would be proud to ask friends and family for. This comes first because the money comes from asking, and asking is easy when you believe in it.
2. **Which charity will help me raise it?** Within that cause, the one with the most help: a coach, group runs, fundraising help, a team, gear, a bus to the start. The prices are almost all the same, the help is not.
3. **Can I sign up, and what am I agreeing to?** Whether they are still taking runners, the date the money is due, and the four fine-print answers: if I don't raise it all, if I get hurt, can I move to next year, until when can I back out. "They don't say" is an answer; it means ask before you sign.

## Design principles

1. **Answer, then show.** Every screen leads with what the reader should do or what is true for them, and the list backs it up. Options are never the headline.
2. **Look like the thing.** The identity comes from a race bib and the start-line print around it: one big number, one loud print color, black type on paper white, small print at the bottom, a tear-off strip. If it wouldn't look right taped to a corral fence, it doesn't belong.
3. **Every number is a quote.** The amount, the help, the status and the fine print each link to the charity's page and carry the date they were read. When we couldn't find it, the page says "they don't say," never a guess.
4. **Plain words, any age.** Copy reads like a friend who has done this before. No jargon, no scores without a sentence next to them saying what they mean.
5. **Encourage, then disclose.** Fine print is where you are ready for it, after you have found a charity you like. It is never the first thing on the screen and never styled as a warning.

## What we will not do

- No stat tiles or KPI rows.
- No cards on a gray background, no dashboard framing.
- No pill soup: no rows of colored tags standing in for sentences.
- No stock photos, no hero photo of runners, no countdown clock.
- No generic accent color: no product-blue, no gradient, no "brand purple." One accent, chosen for contrast, used for five things only.
- No logo walls. A logo tells the reader nothing about the program.
- No ratings out of ten shown as stars or bars without the words behind them.

## Typography and color direction

**The reference object is the bib**, kept in the layout: one big number, a band, small print, a tear-off line. The first draft's paper cream and safety orange with a condensed face read as a poster and were replaced on September 15, 2026 with a palette and a typeface a product team would ship. The layout did not change.

**Type.** One family from Google Fonts: **Instrument Sans**, 400 to 700. Headings, the amount to raise, status words and buttons are set in 700 uppercase with 0.03 to 0.05 em tracking, which keeps the race-signage feel without a condensed face. Everything read as sentences is 400 to 600 sentence case. Tabular figures wherever a number appears.

**Color.** White, a cool gray scale, one navy, two status colors.
- *Background* `#FFFFFF`, *surface* `#F8FAFC`, *ink* `#0F172A`, *secondary* `#475569`, *muted* `#64748B`, *rules* `#E2E8F0` and `#CBD5E1`.
- *Accent* `#1E3A8A`, a deep navy: the chosen answer, the question numerals, the bib band, the primary button. Never body text, never decoration.
- *Status:* green `#15803D` for taking runners, amber `#B45309` for waitlist, muted gray for closed or unstated. Each always sits next to the word.
- *Dark mode:* `#0B1220` ground, `#E2E8F0` ink, accent lifted to `#6C8CFF` with dark text on it, status colors lifted to stay legible.

**Details.** Rules are light gray, one to one-and-a-half pixels. Square corners. No shadows, no gradients, no icons.

## Constraints carried into every concept

Static HTML with data injected at build time. Fonts only from fonts.googleapis.com. Works at 390, 1100, 1280 and 1440 wide with no horizontal scroll, in light and dark mode, fully keyboard navigable. Every fact on screen comes from `data/races/nyc-2026.json`; nothing is estimated. Copy plain enough for any age.
