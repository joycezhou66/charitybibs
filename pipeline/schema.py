"""Data model for one charity program, and the JSON schema handed to the extractor.

Every non-null factual field must be backed by a verbatim quote and a source URL.
`verify.py` enforces this after extraction; `build.py` derives the scores.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

SUPPORT_KEYS: list[tuple[str, str]] = [
    ("coaching", "Coaching"),
    ("group_runs", "Group runs"),
    ("training_plan", "Training plan"),
    ("fundraising_coaching", "Fundraising help"),
    ("team_events", "Team events"),
    ("gear", "Gear"),
    ("fundraising_page", "Fundraising page"),
    ("bus_to_start", "Bus to start"),
    ("charity_village", "Charity Village"),
    ("hotel_or_travel", "Hotel/travel"),
]

Status = Literal["open", "waitlist", "closed", "unknown"]

# Cause is a curated categorisation, maintained by hand in data/races/<race>.json.
# It is the one field on the site that is not extracted or quote-verified, and the
# methodology section says so.
CAUSES = [
    "Cancer", "Children's health", "Mental health", "Disability & adaptive sport",
    "Youth & education", "Environment & parks", "Veterans & first responders",
    "Housing & community", "Survivors of violence & trafficking", "Humanitarian", "Legal aid",
]


class Support(BaseModel):
    coaching: Optional[bool] = None
    group_runs: Optional[bool] = None
    training_plan: Optional[bool] = None
    fundraising_coaching: Optional[bool] = None
    team_events: Optional[bool] = None
    gear: Optional[bool] = None
    fundraising_page: Optional[bool] = None
    bus_to_start: Optional[bool] = None
    charity_village: Optional[bool] = None
    hotel_or_travel: Optional[bool] = None


class Sourced(BaseModel):
    """A claim with provenance. `pub` is False when the charity does not publish it."""

    pub: bool = False
    text: str = "Not published"
    quote: Optional[str] = None
    source: Optional[str] = None
    method: Optional[str] = None


class Charity(BaseModel):
    id: str
    name: str
    cause: Optional[str] = Field(default=None, description="Curated category from CAUSES; not extracted, not quote-verified")
    focus: Optional[str] = Field(default=None, description="One-line plain description of what the charity does; curated")
    level: Optional[str] = None
    platform: Optional[str] = None
    status: Status = "unknown"
    spots: Optional[str] = None

    min: Optional[int] = None
    minNote: str = ""
    minSource: Optional[str] = None
    minQuote: Optional[str] = None

    fee: Optional[int] = None
    feeLabel: Optional[str] = None
    feeCreditable: Optional[bool] = None
    regSeparate: Optional[bool] = None
    deadline: Optional[str] = Field(default=None, description="ISO date")

    support: Support = Field(default_factory=Support)
    supportScore: int = 0
    supportNotes: str = ""
    supportQuote: Optional[str] = None
    supportSource: Optional[str] = None

    shortfall: Sourced = Field(default_factory=Sourced)
    chargeSchedule: Optional[str] = None
    freeExit: Optional[str] = None
    freeExitQuote: Optional[str] = None
    injury: Sourced = Field(default_factory=Sourced)
    deferral: Sourced = Field(default_factory=Sourced)
    termsScore: int = 0

    url: str
    verified: str
    flags: list[str] = Field(default_factory=list)

    def compute_scores(self) -> "Charity":
        self.supportScore = sum(1 for k, _ in SUPPORT_KEYS if getattr(self.support, k) is True)
        self.termsScore = (
            int(self.shortfall.pub)
            + int(bool(self.chargeSchedule or self.freeExit))
            + int(self.injury.pub)
            + int(self.deferral.pub)
        )
        return self


class Dataset(BaseModel):
    refreshed: str
    charities: list[Charity]


# The tool input schema handed to the model. Kept explicit (not derived) so the
# prompt contract is readable and stable even if the pydantic model grows.
EXTRACTION_TOOL = {
    "name": "record_charity_program",
    "description": (
        "Record what a marathon charity program publishes about runner support and the "
        "terms of the fundraising commitment. Use null for anything not stated. Every "
        "non-null factual field MUST have a verbatim quote copied from the page text and "
        "the URL it came from; fields without a quote will be discarded."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "level": {"type": ["string", "null"], "enum": ["Gold", "Silver", "Bronze", None]},
            "platform": {"type": ["string", "null"]},
            "status": {"type": "string", "enum": ["open", "waitlist", "closed", "unknown"]},
            "status_quote": {"type": ["string", "null"]},
            "spots": {"type": ["string", "null"]},
            "minimum": {"type": ["integer", "null"]},
            "minimum_note": {"type": "string"},
            "minimum_quote": {"type": ["string", "null"]},
            "minimum_source": {"type": ["string", "null"]},
            "fee_amount": {"type": ["integer", "null"]},
            "fee_label": {"type": ["string", "null"]},
            "fee_counts_toward_minimum": {"type": ["boolean", "null"]},
            "fee_quote": {"type": ["string", "null"]},
            "registration_separate": {"type": ["boolean", "null"]},
            "registration_quote": {"type": ["string", "null"]},
            "deadline": {"type": ["string", "null"], "description": "ISO date YYYY-MM-DD"},
            "deadline_quote": {"type": ["string", "null"]},
            "support": {
                "type": "object",
                "properties": {k: {"type": ["boolean", "null"]} for k, _ in SUPPORT_KEYS},
            },
            "support_notes": {"type": "string"},
            "support_quote": {"type": ["string", "null"]},
            "support_source": {"type": ["string", "null"]},
            "shortfall_published": {"type": "boolean"},
            "shortfall_text": {"type": ["string", "null"]},
            "shortfall_quote": {"type": ["string", "null"]},
            "shortfall_source": {"type": ["string", "null"]},
            "charge_schedule": {"type": ["string", "null"]},
            "charge_schedule_quote": {"type": ["string", "null"]},
            "free_exit_date": {"type": ["string", "null"], "description": "ISO date"},
            "free_exit_quote": {"type": ["string", "null"]},
            "injury_published": {"type": "boolean"},
            "injury_text": {"type": ["string", "null"]},
            "injury_quote": {"type": ["string", "null"]},
            "injury_source": {"type": ["string", "null"]},
            "deferral_published": {"type": "boolean"},
            "deferral_text": {"type": ["string", "null"]},
            "deferral_quote": {"type": ["string", "null"]},
            "deferral_source": {"type": ["string", "null"]},
            "flags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["status", "minimum_note", "support", "support_notes",
                     "shortfall_published", "injury_published", "deferral_published", "flags"],
    },
}
