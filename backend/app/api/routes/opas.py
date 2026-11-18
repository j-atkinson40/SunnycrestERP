"""Opas's own surfaces — what she can do for the signed-in user.

⚠️ **THIS ROUTER CARRIES NO `area:` TAG, DELIBERATELY, AND THAT IS WHY IT NEEDED
AN ENTRY IN `COMPOSED_ROUTES`.** It spans areas by construction: one response
describes payroll for Susan and would describe orders and invoices for somebody
else. A single tag would either over-grant (tag it `payroll` and an orders user
is refused her own list) or break it (leave it untagged and the area guard
refuses every limited role, which is the behaviour this endpoint exists to end).

The third option is the one `areas.py` names: the surface FILTERS ITSELF, and
says so out loud by being listed in `COMPOSED_ROUTES`. The filtering lives in
`services/opas/capabilities.py` and the test that a payroll-limited caller gets
ONLY payroll entries is the thing that makes the entry honest — per that
tuple's own warning, "a 200 full of somebody else's work is the failure this is
most likely to produce."
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.role import Role
from app.models.user import User
from app.services.opas.capabilities import capabilities_for

router = APIRouter()


@router.get("/capabilities")
def list_capabilities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The entries Opas may offer this user, composed from her role's areas.

    ⚠️ **NO PERMISSION GATE ON THE ROUTE ITSELF.** Every entry carries its own
    permission and is dropped when the caller lacks it, so a user with no
    payroll permissions gets `{"capabilities": []}` rather than a 403. The
    distinction is deliberate: an empty Opas is a correct Opas for someone with
    nothing to do in it, and a 403 on the entrance would make the shell render
    an error where it should render nothing.

    ⚠️ **`limited_to_areas` IS READ FROM THE ROLE, NOT FROM THE TOKEN OR THE
    REQUEST.** `/auth/me` reports it to the client so the shell can be chosen,
    but nothing here trusts that report back: a client that sent its own area
    list would be choosing its own grants.
    """
    role = db.query(Role).filter(Role.id == current_user.role_id).first()
    limited_to_areas = getattr(role, "limited_to_areas", None) if role else None

    entries = capabilities_for(db, current_user, limited_to_areas=limited_to_areas)
    return {
        "capabilities": [
            {
                "id": e.id,
                "label": e.label,
                # Omitted rather than null when absent — the client renders only
                # what exists, the same contract the catalog panes use.
                **({"hint": e.hint} if e.hint else {}),
                "area": e.area,
                "level": e.level,
                "phrases": list(e.phrases),
                "target": e.target,
            }
            for e in entries
        ]
    }
