"""Build the data snapshot for the GitHub Pages demo (index.html at the repository root).

Runs the repository's own synthetic generator, feature builder and descriptive metrics, then
estimates person-level context effects with the within-person coefficients from
``contextual.within_beta`` plus simple empirical-Bayes shrinkage (a lightweight stand-in for the
mixed-effects model, so the demo can be built without statsmodels), and classifies them with
``contextual.classify``. Hidden ground truth, protected attributes, ratings and promotions are
never read. Everything is synthetic and seeded, so the output is reproducible.

Usage:  python scripts/build_pages_demo.py
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for pkg in ("shared", "analytics", "coordinator"):
    sys.path.insert(0, str(ROOT / "packages" / pkg))

try:  # contextual.py imports statsmodels at module level; the functions used here do not need it.
    import statsmodels.formula.api  # noqa: F401
except ImportError:
    for _name in ("statsmodels", "statsmodels.api", "statsmodels.formula", "statsmodels.formula.api"):
        sys.modules[_name] = types.ModuleType(_name)
    sys.modules["statsmodels"].api = sys.modules["statsmodels.api"]
    sys.modules["statsmodels"].formula = sys.modules["statsmodels.formula"]
    sys.modules["statsmodels.formula"].api = sys.modules["statsmodels.formula.api"]

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from meritvector_analytics.contextual import OUTCOMES, classify, raw_estimates, within_beta  # noqa: E402
from meritvector_analytics.descriptive import employee_metrics, portfolio_trend, project_health, risk_trends  # noqa: E402
from meritvector_analytics.features import build_features, design_matrix  # noqa: E402
from meritvector_analytics.synthetic import generate  # noqa: E402

N_MEETINGS = 12  # sample transcripts for the coordinator page (assistance data only)


def rnd(x: Any, n: int = 2) -> float | None:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    return round(float(x), n)


def person_estimates(m: pd.DataFrame) -> dict[str, dict[str, dict]]:
    """Within-person context adjustment with shrinkage, one entry per employee and outcome."""
    people: dict[str, dict[str, dict]] = {}
    for outcome, meta in OUTCOMES.items():
        d = m.dropna(subset=[outcome]).reset_index(drop=True)
        X = design_matrix(d)
        y = d[outcome].astype(float).to_numpy()
        beta = within_beta(X.to_numpy(), y, d["employee_id"].to_numpy())
        d = d.assign(_res=y - X.to_numpy() @ beta)
        g = d.groupby("employee_id")
        effect = meta["sign"] * (g["_res"].mean() - d["_res"].mean())
        n = g.size()
        sd_within = np.sqrt(np.average(g["_res"].var().fillna(0), weights=n))
        se = sd_within / np.sqrt(n)
        tau2 = max(float(effect.var() - np.mean(se**2)), 1e-6)
        est = effect * tau2 / (tau2 + se**2)
        se_post = np.sqrt(tau2 * se**2 / (tau2 + se**2))
        e = pd.DataFrame({"adjusted_estimate": est, "ci_low": est - 1.96 * se_post, "ci_high": est + 1.96 * se_post, "n": n})
        e = e.reset_index()
        e["conclusion"] = classify(e, outcome)
        raw = raw_estimates(m, outcome).set_index("employee_id")
        for row in e.itertuples():
            people.setdefault(row.employee_id, {})[outcome] = {
                "raw": rnd(raw.loc[row.employee_id, "raw_estimate"]),
                "adj": rnd(row.adjusted_estimate),
                "lo": rnd(row.ci_low),
                "hi": rnd(row.ci_high),
                "n": int(row.n),
                "c": row.conclusion,
            }
    return people


def context_coefficients(m: pd.DataFrame) -> dict[str, dict]:
    out = {}
    for outcome, meta in OUTCOMES.items():
        d = m.dropna(subset=[outcome]).reset_index(drop=True)
        X = design_matrix(d)
        beta = within_beta(X.to_numpy(), d[outcome].astype(float).to_numpy(), d["employee_id"].to_numpy())
        out[outcome] = {
            "label": meta["label"],
            "unit": meta["unit"],
            "terms": [{"term": t, "b": rnd(b, 3)} for t, b in zip(X.columns, beta, strict=True)],
        }
    return out


def projects_table(ds, m: pd.DataFrame, health: pd.DataFrame) -> list[dict]:
    cols = ["project_id", "health", "open_risks", "open_high_risks", "open_dependencies"]
    p = ds.projects.merge(health[cols], on="project_id")
    agg = m.groupby("project_id").agg(
        ms=("on_time", "size"), on_time=("on_time", "mean"), sv=("schedule_variance_pct", "mean"), q=("quality_score", "mean")
    )
    p = p.merge(agg, left_on="project_id", right_index=True, how="left")
    names = ds.employees.set_index("employee_id")["display_name"].to_dict()
    return [
        {
            "id": x.project_id,
            "name": x.name,
            "bu": x.business_unit,
            "kind": x.kind,
            "status": x.status,
            "lead": names.get(x.lead_employee_id, ""),
            "start": str(x.start_date)[:10],
            "end": str(x.planned_end)[:10],
            "cx": int(x.technical_complexity),
            "deps": int(x.dependency_count),
            "rc": rnd(x.resource_constraint),
            "team": int(x.team_size),
            "env": x.environment,
            "mat": x.maturity,
            "health": x.health,
            "risks": int(x.open_risks),
            "hr": int(x.open_high_risks),
            "opdeps": int(x.open_dependencies),
            "ms": 0 if pd.isna(x.ms) else int(x.ms),
            "ot": rnd(x.on_time, 3),
            "sv": rnd(x.sv, 1),
            "q": rnd(x.q),
        }
        for x in p.itertuples()
    ]


def employees_table(ds, fs, people: dict) -> list[dict]:
    em = employee_metrics(fs).set_index("employee_id")
    rows = []
    for e in ds.employees.itertuples():
        x = em.loc[e.employee_id] if e.employee_id in em.index else None
        has = x is not None and not pd.isna(x.milestones)
        rows.append(
            {
                "id": e.employee_id,
                "mgr": e.manager_id if isinstance(e.manager_id, str) else None,
                "name": e.display_name,
                "fam": e.job_family,
                "lvl": e.level,
                "bu": e.business_unit,
                "joined": str(e.joined_on)[:10],
                "ms": int(x.milestones) if has else 0,
                "ot": rnd(x.on_time_rate, 3) if has else None,
                "cx": rnd(x.mean_complexity) if has else None,
                "rcx": rnd(x.mean_resource_constraint) if has else None,
                "est": people.get(e.employee_id, {}),
            }
        )
    # Alphabetical only: the product never sorts or ranks people by performance.
    return sorted(rows, key=lambda r: r["name"])


def pick_personas(emps: list[dict]) -> dict[str, str]:
    """Like the API's demo personas: a low raw on-time rate but above context expectation, plus their manager."""
    cand = [
        e
        for e in emps
        if e["est"].get("schedule_variance_pct", {}).get("c") == "above_context_expectation" and e["ot"] is not None and e["mgr"]
    ]
    cand.sort(key=lambda e: (e["ot"], -e["est"]["schedule_variance_pct"]["adj"]))
    return {"employee": cand[0]["id"], "manager": cand[0]["mgr"]}


