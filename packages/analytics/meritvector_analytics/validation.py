"""Layer E — scientific validation.

Everything here evaluates the models; nothing here feeds individual estimates.
Historical manager ratings and promotions are treated as potentially biased labels
and are used only to *audit* their relationship with evidence, never as targets.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold

from meritvector_analytics.contextual import (
    MIN_MILESTONES,
    OUTCOMES,
    add_person_means,
    classify,
    context_formula,
    fit_context_ols,
    fit_mixed,
    mixed_estimates,
    residual_estimates,
    within_beta,
    within_person_formula,
)
from meritvector_analytics.features import CONTEXT_NUMERIC, LeakageError, design_matrix
from meritvector_shared import FORBIDDEN_MODEL_COLUMNS

OUTCOME = "schedule_variance_pct"
MIN_FAIRNESS_CELL = 20


def _metrics(y, p) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y, p)),
        "rmse": float(np.sqrt(mean_squared_error(y, p))),
        "r2": float(r2_score(y, p)),
    }


def out_of_time_split(m: pd.DataFrame, holdout_months: int = 6) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    cutoff = m["planned_date"].max() - pd.DateOffset(months=holdout_months)
    return m[m["planned_date"] <= cutoff].copy(), m[m["planned_date"] > cutoff].copy(), str(cutoff.date())


def _align(Xtr: pd.DataFrame, Xte: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cols = sorted(set(Xtr.columns) | set(Xte.columns))
    return Xtr.reindex(columns=cols, fill_value=0.0), Xte.reindex(columns=cols, fill_value=0.0)


def baseline_comparison(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, Any]:
    """Out-of-time predictive comparison on future milestones."""
    ytr, yte = train[OUTCOME].to_numpy(), test[OUTCOME].to_numpy()
    Xtr, Xte = _align(design_matrix(train), design_matrix(test))
    results: dict[str, Any] = {}
    results["global_mean"] = _metrics(yte, np.full_like(yte, ytr.mean(), dtype=float))

    ols = LinearRegression().fit(Xtr, ytr)
    results["context_ols"] = _metrics(yte, ols.predict(Xte))

    gbm = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, random_state=0).fit(Xtr, ytr)
    results["context_gbm"] = _metrics(yte, gbm.predict(Xte))

    # Employee history only (ignores context): mean of past outcomes, shrunk to grand mean.
    g = train.groupby("employee_id")[OUTCOME].agg(["mean", "size"])
    k = 5.0
    shrunk = (g["mean"] * g["size"] + ytr.mean() * k) / (g["size"] + k)
    results["employee_history_only"] = _metrics(yte, test["employee_id"].map(shrunk).fillna(ytr.mean()).to_numpy())

    # Context + employee random intercept (the model used for adjusted estimates).
    mres, _, _, _ = fit_mixed(train, OUTCOME, project_vc=False)
    fe = mres.predict(test)
    re = pd.Series({k_: float(v.iloc[0]) for k_, v in mres.random_effects.items()})
    pred = fe.to_numpy() + test["employee_id"].map(re).fillna(0.0).to_numpy()
    results["context_plus_employee_mixed"] = _metrics(yte, pred)

    best = min(results, key=lambda name: results[name]["mae"])
    return {
        "models": results,
        "best_by_mae": best,
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "test_employees_unseen": int((~test["employee_id"].isin(train["employee_id"])).sum()),
    }


def grouped_cross_validation(train: pd.DataFrame, folds: int = 5) -> dict[str, Any]:
    """Cross-validation grouped by project, so a project's milestones never straddle folds."""
    X, y = design_matrix(train), train[OUTCOME].to_numpy()
    groups = train["project_id"].to_numpy()
    out: dict[str, list[float]] = {"context_ridge": [], "context_gbm": []}
    for tr, te in GroupKFold(n_splits=folds).split(X, y, groups):
        r = Ridge(alpha=1.0).fit(X.iloc[tr], y[tr])
        out["context_ridge"].append(mean_absolute_error(y[te], r.predict(X.iloc[te])))
        gbm = HistGradientBoostingRegressor(max_iter=150, learning_rate=0.05, random_state=0).fit(X.iloc[tr], y[tr])
        out["context_gbm"].append(mean_absolute_error(y[te], gbm.predict(X.iloc[te])))
    return {name: {"mae_mean": float(np.mean(v)), "mae_sd": float(np.std(v)), "folds": folds} for name, v in out.items()}


