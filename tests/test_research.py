"""Research laboratory workstreams (small synthetic organisation, fast)."""

import pandas as pd
import pytest

from meritvector_analytics.research import (
    ResearchData,
    causal,
    classification,
    clustering,
    eda,
    experiments,
    growth,
    hypotheses,
    lab,
    pseudonym,
    regression,
)
from meritvector_analytics.research.registry import MILESTONE_RISK_SPEC, ModelSpec
from meritvector_shared import FORBIDDEN_MODEL_COLUMNS


@pytest.fixture(scope="module")
def rd(small_dataset):
    return ResearchData.from_synthetic(small_dataset)


def test_dataset_version_is_stable_and_content_addressed(rd, small_dataset):
    assert rd.dataset_version.startswith("ds-")
    assert ResearchData.from_synthetic(small_dataset).dataset_version == rd.dataset_version


def test_research_frames_never_contain_forbidden_columns(rd):
    for df in (
        rd.milestone_frame,
        rd.employee_frame.drop(columns=["mean_rating", "meetings_per_month", "emails_per_month", "hours_per_month"]),
    ):
        assert not set(df.columns) & set(FORBIDDEN_MODEL_COLUMNS)


def test_eda_describes_distributions(rd):
    v = eda.variables(rd, "milestone")["variables"]["schedule_variance_pct"]
    assert v["n"] > 100 and v["p25"] <= v["median"] <= v["p75"] and v["iqr"] >= 0
    assert sum(v["histogram"]["counts"]) == v["n"]
    assert eda.missingness(rd)["rates"]["quality_score"] > 0


def test_assignment_analysis_detects_non_random_assignment(rd):
    a = eda.assignment_analysis(rd)
    assert 0 < a["difficulty_between_people"]["icc1"] < 1


def test_registered_hypotheses_report_effect_sizes(rd):
    res = hypotheses.run_hypotheses(rd)["hypotheses"]
    assert set(res) == {f"H{i}" for i in range(1, 9)}
    for hid in ("H2", "H3", "H5", "H6"):
        r = res[hid]["result"]
        assert "p_value" in r and "p_adjusted" in r and r["p_adjusted"] >= r["p_value"] - 1e-12
        assert r["effect_size"]["value"] is not None
    assert res["H6"]["result"]["assumptions"]["unit"].startswith("project means")


def test_regression_comparison_and_negative_controls(rd):
    r = regression.compare_models(rd, folds=3)
    names = {m["model"] for m in r["models"]}
    assert {"ols_linear", "ridge_cv", "lasso_cv", "ols_interactions", "spline_additive", "gradient_boosting"} <= names
    nc = r["negative_controls"]
    assert "joint_p" in nc and "naive_iid_p" in nc
    assert all(row["n_train"] > 0 for row in r["learning_curve"])


def test_classifier_features_are_point_in_time(rd):
    snaps = classification.build_snapshots(rd)
    assert (snaps["_max_feature_time"] <= snaps["snapshot_date"]).all()
    assert set(snaps["label"]) == {0, 1}


def test_classifier_features_ignore_future_records(rd):
    """Deleting everything after a snapshot date must not change that snapshot's features."""
    snaps = classification.build_snapshots(rd)
    row = snaps.iloc[len(snaps) // 2]
    cutoff = row["snapshot_date"]
    pid = row["project_id"]
    trimmed = ResearchData(
        events=rd.events[pd.to_datetime(rd.events["occurred_at"]) <= cutoff],
        employees=rd.employees,
        projects=rd.projects,
        milestones=rd.milestones.assign(
            actual_date=[a if (a is not None and pd.notna(a) and pd.Timestamp(a) <= cutoff) else None for a in rd.milestones["actual_date"]]
        ),
        risks=rd.risks.assign(
            mitigated_on=[m if (m is not None and pd.notna(m) and pd.Timestamp(m) <= cutoff) else None for m in rd.risks["mitigated_on"]]
        ),
        dependencies=rd.dependencies.assign(
            resolved_on=[
                x if (x is not None and pd.notna(x) and pd.Timestamp(x) <= cutoff) else None for x in rd.dependencies["resolved_on"]
            ]
        ),
        ratings=rd.ratings,
        as_of=rd.as_of,
    )
    again = classification.build_snapshots(trimmed)
    a = snaps[(snaps.project_id == pid) & (snaps.snapshot_date == cutoff)].iloc[0]
    b = again[(again.project_id == pid) & (again.snapshot_date == cutoff)].iloc[0]
    for f in classification.FEATURES:
        assert a[f] == b[f], f


def test_classifier_reports_full_metric_set(rd):
    r = classification.train_and_evaluate(rd)
    assert r["leakage_check"]["all_features_before_snapshot"]
    for m in r["models"]:
        assert {"precision", "recall", "f1", "pr_auc", "roc_auc", "brier", "confusion", "calibration", "threshold"} <= set(m)
    assert "heuristic_last_milestone_slipped" in r["baselines"]
    assert "evaluat" in r["use_restriction"].lower()


def test_clustering_requires_stability(rd):
    r = clustering.explore(rd, k_range=range(2, 4), n_boot=5)
    assert r["unit"] == "project"
    assert r["selected_k"] is None or all("jaccard_stability" in p for p in r["profiles"])


def test_growth_model_runs(rd):
    g = growth.growth_model(rd)
    assert 0 <= g["p_value"] <= 1 and g["slope_sd_pp_per_year"] >= 0


def test_dag_backdoor_logic():
    spec = causal.load_dags()["resources_delivery"]
    dag = causal.DAG(spec["nodes"], spec["edges"])
    measured = set(spec["candidate_adjustment_sets"]["measured_context"])
    assert dag.backdoor_ok("resource_constraint", "schedule_variance_pct", measured) is False  # latent skill confounds
    full = causal.DAG({**spec["nodes"], "skill": {"observed": True}, "assignment_policy": {"observed": True}}, spec["edges"])
    assert full.backdoor_ok("resource_constraint", "schedule_variance_pct", measured | {"assignment_policy"}) is True
    assert causal.e_value_from_d(0.0) == pytest.approx(1.0)


def test_coordinator_experiment_has_power_analysis_and_cuped(small_dataset):
    r = experiments.coordinator_experiment(small_dataset.employees)
    assert r["power"]["minimum_detectable_effect_pp"] > 0
    assert "cuped_difference_pp" in r["primary"] and "did_estimate_pp" in r["quasi_experiment"]


def test_model_spec_refuses_incomplete_or_unsafe_specs():
    ModelSpec(version="t", **MILESTONE_RISK_SPEC)
    with pytest.raises(ValueError):
        ModelSpec(version="t", **{**MILESTONE_RISK_SPEC, "prohibited_uses": ["none"]})
    with pytest.raises(ValueError):
        ModelSpec(version="t", **{**MILESTONE_RISK_SPEC, "leakage_controls": []})


def test_lab_runs_are_reproducible_and_strip_private_fields(rd):
    a = lab.run(rd, "causal_resources")
    b = lab.run(rd, "causal_resources")
    assert a["result_hash"] == b["result_hash"] and a["dataset_version"] == rd.dataset_version
    g = lab.run(rd, "growth")
    assert "_slopes" not in g["result"]
    md = lab.report_markdown(a)
    assert md.startswith("# ") and "Synthetic data" in md


def test_pseudonyms_are_stable_and_not_identifying():
    assert pseudonym("SYN-E0001") == pseudonym("SYN-E0001") and "E0001" not in pseudonym("SYN-E0001")
