"""API integration tests: RBAC, tenant separation, governance, workflows and audit."""

from conftest import login

EMP_ENDPOINTS = [
    "/workspace/today",
    "/workspace/projects",
    "/workspace/coordinator",
    "/workspace/data",
    "/meetings",
    "/evidence/me",
]


def _personas(c):
    ps = c.get("/auth/demo-personas").json()
    return {(p["tenant_id"], p["label"]): p for p in ps}


def test_health(api_client):
    r = api_client.get("/health").json()
    assert r["status"] == "ok" and r["synthetic_data_only"] is True


def test_requires_authentication(api_client):
    assert api_client.get("/workspace/today").status_code == 401
    assert api_client.get("/workspace/today", headers={"Authorization": "Bearer forged.token"}).status_code == 401


def test_employee_workspace_and_restrictions(api_client):
    p = _personas(api_client)[("synthetic-pmo", "Employee")]
    h = login(api_client, p["user_id"])
    for e in EMP_ENDPOINTS + ["/workspace/development"]:
        assert api_client.get(e, headers=h).status_code == 200, e
    # Employees cannot see analysis pages or other people's contribution.
    for e in ["/analysis/context", "/analysis/experiment", "/team/insights", "/admin/audit", "/admin/settings"]:
        assert api_client.get(e, headers=h).status_code == 403, e
    others = [x for x in ("SYN-E0005", "SYN-E0006") if x != p["employee_id"]]
    assert api_client.get(f"/employees/{others[0]}/contribution", headers=h).status_code == 403
    assert api_client.get(f"/employees/{p['employee_id']}/contribution", headers=h).status_code == 200