def leakage_checks(m: pd.DataFrame, train: pd.DataFrame, test: pd.DataFrame) -> list[dict[str, Any]]:
    checks = []
    X = design_matrix(m)
    forbidden = sorted(set(X.columns) & set(FORBIDDEN_MODEL_COLUMNS))
    checks.append(
        {
            "check": "No hidden ground truth, protected attributes, ratings or activity in features",
            "passed": not forbidden,
            "detail": forbidden or "none present",
        }
    )
    banned_outcome_derived = {"actual_date", "slip_days", "on_time", "quality_score", "approved_first_pass", OUTCOME}
    present = sorted(set(X.columns) & banned_outcome_derived)
    checks.append({"check": "No outcome-derived fields in the design matrix", "passed": not present, "detail": present or "none present"})
    checks.append(
        {
            "check": "Out-of-time split is strictly chronological",
            "passed": bool(train["planned_date"].max() < test["planned_date"].min()),
            "detail": f"train ≤ {train['planned_date'].max().date()} < test ≥ {test['planned_date'].min().date()}",
        }
    )
    corr = X.apply(lambda c: abs(np.corrcoef(c, m[OUTCOME])[0, 1]) if c.std() > 0 else 0.0)
    checks.append(
        {
            "check": "No single feature near-perfectly predicts the outcome (|r| < 0.9)",
            "passed": bool((corr < 0.9).all()),
            "detail": f"max |r| = {corr.max():.2f} ({corr.idxmax()})",
        }
    )
    # Permutation sanity: models trained on shuffled targets must have no out-of-time skill on average.
    rng = np.random.default_rng(0)
    Xtr, Xte = _align(design_matrix(train), design_matrix(test))
    r2s = [r2_score(test[OUTCOME], LinearRegression().fit(Xtr, rng.permutation(train[OUTCOME].to_numpy())).predict(Xte)) for _ in range(20)]
    r2 = float(np.mean(r2s))
    checks.append(
        {
            "check": "Permuted-target models have no out-of-time skill (mean R² over 20 shuffles ≤ 0.02)",
            "passed": bool(r2 <= 0.02),
            "detail": f"mean R² = {r2:.3f} (max {max(r2s):.3f})",
        }
    )
    return checks


def cluster_bootstrap_effects(m: pd.DataFrame, n_boot: int = 200, seed: int = 0) -> pd.DataFrame:
    """Percentile CIs for employee estimates, resampling *projects*.

    Context coefficients are re-estimated within person in every resample (fixed-effects estimator), so the check is
    independent of the mixed model's distributional assumptions but shares its identification strategy.
    """
    rng = np.random.default_rng(seed)
    d = m.dropna(subset=[OUTCOME]).reset_index(drop=True)
    X = design_matrix(d).to_numpy()
    y = d[OUTCOME].to_numpy()
    proj_codes, proj_index = pd.factorize(d["project_id"])
    emp_codes, emp_index = pd.factorize(d["employee_id"])
    rows_by_proj = [np.nonzero(proj_codes == i)[0] for i in range(len(proj_index))]
    sign = OUTCOMES[OUTCOME]["sign"]
    draws = np.full((n_boot, len(emp_index)), np.nan)
    for b in range(n_boot):
        pick = rng.integers(0, len(rows_by_proj), len(rows_by_proj))
        idx = np.concatenate([rows_by_proj[i] for i in pick])
        beta = within_beta(X[idx], y[idx], emp_codes[idx])
        resid = y[idx] - X[idx] @ beta
        sums = np.bincount(emp_codes[idx], weights=resid, minlength=len(emp_index))
        cnt = np.bincount(emp_codes[idx], minlength=len(emp_index))
        with np.errstate(invalid="ignore", divide="ignore"):
            person = sums / np.where(cnt > 0, cnt, np.nan)
            draws[b] = sign * (person - np.nanmean(person))
    lo = np.nanpercentile(draws, 2.5, axis=0)
    hi = np.nanpercentile(draws, 97.5, axis=0)
    return pd.DataFrame(
        {"employee_id": emp_index, "boot_ci_low": lo, "boot_ci_high": hi, "boot_valid_draws": np.isfinite(draws).sum(axis=0)}
    )


