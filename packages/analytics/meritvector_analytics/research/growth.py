"""Workstream 6 — longitudinal growth model (random slopes).

Per-person trend tests are under-powered at v0.1 evidence density. A random-slope model pools information across
people to ask a population question first: is there between-person variance in growth of the context-adjusted
signal? Individual slopes are then shrunk BLUPs with conditional intervals.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from meritvector_analytics.research.data import ResearchData, jsonable, pseudonym


def growth_model(rd: ResearchData, min_milestones: int = 6) -> dict[str, Any]:
    ols, d = rd.context_ols
    d = d.assign(signal=-ols.resid, years=d["month_index"] / 12.0)
    n = d.groupby("employee_id").size()
    d = d[d["employee_id"].isin(n[n >= min_milestones].index)].copy()
    d["years_c"] = d["years"] - d["years"].mean()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fits = {}
        for name, re_f in (("intercept", "1"), ("slope", "~years_c")):
            best = None
            for method in ("lbfgs", "bfgs", "powell", "nm"):
                try:
                    r = smf.mixedlm("signal ~ years_c", d, groups=d["employee_id"], re_formula=re_f).fit(reml=False, method=[method])
                except (np.linalg.LinAlgError, ValueError):
                    continue
                if not np.isfinite(r.llf):
                    continue
                if best is None or r.llf > best.llf:
                    best = r
            fits[name] = best
    m1, m2 = fits["intercept"], fits["slope"]
    lr = max(0.0, 2 * (m2.llf - m1.llf))
    # Boundary-corrected LRT: 50:50 mixture of chi2(1) and chi2(2).
    p = 0.5 * stats.chi2.sf(lr, 1) + 0.5 * stats.chi2.sf(lr, 2)
    cov = np.asarray(m2.cov_re)
    slope_var = float(cov[1, 1])
    rows = []
    for emp, eff in m2.random_effects.items():
        c = np.asarray(m2.random_effects_cov[emp])
        slope = float(eff.iloc[1]) + float(m2.fe_params["years_c"])
        se = float(np.sqrt(max(c[1, 1], 0)))
        rows.append({"pid": pseudonym(emp), "employee_id": emp, "slope": slope, "ci_low": slope - 1.96 * se, "ci_high": slope + 1.96 * se})
    slopes = pd.DataFrame(rows)
    return jsonable(
        {
            "kind": "descriptive",
            "status": "exploratory",
            "question": "Does growth in context-adjusted delivery signal vary between people?",
            "n_employees": int(d["employee_id"].nunique()),
            "n_milestones": int(len(d)),
            "mean_slope_pp_per_year": float(m2.fe_params["years_c"]),
            "slope_sd_pp_per_year": float(np.sqrt(max(slope_var, 0))),
            "lrt_statistic": float(lr),
            "p_value": float(p),
            "improving_with_ci_above_zero": int((slopes["ci_low"] > 0).sum()),
            "declining_with_ci_below_zero": int((slopes["ci_high"] < 0).sum()),
            "interpretation": (
                f"Between-person variation in growth is {'detectable' if p < 0.05 else 'not detectable'} "
                f"(LRT p={p:.3g}); typical growth varies by ±{np.sqrt(max(slope_var, 0)):.1f} pp/year around the average."
            ),
            "regression_to_mean_note": "Slopes are shrunk towards the average; a person who started unusually badly will "
            "appear to improve partly by chance (Barnett et al. 2005).",
            "_slopes": slopes,
        }
    )
