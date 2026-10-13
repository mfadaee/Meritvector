import hashlib

import pandas as pd

from meritvector_analytics.synthetic import SyntheticConfig, generate
from meritvector_shared import FORBIDDEN_MODEL_COLUMNS


def test_full_organisation_shape(full_dataset):
    c = full_dataset.metadata["counts"]
    assert c["employees"] == 300
    assert c["program_managers"] == 30 and c["project_managers"] == 200 and c["technical_project_managers"] == 70
    assert c["projects"] >= 100
    assert c["business_units"] >= 3
    span = pd.to_datetime(full_dataset.events["occurred_at"])
    assert (span.max() - span.min()).days >= 700  # ~24 months of history
    assert full_dataset.projects["technical_complexity"].nunique() == 5


def test_everything_is_labelled_synthetic(full_dataset):
    assert full_dataset.employees["is_synthetic"].all()
    assert full_dataset.projects["is_synthetic"].all()
    assert full_dataset.meetings["is_synthetic"].all()
    assert all(e["synthetic"] for e in full_dataset.events["provenance"])
    assert "SYNTHETIC" in full_dataset.metadata["label"]


def test_reproducible_with_seed():
    cfg = SyntheticConfig(seed=5, n_program_managers=2, n_project_managers=10, n_technical_pms=3)
    h = [hashlib.sha256(generate(cfg).events.to_json().encode()).hexdigest() for _ in range(2)]
    assert h[0] == h[1]
    other = generate(SyntheticConfig(seed=6, n_program_managers=2, n_project_managers=10, n_technical_pms=3))
    assert hashlib.sha256(other.events.to_json().encode()).hexdigest() != h[0]


def test_hidden_truth_is_not_in_observable_tables(full_dataset):
    for name in full_dataset.OBSERVABLE:
        df = getattr(full_dataset, name)
        hidden = {
            "true_contribution",
            "growth_per_year",
            "activity_propensity",
            "visibility",
            "archetype",
            "rater_leniency",
            "protected_group",
        }
        assert not hidden & set(df.columns), name
    payload_keys = set().union(*full_dataset.events["payload"].map(lambda p: set(p)))
    assert not payload_keys & set(FORBIDDEN_MODEL_COLUMNS) - {"meetings_attended", "emails_sent", "working_hours"}


def test_required_variation_present(full_dataset):
    arche = set(full_dataset.ground_truth["archetype"])
    assert {
        "difficult_projects_strong",
        "favourable_projects_average",
        "high_activity_weaker_outcomes",
        "low_visibility_strong",
        "improving",
        "resource_constrained",
    } <= arche
    # Manager ratings exist and are an imperfect label.
    assert full_dataset.manager_ratings["manager_rating"].between(1, 5).all()


def test_evidence_records_have_required_fields(small_dataset):
    required = {
        "event_id",
        "employee_id",
        "project_id",
        "occurred_at",
        "source_system",
        "category",
        "evidence_ref",
        "quality_indicators",
        "provenance",
        "validation_status",
    }
    assert required <= set(small_dataset.events.columns)