def calibration(train: pd.DataFrame, test: pd.DataFrame, threshold: float = 10.0, bins: int = 10) -> dict[str, Any]:
    """Calibration of P(milestone slips > threshold%) from context, evaluated out of time."""
    Xtr, Xte = _align(design_matrix(train), design_matrix(test))
    ytr = (train[OUTCOME] > threshold).astype(int).to_numpy()
    yte = (test[OUTCOME] > threshold).astype(int).to_numpy()
    clf = LogisticRegression(max_iter=2000).fit(Xtr, ytr)
    p = clf.predict_proba(Xte)[:, 1]
    edges = np.linspace(0, 1, bins + 1)
    which = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    table = []
    ece = 0.0
    for b in range(bins):
        sel = which == b
        if sel.sum() == 0:
            continue
        mp, fo = float(p[sel].mean()), float(yte[sel].mean())
        ece += sel.mean() * abs(mp - fo)
        table.append({"bin": b, "mean_predicted": mp, "observed_rate": fo, "n": int(sel.sum())})
    return {
        "event": f"milestone slips more than {threshold:.0f}% of its interval",
        "brier": float(brier_score_loss(yte, p)),
        "brier_climatology": float(brier_score_loss(yte, np.full_like(p, ytr.mean()))),
        "expected_calibration_error": float(ece),
        "reliability": table,
    }


def sensitivity(m: pd.DataFrame, base: pd.DataFrame) -> dict[str, Any]:
    """Re-estimate employee effects under alternative specifications (all within-person unless stated)."""
    no_rc = [c for c in CONTEXT_NUMERIC if c != "resource_constraint"]
    no_cx = [c for c in CONTEXT_NUMERIC if c not in ("technical_complexity", "dependency_count")]
    specs: dict[str, dict[str, Any]] = {
        "no_project_variance_component": {"project_vc": False},
        "add_business_unit_fixed_effects": {"extra": "C(business_unit)"},
        "drop_resource_constraint": {"numeric": no_rc},
        "drop_complexity_and_dependencies": {"numeric": no_cx},
        "winsorised_outcome_5_95": {"winsor": True},
        "random_intercept_only_v0_1": {"within": False},
        "no_context_adjustment": {"formula": f"{OUTCOME} ~ 1", "within": False},
    }
    base = base.set_index("employee_id")
    results, per_spec = {}, {}
    for name, spec in specs.items():
        d = m.copy()
        if spec.get("winsor"):
            lo, hi = d[OUTCOME].quantile([0.05, 0.95])
            d[OUTCOME] = d[OUTCOME].clip(lo, hi)
        numeric = spec.get("numeric", CONTEXT_NUMERIC)
        between = None
        if spec.get("within", True):
            d, between = add_person_means(d, numeric)
            formula = within_person_formula(OUTCOME, numeric=numeric, extra=spec.get("extra", ""))
        else:
            formula = spec.get("formula") or context_formula(OUTCOME, numeric=numeric, extra=spec.get("extra", ""))
        res, md, _, _ = fit_mixed(d, OUTCOME, formula=formula, project_vc=spec.get("project_vc", True))
        est = mixed_estimates(res, md, OUTCOME, between=between)
        est["conclusion"] = classify(est, OUTCOME)
        est = est.set_index("employee_id")
        joined = base.join(est, rsuffix="_alt", how="inner")
        rho = stats.spearmanr(joined["adjusted_estimate"], joined["adjusted_estimate_alt"]).statistic
        changed = float((joined["conclusion"] != joined["conclusion_alt"]).mean())
        results[name] = {"spearman_with_base": float(rho), "share_conclusions_changed": changed}
        per_spec[name] = est[["adjusted_estimate", "ci_low", "ci_high", "conclusion"]]
    # Robust regression (Huber) on residual estimates.
    import statsmodels.formula.api as smf

    d = m.dropna(subset=[OUTCOME])
    rlm = smf.rlm(context_formula(OUTCOME), data=d).fit()
    huber = (-(d.assign(r=rlm.resid).groupby("employee_id")["r"].mean())).rename("huber")
    joined = base.join(huber, how="inner")
    results["huber_robust_residuals"] = {
        "spearman_with_base": float(stats.spearmanr(joined["adjusted_estimate"], joined["huber"]).statistic),
        "share_conclusions_changed": None,
    }
    return {"specifications": results, "per_spec": per_spec}


