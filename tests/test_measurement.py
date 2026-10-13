import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from meritvector_analytics.features import CONTEXT_CATEGORICAL, CONTEXT_NUMERIC
from meritvector_analytics.measurement import (
    config_dir,
    find_metric,
    list_job_families,
    load_job_family,
    load_library,
    load_ontology,
)
from meritvector_analytics.measurement.spec import CONSTRUCTS, JobFamilySpec, Ontology

ROOT = Path(__file__).resolve().parents[1]


def test_ontology_defines_all_constructs():
    o = load_ontology()
    assert set(o.constructs) == set(CONSTRUCTS)
    assert o.constructs["activity"].may_increase_merit is False
    for c in o.constructs.values():
        assert c.prohibited_interpretations and c.limitations and c.intended_use


def test_ontology_rejects_activity_as_merit():
    raw = yaml.safe_load((config_dir() / "measurement" / "ontology.yaml").read_text())
    raw["constructs"]["activity"]["may_increase_merit"] = True
    with pytest.raises(ValueError):
        Ontology.model_validate(raw)


def test_pmo_spec_dimensions():
    pmo = load_job_family("pmo")
    ids = {d.id for d in pmo.context_dimensions}
    required = {
        "budget_scope",
        "technical_complexity",
        "schedule_criticality",
        "organisational_visibility",
        "stakeholder_complexity",
        "cross_functional_dependencies",
        "resource_availability",
        "scope_volatility",
        "technical_uncertainty",
        "operational_criticality",
        "geographic_distribution",
        "vendor_complexity",
        "regulatory_constraints",
        "integration_difficulty",
        "delivery_maturity",
    }
    assert required <= ids
    assert len(pmo.responsibility_dimensions) == 10 and len(pmo.outcome_dimensions) == 10
    # Responsibility describes scope; it is never modelled as performance credit.
    assert all(d.status != "modelled" for d in pmo.responsibility_dimensions)


def test_context_model_reads_covariates_from_spec():
    numeric, categorical = load_job_family("pmo").context_covariates()
    assert numeric == CONTEXT_NUMERIC and categorical == CONTEXT_CATEGORICAL
    assert set(numeric) == {
        "technical_complexity",
        "dependency_count",
        "resource_constraint",
        "scope_changes_to_date",
        "team_size",
        "size_band",
    }


def test_second_job_family_is_valid_and_illustrative():
    fams = {f["id"]: f for f in list_job_families()}
    assert {"pmo", "engineering_example"} <= set(fams)
    eng = load_job_family("engineering_example")
    assert eng.status == "illustrative"
    assert all(d.status == "planned" for d in eng.context_dimensions)


def test_spec_validation_rejects_inconsistent_config():
    raw = yaml.safe_load((config_dir() / "job_families" / "pmo" / "family.yaml").read_text())
    bad = dict(raw, metrics=[dict(raw["metrics"][5], direction="higher_is_better")])  # activity metric
    with pytest.raises(ValueError):
        JobFamilySpec.model_validate(bad)
    bad2 = dict(raw, competencies=dict(raw["competencies"], levels={"Z9": {}}))
    with pytest.raises(ValueError):
        JobFamilySpec.model_validate(bad2)


def test_competency_framework_comes_from_spec():
    from meritvector_analytics.competency import load_framework

    fw = load_framework()
    assert fw["levels"]["P3"] == {
        "project_delivery": 6,
        "ownership": 4,
        "risk_leadership": 4,
        "stakeholder_management": 2,
        "technical_judgement": 1,
    }
    assert fw["competencies"]["technical_judgement"]["opportunity_rule"] == "had_complex_project"


def test_metric_definitions_have_plain_language():
    m = find_metric("adjusted_schedule_estimate")
    assert m and "conditions" in m.plain_language and m.prohibited_interpretations
    assert find_metric("activity_volume").direction == "neutral"
    assert find_metric("does_not_exist") is None


def test_evidence_library_is_well_formed():
    lib = load_library()["entries"]
    ids = [e["id"] for e in lib]
    assert len(ids) == len(set(ids)) and len(ids) >= 30
    for e in lib:
        assert e["verification"] in {"doi_confirmed", "citation_confirmed", "official_source"}
        assert e["url"], e["id"]
        for k in ("main_finding", "limitations", "relevance", "design_implications"):
            assert e[k], (e["id"], k)
    areas = {e["area"] for e in lib}
    assert {"performance_theory", "measurement", "ratings", "causal_inference", "governance"} <= areas


def test_ontology_references_exist_in_library():
    ids = {e["id"] for e in load_library()["entries"]}
    o = load_ontology()
    refs = set(o.conceptual_model.references) | {r for c in o.constructs.values() for r in c.references}
    assert refs <= ids, refs - ids


def test_generated_schema_and_docs_are_current():
    for script in ("scripts/export_schemas.py", "scripts/render_research_docs.py"):
        r = subprocess.run([sys.executable, str(ROOT / script), "--check"], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
