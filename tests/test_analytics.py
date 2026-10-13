import ast
from pathlib import Path

import numpy as np
import pytest

from meritvector_analytics.evaluation import recovery_report
from meritvector_analytics.features import LeakageError, assert_no_forbidden_columns, build_features, design_matrix
from meritvector_shared import FORBIDDEN_MODEL_COLUMNS

PKG = Path(__file__).resolve().parents[1] / "packages" / "analytics" / "meritvector_analytics"


def test_features_exclude_non_assessment_and_disputed(small_dataset):
    ev = small_dataset.events.copy()
    fs = build_features(ev, small_dataset.employees, small_dataset.config.as_of)
    assert set(fs.events["data_category"]) == {"assessment_evidence"}
    target = fs.milestones["event_id"].iloc[0]
    ev.loc[ev["event_id"] == target, "validation_status"] = "disputed"
    fs2 = build_features(ev, small_dataset.employees, small_dataset.config.as_of)
    assert target not in set(fs2.milestones["event_id"])


def test_right_censoring_guard(small_dataset):
    fs = build_features(small_dataset.events, small_dataset.employees, small_dataset.config.as_of)
    assert fs.censored_excluded > 0
    assert fs.milestones["planned_date"].max() <= fs.as_of - np.timedelta64(90, "D")


def test_design_matrix_has_no_forbidden_columns(small_result):
    X = design_matrix(small_result.features.milestones)
    assert not set(X.columns) & set(FORBIDDEN_MODEL_COLUMNS)
    with pytest.raises(LeakageError):
        assert_no_forbidden_columns(X.assign(true_contribution=1.0))


def test_training_code_never_reads_ground_truth():
    """Only evaluation.py may reference hidden ground truth."""
    for f in PKG.glob("*.py"):
        if f.name in ("evaluation.py", "synthetic.py"):
            continue
        tree = ast.parse(f.read_text())
        imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert "meritvector_analytics.evaluation" not in imported, f.name
        assert "ground_truth" not in f.read_text(), f.name


def test_pipeline_outputs(small_result):
    r = small_result
    assert {"schedule_variance_pct", "quality_score"} == set(r.estimates["outcome"])
    assert all(c["passed"] for c in r.validation["leakage_checks"])
    assert r.metrics["context_models"]["schedule_variance_pct"]["diagnostics"]["mixed_converged"]
    assert {"global_mean", "context_ols", "context_plus_employee_mixed"} <= set(r.validation["out_of_time"]["models"])
    assert r.model_card.startswith("# Model card")
    # Abstention: people with very few milestones are never given a strong conclusion.
    sched = r.estimates[r.estimates["outcome"] == "schedule_variance_pct"]
    assert (sched.loc[sched["n"] < 6, "conclusion"] == "insufficient_evidence").all()
    # No ranking fields anywhere.
    assert not {"rank", "ranking", "percentile", "promotion_readiness"} & set(r.estimates.columns)


def test_competencies_never_score_promotion(small_result):
    c = small_result.competencies
    assert set(c["status"]) <= {"demonstrated", "emerging", "evidence_gap", "not_expected_at_level", "demonstrated_beyond_level"}


def test_results_are_reproducible(small_dataset, small_result):
    from meritvector_analytics.pipeline import run_pipeline

    d = small_dataset
    again = run_pipeline(d.events, d.employees, str(d.config.as_of), n_boot=30)
    a = small_result.estimates.sort_values(["outcome", "employee_id"])["adjusted_estimate"].to_numpy()
    b = again.estimates.sort_values(["outcome", "employee_id"])["adjusted_estimate"].to_numpy()
    assert np.allclose(a, b)
    assert small_result.data_hash == again.data_hash
    assert small_result.validation["out_of_time"]["models"] == again.validation["out_of_time"]["models"]


def test_fairness_audit_is_aggregated_only(small_result):
    f = small_result.fairness
    assert f is not None
    for g in f["groups"]:
        assert "employee_id" not in g


def test_recovery_small_org(small_dataset, small_result):
    rep = recovery_report(small_result, small_dataset.ground_truth, small_dataset.manager_ratings)
    assert rep["spearman_truth_vs_adjusted"] > rep["spearman_truth_vs_raw"]
