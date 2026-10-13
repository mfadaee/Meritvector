"""Scenario lab A–F: each scenario's analysis must reach the conclusion its hidden truth supports."""

from meritvector_analytics.simulations import scenarios


def test_a_raw_gap_is_explained_by_conditions():
    r = scenarios.scenario_a()
    assert r["people"]["A"]["raw_on_time"] - r["people"]["B"]["raw_on_time"] > 0.5  # raw metrics strongly favour A
    lo, hi = r["difference_b_minus_a"]["ci95"]
    assert lo <= r["_truth"]["true_difference_pp"] <= hi  # truth (no difference) inside the interval
    assert "does not support" in r["finding"]


def test_a_detects_a_real_difference_when_there_is_one():
    r = scenarios.scenario_a(scenarios.ScenarioAConfig(skill_b=1.5))
    assert r["difference_b_minus_a"]["ci95"][0] > 0


def test_b_activity_is_not_contribution():
    r = scenarios.scenario_b()
    assert abs(r["population"]["spearman_meetings_quality"]) < 0.2
    assert r["people"]["A"]["meetings_per_month"] > r["people"]["B"]["meetings_per_month"]
    assert r["people"]["B"]["quality_mean"] > r["people"]["A"]["quality_mean"]


def test_c_rater_effects_are_detected():
    r = scenarios.scenario_c()
    assert r["rater_effect_test"]["p_value"] < 0.01
    assert abs(r["rater_effect_test"]["estimated_rater_gap"] - r["_truth"]["leniency_gap"]) < 0.6


def test_d_adjustment_reverses_misleading_raw_trend():
    r = scenarios.scenario_d()
    assert r["raw_slope_per_year"]["estimate"] > 0  # raw: looks worse over time
    assert r["adjusted_slope_per_year"]["estimate"] > 0  # adjusted: improving, same sign as truth
    lo, hi = r["adjusted_slope_per_year"]["ci95"]
    assert lo <= r["_truth"]["true_slope_pp_per_year"] <= hi


def test_e_visibility_moves_ratings_not_evidence():
    r = scenarios.scenario_e()["difference_in_differences"]
    assert r["rating"]["ci95"][0] > 0
    assert r["evidence"]["ci95"][0] <= 0 <= r["evidence"]["ci95"][1]


def test_f_fixed_teams_are_not_individually_identifiable():
    r = scenarios.scenario_f()
    assert r["fixed_team"]["identifiable"] is False
    assert r["with_verified_workstream_evidence"]["spearman_with_truth"] >= r["rotating_teams"]["spearman_with_truth"] - 0.05


def test_public_view_hides_truth():
    assert all(not k.startswith("_") for k in scenarios.public(scenarios.scenario_b()))
