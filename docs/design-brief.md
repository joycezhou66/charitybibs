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
- No generic accent color: no product-blue, no gradient, no "brand purple."
- No logo walls. A logo tells the reader nothing about the program.
- No ratings out of ten shown as stars or bars without the words behind them.

## Typography and color direction

**The reference object is the bib.** A NYC Marathon bib is warm white Tyvek, a condensed black number about a hand tall, a solid color band that tells the marshals your wave, the runner's name in small caps, tiny print at the foot, and a perforated strip you tear off for bag check. Start-line print follows the same rules: corral signs and mile markers are one condensed face, one color, high contrast, readable at a jog.

**Type.** Two faces, both from Google Fonts because that is what the site's CSP allows.
- *Bib face:* **Barlow Condensed**, 600 to 800, for the amount to raise, for headings, and for uppercase labels with wide tracking. Tabular figures everywhere a number appears, so columns of dollars line up like a results sheet. The amount is set like a bib number: it is the number the runner is staring at, so give it the size it has in their head.
- *Text face:* **Archivo** at 15 to 16 px for everything read as sentences. Neutral, slightly wide, prints well. Small print at 12 to 13 px, never lighter than the muted ink.
- No italics for emphasis. Emphasis is weight or the print color, one or the other.

**Color.** Paper, ink, one print color, three status inks. Nothing else.
- *Paper:* warm white (`#F7F4EE`), the Tyvek tone, not pure white. Dark mode inverts to the night-before-race black (`#141210`) with the same print color, like a corral sign under floodlights.
- *Ink:* near-black (`#141210`) for everything readable; a muted ink for dates, sources and small print.
- *Print color:* one safety orange (`#F0501E`), the color of finish-line barricade tape and the wave band on a bib. It marks exactly three things: the current selection, the thing to do next, and the band on a charity's "bib." It is never used decoratively and never for body text.
- *Status inks*, borrowed from wave colors: green for taking runners, amber for waitlist, ink-grey for closed. Each always sits next to the word, never alone.

**Details that carry the identity without decoration.** Rules are black hairlines, not grey. Section dividers can be a perforation, a dashed rule, marking where the fine print "tears off." Uppercase micro-labels ("YOU RAISE", "DUE", "TAKING RUNNERS?") are set in the bib face with 0.08 em tracking, the way a bib prints "WAVE 1 · CORRAL B." Corners are square or barely rounded. Shadows are absent; a bib is flat.

## Constraints carried into every concept

Static HTML with data injected at build time. Fonts only from fonts.googleapis.com. Works at 390, 1100, 1280 and 1440 wide with no horizontal scroll, in light and dark mode, fully keyboard navigable. Every fact on screen comes from `data/races/nyc-2026.json`; nothing is estimated. Copy plain enough for any age.
