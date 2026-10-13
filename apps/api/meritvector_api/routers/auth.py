"""Demo authentication.

v0.1 uses demo sign-in as synthetic users (no passwords) so the platform can be
explored without credentials. It is controlled by ``MV_DEMO_AUTH`` and must be
replaced by SSO (OIDC/SAML) before any real deployment — see ROADMAP.md.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from meritvector_api import audit
from meritvector_api.db import get_db
from meritvector_api.models import Employee, Project, Tenant, User
from meritvector_api.security import Principal, current_principal, issue_token
from meritvector_api.settings import get_settings
from meritvector_api.training import latest_run

router = APIRouter(prefix="/auth", tags=["auth"])


def _require_demo() -> None:
    if not get_settings().demo_auth_enabled:
        raise HTTPException(404, "Demo sign-in is disabled")


class LoginRequest(BaseModel):
    user_id: str


def _persona(u: User, label: str, why: str) -> dict:
    return {
        "user_id": u.id,
        "display_name": u.display_name,
        "role": u.role,
        "tenant_id": u.tenant_id,
        "employee_id": u.employee_id,
        "label": label,
        "description": why,
    }


def _employee_persona(db: Session, tenant_id: str, preferred: str | None) -> Employee | None:
    """A delivery employee with an active project, preferably in the flagship experiment's team."""
    active_leads = set(
        db.scalars(select(Project.lead_employee_id).where(Project.tenant_id == tenant_id, Project.status == "active"))
    )
    pref = db.get(Employee, preferred) if preferred else None
    if pref is not None and pref.id in active_leads:
        return pref
    stmt = select(Employee).where(
        Employee.tenant_id == tenant_id, Employee.job_family != "program_manager", Employee.id.in_(active_leads)
    )
    if pref is not None:
        team = db.scalars(stmt.where(Employee.manager_id == pref.manager_id).order_by(Employee.id)).first()
        if team is not None:
            return team
    return db.scalars(stmt.order_by(Employee.id)).first()


@router.get("/demo-personas")
def demo_personas(db: Session = Depends(get_db)) -> list[dict]:
    _require_demo()
    out = []
    for t in db.scalars(select(Tenant).order_by(Tenant.id)):
        run = latest_run(db, t.id)
        emp = _employee_persona(db, t.id, run.experiment.get("employees", {}).get("B") if run else None)
        if emp is not None:
            out.append(
                _persona(db.get(User, f"u-{emp.id}"), "Employee", f"{emp.job_family.replace('_', ' ').title()} — {t.name}")
            )
            mgr = db.get(User, f"u-{emp.manager_id}")
            if mgr is not None:
                out.append(_persona(mgr, "Manager", f"Programme manager of {emp.display_name} — {t.name}"))
        for role, label in (("hr_reviewer", "HR reviewer"), ("admin", "Administrator")):
            u = db.scalars(select(User).where(User.tenant_id == t.id, User.role == role).order_by(User.id)).first()
            if u is not None:
                out.append(_persona(u, label, t.name))
    return out


@router.get("/demo-users")
def demo_users(q: str = "", tenant_id: str | None = None, limit: int = 20, db: Session = Depends(get_db)) -> list[dict]:
    _require_demo()
    stmt = select(User)
    if tenant_id:
        stmt = stmt.where(User.tenant_id == tenant_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(User.display_name.ilike(like), User.id.ilike(like)))
    return [
        {"user_id": u.id, "display_name": u.display_name, "role": u.role, "tenant_id": u.tenant_id}
        for u in db.scalars(stmt.order_by(User.display_name).limit(min(limit, 50)))
    ]


@router.post("/demo-login")
def demo_login(req: LoginRequest, db: Session = Depends(get_db)) -> dict:
    _require_demo()
    u = db.get(User, req.user_id)
    if u is None:
        raise HTTPException(404, "Unknown user")
    audit.record(
        db,
        tenant_id=u.tenant_id,
        actor_user_id=u.id,
        actor_role=u.role,
        action="login",
        resource_type="session",
        detail={"method": "demo"},
    )
    return {"token": issue_token(u), "user": {"user_id": u.id, "display_name": u.display_name, "role": u.role}}


@router.get("/me")
def me(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> dict:
    t = db.get(Tenant, p.tenant_id)
    emp = db.get(Employee, p.employee_id) if p.employee_id else None
    reports = 0
    if emp is not None and p.role == "manager":
        reports = len(db.scalars(select(Employee.id).where(Employee.manager_id == emp.id)).all())
    return {
        "user_id": p.user_id,
        "display_name": p.display_name,
        "role": p.role,
        "employee_id": p.employee_id,
        "tenant": {
            "id": t.id,
            "name": t.name,
            "is_synthetic": t.is_synthetic,
            "assessment_enabled": t.assessment_enabled,
            "as_of": str(t.as_of),
        },
        "employee": {"job_family": emp.job_family, "level": emp.level, "business_unit": emp.business_unit} if emp else None,
        "direct_reports": reports,
        "permissions": {
            "workspace": p.employee_id is not None,
            "team_contribution": p.role == "manager" and t.assessment_enabled,
            "all_contribution": p.role == "hr_reviewer" and t.assessment_enabled,
            "analysis": p.role in ("manager", "hr_reviewer") and t.assessment_enabled,
            "validation": p.role in ("manager", "hr_reviewer", "admin") and t.assessment_enabled,
            "fairness_audit": p.role in ("hr_reviewer", "admin") and t.assessment_enabled,
            "administration": p.role in ("admin", "hr_reviewer"),
        },
    }
