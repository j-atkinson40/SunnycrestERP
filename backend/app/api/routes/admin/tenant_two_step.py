"""Platform-realm recovery for a tenant user locked out of two-step.

Payroll 2, ruling 3: *"Report how the platform realm would do it; build only if
it's under ~50 lines, otherwise STATE."*

### The case this exists for, and the three steps before it

A user required to use two-step who loses her phone recovers through her
**recovery codes** — ten of them, shown once at enrolment, each single-use
(`r225`). If those are gone too, another tenant admin clears her enrolment
through `POST /api/v1/users/{id}/two-step/reset`, which deliberately refuses a
self-clear so that losing a device always takes a second person.

⚠️ **THE SOLE-ADMIN CASE IS WHERE BOTH OF THOSE RUN OUT, AND IT IS NOT
HYPOTHETICAL FOR A SMALL TENANT.** If the only admin is the locked-out user,
"ask another administrator" names nobody. Measured: impersonation does not
rescue her either — it mints a token with `mfa: True`
(`impersonation_service.py:73`), so a platform admin CAN act as her, but acting
as her means the tenant reset endpoint sees `current_user.id == target.id` and
refuses as a self-clear. The existing paths genuinely terminate.

### How the platform realm does it

The same way it does everything else that crosses a tenant boundary: a
`/api/platform/admin/*` route behind `get_current_platform_user`. That realm
already owns impersonation, migrations and feature flags for exactly this
reason — operations a tenant cannot perform on itself.

⚠️ **THE AUDIT ROW CANNOT NAME THE PLATFORM ACTOR IN ITS ACTOR COLUMN, AND THAT
IS A KNOWN SCHEMA LIMITATION RATHER THAN A CHOICE HERE.** `audit_logs.user_id`
is `FOREIGN KEY ... REFERENCES users(id)` (verified against the live schema), and
a `PlatformUser` id cannot satisfy it — the limitation CLAUDE.md records under
"Audit attribution limitation". So `user_id` is NULL and the actor is written
into `changes` as `platform_actor_id` / `platform_actor_email`, which is
queryable. A NULL actor column on a security operation is weak; it is recorded
rather than worked around, because inventing a tenant user to attribute it to
would be worse.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_platform_user
from app.core import two_step
from app.database import get_db
from app.models.platform_user import PlatformUser
from app.models.user import User
from app.services import audit_service

router = APIRouter()


@router.post("/{company_id}/users/{user_id}/two-step/reset")
def reset_tenant_user_two_step(
    company_id: str,
    user_id: str,
    admin: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """Clear a tenant user's two-step enrolment. Last resort.

    She must enrol again at her next sign-in — this does not let her past the
    guard, it only lets her start over. `company_id` is required in the path so
    a mistyped user id cannot silently reach another tenant's user.
    """
    user = (
        db.query(User)
        .filter(User.id == user_id, User.company_id == company_id)
        .first()
    )
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found in that tenant")

    had = two_step.clear_two_step(db, user.id)
    audit_service.log_action(
        db,
        company_id=company_id,
        action="two_step_reset_by_platform",
        entity_type="user",
        entity_id=user.id,
        user_id=None,          # see the module docstring: FK forbids the real actor
        changes={
            "reset_for": user.id,
            "had_enrolment": had,
            "platform_actor_id": admin.id,
            "platform_actor_email": admin.email,
        },
    )
    db.commit()
    return {"user_id": user.id, "had_enrolment": had, "enrolled": False}
