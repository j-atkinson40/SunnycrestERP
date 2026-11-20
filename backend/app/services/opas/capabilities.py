"""What Opas can do for the signed-in user, composed per AREA on the server.

⚠️ **WHY THIS IS NOT A CLIENT CONSTANT.** Opas's idle offerings have been
client-side strings since the capture arc — `IDLE_PILL_LABEL = "New order"` in
`components/opas/opas-prompts.ts`. For an unlimited user that is harmless. For
Susan it is wrong in the way that matters: her role is limited to payroll, and
an Opas that offers to start an order is offering a thing the server will refuse
and that she should never have been shown. The list has to be composed where the
areas are known, which is here.

⚠️ **THE AREA PREDICATE IS THE NOTE'S, NOT A SECOND ONE.** `allowed_area_grants`
+ `area_admits_read` are the same two functions `fragments/emission.py` calls to
decide which note fragments exist for a caller. A second implementation would be
a second thing to keep in step, and the note already proved these two handle the
three-outcome case (`None` / `[]` / `{...}`) correctly.

⚠️ **AND `area_admits_read` IS DELIBERATELY NOT ENOUGH ON ITS OWN HERE.** Its own
docstring says so: *"a surface that offers an action must check the level itself"*.
Opas offers ACTIONS, not just sightings — "upload this week's hours" is a write.
So an entry declares the LEVEL it needs, and a `view`-only grant is offered only
the `view` entries. A payroll role that can see the week but not approve it must
not be offered approval, because an offer that 403s is worse than no offer.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from sqlalchemy.orm import Session

from app.core.areas import CROSS_AREA, allowed_area_grants, area_admits_read
from app.services.payroll.r115_schedule import current_form_period
from app.services.payroll.week_calendar import current_week_end
from app.services.permission_service import user_has_permission
from app.models.user import User

#: The two levels an entry can require. Mirrors `areas.py`'s grant vocabulary
#: rather than inventing a parallel one.
VIEW = "view"
CHANGE = "change"


@dataclass(frozen=True)
class OpasCapability:
    """One thing Opas can do, and everything needed to decide who may see it.

    `id` is the TYPED ACT and is stable — the client switches on it and tests
    assert on it, so renaming one is a contract change, not a copy edit.

    `phrases` is what the user can type to reach this entry. It lives on the
    server with the entry rather than in a client matcher, because the client
    must not hold a phrase for an entry it was never given: that is how a
    payroll user ends up with a working shortcut to an order.
    """

    id: str
    label: str
    area: str
    level: str
    permission: str | None
    phrases: tuple[str, ...]
    #: Where it opens. A Focus id (`focus:weekly-payroll`) or a route
    #: (`/payroll`).
    #:
    #: ⚠️ **MAY CARRY `{week_end}`, WHICH THE ENDPOINT FILLS — AND AN UNSCOPED
    #: TARGET OPENED NOTHING.** Found in the PR C walk-through: picking "This
    #: week's payroll" navigated to `/home?focus=weekly-payroll` and the Focus
    #: did not render at all. The page showed only the note under a URL that
    #: claimed a Focus. The working shape is the one the note's own line already
    #: uses — `?focus=weekly-payroll&week_end=<date>` — so the week entries
    #: declare the placeholder and `capabilities_for` substitutes the current
    #: payroll week. An entry whose placeholder cannot be filled is DROPPED
    #: rather than offered unscoped.
    target: str
    #: One line under the label. Absent rather than empty when there is nothing
    #: to add — the client renders only what exists.
    hint: str | None = None


#: ──────────────────────────────────────────────────────────────── the registry
#:
#: ⚠️ **ONE ENTRY PER THING A USER WOULD ASK FOR, NOT ONE PER ROUTE.** The
#: catalogue is Opas's vocabulary, so it is written in her words ("this week's
#: payroll"), and several entries can open the same surface with different
#: scope. `weekly-payroll` appears twice for exactly that reason: reviewing the
#: week and uploading its hours are different requests that happen to land in
#: the same Focus.
#:
#: ⚠️ **PAYROLL ONLY, DELIBERATELY, AND THE EMPTINESS ELSEWHERE IS THE POINT.**
#: This ships with the payroll area populated because that is the area a limited
#: role is live on today. Adding `orders` entries without the area tags and
#: level checks that go with them would hand an unlimited user a list and a
#: limited user a silent over-grant; see the warning on `COMPOSED_ROUTES`. Other
#: areas earn entries when their own shell work lands.
CAPABILITIES: tuple[OpasCapability, ...] = (
    OpasCapability(
        id="payroll_week_review",
        label="This week's payroll",
        hint="Hours, questions and dues for the week being processed",
        area="payroll",
        level=VIEW,
        permission="payroll.view",
        phrases=(
            "this week's payroll",
            "this weeks payroll",
            "weekly payroll",
            "payroll",
            "the week",
            "review the week",
            "dues",
            "union dues",
        ),
        target="focus:weekly-payroll?week_end={week_end}",
    ),
    OpasCapability(
        id="payroll_hours_upload",
        label="Upload hours",
        hint="The Employee Hours file from Payentry",
        area="payroll",
        level=CHANGE,
        permission="payroll.upload",
        phrases=(
            "upload hours",
            "upload the hours",
            "upload employee hours",
            "hours",
            "employee hours",
            "add hours",
            "upload this week's hours",
        ),
        target="focus:weekly-payroll?week_end={week_end}#upload",
    ),
    OpasCapability(
        id="payroll_dues_report",
        label="Dues reports",
        hint="Past weeks, and the monthly union figures",
        area="payroll",
        level=VIEW,
        permission="payroll.view",
        phrases=(
            "dues report",
            "dues reports",
            "past weeks",
            "previous weeks",
            "monthly dues",
            "union report",
            "reports",
        ),
        target="/payroll",
    ),
    OpasCapability(
        id="payroll_union_form",
        label="Union form",
        hint="The R-115 for the month being remitted",
        area="payroll",
        level=VIEW,
        permission="payroll.view",
        #: ⚠️ **"FORM" IS DELIBERATELY NOT HERE.** It is the first word a
        #: person reaches for and it is ambiguous across the whole platform —
        #: an intake form, a correction form, this. The phrases that resolve
        #: are the ones that name the UNION or the R-115, and the matcher's
        #: containment pass then catches "the union form" and "r115 form"
        #: without "form" alone pulling this entry out of nowhere.
        phrases=(
            "union form",
            "r115",
            "r-115",
            "the r115",
            "union remittance",
            "remittance",
            "monthly union form",
            "union dues form",
        ),
        target="focus:union-form?period={form_period}",
    ),
)


def _level_admits(entry: OpasCapability, grants: dict[str, str] | None) -> bool:
    """Does the caller's grant on this entry's area reach the entry's level?

    `grants is None` is the unlimited role and reaches everything. Otherwise a
    `view` entry needs the area present at any level, and a `change` entry needs
    that area's grant to actually be `change`.

    ⚠️ `area_admits_read` is called first and separately, so `CROSS_AREA` is
    already refused for every limited caller by the time this runs. It is not
    re-checked here; one refusal in one place.
    """
    if grants is None:
        return True
    if entry.level == VIEW:
        return True
    return grants.get(entry.area) == CHANGE


def capabilities_for(db: Session, user: User, *, limited_to_areas) -> list[OpasCapability]:
    """The entries this user may be offered, in registry order.

    Three gates, each of which can only remove entries:

        area        `area_admits_read` — the note's own predicate
        level       a `view` grant is not offered a write
        permission  the existing permission check, unchanged

    ⚠️ **ORDER IS THE REGISTRY'S ORDER AND IS NOT RANKED.** Nothing here knows
    what the user is in the middle of, so any ranking would be invented. The
    note is what says what needs doing today; this list says what can be asked
    for at all.
    """
    grants = allowed_area_grants(limited_to_areas)

    #: The week being PROCESSED today, which is not the calendar week — see
    #: `week_calendar.current_payroll_week`. Computed once per request.
    week_end = current_week_end(date.today()).isoformat()

    out: list[OpasCapability] = []
    for entry in CAPABILITIES:
        if not area_admits_read(entry.area, grants):
            continue
        if not _level_admits(entry, grants):
            continue
        if entry.permission and not user_has_permission(user, db, entry.permission):
            continue
        if "{form_period}" in entry.target:
            # ⚠️ FILLED BY THE SERVER, for the same reason `{week_end}` is: an
            # unscoped `focus:union-form` opens a Focus that does not know
            # which month it is about, and the walk-through of 2026-11-18
            # caught exactly that shape on the week entry — a URL that claims
            # a surface and renders nothing.
            y, m = current_form_period(date.today())
            entry = replace(entry, target=entry.target.format(
                form_period=f"{y}-{m:02d}"))
        if "{week_end}" in entry.target:
            # ⚠️ REPLACED, NOT APPENDED. The entry is frozen, so this produces a
            # new one; the registry keeps its placeholder and stays declarative.
            entry = replace(entry, target=entry.target.format(week_end=week_end))
        out.append(entry)
    return out


def match_phrase(text: str, entries: list[OpasCapability]) -> OpasCapability | None:
    """Resolve typed text against the entries THIS CALLER WAS GIVEN.

    ⚠️ **THE CANDIDATE SET IS THE COMPOSED LIST, NEVER `CAPABILITIES`.** Matching
    against the whole registry would re-open on the typing path exactly what the
    area gates just closed on the listing path — the user would be shown three
    entries and be able to type her way into a fourth.

    Exact normalised match first, then a whole-phrase containment, so "payroll"
    does not beat "upload hours" when the user typed the latter. No fuzzy
    matching: a wrong guess here opens the wrong surface, and Opas asking is
    cheaper than Opas being wrong.
    """
    norm = " ".join((text or "").strip().lower().replace("’", "'").split())
    if not norm:
        return None
    for entry in entries:
        if norm in entry.phrases:
            return entry
    for entry in entries:
        for phrase in entry.phrases:
            if phrase in norm:
                return entry
    return None
