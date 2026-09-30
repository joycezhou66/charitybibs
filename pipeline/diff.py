"""Compare a freshly verified dataset against the published one and write a review note.

The output markdown becomes the body of the weekly pull request. A human approves the PR;
nothing reaches the site without that. Only changed fields are listed.
"""
from __future__ import annotations

from .schema import Charity, Dataset

WATCHED = [
    "cause", "min", "status", "fee", "feeCreditable", "regSeparate", "deadline",
    "supportScore", "termsScore", "chargeSchedule", "freeExit", "level", "platform",
]


def _flat(c: Charity) -> dict:
    d = {k: getattr(c, k) for k in WATCHED}
    d["shortfall"] = c.shortfall.text if c.shortfall.pub else "Not published"
    d["injury"] = c.injury.text if c.injury.pub else "Not published"
    d["deferral"] = c.deferral.text if c.deferral.pub else "Not published"
    for k in type(c.support).model_fields:
        d[f"support.{k}"] = getattr(c.support, k)
    return d


def diff(old: Dataset, new: Dataset) -> dict:
    o = {c.id: c for c in old.charities}
    n = {c.id: c for c in new.charities}
    changes: dict[str, list[tuple[str, object, object]]] = {}
    for cid, nc in n.items():
        if cid not in o:
            changes[cid] = [("(new charity)", None, nc.name)]
            continue
        a, b = _flat(o[cid]), _flat(nc)
        delta = [(k, a[k], b[k]) for k in b if a.get(k) != b[k]]
        if delta:
            changes[cid] = delta
    removed = [cid for cid in o if cid not in n]
    unverified = {cid: [f for f in c.flags if f.startswith("unverified")] for cid, c in n.items()}
    unverified = {k: v for k, v in unverified.items() if v}
    unread = [cid for cid, c in n.items() if any(f.startswith("listed only") for f in c.flags)]
    return {"changes": changes, "removed": removed, "unverified": unverified, "unread": unread,
            "names": {cid: c.name for cid, c in n.items()} | {cid: c.name for cid, c in o.items()}}


def render(d: dict, race: str, spend: dict | None = None) -> str:
    names = d["names"]
    new = [cid for cid, delta in d["changes"].items() if delta and delta[0][0] == "(new charity)"]
    changed = {cid: delta for cid, delta in d["changes"].items() if cid not in set(new)}
    unread = d.get("unread") or []
    lines = [f"## Weekly refresh — {race}", ""]
    if spend:
        stopped = spend.get("stopped")
        lines.append(f"API spend this run: **${spend.get('total_usd', 0):.2f}** across {len(spend.get('charities', {}))} charities"
                     + (f" ({stopped})" if stopped else "") + ".")
        lines.append("")
    if not d["changes"] and not d["removed"]:
        lines.append("No field changes detected. Verified dates updated.")
    else:
        lines.append(f"**{len(changed)} charities changed**, {len(new)} added, {len(d['removed'])} removed from seeds.")
        lines.append("")
        if changed or d["removed"]:
            lines.append("| Charity | Field | Was | Now |")
            lines.append("|---|---|---|---|")
            for cid, delta in changed.items():
                for k, a, b in delta:
                    lines.append(f"| {names.get(cid, cid)} | `{k}` | {a!r} | {b!r} |")
            for cid in d["removed"]:
                lines.append(f"| {names.get(cid, cid)} | — | listed | **removed from seed list** |")
        if new:
            read_new = [c for c in new if c not in set(unread)]
            lines += ["", f"<details><summary>{len(new)} charities added from the official list "
                          f"({len(read_new)} read this run, {len(new) - len(read_new)} listed only)</summary>", ""]
            lines += [f"- {names.get(cid, cid)}" + ("" if cid in set(read_new) else " (not yet read)") for cid in new]
            lines += ["", "</details>"]
    if unread:
        lines += ["", f"**{len(unread)} charities are listed but not yet read.** They show on the site with no amounts "
                      "or terms until a future run reads their pages."]
    if d["unverified"]:
        lines += ["", "### Dropped as unverifiable (quote not found in fetched page)", ""]
        for cid, fl in d["unverified"].items():
            for f in fl:
                lines.append(f"- {names.get(cid, cid)}: {f}")
        lines += ["", "_A dropped field keeps its previous published value only for `min`; everything else falls back to \"not published\" until re-verified. Check these by hand before merging._"]
    lines += ["", "---", "Review: open the site preview, click each changed row, confirm the quote matches the linked page. Merge to publish."]
    return "\n".join(lines)
