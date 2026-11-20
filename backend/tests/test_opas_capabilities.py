"""`GET /opas/capabilities` — Opas's list, composed per area on the server.

⚠️ **WHAT THESE TESTS ARE FOR.** `COMPOSED_ROUTES` warns in its own comment that
the dangerous failure is "a 200 full of somebody else's work". So every test
here asserts the SET OF IDS RETURNED, never the status code alone. A 200 with
an orders entry in it is the thing being guarded against, and a status
assertion cannot see it.

Four probe roles, created and torn down here:

    payroll-change   limited_to_areas=["payroll"]            (bare = change)
    payroll-view     limited_to_areas=["payroll:view"]       view only
    nothing          limited_to_areas=[]                     limited to NOTHING
    unlimited        an existing seeded role, areas NULL

⚠️ `limited_to_areas` IS WRITTEN THROUGH THE ORM, never as raw SQL. STATE
2026-11-17: the column is `jsonb`, and a test that wrote `'{}'` failed with
"column is of type jsonb but expression is of type text[]" in setup AND
teardown, so its assertion never ran.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import create_access_token
from app.main import app
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User

TESTCO_ID = "staging-test-001"
PFX = "opascap-"
#: Tenant resolution is by slug header in tests; without it every call 404s
#: with "Company not found", which is a harness failure and not a refusal.
HEADERS_SLUG = {"X-Company-Slug": "testco"}

#: (role suffix, limited_to_areas, permissions granted)
PROBES: tuple[tuple[str, list[str] | None, tuple[str, ...]], ...] = (
    ("change", ["payroll"], ("payroll.view", "payroll.upload")),
    ("view", ["payroll:view"], ("payroll.view", "payroll.upload")),
    ("nothing", [], ("payroll.view", "payroll.upload")),
    ("noperm", ["payroll"], ()),
    #: ⚠️ AREAS **None** = unlimited, with the SAME permissions as the
    #: limited probe. This is the only shape that isolates the area gate;
    #: see the superset test for why the seeded `office` role could not.
    ("unlimited-perms", None, ("payroll.view", "payroll.upload")),
)


def _purge(db) -> None:
    db.execute(text("DELETE FROM users WHERE id LIKE :p"), {"p": f"{PFX}user-%"})
    db.execute(text("DELETE FROM role_permissions WHERE role_id LIKE :p"), {"p": f"{PFX}role-%"})
    db.execute(text("DELETE FROM roles WHERE id LIKE :p"), {"p": f"{PFX}role-%"})


@pytest.fixture(scope="module")
def actors():
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        office_role_id = db.execute(text(
            "SELECT id FROM roles WHERE company_id=:c AND slug='office' LIMIT 1"
        ), {"c": TESTCO_ID}).scalar()
        if office_role_id is None:
            pytest.skip("testco has no 'office' role — run the role seed")
        # Control: the role being called unlimited must actually be unlimited.
        assert db.execute(text(
            "SELECT limited_to_areas IS NULL FROM roles WHERE id=:r"
        ), {"r": office_role_id}).scalar() is True, "office role is not NULL-areas"

        _purge(db)
        tokens: dict[str, str] = {}
        for suffix, areas, perms in PROBES:
            rid, uid = f"{PFX}role-{suffix}", f"{PFX}user-{suffix}"
            db.add(Role(id=rid, company_id=TESTCO_ID, name=f"Opas probe {suffix}",
                        slug=f"{PFX}{suffix}", is_system=False, is_active=True,
                        limited_to_areas=areas))
            db.flush()
            for key in perms:
                db.add(RolePermission(role_id=rid, permission_key=key))
            db.add(User(id=uid, email=f"{PFX}{suffix}@testco.example.com",
                        hashed_password="x", is_active=True,
                        first_name="Opas", last_name=suffix.title(),
                        role_id=rid, company_id=TESTCO_ID))
            tokens[suffix] = create_access_token({"sub": uid, "company_id": TESTCO_ID})

        uid = f"{PFX}user-unlimited"
        db.add(User(id=uid, email=f"{PFX}unlimited@testco.example.com",
                    hashed_password="x", is_active=True,
                    first_name="Opas", last_name="Unlimited",
                    role_id=office_role_id, company_id=TESTCO_ID))
        tokens["unlimited"] = create_access_token({"sub": uid, "company_id": TESTCO_ID})
        db.commit()

        # Control: the probe rows the assertions depend on actually exist.
        n = db.execute(text("SELECT count(*) FROM roles WHERE id LIKE :p"),
                       {"p": f"{PFX}role-%"}).scalar()
        assert n == len(PROBES), f"expected {len(PROBES)} probe roles, found {n}"

        yield tokens
    finally:
        _purge(db)
        db.commit()
        db.close()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _ids(client: TestClient, token: str) -> list[str]:
    r = client.get("/api/v1/opas/capabilities",
                   headers={"Authorization": f"Bearer {token}", **HEADERS_SLUG})
    assert r.status_code == 200, (r.status_code, r.text[:300])
    return [c["id"] for c in r.json()["capabilities"]]


def test_payroll_limited_gets_ONLY_payroll(actors, client):
    """⚠️ THE ENTRY IN `COMPOSED_ROUTES` IS A PROMISE AND THIS IS THE PROMISE.

    Asserts the exact id set — not a count, and not the status. Every id
    returned must belong to the payroll area, which is checked by reading each
    entry's own `area` field back rather than by trusting the ids to look
    payroll-shaped.
    """
    r = client.get("/api/v1/opas/capabilities",
                   headers={"Authorization": f"Bearer {actors['change']}", **HEADERS_SLUG})
    assert r.status_code == 200, r.text[:300]
    caps = r.json()["capabilities"]

    # ⚠️ THE EXACT LIST, IN ORDER — a ratchet, not a convenience. It caught
    # `payroll_union_form` being added in Payroll 5b, which is what it is for:
    # a new entry reaching an area-limited reader is a decision, and it should
    # not be possible to make it by appending to a registry.
    assert [c["id"] for c in caps] == [
        "payroll_week_review", "payroll_hours_upload", "payroll_dues_report",
        "payroll_union_form",
    ], [c["id"] for c in caps]
    assert {c["area"] for c in caps} == {"payroll"}, {c["area"] for c in caps}
    # And the control that makes the claim mean something: a non-empty answer.
    assert caps, "empty list would satisfy 'only payroll' vacuously"


def test_a_view_grant_is_NOT_offered_the_upload(actors, client):
    """A `payroll:view` role sees the week and is never offered to change it.

    ⚠️ This is the test that `area_admits_read` alone would have failed. Its own
    docstring says the level is not consulted there; the entry's `level` and
    `_level_admits` are what refuse the write, and this is what holds them.
    """
    ids = _ids(client, actors["view"])
    assert "payroll_week_review" in ids, ids
    assert "payroll_dues_report" in ids, ids
    assert "payroll_hours_upload" not in ids, (
        "a view-only grant was offered an upload; an offer that 403s is worse "
        "than no offer"
    )


def test_limited_to_NOTHING_gets_nothing(actors, client):
    """`limited_to_areas = []` is limited to nothing, and is not `None`.

    The three-outcome rule from `allowed_area_grants`, exercised end to end:
    an empty list must not fall through to the unlimited branch.
    """
    assert _ids(client, actors["nothing"]) == []


def test_permissions_still_apply_inside_the_area(actors, client):
    """In-area and still refused: no payroll permissions, no payroll entries.

    Two gates, not one. The area says which entries could exist; the permission
    says whether this user may have them. Dropping either would widen access.
    """
    assert _ids(client, actors["noperm"]) == []


def test_unlimited_AREAS_gets_at_least_what_the_limited_user_gets(actors, client):
    """An unlimited role is never offered LESS than a limited one.

    ⚠️ **THE FIRST VERSION OF THIS TEST COMPARED AGAINST THE SEEDED `office`
    ROLE AND FAILED — CORRECTLY, AND THE FAILURE IS WORTH KEEPING.** `office`
    has areas NULL, so it passes the area gate for every entry, and it holds no
    payroll permission, so it is offered nothing. Area-unlimited is NOT
    permission-unlimited, and a test that treats the two as one thing is
    asserting the very conflation `test_permissions_still_apply_inside_the_area`
    exists to deny.

    So the comparison is against a role with areas **None** and the SAME
    permissions as the limited probe — the only shape in which a difference can
    be attributed to the area filter at all.
    """
    limited = set(_ids(client, actors["change"]))
    unlimited = set(_ids(client, actors["unlimited-perms"]))
    assert limited, "control: the limited role must be offered something"
    assert limited <= unlimited, {"limited_only": sorted(limited - unlimited)}


def test_the_seeded_office_role_is_offered_NOTHING_and_that_is_correct(actors, client):
    """Area-unlimited, payroll-permissionless: an empty Opas is the right Opas.

    Kept as its own test because it is the state most users are in, and because
    it is the evidence for the docstring above rather than a claim about areas.
    """
    assert _ids(client, actors["unlimited"]) == []


def test_the_payload_omits_an_absent_hint_rather_than_sending_null(actors, client):
    """`hint` is absent when there is none — the catalog panes' own contract.

    Every entry shipped today HAS a hint, so this test would pass vacuously
    against the data alone. It therefore asserts the SHAPE RULE directly on the
    serialiser: an entry constructed without a hint must serialise without the
    key.
    """
    from app.services.opas.capabilities import OpasCapability

    bare = OpasCapability(id="x", label="X", area="payroll", level="view",
                          permission=None, phrases=("x",), target="/x")
    assert bare.hint is None
    payload = {"id": bare.id, **({"hint": bare.hint} if bare.hint else {})}
    assert "hint" not in payload, payload

    # And the live payload still carries the hints it does have, so the rule
    # above cannot be satisfied by dropping hints altogether.
    r = client.get("/api/v1/opas/capabilities",
                   headers={"Authorization": f"Bearer {actors['change']}", **HEADERS_SLUG})
    assert any("hint" in c for c in r.json()["capabilities"]), r.text[:300]


def test_typed_matching_cannot_reach_an_entry_the_caller_was_not_GIVEN(actors, client):
    """⚠️ THE TYPING PATH MUST NOT RE-OPEN WHAT THE LISTING PATH CLOSED.

    `match_phrase` takes the COMPOSED list, so a user whose list is empty
    resolves nothing however exactly she types a phrase that exists in the
    registry. Matching against `CAPABILITIES` would hand her a working shortcut
    to a surface she is not allowed to see.
    """
    from app.services.opas.capabilities import CAPABILITIES, match_phrase

    phrase = CAPABILITIES[0].phrases[0]
    assert match_phrase(phrase, list(CAPABILITIES)) is not None, (
        "control: this phrase must resolve against the full registry"
    )
    assert match_phrase(phrase, []) is None, (
        "a caller with no entries resolved a phrase anyway"
    )


def test_an_exact_match_beats_a_containment(actors, client):
    """"dues report" must resolve to the REPORTS entry, not the week.

    ⚠️ **THE FIRST VERSION OF THIS TEST COULD NOT FAIL.** It used "upload hours"
    and "payroll", and for both of those the two pass orders return the SAME
    answer — so swapping exact-first for containment-first left it green. It
    asserted true things and discriminated nothing: CLAUDE.md §11, "a check that
    passes for a reason unrelated to what it claims".

    The input below was found by enumerating the registry for a phrase that is
    exactly a LATER entry's and also CONTAINS an EARLIER entry's — "dues report"
    contains "dues", which belongs to the week. Exact-first answers the reports
    entry; containment-first answers the week. Now the break fires.
    """
    from app.services.opas.capabilities import CAPABILITIES, match_phrase

    entries = list(CAPABILITIES)
    assert match_phrase("dues report", entries).id == "payroll_dues_report"
    assert match_phrase("monthly dues", entries).id == "payroll_dues_report"
    # Containment still works when nothing matches exactly.
    assert match_phrase("I need to upload hours for this week", entries).id == (
        "payroll_hours_upload"
    )
    # And the plain word still reaches the week, which is the common request.
    assert match_phrase("payroll", entries).id == "payroll_week_review"


def test_the_route_is_composed_and_not_common(actors, client):
    """The guard must step aside for exactly this one method+path.

    ⚠️ `is_common` is asserted FALSE deliberately. A Phase 0 report once claimed
    a route was in `COMMON_ROUTES` when it was not, and the difference matters:
    common means "the area check does not apply", composed means "the handler
    filters and is accountable for it".
    """
    from app.core.areas import is_common, is_composed

    assert is_composed("GET", "/opas/capabilities") is True
    assert is_common("GET", "/opas/capabilities") is False
    # Exact, not prefix: a write under /opas must not inherit the exemption.
    assert is_composed("POST", "/opas/capabilities") is False
    assert is_composed("GET", "/opas/anything-else") is False


def test_the_two_matchers_AGREE_on_the_shared_case_table():
    """⚠️ THE RULE IS IMPLEMENTED TWICE AND THIS IS WHAT HOLDS THEM TOGETHER.

    `match_phrase` here and `matchCapability` in
    `frontend/src/services/opas-capabilities-service.ts` resolve the same typed
    phrase, because doing it on the client avoids a round trip per keystroke and
    doing it on the server is what the listing path already trusts. Two
    implementations of one rule drift; when they do, the client opens a
    different surface from the one the server would have named.

    So both read `frontend/src/components/opas/capability-match-cases.json`.
    This test asserts the SERVER agrees with every row; the vitest file asserts
    the CLIENT does. A change to either matcher that is not made to both turns
    one of them red.

    ⚠️ Precedent for a backend test reading a frontend file:
    `test_the_done_strings_AGREE_across_the_two_surfaces`, which exists for the
    same reason about the same subsystem.
    """
    import json
    from pathlib import Path

    from app.services.opas.capabilities import CAPABILITIES, match_phrase

    root = Path(__file__).resolve().parents[2]
    table = root / "frontend/src/components/opas/capability-match-cases.json"
    assert table.exists(), f"shared case table not found at {table}"
    cases = json.loads(table.read_text())["cases"]
    # Control: a path that resolved to an empty or tiny table would make this
    # test pass by having nothing to check.
    assert len(cases) >= 14, f"only {len(cases)} cases — table looks wrong"
    assert any(c["typed"] == "dues report" for c in cases), (
        "the discriminating case is missing from the shared table"
    )

    by_id = {e.id: e for e in CAPABILITIES}
    sets = {
        "all": list(CAPABILITIES),
        "none": [],
        "view_only": [by_id["payroll_week_review"], by_id["payroll_dues_report"]],
    }

    for c in cases:
        got = match_phrase(c["typed"], sets[c["entries"]])
        assert (got.id if got else None) == c["expect"], (
            f'typed {c["typed"]!r} over {c["entries"]}: '
            f'server said {got.id if got else None!r}, table says {c["expect"]!r}'
            + (f' — {c["why"]}' if c.get("why") else "")
        )


def test_the_week_entries_are_SCOPED_to_the_week_being_worked(actors, client):
    """⚠️ AN UNSCOPED FOCUS TARGET OPENS NOTHING, FOUND IN THE WALK-THROUGH.

    Picking "This week's payroll" navigated to `/home?focus=weekly-payroll`
    and the Focus did not render — the page showed the note under a URL that
    claimed a surface. The note's own line already used the working shape, so
    the week entries carry `week_end` and the endpoint fills it.

    Asserts the DATE, derived here from the calendar rather than copied from
    the endpoint's output — an expected value taken from the thing under test
    cannot test it.
    """
    from datetime import date, timedelta

    from app.services.payroll.week_calendar import WEEK_END_WEEKDAY

    today = date.today()
    expected = (today - timedelta(days=(today.weekday() - WEEK_END_WEEKDAY) % 7)).isoformat()

    r = client.get("/api/v1/opas/capabilities",
                   headers={"Authorization": f"Bearer {actors['change']}", **HEADERS_SLUG})
    caps = {c["id"]: c["target"] for c in r.json()["capabilities"]}

    assert caps["payroll_week_review"] == f"focus:weekly-payroll?week_end={expected}"
    assert caps["payroll_hours_upload"] == f"focus:weekly-payroll?week_end={expected}#upload"
    # ⚠️ AND NO PLACEHOLDER SURVIVES INTO THE PAYLOAD. An unfilled `{week_end}`
    # would reach the browser as a literal and navigate to a week named
    # "{week_end}" — which is the unscoped failure wearing a date's clothes.
    for target in caps.values():
        assert "{" not in target, target

    # The route entry is untouched by any of this.
    assert caps["payroll_dues_report"] == "/payroll"
