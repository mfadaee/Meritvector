"""Layer B — contextual adjustment.

Two families of model are fitted on achieved milestones:

1. **Context baseline (OLS)** — outcome ~ operating conditions, with standard errors
   clustered by project. Describes how much outcomes depend on context. Its
   residuals give a simple "relative to context expectation" estimate.
2. **Mixed-effects model** — the same fixed effects plus a random intercept per
   employee and a variance component per project (projects nested in employees).
   Employee intercepts are shrunk towards zero in proportion to how little evidence
   exists, and come with conditional standard errors.

Interpretation guard-rails (also surfaced in the API and model card):
  * Estimates are *adjusted associations*, not causal effects of a person.
  * Unmeasured context (team quality, sponsor support, luck) remains in the estimate.
  * Where evidence is thin or intervals are wide, the system abstains.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from meritvector_analytics.features import CONTEXT_CATEGORICAL, CONTEXT_NUMERIC

OUTCOMES: dict[str, dict[str, Any]] = {
    # sign: +1 when larger raw values are better
    "schedule_variance_pct": {
        "label": "Schedule variance (% of milestone interval)",
        "sign": -1,
        "unit": "pp",
        "max_ci_width": 22.0,
    },
    "quality_score": {"label": "Deliverable review score (1–5)", "sign": 1, "unit": "points", "max_ci_width": 1.1},
}
MIN_MILESTONES = 6


def context_formula(outcome: str, numeric: list[str] | None = None, categorical: list[str] | None = None, extra: str = "") -> str:
    numeric = CONTEXT_NUMERIC if numeric is None else numeric
    categorical = CONTEXT_CATEGORICAL if categorical is None else categorical
    terms = list(numeric) + [f"C({c})" for c in categorical] + ["month_index"]
    f = f"{outcome} ~ " + " + ".join(terms)
    return f + (f" + {extra}" if extra else "")


@dataclass
class ContextResult:
    outcome: str
    ols: Any
    coefficients: pd.DataFrame
    raw: pd.DataFrame
    residual_estimates: pd.DataFrame
    mixed_estimates: pd.DataFrame
    variance_components: dict[str, float]
    diagnostics: dict[str, Any] = field(default_factory=dict)


PM_SUFFIX = "__pm"


def add_person_means(m: pd.DataFrame, numeric: list[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Add each person's mean of every numeric context variable (Mundlak / correlated random effects).

    Stronger people are often given harder work. A random-intercept model then confounds the effect of conditions with
    who was assigned to them, under-estimating how much conditions matter. Adding person means makes the context
    coefficients *within-person* (estimated from the same person's projects) while keeping shrunk person intercepts.
    """
    numeric = CONTEXT_NUMERIC if numeric is None else numeric
    m = m.copy()
    cols = []
    for c in numeric:
        m[c + PM_SUFFIX] = m.groupby("employee_id")[c].transform("mean")
        cols.append(c + PM_SUFFIX)
    return m, cols


