"""Layer D — evidence-based development insights.

Maps validated evidence to a configurable job-level competency framework. Produces
"demonstrated / emerging / evidence gap" per competency with links to the evidence
records. It deliberately does **not** produce promotion readiness, scores or ranks;
any employment-related use requires qualified human review.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from importlib import resources
from typing import Any

import pandas as pd

from meritvector_analytics.features import ON_TIME_THRESHOLD_PCT, FeatureSet


def load_framework(path: str | None = None) -> dict[str, Any]:
    if path:
        with open(path) as fh:
            return json.load(fh)
    return json.loads(resources.files("meritvector_analytics.config").joinpath("competency_framework.json").read_text())


def _p(ev: pd.DataFrame, key: str) -> pd.Series:
    return ev["payload"].map(lambda p: p.get(key) if isinstance(p, dict) else None)


def _rule_frames(fs: FeatureSet) -> dict[str, pd.DataFrame]:
    """Each rule yields rows (employee_id, evidence_ref, occurred_at)."""
    ev, m = fs.events, fs.milestones
    ctx = m.drop_duplicates("project_id").set_index("project_id")
    cols = ["employee_id", "evidence_ref", "occurred_at"]

    def cat(c: str) -> pd.DataFrame:
        return ev[ev["category"] == c]

    rules: dict[str, Callable[[], pd.DataFrame]] = {
        "milestone_on_time": lambda: ev[
            ev["event_id"].isin(m.loc[m["schedule_variance_pct"] <= ON_TIME_THRESHOLD_PCT, "event_id"])
        ],
        "benefits_case_met": lambda: cat("project_outcome")[_p(cat("project_outcome"), "benefits_case_met") == True],  # noqa: E712
        "first_pass_approval_complex": lambda: (
            lambda d: d[
                (_p(d, "approved_first_pass") == True)  # noqa: E712
                & (d["project_id"].map(ctx["technical_complexity"]) >= 4)
            ]
        )(cat("document_reviewed")),
        "blocker_resolved_fast": lambda: (lambda d: d[_p(d, "days_to_resolve").astype(float) <= 7])(cat("blocker_resolved")),
        "dependency_resolved": lambda: cat("dependency_resolved"),
        "cross_unit_dependency_resolved": lambda: (lambda d: d[_p(d, "cross_unit") == True])(cat("dependency_resolved")),  # noqa: E712
        "positive_stakeholder_feedback": lambda: (lambda d: d[_p(d, "score").astype(float) >= 4])(cat("stakeholder_feedback")),
        "proactive_risk": lambda: (lambda d: d[_p(d, "proactive") == True])(cat("risk_identified")),  # noqa: E712
        "risk_mitigated": lambda: cat("risk_mitigated"),
        "scope_change_governed": lambda: cat("scope_change_approved"),
        "programme_milestone": lambda: ev[
            (ev["category"] == "milestone_achieved") & (ev["project_id"].map(ctx["programme"]) == True)  # noqa: E712
        ],
    }
    return {k: f()[cols] for k, f in rules.items()}


def competency_evidence(fs: FeatureSet, framework: dict[str, Any] | None = None) -> pd.DataFrame:
    fw = framework or load_framework()
    window_start = fs.as_of - pd.DateOffset(months=int(fw.get("window_months", 12)))
    frames = _rule_frames(fs)
    m = fs.milestones
    had_complex = m.groupby("employee_id")["technical_complexity"].max() >= 4
    tagged = pd.concat([f.assign(rule=r) for r, f in frames.items()], ignore_index=True)
    by_emp = {k: g for k, g in tagged.groupby("employee_id")}
    empty = tagged.iloc[0:0]
    rows = []
    for emp in fs.employees.itertuples():
        expected = fw["levels"].get(emp.level, {})
        mine = by_emp.get(emp.employee_id, empty)
        for key, comp in fw["competencies"].items():
            ev = mine[mine["rule"].isin(comp["rules"])]
            ev = ev.drop_duplicates("evidence_ref").sort_values("occurred_at", ascending=False)
            recent = ev[ev["occurred_at"] >= window_start]
            need = expected.get(key)
            if need is None:
                status = "not_expected_at_level" if len(recent) == 0 else "demonstrated_beyond_level"
            elif len(recent) >= need:
                status = "demonstrated"
            elif len(recent) > 0:
                status = "emerging"
            else:
                status = "evidence_gap"
            note = None
            if comp.get("opportunity_rule") == "had_complex_project" and not bool(had_complex.get(emp.employee_id, False)):
                note = "No complexity 4–5 project assignments in the record — gap may reflect opportunity, not capability."
            elif status in ("evidence_gap", "emerging") and comp.get("perception_based"):
                note = "Perception-based evidence; survey coverage is incomplete and noisy."
            rows.append(
                {
                    "employee_id": emp.employee_id,
                    "competency": key,
                    "label": comp["label"],
                    "evidence_total": int(len(ev)),
                    "evidence_window": int(len(recent)),
                    "expected_at_level": need,
                    "status": status,
                    "examples": ev["evidence_ref"].head(3).tolist(),
                    "opportunity_note": note,
                }
            )
    return pd.DataFrame(rows)
