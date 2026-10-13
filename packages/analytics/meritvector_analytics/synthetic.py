"""Synthetic PMO organisation generator.

EVERY PERSON, PROJECT, MEETING AND NUMBER PRODUCED BY THIS MODULE IS SYNTHETIC.

The generator simulates a programme-management office over 24 months. Outcomes are
produced by a known data-generating process so that the analytics can be evaluated
against hidden ground truth:

* each employee has a latent contribution parameter (``true_contribution``) and a
  growth rate; these are *hidden* and written only to ``ground_truth``;
* project operating conditions (complexity, dependencies, resource constraints,
  scope volatility, delivery environment, maturity) shift outcomes independently of
  the person, and assignment is *not* random — stronger people are somewhat more
  likely to receive harder projects, which is exactly the confounding that makes
  raw metrics misleading;
* activity volume (meetings, e-mails, hours) is driven by an independent
  ``activity_propensity`` and has no causal effect on outcomes;
* historical manager ratings reward raw outcomes, visibility and activity, include
  rater leniency and a deliberate synthetic bias against one protected group, so
  they are a *biased label*, not ground truth.

Only observable records (events, registers, meetings, ratings) are exposed to the
rest of the platform. Hidden parameters must never reach model features; see
``meritvector_shared.FORBIDDEN_MODEL_COLUMNS`` and the leakage checks.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SYNTHETIC_LABEL = "SYNTHETIC — generated for demonstration; not a real person or project"

BUSINESS_UNITS = (
    "Retail Banking",
    "Infrastructure",
    "Digital Products",
    "Corporate Services",
    "Regulatory Programmes",
)

# Business-unit delivery environments differ (hidden fixed effects, in schedule %).
_BU_EFFECT = {
    "Retail Banking": 1.0,
    "Infrastructure": 3.0,
    "Digital Products": -2.0,
    "Corporate Services": -1.0,
    "Regulatory Programmes": 4.0,
}
_ENV_EFFECT = {"internal": 0.0, "customer_facing": 2.5, "regulated": 6.0}
_MATURITY_EFFECT = {"established": 0.0, "greenfield": 4.0}

_FIRST = (
    "Avery", "Jordan", "Riley", "Morgan", "Casey", "Quinn", "Rowan", "Sasha", "Imani", "Kenji",
    "Priya", "Mateo", "Leila", "Tomasz", "Aisha", "Oskar", "Nadia", "Ravi", "Elena", "Kwame",
    "Ingrid", "Diego", "Mei", "Farah", "Lukas", "Amara", "Hiro", "Zara", "Emeka", "Sofia",
    "Arjun", "Noor", "Mikael", "Thandi", "Yusuf", "Clara", "Dev", "Ines", "Bilal", "Freya",
)
_LAST = (
    "Lindqvist", "Okafor", "Moreau", "Tanaka", "Haddad", "Novak", "Reyes", "Mensah", "Kowalski", "Banerjee",
    "Fischer", "Abara", "Castillo", "Sato", "Nkosi", "Petrov", "Duarte", "Iyer", "Varga", "Osei",
    "Holm", "Rahman", "Bianchi", "Kariuki", "Dubois", "Yilmaz", "Larsen", "Mwangi", "Ortiz", "Chen",
    "Brennan", "Aziz", "Kaur", "Svensson", "Adeyemi", "Morita", "Silva", "Jansen", "Nair", "Quispe",
)

_PROJECT_THEMES = (
    "Payments Modernisation", "Data Platform Migration", "Branch Network Refresh", "Customer Portal",
    "Identity & Access Upgrade", "Regulatory Reporting", "Cloud Landing Zone", "CRM Consolidation",
    "Mobile App Release", "Network Resilience", "ERP Upgrade", "Fraud Analytics", "Contact Centre Rebuild",
    "Data Retention Controls", "API Gateway Rollout", "Finance Close Automation", "Vendor Onboarding",
    "Disaster Recovery Uplift", "Analytics Self-Service", "Document Management", "Pricing Engine",
    "Onboarding Journey", "Treasury Platform", "Workplace Tech Refresh",
)

_TEAMS = (
    "Platform Engineering", "Security Architecture", "Procurement", "Legal", "Data Governance",
    "Enterprise Architecture", "Vendor Management", "Change Management", "Finance Systems", "Network Operations",
)

_ARCHETYPE_SHARES = (
    # name, share of PM/TPM population, skill mean, skill sd
    ("difficult_projects_strong", 25 / 270, 1.2, 0.35),
    ("favourable_projects_average", 25 / 270, 0.0, 0.3),
    ("high_activity_weaker_outcomes", 20 / 270, -0.9, 0.35),
    ("low_visibility_strong", 20 / 270, 1.0, 0.35),
    ("improving", 25 / 270, -0.6, 0.35),
    ("resource_constrained", 25 / 270, 0.0, 0.7),
)


@dataclass(frozen=True)
class SyntheticConfig:
    seed: int = 20261013
    tenant_id: str = "synthetic-pmo"
    tenant_name: str = "Synthetic PMO (demo organisation)"
    n_program_managers: int = 30
    n_project_managers: int = 200
    n_technical_pms: int = 70
    months: int = 24
    as_of: date = date(2026, 10, 12)
    late_joiner_share: float = 0.08
    id_prefix: str = "SYN"

    @property
    def start(self) -> date:
        return self.as_of - timedelta(days=round(self.months * 30.44))


@dataclass
class SyntheticDataset:
    """Observable tables plus the controlled and hidden tables, kept apart."""

    config: SyntheticConfig
    employees: pd.DataFrame
    projects: pd.DataFrame
    milestones: pd.DataFrame
    risks: pd.DataFrame
    dependencies: pd.DataFrame
    events: pd.DataFrame
    meetings: pd.DataFrame
    manager_ratings: pd.DataFrame
    promotions: pd.DataFrame
    # Access-controlled: used only for aggregated fairness auditing.
    protected_attributes: pd.DataFrame
    # Hidden: used only to evaluate models. Never stored in the application database.
    ground_truth: pd.DataFrame
    metadata: dict[str, Any] = field(default_factory=dict)

    OBSERVABLE = (
        "employees", "projects", "milestones", "risks", "dependencies", "events",
        "meetings", "manager_ratings", "promotions",
    )

    def write(self, directory: str | Path) -> Path:
        """Write the dataset as CSV/JSONL. Hidden ground truth goes to ``hidden/``."""
        out = Path(directory)
        (out / "hidden").mkdir(parents=True, exist_ok=True)
        (out / "controlled").mkdir(parents=True, exist_ok=True)
        for name in self.OBSERVABLE:
            df = getattr(self, name)
            if name in ("events", "meetings"):
                df.to_json(out / f"{name}.jsonl", orient="records", lines=True, date_format="iso")
            else:
                df.to_csv(out / f"{name}.csv", index=False)
        self.protected_attributes.to_csv(out / "controlled" / "protected_attributes.csv", index=False)
        self.ground_truth.to_csv(out / "hidden" / "ground_truth.csv", index=False)
        (out / "metadata.json").write_text(json.dumps(self.metadata, indent=2, default=str))
        return out


def _sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + np.exp(-x)))


def _ts(d: date, rng: np.random.Generator) -> datetime:
    return datetime.combine(d, time(hour=int(rng.integers(8, 18)), minute=int(rng.integers(0, 60))))


class _Builder:
    def __init__(self, cfg: SyntheticConfig):
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        self.start = cfg.start
        self.as_of = cfg.as_of
        self.total_days = (self.as_of - self.start).days
        self.events: list[dict[str, Any]] = []
        self.milestones: list[dict[str, Any]] = []
        self.risks: list[dict[str, Any]] = []
        self.deps: list[dict[str, Any]] = []
        self.projects: list[dict[str, Any]] = []
        self._event_seq = 0
        self.batch = f"synthetic-{cfg.seed}"

    # ------------------------------------------------------------------ helpers
    def eid(self, prefix: str) -> str:
        self._event_seq += 1
        return f"{self.cfg.id_prefix}-{prefix}-{self._event_seq:07d}"

    def month_index(self, d: date) -> float:
        return (d - self.start).days / 30.44

    def emit(
        self,
        *,
        employee_id: str,
        project_id: str | None,
        when: date,
        source: str,
        category: str,
        ref: str,
        payload: dict[str, Any],
        quality: dict[str, Any] | None = None,
        data_category: str = "assessment_evidence",
        validated: bool = True,
    ) -> None:
        if when > self.as_of:
            return  # nothing observable has happened yet
        raw = json.dumps([employee_id, project_id, str(when), category, ref, payload], sort_keys=True, default=str)
        self.events.append(
            {
                "event_id": self.eid("EV"),
                "tenant_id": self.cfg.tenant_id,
                "employee_id": employee_id,
                "project_id": project_id,
                "occurred_at": _ts(when, self.rng).isoformat(),
                "source_system": source,
                "category": category,
                "data_category": data_category,
                "evidence_ref": ref,
                "quality_indicators": quality or {},
                "provenance": {
                    "connector": f"mock:{source}",
                    "ingest_batch": self.batch,
                    "raw_hash": hashlib.sha256(raw.encode()).hexdigest()[:16],
                    "synthetic": True,
                },
                "validation_status": "validated" if validated else "unvalidated",
                "payload": payload,
            }
        )

    # --------------------------------------------------------------- employees
    def build_employees(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        cfg, rng = self.cfg, self.rng
        n_pgm, n_pm, n_tpm = cfg.n_program_managers, cfg.n_project_managers, cfg.n_technical_pms
        families = ["program_manager"] * n_pgm + ["project_manager"] * n_pm + ["technical_project_manager"] * n_tpm
        n = len(families)
        names: set[str] = set()
        rows, truth, protected = [], [], []

        delivery_idx = list(range(n_pgm, n))
        rng.shuffle(delivery_idx)
        archetype = {i: "general" for i in range(n)}
        cursor = 0
        for name, share, _, _ in _ARCHETYPE_SHARES:
            k = max(1, round(share * len(delivery_idx))) if len(delivery_idx) >= 12 else (1 if cursor < len(delivery_idx) else 0)
            for i in delivery_idx[cursor : cursor + k]:
                archetype[i] = name
            cursor += k
        params = {a[0]: (a[2], a[3]) for a in _ARCHETYPE_SHARES}

        # Programme managers manage delivery staff within their business unit.
        pgm_ids = [f"{cfg.id_prefix}-E{i + 1:04d}" for i in range(n_pgm)]
        pgm_bu = {pid: BUSINESS_UNITS[i % len(BUSINESS_UNITS)] for i, pid in enumerate(pgm_ids)}
        leniency = {pid: float(rng.normal(0, 0.35)) for pid in pgm_ids}
        directors = {bu: f"{cfg.id_prefix}-DIR-{j + 1:02d}" for j, bu in enumerate(BUSINESS_UNITS)}
        for d in directors.values():
            leniency[d] = float(rng.normal(0, 0.35))

        for i, fam in enumerate(families):
            emp_id = f"{cfg.id_prefix}-E{i + 1:04d}"
            while True:
                nm = f"{rng.choice(_FIRST)} {rng.choice(_LAST)}"
                if nm not in names:
                    names.add(nm)
                    break
            arch = archetype[i]
            mu, sd = params.get(arch, (0.0, 1.0))
            skill = float(rng.normal(mu, sd))
            growth = float(rng.normal(0.9, 0.2)) if arch == "improving" else float(rng.normal(0.0, 0.12))
            activity = float(rng.normal(0, 1))
            visibility = float(rng.normal(0, 1))
            if arch == "high_activity_weaker_outcomes":
                activity += 2.0
                visibility += 0.6
            elif arch == "low_visibility_strong":
                activity -= 1.5
                visibility -= 1.3
            if fam == "program_manager":
                bu = pgm_bu[emp_id]
                manager = directors[bu]
                level = "M5" if rng.random() < 0.7 else "M6"
            else:
                manager = pgm_ids[(i - n_pgm) % n_pgm]
                bu = pgm_bu[manager]
                prefix = "T" if fam == "technical_project_manager" else "P"
                level = prefix + str(rng.choice([2, 3, 4], p=[0.35, 0.45, 0.2]))
            late = rng.random() < cfg.late_joiner_share and fam != "program_manager"
            join_day = int(rng.integers(300, 560)) if late else 0
            rows.append(
                {
                    "employee_id": emp_id,
                    "tenant_id": cfg.tenant_id,
                    "display_name": nm,
                    "job_family": fam,
                    "level": level,
                    "business_unit": bu,
                    "manager_id": manager,
                    "joined_on": self.start + timedelta(days=join_day),
                    "is_synthetic": True,
                    "synthetic_label": SYNTHETIC_LABEL,
                }
            )
            truth.append(
                {
                    "employee_id": emp_id,
                    "archetype": arch,
                    "true_contribution": skill,
                    "growth_per_year": growth,
                    "activity_propensity": activity,
                    "visibility": visibility,
                    "rater_leniency": leniency.get(manager, 0.0),
                }
            )
            # Protected group assigned independently of everything else; any outcome
            # gap in manager ratings is therefore synthetic rater bias.
            protected.append({"employee_id": emp_id, "protected_group": "G2" if rng.random() < 0.4 else "G1"})

        self.leniency = leniency
        return pd.DataFrame(rows), pd.DataFrame(truth), pd.DataFrame(protected)

    # ---------------------------------------------------------------- projects
    def _context(self, fam: str, arch: str, skill: float, bu: str, programme: bool) -> dict[str, Any]:
        rng = self.rng
        cx_tilt = {"difficult_projects_strong": 1.4, "favourable_projects_average": -1.4}.get(arch, 0.0)
        rc_tilt = {
            "difficult_projects_strong": 0.9,
            "resource_constrained": 1.8,
            "favourable_projects_average": -1.6,
        }.get(arch, 0.0)
        cx_latent = 0.35 * skill + cx_tilt + (0.5 if fam == "technical_project_manager" else 0.0) + rng.normal(0, 0.9)
        complexity = int(np.clip(round(3 + cx_latent), 1, 5))
        resource_constraint = round(_sigmoid(-1.1 + rc_tilt + 0.15 * skill + rng.normal(0, 0.8)), 2)
        dep_tilt = 1.0 if arch == "difficult_projects_strong" else (-0.5 if arch == "favourable_projects_average" else 0.0)
        dependency_count = int(rng.poisson(max(0.2, 0.6 + 0.9 * (complexity - 1) + dep_tilt)))
        size_band = 3 if programme else int(rng.choice([1, 2, 3], p=[0.4, 0.4, 0.2]))
        team_size = int(3 + rng.poisson(2.5 * size_band))
        env_p = [0.3, 0.3, 0.4] if bu == "Regulatory Programmes" else [0.45, 0.37, 0.18]
        environment = str(rng.choice(["internal", "customer_facing", "regulated"], p=env_p))
        maturity = str(rng.choice(["greenfield", "established"], p=[0.4, 0.6]))
        return {
            "technical_complexity": complexity,
            "dependency_count": dependency_count,
            "resource_constraint": resource_constraint,
            "size_band": size_band,
            "team_size": team_size,
            "environment": environment,
            "maturity": maturity,
        }

    def build_projects(self, employees: pd.DataFrame, truth: pd.DataFrame) -> None:
        rng = self.rng
        tmap = truth.set_index("employee_id")
        pseq = 0
        for emp in employees.itertuples():
            t = tmap.loc[emp.employee_id]
            programme = emp.job_family == "program_manager"
            day = (emp.joined_on - self.start).days + int(rng.integers(0, 60))
            while day < self.total_days - 90:
                pseq += 1
                pid = f"{self.cfg.id_prefix}-P{pseq:04d}"
                duration = int(rng.integers(300, 460)) if programme else int(rng.integers(120, 300))
                ctx = self._context(emp.job_family, t.archetype, t.true_contribution, emp.business_unit, programme)
                theme = _PROJECT_THEMES[pseq % len(_PROJECT_THEMES)]
                name = f"{theme} {'Programme' if programme else 'Project'} {pseq:03d}"
                start = self.start + timedelta(days=day)
                self._simulate_project(pid, name, emp, t, ctx, start, duration, programme)
                day += duration + int(rng.integers(0, 50))

    def _simulate_project(self, pid, name, emp, t, ctx, start: date, duration: int, programme: bool) -> None:
        rng, cfg = self.rng, self.cfg
        lead = emp.employee_id
        planned_end = start + timedelta(days=duration)
        cx, dep, rc = ctx["technical_complexity"], ctx["dependency_count"], ctx["resource_constraint"]
        project_shock = float(rng.normal(0, 4.5))

        def skill_at(d: date) -> float:
            return float(t.true_contribution + t.growth_per_year * self.month_index(d) / 12.0)

        # Kick-off: the PMO complexity assessment records operating conditions.
        self.emit(
            employee_id=lead, project_id=pid, when=start, source="pmo_register", category="complexity_assessment",
            ref=f"PMO-{pid}-CA", payload=dict(ctx, programme=programme),
            quality={"assessor": "pmo_office", "method": "pmo_complexity_rubric_v2"},
        )
        if rc >= 0.4:
            self.emit(
                employee_id=lead, project_id=pid, when=start + timedelta(days=int(rng.integers(3, 30))),
                source="pmo_register", category="resource_limitation", ref=f"PMO-{pid}-RL",
                payload={"resource_constraint": rc, "unfilled_roles": int(round(rc * ctx["team_size"] / 2))},
            )

        # Scope changes arrive during the project (time-varying condition).
        n_scope = int(rng.poisson(0.3 + 0.25 * cx + (0.4 if ctx["maturity"] == "greenfield" else 0.0)))
        scope_days = sorted(int(rng.integers(10, max(11, duration - 10))) for _ in range(n_scope))
        for k, sd in enumerate(scope_days):
            self.emit(
                employee_id=lead, project_id=pid, when=start + timedelta(days=sd), source="jira",
                category="scope_change_approved", ref=f"JIRA-{pid}-SC{k + 1}",
                payload={"change_id": f"{pid}-SC{k + 1}", "impact": str(rng.choice(["minor", "moderate", "major"], p=[0.5, 0.35, 0.15]))},
                quality={"approved_by": "change_board"},
            )

        # Dependencies on other teams.
        for k in range(dep):
            raised = start + timedelta(days=int(rng.integers(0, max(1, duration // 3))))
            res_days = int(max(3, rng.gamma(2.0, (10 + 15 * rc - 3 * skill_at(raised)) / 2 + 3)))
            resolved = raised + timedelta(days=res_days)
            did = f"{pid}-D{k + 1}"
            team = str(rng.choice(_TEAMS))
            self.deps.append(
                {"dependency_id": did, "project_id": pid, "owner_employee_id": lead, "depends_on": team,
                 "description": f"{team} deliverable required for {name}", "raised_on": raised,
                 "resolved_on": resolved if resolved <= self.as_of else None,
                 "status": "resolved" if resolved <= self.as_of else "open"}
            )
            self.emit(employee_id=lead, project_id=pid, when=raised, source="jira", category="dependency_registered",
                      ref=f"JIRA-{did}", payload={"dependency_id": did, "depends_on": team})
            self.emit(employee_id=lead, project_id=pid, when=resolved, source="jira", category="dependency_resolved",
                      ref=f"JIRA-{did}-R", payload={"dependency_id": did, "days_open": res_days, "cross_unit": True},
                      quality={"days_open": res_days})

        # Milestones.
        n_ms = 3 + ctx["size_band"] + int(rng.integers(0, 2))
        planned = [start + timedelta(days=round(duration * (k + 1) / n_ms)) for k in range(n_ms)]
        prev = start
        last_svp = None
        last_actual = None
        source = "jira" if emp.job_family == "technical_project_manager" else str(rng.choice(["jira", "asana", "monday"]))
        for k, p in enumerate(planned):
            interval = max(14, (p - prev).days)
            vol = sum(1 for sd in scope_days if start + timedelta(days=sd) <= p)
            s = skill_at(p)
            noise = float(rng.standard_t(5) * 6.5)
            svp = (
                -10.0 + 5.5 * (cx - 3) + 2.2 * dep + 22.0 * rc + 4.0 * vol
                + _ENV_EFFECT[ctx["environment"]] + _MATURITY_EFFECT[ctx["maturity"]]
                + (1.5 if ctx["team_size"] > 12 else 0.0) + _BU_EFFECT[emp.business_unit]
                + project_shock - 8.0 * s + noise
            )
            svp = float(max(svp, -25.0))
            actual = p + timedelta(days=round(svp / 100.0 * interval))
            mid = f"{pid}-M{k + 1}"
            achieved = actual <= self.as_of
            status = "achieved" if achieved else ("overdue" if p < self.as_of else "planned")
            self.milestones.append(
                {"milestone_id": mid, "project_id": pid, "name": f"Milestone {k + 1} of {n_ms}", "owner_employee_id": lead,
                 "planned_date": p, "actual_date": actual if achieved else None, "status": status}
            )
            # Tasks: volume scales with activity propensity — counting them rewards busyness.
            n_tasks = 2 + int(rng.poisson(1.5 + 1.2 * max(t.activity_propensity, 0)))
            for j in range(n_tasks):
                created = prev + timedelta(days=int(rng.integers(0, max(1, interval // 2))))
                due = created + timedelta(days=int(rng.integers(5, 25)))
                on_time = rng.random() < _sigmoid(1.0 + 0.4 * s - 1.0 * rc)
                done = due + timedelta(days=0 if on_time else int(rng.integers(1, 15)))
                ref = f"{source.upper()}-{mid}-T{j + 1}"
                self.emit(employee_id=lead, project_id=pid, when=created, source=source, category="task_created",
                          ref=ref, payload={"task_id": ref, "due_date": str(due)})
                self.emit(employee_id=lead, project_id=pid, when=done, source=source, category="task_completed",
                          ref=ref + "-C", payload={"task_id": ref, "due_date": str(due), "on_time": bool(on_time)})
            if achieved:
                self.emit(
                    employee_id=lead, project_id=pid, when=actual, source=source, category="milestone_achieved",
                    ref=f"{source.upper()}-{mid}",
                    payload={"milestone_id": mid, "planned_date": str(p), "actual_date": str(actual),
                             "baseline_interval_days": interval, "milestone_index": k + 1, "milestone_count": n_ms},
                    quality={"verified_by": "pmo_register"},
                )
                if svp > 30:
                    self.emit(employee_id=lead, project_id=pid, when=p, source="pmo_register", category="schedule_changed",
                              ref=f"PMO-{mid}-RB", payload={"milestone_id": mid, "slip_days": (actual - p).days})
                # Deliverable review.
                quality_score = float(np.clip(3.3 + 0.45 * s - 0.12 * (cx - 3) - 0.6 * rc + rng.normal(0, 0.55), 1, 5))
                missing_q = rng.random() < (0.06 + (0.12 if ctx["environment"] == "internal" else 0.0))
                first_pass = rng.random() < _sigmoid(0.4 + 0.9 * s - 0.25 * (cx - 3))
                self.emit(
                    employee_id=lead, project_id=pid, when=actual + timedelta(days=int(rng.integers(1, 6))),
                    source="ms_graph", category="document_reviewed", ref=f"DOC-{mid}",
                    payload={"milestone_id": mid, "document": f"{mid} deliverable", "approved_first_pass": bool(first_pass)},
                    quality={} if missing_q else {"review_score": round(quality_score, 1), "reviewer": "quality_board"},
                )
                last_svp, last_actual = svp, actual
            prev = p

        # Risks and issues.
        n_risks = int(rng.poisson(1.0 + 0.6 * cx + 0.3 * dep))
        for k in range(n_risks):
            rid = f"{pid}-R{k + 1}"
            ident = start + timedelta(days=int(rng.integers(0, max(1, duration - 20))))
            s = skill_at(ident)
            proactive = rng.random() < _sigmoid(0.2 + 0.8 * s)
            severity = str(rng.choice(["low", "medium", "high"], p=[0.35, 0.45, 0.2]))
            mitigated = rng.random() < _sigmoid(0.5 + 0.9 * s - 1.2 * rc - 0.15 * (cx - 3))
            mit_days = int(max(3, rng.gamma(2.0, 9.0 - 2.0 * s + 6 * rc)))
            mit_on = ident + timedelta(days=mit_days)
            materialised = (not mitigated) and rng.random() < 0.6
            status = "mitigated" if mitigated and mit_on <= self.as_of else ("issue" if materialised else "open")
            if status == "open" and ident + timedelta(days=60) < self.as_of and planned_end < self.as_of:
                status = "closed"
            self.risks.append(
                {"risk_id": rid, "project_id": pid, "owner_employee_id": lead, "title": f"{rng.choice(_RISK_TITLES)}",
                 "severity": severity, "identified_on": ident, "mitigated_on": mit_on if status == "mitigated" else None,
                 "status": status, "kind": "issue" if status == "issue" else "risk"}
            )
            self.emit(employee_id=lead, project_id=pid, when=ident, source="pmo_register", category="risk_identified",
                      ref=f"RAID-{rid}", payload={"risk_id": rid, "severity": severity, "proactive": bool(proactive)},
                      quality={"identified_before_impact": bool(proactive)})
            if mitigated:
                self.emit(employee_id=lead, project_id=pid, when=mit_on, source="pmo_register", category="risk_mitigated",
                          ref=f"RAID-{rid}-M", payload={"risk_id": rid, "days_to_mitigate": mit_days, "severity": severity})
            elif materialised:
                self.emit(employee_id=lead, project_id=pid, when=ident + timedelta(days=int(rng.integers(10, 40))),
                          source="pmo_register", category="issue_raised", ref=f"RAID-{rid}-I",
                          payload={"risk_id": rid, "severity": severity})

        # Blockers.
        for k in range(int(rng.poisson(0.6 + 0.5 * dep + rc))):
            raised = start + timedelta(days=int(rng.integers(0, max(1, duration - 10))))
            s = skill_at(raised)
            days = int(max(1, rng.gamma(2.0, max(1.0, (6 - 2 * s + 8 * rc) / 2))))
            ref = f"JIRA-{pid}-B{k + 1}"
            self.emit(employee_id=lead, project_id=pid, when=raised, source="jira", category="blocker_raised",
                      ref=ref, payload={"blocker_id": ref})
            self.emit(employee_id=lead, project_id=pid, when=raised + timedelta(days=days), source="jira",
                      category="blocker_resolved", ref=ref + "-R", payload={"blocker_id": ref, "days_to_resolve": days},
                      quality={"days_to_resolve": days})

        # Stakeholder feedback: noisy, inconsistent and strongly visibility-driven.
        for k in range(int(rng.integers(1, 4))):
            if rng.random() < 0.15:
                continue  # survey not returned
            when = start + timedelta(days=int(rng.integers(30, max(31, duration))))
            score = int(np.clip(round(3.2 + 0.25 * skill_at(when) + 0.55 * t.visibility + rng.normal(0, 1.0)), 1, 5))
            self.emit(employee_id=lead, project_id=pid, when=when, source="stakeholder_survey",
                      category="stakeholder_feedback", ref=f"SURVEY-{pid}-{k + 1}",
                      payload={"score": score, "respondent_role": str(rng.choice(["sponsor", "business_owner", "end_user_rep"]))},
                      quality={"response_scale": "1-5", "single_respondent": True})

        completed = last_actual is not None and all(m["status"] == "achieved" for m in self.milestones[-n_ms:])
        actual_end = last_actual if completed else None
        if completed:
            budget_var = float(2 + 6 * rc + 2 * (cx - 3) - 3 * skill_at(last_actual) + rng.normal(0, 6))
            self.emit(employee_id=lead, project_id=pid, when=last_actual + timedelta(days=7), source="pmo_register",
                      category="project_outcome", ref=f"PMO-{pid}-CLOSE",
                      payload={"final_schedule_variance_pct": round(last_svp or 0.0, 1), "budget_variance_pct": round(budget_var, 1),
                               "benefits_case_met": bool(rng.random() < _sigmoid(0.3 + 0.6 * skill_at(last_actual) - 0.4 * rc))},
                      quality={"closure_review": "pmo_gate_5"})
        status = "completed" if completed else ("active" if start <= self.as_of else "planned")
        self.projects.append(
            {"project_id": pid, "tenant_id": cfg.tenant_id, "name": name, "business_unit": emp.business_unit,
             "lead_employee_id": lead, "kind": "programme_workstream" if programme else "project",
             "start_date": start, "planned_end": planned_end, "actual_end": actual_end, "status": status,
             "is_synthetic": True, **ctx}
        )

    # -------------------------------------------------------------- activity
    def build_activity(self, employees: pd.DataFrame, truth: pd.DataFrame) -> None:
        rng = self.rng
        tmap = truth.set_index("employee_id")
        for emp in employees.itertuples():
            a = float(tmap.loc[emp.employee_id, "activity_propensity"])
            m = 0
            while True:
                d = self.start + timedelta(days=round(30.44 * m) + 27)
                if d > self.as_of:
                    break
                m += 1
                if d < emp.joined_on:
                    continue
                self.emit(
                    employee_id=emp.employee_id, project_id=None, when=d, source="ms_graph", category="activity_summary",
                    ref=f"GRAPH-ACT-{emp.employee_id}-{d:%Y%m}", data_category="diagnostic_activity",
                    payload={"month": f"{d:%Y-%m}", "meetings_attended": int(rng.poisson(max(4, 22 + 9 * a))),
                             "emails_sent": int(rng.poisson(max(20, 160 + 70 * a))),
                             "working_hours": round(float(np.clip(160 + 14 * a + rng.normal(0, 8), 120, 230)), 1)},
                    quality={"metadata_only": True, "content_collected": False},
                )

    # --------------------------------------------------------------- ratings
    def build_ratings(self, employees: pd.DataFrame, truth: pd.DataFrame, protected: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        rng = self.rng
        ms = pd.DataFrame(self.milestones)
        ms = ms[ms["status"] == "achieved"].copy()
        ms["slip_days"] = [(a - p).days for a, p in zip(ms["actual_date"], ms["planned_date"], strict=True)]
        tmap = truth.set_index("employee_id")
        gmap = protected.set_index("employee_id")["protected_group"]
        rows = []
        n_periods = max(1, self.cfg.months // 6)
        latent_by_period = []
        for k in range(n_periods):
            p_start = self.start + timedelta(days=round(k * 182.6))
            p_end = self.start + timedelta(days=round((k + 1) * 182.6))
            in_p = ms[(ms["actual_date"] >= p_start) & (ms["actual_date"] < p_end)]
            on_time = in_p.assign(ot=in_p["slip_days"] <= 3).groupby("owner_employee_id")["ot"].mean()
            ot_z = (on_time - on_time.mean()) / (on_time.std() or 1.0)
            mid = p_start + (p_end - p_start) / 2
            for emp in employees.itertuples():
                if emp.joined_on > p_end - timedelta(days=60):
                    continue
                tr = tmap.loc[emp.employee_id]
                s = tr.true_contribution + tr.growth_per_year * self.month_index(mid) / 12
                latent = (
                    0.55 * float(ot_z.get(emp.employee_id, 0.0)) + 0.5 * tr.visibility + 0.35 * tr.activity_propensity
                    + 0.2 * s + tr.rater_leniency - (0.3 if gmap[emp.employee_id] == "G2" else 0.0) + rng.normal(0, 0.55)
                )
                latent_by_period.append(latent)
                rows.append({"employee_id": emp.employee_id, "rater_id": emp.manager_id, "period": f"H{k + 1}",
                             "period_end": p_end, "_latent": latent})
        df = pd.DataFrame(rows)
        cuts = np.quantile(df["_latent"], [0.05, 0.25, 0.70, 0.92])
        df["manager_rating"] = 1 + np.searchsorted(cuts, df["_latent"].to_numpy())
        df = df.drop(columns="_latent")
        df["label_note"] = "historical rating — treated as a potentially biased label, not ground truth"
        promos = []
        for year, periods in ((1, ("H1", "H2")), (2, ("H3", "H4"))):
            sub = df[df["period"].isin(periods)].groupby("employee_id")["manager_rating"].mean()
            for emp_id, r in sub.items():
                promos.append({"employee_id": emp_id, "cycle": f"Y{year}", "promoted": bool(r >= 4 and rng.random() < 0.55)})
        return df, pd.DataFrame(promos)

    # -------------------------------------------------------------- meetings
    def build_meetings(self, employees: pd.DataFrame) -> pd.DataFrame:
        rng = self.rng
        names = employees.set_index("employee_id")["display_name"]
        pool = employees["employee_id"].tolist()
        rows = []
        active = [p for p in self.projects if p["status"] == "active"]
        open_ms = pd.DataFrame(self.milestones)
        for p in active:
            lead = p["lead_employee_id"]
            others = [str(x) for x in rng.choice(pool, size=3, replace=False) if x != lead][:2]
            attendees = [lead, *others]
            nm = {e: names[e].split()[0] for e in attendees}
            past = self.as_of - timedelta(days=int(rng.integers(1, 12)))
            upcoming_ms = open_ms[(open_ms["project_id"] == p["project_id"]) & (open_ms["status"] != "achieved")]
            next_ms = upcoming_ms["name"].iloc[0] if len(upcoming_ms) else "closure"
            transcript = _transcript(rng, p, nm, attendees, past, next_ms)
            rows.append({"meeting_id": f"{p['project_id']}-MTG-{past:%Y%m%d}", "tenant_id": self.cfg.tenant_id,
                         "project_id": p["project_id"], "title": f"{p['name']} — weekly delivery sync",
                         "scheduled_at": datetime.combine(past, time(10, 0)).isoformat(), "attendees": attendees,
                         "organiser_id": lead, "transcript": transcript, "data_category": "assistance", "is_synthetic": True})
            for k in range(int(rng.integers(1, 3))):
                fut = self.as_of + timedelta(days=int(rng.integers(0, 8)))
                rows.append({"meeting_id": f"{p['project_id']}-MTG-{fut:%Y%m%d}-{k}", "tenant_id": self.cfg.tenant_id,
                             "project_id": p["project_id"],
                             "title": f"{p['name']} — {rng.choice(['steering committee', 'risk review', 'stakeholder check-in', 'dependency sync'])}",
                             "scheduled_at": datetime.combine(fut, time(int(rng.integers(9, 17)), 0)).isoformat(),
                             "attendees": attendees, "organiser_id": lead, "transcript": None,
                             "data_category": "assistance", "is_synthetic": True})
        return pd.DataFrame(rows)


_RISK_TITLES = (
    "Vendor delivery slippage", "Key resource availability", "Test environment instability", "Data migration quality",
    "Regulatory interpretation change", "Integration defects", "Budget approval delay", "Security review backlog",
    "Stakeholder alignment", "Licence procurement lead time", "Legacy system knowledge gap", "Performance at scale",
)

_ACTION_TEMPLATES = (
    "{o}: I'll {verb} by {due}.",
    "{lead}: {o}, can you {verb} before {due}? {o}: Yes, will do.",
    "ACTION: {o} to {verb} by {due}.",
    "{o}: I will {verb} by {due}.",
)
_VERBS = (
    "update the delivery plan", "send the revised estimate to the sponsor", "confirm test environment dates",
    "draft the change request", "chase the vendor for the contract amendment", "review the data migration results",
    "prepare the steering committee pack", "book the cutover rehearsal", "close out the open security findings",
    "circulate the RAID log", "agree acceptance criteria with the business owner",
)
_DECISIONS = (
    "move the go-live to a phased rollout", "defer the reporting module to phase two", "use the existing API gateway",
    "freeze scope for this release", "run an additional regression cycle", "bring in a contractor for testing",
)
_RISK_LINES = (
    "There's a risk that the vendor misses the hardware delivery date.",
    "I'm worried the test environment won't be ready in time.",
    "There is a risk that key testers are pulled onto the incident backlog.",
    "There's a risk that the data quality issues delay migration.",
)


def _transcript(rng, project, nm, attendees, when: date, next_ms: str) -> str:
    lead = nm[attendees[0]]
    o1 = nm[attendees[1]] if len(attendees) > 1 else lead
    o2 = nm[attendees[-1]]
    def due(days):
        return str(when + timedelta(days=days))
    lines = [
        f"{lead}: Thanks for joining. Quick status on {project['name']}.",
        f"{o1}: Build is on track; we finished the integration tests for {next_ms.lower()} prep.",
        f"{lead}: {rng.choice(_RISK_LINES)}",
        f"{o2}: We're still waiting on {rng.choice(_TEAMS)} for the sign-off on the interface design.",
        f"{lead}: So we've agreed to {rng.choice(_DECISIONS)}.",
    ]
    picked = rng.choice(len(_VERBS), size=3, replace=False)
    owners = [o1, o2, lead]
    for i, vi in enumerate(picked):
        choices = [t for t in _ACTION_TEMPLATES if owners[i] != lead or "{lead}" not in t]
        tpl = choices[int(rng.integers(0, len(choices)))]
        lines.append(tpl.format(o=owners[i], lead=lead, verb=_VERBS[int(vi)], due=due(int(rng.integers(2, 15)))))
    lines.append(f"{o1}: Decision: {rng.choice(_DECISIONS)}.")
    lines.append(f"{lead}: This is blocked by {rng.choice(_TEAMS)} approving the firewall change.")
    lines.append(f"{lead}: Great, thanks everyone. Same time next week.")
    return "\n".join(lines)


def generate(config: SyntheticConfig | None = None) -> SyntheticDataset:
    """Generate a complete, reproducible synthetic organisation."""
    cfg = config or SyntheticConfig()
    b = _Builder(cfg)
    employees, truth, protected = b.build_employees()
    b.build_projects(employees, truth)
    b.build_activity(employees, truth)
    ratings, promos = b.build_ratings(employees, truth, protected)
    meetings = b.build_meetings(employees)
    events = pd.DataFrame(b.events).sort_values("occurred_at", kind="stable").reset_index(drop=True)
    projects = pd.DataFrame(b.projects)
    metadata = {
        "label": SYNTHETIC_LABEL,
        "seed": cfg.seed,
        "tenant_id": cfg.tenant_id,
        "as_of": cfg.as_of.isoformat(),
        "start": cfg.start.isoformat(),
        "counts": {
            "employees": len(employees),
            "program_managers": int((employees["job_family"] == "program_manager").sum()),
            "project_managers": int((employees["job_family"] == "project_manager").sum()),
            "technical_project_managers": int((employees["job_family"] == "technical_project_manager").sum()),
            "projects": len(projects),
            "milestones": len(b.milestones),
            "events": len(events),
            "meetings": len(meetings),
            "business_units": len(BUSINESS_UNITS),
        },
        "generator": "meritvector_analytics.synthetic v0.1.0",
    }
    return SyntheticDataset(
        config=cfg,
        employees=employees,
        projects=projects,
        milestones=pd.DataFrame(b.milestones),
        risks=pd.DataFrame(b.risks),
        dependencies=pd.DataFrame(b.deps),
        events=events,
        meetings=meetings,
        manager_ratings=ratings,
        promotions=promos,
        protected_attributes=protected,
        ground_truth=truth,
        metadata=metadata,
    )


SANDBOX_CONFIG = SyntheticConfig(
    seed=99,
    tenant_id="synthetic-sandbox",
    tenant_name="Synthetic Sandbox (assessment disabled)",
    n_program_managers=2,
    n_project_managers=8,
    n_technical_pms=2,
    id_prefix="SBX",
)
