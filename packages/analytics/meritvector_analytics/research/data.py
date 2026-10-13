"""Research dataset: one object holding the observable frames plus lazily computed derived tables."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

import numpy as np
import pandas as pd

from meritvector_analytics.contextual import ContextResult, fit_context_ols, run_contextual
from meritvector_analytics.features import FeatureSet, build_features, employee_activity_summary
from meritvector_shared import FORBIDDEN_MODEL_COLUMNS


def pseudonym(employee_id: str) -> str:
    return "R-" + hashlib.sha256(f"mv-research:{employee_id}".encode()).hexdigest()[:8]


def jsonable(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [jsonable(v) for v in o]
    if isinstance(o, np.generic):
        o = o.item()
    if isinstance(o, float) and not np.isfinite(o):
        return None
    if isinstance(o, pd.Timestamp):
        return o.isoformat()
    return o


@dataclass
class ResearchData:
    events: pd.DataFrame
    employees: pd.DataFrame
    projects: pd.DataFrame
    milestones: pd.DataFrame
    risks: pd.DataFrame
    dependencies: pd.DataFrame
    ratings: pd.DataFrame
    as_of: str
    seed: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_synthetic(cls, ds) -> ResearchData:
        return cls(
            events=ds.events,
            employees=ds.employees,
            projects=ds.projects,
            milestones=ds.milestones,
            risks=ds.risks,
            dependencies=ds.dependencies,
            ratings=ds.manager_ratings,
            as_of=str(ds.config.as_of),
            seed=ds.config.seed,
            meta={"source": "synthetic", **ds.metadata["counts"]},
        )

    # -------------------------------------------------------------- versioning
    @cached_property
    def dataset_version(self) -> str:
        h = hashlib.sha256()
        for eid, st in sorted(zip(self.events["event_id"], self.events["validation_status"], strict=True)):
            h.update(f"{eid}:{st};".encode())
        h.update(json.dumps(sorted(self.projects["project_id"].tolist())).encode())
        return "ds-" + h.hexdigest()[:12]

    # -------------------------------------------------------------- derived
    @cached_property
    def features(self) -> FeatureSet:
        return build_features(self.events, self.employees, self.as_of)

    @cached_property
    def milestone_frame(self) -> pd.DataFrame:
        """Milestone features joined with the PMO's recorded (unmodelled) project dimensions."""
        m = self.features.milestones
        extra = [
            c
            for c in self.projects.columns
            if c not in m.columns
            and c
            not in (
                "tenant_id",
                "name",
                "lead_employee_id",
                "start_date",
                "planned_end",
                "actual_end",
                "status",
                "is_synthetic",
                "kind",
            )
        ]
        out = m.merge(self.projects[["project_id", *extra]], on="project_id", how="left")
        bad = set(out.columns) & set(FORBIDDEN_MODEL_COLUMNS)
        assert not bad, bad
        return out

    @cached_property
    def schedule(self) -> ContextResult:
        return run_contextual(self.features.milestones, "schedule_variance_pct")

    @cached_property
    def context_ols(self):
        return fit_context_ols(self.features.milestones, "schedule_variance_pct")

    @cached_property
    def employee_frame(self) -> pd.DataFrame:
        m = self.features.milestones
        est = self.schedule.mixed_estimates.set_index("employee_id")
        resid = self.schedule.residual_estimates.set_index("employee_id")
        g = m.groupby("employee_id")
        df = pd.DataFrame(
            {
                "n_milestones": g.size(),
                "raw_on_time": g["on_time"].mean(),
                "raw_mean_svp": g["schedule_variance_pct"].mean(),
                "mean_complexity": g["technical_complexity"].mean(),
                "mean_resource_constraint": g["resource_constraint"].mean(),
                "quality_mean": g["quality_score"].mean(),
            }
        )
        df = df.join(est[["adjusted_estimate", "ci_low", "ci_high", "conclusion"]].rename(columns={"adjusted_estimate": "adjusted_signal"}))
        df = df.join(resid[["context_expected"]])
        # Early vs later periods (for assignment analysis).
        first = m[m["month_index"] < 12].groupby("employee_id")
        later = m[m["month_index"] >= 12]
        ols, d = self.context_ols
        d = d.assign(fitted=ols.fittedvalues)
        df["first_year_on_time"] = first["on_time"].mean()
        df["first_year_n"] = first.size()
        df["later_context_expected"] = d[d["month_index"] >= 12].groupby("employee_id")["fitted"].mean()
        df["later_n"] = later.groupby("employee_id").size()
        act = employee_activity_summary(self.features.activity).set_index("employee_id")
        df = df.join(act)
        r = self.ratings.groupby("employee_id").agg(mean_rating=("manager_rating", "mean"), rater_id=("rater_id", "last"))
        df = df.join(r)
        emp = self.employees.set_index("employee_id")[["job_family", "business_unit", "level", "manager_id"]]
        df = df.join(emp, how="left").reset_index()
        df["pid"] = df["employee_id"].map(pseudonym)
        return df

    @cached_property
    def project_frame(self) -> pd.DataFrame:
        m = self.features.milestones
        g = m.groupby("project_id")
        out = self.projects.set_index("project_id").join(
            pd.DataFrame(
                {
                    "milestones_settled": g.size(),
                    "project_on_time": g["on_time"].mean(),
                    "project_mean_svp": g["schedule_variance_pct"].mean(),
                    "project_quality": g["quality_score"].mean(),
                }
            ),
            how="left",
        )
        issues = self.risks[self.risks["kind"] == "issue"].groupby("project_id").size()
        rk = self.risks.groupby("project_id").size()
        out["risks"] = rk.reindex(out.index).fillna(0)
        out["issues"] = issues.reindex(out.index).fillna(0)
        owned = self.risks.groupby("project_id").size()
        out["risks_owned"] = owned.reindex(out.index).fillna(0)
        return out.reset_index()