def main() -> None:
    ds = generate()
    fs = build_features(ds.events, ds.employees, ds.config.as_of)
    m = fs.milestones
    as_of = str(ds.config.as_of)
    health = project_health(ds.projects, ds.milestones, ds.risks, ds.dependencies, as_of)
    people = person_estimates(m)
    emps = employees_table(ds, fs, people)
    conclusions: dict[str, dict[str, int]] = {}
    for est in people.values():
        for outcome, v in est.items():
            conclusions.setdefault(outcome, {}).setdefault(v["c"], 0)
            conclusions[outcome][v["c"]] += 1
    meetings = ds.meetings[ds.meetings["transcript"].notna()].sort_values("scheduled_at", ascending=False).head(N_MEETINGS)
    out = {
        "as_of": as_of,
        "seed": ds.config.seed,
        "tenant": ds.config.tenant_name,
        "counts": {
            "employees": len(ds.employees),
            "projects": len(ds.projects),
            "modelled_milestones": len(m),
            "censored_excluded": int(fs.censored_excluded),
        },
        "trend": [
            {"q": str(x.quarter), "n": int(x.milestones), "on_time": rnd(x.on_time_rate, 3), "sv": rnd(x.mean_schedule_variance_pct, 1)}
            for x in portfolio_trend(m).itertuples()
        ],
        "health": {k: int(v) for k, v in health["health"].value_counts().items()},
        "risk_trend": [{k: (v if k == "month" else int(v)) for k, v in row.items()} for row in risk_trends(fs.events).to_dict("records")],
        "projects": projects_table(ds, m, health),
        "context": context_coefficients(m),
        "employees": emps,
        "personas": pick_personas(emps),
        "conclusions": conclusions,
        "meetings": [{"title": x.title, "when": str(x.scheduled_at)[:16], "transcript": x.transcript} for x in meetings.itertuples()],
    }
    page = ROOT / "index.html"
    html = page.read_text()
    start = '<script id="mvdata" type="application/json">'
    a = html.index(start) + len(start)
    b = html.index("</script>", a)
    data = json.dumps(out, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    page.write_text(html[:a] + "\n" + data + "\n" + html[b:])
    print(f"Wrote demo data ({len(data) // 1024} KB) into {page.name}")


if __name__ == "__main__":
    main()
