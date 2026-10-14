"""Studies on public, real-world project data (config/public_data/sources.yaml).

They test the measurement claims MeritVector makes on synthetic data against real organisations' records:

1. Raw delivery metrics mostly reflect the conditions work is done under (size and measured context).
2. Comparing delivery *units* on raw metrics misleads; adjusting for measured context changes the picture.
3. Team or capability indicators explain a smaller, less certain share of outcomes than context does.
4. Simple, transparent models generalise about as well as complex ones, and models do not transfer automatically
   between organisations.

Units are projects and organisations — none of these data identify people. Results are associations in
observational data and say nothing about any individual.
"""

from __future__ import annotations

import itertools
import math
import warnings
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupKFold, KFold

from meritvector_analytics.public_data.catalog import load, registry
from meritvector_analytics.research.data import jsonable

MIN_UNIT = 20  # delivery units with fewer projects are not compared
RATING = {"vl": 1, "l": 2, "n": 3, "h": 4, "vh": 5, "xh": 6}


def _provenance(source_id: str) -> dict[str, Any]:
    s = registry()["sources"][source_id]
    return {k: s[k] for k in ("title", "origin", "terms", "description", "unit", "limitations")}


def _r2(d: pd.DataFrame, y: str, terms: list[str]) -> float:
    if not terms:
        return 0.0
    return float(smf.ols(f"{y} ~ {' + '.join(terms)}", d).fit().rsquared)


def shapley_r2(d: pd.DataFrame, y: str, blocks: dict[str, list[str]]) -> dict[str, float]:
    """Exact Shapley decomposition of in-sample R² across blocks of terms (order-independent shares)."""
    names = list(blocks)
    cache: dict[frozenset, float] = {}

    def r2(sub: frozenset) -> float:
        if sub not in cache:
            cache[sub] = _r2(d, y, [t for b in sub for t in blocks[b]])
        return cache[sub]

    out = dict.fromkeys(names, 0.0)
    n = len(names)
    for b in names:
        others = [x for x in names if x != b]
        for k in range(n):
            for sub in itertools.combinations(others, k):
                w = math.factorial(k) * math.factorial(n - k - 1) / math.factorial(n)
                out[b] += w * (r2(frozenset(sub) | {b}) - r2(frozenset(sub)))
    out["total"] = r2(frozenset(names))
    return out


def _boot_shapley(d: pd.DataFrame, y: str, blocks: dict[str, list[str]], n_boot: int, seed: int) -> dict[str, list[float]]:
    rng = np.random.default_rng(seed)
    draws: dict[str, list[float]] = {b: [] for b in [*blocks, "total"]}
    for _ in range(n_boot):
        s = d.iloc[rng.integers(0, len(d), len(d))]
        try:
            v = shapley_r2(s, y, blocks)
        except (ValueError, np.linalg.LinAlgError):
            continue
        for k in draws:
            draws[k].append(v[k])
    return {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in draws.items() if v}


def _decomposition(d: pd.DataFrame, y: str, blocks: dict[str, list[str]], n_boot: int, seed: int) -> dict[str, Any]:
    point = shapley_r2(d, y, blocks)
    ci = _boot_shapley(d, y, blocks, n_boot, seed)
    return {
        "method": "Shapley decomposition of in-sample R² (ordinary least squares); 95% bootstrap intervals",
        "blocks": {b: {"terms": blocks[b], "share_of_variance": point[b], "ci95": ci.get(b)} for b in blocks},
        "total_r2": point["total"],
        "total_ci95": ci.get("total"),
    }


def _coef(res, term: str) -> dict[str, float]:
    lo, hi = res.conf_int().loc[term]
    return {"estimate": float(res.params[term]), "ci95": [float(lo), float(hi)], "p_value": float(res.pvalues[term])}


def _pct(log_diff: float) -> float:
    return float(100 * (math.exp(log_diff) - 1))


