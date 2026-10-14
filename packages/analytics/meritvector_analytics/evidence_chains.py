"""Evidence chains: risk → mitigation → next milestone, and dependency → resolution → next milestone.

Links come from two places, and every link says which:

* ``inferred`` — built by a stated rule from register records (same project, temporal order, at most
  ``WINDOW_DAYS`` apart). A temporal sequence only — it is not evidence that the mitigation caused the outcome.
* ``manual`` — recorded by a person, with their identity and note, and shown as such.

Attributions (a person's own account of their contribution to a node) are attached for reading. They are
self-reported narrative evidence and are never used by the statistical models.
"""

from __future__ import annotations

from datetime import date
from typing import Any

WINDOW_DAYS = 90
INFERENCE_RULE = (
    f"Same project; the milestone is the first one planned on or after the mitigation/resolution date, within "
    f"{WINDOW_DAYS} days. This shows order in time, not cause."
)


def _d(v: Any) -> date | None:
    if v is None or v == "":
        return None
    return v if isinstance(v, date) else date.fromisoformat(str(v)[:10])


def _next_milestone(milestones: list[dict[str, Any]], after: date) -> dict[str, Any] | None:
    cands = [m for m in milestones if (pd := _d(m["planned_date"])) and 0 <= (pd - after).days <= WINDOW_DAYS]
    return min(cands, key=lambda m: _d(m["planned_date"])) if cands else None


def _milestone_node(m: dict[str, Any]) -> dict[str, Any]:
    planned, actual = _d(m["planned_date"]), _d(m.get("actual_date"))
    if actual is None:
        outcome = "not yet achieved"
    else:
        slip = (actual - planned).days
        outcome = "on time" if slip <= 0 else f"{slip} days late"
    return {
        "type": "milestone",
        "id": m["id"],
        "label": m["name"],
        "date": str(planned),
        "owner_employee_id": m.get("owner_employee_id"),
        "outcome": outcome,
    }


def build_chains(
    risks: list[dict[str, Any]],
    dependencies: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
    links: list[dict[str, Any]] | None = None,
    attributions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    links = links or []
    attributions = attributions or []
    by_node: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for a in attributions:
        by_node.setdefault((a["target_type"], a["target_id"]), []).append(a)
    ms_by_id = {m["id"]: m for m in milestones}

    def attach(node: dict[str, Any]) -> dict[str, Any]:
        node["attributions"] = by_node.get((node["type"], node["id"]), [])
        return node

    chains = []
    for r in risks:
        nodes = [
            attach(
                {
                    "type": "risk",
                    "id": r["id"],
                    "label": r["title"],
                    "date": str(_d(r["identified_on"])),
                    "owner_employee_id": r.get("owner_employee_id"),
                    "outcome": f"{r['severity']} severity · {r['status']}",
                }
            )
        ]
        edges = []
        mitigated = _d(r.get("mitigated_on"))
        if mitigated:
            nodes.append(
                {
                    "type": "mitigation",
                    "id": f"{r['id']}:mitigation",
                    "label": "Mitigation recorded",
                    "date": str(mitigated),
                    "owner_employee_id": r.get("owner_employee_id"),
                    "outcome": f"{(mitigated - _d(r['identified_on'])).days} days after identification",
                    "attributions": by_node.get(("mitigation", r["id"]), []),
                }
            )
            edges.append({"from": r["id"], "to": f"{r['id']}:mitigation", "relation": "mitigated_by", "origin": "register"})
            nxt = _next_milestone(milestones, mitigated)
            if nxt:
                nodes.append(attach(_milestone_node(nxt)))
                edges.append(
                    {"from": f"{r['id']}:mitigation", "to": nxt["id"], "relation": "precedes", "origin": "inferred", "rule": INFERENCE_RULE}
                )
        chains.append({"kind": "risk", "root": r["id"], "nodes": nodes, "edges": edges})
    for dep in dependencies:
        nodes = [
            attach(
                {
                    "type": "dependency",
                    "id": dep["id"],
                    "label": f"Depends on {dep['depends_on']}: {dep['description']}",
                    "date": str(_d(dep["raised_on"])),
                    "owner_employee_id": dep.get("owner_employee_id"),
                    "outcome": dep["status"],
                }
            )
        ]
        edges = []
        resolved = _d(dep.get("resolved_on"))
        if resolved:
            nxt = _next_milestone(milestones, resolved)
            nodes[0]["outcome"] = f"resolved after {(resolved - _d(dep['raised_on'])).days} days"
            if nxt:
                nodes.append(attach(_milestone_node(nxt)))
                edges.append({"from": dep["id"], "to": nxt["id"], "relation": "unblocks", "origin": "inferred", "rule": INFERENCE_RULE})
        chains.append({"kind": "dependency", "root": dep["id"], "nodes": nodes, "edges": edges})
    manual = []
    for link in links:
        edge = {
            "from": link["from_id"],
            "to": link["to_id"],
            "from_type": link["from_type"],
            "to_type": link["to_type"],
            "relation": link["relation"],
            "origin": "manual",
            "created_by": link.get("created_by_name") or link.get("created_by"),
            "created_at": str(link.get("created_at", ""))[:10],
            "note": link.get("note"),
        }
        manual.append(edge)
        for c in chains:
            ids = {n["id"] for n in c["nodes"]}
            if edge["from"] in ids or edge["to"] in ids:
                c["edges"].append(edge)
                missing = edge["to"] if edge["from"] in ids else edge["from"]
                if missing in ms_by_id and missing not in ids:
                    c["nodes"].append(attach(_milestone_node(ms_by_id[missing])))
    return {
        "chains": chains,
        "manual_links": manual,
        "inference_rule": INFERENCE_RULE,
        "note": "Chains show how records connect in time. They do not establish cause, and they are not a score.",
    }
