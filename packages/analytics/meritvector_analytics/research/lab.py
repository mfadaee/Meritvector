"""Research laboratory runner: dispatch a workstream, record provenance, render a report."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from typing import Any

from meritvector_analytics import __version__
from meritvector_analytics.research import causal, classification, clustering, eda, experiments, growth, hypotheses, regression
from meritvector_analytics.research.data import ResearchData, jsonable
from meritvector_analytics.research.registry import CONTEXT_MODEL_SPEC, MILESTONE_RISK_SPEC, ModelSpec
from meritvector_analytics.simulations import scenarios


def _hypotheses(rd: ResearchData, **_: Any) -> dict[str, Any]:
    ex = experiments.coordinator_experiment(rd.employees)
    g = growth.growth_model(rd)
    extra = {
        "H7": {
            "statistic": ex["primary"]["difference_pp"],
            "p_value": ex["primary"]["welch_p"],
            "effect_size": {"name": "difference (pp)", "value": ex["primary"]["difference_pp"], "ci95": ex["primary"]["ci_pp"]},
            "n": ex["primary"]["n_treatment"] + ex["primary"]["n_control"],
            "assumptions": {"design": "randomised (simulated)"},
        },
        "H8": {
            "statistic": g["lrt_statistic"],
            "p_value": g["p_value"],
            "effect_size": {"name": "slope SD (pp/year)", "value": g["slope_sd_pp_per_year"], "ci95": None},
            "n": g["n_employees"],
            "assumptions": {"test": "boundary-corrected LRT"},
        },
    }
    return hypotheses.run_hypotheses(rd, extra=extra)


def _scenario(rd: ResearchData, scenario: str = "A", **_: Any) -> dict[str, Any]:
    return scenarios.public(scenarios.SCENARIOS[scenario.upper()]())


def _scenarios_all(rd: ResearchData, **_: Any) -> dict[str, Any]:
    return {
        "kind": "simulation",
        "status": "exploratory",
        "scenarios": {k: scenarios.public(v) for k, v in scenarios.run_all().items()},
    }


WORKSTREAMS: dict[str, tuple[str, Callable[..., dict[str, Any]]]] = {
    "eda_variables": ("EDA — variable distributions", lambda rd, level="employee", **_: eda.variables(rd, level)),
    "eda_correlations": ("EDA — correlations", lambda rd, level="employee", **_: eda.correlations(rd, level)),
    "eda_missingness": ("EDA — missing-data diagnostics", lambda rd, **_: eda.missingness(rd)),
    "assignment": ("RQ1 — assignment of difficult projects", lambda rd, **_: eda.assignment_analysis(rd)),
    "activity": ("RQ4 — activity vs contribution", lambda rd, **_: eda.activity_vs_contribution(rd)),
    "hypotheses": ("Registered hypothesis tests", _hypotheses),
    "regression": ("RQ2 — regression model comparison", lambda rd, **_: regression.compare_models(rd)),
    "classification": ("RQ6 — 30-day milestone risk", lambda rd, **_: classification.train_and_evaluate(rd)),
    "clustering": ("RQ7 — project environments (PCA & clustering)", lambda rd, **_: clustering.explore(rd)),
    "growth": ("RQ8 — growth model", lambda rd, **_: growth.growth_model(rd)),
    "causal_resources": ("RQ9 — resources and delivery (causal)", lambda rd, **_: causal.resources_delivery(rd)),
    "causal_raw_kpis": ("Raw KPIs and project difficulty", lambda rd, **_: causal.raw_kpis_difficulty(rd)),
    "experiment": ("RQ10 — coordinator experiment (simulated)", lambda rd, **_: experiments.coordinator_experiment(rd.employees)),
    "scenario": ("Scenario lab — single scenario", _scenario),
    "scenarios": ("Scenario lab — all scenarios A–F", _scenarios_all),
}


def strip_private(o: Any) -> Any:
    if isinstance(o, dict):
        return {k: strip_private(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, list):
        return [strip_private(v) for v in o]
    return o


def result_hash(result: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()[:16]


def run(rd: ResearchData, workstream: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    if workstream not in WORKSTREAMS:
        raise KeyError(f"unknown workstream {workstream!r}")
    params = params or {}
    title, fn = WORKSTREAMS[workstream]
    t0 = time.time()
    result = strip_private(jsonable(fn(rd, **params)))
    return {
        "workstream": workstream,
        "title": title,
        "params": params,
        "dataset_version": rd.dataset_version,
        "code_version": __version__,
        "seed": rd.seed,
        "duration_s": round(time.time() - t0, 2),
        "status": result.get("status", "exploratory"),
        "kind": result.get("kind"),
        "result": result,
        "result_hash": result_hash(result),
    }


def model_specs() -> list[dict[str, Any]]:
    return [
        ModelSpec(version="0.2", **CONTEXT_MODEL_SPEC).model_dump(),
        ModelSpec(version="0.2", **MILESTONE_RISK_SPEC).model_dump(),
    ]


def report_markdown(run_record: dict[str, Any]) -> str:
    r = run_record["result"]
    lines = [
        f"# {run_record['title']}",
        "",
        f"*Workstream `{run_record['workstream']}` · status **{run_record['status']}** · dataset {run_record['dataset_version']} · "
        f"code v{run_record['code_version']} · result hash `{run_record['result_hash']}`*",
        "",
        "> Synthetic data. Exploratory results describe method behaviour under a known simulation; they are not real-world findings.",
        "",
    ]
    for key in ("question", "conclusion", "interpretation", "plain_language", "identification", "finding"):
        if r.get(key):
            lines += [f"**{key.replace('_', ' ').capitalize()}.** {r[key]}", ""]
    lines += ["## Full result", "", "```json", json.dumps(r, indent=2, default=str)[:20000], "```", ""]
    return "\n".join(lines)
