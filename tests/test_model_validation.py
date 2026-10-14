"""Scientific validation on the full 300-person synthetic organisation (takes ~1 minute)."""

import pytest

from meritvector_analytics.evaluation import recovery_report


@pytest.mark.slow
def test_context_adjustment_recovers_hidden_contribution(full_dataset, full_result):
    rep = recovery_report(full_result, full_dataset.ground_truth, full_dataset.manager_ratings)
    assert rep["spearman_truth_vs_adjusted"] >= 0.65
    assert rep["spearman_truth_vs_adjusted"] - rep["spearman_truth_vs_raw"] >= 0.25
    # Historical ratings are a biased label: they track the truth poorly.
    assert rep["spearman_truth_vs_manager_rating"] < rep["spearman_truth_vs_adjusted"]
    # 95% intervals should roughly cover the true effect.
    assert rep["interval_coverage_of_true_effect"] >= 0.8
    assert rep["directional_accuracy_of_strong_conclusions"] >= 0.85


@pytest.mark.slow
def test_out_of_time_model_beats_baselines(full_result):
    models = full_result.validation["out_of_time"]["models"]
    assert models["context_ols"]["mae"] < models["global_mean"]["mae"]
    assert models["context_plus_employee_mixed"]["mae"] < models["context_ols"]["mae"]
    assert all(c["passed"] for c in full_result.validation["leakage_checks"])
    assert full_result.validation["calibration"]["brier"] < full_result.validation["calibration"]["brier_climatology"]


@pytest.mark.slow
def test_experiment_reports_uncertainty_honestly(full_result):
    e = full_result.experiment
    assert e["status"] in {"supported_difference", "inconclusive"}
    assert e["raw_metrics"]["A"]["on_time_rate"] > e["raw_metrics"]["B"]["on_time_rate"]
    assert e["operating_conditions"]["B"]["context_expected_variance_pct"] > e["operating_conditions"]["A"]["context_expected_variance_pct"]
    assert len(e["sensitivity"]) >= 5
    if e["status"] == "inconclusive":
        assert "Inconclusive" in e["verdict"]


@pytest.mark.slow
def test_fairness_audit_detects_synthetic_rating_bias(full_result):
    f = full_result.fairness
    assert f["gaps"]["rating"]["ci_low"] > 0  # the generator penalises group G2 in ratings only
    assert "rating bias" in f["finding"]


@pytest.mark.slow
def test_within_person_model_recovers_true_context_effects(full_result):
    """Generator: +5.5 pp per complexity level, +22 pp per unit resource shortfall, +2.2 pp per dependency."""
    w = full_result.metrics["context_models"]["schedule_variance_pct"]["diagnostics"]["within_person_coefficients"]
    assert abs(w["technical_complexity"] - 5.5) < 1.2
    assert abs(w["resource_constraint"] - 22.0) < 4.0
    assert abs(w["dependency_count"] - 2.2) < 0.6


@pytest.mark.slow
def test_people_on_difficult_projects_are_not_under_credited(full_dataset, full_result):
    rep = recovery_report(full_result, full_dataset.ground_truth, full_dataset.manager_ratings)
    arche = {r["archetype"]: r for r in rep["by_archetype"]}
    hard = arche["difficult_projects_strong"]
    assert hard["mean_raw"] < 0 < hard["mean_adjusted"]  # raw KPIs penalise them; adjustment does not
    assert abs(hard["mean_adjusted"] - hard["mean_true_effect"]) < 3.0


@pytest.mark.slow
def test_negative_controls_are_null_with_clustered_inference(full_dataset):
    from meritvector_analytics.research import ResearchData
    from meritvector_analytics.research.regression import negative_controls

    nc = negative_controls(ResearchData.from_synthetic(full_dataset))
    assert nc["joint_p"] >= 0.05