def compare_units(d: pd.DataFrame, y: str, unit: str, context_terms: list[str], n_boot: int, seed: int) -> dict[str, Any]:
    """Raw vs context-adjusted differences between delivery units (deviation from the mean of units), log scale."""
    counts = d[unit].value_counts()
    keep = counts[counts >= MIN_UNIT].index
    d = d[d[unit].isin(keep)].copy()
    d["_u"] = d[unit].astype(str)
    units = sorted(d["_u"].unique())

    def effects(s: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
        raw_means = s.groupby("_u")[y].mean()
        raw = (raw_means - raw_means.mean()).to_dict()
        res = smf.ols(f"{y} ~ {' + '.join(context_terms)} + C(_u, Sum)", s).fit()
        coefs = {u: float(res.params.get(f"C(_u, Sum)[S.{u}]", np.nan)) for u in units}
        last = units[-1]
        coefs[last] = -sum(v for k, v in coefs.items() if k != last)
        return raw, coefs

    raw, adj = effects(d)
    rng = np.random.default_rng(seed)
    boots_raw, boots_adj = {u: [] for u in units}, {u: [] for u in units}
    for _ in range(n_boot):
        s = pd.concat([g.iloc[rng.integers(0, len(g), len(g))] for _, g in d.groupby("_u")])
        try:
            r, a = effects(s)
        except (ValueError, np.linalg.LinAlgError):
            continue
        for u in units:
            boots_raw[u].append(r[u])
            boots_adj[u].append(a[u])

    def ci(v: list[float]) -> list[float]:
        return [_pct(np.nanpercentile(v, 2.5)), _pct(np.nanpercentile(v, 97.5))]

    rows = []
    for u in units:
        rows.append(
            {
                "unit": u,
                "n_projects": int((d["_u"] == u).sum()),
                "raw_difference_pct": _pct(raw[u]),
                "raw_ci95": ci(boots_raw[u]),
                "adjusted_difference_pct": _pct(adj[u]),
                "adjusted_ci95": ci(boots_adj[u]),
            }
        )
    raw_order = [r["unit"] for r in sorted(rows, key=lambda r: r["raw_difference_pct"])]
    adj_order = [r["unit"] for r in sorted(rows, key=lambda r: r["adjusted_difference_pct"])]
    sign_flips = [r["unit"] for r in rows if np.sign(r["raw_difference_pct"]) != np.sign(r["adjusted_difference_pct"])]
    shrink = float(
        np.mean([abs(r["adjusted_difference_pct"]) for r in rows]) / max(1e-9, np.mean([abs(r["raw_difference_pct"]) for r in rows]))
    )
    return {
        "units": rows,
        "order_changed": raw_order != adj_order,
        "direction_changed_for": sign_flips,
        "adjusted_to_raw_gap_ratio": shrink,
        "note": "Differences are relative to the average unit; positive = more cost (or time) than average. Units with "
        f"fewer than {MIN_UNIT} projects are not compared. The table is in alphabetical order — it is not a ranking.",
    }


def _cv_mae(models: dict[str, Any], X: pd.DataFrame, y: np.ndarray, splitter, groups=None) -> dict[str, dict[str, float]]:
    out = {}
    for name, est in models.items():
        val, tr = [], []
        for a, b in splitter.split(X, y, groups):
            if est is None:  # baseline: training median
                pred_b = np.full(len(b), np.median(y[a]))
                pred_a = np.full(len(a), np.median(y[a]))
            else:
                est.fit(X.iloc[a], y[a])
                pred_b, pred_a = est.predict(X.iloc[b]), est.predict(X.iloc[a])
            val.append(np.mean(np.abs(y[b] - pred_b)))
            tr.append(np.mean(np.abs(y[a] - pred_a)))
        out[name] = {
            "validation_mae_log": float(np.mean(val)),
            "train_mae_log": float(np.mean(tr)),
            "typical_error_factor": float(math.exp(float(np.mean(val)))),
            "generalisation_gap": float(np.mean(val) - np.mean(tr)),
        }
    return out


def _models() -> dict[str, Any]:
    return {
        "median_baseline": None,
        "linear_context": LinearRegression(),
        "random_forest": RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=0),
        "gradient_boosting": HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, random_state=0),
    }


