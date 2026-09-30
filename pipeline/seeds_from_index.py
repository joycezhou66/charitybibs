"""Build the full NYC seed list from the captured NYRR charity index.

    python -m pipeline.seeds_from_index            # rewrites data/seeds/nyc-2026.yaml
    python -m pipeline.seeds_from_index --dry-run  # just report

Existing seed entries are kept exactly as they are (ids, URLs, hand-written cause and
focus) and gain `level` and `nyrr_key` from the index. Every other charity on NYRR's
list is appended with: a slug id, NYRR's full name, the website from NYRR's contact
card (or nothing, in which case the site links to NYRR's list), a cause mapped from
NYRR's category plus a keyword rule (documented below, correctable by hand), and a
one-line focus taken from the first sentence of NYRR's blurb.

Cause rule (first match wins):
  keywords in name+blurb → Cancer / Children's health / Mental health / Disability &
  adaptive sport / Veterans & first responders / Survivors of violence & trafficking /
  Legal aid / Housing & community / Environment & parks
  else NYRR category → Advocacy & rights / Animals / Arts & culture / Youth & education /
  Humanitarian / Faith / Health & medical research / Sports & running / Community services
"""
from __future__ import annotations

import argparse
import difflib
import html as htmllib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parent.parent
CAPTURE = ROOT / "research/nyrr-index/charities.json"
SEEDS = ROOT / "data/seeds/nyc-2026.yaml"
NYRR_LIST = "https://events.nyrr.org/events/9c9d0a40e9f5586e44e0/charity_partners"

KEYWORDS = [
    ("Cancer", r"\bcancer|leukemia|lymphoma|myeloma|melanoma|sarcoma|tumor|oncolog"),
    ("Children's health", r"children'?s hospital|pediatric|paediatric|sick kids|childhood (illness|disease|cancer)|hospital for children|make-a-wish|ronald mcdonald"),
    ("Mental health", r"mental (health|illness)|suicide|depression|anxiety|autism|nami\b|eating disorder|addiction|recovery"),
    ("Disability & adaptive sport", r"disabilit|adaptive|blind|wheelchair|amputee|paralys|challenged athlete|special olympics|achilles"),
    ("Veterans & first responders", r"veteran|military|first responder|firefighter|wounded|gold star|police"),
    ("Survivors of violence & trafficking", r"domestic violence|trafficking|abuse survivor|sexual assault|gender-based violence"),
    ("Legal aid", r"legal (aid|services)|lawyer|justice"),
    ("Housing & community", r"homeless|housing|shelter|food (bank|pantry|insecurity)|hunger|soup kitchen"),
    ("Environment & parks", r"park|conservancy|environment|climate|wildlife|bird|river|garden|trees"),
]
CATEGORY = {
    "Advocacy": "Advocacy & rights", "Animal Rights/Welfare": "Animals", "Arts & Culture": "Arts & culture",
    "Education": "Youth & education", "Youth": "Youth & education", "Emergency Relief": "Humanitarian",
    "Environment": "Environment & parks", "Faith Based/Religion": "Faith",
    "Healthcare/Medicine": "Health & medical research", "Research": "Health & medical research",
    "Military/Veteran Services": "Veterans & first responders", "Social Service": "Community services",
    "Sports": "Sports & running",
}
IGNORE_CATEGORIES = {"International", "Other"}  # matched the wrong controls during capture
GENERIC_EMAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com", "me.com"}
# Existing seeds whose NYRR listing name differs too much for fuzzy matching.
MANUAL = {"coc": "Circle of Care for families of children", "nami": "NAMI-NYC", "chop": "Children's Hospital of Philadelphia",
          "concern": "Concern Worldwide", "msahc": "The Mount Sinai Adolescent"}


def full_name(c: dict) -> str:
    m = re.search(r'class="charity-name[^"]*">([^<]+)<', c.get("contact_html") or "")
    return htmllib.unescape(m.group(1)).strip() if m else c["name"].replace("...", "").strip()


def website(c: dict) -> str | None:
    m = re.search(r'href="(https?://[^"]+)"[^>]*class="[^"]*website-text', c.get("contact_html") or "")
    if m:
        return m.group(1)
    m = re.search(r'mailto:([^"]+)"', c.get("contact_html") or "")
    if m:
        dom = m.group(1).split("@")[-1].lower()
        if dom and dom not in GENERIC_EMAIL and "." in dom:
            return f"https://{dom}/"
    return None