def missing_data_diagnostics(m: pd.DataFrame, events: pd.DataFrame, employees: pd.DataFrame) -> dict[str, Any]:
    q_missing = m["quality_score"].isna()
    by_env = m.assign(qm=q_missing).groupby("environment")["qm"].mean().to_dict()
    tab = pd.crosstab(m["environment"], q_missing)
    chi2_p = float(stats.chi2_contingency(tab)[1]) if tab.shape[1] == 2 else float("nan")
    counts = m.groupby("employee_id").size().reindex(employees["employee_id"]).fillna(0)
    feedback = events[events["category"] == "stakeholder_feedback"].groupby("project_id").size()
    projects = m["project_id"].unique()
    return {
        "milestone_feature_missing_rate": {c: float(m[c].isna().mean()) for c in CONTEXT_NUMERIC + ["quality_score"]},
        "quality_missing_by_environment": {k: float(v) for k, v in by_env.items()},
        "quality_missingness_depends_on_environment_p": chi2_p,
        "interpretation": "Quality scores are not missing completely at random (missingness depends on delivery "
        "environment). Quality models condition on environment; complete-case estimates may still be biased."
        if chi2_p < 0.05
        else "No evidence that quality missingness depends on delivery environment.",
        "employees_below_min_evidence": int((counts < MIN_MILESTONES).sum()),
        "employees_with_no_milestones": int((counts == 0).sum()),
        "projects_without_stakeholder_feedback": int(len(set(projects) - set(feedback.index))),
    }