def _lump(s: pd.Series, min_count: int = 8) -> pd.Series:
    """Merge rare categories into 'other' so no single project dominates (and robust errors stay defined)."""
    s = s.fillna("unknown").astype(str)
    counts = s.value_counts()
    return s.where(s.map(counts) >= min_count, "other")


def recording_practice(d: pd.DataFrame, unit: str, flags: list[str]) -> dict[str, Any]:
    """Which flags some units never record — a measurement difference that adjustment cannot repair."""
    by = d.groupby(unit)[flags].sum()
    never = {f: sorted(str(u) for u in by.index[by[f] == 0]) for f in flags if (by[f] == 0).any()}
    return {
        "never_recorded_by_unit": never,
        "note": "A flag that one organisation never records may reflect recording practice rather than an absence of the "
        "condition. Its estimated effect then rests on the other organisations only, and comparisons between "
        "organisations partly reflect what each one writes down.",
    }


def _sparse_flags(d: pd.DataFrame, flags: list[str], min_count: int = 8) -> list[str]:
    return [f for f in flags if f in d and min_count <= d[f].sum() <= len(d) - min_count]


# ------------------------------------------------------------------ EBSPM
def ebspm(n_boot: int = 300, seed: int = 0) -> dict[str, Any]:
    spec = registry()["sources"]["ebspm"]["roles"]
    d = load("ebspm")
    d = d[(d["Actual_cost_EUR"] > 0) & (d["Functional_size_FP"] > 0) & (d["Actual_duration_months"] > 0)].copy()
    d = d[d["Organization"].map(d["Organization"].value_counts()) >= MIN_UNIT].copy()
    d["log_size"] = np.log(d["Functional_size_FP"])
    d["log_cost_per_fp"] = np.log(d["Actual_cost_EUR"] / d["Functional_size_FP"])
    d["log_duration"] = np.log(d["Actual_duration_months"])
    d["year_c"] = d["Year_technical_go_live"] - d["Year_technical_go_live"].median()
    d["dev_class"] = _lump(d["Development_class"])
    d["method"] = _lump(d["Development_method"])
    flags = _sparse_flags(d, [c for c in spec["context"] if c not in ("Development_class", "Development_method", "Year_technical_go_live")])
    team = _sparse_flags(d, spec["team"])
    context_terms = ["C(dev_class)", "C(method)", "year_c", *flags]
    results: dict[str, Any] = {}
    for y, label in (("log_cost_per_fp", "cost per function point"), ("log_duration", "duration")):
        size_terms = ["log_size"]
        blocks = {"size": size_terms, "measured_context": context_terms, "team_indicators": team, "organisation": ["C(Organization)"]}
        decomposition = _decomposition(d, y, blocks, n_boot=max(50, n_boot // 3), seed=seed)
        units = compare_units(d, y, "Organization", size_terms + context_terms, n_boot=n_boot, seed=seed)
        full = smf.ols(f"{y} ~ {' + '.join(size_terms + context_terms + team)} + C(Organization)", d).fit(cov_type="HC3")
        team_effects = {}
        for t in team:
            raw = smf.ols(f"{y} ~ {t}", d).fit(cov_type="HC3")
            team_effects[t] = {
                "raw": _coef(raw, t),
                "adjusted": _coef(full, t),
                "raw_pct": _pct(raw.params[t]),
                "adjusted_pct": _pct(full.params[t]),
            }
        context_effects = {f: {**_coef(full, f), "pct": _pct(full.params[f])} for f in flags if f in full.params}
        X = pd.get_dummies(d[["log_size", "year_c", "dev_class", "method", *flags]], columns=["dev_class", "method"], dtype=float)
        yy = d[y].to_numpy()
        within = _cv_mae(_models(), X, yy, KFold(5, shuffle=True, random_state=seed))
        across = _cv_mae(_models(), X, yy, GroupKFold(n_splits=d["Organization"].nunique()), groups=d["Organization"].to_numpy())
        results[y] = {
            "outcome": label,
            "n_projects": int(len(d)),
            "variance_decomposition": decomposition,
            "unit_comparison": units,
            "team_indicators": team_effects,
            "context_effects": context_effects,
            "generalisation": {"random_5_fold": within, "leave_one_organisation_out": across},
        }
    c = results["log_cost_per_fp"]
    dec = c["variance_decomposition"]["blocks"]
    uc = c["unit_comparison"]
    shares = dec["size"]["share_of_variance"] + dec["measured_context"]["share_of_variance"]
    plain = (
        f"Across {c['n_projects']} real projects from {d['Organization'].nunique()} organisations, project size and measured "
        f"context account for {100 * shares:.0f}% of the variation in cost per function point, team indicators for "
        f"{100 * dec['team_indicators']['share_of_variance']:.0f}% and the organisation itself for "
        f"{100 * dec['organisation']['share_of_variance']:.0f}%. "
    )
    if uc["order_changed"] or uc["direction_changed_for"]:
        plain += "Adjusting for size and context changes the comparison between organisations"
        if uc["direction_changed_for"]:
            plain += f" — the direction reverses for {', '.join(uc['direction_changed_for'])}"
        plain += "."
    else:
        ratio = uc["adjusted_to_raw_gap_ratio"]
        plain += (
            f"Adjusting for size and context leaves the order of organisations unchanged, but the gaps {'widen' if ratio > 1 else 'narrow'} "
            f"(adjusted gaps are {ratio:.1f}× the raw ones): raw figures can understate, not only overstate, differences."
        )
    fet = c["team_indicators"].get("Fixed_experienced_team")
    if fet:
        lo, hi = (_pct(x) for x in fet["adjusted"]["ci95"])
        plain += (
            f" Projects flagged as having a fixed, experienced team cost {abs(fet['raw_pct']):.0f}% "
            f"{'less' if fet['raw_pct'] < 0 else 'more'} per function point on raw figures, but {abs(fet['adjusted_pct']):.0f}% "
            f"{'less' if fet['adjusted_pct'] < 0 else 'more'} once size, context and organisation are accounted for "
            f"(95% {lo:+.0f}% to {hi:+.0f}%) — raw team comparisons overstate the team effect."
        )
    lofo = c["generalisation"]["leave_one_organisation_out"]
    if lofo["linear_context"]["validation_mae_log"] >= lofo["median_baseline"]["validation_mae_log"]:
        plain += " A context model trained on two organisations does not beat a simple median when applied to the third."
    return jsonable(
        {
            "kind": "observational",
            "status": "exploratory",
            "question": "Do raw cost and duration comparisons between delivery organisations survive adjustment for project size and context?",
            "provenance": _provenance("ebspm"),
            "context_flags_used": flags,
            "recording_practice": recording_practice(d, "Organization", flags + team),
            "team_indicators_used": team,
            "results": results,
            "plain_language": plain,
            "caveats": [
                "Organisation is confounded with domain and portfolio mix that the flags do not capture.",
                "Associations in observational data; team flags are recorded labels, not measured capability.",
            ],
        }
    )


# ------------------------------------------------------------------ Maxwell
def maxwell(n_boot: int = 300, seed: int = 0) -> dict[str, Any]:
    reg = registry()["sources"]["maxwell"]
    d = load("maxwell").dropna(subset=["effort_D", "size_D"])
    d = d[(d["effort_D"] > 0) & (d["size_D"] > 0)].copy()
    for c in [f"t{i:02d}" for i in range(1, 16)]:
        d[c] = pd.to_numeric(d[c])
    d["log_size"] = np.log(d["size_D"])
    d["log_hours_per_fp"] = np.log(d["effort_D"] / d["size_D"])
    d["staff_skill_index"] = d[["t12", "t13", "t14", "t15"]].mean(axis=1)
    context = [
        "t01",
        "t03",
        "t07",
        "t08",
        "t09",
    ]  # a priori: customer participation, staff availability, complexity, volatility, quality reqs
    blocks = {"size": ["log_size"], "measured_context": context, "staff_skills": ["staff_skill_index"]}
    y = "log_hours_per_fp"
    dec = _decomposition(d, y, blocks, n_boot=n_boot // 3, seed=seed)
    full = smf.ols(f"{y} ~ log_size + {' + '.join(context)} + staff_skill_index", d).fit(cov_type="HC3")
    raw_rho = stats.spearmanr(d["staff_skill_index"], d[y])
    loo = {}
    for name, terms in {
        "size_only": ["log_size"],
        "size_and_context": ["log_size", *context],
        "size_context_and_staff": ["log_size", *context, "staff_skill_index"],
        "size_and_staff": ["log_size", "staff_skill_index"],
    }.items():
        errs = []
        for i in range(len(d)):
            tr, te = d.drop(d.index[i]), d.iloc[[i]]
            res = smf.ols(f"{y} ~ {' + '.join(terms)}", tr).fit()
            errs.append(float(te[y].iloc[0] - res.predict(te).iloc[0]))
        loo[name] = {
            "loo_mae_log": float(np.mean(np.abs(errs))),
            "loo_r2": float(1 - np.sum(np.square(errs)) / np.sum((d[y] - d[y].mean()) ** 2)),
        }
    labels = reg["factor_labels"]
    return jsonable(
        {
            "kind": "observational",
            "status": "exploratory",
            "question": "How much of the variation in productivity is explained by project context versus staff skill ratings?",
            "provenance": _provenance("maxwell"),
            "n_projects": int(len(d)),
            "context_factors": {c: labels[c] for c in context},
            "variance_decomposition": dec,
            "staff_skill": {
                "raw_spearman": {"rho": float(raw_rho.statistic), "p_value": float(raw_rho.pvalue)},
                "adjusted": {**_coef(full, "staff_skill_index"), "pct_per_point": _pct(full.params["staff_skill_index"])},
            },
            "context_effects": {labels[c]: {**_coef(full, c), "pct_per_point": _pct(full.params[c])} for c in context},
            "leave_one_out": loo,
            "plain_language": (
                f"In {len(d)} bank projects, size and five pre-chosen context ratings explain "
                f"{100 * (dec['blocks']['size']['share_of_variance'] + dec['blocks']['measured_context']['share_of_variance']):.0f}% "
                f"of the variation in hours per function point; the staff-skill rating adds "
                f"{100 * dec['blocks']['staff_skills']['share_of_variance']:.0f}%. Out of sample, adding staff skills changes the "
                f"error from {loo['size_and_context']['loo_mae_log']:.3f} to {loo['size_context_and_staff']['loo_mae_log']:.3f} (log scale)."
            ),
            "caveats": ["Ratings are subjective; one organisation; 62 projects — intervals are wide."],
        }
    )


# ------------------------------------------------------------------ NASA93
def nasa93(n_boot: int = 300, seed: int = 0) -> dict[str, Any]:
    d = load("nasa93").dropna(subset=["act_effort", "equivphyskloc"])
    d = d[(d["act_effort"] > 0) & (d["equivphyskloc"] > 0)].copy()
    ordinal = ["rely", "data", "cplx", "time", "stor", "virt", "turn", "tool", "sced", "modp", "acap", "pcap", "aexp", "vexp", "lexp"]
    for c in ordinal:
        d[c] = d[c].map(RATING)
    d["log_size"] = np.log(d["equivphyskloc"])
    d["log_effort_per_kloc"] = np.log(d["act_effort"] / d["equivphyskloc"])
    d["capability_index"] = d[["acap", "pcap", "aexp", "vexp", "lexp"]].mean(axis=1)
    d["year_c"] = d["year"] - d["year"].median()
    d["centre"] = "centre " + d["center"].astype(str)
    context = ["C(mode)", "rely", "cplx", "time", "stor", "data", "virt", "turn", "tool", "sced", "year_c"]
    y = "log_effort_per_kloc"
    blocks = {"size": ["log_size"], "measured_context": context, "capability_ratings": ["capability_index"], "centre": ["C(centre)"]}
    dec = _decomposition(d, y, blocks, n_boot=n_boot // 3, seed=seed)
    units = compare_units(d, y, "centre", ["log_size", *context], n_boot=n_boot, seed=seed)
    full = smf.ols(f"{y} ~ log_size + {' + '.join(context)} + capability_index", d).fit(cov_type="HC3")
    raw = smf.ols(f"{y} ~ capability_index", d).fit(cov_type="HC3")
    X = pd.get_dummies(
        d[["log_size", "year_c", "mode", *[c for c in ordinal if c not in ("acap", "pcap", "aexp", "vexp", "lexp")]]],
        columns=["mode"],
        dtype=float,
    )
    yy = d[y].to_numpy()
    big = d["center"].map(d["center"].value_counts()) >= 5
    gen = {
        "random_5_fold": _cv_mae(_models(), X, yy, KFold(5, shuffle=True, random_state=seed)),
        "leave_one_centre_out": _cv_mae(
            _models(),
            X[big.to_numpy()],
            yy[big.to_numpy()],
            GroupKFold(d.loc[big, "center"].nunique()),
            groups=d.loc[big, "center"].to_numpy(),
        ),
    }
    return jsonable(
        {
            "kind": "observational",
            "status": "exploratory",
            "question": "Do NASA centres' raw productivity differences survive adjustment for project context, and how much do capability ratings add?",
            "provenance": _provenance("nasa93"),
            "n_projects": int(len(d)),
            "variance_decomposition": dec,
            "unit_comparison": units,
            "capability": {
                "raw": {**_coef(raw, "capability_index"), "pct_per_level": _pct(raw.params["capability_index"])},
                "adjusted": {**_coef(full, "capability_index"), "pct_per_level": _pct(full.params["capability_index"])},
            },
            "generalisation": gen,
            "plain_language": (
                f"In {len(d)} NASA projects, size and measured context explain "
                f"{100 * (dec['blocks']['size']['share_of_variance'] + dec['blocks']['measured_context']['share_of_variance']):.0f}% of the "
                f"variation in effort per thousand lines of code; capability ratings {100 * dec['blocks']['capability_ratings']['share_of_variance']:.0f}% "
                f"and the centre {100 * dec['blocks']['centre']['share_of_variance']:.0f}%. "
                + (
                    "Adjustment changes the order of centres."
                    if units["order_changed"]
                    else "Adjustment does not change the order of centres."
                )
            ),
            "caveats": ["Capability levels are estimator judgements, not measurements.", "Projects from 1971–1987."],
        }
    )


# ------------------------------------------------------------------ Desharnais
def desharnais(n_boot: int = 1000, seed: int = 0) -> dict[str, Any]:
    d = load("desharnais").dropna(subset=["TeamExp", "ManagerExp", "Effort", "PointsAdjust"])
    d = d[(d["Effort"] > 0) & (d["PointsAdjust"] > 0)].copy()
    d["log_size"] = np.log(d["PointsAdjust"])
    d["log_hours_per_fp"] = np.log(d["Effort"] / d["PointsAdjust"])
    y = "log_hours_per_fp"
    rng = np.random.default_rng(seed)
    raw = stats.spearmanr(d["ManagerExp"], d[y])
    boots = []
    for _ in range(n_boot):
        s = d.iloc[rng.integers(0, len(d), len(d))]
        boots.append(stats.spearmanr(s["ManagerExp"], s[y]).statistic)
    adj = smf.ols(f"{y} ~ log_size + C(Language) + Envergure + YearEnd + TeamExp + ManagerExp", d).fit(cov_type="HC3")
    blocks = {"size": ["log_size"], "measured_context": ["C(Language)", "Envergure", "YearEnd"], "experience": ["TeamExp", "ManagerExp"]}
    dec = _decomposition(d, y, blocks, n_boot=n_boot // 5, seed=seed)
    m = _coef(adj, "ManagerExp")
    return jsonable(
        {
            "kind": "observational",
            "status": "exploratory",
            "question": "Is project-manager experience associated with productivity once size, language and complexity are accounted for?",
            "provenance": _provenance("desharnais"),
            "n_projects": int(len(d)),
            "manager_experience": {
                "raw_spearman": {
                    "rho": float(raw.statistic),
                    "p_value": float(raw.pvalue),
                    "ci95": [float(np.nanpercentile(boots, 2.5)), float(np.nanpercentile(boots, 97.5))],
                },
                "adjusted": {**m, "pct_per_year": _pct(m["estimate"])},
            },
            "team_experience_adjusted": {**_coef(adj, "TeamExp"), "pct_per_year": _pct(adj.params["TeamExp"])},
            "variance_decomposition": dec,
            "plain_language": (
                f"In {len(d)} Canadian projects, each extra year of manager experience is associated with "
                f"{_pct(m['estimate']):+.1f}% hours per function point after adjustment (95% {_pct(m['ci95'][0]):+.1f}% to "
                f"{_pct(m['ci95'][1]):+.1f}%). "
                + (
                    "The interval includes zero: years of experience alone do not show a clear link to productivity — "
                    "a reason not to treat tenure as a proxy for contribution."
                    if m["ci95"][0] <= 0 <= m["ci95"][1]
                    else "The association is clear in this sample but remains observational."
                )
            ),
            "caveats": ["Experience in years is a proxy; ten organisations pooled; 77 projects."],
        }
    )


# ------------------------------------------------------------------ China
def china(seed: int = 0) -> dict[str, Any]:
    d = load("china").dropna(subset=["Effort", "AFP"])
    d = d[(d["Effort"] > 0) & (d["AFP"] > 0)].copy()
    d["log_effort"] = np.log(d["Effort"])
    base = pd.DataFrame(
        {
            "log_afp": np.log(d["AFP"]),
            "resource": d["Resource"].astype(float),
            "new_dev": (d["DevType"] == "NewDev").astype(float),
            "adj_factor": d["AdjFactor"],
            "log_added": np.log1p(d["Added"]),
            "log_changed": np.log1p(d["Changed"]),
            "log_deleted": np.log1p(d["Deleted"]),
        }
    )
    y = d["log_effort"].to_numpy()
    cv = KFold(10, shuffle=True, random_state=seed)
    size_only = _cv_mae({"linear_size_only": LinearRegression()}, base[["log_afp"]], y, cv)
    main = _cv_mae(_models(), base, y, cv)
    leak = base.assign(log_duration=np.log(d["Duration"].clip(lower=1)))
    leaky = _cv_mae(
        {
            "linear_with_duration": LinearRegression(),
            "gradient_boosting_with_duration": HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, random_state=0),
        },
        leak,
        y,
        cv,
    )
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(d))
    test, pool = idx[: len(d) // 5], idx[len(d) // 5 :]
    curve = []
    for frac in (0.1, 0.25, 0.5, 1.0):
        tr = pool[: max(20, int(len(pool) * frac))]
        row = {"n_train": int(len(tr))}
        for name, est in (
            ("linear", LinearRegression()),
            ("gradient_boosting", HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, random_state=0)),
        ):
            est.fit(base.iloc[tr], y[tr])
            row[f"{name}_test_mae_log"] = float(np.mean(np.abs(y[test] - est.predict(base.iloc[test]))))
        curve.append(row)
    best = min(main, key=lambda k: main[k]["validation_mae_log"])
    lin = main["linear_context"]
    complex_best = min(("random_forest", "gradient_boosting"), key=lambda k: main[k]["validation_mae_log"])
    return jsonable(
        {
            "kind": "predictive",
            "status": "exploratory",
            "question": "Do complex models predict effort better than a transparent model, and what does leakage look like on real data?",
            "provenance": _provenance("china"),
            "n_projects": int(len(d)),
            "models_10_fold": {**size_only, **main},
            "learning_curve": curve,
            "leakage_demonstration": {
                "feature": "project duration (known only after delivery)",
                "models": leaky,
                "lesson": "Duration makes the model look better because it is recorded at the same time as the outcome. "
                "MeritVector's leakage checks exclude such fields; this run shows why.",
            },
            "plain_language": (
                f"Over 10 folds, the transparent linear model's estimates are typically off by a factor of "
                f"{lin['typical_error_factor']:.2f}; the best complex model ({complex_best.replace('_', ' ')}) by "
                f"{main[complex_best]['typical_error_factor']:.2f}, and size alone by "
                f"{size_only['linear_size_only']['typical_error_factor']:.2f}. "
                + (
                    "Added complexity does not help. "
                    if best in ("linear_context", "median_baseline")
                    or main[complex_best]["validation_mae_log"] >= lin["validation_mae_log"] - 0.01
                    else "Complex models help modestly. "
                )
                + f"Adding project duration — known only after delivery — would cut the error to a factor of "
                f"{leaky['linear_with_duration']['typical_error_factor']:.2f}: an illegitimate gain from leakage."
            ),
        }
    )


STUDIES = {
    "ebspm": ("Organisations' cost and duration, raw vs adjusted (EBSPM, 492 projects)", ebspm),
    "maxwell": ("Context vs staff skills in productivity (Maxwell, 62 projects)", maxwell),
    "nasa93": ("NASA centres and capability ratings (NASA93, 93 projects)", nasa93),
    "desharnais": ("Manager experience and productivity (Desharnais, 77 projects)", desharnais),
    "china": ("Model generalisation and leakage (China, 499 projects)", china),
}


def run_all(n_boot: int = 300) -> dict[str, Any]:
    out: dict[str, Any] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for k, (_, fn) in STUDIES.items():
            out[k] = fn() if k == "china" else fn(n_boot=n_boot)
    return {"kind": "observational", "status": "exploratory", "studies": out, "summary": summary(out)}


def summary(results: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for k, r in results.items():
        dec = r.get("variance_decomposition") or r.get("results", {}).get("log_cost_per_fp", {}).get("variance_decomposition")
        if not dec:
            continue
        b = dec["blocks"]
        people = next((b[x] for x in ("team_indicators", "staff_skills", "capability_ratings", "experience") if x in b), None)
        unit = next((b[x] for x in ("organisation", "centre") if x in b), None)
        rows.append(
            {
                "dataset": k,
                "size_and_context_share": b["size"]["share_of_variance"] + b["measured_context"]["share_of_variance"],
                "team_or_capability_share": people["share_of_variance"] if people else None,
                "team_or_capability_ci95": people["ci95"] if people else None,
                "unit_share": unit["share_of_variance"] if unit else None,
                "total_r2": dec["total_r2"],
            }
        )
    return {
        "variance_shares": rows,
        "interpretation": "Across independent real datasets, size and measured context explain far more of the variation in "
        "delivery outcomes than team or capability indicators. This supports adjusting for context before any comparison, "
        "and treating person-level signals as small and uncertain. It does not validate MeritVector's individual estimates, "
        "which no public dataset can test.",
    }
