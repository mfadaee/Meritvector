"""Workstream 4 — classification with a valid target: 30-day milestone risk (project level).

Target: a milestone due in the next 30 days slips by more than 10% of its planned interval.
Unit: one snapshot per milestone, taken 30 days before its planned date.
Features: only information recorded on or before the snapshot date (point-in-time; Kaufman et al. 2012).
This is an operational early warning for projects. It never scores people.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from meritvector_analytics.research.data import ResearchData, jsonable

HORIZON_DAYS = 30
SLIP_THRESHOLD_PCT = 10.0
CENSOR_DAYS = 90
STATIC = [
    "technical_complexity",
    "dependency_count",
    "resource_constraint",
    "size_band",
    "team_size",
    "schedule_criticality",
    "stakeholder_groups",
    "technical_uncertainty",
    "integration_points",
    "vendor_count",
]


def build_snapshots(rd: ResearchData) -> pd.DataFrame:
    as_of = pd.Timestamp(rd.as_of)
    ms = rd.milestones.copy()
    for c in ("planned_date", "actual_date"):
        ms[c] = pd.to_datetime(ms[c])
    pr = rd.projects.copy()
    for c in ("start_date", "planned_end"):
        pr[c] = pd.to_datetime(pr[c])
    pr = pr.set_index("project_id")
    n_ms = ms.groupby("project_id").size()
    interval = (pr["planned_end"] - pr["start_date"]).dt.days / n_ms.reindex(pr.index)
    ms["interval"] = ms["project_id"].map(interval)
    ms["t"] = ms["planned_date"] - pd.Timedelta(days=HORIZON_DAYS)
    ms["start"] = ms["project_id"].map(pr["start_date"])
    # Eligible: snapshot after kick-off, outcome observable (settled or definitely late), not right-censored.
    elig = ms[(ms["t"] > ms["start"] + pd.Timedelta(days=7)) & (ms["planned_date"] <= as_of - pd.Timedelta(days=CENSOR_DAYS))].copy()
    slip_pct = 100 * (elig["actual_date"] - elig["planned_date"]).dt.days / elig["interval"].clip(lower=1)
    late_unobserved = elig["actual_date"].isna()  # still not achieved long after its date => late
    elig["label"] = ((slip_pct > SLIP_THRESHOLD_PCT) | late_unobserved).astype(int)

    risks = rd.risks.copy()
    risks["identified_on"] = pd.to_datetime(risks["identified_on"])
    risks["mitigated_on"] = pd.to_datetime(risks["mitigated_on"])
    deps = rd.dependencies.copy()
    deps["raised_on"] = pd.to_datetime(deps["raised_on"])
    deps["resolved_on"] = pd.to_datetime(deps["resolved_on"])
    sc = rd.events[rd.events["category"] == "scope_change_approved"][["project_id", "occurred_at"]].copy()
    sc["occurred_at"] = pd.to_datetime(sc["occurred_at"])
    by_p_ms = {k: g for k, g in ms.groupby("project_id")}
    by_p_r = {k: g for k, g in risks.groupby("project_id")}
    by_p_d = {k: g for k, g in deps.groupby("project_id")}
    by_p_s = {k: g for k, g in sc.groupby("project_id")}
    rows = []
    for r in elig.itertuples():
        t = r.t
        prior = by_p_ms[r.project_id]
        prior = prior[(prior["actual_date"].notna()) & (prior["actual_date"] <= t)]
        slips = 100 * (prior["actual_date"] - prior["planned_date"]).dt.days / prior["interval"].clip(lower=1)
        overdue = by_p_ms[r.project_id]
        overdue = overdue[(overdue["planned_date"] < t) & ((overdue["actual_date"].isna()) | (overdue["actual_date"] > t))]
        rk = by_p_r.get(r.project_id, risks.iloc[0:0])
        open_r = rk[(rk["identified_on"] <= t) & ((rk["mitigated_on"].isna()) | (rk["mitigated_on"] > t))]
        dp = by_p_d.get(r.project_id, deps.iloc[0:0])
        open_d = dp[(dp["raised_on"] <= t) & ((dp["resolved_on"].isna()) | (dp["resolved_on"] > t))]
        s = by_p_s.get(r.project_id, sc.iloc[0:0])
        p = pr.loc[r.project_id]
        row = {
            "milestone_id": r.milestone_id,
            "project_id": r.project_id,
            "snapshot_date": t,
            "label": r.label,
            "prior_milestones_achieved": len(prior),
            "prior_mean_slip_pct": float(slips.mean()) if len(slips) else 0.0,
            "last_slip_pct": float(slips.iloc[-1]) if len(slips) else 0.0,
            "has_prior": int(len(slips) > 0),
            "overdue_at_snapshot": len(overdue),
            "open_risks": len(open_r),
            "open_high_risks": int((open_r["severity"] == "high").sum()),
            "open_dependencies": len(open_d),
            "scope_changes_so_far": int((s["occurred_at"] <= t).sum()),
            "days_into_project": int((t - p["start_date"]).days),
            "regulated": int(p["environment"] == "regulated"),
            "greenfield": int(p["maturity"] == "greenfield"),
            # Leakage audit trail: latest timestamp used by any time-varying feature.
            "_max_feature_time": max(
                [
                    x
                    for x in [
                        prior["actual_date"].max(),
                        open_r["identified_on"].max(),
                        open_d["raised_on"].max(),
                        s.loc[s["occurred_at"] <= t, "occurred_at"].max(),
                    ]
                    if pd.notna(x)
                ],
                default=p["start_date"],
            ),
        }
        for c in STATIC:
            row[c] = p[c]
        rows.append(row)
    return pd.DataFrame(rows).sort_values("snapshot_date").reset_index(drop=True)


FEATURES = [
    "prior_milestones_achieved",
    "prior_mean_slip_pct",
    "last_slip_pct",
    "has_prior",
    "overdue_at_snapshot",
    "open_risks",
    "open_high_risks",
    "open_dependencies",
    "scope_changes_so_far",
    "days_into_project",
    "regulated",
    "greenfield",
    *STATIC,
]


def _models() -> dict[str, Any]:
    return {
        "logistic_regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")),
        "decision_tree": DecisionTreeClassifier(max_depth=4, min_samples_leaf=30, class_weight="balanced", random_state=0),
        "random_forest": RandomForestClassifier(
            n_estimators=300, min_samples_leaf=10, class_weight="balanced_subsample", random_state=0, n_jobs=-1
        ),
        "gradient_boosting": HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, class_weight="balanced", random_state=0),
    }


def _choose_threshold(y: np.ndarray, p: np.ndarray, cost_fn: float, cost_fp: float) -> float:
    grid = np.linspace(0.05, 0.95, 91)
    costs = [cost_fn * ((p < t) & (y == 1)).sum() + cost_fp * ((p >= t) & (y == 0)).sum() for t in grid]
    return float(grid[int(np.argmin(costs))])


def _calibration(y: np.ndarray, p: np.ndarray, bins: int = 10) -> list[dict[str, float]]:
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    return [
        {"mean_predicted": float(p[idx == b].mean()), "observed": float(y[idx == b].mean()), "n": int((idx == b).sum())}
        for b in range(bins)
        if (idx == b).sum()
    ]


def train_and_evaluate(rd: ResearchData, cost_fn: float = 3.0, cost_fp: float = 1.0) -> dict[str, Any]:
    snaps = build_snapshots(rd)
    leak_ok = bool((snaps["_max_feature_time"] <= snaps["snapshot_date"]).all())
    n = len(snaps)
    cut_test = snaps["snapshot_date"].quantile(0.75)
    cut_val = snaps["snapshot_date"].quantile(0.6)
    train = snaps[snaps["snapshot_date"] <= cut_val]
    val = snaps[(snaps["snapshot_date"] > cut_val) & (snaps["snapshot_date"] <= cut_test)]
    test = snaps[snaps["snapshot_date"] > cut_test]
    Xtr, ytr = train[FEATURES].astype(float), train["label"].to_numpy()
    Xva, yva = val[FEATURES].astype(float), val["label"].to_numpy()
    Xte, yte = test[FEATURES].astype(float), test["label"].to_numpy()
    base_rate = float(ytr.mean())
    results = []
    fitted = {}
    for name, model in _models().items():
        model.fit(Xtr, ytr)
        thr = _choose_threshold(yva, model.predict_proba(Xva)[:, 1], cost_fn, cost_fp)
        # Refit on train+validation for the final test evaluation.
        model.fit(pd.concat([Xtr, Xva]), np.concatenate([ytr, yva]))
        p = model.predict_proba(Xte)[:, 1]
        yhat = (p >= thr).astype(int)
        tn, fp, fn, tp = confusion_matrix(yte, yhat, labels=[0, 1]).ravel()
        prec, rec, _ = precision_recall_curve(yte, p)
        results.append(
            {
                "model": name,
                "threshold": thr,
                "precision": float(precision_score(yte, yhat, zero_division=0)),
                "recall": float(recall_score(yte, yhat)),
                "f1": float(f1_score(yte, yhat)),
                "pr_auc": float(average_precision_score(yte, p)),
                "roc_auc": float(roc_auc_score(yte, p)),
                "brier": float(brier_score_loss(yte, p)),
                "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
                "expected_cost_per_100": float(100 * (cost_fn * fn + cost_fp * fp) / len(yte)),
                "calibration": _calibration(yte, p),
                "pr_curve": [
                    {"precision": float(a), "recall": float(b)}
                    for a, b in zip(prec[:: max(1, len(prec) // 40)], rec[:: max(1, len(rec) // 40)], strict=False)
                ],
            }
        )
        fitted[name] = model
    # Baselines.
    heuristic = (test["last_slip_pct"] > SLIP_THRESHOLD_PCT).astype(int).to_numpy()
    tn, fp, fn, tp = confusion_matrix(yte, heuristic, labels=[0, 1]).ravel()
    baselines = {
        "base_rate_pr_auc": float(yte.mean()),
        "brier_climatology": float(brier_score_loss(yte, np.full(len(yte), base_rate))),
        "heuristic_last_milestone_slipped": {
            "precision": float(tp / max(1, tp + fp)),
            "recall": float(tp / max(1, tp + fn)),
            "f1": float(f1_score(yte, heuristic)),
            "expected_cost_per_100": float(100 * (cost_fn * fn + cost_fp * fp) / len(yte)),
        },
    }
    best = max(results, key=lambda r: r["pr_auc"])
    imp = permutation_importance(fitted[best["model"]], Xte, yte, scoring="average_precision", n_repeats=10, random_state=0)
    importance = sorted(
        [
            {"feature": f, "importance": float(m), "sd": float(s)}
            for f, m, s in zip(FEATURES, imp.importances_mean, imp.importances_std, strict=True)
        ],
        key=lambda r: -r["importance"],
    )
    return jsonable(
        {
            "kind": "predictive",
            "status": "exploratory",
            "question": "Which milestones due in the next 30 days are at elevated risk of slipping more than 10%?",
            "target": (
                f"milestone slips > {SLIP_THRESHOLD_PCT:.0f}% of its interval (or is still unachieved) — "
                f"snapshot {HORIZON_DAYS} days before due"
            ),
            "unit": "project milestone snapshot",
            "n_snapshots": n,
            "positive_rate_train": base_rate,
            "split": {
                "train_until": str(cut_val.date()),
                "validation_until": str(cut_test.date()),
                "n_train": len(train),
                "n_validation": len(val),
                "n_test": len(test),
            },
            "class_imbalance": "class_weight='balanced'; thresholds chosen on a later validation window by expected cost",
            "costs": {"false_negative": cost_fn, "false_positive": cost_fp},
            "leakage_check": {"all_features_before_snapshot": leak_ok},
            "models": results,
            "baselines": baselines,
            "best_by_pr_auc": best["model"],
            "permutation_importance": importance[:12],
            "use_restriction": "Early warning for project teams. Never used to evaluate the project manager.",
            "_snapshots": snaps,
        }
    )
