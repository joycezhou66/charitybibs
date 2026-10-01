from pipeline.verify import quote_found, normalize, verify
from pipeline.schema import Charity

PAGE = """Team Example — TCS New York City Marathon 2026
Fundraising minimum: $4,000 per runner.
If the fundraising minimum is not met by November 1, 2026, the remaining balance will be charged to the credit card on file.
Runners receive a personal fundraising page, weekly group runs in Central Park, and a dedicated coach.
Applications are now closed for 2026."""

CACHE = {"id": "ex", "name": "Team Example", "pages": [{"url": "https://example.org/run", "text": PAGE, "fetched": "2026-09-14"}]}


def test_exact_quote_found():
    assert quote_found("Fundraising minimum: $4,000 per runner.", PAGE)


def test_normalized_quote_found():
    # curly quotes, extra whitespace, different case
    assert quote_found("fundraising   MINIMUM: $4,000 per runner", PAGE)


def test_fuzzy_quote_found():
    assert quote_found("the remaining balance will be charged to the credit card on file", PAGE)
    assert quote_found("the remaining balance will be charged to the credit-card on file", PAGE)


def test_fabricated_quote_rejected():
    assert not quote_found("Runners are released from the minimum if injured.", PAGE)
    assert not quote_found("", PAGE)
    assert not quote_found(None, PAGE)


def test_short_quote_rejected():
    assert not quote_found("$4,000", PAGE)  # too short to be evidence


def test_verify_keeps_supported_fields_and_drops_unsupported():
    raw = {
        "status": "closed", "status_quote": "Applications are now closed for 2026.",
        "minimum": 4000, "minimum_quote": "Fundraising minimum: $4,000 per runner.", "minimum_source": "https://example.org/run",
        "minimum_note": "",
        "fee_amount": 150, "fee_quote": "A $150 non-refundable registration fee applies.",  # not on page → dropped
        "support": {"coaching": True, "group_runs": True, "fundraising_page": True, "gear": None},
        "support_notes": "coach, group runs, fundraising page",
        "support_quote": "Runners receive a personal fundraising page, weekly group runs in Central Park, and a dedicated coach.",
        "shortfall_published": True, "shortfall_text": "Card charged the balance Nov 1.",
        "shortfall_quote": "the remaining balance will be charged to the credit card on file",
        "shortfall_source": "https://example.org/run",
        "injury_published": True, "injury_text": "Released if injured", "injury_quote": "Runners are released if injured.",  # fabricated → dropped
        "deferral_published": False,
        "flags": [],
    }
    c = verify(raw, CACHE, existing=None, verified_on="2026-09-14")
    assert c.min == 4000 and c.status == "closed"
    assert c.fee is None and any("unverified: fee" in f for f in c.flags)
    assert c.support.coaching is True and c.supportScore == 3
    assert c.shortfall.pub and "charged" in c.shortfall.text
    assert not c.injury.pub and any("unverified: injury" in f for f in c.flags)
    assert c.termsScore == 1


def test_verify_carries_over_minimum_when_crawl_fails():
    existing = Charity(id="ex", name="Team Example", min=4000, minSource="https://example.org/old", url="https://example.org/run", verified="2026-08-01")
    raw = {"status": "unknown", "minimum": None, "minimum_note": "", "support": {}, "support_notes": "",
           "shortfall_published": False, "injury_published": False, "deferral_published": False, "flags": []}
    c = verify(raw, {"id": "ex", "name": "Team Example", "pages": []}, existing=existing, verified_on="2026-09-14")
    assert c.min == 4000 and any("carried over" in f for f in c.flags)


def test_support_cleared_without_quote():
    raw = {"status": "unknown", "minimum": None, "minimum_note": "", "support": {"coaching": True}, "support_notes": "coach",
           "support_quote": "We give every runner a coach.",  # not on page
           "shortfall_published": False, "injury_published": False, "deferral_published": False, "flags": []}
    c = verify(raw, CACHE, existing=None, verified_on="2026-09-14")
    assert c.support.coaching is None and c.supportScore == 0


def test_minimum_does_not_flip_tiers_while_old_figure_is_still_on_the_page():
    from pipeline.schema import Charity
    existing = Charity(id="v", name="V", url="https://v.org", verified="2026-09-14", min=3750)
    cache = {"id": "v", "name": "V", "pages": [{"url": "https://v.org/run", "fetched": "2026-09-30",
             "text": "Runner (we provide the race entry) without a hotel stay - $3,750. Fundraiser only (own entry) - $2,000."}]}
    raw = {"status": "open", "status_quote": "we provide the race entry", "minimum": 2000,
           "minimum_quote": "Runner (we provide the race entry) without a hotel stay - $3,750. Fundraiser only (own entry) - $2,000.",
           "support": {}, "shortfall_published": False, "injury_published": False, "deferral_published": False, "flags": []}
    c = verify(raw, cache, existing)
    assert c.min == 3750 and any(f.startswith("minimum kept at 3750") for f in c.flags)
    # a genuine change, where the old figure is gone, goes through
    raw2 = dict(raw, minimum=4000, minimum_quote="The 2026 minimum is $4,000.")
    cache2 = {**cache, "pages": [{**cache["pages"][0], "text": "The 2026 minimum is $4,000."}]}
    assert verify(raw2, cache2, existing).min == 4000
