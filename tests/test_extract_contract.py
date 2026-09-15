"""The extractor is exercised with a fake client so the contract is tested without an API key."""
from types import SimpleNamespace

from pipeline.extract import extract_one, SYSTEM
from pipeline.schema import EXTRACTION_TOOL


class FakeClient:
    def __init__(self):
        self.calls = []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        block = SimpleNamespace(type="tool_use", name=EXTRACTION_TOOL["name"],
                                input={"status": "open", "minimum": 3500, "minimum_quote": "min is $3,500", "minimum_note": "",
                                       "support": {}, "support_notes": "", "shortfall_published": False,
                                       "injury_published": False, "deferral_published": False, "flags": []})
        return SimpleNamespace(content=[block])


def test_extract_forces_tool_and_passes_pages():
    cache = {"id": "x", "name": "X", "pages": [{"url": "https://x.org/run", "text": "min is $3,500", "fetched": "2026-09-14"}]}
    fc = FakeClient()
    out = extract_one(cache, "TCS NYC Marathon 2026", client=fc, model="test-model")
    assert out["minimum"] == 3500
    kw = fc.calls[0]
    assert kw["tool_choice"] == {"type": "tool", "name": EXTRACTION_TOOL["name"]}
    assert kw["tools"][0]["input_schema"]["required"]
    assert kw["system"] == SYSTEM
    assert 'url="https://x.org/run"' in kw["messages"][0]["content"]


def test_schema_has_quote_for_every_factual_field():
    props = EXTRACTION_TOOL["input_schema"]["properties"]
    for fact in ["minimum", "fee_amount", "deadline", "free_exit_date", "charge_schedule", "status"]:
        base = fact.replace("_amount", "").replace("_date", "")
        assert any(k.startswith(base) and k.endswith("_quote") for k in props), f"{fact} has no quote field"
