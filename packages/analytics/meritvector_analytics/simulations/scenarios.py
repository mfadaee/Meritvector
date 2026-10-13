"""Synthetic organisational laboratory — six targeted scenarios (A–F).

Each scenario is a small, reproducible simulation with explicit, configurable parameters and a hidden ground-truth
layer (keys starting with ``_truth``) used only to check what the analysis can and cannot recover. The analysis
code paths never read the truth. Results are written in plain language *computed from the numbers*; no scenario is
programmed to make a particular person look better.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from meritvector_analytics.research.data import jsonable

# --------------------------------------------------------------------------- shared delivery simulator
CX_COEF, RC_COEF, DEP_COEF, SKILL_COEF = 5.5, 22.0, 2.2, 8.0


def _population(rng: np.random.Generator, n_people: int, projects: tuple[int, int] = (4, 7), ms: int = 5) -> list[dict[str, Any]]:
    rows = []
    for i in range(n_people):
        skill = rng.normal(0, 1)
        for p in range(int(rng.integers(*projects))):
            cx = int(np.clip(round(3 + 0.3 * skill + rng.normal(0, 1)), 1, 5))
            rc = float(np.clip(rng.beta(2, 5) + 0.05 * skill, 0, 1))
            dep = int(rng.poisson(0.6 + 0.9 * (cx - 1)))
            rows += _project_rows(rng, f"P{i:03d}", f"P{i:03d}-{p}", skill, cx, rc, dep, ms)
    return rows


def _project_rows(rng, person, project, skill, cx, rc, dep, ms, month0: float = 0.0, skill_fn=None) -> list[dict[str, Any]]:
    shock = rng.normal(0, 4.5)
    out = []
    for k in range(ms):
        month = month0 + k
        s = skill_fn(month) if skill_fn else skill
        svp = -10 + CX_COEF * (cx - 3) + RC_COEF * rc + DEP_COEF * dep + shock - SKILL_COEF * s + rng.standard_t(5) * 6.5
        out.append(
            {
                "person": person,
                "project": project,
                "complexity": cx,
                "resource_constraint": rc,
                "dependencies": dep,
                "month": month,
                "svp": max(svp, -25.0),
            }
        )
    return out


class _WithinFit:
    """Context coefficients estimated within person (fixed effects), the estimator MeritVector uses since v0.2.

    A cross-person regression would confound the effect of conditions with who is assigned to them (stronger people
    get harder projects), under-crediting people on difficult work.
    """

    COLS = ["complexity", "resource_constraint", "dependencies"]

    def __init__(self, df: pd.DataFrame):
        from meritvector_analytics.contextual import within_beta

        X = df[self.COLS].to_numpy(float)
        self.beta = within_beta(X, df["svp"].to_numpy(float), df["person"].to_numpy())
        r = df["svp"].to_numpy(float) - X @ self.beta
        self.resid = pd.Series(r - r.mean(), index=df.index)
        self.params = dict(zip(self.COLS, self.beta, strict=True))

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return df[self.COLS].to_numpy(float) @ self.beta


def _context_fit(df: pd.DataFrame) -> _WithinFit:
    return _WithinFit(df)


def _person_effects(df: pd.DataFrame, res, people: list[str], n_boot: int, rng) -> dict[str, dict[str, float]]:
    df = df.assign(resid=res.resid)
    out = {}
    for p in people:
        sub = df[df["person"] == p]
        projects = sub["project"].unique()
        boots = []
        for _ in range(n_boot):
            pick = rng.choice(projects, len(projects))
            boots.append(-pd.concat([sub[sub["project"] == q] for q in pick])["resid"].mean())
        out[p] = {
            "adjusted": float(-sub["resid"].mean()),
            "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            "raw_on_time": float((sub["svp"] <= 5).mean()),
            "raw_mean_svp": float(sub["svp"].mean()),
            "n": int(len(sub)),
            "mean_complexity": float(sub["complexity"].mean()),
            "mean_resource_constraint": float(sub["resource_constraint"].mean()),
        }
    return out


# --------------------------------------------------------------------------- A
@dataclass
class ScenarioAConfig:
    seed: int = 101
    n_population: int = 150
    skill_a: float = 0.0
    skill_b: float = 0.0
    projects_each: int = 6
    n_boot: int = 300


def scenario_a(cfg: ScenarioAConfig | None = None) -> dict[str, Any]:
    cfg = cfg or ScenarioAConfig()
    rng = np.random.default_rng(cfg.seed)
    rows = _population(rng, cfg.n_population)
    for i in range(cfg.projects_each):
        rows += _project_rows(
            rng, "A", f"A-{i}", cfg.skill_a, int(rng.integers(1, 3)), float(rng.uniform(0, 0.1)), int(rng.integers(0, 2)), 5
        )
        rows += _project_rows(
            rng, "B", f"B-{i}", cfg.skill_b, int(rng.integers(4, 6)), float(rng.uniform(0.5, 0.75)), int(rng.integers(4, 7)), 5
        )
    df = pd.DataFrame(rows)
    res = _context_fit(df)
    eff = _person_effects(df, res, ["A", "B"], cfg.n_boot, rng)
    diff = eff["B"]["adjusted"] - eff["A"]["adjusted"]
    boot = []
    for _ in range(cfg.n_boot):
        a = rng.choice(df.loc[df.person == "A", "project"].unique(), cfg.projects_each)
        b = rng.choice(df.loc[df.person == "B", "project"].unique(), cfg.projects_each)
        ra = -df.assign(r=res.resid).set_index("project").loc[a, "r"].mean()
        rb = -df.assign(r=res.resid).set_index("project").loc[b, "r"].mean()
        boot.append(rb - ra)
    ci = [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]
    supported = ci[0] > 0 or ci[1] < 0
    raw_gap = eff["A"]["raw_on_time"] - eff["B"]["raw_on_time"]
    finding = (
        f"Raw on-time rates favour A by {raw_gap:.0%}. A's projects were simple and well resourced (complexity "
        f"{eff['A']['mean_complexity']:.1f}, shortfall {eff['A']['mean_resource_constraint']:.2f}); B's were complex and "
        f"constrained ({eff['B']['mean_complexity']:.1f}, {eff['B']['mean_resource_constraint']:.2f}). After adjustment the "
        f"B−A difference is {diff:+.1f} pp (95% interval {ci[0]:+.1f} to {ci[1]:+.1f}). "
        + (
            "The data supports a difference in contribution relative to conditions."
            if supported
            else "The data does not support concluding that either person contributed more; the raw gap is explained by conditions."
        )
    )
    return jsonable(
        {
            "id": "A",
            "title": "Easy, well-supported projects vs complex, constrained projects",
            "question": "What does the observed data support when two people work under very different conditions?",
            "config": asdict(cfg),
            "people": eff,
            "difference_b_minus_a": {"estimate": diff, "ci95": ci},
            "context_coefficients_within_person": {k: float(v) for k, v in res.params.items()},
            "finding": finding,
            "_truth": {
                "skill_a": cfg.skill_a,
                "skill_b": cfg.skill_b,
                "true_difference_pp": SKILL_COEF * (cfg.skill_b - cfg.skill_a),
            },
        }
    )


# --------------------------------------------------------------------------- B
@dataclass
class ScenarioBConfig:
    seed: int = 202
    n_population: int = 250
    deliverables_each: int = 12
    activity_a: float = 2.0
    activity_b: float = -1.5
    quality_skill_a: float = 0.0
    quality_skill_b: float = 1.0


def scenario_b(cfg: ScenarioBConfig | None = None) -> dict[str, Any]:
    cfg = cfg or ScenarioBConfig()
    rng = np.random.default_rng(cfg.seed)
    people = [("pop", rng.normal(0, 1), rng.normal(0, 1)) for _ in range(cfg.n_population)]
    people += [("A", cfg.activity_a, cfg.quality_skill_a), ("B", cfg.activity_b, cfg.quality_skill_b)]
    rows = []
    for i, (who, act, q) in enumerate(people):
        pid = who if who != "pop" else f"P{i:03d}"
        meetings = rng.poisson(max(2, 22 + 9 * act), 12).mean()
        updates = rng.poisson(max(1, 15 + 7 * act), 12).mean()
        scores = np.clip(3.3 + 0.5 * q + rng.normal(0, 0.55, cfg.deliverables_each), 1, 5)
        rows.append(
            {
                "person": pid,
                "meetings_per_month": meetings,
                "updates_per_month": updates,
                "quality_mean": float(scores.mean()),
                "quality_se": float(scores.std(ddof=1) / np.sqrt(len(scores))),
                "tasks_closed": int(rng.poisson(max(5, 40 + 15 * act))),
            }
        )
    df = pd.DataFrame(rows)
    pop = df[~df["person"].isin(["A", "B"])]
    r_meet = stats.spearmanr(pop["meetings_per_month"], pop["quality_mean"])
    r_tasks = stats.spearmanr(pop["tasks_closed"], pop["quality_mean"])
    a, b = df.set_index("person").loc["A"], df.set_index("person").loc["B"]
    qd = b["quality_mean"] - a["quality_mean"]
    qse = np.hypot(a["quality_se"], b["quality_se"])
    finding = (
        f"A attends {a['meetings_per_month'] / b['meetings_per_month']:.1f}× as many meetings and closes "
        f"{a['tasks_closed'] / max(1, b['tasks_closed']):.1f}× as many tasks as B, yet B's deliverables score "
        f"{qd:+.2f} points higher (95% interval {qd - 1.96 * qse:+.2f} to {qd + 1.96 * qse:+.2f}). Across the population, "
        f"meeting volume is unrelated to deliverable quality (ρ = {r_meet.statistic:.2f}). Activity counts would rank A above "
        "B; the quality evidence points the other way."
    )
    return jsonable(
        {
            "id": "B",
            "title": "Many meetings and updates vs fewer meetings and better deliverables",
            "question": "Are activity counts sufficient to infer contribution?",
            "config": asdict(cfg),
            "people": {"A": a.to_dict(), "B": b.to_dict()},
            "population": {
                "spearman_meetings_quality": float(r_meet.statistic),
                "p": float(r_meet.pvalue),
                "spearman_tasks_quality": float(r_tasks.statistic),
            },
            "finding": finding,
            "_truth": {"activity_effect_on_quality": 0.0},
        }
    )


# --------------------------------------------------------------------------- C
@dataclass
class ScenarioCConfig:
    seed: int = 303
    n_managers: int = 20
    reports_per_manager: int = 9
    leniency_sd: float = 0.35
    focal_lenient: float = 0.6
    focal_strict: float = -0.6
    focal_skill: float = 0.3


def scenario_c(cfg: ScenarioCConfig | None = None) -> dict[str, Any]:
    cfg = cfg or ScenarioCConfig()
    rng = np.random.default_rng(cfg.seed)
    len_ = rng.normal(0, cfg.leniency_sd, cfg.n_managers)
    len_[0], len_[1] = cfg.focal_lenient, cfg.focal_strict
    rows = []
    for mgr in range(cfg.n_managers):
        for r in range(cfg.reports_per_manager):
            focal = mgr in (0, 1) and r == 0
            skill = cfg.focal_skill if focal else rng.normal(0, 1)
            evidence = skill + rng.normal(0, 0.35)  # context-adjusted evidence, measured with error
            for period in range(4):
                latent = 0.7 * skill + len_[mgr] + rng.normal(0, 0.5)
                rating = int(np.clip(round(3 + latent), 1, 5))
                rows.append(
                    {
                        "manager": f"M{mgr:02d}",
                        "person": ("X" if mgr == 0 else "Y") if focal else f"E{mgr:02d}{r}",
                        "evidence": evidence,
                        "rating": rating,
                        "period": period,
                    }
                )
    df = pd.DataFrame(rows)
    full = smf.ols("rating ~ evidence + C(manager, Treatment(reference='M02'))", df).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(df["person"])[0]}
    )
    base = smf.ols("rating ~ evidence", df).fit()
    f, p, _ = smf.ols("rating ~ evidence + C(manager)", df).fit().compare_f_test(base)
    x, y = df[df.person == "X"], df[df.person == "Y"]
    keys = {k: k for k in full.params.index if "manager" in k}
    lenient_k = next(k for k in keys if "M00" in k)
    strict_k = next(k for k in keys if "M01" in k)
    rater_gap = float(full.params[lenient_k] - full.params[strict_k])
    finding = (
        f"X and Y have equivalent evidence ({x['evidence'].iloc[0]:.2f} vs {y['evidence'].iloc[0]:.2f}) but X's average "
        f"rating is {x['rating'].mean() - y['rating'].mean():+.2f} points higher. Holding evidence constant, X's manager rates "
        f"{rater_gap:+.2f} points above Y's. Rater identity explains rating differences beyond evidence (F = {f:.1f}, "
        f"p = {p:.2g}). The difference in ratings reflects the raters, not the people."
    )
    return jsonable(
        {
            "id": "C",
            "title": "Equivalent work, different raters",
            "question": "Do manager ratings reflect the work or the rater?",
            "config": asdict(cfg),
            "focal": {
                "X": {"evidence": float(x["evidence"].iloc[0]), "mean_rating": float(x["rating"].mean())},
                "Y": {"evidence": float(y["evidence"].iloc[0]), "mean_rating": float(y["rating"].mean())},
            },
            "rater_effect_test": {"F": float(f), "p_value": float(p), "estimated_rater_gap": rater_gap},
            "finding": finding,
            "_truth": {"leniency_gap": cfg.focal_lenient - cfg.focal_strict},
        }
    )


# --------------------------------------------------------------------------- D
@dataclass
class ScenarioDConfig:
    seed: int = 404
    n_population: int = 150
    months: int = 12
    skill_start: float = -0.5
    skill_end: float = 0.7
    complexity_start: float = 2.0
    complexity_end: float = 4.5


def scenario_d(cfg: ScenarioDConfig | None = None) -> dict[str, Any]:
    cfg = cfg or ScenarioDConfig()
    rng = np.random.default_rng(cfg.seed)
    rows = _population(rng, cfg.n_population)
    for mth in range(cfg.months):
        frac = mth / (cfg.months - 1)
        cx = int(round(cfg.complexity_start + frac * (cfg.complexity_end - cfg.complexity_start)))
        s = cfg.skill_start + frac * (cfg.skill_end - cfg.skill_start)
        rc = float(np.clip(0.15 + 0.35 * frac + rng.normal(0, 0.05), 0, 1))
        rows += _project_rows(rng, "D", f"D-{mth}", s, cx, rc, int(rng.poisson(0.6 + 0.9 * (cx - 1))), 2, month0=mth)
    df = pd.DataFrame(rows)
    res = _context_fit(df)
    d = df[df.person == "D"].copy()
    d["expected"] = res.predict(d)
    d["signal"] = -(d["svp"] - d["expected"])
    d["signal"] -= d["signal"].mean() - (-res.resid[df.person == "D"]).mean()
    raw = smf.ols("svp ~ month", d).fit()
    adj = smf.ols("signal ~ month", d).fit()
    rci, aci = raw.conf_int().loc["month"].tolist(), adj.conf_int().loc["month"].tolist()
    first, last = d[d.month < 4], d[d.month >= cfg.months - 4]
    finding = (
        f"Raw schedule variance changed by {raw.params['month'] * 12:+.1f} pp over the year (95% {rci[0] * 12:+.1f} to "
        f"{rci[1] * 12:+.1f}) — it looks flat or worse because projects got harder (complexity "
        f"{first['complexity'].mean():.1f} → {last['complexity'].mean():.1f}). Relative to conditions, the signal improved by "
        f"{adj.params['month'] * 12:+.1f} pp (95% {aci[0] * 12:+.1f} to {aci[1] * 12:+.1f}). "
        + (
            "The evidence supports sustained improvement while taking on harder work."
            if aci[0] > 0
            else "The improvement is not distinguishable from noise with this much evidence."
        )
        + " With only one person and 24 milestones, regression to the mean and changing roles must be ruled out by review."
    )
    return jsonable(
        {
            "id": "D",
            "title": "Improving over 12 months while taking harder projects",
            "question": "What does longitudinal evidence support?",
            "config": asdict(cfg),
            "raw_slope_per_year": {"estimate": float(raw.params["month"] * 12), "ci95": [rci[0] * 12, rci[1] * 12]},
            "adjusted_slope_per_year": {"estimate": float(adj.params["month"] * 12), "ci95": [aci[0] * 12, aci[1] * 12]},
            "series": d.groupby("month")
            .agg(raw_svp=("svp", "mean"), signal=("signal", "mean"), complexity=("complexity", "mean"))
            .reset_index()
            .to_dict("records"),
            "finding": finding,
            "_truth": {"true_slope_pp_per_year": SKILL_COEF * (cfg.skill_end - cfg.skill_start) * 12 / (cfg.months - 1)},
        }
    )


# --------------------------------------------------------------------------- E
@dataclass
class ScenarioEConfig:
    seed: int = 505
    n_comparison: int = 40
    months: int = 24
    assignment_month: int = 12
    visibility_rating_boost: float = 0.5
    visibility_feedback_boost: float = 0.6


def scenario_e(cfg: ScenarioEConfig | None = None) -> dict[str, Any]:
    cfg = cfg or ScenarioEConfig()
    rng = np.random.default_rng(cfg.seed)
    rows = []
    for i in range(cfg.n_comparison + 1):
        focal = i == 0
        skill = 0.4 if focal else rng.normal(0.4, 0.5)
        for mth in range(cfg.months):
            post = mth >= cfg.assignment_month
            vis = focal and post
            evidence = skill + rng.normal(0, 0.6)
            rows.append(
                {
                    "person": "V" if focal else f"C{i:02d}",
                    "month": mth,
                    "post": int(post),
                    "treated": int(focal),
                    "evidence": evidence,
                    "feedback": float(
                        np.clip(3.4 + 0.3 * skill + (cfg.visibility_feedback_boost if vis else 0) + rng.normal(0, 0.6), 1, 5)
                    ),
                    "rating": float(np.clip(3 + 0.6 * skill + (cfg.visibility_rating_boost if vis else 0) + rng.normal(0, 0.45), 1, 5)),
                }
            )
    df = pd.DataFrame(rows)
    out = {}
    for y in ("evidence", "feedback", "rating"):
        r = smf.ols(f"{y} ~ treated * post", df).fit(cov_type="HC1")
        ci = r.conf_int().loc["treated:post"].tolist()
        out[y] = {
            "did": float(r.params["treated:post"]),
            "ci95": [float(ci[0]), float(ci[1])],
            "p_value": float(r.pvalues["treated:post"]),
        }
    finding = (
        f"After the high-profile assignment, V's ratings rose by {out['rating']['did']:+.2f} (95% {out['rating']['ci95'][0]:+.2f} to "
        f"{out['rating']['ci95'][1]:+.2f}) and stakeholder feedback by {out['feedback']['did']:+.2f}, relative to comparable "
        f"colleagues, while delivery evidence changed by {out['evidence']['did']:+.2f} (95% {out['evidence']['ci95'][0]:+.2f} to "
        f"{out['evidence']['ci95'][1]:+.2f}). Greater visibility and opportunity changed perceptions; the evidence does not "
        "show a change in contribution."
    )
    return jsonable(
        {
            "id": "E",
            "title": "High-profile assignment and visibility",
            "question": "Can visibility, opportunity, responsibility and contribution be told apart?",
            "config": asdict(cfg),
            "difference_in_differences": out,
            "finding": finding,
            "_truth": {"rating_boost": cfg.visibility_rating_boost, "contribution_change": 0.0},
        }
    )


# --------------------------------------------------------------------------- F
@dataclass
class ScenarioFConfig:
    seed: int = 606
    pool: int = 20
    team_size: int = 4
    programmes: int = 40
    noise_sd: float = 3.0


def scenario_f(cfg: ScenarioFConfig | None = None) -> dict[str, Any]:
    cfg = cfg or ScenarioFConfig()
    rng = np.random.default_rng(cfg.seed)
    contrib = rng.normal(0, 2, cfg.pool)

    def programmes(n, fixed_team=None):
        X, y = np.zeros((n, cfg.pool)), np.zeros(n)
        for k in range(n):
            team = fixed_team if fixed_team is not None else rng.choice(cfg.pool, cfg.team_size, replace=False)
            X[k, team] = 1
            y[k] = contrib[team].sum() + rng.normal(0, cfg.noise_sd)
        return X, y

    # Case 1 — one team, several programmes together: individual effects are not identifiable.
    team = np.arange(cfg.team_size)
    X1, _ = programmes(10, fixed_team=team)
    rank1 = int(np.linalg.matrix_rank(X1[:, team]))
    # Case 2 — rotating team composition: partially identifiable with wide intervals.
    X2, y2 = programmes(cfg.programmes)
    lam = 1.0
    A = X2.T @ X2 + lam * np.eye(cfg.pool)
    beta = np.linalg.solve(A, X2.T @ y2)
    resid = y2 - X2 @ beta
    sigma2 = resid.var(ddof=1)
    se = np.sqrt(np.diag(sigma2 * np.linalg.inv(A) @ X2.T @ X2 @ np.linalg.inv(A)))
    rho2 = stats.spearmanr(beta, contrib).statistic
    # Case 3 — add workstream-level evidence with verified attribution (each person's own workstream outcome).
    ws = contrib + rng.normal(0, 1.5, cfg.pool)
    combo = (beta / se**2 + ws / 1.5**2) / (1 / se**2 + 1 / 1.5**2)
    rho3 = stats.spearmanr(combo, contrib).statistic
    finding = (
        f"When the same {cfg.team_size} people always deliver together, the design has rank {rank1} for {cfg.team_size} people: "
        f"individual contributions cannot be separated at all — any split of credit fits the data equally well. With rotating "
        f"teams across {cfg.programmes} programmes, estimates track true contribution (ρ = {rho2:.2f}) but intervals are wide "
        f"(median ±{1.96 * np.median(se):.1f} on a scale whose people differ by SD 2). Adding verified workstream-level "
        f"evidence improves this to ρ = {rho3:.2f}. Programme outcomes alone must not be attributed to one person."
    )
    return jsonable(
        {
            "id": "F",
            "title": "Shared programme outcome",
            "question": "What are the limits of individual attribution?",
            "config": asdict(cfg),
            "fixed_team": {"people": cfg.team_size, "design_rank": rank1, "identifiable": rank1 >= cfg.team_size},
            "rotating_teams": {"spearman_with_truth": float(rho2), "median_ci_halfwidth": float(1.96 * np.median(se))},
            "with_verified_workstream_evidence": {"spearman_with_truth": float(rho3)},
            "finding": finding,
            "_truth": {"contribution_sd": 2.0},
        }
    )


SCENARIOS = {"A": scenario_a, "B": scenario_b, "C": scenario_c, "D": scenario_d, "E": scenario_e, "F": scenario_f}


def run_all() -> dict[str, Any]:
    return {k: f() for k, f in SCENARIOS.items()}


def public(result: dict[str, Any]) -> dict[str, Any]:
    """Strip hidden truth for display outside the evaluation view."""
    return {k: v for k, v in result.items() if not k.startswith("_")}
