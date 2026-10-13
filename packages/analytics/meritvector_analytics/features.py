"""Feature engineering: raw evidence events -> engineered analysis tables.

Raw source records (``evidence_events``) are never modified here. This module derives
engineered features from them, using only information that was available at the
time each outcome was planned (no look-ahead), and only from records that are
eligible for assessment:

* ``data_category == "assessment_evidence"`` (assistance content, organisational
  reporting and diagnostic activity are excluded);
* validation status not ``disputed``/``retracted`` (employee challenges are honoured).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from meritvector_shared import EXCLUDED_VALIDATION_STATUSES, FORBIDDEN_MODEL_COLUMNS

CONTEXT_NUMERIC = [
    "technical_complexity",
    "dependency_count",
    "resource_constraint",
    "scope_changes_to_date",
    "team_size",
    "size_band",
]
CONTEXT_CATEGORICAL = ["environment", "maturity", "job_family"]
ON_TIME_THRESHOLD_PCT = 5.0
# Right-censoring guard: a milestone planned recently is only observed if it finished early or on time,
# so recent achieved milestones are an optimistic sample. Exclude milestones planned within this window.
CENSOR_WINDOW_DAYS = 90


@dataclass
class FeatureSet:
    milestones: pd.DataFrame  # one row per achieved milestone (unit of analysis)
    events: pd.DataFrame  # eligible assessment events, payload columns flattened where useful
    activity: pd.DataFrame  # diagnostic activity (never a model input)
    employees: pd.DataFrame
    as_of: pd.Timestamp
    censored_excluded: int = 0


class LeakageError(RuntimeError):
    pass


def assert_no_forbidden_columns(df: pd.DataFrame, where: str = "features") -> None:
    bad = sorted(set(df.columns) & set(FORBIDDEN_MODEL_COLUMNS))
    if bad:
        raise LeakageError(f"forbidden columns present in {where}: {bad}")


def _payload(df: pd.DataFrame, key: str, col: str = "payload") -> pd.Series:
    return df[col].map(lambda p: p.get(key) if isinstance(p, dict) else None)


def eligible_events(events: pd.DataFrame) -> pd.DataFrame:
    ev = events[
        (events["data_category"] == "assessment_evidence") & (~events["validation_status"].isin(EXCLUDED_VALIDATION_STATUSES))
    ].copy()
    ev["occurred_at"] = pd.to_datetime(ev["occurred_at"])
    return ev


def build_features(
    events: pd.DataFrame, employees: pd.DataFrame, as_of: str | pd.Timestamp, censor_window_days: int = CENSOR_WINDOW_DAYS
) -> FeatureSet:
    as_of_ts = pd.Timestamp(as_of)
    emp_cols = ["employee_id", "display_name", "job_family", "level", "business_unit", "manager_id", "joined_on"]
    emp = employees[[c for c in emp_cols if c in employees.columns]].copy()
    assert_no_forbidden_columns(emp, "employee attributes")

    activity = events[events["category"] == "activity_summary"].copy()
    if len(activity):
        for k in ("month", "meetings_attended", "emails_sent", "working_hours"):
            activity[k] = _payload(activity, k)
        activity = activity[["employee_id", "month", "meetings_attended", "emails_sent", "working_hours"]]

    ev = eligible_events(events)

    # Project context from the PMO complexity assessment (recorded at kick-off).
    ca = ev[ev["category"] == "complexity_assessment"].sort_values("occurred_at").drop_duplicates("project_id", keep="last")
    ctx = pd.DataFrame({"project_id": ca["project_id"].to_numpy()})
    for k in (
        "technical_complexity",
        "dependency_count",
        "resource_constraint",
        "size_band",
        "team_size",
        "environment",
        "maturity",
        "programme",
    ):
        ctx[k] = _payload(ca, k).to_numpy()
    ctx["project_start"] = ca["occurred_at"].dt.normalize().to_numpy()

    ma = ev[ev["category"] == "milestone_achieved"].copy()
    m = pd.DataFrame(
        {
            "event_id": ma["event_id"].to_numpy(),
            "employee_id": ma["employee_id"].to_numpy(),
            "project_id": ma["project_id"].to_numpy(),
            "milestone_id": _payload(ma, "milestone_id").to_numpy(),
            "planned_date": pd.to_datetime(_payload(ma, "planned_date")).to_numpy(),
            "actual_date": pd.to_datetime(_payload(ma, "actual_date")).to_numpy(),
            "interval_days": _payload(ma, "baseline_interval_days").astype(float).to_numpy(),
            "milestone_index": _payload(ma, "milestone_index").astype(float).to_numpy(),
        }
    )
    cutoff = as_of_ts - pd.Timedelta(days=censor_window_days)
    censored = int((m["planned_date"] > cutoff).sum())
    m = m[m["planned_date"] <= cutoff].copy()
    m["slip_days"] = (m["actual_date"] - m["planned_date"]).dt.days.astype(float)
    m["schedule_variance_pct"] = 100.0 * m["slip_days"] / m["interval_days"].clip(lower=1)
    m["on_time"] = (m["schedule_variance_pct"] <= ON_TIME_THRESHOLD_PCT).astype(int)

    # Time-varying condition: approved scope changes *before* the milestone's planned date.
    sc = ev[ev["category"] == "scope_change_approved"][["project_id", "occurred_at"]]
    m = m.merge(ctx, on="project_id", how="left")
    if len(sc):
        joined = m[["milestone_id", "project_id", "planned_date"]].merge(sc, on="project_id", how="left")
        joined["before"] = joined["occurred_at"] <= joined["planned_date"]
        counts = joined.groupby("milestone_id")["before"].sum()
        m["scope_changes_to_date"] = m["milestone_id"].map(counts).fillna(0).astype(float)
    else:
        m["scope_changes_to_date"] = 0.0

    # Deliverable quality (optional — reviews do not always record a score).
    dr = ev[ev["category"] == "document_reviewed"]
    q = pd.DataFrame(
        {
            "milestone_id": _payload(dr, "milestone_id").to_numpy(),
            "quality_score": dr["quality_indicators"]
            .map(lambda d: d.get("review_score") if isinstance(d, dict) else None)
            .astype(float)
            .to_numpy(),
            "approved_first_pass": _payload(dr, "approved_first_pass").astype(float).to_numpy(),
        }
    ).drop_duplicates("milestone_id", keep="last")
    m = m.merge(q, on="milestone_id", how="left")
    m = m.merge(emp[["employee_id", "job_family", "business_unit", "level"]], on="employee_id", how="left")

    start = m["planned_date"].min()
    m["month_index"] = (m["planned_date"] - start).dt.days / 30.44
    m["period"] = (m["month_index"] // 6).clip(upper=3).astype(int)
    m["quarter"] = m["planned_date"].dt.to_period("Q").astype(str)
    for c in ("technical_complexity", "dependency_count", "resource_constraint", "size_band", "team_size"):
        m[c] = m[c].astype(float)
    m = m.sort_values(["employee_id", "planned_date"]).reset_index(drop=True)
    assert_no_forbidden_columns(m, "milestone features")
    return FeatureSet(milestones=m, events=ev, activity=activity, employees=emp, as_of=as_of_ts, censored_excluded=censored)


def design_matrix(
    m: pd.DataFrame, numeric: list[str] | None = None, categorical: list[str] | None = None, include_time: bool = True
) -> pd.DataFrame:
    """Context design matrix (no employee identity). Used by models and validation."""
    numeric = CONTEXT_NUMERIC if numeric is None else numeric
    categorical = CONTEXT_CATEGORICAL if categorical is None else categorical
    X = m[numeric].astype(float).copy()
    if include_time:
        X["month_index"] = m["month_index"].astype(float)
    for c in categorical:
        d = pd.get_dummies(m[c].astype(str), prefix=c, drop_first=True, dtype=float)
        X = pd.concat([X, d], axis=1)
    assert_no_forbidden_columns(X, "design matrix")
    return X


def employee_activity_summary(activity: pd.DataFrame) -> pd.DataFrame:
    if not len(activity):
        return pd.DataFrame(columns=["employee_id", "meetings_per_month", "emails_per_month", "hours_per_month"])
    return (
        activity.groupby("employee_id")
        .agg(
            meetings_per_month=("meetings_attended", "mean"),
            emails_per_month=("emails_sent", "mean"),
            hours_per_month=("working_hours", "mean"),
        )
        .reset_index()
    )


def evidence_counts(ev: pd.DataFrame) -> pd.DataFrame:
    return ev.groupby(["employee_id", "category"]).size().unstack(fill_value=0)


def safe_rate(num: pd.Series, den: pd.Series) -> pd.Series:
    return (num / den.replace(0, np.nan)).astype(float)
