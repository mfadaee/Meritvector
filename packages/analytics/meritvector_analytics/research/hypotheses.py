"""Workstream 2 — registered hypothesis tests (config/research/hypotheses.yaml).

Each result reports the test statistic, p-value, an effect size with a confidence interval, assumption checks and
the family-wise adjusted p-value. Units of analysis follow the registration (e.g. project means for H6 to avoid
treating repeated milestones as independent).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import yaml
from scipy import stats
from statsmodels.stats.multitest import multipletests

from meritvector_analytics.measurement import config_dir
from meritvector_analytics.research.data import ResearchData, jsonable


def registered() -> dict[str, Any]:
    return yaml.safe_load((config_dir() / "research" / "hypotheses.yaml").read_text())


def _boot_ci(fn, *arrays, n: int = 1000, seed: int = 0) -> list[float]:
    rng = np.random.default_rng(seed)
    k = len(arrays[0])
    vals = []
    for _ in range(n):
        i = rng.integers(0, k, k)
        try:
            vals.append(fn(*[a[i] for a in arrays]))
        except (ValueError, ZeroDivisionError, FloatingPointError):
            continue
    return [float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))]


def _spearman(x: pd.Series, y: pd.Series) -> dict[str, Any]:
    d = pd.concat([x, y], axis=1).dropna()
    a, b = d.iloc[:, 0].to_numpy(float), d.iloc[:, 1].to_numpy(float)
    r = stats.spearmanr(a, b)
    return {
        "statistic": float(r.statistic),
        "p_value": float(r.pvalue),
        "n": int(len(d)),
        "effect_size": {
            "name": "Spearman rho",
            "value": float(r.statistic),
            "ci95": _boot_ci(lambda u, v: stats.spearmanr(u, v).statistic, a, b),
        },
        "assumptions": {"monotone_relationship": "assumed", "independent_units": "employees"},
    }


def _eta_squared(groups: list[np.ndarray]) -> float:
    allx = np.concatenate(groups)
    ssb = sum(len(g) * (g.mean() - allx.mean()) ** 2 for g in groups)
    sst = ((allx - allx.mean()) ** 2).sum()
    return float(ssb / sst) if sst else 0.0


def _kruskal_anova(value: pd.Series, group: pd.Series) -> dict[str, Any]:
    d = pd.DataFrame({"v": value, "g": group}).dropna()
    groups = [g["v"].to_numpy(float) for _, g in d.groupby("g") if len(g) >= 3]
    h = stats.kruskal(*groups)
    f = stats.f_oneway(*groups)
    lev = stats.levene(*groups)
    labels = d["g"].to_numpy()
    vals = d["v"].to_numpy(float)
    eta = _eta_squared(groups)

    def boot_eta(v, lab):
        gs = [v[lab == k] for k in np.unique(lab) if (lab == k).sum() >= 2]
        return _eta_squared(gs)

    return {
        "statistic": float(h.statistic),
        "p_value": float(h.pvalue),
        "n": int(len(d)),
        "groups": len(groups),
        "anova": {"F": float(f.statistic), "p_value": float(f.pvalue)},
        "effect_size": {"name": "eta squared", "value": eta, "ci95": _boot_ci(boot_eta, vals, labels)},
        "assumptions": {"levene_p": float(lev.pvalue), "equal_variances": bool(lev.pvalue > 0.05)},
        "group_means": {str(k): float(g["v"].mean()) for k, g in d.groupby("g")},
    }


def _rater_effect(rd: ResearchData) -> dict[str, Any]:
    r = rd.ratings.merge(rd.employee_frame[["employee_id", "adjusted_signal"]], on="employee_id").dropna(subset=["adjusted_signal"])
    counts = r.groupby("rater_id").size()
    r = r[r["rater_id"].isin(counts[counts >= 8].index)]
    base = smf.ols("manager_rating ~ adjusted_signal + C(period)", r).fit()
    full = smf.ols("manager_rating ~ adjusted_signal + C(period) + C(rater_id)", r).fit()
    an = sm.stats.anova_lm(base, full)
    ss_rater = base.ssr - full.ssr
    peta = float(ss_rater / (ss_rater + full.ssr))
    return {
        "statistic": float(an["F"].iloc[1]),
        "p_value": float(an["Pr(>F)"].iloc[1]),
        "n": int(len(r)),
        "raters": int(r["rater_id"].nunique()),
        "effect_size": {"name": "partial eta squared (rater)", "value": peta, "ci95": None},
        "evidence_slope": float(full.params["adjusted_signal"]),
        "assumptions": {"design": "ANCOVA, ratings nested in raters; ratings treated as interval (1–5) — approximation"},
    }


def _ols_coefficient(rd: ResearchData, term: str) -> dict[str, Any]:
    ols, d = rd.context_ols
    coef, ci = float(ols.params[term]), ols.conf_int().loc[term].tolist()
    t = float(ols.tvalues[term])
    dof = float(ols.df_resid)
    f = abs(t) / np.sqrt(dof)
    rv = 0.5 * (np.sqrt(f**4 + 4 * f**2) - f**2)  # Cinelli & Hazlett (2020) robustness value, q = 1
    std = coef * d[term].std() / d["schedule_variance_pct"].std()
    return {
        "statistic": t,
        "p_value": float(ols.pvalues[term]),
        "n": int(ols.nobs),
        "effect_size": {
            "name": "coefficient (pp per unit)",
            "value": coef,
            "ci95": [float(ci[0]), float(ci[1])],
            "standardised": float(std),
        },
        "robustness_value": float(rv),
        "assumptions": {"se": "cluster-robust by project", "causal": "association only — see causal workstream"},
    }


def _hedges_g(a: np.ndarray, b: np.ndarray) -> tuple[float, list[float]]:
    na, nb = len(a), len(b)
    sp = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    d = (a.mean() - b.mean()) / sp
    j = 1 - 3 / (4 * (na + nb) - 9)
    g = d * j
    se = np.sqrt((na + nb) / (na * nb) + g**2 / (2 * (na + nb)))
    return float(g), [float(g - 1.96 * se), float(g + 1.96 * se)]


def _welch(rd: ResearchData, levels: list[str]) -> dict[str, Any]:
    p = rd.project_frame.dropna(subset=["project_mean_svp"])
    a = p.loc[p["environment"] == levels[0], "project_mean_svp"].to_numpy(float)
    b = p.loc[p["environment"] == levels[1], "project_mean_svp"].to_numpy(float)
    w = stats.ttest_ind(a, b, equal_var=False)
    mw = stats.mannwhitneyu(a, b)
    g, gci = _hedges_g(a, b)
    cliff = float((np.sign(a[:, None] - b[None, :])).mean())
    return {
        "statistic": float(w.statistic),
        "p_value": float(w.pvalue),
        "n": int(len(a) + len(b)),
        "means": {levels[0]: float(a.mean()), levels[1]: float(b.mean())},
        "effect_size": {"name": "Hedges g", "value": g, "ci95": gci, "cliffs_delta": cliff},
        "robustness": {"mann_whitney_p": float(mw.pvalue)},
        "assumptions": {
            "unit": "project means (repeated milestones aggregated)",
            "shapiro_p": [float(stats.shapiro(a[:500]).pvalue), float(stats.shapiro(b[:500]).pvalue)],
        },
        "note": "Unadjusted comparison: regulated projects also differ in complexity and size, so a difference "
        "describes conditions, not causes.",
    }


def run_hypotheses(rd: ResearchData, extra: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Run every registered hypothesis. ``extra`` supplies results computed elsewhere (e.g. H7 experiment, H8 growth)."""
    reg = registered()
    e = rd.employee_frame
    out: dict[str, dict[str, Any]] = {}
    for h in reg["hypotheses"]:
        hid, test, v = h["id"], h["test"], h["variables"]
        try:
            if test == "spearman":
                if hid == "H1":
                    sub = e[(e["first_year_n"] >= 3) & (e["later_n"] >= 3)]
                    res = _spearman(sub[v["x"]], sub[v["y"]])
                else:
                    res = _spearman(e[v["x"]], e[v["y"]])
            elif test == "kruskal_anova":
                res = _kruskal_anova(e[v["value"]], e[v["group"]])
            elif test == "rater_effect_anova":
                res = _rater_effect(rd)
            elif test == "ols_cluster_coefficient":
                res = _ols_coefficient(rd, v["term"])
            elif test == "welch_t":
                res = _welch(rd, v["levels"])
            elif extra and hid in extra:
                res = extra[hid]
            else:
                res = {"skipped": "requires a result from another workstream"}
        except (ValueError, KeyError, np.linalg.LinAlgError) as exc:
            res = {"error": str(exc)}
        out[hid] = {"registration": h, "result": res}
    for fam in reg["families"]:
        ids = [i for i in fam["hypotheses"] if "p_value" in out[i]["result"]]
        if not ids:
            continue
        method = {"holm": "holm", "bh": "fdr_bh"}[fam["correction"]]
        rej, padj, _, _ = multipletests([out[i]["result"]["p_value"] for i in ids], alpha=reg["alpha"], method=method)
        for i, r_, pa in zip(ids, rej, padj, strict=True):
            out[i]["result"]["p_adjusted"] = float(pa)
            out[i]["result"]["family"] = fam["id"]
            out[i]["result"]["decision"] = "reject H0" if r_ else "fail to reject H0"
    for o in out.values():
        r = o["result"]
        if "p_value" in r and "decision" not in r:
            r["decision"] = "reject H0" if r["p_value"] < reg["alpha"] else "fail to reject H0"
            r["p_adjusted"] = r["p_value"]
    return jsonable(
        {
            "kind": "inferential",
            "alpha": reg["alpha"],
            "hypotheses": out,
            "note": "Decisions use family-wise adjusted p-values; effect sizes and intervals matter more than "
            "the binary decision. Synthetic data: results show method behaviour, not real-world findings.",
        }
    )
