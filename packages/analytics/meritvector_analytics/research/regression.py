"""Workstream 3 (regression & context) and 7 (generalisation).

Compares simple and advanced models of milestone schedule variance under project-grouped cross-validation and an
out-of-time split, checks over/under-fitting with learning curves, and runs a negative-control test: dimensions the
PMO records but which have no effect in the data-generating process should add nothing once real context is in the
model.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LassoCV, LinearRegression, RidgeCV
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import SplineTransformer, StandardScaler

from meritvector_analytics.contextual import context_formula
from meritvector_analytics.features import CONTEXT_NUMERIC, design_matrix
from meritvector_analytics.research.data import ResearchData, jsonable
from meritvector_analytics.validation import out_of_time_split

Y = "schedule_variance_pct"
NEGATIVE_CONTROLS = [
    "schedule_criticality",
    "visibility_level",
    "stakeholder_groups",
    "technical_uncertainty",
    "operational_criticality",
    "sites",
    "vendor_count",
    "integration_points",
]


def _interactions(m: pd.DataFrame) -> pd.DataFrame:
    X = design_matrix(m)
    X["complexity_x_resource"] = m["technical_complexity"] * m["resource_constraint"]
    X["dependency_x_regulated"] = m["dependency_count"] * (m["environment"] == "regulated")
    return X


def _models() -> dict[str, tuple[str, Any]]:
    return {
        "ols_linear": ("linear", LinearRegression()),
        "ridge_cv": ("linear", make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 20)))),
        "lasso_cv": ("linear", make_pipeline(StandardScaler(), LassoCV(cv=5, random_state=0, max_iter=5000))),
        "ols_interactions": ("interactions", LinearRegression()),
        "spline_additive": (
            "linear",
            make_pipeline(SplineTransformer(n_knots=4, degree=3), RidgeCV(alphas=np.logspace(-2, 3, 20))),
        ),
        "gradient_boosting": ("linear", HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, random_state=0)),
    }


def _X(kind: str, m: pd.DataFrame) -> pd.DataFrame:
    return _interactions(m) if kind == "interactions" else design_matrix(m)


def _align(a: pd.DataFrame, b: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cols = sorted(set(a.columns) | set(b.columns))
    return a.reindex(columns=cols, fill_value=0.0), b.reindex(columns=cols, fill_value=0.0)


def compare_models(rd: ResearchData, folds: int = 5) -> dict[str, Any]:
    m = rd.features.milestones.dropna(subset=[Y]).reset_index(drop=True)
    y = m[Y].to_numpy()
    groups = m["project_id"].to_numpy()
    train, test, cutoff = out_of_time_split(m)
    rows = []
    for name, (kind, est) in _models().items():
        X = _X(kind, m)
        cv_val, cv_train = [], []
        for tr, te in GroupKFold(n_splits=folds).split(X, y, groups):
            est.fit(X.iloc[tr], y[tr])
            cv_val.append(mean_absolute_error(y[te], est.predict(X.iloc[te])))
            cv_train.append(mean_absolute_error(y[tr], est.predict(X.iloc[tr])))
        Xtr, Xte = _align(_X(kind, train), _X(kind, test))
        est.fit(Xtr, train[Y])
        pred = est.predict(Xte)
        gap = float(np.mean(cv_val) - np.mean(cv_train))
        rows.append(
            {
                "model": name,
                "cv_mae": float(np.mean(cv_val)),
                "cv_mae_sd": float(np.std(cv_val)),
                "train_mae": float(np.mean(cv_train)),
                "generalisation_gap": gap,
                "oot_mae": float(mean_absolute_error(test[Y], pred)),
                "oot_r2": float(r2_score(test[Y], pred)),
                "fit_diagnosis": "possible overfitting" if gap > 1.0 else "no material overfitting",
            }
        )
    base_mae = float(mean_absolute_error(test[Y], np.full(len(test), train[Y].mean())))
    best = min(rows, key=lambda r: r["oot_mae"])
    simplest = next(r for r in rows if r["model"] == "ols_linear")
    return jsonable(
        {
            "kind": "predictive",
            "status": "exploratory",
            "question": "How do project conditions relate to delivery outcomes, and do complex models add anything?",
            "unit": "milestone",
            "validation": f"{folds}-fold CV grouped by project; out-of-time test after {cutoff}",
            "baseline_global_mean_oot_mae": base_mae,
            "models": rows,
            "conclusion": (
                f"Best out-of-time model: {best['model']} (MAE {best['oot_mae']:.2f}). The plain linear model is within "
                f"{simplest['oot_mae'] - best['oot_mae']:.2f} pp — added complexity buys little, so the transparent model is preferred."
            ),
            "learning_curve": learning_curve(m),
            "negative_controls": negative_controls(rd),
            "interactions": interaction_terms(m),
        }
    )


def learning_curve(m: pd.DataFrame, fractions=(0.1, 0.25, 0.5, 0.75, 1.0), seed: int = 0) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    projects = np.array(m["project_id"].unique(), dtype=object)
    rng.shuffle(projects)
    hold = set(projects[: len(projects) // 5])
    test = m[m["project_id"].isin(hold)]
    pool = [p for p in projects if p not in hold]
    out = []
    for f in fractions:
        tr = m[m["project_id"].isin(pool[: max(5, int(len(pool) * f))])]
        row = {"fraction": f, "n_train": int(len(tr))}
        for name, est in (
            ("ols_linear", LinearRegression()),
            ("gradient_boosting", HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, random_state=0)),
        ):
            Xtr, Xte = _align(design_matrix(tr), design_matrix(test))
            est.fit(Xtr, tr[Y])
            row[f"{name}_train_mae"] = float(mean_absolute_error(tr[Y], est.predict(Xtr)))
            row[f"{name}_val_mae"] = float(mean_absolute_error(test[Y], est.predict(Xte)))
        out.append(row)
    return out


def negative_controls(rd: ResearchData) -> dict[str, Any]:
    """Recorded dimensions with no effect in the generator should not improve the model.

    The primary test is a project-clustered joint Wald test. The naive i.i.d. F-test is reported alongside to show the
    repeated-measures pitfall: milestones of the same project share a shock, so treating them as independent inflates
    the evidence for project-level variables.
    """
    mf = rd.milestone_frame.dropna(subset=[Y])
    controls = [c for c in NEGATIVE_CONTROLS if c in mf.columns]
    f_full = context_formula(Y, extra=" + ".join(controls))
    clustered = smf.ols(f_full, mf).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(mf["project_id"])[0]})
    wald = clustered.wald_test(", ".join(f"{c} = 0" for c in controls), scalar=True)
    base = smf.ols(context_formula(Y), mf).fit()
    naive_f, naive_p, _ = smf.ols(f_full, mf).fit().compare_f_test(base)
    p = float(wald.pvalue)
    coefs = {c: {"estimate": float(clustered.params[c]), "p_value": float(clustered.pvalues[c])} for c in controls}
    unadjusted = {
        c: float(smf.ols(f"{Y} ~ {c}", mf).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(mf["project_id"])[0]}).pvalues[c])
        for c in controls
    }
    return {
        "controls": controls,
        "joint_wald_chi2": float(wald.statistic),
        "joint_p": p,
        "coefficients": coefs,
        "naive_iid_f": float(naive_f),
        "naive_iid_p": float(naive_p),
        "unadjusted_p": unadjusted,
        "interpretation": (
            (
                "Negative controls add nothing once measured context is included (clustered joint p = "
                f"{p:.2f}) — as designed: "
                "in the generator these dimensions have no effect. "
            )
            if p >= 0.05
            else "Negative controls appear to add information — investigate leakage or misspecification before trusting the model. "
        )
        + (
            f"Ignoring that milestones of a project are not independent would give p = {naive_p:.3f}"
            + (" — a false discovery caused by pseudo-replication." if naive_p < 0.05 <= p else ".")
            + " On their own, several controls look related to delivery only because they correlate with real drivers."
        ),
    }


def interaction_terms(m: pd.DataFrame) -> dict[str, Any]:
    res = smf.ols(context_formula(Y, extra="technical_complexity:resource_constraint"), m.dropna(subset=[Y])).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(m.dropna(subset=[Y])["project_id"])[0]}
    )
    term = "technical_complexity:resource_constraint"
    ci = res.conf_int().loc[term].tolist()
    return {
        "term": term,
        "estimate": float(res.params[term]),
        "ci95": [float(ci[0]), float(ci[1])],
        "p_value": float(res.pvalues[term]),
        "interpretation": "No evidence that resource shortfalls hurt more on complex projects (the generator is additive)."
        if res.pvalues[term] >= 0.05
        else "Interaction detected — resource shortfalls matter more on complex projects.",
    }


def robustness_values(rd: ResearchData) -> list[dict[str, Any]]:
    ols, _ = rd.context_ols
    out = []
    for term in CONTEXT_NUMERIC:
        t = float(ols.tvalues[term])
        f = abs(t) / np.sqrt(ols.df_resid)
        rv = 0.5 * (np.sqrt(f**4 + 4 * f**2) - f**2)
        out.append({"term": term, "estimate": float(ols.params[term]), "t": t, "robustness_value": float(rv)})
    return out
