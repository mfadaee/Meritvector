"""Deep Work Intelligence: evidence chains, attribution workflow, responsibility scope, retrieval, fairness extras."""

from __future__ import annotations

from conftest import login
from sqlalchemy import select

from meritvector_analytics.evidence_chains import build_chains
from meritvector_analytics.responsibility import labelled_dimensions, responsibility_scope
from meritvector_coordinator import Document, search


def test_chain_links_mitigation_to_next_milestone_and_labels_inference():
    risks = [
        {
            "id": "R1",
            "title": "Vendor slip",
            "identified_on": "2025-01-01",
            "mitigated_on": "2025-02-01",
            "severity": "high",
            "status": "mitigated",
            "owner_employee_id": "E1",
        }
    ]
    ms = [
        {"id": "M0", "name": "Design", "planned_date": "2025-01-20", "actual_date": "2025-01-20", "owner_employee_id": "E1"},
        {"id": "M1", "name": "Build", "planned_date": "2025-03-01", "actual_date": "2025-03-05", "owner_employee_id": "E1"},
        {"id": "M2", "name": "Launch", "planned_date": "2025-09-01", "actual_date": None, "owner_employee_id": "E1"},
    ]
    out = build_chains(risks, [], ms, attributions=[{"target_type": "milestone", "target_id": "M1", "role": "led"}])
    chain = out["chains"][0]
    assert [n["id"] for n in chain["nodes"]] == ["R1", "R1:mitigation", "M1"]
    inferred = [e for e in chain["edges"] if e["origin"] == "inferred"]
    assert inferred and "not cause" in inferred[0]["rule"]
    assert chain["nodes"][2]["outcome"] == "4 days late" and chain["nodes"][2]["attributions"]
    # Outside the window -> no inferred milestone link.
    late = build_chains([{**risks[0], "mitigated_on": "2025-05-01"}], [], ms)
    assert len(late["chains"][0]["nodes"]) == 2


def test_retrieval_ranks_relevant_documents_and_returns_sources():
    docs = [
        Document("a", "meeting", "Vendor steering", "Agreed to escalate the vendor contract delay", "/meetings/a"),
        Document("b", "project", "Data platform", "Migration of the reporting warehouse", "/projects/b"),
        Document("c", "decision", "Escalate vendor", "Escalate vendor delay to the sponsor", "/meetings/c"),
    ]
    hits = search(docs, "vendor delay")
    assert {h["id"] for h in hits} == {"a", "c"} and all(h["url"] and h["matched_terms"] for h in hits)
    assert search(docs, "the and of") == []


def test_responsibility_scope_is_described_not_scored():
    projects = [
        {"decision_authority": 2, "budget_accountable": True, "scope_level": "tactical", "workstreams": 2},
        {"decision_authority": 4, "budget_accountable": False, "scope_level": "strategic", "workstreams": 3},
    ]
    s = responsibility_scope(projects, risks_owned=5)
    rows = {r["id"]: r for r in s["dimensions"]}
    assert rows["decision_authority"]["value"]["mean"] == 3.0
    assert rows["budget_accountability"]["summary"] == "Yes on 1 of 2 projects"
    assert rows["risk_ownership"]["value"] == 5
    assert "not better performance" in s["note"]
    lab = labelled_dimensions({"technical_complexity": 4, "budget_accountable": True})
    tc = next(d for d in lab["context"] if d["id"] == "technical_complexity")
    assert tc["display"] == "4 of 5"


def test_extended_fairness_reports_opportunity_coverage_and_error(small_result):
    ext = small_result.fairness["extended"]
    assert ext.get("suppressed") or {"opportunity", "missing_evidence", "model_error"} <= set(ext)
    if not ext.get("suppressed"):
        assert "difference" in ext["opportunity"]["mean_complexity"] and ext["multiple_comparisons"]


def _lead_with_mitigated_risk():
    from meritvector_api import db as dbm
    from meritvector_api.models import Project, Risk, User

    with dbm.session() as s:
        for r in s.scalars(select(Risk).where(Risk.tenant_id == "synthetic-pmo", Risk.mitigated_on.is_not(None))):
            pr = s.get(Project, r.project_id)
            if r.owner_employee_id == pr.lead_employee_id:
                u = s.scalars(select(User).where(User.employee_id == pr.lead_employee_id)).first()
                if u:
                    return u.id, pr.id, r.id
    raise AssertionError("no suitable risk")


