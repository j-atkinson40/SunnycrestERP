"""The note is a COMPOSED SURFACE — Payroll 5a.

⚠️ **THE BUG THIS CLOSES: `GET /note/today` ANSWERED 403 FOR SUSAN.** The note
is the first screen after sign-in, and her role is `limited_to_areas =
["payroll"]`. The note's router spans areas and carries no area tag, so the
area guard refused it with reason `untagged`. The one person the payroll work
was built for could not get past her home page.

`COMPOSED_SURFACES` in `app/core/areas.py` has named the note as the first
surface to fix since 2026-11-06, in those words: "the payroll user's error page
IS this surface refusing."

⚠️ **THE FIX MOVES A GUARD RATHER THAN REMOVING ONE, AND THAT IS THE RISK.**
The route is now in `COMPOSED_ROUTES`, so `enforce_area_limit` steps aside and
the SURFACE filters instead. If the filtering were absent or wrong, the note
would answer 200 with another area's work on it — which looks like success.
A test that only asserted 200 would therefore pass on exactly the outcome worth
preventing, so every test here asserts WHAT CAME BACK, not merely that
something did.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.areas import CROSS_AREA, allowed_area_grants, area_admits_read
from app.main import app
from app.models.user import User
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture
from tests._two_step import tenant_token

_canonical_tenant = make_canonical_tenant_fixture()

HEADERS = {"X-Company-Slug": "testco"}
TODAY = "/api/v1/note/today"

#: `area-probe-` ids are exempt from `test_no_undeclared_role_carries_areas`,
#: which is the suite's guard against a role acquiring areas by accident.
ROLES = {
    # slug suffix -> (limited_to_areas, permission keys)
    "payroll": (["payroll"], ["payroll.view", "payroll.approve"]),
    # ⚠️ `[]` IS A ROLE LIMITED TO NOTHING, and is NOT `None`. Both are falsey;
    # they mean opposite things. This actor exists so that distinction has a
    # test rather than only a comment.
    "nothing": ([], ["payroll.view"]),
}


def H(token):
    return {**HEADERS, "Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def actors():
    """One limited role per entry in ROLES, plus the seeded unlimited admin."""
    from app.database import SessionLocal
    from app.models.role import Role
    from app.models.role_permission import RolePermission

    db = SessionLocal()
    ids = {k: (f"area-probe-note-{k}", f"area-probe-note-role-{k}") for k in ROLES}

    def wipe():
        for uid, rid in ids.values():
            db.execute(text("DELETE FROM audit_logs WHERE user_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM daily_notes WHERE subject_id=:u"), {"u": uid})
            db.execute(text("DELETE FROM users WHERE id=:u"), {"u": uid})
            db.execute(text("DELETE FROM role_permissions WHERE role_id=:r"), {"r": rid})
            db.execute(text("DELETE FROM roles WHERE id=:r"), {"r": rid})

    try:
        wipe()
        out = {}
        for key, (areas, perms) in ROLES.items():
            uid, rid = ids[key]
            db.add(Role(id=rid, company_id=TESTCO_ID,
                        name=f"Area Probe Note {key}", slug=f"area-probe-note-{key}",
                        is_system=False, is_active=True, limited_to_areas=areas))
            db.flush()
            for p in perms:
                db.add(RolePermission(role_id=rid, permission_key=p))
            db.add(User(id=uid, email=f"{uid}@testco.example.com",
                        hashed_password="not-a-credential", first_name="Note",
                        last_name=key.title(), role_id=rid, company_id=TESTCO_ID))
            out[key] = uid
        db.commit()

        # Control: the roles must really carry the areas they claim, or every
        # assertion below is about an unlimited user and proves nothing.
        for key in ROLES:
            got = db.execute(text("SELECT limited_to_areas FROM roles WHERE id=:r"),
                             {"r": ids[key][1]}).scalar()
            assert got == ROLES[key][0], f"{key}: stored areas {got!r}"

        admin_id = db.execute(text(
            "SELECT u.id FROM users u JOIN roles r ON r.id=u.role_id "
            "WHERE u.company_id=:c AND r.slug='admin' AND r.limited_to_areas IS NULL "
            "LIMIT 1"), {"c": TESTCO_ID}).scalar()
        if admin_id is None:
            pytest.skip("testco has no unlimited admin — run the role seed")
        out["admin"] = admin_id

        yield {k: tenant_token(v, TESTCO_ID) for k, v in out.items()}
    finally:
        wipe()
        db.commit()
        db.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ── the 403 is gone ──────────────────────────────────────────────────────────


def test_a_payroll_limited_user_reaches_her_own_note(client, actors):
    """⚠️ THE REGRESSION. This answered 403 `area_restricted`/untagged."""
    r = client.get(TODAY, headers=H(actors["payroll"]))
    assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
    body = r.json()
    # `prose` is a list in every case including the empty one — an absent key
    # would let a client read "not built yet" as "nothing to say today".
    assert isinstance(body.get("prose"), list), body.keys()
    assert isinstance(body.get("standing_set"), list)


def test_the_guard_is_what_changed_not_the_whole_router(client, actors):
    """⚠️ FAIL-CLOSED CONTROL. Only `GET /note/today` was opened.

    `COMPOSED_ROUTES` matches exact (method, path) pairs. `POST /note/defer`
    composes nothing and filters nothing, so a limited role is still refused
    there. If this starts returning anything but 403, somebody has widened the
    entry to a prefix and every sibling route added later came with it.
    """
    r = client.post("/api/v1/note/defer", headers=H(actors["payroll"]),
                    json={"fragment_id": "weekly_dues", "subject_id": "x",
                          "preset": "tomorrow"})
    assert r.status_code == 403, f"{r.status_code}: {r.text[:200]}"
    assert r.json()["detail"]["code"] == "area_restricted"


# ── and she sees ONLY payroll ───────────────────────────────────────────────


def _areas_of(prose_items):
    from app.services.fragments.registry import get_registry
    reg = get_registry()
    return {reg[p["fragment_id"]].area
            for p in prose_items if p.get("fragment_id") in reg}


def test_her_note_carries_payroll_fragments_and_no_others(client, actors):
    """⚠️ THE ONE THAT MATTERS. A 200 full of accounting is the failure mode.

    Asserting the SET of areas rather than "no accounting" — naming one area to
    exclude would pass the day somebody adds a sixth fragment in a seventh area.
    """
    r = client.get(TODAY, headers=H(actors["payroll"]))
    assert r.status_code == 200
    got = _areas_of(r.json()["prose"])
    assert got <= {"payroll"}, f"out-of-area fragments on her note: {got}"


def test_a_cross_area_fragment_is_withheld_from_her(client, actors):
    """`tasks_due_today` is `any_authenticated` AND `CROSS_AREA`.

    It is the fragment most likely to leak: its audience admits everybody, so
    only the area declaration keeps it off a limited note. Every area creates
    tasks, so showing it would put other areas' subject lines on her page
    through the one fragment that admits it cannot tell which area it is in.
    """
    r = client.get(TODAY, headers=H(actors["payroll"]))
    ids = {p.get("fragment_id") for p in r.json()["prose"]}
    assert "tasks_due_today" not in ids, "cross-area fragment reached a limited role"


def test_her_standing_set_is_filtered_too(client, actors):
    """The register is the other half of the surface, and `workload` is
    cross-area — it summarises deliveries and the ancillary pool. A payroll
    role has no template and falls back to exactly that line, so without
    filtering here the prose would be clean and the register would leak.

    An EMPTY standing set is the correct outcome, not an error.
    """
    r = client.get(TODAY, headers=H(actors["payroll"]))
    assert r.status_code == 200
    assert [e["entry_id"] for e in r.json()["standing_set"]] == []


# ── positive controls: the filter is a filter, not an empty surface ─────────


def test_an_unlimited_admin_is_unchanged(client, actors):
    """⚠️ THE CONTROL THAT STOPS ALL OF THE ABOVE BEING VACUOUS.

    Every assertion above is satisfied by a note that returns nothing to
    anybody. The admin's role is NULL-areas, so the admin must still get the
    cross-area fragment and the standing set the limited user does not.
    """
    r = client.get(TODAY, headers=H(actors["admin"]))
    assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
    assert isinstance(r.json()["standing_set"], list)
    assert len(r.json()["standing_set"]) >= 1, (
        "the unlimited admin has an empty standing set — the filter is "
        "removing lines from a role with NO restriction, which means "
        "`limited_to_areas IS NULL` is being read as a restriction"
    )


def test_the_payroll_fragment_exists_and_is_declared_payroll():
    """⚠️ Without this, "payroll fragments only" is true of an empty note.

    `test_her_note_carries_payroll_fragments_and_no_others` asserts a SUBSET,
    and the empty set is a subset of everything. This asserts the registry
    actually holds a payroll fragment for that test to be about.
    """
    from app.services.fragments.registry import get_registry

    reg = get_registry()
    payroll = {fid for fid, d in reg.items() if d.area == "payroll"}
    assert payroll, "no fragment declares area='payroll'"
    assert "weekly_dues" in payroll


# ── [] is not None ──────────────────────────────────────────────────────────


def test_a_role_limited_to_nothing_gets_an_empty_note_not_an_error(client, actors):
    """⚠️ `[]` AND `None` ARE BOTH FALSEY AND MEAN OPPOSITE THINGS.

    A role limited to `[]` reaches nothing. The note must still answer 200 with
    an empty prose list — "nothing to say" is a real state and a quiet day
    produces it legitimately. A 500 here is the classic `if role.areas:` bug:
    the empty list takes the unlimited branch and the user sees EVERYTHING.
    """
    r = client.get(TODAY, headers=H(actors["nothing"]))
    assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
    body = r.json()
    assert body["prose"] == [], f"a role limited to nothing got: {body['prose']}"
    assert body["standing_set"] == []


def test_the_helper_separates_none_from_empty():
    """The unit-level statement of the same thing, in the one function both
    the note and the standing set call, so neither can drift from it."""
    assert allowed_area_grants(None) is None          # unlimited
    assert allowed_area_grants([]) == {}              # limited to nothing
    assert allowed_area_grants(["payroll"]) == {"payroll": "change"}
    assert allowed_area_grants(["orders:view"]) == {"orders": "view"}

    # and the two must behave oppositely at the point of use
    assert area_admits_read("payroll", None) is True
    assert area_admits_read("payroll", {}) is False
    assert area_admits_read(CROSS_AREA, None) is True
    assert area_admits_read(CROSS_AREA, {"payroll": "change"}) is False


# ── the declaration is enforced ─────────────────────────────────────────────


def test_a_fragment_without_an_area_cannot_register():
    """(6) AREA is structural, like the other five. A fragment that reaches a
    user without one cannot be filtered, and "cannot be filtered" resolves to
    "shown to everyone" in any implementation that does not check."""
    from app.services.fragments.registry import register_fragment
    from app.services.fragments.types import (
        Audience,
        FragmentDeclaration,
        FragmentDeclarationError,
    )

    def _cond(db, *, user):
        return []

    base = dict(label="x", kind="non_prompt", audience=Audience.any_authenticated(),
                condition=_cond, target_surface="peek", target_key="k",
                subject_kind="company")

    with pytest.raises(FragmentDeclarationError) as e:
        register_fragment(FragmentDeclaration(fragment_id="no_area_probe", **base))
    assert "AREA" in str(e.value)

    with pytest.raises(FragmentDeclarationError) as e:
        register_fragment(
            FragmentDeclaration(fragment_id="typo_area_probe", area="payrol", **base))
    assert "payrol" in str(e.value), "a typo must name itself, not fail silently"


def test_every_registered_fragment_declares_a_real_area():
    """Membership, not spot-checks. A new fragment added in a later arc is
    covered by this the day it is written."""
    from app.core.areas import KNOWN_AREAS
    from app.services.fragments.registry import get_registry

    reg = get_registry()
    assert reg, "empty registry — this test would assert nothing"
    bad = {fid: d.area for fid, d in reg.items()
           if d.area != CROSS_AREA and d.area not in KNOWN_AREAS}
    assert bad == {}, f"fragment(s) declaring a non-area: {bad}"
