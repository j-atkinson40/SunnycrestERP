"""What "today" and "now" mean for one tenant.

⚠️ THIS EXISTS BECAUSE EIGHT PLACES ALREADY ANSWERED THE QUESTION AND THEY DISAGREE.
Enumerated 2026-10-16, every reader of `companies.timezone`:

    reader                                              fallback when NULL
    --------------------------------------------------- ------------------
    delivery_schedule_service._get_tenant_timezone:347  America/New_York
    widgets/today_widget_service                        America/New_York
    note/settling_sweep._tz_for:65                      America/New_York
    note/settling.py:115                                America/New_York
    briefings/scheduler_integration._resolve_tz:151     America/New_York
    workflow_scheduler._resolve_tenant_tz:68            America/New_York
    maps_of_content/schedule_sweep:157                  America/New_York
    order_list/service.today_for:60                     ⚠️ UTC

Seven say Eastern, one says UTC, and the COLUMN DEFAULT is `"UTC"`
(`app/models/company.py:39-41`). So a tenant with no timezone gets two different
answers to "what day is it" depending on which surface is asked.

⚠️ AND THERE IS A NINTH, WITH THIS MODULE'S OWN FUNCTION NAME. `note/service.py:34`
defines its own `tenant_today(db, company_id)` — same signature, same name, different
module. Two functions called `tenant_today` is worse than two that merely disagree,
because an import line decides which one a caller gets and neither is wrong-looking.

⚠️ THAT COLLISION HAS ALREADY COST A TEST. `test_a_different_day_is_a_different_note`
compared `note.service.tenant_today` (the TENANT's zone — "UTC" for a fixture tenant)
against `date.today()` (the CONTAINER's zone), which agree for twenty hours a day and
diverge between 20:00 and midnight Eastern. It passed every run that day until 00:18
UTC. Fixed in the test by deriving tomorrow from the note's own day; the duplication is
untouched and is the reason this enumeration exists.

⚠️ THIS MODULE DOES NOT FIX THAT, AND SAYING SO IS THE POINT. Repointing eight readers
at one resolver changes the behaviour of the note surface, the briefing sweep, the
dispatch board and the order list all at once — each of which has its own tests written
against its own fallback. That is a sweep with its own dispatch, not a side effect of the
invoice batch. What this module does is stop the batch from inventing a NINTH answer, and
leave the enumeration written down where the next person will find it.

**Fallback here is `America/New_York`**, matching seven of the eight. For the batch
specifically that is also the safer direction: it is the business's own zone, and erring
toward it means an order is invoiced on the evening of its service date rather than
potentially the evening before.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.company import Company

logger = logging.getLogger(__name__)

#: ⚠️ NOT `UTC`, AND NOT THE COLUMN DEFAULT. See the module docstring — the column
#: defaults to `"UTC"`, which is a default nobody chose rather than a decision, and seven
#: of the eight existing readers fall back to Eastern.
DEFAULT_TZ = "America/New_York"


def tenant_timezone(db: Session, tenant_id: str) -> ZoneInfo:
    """The tenant's IANA zone, or `DEFAULT_TZ` if unset or unrecognised.

    ⚠️ AN UNRECOGNISED ZONE LOGS AND FALLS BACK RATHER THAN RAISING. A bad string in one
    tenant's configuration should not abort a per-tenant sweep for every other tenant —
    the wrapper would record the whole run as failed. It is logged at WARNING so it is
    recoverable from the logs rather than silent.
    """
    name = db.query(Company.timezone).filter(Company.id == tenant_id).scalar()
    if not name:
        return ZoneInfo(DEFAULT_TZ)
    try:
        return ZoneInfo(name)
    except Exception:
        logger.warning(
            "tenant %s has unrecognised timezone %r; falling back to %s",
            tenant_id, name, DEFAULT_TZ,
        )
        return ZoneInfo(DEFAULT_TZ)


def tenant_now(db: Session, tenant_id: str) -> datetime:
    """Current instant, expressed in the tenant's zone."""
    return datetime.now(tenant_timezone(db, tenant_id))


def tenant_today(db: Session, tenant_id: str) -> date:
    """The tenant's current calendar date.

    ⚠️ THIS IS THE FUNCTION THE END-OF-DAY BATCH TURNS ON, so the difference from
    `date.today()` is worth stating concretely. The batch runs at 18:00 America/New_York
    = 22:00 UTC in EDT. On that instant the UTC date and the Eastern date are the same,
    so for the 18:00 job the two agree — but they do NOT agree for the nightly 23:xx
    block (03:xx UTC the following day), and they would not agree if the batch ever moved
    later. Reading the tenant's date removes the question rather than relying on the
    current hour keeping them aligned.
    """
    return tenant_now(db, tenant_id).date()