def test_evidence_chain_link_and_attribution_workflow(api_client):
    user_id, project_id, risk_id = _lead_with_mitigated_risk()
    h = login(api_client, user_id)
    chains = api_client.get(f"/portfolio/projects/{project_id}/evidence-chains", headers=h).json()
    assert chains["chains"] and chains["inference_rule"]
    ms = api_client.get(f"/portfolio/projects/{project_id}", headers=h).json()["milestones"]
    link = api_client.post(
        "/evidence-links",
        json={
            "project_id": project_id,
            "from_type": "mitigation",
            "from_id": risk_id,
            "to_type": "milestone",
            "to_id": ms[-1]["id"],
            "relation": "protects",
            "note": "Fallback supplier kept the launch date",
        },
        headers=h,
    )
    assert link.status_code == 200, link.text
    after = api_client.get(f"/portfolio/projects/{project_id}/evidence-chains", headers=h).json()
    assert any(e["origin"] == "manual" for e in after["manual_links"])
    # Cross-project links are refused.
    other = api_client.post(
        "/evidence-links",
        json={
            "project_id": project_id,
            "from_type": "milestone",
            "from_id": "nope",
            "to_type": "milestone",
            "to_id": ms[0]["id"],
            "relation": "precedes",
        },
        headers=h,
    )
    assert other.status_code == 404

    a = api_client.post(
        "/attributions",
        json={"target_type": "mitigation", "target_id": risk_id, "role": "led", "description": "Negotiated the fallback supplier."},
        headers=h,
    ).json()
    assert a["status"] == "claimed" and a["data_category"] == "self_reported"
    assert any(x["id"] == a["id"] for x in api_client.get("/attributions/me", headers=h).json())
    # The author cannot review their own claim; HR can, and a dispute needs a reason.
    assert api_client.post(f"/attributions/{a['id']}/review", json={"decision": "confirmed"}, headers=h).status_code == 403
    hr = login(api_client, "u-SYN-HR1")
    assert any(x["id"] == a["id"] for x in api_client.get("/attributions/review", headers=hr).json())
    assert api_client.post(f"/attributions/{a['id']}/review", json={"decision": "disputed"}, headers=hr).status_code == 422
    ok = api_client.post(f"/attributions/{a['id']}/review", json={"decision": "confirmed", "note": "Matches the RAID log"}, headers=hr)
    assert ok.json()["status"] == "confirmed"
    # Another employee does not see the attribution on the chain.
    from meritvector_api import db as dbm
    from meritvector_api.models import User

    with dbm.session() as s:
        other_user = next(
            u.id for u in s.scalars(select(User).where(User.tenant_id == "synthetic-pmo", User.role == "employee")) if u.id != user_id
        )
    seen = api_client.get(f"/portfolio/projects/{project_id}/evidence-chains", headers=login(api_client, other_user)).json()
    assert not any(n["attributions"] for c in seen["chains"] for n in c["nodes"])


def test_responsibility_scope_and_dimensions_endpoints(api_client):
    user_id, project_id, _ = _lead_with_mitigated_risk()
    h = login(api_client, user_id)
    dims = api_client.get(f"/portfolio/projects/{project_id}/dimensions", headers=h).json()
    assert {d["id"] for d in dims["responsibility"]} >= {"decision_authority", "risk_ownership"}
    me = api_client.get("/auth/me", headers=h).json()
    scope = api_client.get(f"/employees/{me['employee_id']}/responsibility-scope", headers=h).json()
    assert scope["projects_led"] >= 1 and scope["dimensions"]


def test_knowledge_search_is_scoped(api_client):
    user_id, _, _ = _lead_with_mitigated_risk()
    h = login(api_client, user_id)
    r = api_client.get("/coordinator/search", params={"q": "dependency vendor"}, headers=h).json()
    assert r["searched"] > 0 and isinstance(r["results"], list)
    assert api_client.get("/coordinator/search", params={"q": "x"}, headers=h).status_code == 422
    # HR has no meetings in the index: meeting results never appear for non-attendees.
    hr = api_client.get("/coordinator/search", params={"q": "meeting review"}, headers=login(api_client, "u-SYN-HR1")).json()
    assert all(x["kind"] not in ("meeting", "decision") for x in hr["results"])