def within_beta(X: np.ndarray, y: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Within-person (fixed-effects) context coefficients via group demeaning; constant-within-person columns drop out."""
    codes, _ = pd.factorize(groups)
    cnt = np.bincount(codes)
    mx = np.vstack([np.bincount(codes, weights=X[:, j]) for j in range(X.shape[1])]).T / cnt[:, None]
    my = np.bincount(codes, weights=y) / cnt
    beta, *_ = np.linalg.lstsq(X - mx[codes], y - my[codes], rcond=None)
    return beta


def within_person_formula(outcome: str, numeric: list[str] | None = None, categorical: list[str] | None = None, extra: str = "") -> str:
    numeric = CONTEXT_NUMERIC if numeric is None else numeric
    pm = " + ".join(c + PM_SUFFIX for c in numeric)
    return context_formula(outcome, numeric, categorical, extra=(pm + (f" + {extra}" if extra else "")) if pm else extra)


def fit_context_ols(m: pd.DataFrame, outcome: str, formula: str | None = None):
    d = m.dropna(subset=[outcome])
    res = smf.ols(formula or context_formula(outcome), data=d).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(d["project_id"])[0]}
    )
    return res, d


def coefficient_table(res) -> pd.DataFrame:
    ci = res.conf_int()
    return pd.DataFrame(
        {
            "term": res.params.index,
            "estimate": res.params.values,
            "ci_low": ci[0].values,
            "ci_high": ci[1].values,
            "p_value": res.pvalues.values,
        }
    )


def raw_estimates(m: pd.DataFrame, outcome: str) -> pd.DataFrame:
    sign = OUTCOMES[outcome]["sign"]
    d = m.dropna(subset=[outcome])
    g = d.groupby("employee_id")[outcome]
    grand = d[outcome].mean()
    est = sign * (g.mean() - grand)
    se = g.std() / np.sqrt(g.count())
    return pd.DataFrame({"raw_estimate": est, "raw_se": se, "n": g.count(), "raw_mean": g.mean()}).reset_index()


def residual_estimates(m: pd.DataFrame, outcome: str, ols_res, d: pd.DataFrame) -> pd.DataFrame:
    sign = OUTCOMES[outcome]["sign"]
    r = d.assign(_resid=ols_res.resid, _fitted=ols_res.fittedvalues)
    g = r.groupby("employee_id")
    out = pd.DataFrame(
        {
            "residual_estimate": sign * g["_resid"].mean(),
            "residual_se": g["_resid"].std() / np.sqrt(g.size()),
            # Context-expected outcome: the operating-difficulty index for this person's work.
            "context_expected": g["_fitted"].mean(),
        }
    ).reset_index()
    return out


def fit_mixed(m: pd.DataFrame, outcome: str, formula: str | None = None, project_vc: bool = True):
    """Fit the mixed model; fall back to employee-only random intercepts if needed."""
    d = m.dropna(subset=[outcome]).reset_index(drop=True)
    f = formula or context_formula(outcome)
    caught: list[str] = []
    for use_vc in [True, False] if project_vc else [False]:
        for method in ("lbfgs", "bfgs", "powell"):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                try:
                    model = smf.mixedlm(
                        f,
                        d,
                        groups=d["employee_id"],
                        re_formula="1",
                        vc_formula={"project": "0 + C(project_id)"} if use_vc else None,
                    )
                    res = model.fit(reml=True, method=[method])
                except (np.linalg.LinAlgError, ValueError) as exc:
                    caught.append(f"{method} failed (project_vc={use_vc}): {exc}")
                    continue
            msgs = sorted({type(x.message).__name__ + ": " + str(x.message).split("\n")[0] for x in w})
            caught.extend(msgs)
            if res.converged:
                return res, d, use_vc, caught
    raise RuntimeError(f"mixed model failed to converge: {caught}")


def mixed_estimates(res, d: pd.DataFrame, outcome: str, between: list[str] | None = None) -> pd.DataFrame:
    """Employee effects relative to context, with conditional 95% intervals.

    With ``between`` (Mundlak person-mean terms) the effect is the shrunk random intercept plus the between-person
    component (person means − population means)·γ, i.e. everything about the person's outcomes not explained by the
    within-person effect of their conditions. Its variance adds the uncertainty of γ.
    """
    sign = OUTCOMES[outcome]["sign"]
    rows = []
    re_cov = res.random_effects_cov
    n = d.groupby("employee_id").size()
    if between:
        pm = d.groupby("employee_id")[between].first()
        centred = pm - pm.mean()
        gamma = res.fe_params[between].to_numpy()
        cov_g = res.cov_params().loc[between, between].to_numpy()
    for emp, eff in res.random_effects.items():
        val = float(eff.iloc[0])
        var = float(np.asarray(re_cov[emp])[0, 0])
        if between:
            x = centred.loc[emp].to_numpy()
            val += float(x @ gamma)
            var += float(x @ cov_g @ x)
        se = float(np.sqrt(max(var, 0.0)))
        est = sign * val
        rows.append(
            {
                "employee_id": emp,
                "adjusted_estimate": est,
                "adjusted_se": se,
                "ci_low": est - 1.96 * se,
                "ci_high": est + 1.96 * se,
                "n": int(n.get(emp, 0)),
            }
        )
    return pd.DataFrame(rows)


def classify(est: pd.DataFrame, outcome: str, min_n: int = MIN_MILESTONES) -> pd.Series:
    """Evidence-based conclusion with explicit abstention."""
    max_w = OUTCOMES[outcome]["max_ci_width"]
    width = est["ci_high"] - est["ci_low"]
    label = np.where(
        (est["n"] < min_n) | (width > max_w),
        "insufficient_evidence",
        np.where(
            est["ci_low"] > 0,
            "above_context_expectation",
            np.where(est["ci_high"] < 0, "below_context_expectation", "within_expected_range"),
        ),
    )
    return pd.Series(label, index=est.index)


def run_contextual(m: pd.DataFrame, outcome: str, within_person: bool = True) -> ContextResult:
    """Context models for one outcome.

    ``within_person=True`` (default since v0.2) uses the Mundlak specification for the adjusted estimates; ``False``
    reproduces v0.1 (random intercept only), kept as a sensitivity specification.
    """
    ols, d = fit_context_ols(m, outcome)
    raw = raw_estimates(m, outcome)
    resid = residual_estimates(m, outcome, ols, d)
    between = None
    if within_person:
        mw, between = add_person_means(m)
        mres, md, used_vc, msgs = fit_mixed(mw, outcome, formula=within_person_formula(outcome))
    else:
        mres, md, used_vc, msgs = fit_mixed(m, outcome)
    mixed = mixed_estimates(mres, md, outcome, between=between)
    mixed["conclusion"] = classify(mixed, outcome)
    vc = {"employee_intercept_var": float(np.asarray(mres.cov_re)[0, 0]), "residual_var": float(mres.scale)}
    if used_vc and len(mres.vcomp):
        vc["project_var"] = float(mres.vcomp[0])
    total = sum(vc.values())
    vc["employee_share_of_variance"] = vc["employee_intercept_var"] / total if total else float("nan")

    # Assumption diagnostics.
    from scipy import stats
    from statsmodels.stats.diagnostic import het_breuschpagan

    resid_ = np.asarray(mres.resid)
    bp = het_breuschpagan(ols.resid, sm.add_constant(ols.model.exog[:, 1:]))
    diagnostics = {
        "specification": "within-person (Mundlak) mixed model" if within_person else "random-intercept mixed model (v0.1)",
        "within_person_coefficients": {c: float(mres.fe_params[c]) for c in CONTEXT_NUMERIC if c in mres.fe_params},
        "n_observations": int(len(md)),
        "n_employees": int(md["employee_id"].nunique()),
        "n_projects": int(md["project_id"].nunique()),
        "mixed_converged": bool(mres.converged),
        "project_variance_component": used_vc,
        "fit_warnings": msgs,
        "ols_r2": float(ols.rsquared),
        "residual_skew": float(stats.skew(resid_)),
        "residual_excess_kurtosis": float(stats.kurtosis(resid_)),
        "breusch_pagan_p": float(bp[1]),
        "assumption_notes": _assumption_notes(resid_, bp[1]),
    }
    return ContextResult(outcome, ols, coefficient_table(ols), raw, resid, mixed, vc, diagnostics)


def _assumption_notes(resid: np.ndarray, bp_p: float) -> list[str]:
    from scipy import stats

    notes = []
    if abs(stats.kurtosis(resid)) > 1:
        notes.append(
            "Residuals are heavy-tailed; intervals assume approximate normality and may be optimistic. "
            "Bootstrap and robust-regression sensitivity checks are reported alongside."
        )
    if bp_p < 0.05:
        notes.append(
            "Residual variance changes with context (Breusch–Pagan p<0.05); cluster-robust standard "
            "errors are used for context coefficients."
        )
    notes.append("Assignment to projects is not random: adjusted estimates remove *measured* context only.")
    return notes
