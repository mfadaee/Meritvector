"""Authentication (signed bearer tokens) and role-based access control.

Roles:
  employee     — own workspace, own evidence, own development record
  manager      — the above, plus contribution detail for *direct reports*
  hr_reviewer  — contribution detail across the tenant, governance approval,
                 aggregated fairness audit, evidence-challenge resolution
  admin        — tenant configuration, retention, audit log, jobs; deliberately
                 *no* access to individual performance evidence (data minimisation)

Every query is scoped to the caller's tenant.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from meritvector_api.db import get_db
from meritvector_api.models import Employee, Tenant, User
from meritvector_api.settings import get_settings


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    role: str
    employee_id: str | None
    display_name: str


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue_token(user: User) -> str:
    s = get_settings()
    body = {"sub": user.id, "tid": user.tenant_id, "exp": int(time.time()) + s.token_ttl_minutes * 60}
    payload = _b64(json.dumps(body, separators=(",", ":")).encode())
    sig = _b64(hmac.new(s.secret_key.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def verify_token(token: str) -> dict:
    s = get_settings()
    try:
        payload, sig = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token") from exc
    expected = _b64(hmac.new(s.secret_key.encode(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    body = json.loads(_unb64(payload))
    if body["exp"] < time.time():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    return body


def current_principal(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    body = verify_token(authorization.split(" ", 1)[1])
    user = db.get(User, body["sub"])
    if user is None or user.tenant_id != body["tid"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return Principal(user.id, user.tenant_id, user.role, user.employee_id, user.display_name)


def require_roles(*roles: str):
    def dep(p: Principal = Depends(current_principal)) -> Principal:
        if p.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role: {', '.join(roles)}")
        return p

    return dep


def require_assessment_enabled(p: Principal = Depends(current_principal), db: Session = Depends(get_db)) -> Principal:
    tenant = db.get(Tenant, p.tenant_id)
    if tenant is None or not tenant.assessment_enabled:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Performance-assessment features are disabled for this organisation. They require explicit governance "
            "approval by an administrator and an HR reviewer (Administration → Governance).",
        )
    return p


def can_view_assessment(p: Principal, emp: Employee) -> bool:
    if emp.tenant_id != p.tenant_id:
        return False
    if p.employee_id == emp.id:
        return True
    if p.role == "manager" and emp.manager_id == p.employee_id:
        return True
    return p.role == "hr_reviewer"


def can_review(p: Principal, emp: Employee) -> bool:
    if emp.tenant_id != p.tenant_id or p.employee_id == emp.id:
        return False
    return (p.role == "manager" and emp.manager_id == p.employee_id) or p.role == "hr_reviewer"


def get_visible_employee(db: Session, p: Principal, employee_id: str) -> Employee:
    emp = db.get(Employee, employee_id)
    # Return 404 rather than 403 for other tenants so existence is not disclosed.
    if emp is None or emp.tenant_id != p.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
    if not can_view_assessment(p, emp):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not authorised to view this employee's assessment evidence")
    return emp