def test_manager_sees_only_direct_reports(api_client):
    m = _personas(api_client)[("synthetic-pmo", "Manager")]
    h = login(api_client, m["user_id"])
    items = api_client.get("/employees", headers=h).json()["items"]
    assert items and all(e["manager_id"] == m["employee_id"] for e in items)
    assert [e["display_name"] for e in items] == sorted(e["display_name"] for e in items)  # alphabetical, not ranked
    r = api_client.get(f"/employees/{items[0]['id']}/contribution", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert {
        "observed_evidence",
        "raw_metrics",
        "adjusted",
        "competencies",
        "trend",
        "missing_information",
        "review_notes",
    } <= set(body)
    all_emps = api_client.get("/admin/users", headers=login(api_client, "u-SYN-ADMIN")).json()
    assert all_emps["role_counts"]["manager"] == 4
    not_mine = api_client.get("/employees", headers=login(api_client, "u-SYN-HR1")).json()["items"]
    outsider = next(e for e in not_mine if e["manager_id"] != m["employee_id"] and e["id"] != m["employee_id"])
    assert api_client.get(f"/employees/{outsider['id']}/contribution", headers=h).status_code == 403


def test_admin_has_no_individual_evidence_access(api_client):
    h = login(api_client, "u-SYN-ADMIN")
    assert api_client.get("/employees", headers=h).status_code == 403
    assert api_client.get("/employees/SYN-E0010/contribution", headers=h).status_code == 403
    assert api_client.get("/analysis/context", headers=h).status_code == 403
    assert api_client.get("/admin/audit", headers=h).status_code == 200
    v = api_client.get("/analysis/validation", headers=h).json()
    assert isinstance(v["fairness"], dict)  # aggregated audit is available to admins


def test_fairness_restricted_for_managers(api_client):
    m = _personas(api_client)[("synthetic-pmo", "Manager")]
    v = api_client.get("/analysis/validation", headers=login(api_client, m["user_id"])).json()
    assert isinstance(v["fairness"], str)


def test_tenant_separation(api_client):
    h = login(api_client, "u-SBX-HR1")
    assert api_client.get("/portfolio/projects/SYN-P0001", headers=h).status_code == 404
    projects = api_client.get("/portfolio/projects?limit=500", headers=h).json()["items"]
    assert projects and all(p["tenant_id"] == "synthetic-sandbox" for p in projects)


def test_governance_gate_blocks_assessment_until_dual_approval(api_client):
    hr, admin = login(api_client, "u-SBX-HR1"), login(api_client, "u-SBX-ADMIN")
    assert api_client.get("/employees", headers=hr).status_code == 403
    sbx_emp = _personas(api_client)[("synthetic-sandbox", "Employee")]
    assert api_client.get("/workspace/development", headers=login(api_client, sbx_emp["user_id"])).status_code == 403
    # Coordinator still works without assessment.
    assert api_client.get("/workspace/coordinator", headers=login(api_client, sbx_emp["user_id"])).status_code == 200
    # HR cannot request; admin requests; HR approves -> enabled.
    assert api_client.post("/admin/governance/request", json={"purpose": "x" * 30}, headers=hr).status_code == 403
    g = api_client.post(
        "/admin/governance/request", json={"purpose": "Evidence-based development conversations pilot"}, headers=admin
    ).json()
    assert g["status"] == "pending"
    assert api_client.get("/employees", headers=hr).status_code == 403
    g = api_client.post(f"/admin/governance/{g['id']}/approve", json={}, headers=hr).json()
    assert g["status"] == "approved"
    assert api_client.get("/employees", headers=hr).status_code == 200
    # Revoke again so other tests see the default state.
    assert api_client.post("/admin/governance/revoke", json={}, headers=admin).json()["assessment_enabled"] is False
    assert api_client.get("/employees", headers=hr).status_code == 403


def test_challenge_workflow(api_client):
    p = _personas(api_client)[("synthetic-pmo", "Employee")]
    h = login(api_client, p["user_id"])
    ev = api_client.get("/evidence/me?category=milestone_achieved", headers=h).json()["items"][0]
    r = api_client.post(
        f"/evidence/{ev['event_id']}/challenge", json={"reason": "This milestone was delivered by another team."}, headers=h
    )
    assert r.status_code == 200
    cid = r.json()["id"]
    assert api_client.get("/evidence/me?category=milestone_achieved&limit=200", headers=h).json()["items"][0]["validation_status"] in (
        "disputed",
        "validated",
    )
    # The employee cannot resolve their own challenge; their manager can.
    assert (
        api_client.post(f"/evidence/challenges/{cid}/resolve", json={"decision": "rejected", "note": "nope nope"}, headers=h).status_code
        == 403
    )
    mh = login(api_client, f"u-{api_client.get('/workspace/data', headers=h).json()['profile']['employee_id']}")
    mgr = _personas(api_client)[("synthetic-pmo", "Manager")]
    r = api_client.post(
        f"/evidence/challenges/{cid}/resolve",
        json={"decision": "upheld_retract", "note": "Confirmed with PMO"},
        headers=login(api_client, mgr["user_id"]),
    )
    assert r.status_code == 200 and r.json()["status"] == "upheld_retract"
    statuses = {
        e["event_id"]: e["validation_status"]
        for e in api_client.get("/evidence/me?limit=200&category=milestone_achieved", headers=mh).json()["items"]
    }
    assert statuses[ev["event_id"]] == "retracted"
    audit = api_client.get("/admin/audit?action=challenge_resolved", headers=login(api_client, "u-SYN-ADMIN")).json()
    assert audit["total"] >= 1


def test_reviews_are_append_only_and_require_reasons(api_client):
    m = _personas(api_client)[("synthetic-pmo", "Manager")]
    h = login(api_client, m["user_id"])
    emp = api_client.get("/employees", headers=h).json()["items"][0]["id"]
    bad = api_client.post(
        f"/employees/{emp}/reviews",
        json={"agreement": "disagrees_with_evidence", "judgement": "I disagree with this."},
        headers=h,
    )
    assert bad.status_code == 422
    ok = api_client.post(
        f"/employees/{emp}/reviews",
        json={
            "agreement": "disagrees_with_evidence",
            "judgement": "I disagree with this.",
            "disagreement_reasons": "Two milestones were re-planned by the sponsor.",
        },
        headers=h,
    )
    assert ok.status_code == 200
    assert api_client.delete(f"/employees/{emp}/reviews").status_code == 405
    assert api_client.put(f"/employees/{emp}/reviews", json={}, headers=h).status_code == 405
    # Employees cannot review themselves.
    assert (
        api_client.post(
            f"/employees/{emp}/reviews",
            json={"agreement": "agrees_with_evidence", "judgement": "Self review attempt"},
            headers=login(api_client, f"u-{emp}"),
        ).status_code
        == 403
    )


def test_coordinator_flow_and_data_separation(api_client):
    p = _personas(api_client)[("synthetic-pmo", "Employee")]
    h = login(api_client, p["user_id"])
    before = api_client.get("/evidence/me", headers=h).json()["total"]
    r = api_client.post(
        "/coordinator/process-transcript",
        json={"title": "Sync", "transcript": "ACTION: Someone to do a thing by tomorrow.\nDecision: ship it."},
        headers=h,
    )
    assert r.status_code == 200 and r.json()["insight"]["decisions"]
    t = api_client.post("/coordinator/tasks", json={"title": "Write status report"}, headers=h).json()
    assert api_client.patch(f"/coordinator/tasks/{t['id']}", json={"status": "done"}, headers=h).json()["status"] == "done"
    # Assistance activity never creates assessment evidence.
    assert api_client.get("/evidence/me", headers=h).json()["total"] == before
    # Transcripts are visible to attendees only — not to HR or managers.
    mid = r.json()["id"]
    assert api_client.get(f"/meetings/{mid}", headers=login(api_client, "u-SYN-HR1")).status_code in (403, 404)
    mgr = _personas(api_client)[("synthetic-pmo", "Manager")]
    assert api_client.get(f"/meetings/{mid}", headers=login(api_client, mgr["user_id"])).status_code == 404


def test_external_delivery_blocked_by_default(api_client):
    p = _personas(api_client)[("synthetic-pmo", "Employee")]
    h = login(api_client, p["user_id"])
    m = api_client.post(
        "/coordinator/outbox", json={"channel": "slack", "recipient": "#proj", "subject": "Hi", "body": "Update"}, headers=h
    ).json()
    r = api_client.post(f"/coordinator/outbox/{m['id']}/send", json={"confirm": True}, headers=h)
    assert r.status_code == 403 and "disabled" in r.json()["detail"]
    admin = login(api_client, "u-SYN-ADMIN")
    api_client.put("/admin/settings", json={"external_delivery_enabled": True}, headers=admin)
    assert api_client.post(f"/coordinator/outbox/{m['id']}/send", json={"confirm": False}, headers=h).status_code == 403
    ok = api_client.post(f"/coordinator/outbox/{m['id']}/send", json={"confirm": True}, headers=h).json()
    assert ok["status"] == "recorded_by_mock"
    api_client.put("/admin/settings", json={"external_delivery_enabled": False}, headers=admin)


def test_analysis_and_validation_payloads(api_client):
    h = login(api_client, "u-SYN-HR1")
    ctx = api_client.get("/analysis/context", headers=h).json()
    assert ctx["points"] and ctx["models"]["schedule_variance_pct"]["coefficients"]
    ids = [p["employee_id"] for p in ctx["points"]]
    assert ids == sorted(ids)
    v = api_client.get("/analysis/validation", headers=h).json()
    assert all(c["passed"] for c in v["validation"]["leakage_checks"])
    assert v["model_card"].startswith("# Model card")
    runs = api_client.get("/analysis/runs", headers=h).json()
    assert runs and runs[0]["id"].startswith("mv-")


def test_portfolio_endpoints(api_client):
    h = login(api_client, _personas(api_client)[("synthetic-pmo", "Employee")]["user_id"])
    ov = api_client.get("/portfolio/overview", headers=h).json()
    assert ov["kpis"]["employees"] == 44 and ov["delivery_trend"]
    assert ov["evidence_coverage"] is None  # not shown to plain employees
    projects = api_client.get("/portfolio/projects?limit=3", headers=h).json()["items"]
    assert api_client.get(f"/portfolio/projects/{projects[0]['id']}", headers=h).status_code == 200
    cmp = api_client.get(f"/portfolio/compare?ids={projects[0]['id']},{projects[1]['id']}", headers=h).json()
    assert len(cmp["projects"]) == 2
    assert api_client.get("/portfolio/risks", headers=h).json()["monthly"]
    assert api_client.get("/portfolio/bottlenecks", headers=h).json()["dependencies_by_team"]


def test_scheduled_jobs_run_and_are_recorded(api_client):
    from meritvector_api import db as dbm
    from meritvector_api.workflows import run_job

    with dbm.session() as s:
        for name in ("deadline_reminders", "process_new_transcripts", "retention_enforcement"):
            assert run_job(s, name).status == "succeeded", name
    jobs = api_client.get("/admin/jobs", headers=login(api_client, "u-SYN-ADMIN")).json()
    assert {j["name"] for j in jobs["jobs"]} >= {"deadline_reminders", "retrain_models", "retention_enforcement"}
    assert any(r["status"] == "succeeded" for r in jobs["runs"])


def test_retraining_creates_new_version(api_client):
    from meritvector_api import db as dbm
    from meritvector_api.training import train_tenant

    h = login(api_client, "u-SYN-HR1")
    n = len(api_client.get("/analysis/runs", headers=h).json())
    with dbm.session() as s:
        run = train_tenant(s, "synthetic-pmo", n_boot=10)
    runs = api_client.get("/analysis/runs", headers=h).json()
    assert len(runs) == n + 1 and runs[0]["id"] == run.id
    # The upheld challenge changed the evidence, so the data fingerprint differs from the first run.
    assert runs[0]["data_hash"] != runs[-1]["data_hash"]


def _wait_for_run(client, headers, run_id, timeout=120):
    import time

    t0 = time.time()
    while time.time() - t0 < timeout:
        r = client.get(f"/research/runs/{run_id}", headers=headers).json()
        if r["status"] in ("completed", "failed"):
            return r
        time.sleep(0.5)
    raise AssertionError("research run did not finish")


def test_research_lab_runs_reproduces_and_exports(api_client):
    h = login(api_client, "u-SYN-RES")
    ov = api_client.get("/research/overview", headers=h).json()
    assert {w["id"] for w in ov["workstreams"]} >= {"hypotheses", "regression", "classification", "scenarios"}
    assert any(m["name"] == "context_adjusted_delivery" for m in ov["model_registry"])
    run = api_client.post("/research/runs", json={"workstream": "causal_raw_kpis"}, headers=h).json()
    done = _wait_for_run(api_client, h, run["id"])
    assert done["status"] == "completed", done.get("error")
    assert done["dataset_version"].startswith("ds-") and done["result"]["plain_language"]
    rep = api_client.post(f"/research/runs/{run['id']}/reproduce", json={}, headers=h).json()
    again = _wait_for_run(api_client, h, rep["id"])
    assert again["reproduced_identically"] is True
    md = api_client.get(f"/research/runs/{run['id']}/report", headers=h)
    assert md.status_code == 200 and md.text.startswith("# ")
    assert api_client.post("/research/runs", json={"workstream": "nope"}, headers=h).status_code == 404
    assert api_client.post("/research/runs", json={"workstream": "eda_variables", "params": {"sql": "x"}}, headers=h).status_code == 422


def test_research_access_is_restricted(api_client):
    emp = _personas(api_client)[("synthetic-pmo", "Employee")]
    h = login(api_client, emp["user_id"])
    assert api_client.get("/research/overview", headers=h).status_code == 403
    assert api_client.post("/research/runs", json={"workstream": "eda_variables"}, headers=h).status_code == 403
    assert api_client.get("/research/overview", headers=login(api_client, "u-SBX-RES")).status_code == 403  # not approved
    # Measurement definitions are open to everyone ("How was this assessed?").
    m = api_client.get("/measurement/metrics/adjusted_schedule_estimate", headers=h).json()
    assert m["plain_language"] and m["prohibited_interpretations"]
    assert api_client.get("/measurement/metrics/unknown", headers=h).status_code == 404
    assert len(api_client.get("/research/library", headers=h).json()["entries"]) >= 30
    assert {f["id"] for f in api_client.get("/measurement/job-families", headers=h).json()} >= {"pmo", "engineering_example"}


def test_public_data_catalogue_is_listed_with_provenance(api_client):
    h = login(api_client, "u-SYN-RES")
    r = api_client.get("/research/public-data", headers=h).json()
    ids = {s["id"] for s in r["sources"]}
    assert {"ebspm", "maxwell", "nasa93", "desharnais", "china"} <= ids
    assert all(s["origin"] and s["terms"] and len(s["sha256"]) == 64 for s in r["sources"])
    assert "fetch-public-data" in r["fetch_command"]
    bad = api_client.post("/research/runs", json={"workstream": "public_data", "params": {"study": "x", "sql": 1}}, headers=h)
    assert bad.status_code == 422