def host(u: str | None) -> str:
    return re.sub(r"^www\.", "", urlparse(u).netloc.lower()) if u else ""


def norm(s: str) -> str:
    s = s.lower().replace("&", "and")
    s = re.sub(r"\b(the|inc|foundation|fund|of|for|team|nyc|new york|city|2026)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def cause_for(c: dict) -> str:
    text = (full_name(c) + " " + (c.get("blurb") or "")).lower()
    for label, pat in KEYWORDS:
        if re.search(pat, text):
            return label
    for cat in c.get("categories") or []:
        if cat in CATEGORY:
            return CATEGORY[cat]
    return "Community services"


def focus_for(c: dict) -> str:
    b = re.sub(r"\s+", " ", htmllib.unescape(c.get("blurb") or "")).strip()
    if not b:
        return ""
    first = re.split(r"(?<=[.!?])\s", b)[0]
    if len(first) <= 140:
        return first
    cut = first[:137]
    return cut[:cut.rfind(" ")].rstrip(",;:") + "…"


def slug(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", norm(name)).strip("-")[:28] or "charity"
    s, n = base, 2
    while s in taken:
        s, n = f"{base}-{n}", n + 1
    taken.add(s)
    return s


def build(dry_run: bool = False) -> dict:
    cap = json.loads(CAPTURE.read_text())
    seeds = yaml.safe_load(SEEDS.read_text())
    existing = seeds["charities"]
    by_key = {c["key"]: c for c in cap if c.get("key")}
    names = {k: full_name(c) for k, c in by_key.items()}
    normed = {k: norm(n) for k, n in names.items()}
    by_host: dict[str, str] = {}
    for k, c in by_key.items():
        h = host(website(c))
        if h:
            by_host.setdefault(h, k)

    matched: dict[str, str] = {}  # seed id → nyrr key
    for s in existing:
        k = None
        if s["id"] in MANUAL:
            k = next((kk for kk, n in names.items() if n.lower().startswith(MANUAL[s["id"]].lower()[:20])), None)
        if not k:
            for u in s.get("urls", []):
                if host(u) in by_host:
                    k = by_host[host(u)]
                    break
        if not k:
            best = difflib.get_close_matches(norm(s["name"]), list(normed.values()), n=1, cutoff=0.8)
            if best:
                k = next(kk for kk, n in normed.items() if n == best[0])
        if k:
            matched[s["id"]] = k
            s["level"] = (by_key[k].get("tier") or "").title() or s.get("level")
            s["nyrr_key"] = k

    taken = {s["id"] for s in existing}
    used_keys = set(matched.values())
    new = []
    for k, c in by_key.items():
        if k in used_keys:
            continue
        url = website(c)
        entry = {"id": slug(names[k], taken), "name": names[k], "urls": [url] if url else [],
                 "cause": cause_for(c), "focus": focus_for(c), "level": (c.get("tier") or "").title() or None,
                 "nyrr_key": k}
        new.append(entry)
    tier_rank = {"Gold": 0, "Silver": 1, "Bronze": 2}
    new.sort(key=lambda e: (tier_rank.get(e["level"], 3), e["name"].lower()))

    out = dict(seeds)
    out["official_list"] = NYRR_LIST
    out["official_list_note"] = ("Built by pipeline/seeds_from_index.py from research/nyrr-index/charities.json "
                                 "(NYRR's charity partner list on Haku). Existing entries are kept by hand; new ones "
                                 "get cause/focus from NYRR's category and blurb and can be corrected here.")
    out["charities"] = existing + new
    report = {
        "captured": len(by_key), "existing": len(existing), "matched_existing": len(matched),
        "unmatched_existing": [s["id"] for s in existing if s["id"] not in matched],
        "new": len(new), "new_with_url": sum(1 for e in new if e["urls"]),
        "new_without_url": sum(1 for e in new if not e["urls"]),
        "causes": {c: sum(1 for e in out["charities"] if e.get("cause") == c)
                   for c in sorted({e.get("cause") for e in out["charities"] if e.get("cause")})},
        "levels": {l: sum(1 for e in out["charities"] if e.get("level") == l) for l in ("Gold", "Silver", "Bronze", None)},
    }
    if not dry_run:
        SEEDS.write_text(yaml.safe_dump(out, sort_keys=False, allow_unicode=True, width=1000))
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    print(json.dumps(build(ap.parse_args().dry_run), indent=1))
