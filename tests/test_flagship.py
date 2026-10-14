"""Flagship v2: do raw performance metrics misrepresent project-manager contribution?"""

from __future__ import annotations

import re

import pytest
from conftest import login

from meritvector_analytics.evaluation import flagship_truth_check
from meritvector_analytics.flagship import render_report, run_flagship

STEPS = ["1_raw_outcomes", "2_assignment", "3_models", "4_uncertainty", "5_interpretations", "6_sensitivity", "7_proxies"]


@pytest.fixture(scope="module")
def flagship(full_result, full_dataset):
    return run_flagship(full_result, full_dataset.manager_ratings)


def test_all_seven_steps_have_evidence_and_plain_language(flagship):
    assert list(flagship["steps"]) == STEPS
    for k in STEPS:
        if k != "5_interpretations":
            assert len(flagship["steps"][k]["plain_language"]) > 40, k
    assert flagship["steps"]["2_assignment"]["icc_complexity_within_pm"] > 0
    assert flagship["steps"]["4_uncertainty"]["conclusion_counts"]


def test_examples_are_pseudonymous_and_selected_by_an_observable_rule(flagship, full_result, full_dataset):
    ex = flagship["steps"]["5_interpretations"]["examples"]
    assert 1 <= len(ex) <= 4
    assert all(re.fullmatch(r"PM-\d{3}", e["person"]) for e in ex)
    assert "observable" in flagship["steps"]["5_interpretations"]["selection_rule"]
    # Deterministic: the same inputs select the same people.
    again = run_flagship(full_result, full_dataset.manager_ratings)
    assert [e["person"] for e in again["steps"]["5_interpretations"]["examples"]] == [e["person"] for e in ex]


def test_adjusted_evidence_tracks_truth_better_than_every_proxy(flagship, full_result, full_dataset):
    t = flagship_truth_check(full_result, flagship, full_dataset.ground_truth)
    rho = {r["signal"]: r["spearman_with_truth"] for r in t["signals"]}
    adjusted = rho.pop("MeritVector context-adjusted estimate")
    assert adjusted > 0.6 and all(adjusted > v + 0.3 for v in rho.values())
    assert t["adjusted_above_truly_above_average"] > t["raw_top_quintile_truly_above_average"]
    assert set(t["example_true_effects_pp"]) == {e["person"] for e in flagship["steps"]["5_interpretations"]["examples"]}


def test_report_renders_every_step_without_identifiers(flagship, full_result, full_dataset):
    md = render_report(flagship, flagship_truth_check(full_result, flagship, full_dataset.ground_truth), {"Real": "x"})
    for n in range(1, 8):
        assert f"## Step {n} " in md
    assert "SYN-E" not in md and "hidden synthetic truth" in md


def test_flagship_endpoint_is_restricted_and_pseudonymised(api_client):
    from test_api import _personas

    r = api_client.get("/analysis/flagship", headers=login(api_client, "u-SYN-RES"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert list(body["steps"]) == STEPS and "_people" not in body
    assert "SYN-E" not in r.text
    assert body["truth_check"]["note"].startswith("Evaluation only")
    assert api_client.get("/analysis/flagship", headers=login(api_client, "u-SYN-HR1")).status_code == 200
    for label in ("Manager", "Employee"):
        u = _personas(api_client)[("synthetic-pmo", label)]
        assert api_client.get("/analysis/flagship", headers=login(api_client, u["user_id"])).status_code == 403
    assert api_client.get("/analysis/flagship", headers=login(api_client, "u-SYN-ADMIN")).status_code == 403