def _psi(a: np.ndarray, b: np.ndarray, bins: int = 10) -> float:
    edges = np.unique(np.quantile(a, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    pa = np.histogram(np.clip(a, edges[0], edges[-1]), edges)[0] / len(a)
    pb = np.histogram(np.clip(b, edges[0], edges[-1]), edges)[0] / len(b)
    pa, pb = np.clip(pa, 1e-4, None), np.clip(pb, 1e-4, None)
    return float(np.sum((pb - pa) * np.log(pb / pa)))


def drift(train: pd.DataFrame, test: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for c in CONTEXT_NUMERIC + [OUTCOME]:
        a, b = train[c].dropna().to_numpy(float), test[c].dropna().to_numpy(float)
        ks = stats.ks_2samp(a, b)
        psi = _psi(a, b)
        rows.append(
            {
                "feature": c,
                "train_mean": float(a.mean()),
                "test_mean": float(b.mean()),
                "ks_stat": float(ks.statistic),
                "ks_p": float(ks.pvalue),
                "psi": psi,
                "status": "major_shift" if psi > 0.25 else ("moderate_shift" if psi > 0.1 else "stable"),
            }
        )
    return rows


def prediction_error_analysis(train: pd.DataFrame, test: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    Xtr, Xte = _align(design_matrix(train), design_matrix(test))
    model = LinearRegression().fit(Xtr, train[OUTCOME])
    t = test.assign(abs_err=np.abs(test[OUTCOME] - model.predict(Xte)), err=test[OUTCOME] - model.predict(Xte))
    t["resource_band"] = pd.cut(t["resource_constraint"], [-0.01, 0.3, 0.6, 1.0], labels=["low", "medium", "high"]).astype(str)
    out = {}
    for col in ("technical_complexity", "environment", "business_unit", "resource_band", "job_family"):
        g = t.groupby(col)
        out[col] = [
            {"group": str(k), "mae": float(v["abs_err"].mean()), "mean_error": float(v["err"].mean()), "n": int(len(v))} for k, v in g
        ]
    return out


def label_audit(estimates: pd.DataFrame, ratings: pd.DataFrame, raw: pd.DataFrame, activity: pd.DataFrame) -> dict[str, Any]:
    """How do historical manager ratings relate to raw outcomes, adjusted evidence and activity?"""
    r = ratings.groupby("employee_id")["manager_rating"].mean().rename("rating")
    d = (
        estimates.set_index("employee_id")[["adjusted_estimate"]]
        .join(r, how="inner")
        .join(raw.set_index("employee_id")[["raw_estimate"]], how="left")
        .join(activity.set_index("employee_id")[["meetings_per_month"]], how="left")
    ).dropna()

    def rho(a, b):
        return float(stats.spearmanr(d[a], d[b]).statistic)

    return {
        "n_employees": int(len(d)),
        "rating_vs_raw_outcome_spearman": rho("rating", "raw_estimate"),
        "rating_vs_adjusted_estimate_spearman": rho("rating", "adjusted_estimate"),
        "rating_vs_meeting_volume_spearman": rho("rating", "meetings_per_month"),
        "adjusted_estimate_vs_meeting_volume_spearman": rho("adjusted_estimate", "meetings_per_month"),
        "interpretation": "Manager ratings are treated as potentially biased labels. A stronger association with "
        "raw outcomes or activity volume than with context-adjusted evidence suggests ratings "
        "reward favourable circumstances or visible activity.",
    }


def fairness_audit(
    protected: pd.DataFrame,
    estimates: pd.DataFrame,
    raw: pd.DataFrame,
    ratings: pd.DataFrame,
    promotions: pd.DataFrame,
    min_cell: int = MIN_FAIRNESS_CELL,
    n_boot: int = 500,
    seed: int = 0,
) -> dict[str, Any]:
    """Aggregated fairness audit. Returns group-level statistics only; cells < min_cell are suppressed.

    The protected attribute is joined here, inside the audit, and never leaves it at
    individual level.
    """
    rng = np.random.default_rng(seed)
    r = ratings.groupby("employee_id")["manager_rating"].mean().rename("rating")
    p = promotions.groupby("employee_id")["promoted"].max().astype(float).rename("promoted")
    d = (
        protected.set_index("employee_id")[["protected_group"]]
        .join(estimates.set_index("employee_id")[["adjusted_estimate"]], how="inner")
        .join(raw.set_index("employee_id")[["raw_estimate"]], how="left")
        .join(r)
        .join(p)
    )
    groups = []
    for gname, g in d.groupby("protected_group"):
        if len(g) < min_cell:
            groups.append({"group": gname, "n": f"suppressed (<{min_cell})"})
            continue
        groups.append(
            {
                "group": gname,
                "n": int(len(g)),
                "mean_rating": float(g["rating"].mean()),
                "promotion_rate": float(g["promoted"].mean()),
                "mean_adjusted_estimate": float(g["adjusted_estimate"].mean()),
                "mean_raw_estimate": float(g["raw_estimate"].mean()),
            }
        )
    gaps = {}
    names = sorted(d["protected_group"].unique())
    if len(names) == 2 and all(isinstance(x.get("n"), int) for x in groups):
        a, b = names
        for col in ("rating", "adjusted_estimate", "promoted"):
            da, db = (
                d.loc[d["protected_group"] == a, col].dropna().to_numpy(),
                d.loc[d["protected_group"] == b, col].dropna().to_numpy(),
            )
            boots = [rng.choice(da, len(da)).mean() - rng.choice(db, len(db)).mean() for _ in range(n_boot)]
            gaps[col] = {
                "difference": float(da.mean() - db.mean()),
                "ci_low": float(np.percentile(boots, 2.5)),
                "ci_high": float(np.percentile(boots, 97.5)),
                "comparison": f"{a} minus {b}",
            }
    finding = None
    if gaps:
        rating_gap = gaps["rating"]
        evid_gap = gaps["adjusted_estimate"]
        rating_sig = rating_gap["ci_low"] > 0 or rating_gap["ci_high"] < 0
        evid_sig = evid_gap["ci_low"] > 0 or evid_gap["ci_high"] < 0
        opposite = np.sign(rating_gap["difference"]) != np.sign(evid_gap["difference"])
        if rating_sig and (not evid_sig or opposite):
            finding = (
                "Historical manager ratings favour one group although context-adjusted delivery evidence does "
                "not (or points the other way). This pattern is consistent with rating bias and warrants HR "
                "review of the rating process. It is not evidence about any individual."
            )
        elif rating_sig and evid_sig:
            finding = (
                "Ratings and adjusted evidence differ between groups in the same direction; investigate "
                "assignment patterns and unmeasured context before drawing conclusions."
            )
        elif evid_sig:
            finding = (
                "Adjusted evidence differs between groups while ratings do not; check for differences in "
                "project assignment or measurement before interpreting."
            )
        else:
            finding = "No statistically clear group difference in ratings or adjusted evidence at this sample size."
    return {
        "attribute": "protected_group (synthetic)",
        "min_cell_size": min_cell,
        "groups": groups,
        "gaps": gaps,
        "finding": finding,
        "governance": "Aggregated only. Protected attributes are excluded from all individual estimates.",
    }


def assert_training_frame_clean(df: pd.DataFrame) -> None:
    bad = sorted(set(df.columns) & set(FORBIDDEN_MODEL_COLUMNS))
    if bad:
        raise LeakageError(f"forbidden columns in training frame: {bad}")


def run_validation(
    m: pd.DataFrame, events: pd.DataFrame, employees: pd.DataFrame, base_estimates: pd.DataFrame, n_boot: int = 200
) -> dict[str, Any]:
    assert_training_frame_clean(m)
    train, test, cutoff = out_of_time_split(m)
    boot = cluster_bootstrap_effects(m, n_boot=n_boot)
    ols, d = fit_context_ols(m, OUTCOME)
    resid = residual_estimates(m, OUTCOME, ols, d)
    cmp = boot.merge(resid, on="employee_id").merge(base_estimates[["employee_id", "ci_low", "ci_high", "n"]], on="employee_id")
    cmp = cmp[cmp["n"] >= MIN_MILESTONES]
    agree = float((((cmp["boot_ci_low"] > 0) == (cmp["ci_low"] > 0)) & ((cmp["boot_ci_high"] < 0) == (cmp["ci_high"] < 0))).mean())
    sens = sensitivity(m, base_estimates)
    return {
        "out_of_time": {"cutoff": cutoff, **baseline_comparison(train, test)},
        "cross_validation": grouped_cross_validation(train),
        "leakage_checks": leakage_checks(m, train, test),
        "bootstrap": {
            "n_boot": n_boot,
            "method": "cluster bootstrap over projects, residual estimator",
            "direction_agreement_with_mixed_intervals": agree,
            "median_boot_ci_width": float((boot["boot_ci_high"] - boot["boot_ci_low"]).median()),
        },
        "calibration": calibration(train, test),
        "sensitivity": sens["specifications"],
        "missing_data": missing_data_diagnostics(m, events, employees),
        "drift": drift(train, test),
        "prediction_error": prediction_error_analysis(train, test),
        "_bootstrap_table": boot,
        "_sensitivity_tables": sens["per_spec"],
    }
