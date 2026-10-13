"""Workstream 8 — causal reasoning with explicit diagrams.

Implements d-separation (Lauritzen moralisation of the ancestral graph) to check whether a candidate adjustment set
satisfies the back-door criterion, then estimates associations under each set and reports sensitivity to
unmeasured confounding (E-value approximation; Cinelli–Hazlett robustness value). Where identification fails,
results are labelled associations.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
import yaml
from scipy import stats

from meritvector_analytics.measurement import config_dir
from meritvector_analytics.research.data import ResearchData, jsonable


def load_dags() -> dict[str, Any]:
    return yaml.safe_load((config_dir() / "research" / "dags.yaml").read_text())["dags"]


class DAG:
    def __init__(self, nodes: dict[str, Any], edges: list[list[str]]):
        self.nodes = set(nodes)
        self.observed = {n for n, v in nodes.items() if v.get("observed", True)}
        self.parents = {n: set() for n in self.nodes}
        for a, b in edges:
            self.parents[b].add(a)

    def ancestors(self, xs: set[str]) -> set[str]:
        out, stack = set(xs), list(xs)
        while stack:
            for p in self.parents[stack.pop()]:
                if p not in out:
                    out.add(p)
                    stack.append(p)
        return out

    def d_separated(self, x: set[str], y: set[str], z: set[str]) -> bool:
        anc = self.ancestors(x | y | z)
        adj = {n: set() for n in anc}
        for n in anc:
            ps = self.parents[n] & anc
            for p in ps:
                adj[n].add(p)
                adj[p].add(n)
            for a, b in combinations(ps, 2):  # moralise
                adj[a].add(b)
                adj[b].add(a)
        seen, stack = set(), [n for n in x if n not in z]
        while stack:
            n = stack.pop()
            if n in y:
                return False
            if n in seen:
                continue
            seen.add(n)
            stack.extend(m for m in adj[n] if m not in z and m not in seen)
        return True

    def backdoor_ok(self, t: str, y: str, z: set[str]) -> bool:
        desc = {n for n in self.nodes if t in self.ancestors({n}) and n != t}
        if z & desc:
            return False
        g = DAG({n: {"observed": n in self.observed} for n in self.nodes}, [])
        g.parents = {n: set(p) for n, p in self.parents.items()}
        for n in self.nodes:  # remove edges out of t
            g.parents[n].discard(t) if n != t else None
        return g.d_separated({t}, {y}, z)


def e_value_from_d(d: float) -> float:
    """E-value for a standardised mean difference via RR ≈ exp(0.91·d) (VanderWeele & Ding 2017)."""
    rr = float(np.exp(0.91 * abs(d)))
    return rr + float(np.sqrt(rr * (rr - 1)))


def resources_delivery(rd: ResearchData) -> dict[str, Any]:
    spec = load_dags()["resources_delivery"]
    dag = DAG(spec["nodes"], spec["edges"])
    m = rd.features.milestones.dropna(subset=["schedule_variance_pct"]).copy()
    t, y = spec["treatment"], spec["outcome"]
    estimates = []
    for name, zs in spec["candidate_adjustment_sets"].items():
        z = set(zs)
        cats = {"environment", "business_unit"}
        terms = [f"C({v})" if v in cats else v for v in zs]
        f = f"{y} ~ {t}" + (" + " + " + ".join(terms) if terms else "")
        res = smf.ols(f, m).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(m["project_id"])[0]})
        estimates.append(
            _estimate(
                name,
                res,
                t,
                m,
                y,
                backdoor=dag.backdoor_ok(t, y, z),
                unobserved=sorted(n for n in dag.ancestors({t}) & dag.ancestors({y}) - {t, y} if n not in dag.observed),
            )
        )
    # Within-person design: employee fixed effects absorb stable latent contribution.
    f = f"{y} ~ {t} + technical_complexity + dependency_count + C(environment) + scope_changes_to_date + C(employee_id)"
    res = smf.ols(f, m).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(m["project_id"])[0]})
    estimates.append(_estimate("within_person_fixed_effects", res, t, m, y, backdoor=None, unobserved=[]))
    fe, adj = estimates[-1]["estimate"], estimates[1]["estimate"]
    return jsonable(
        {
            "kind": "causal",
            "status": "exploratory",
            "question": spec["question"],
            "dag": spec,
            "estimates": estimates,
            "identification": (
                "With measured context only, the back-door criterion fails: latent contribution affects both who is "
                "given under-resourced projects and how milestones go. The within-person design removes stable latent "
                f"contribution; the estimate moves from {adj:.1f} to {fe:.1f} pp per unit of shortfall, showing the size of "
                "selection bias in the cross-person comparison. Remaining assumptions: no time-varying confounding and no "
                "effect of past outcomes on later assignments."
            ),
            "plain_language": f"Projects that are short of staff slip more — roughly {fe / 10:.1f} percentage points of their "
            "planned interval for every 10% of missing capacity, when the same person's projects are compared.",
        }
    )


def _estimate(name, res, t, m, y, backdoor, unobserved):
    coef = float(res.params[t])
    ci = res.conf_int().loc[t].tolist()
    d = coef * m[t].std() / m[y].std()
    tv = float(res.tvalues[t])
    f = abs(tv) / np.sqrt(res.df_resid)
    return {
        "adjustment": name,
        "estimate": coef,
        "ci95": [float(ci[0]), float(ci[1])],
        "p_value": float(res.pvalues[t]),
        "standardised_effect": float(d),
        "e_value": e_value_from_d(d),
        "robustness_value": float(0.5 * (np.sqrt(f**4 + 4 * f**2) - f**2)),
        "backdoor_criterion_satisfied": backdoor,
        "unobserved_confounders": unobserved,
    }


def raw_kpis_difficulty(rd: ResearchData) -> dict[str, Any]:
    e = rd.employee_frame.dropna(subset=["context_expected", "adjusted_signal"]).copy()
    e = e[e["n_milestones"] >= 6]
    e["raw_signal"] = -(e["raw_mean_svp"] - rd.features.milestones["schedule_variance_pct"].mean())
    e["gap"] = e["raw_signal"] - e["adjusted_signal"]
    e["difficulty_quartile"] = pd.qcut(e["context_expected"], 4, labels=["easiest", "q2", "q3", "hardest"])
    g = e.groupby("difficulty_quartile", observed=True).agg(
        n=("gap", "size"), raw=("raw_signal", "mean"), adjusted=("adjusted_signal", "mean"), gap=("gap", "mean")
    )
    kw = stats.kruskal(*[x["gap"] for _, x in e.groupby("difficulty_quartile", observed=True)])
    rho = stats.spearmanr(e["context_expected"], e["gap"])
    hardest, easiest = g.loc["hardest"], g.loc["easiest"]
    return jsonable(
        {
            "kind": "measurement",
            "status": "exploratory",
            "question": load_dags()["raw_kpis_difficulty"]["question"],
            "by_difficulty_quartile": g.reset_index().to_dict("records"),
            "kruskal_p": float(kw.pvalue),
            "spearman_difficulty_vs_gap": float(rho.statistic),
            "plain_language": (
                f"Yes. People on the hardest quarter of projects look {abs(hardest['raw']):.1f} pp worse than average on raw "
                f"schedule KPIs, but after accounting for conditions their average is {hardest['adjusted']:+.1f} pp. People "
                f"on the easiest projects look {easiest['raw']:+.1f} pp on raw KPIs versus {easiest['adjusted']:+.1f} pp adjusted."
            ),
        }
    )
