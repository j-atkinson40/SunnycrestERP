"""Area-limited roles: default deny, and no change for everyone else.

⚠️ **WHAT THIS REPLACES.** Measured 2026-11-03: 1063 of 1920 tenant endpoints had
no per-user authorization and 886 had no handler-level check either, so a user on
any non-admin role could read journal entries, GL accounts, price lists, CRM
companies, FH cases and email threads. Gating them individually was 886 edits and
886 chances to miss one, plus every future endpoint. `enforce_area_limit` closes
them for a limited role in one place.

The two halves this file has to prove are in tension, which is why both are here:

  (a) a limited role is refused everything outside its areas, AND
  (b) every EXISTING role behaves exactly as it did — identical sets, not
      identical counts.

(b) is the one that would quietly break the tenant. It is asserted against the
same 20-endpoint probe used to find the problem, as a SET.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import create_access_token
from app.main import app
from app.models.role import Role
from app.models.user import User
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

_canonical_tenant = make_canonical_tenant_fixture()

LIMITED_ROLE_ID = "area-probe-limited-role"
LIMITED_USER_ID = "area-probe-limited-user"
UNLIMITED_USER_ID = "area-probe-office-user"

#: The exact 20 read-only calls used in the 2026-11-03 investigation.
PROBE = [
    "/api/v1/journal-entries/entries",
    "/api/v1/journal-entries/gl-accounts",
    "/api/v1/price-management/current-prices",
    "/api/v1/price-management/versions",
    "/api/v1/companies",
    "/api/v1/companies/search?q=a",
    "/api/v1/companies/funeral-homes",
    "/api/v1/companies/health-summary",
    "/api/v1/fh/cases",
    "/api/v1/agents/alerts",
    "/api/v1/agents/activity-log",
    "/api/v1/agents/periods/locked",
    "/api/v1/email/threads",
    "/api/v1/reports/available",
    "/api/v1/statements/runs",
    "/api/v1/employees",
    "/api/v1/customers",
    "/api/v1/products",
    "/api/v1/invoices",
    "/api/v1/vendors",
]

#: The 11 that returned 200 to a user with no permissions. Every one must now be
#: refused to a limited user. Named individually so a shrinking list is a
#: visible change rather than a smaller number.
REACHABLE_BEFORE = [
    "/api/v1/journal-entries/entries",
    "/api/v1/journal-entries/gl-accounts",
    "/api/v1/price-management/current-prices",
    "/api/v1/price-management/versions",
    "/api/v1/companies",
    "/api/v1/companies/search?q=a",
    "/api/v1/fh/cases",
    "/api/v1/agents/alerts",
    "/api/v1/agents/activity-log",
    "/api/v1/agents/periods/locked",
    "/api/v1/email/threads",
]

HEADERS_SLUG = {"X-Company-Slug": "testco"}


def _mk_user(db, user_id: str, role_id: str, email: str) -> None:
    db.execute(text("DELETE FROM users WHERE id=:u"), {"u": user_id})
    db.add(User(id=user_id, email=email, hashed_password="not-a-credential",
                first_name="Area", last_name="Probe",
                role_id=role_id, company_id=TESTCO_ID))


@pytest.fixture(scope="module")
def actors():
    """A limited role + user, and a user on an EXISTING unlimited role.

    ⚠️ **THE UNLIMITED CONTROL IS `admin`, AND IT USED TO BE `office`.** The
    original reasoning is preserved because it was sound and then stopped
    being true: *"deliberately an already-seeded role (`office`), not a fresh
    one: the claim being tested is about roles that exist today."* Phase B
    (2026-11-06) gave `office` an area list, so the role this fixture called
    unlimited stopped being unlimited and its own precondition assert fired —
    16 errors across every test using this fixture, all from one line.

    `admin` is the right control now and not merely an available one: its
    absence from `PLANNED_ROLE_AREAS` is the RECORDED DECISION that an admin
    stays unrestricted, so this control rests on a decision rather than on a
    role that happens not to have been limited yet. James's ruling: a fixture
    needing an unlimited user creates one explicitly, it does not rely on a
    default.
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        unlimited_role_id = db.execute(text(
            "SELECT id FROM roles WHERE company_id=:c AND slug='admin' LIMIT 1"
        ), {"c": TESTCO_ID}).scalar()
        if unlimited_role_id is None:
            pytest.skip("testco has no 'admin' role — run the role seed")

        # ⚠️ The control still runs, and it is still the right control: whatever
        # role this fixture calls unlimited must actually be unlimited. It now
        # points at `admin`, whose NULL is a decision rather than an accident.
        assert db.execute(text(
            "SELECT limited_to_areas IS NULL FROM roles WHERE id=:r"
        ), {"r": unlimited_role_id}).scalar() is True, (
            "the admin role is not NULL-areas — admin must stay unrestricted; "
            "see PLANNED_ROLE_AREAS, which omits it deliberately"
        )

        db.execute(text("DELETE FROM users WHERE id IN (:a,:b)"),
                   {"a": LIMITED_USER_ID, "b": UNLIMITED_USER_ID})
        db.execute(text("DELETE FROM role_permissions WHERE role_id=:r"),
                   {"r": LIMITED_ROLE_ID})
        db.execute(text("DELETE FROM roles WHERE id=:r"), {"r": LIMITED_ROLE_ID})
        db.add(Role(id=LIMITED_ROLE_ID, company_id=TESTCO_ID,
                    name="Area Probe Limited", slug="area-probe-limited",
                    is_system=False, is_active=True,
                    limited_to_areas=["payroll"]))
        db.flush()
        _mk_user(db, LIMITED_USER_ID, LIMITED_ROLE_ID, "area-limited@testco.example.com")
        _mk_user(db, UNLIMITED_USER_ID, unlimited_role_id, "area-admin@testco.example.com")
        db.commit()

        yield {
            "limited": create_access_token({"sub": LIMITED_USER_ID, "company_id": TESTCO_ID}),
            "unlimited": create_access_token({"sub": UNLIMITED_USER_ID, "company_id": TESTCO_ID}),
            "unlimited_role_id": unlimited_role_id,
            # Kept under the old key so callers need no edit; the VALUE is
            # now the admin role id, which is what "unlimited" means here.
            "office_role_id": unlimited_role_id,
        }
    finally:
        db.execute(text("DELETE FROM users WHERE id IN (:a,:b)"),
                   {"a": LIMITED_USER_ID, "b": UNLIMITED_USER_ID})
        db.execute(text("DELETE FROM role_permissions WHERE role_id=:r"),
                   {"r": LIMITED_ROLE_ID})
        db.execute(text("DELETE FROM roles WHERE id=:r"), {"r": LIMITED_ROLE_ID})
        db.commit()
        db.close()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _probe(client, token: str) -> dict[str, int]:
    out = {}
    for path in PROBE:
        r = client.get(path, headers={"Authorization": f"Bearer {token}", **HEADERS_SLUG})
        out[path] = r.status_code
    return out


# ------------------------------------------------------- (a) the break test


def test_a_limited_role_is_refused_every_endpoint_outside_its_areas(client, actors):
    """⚠️ THE BREAK TEST. All 11 of these returned 200 before the guard."""
    results = _probe(client, actors["limited"])
    still_reachable = [p for p in REACHABLE_BEFORE if results[p] == 200]
    assert still_reachable == [], (
        "a payroll-limited user can still reach:\n  " + "\n  ".join(still_reachable)
    )
    for p in REACHABLE_BEFORE:
        assert results[p] == 403, f"{p} -> {results[p]}, expected 403"


def test_the_refusal_names_itself(client, actors):
    """A bare 403 is indistinguishable from a permission failure. This one says
    which areas the account holds, so a support call takes one request."""
    r = client.get("/api/v1/journal-entries/entries",
                   headers={"Authorization": f"Bearer {actors['limited']}", **HEADERS_SLUG})
    assert r.status_code == 403
    detail = r.json()["detail"]
    assert detail["code"] == "area_restricted"
    assert detail["allowed_areas"] == ["payroll"]
    # ⚠️ **WAS `is None` UNTIL PHASE A TAGGED THE ROUTERS, AND THE CHANGE IS AN
    # IMPROVEMENT RATHER THAN A REGRESSION — BUT IT IS A CHANGE.** Before
    # tagging, `journal-entries` declared no area, so the guard refused it with
    # `reason="untagged"` and reported `requested_area: None`. It now declares
    # `accounting`, so the refusal reads `out_of_area` and names it.
    #
    # The DISTINCTION those two reasons exist for is exactly this: untagged
    # means somebody shipped a route without an area and it is a bug report;
    # out_of_area means she asked for someone else's area and it is a
    # permission question. Phase A moves 1,600 method+path pairs from the first
    # category to the second.
    #
    # ⚠️ Her REACH does not change — 403 either way — which is what "Phase A is
    # inert" claims. The refusal BODY changes, and claiming otherwise would be
    # overstating the inertness.
    assert detail["requested_area"] == "accounting", (
        "journal-entries should declare area:accounting after Phase A tagging"
    )


def test_every_probe_endpoint_is_refused_not_merely_the_eleven(client, actors):
    """None of the 20 is reachable — including the ones that already 403'd, so a
    permission regression cannot hide behind the area guard."""
    results = _probe(client, actors["limited"])
    assert [p for p, s in results.items() if s == 200] == []


# ------------------------------- (b) zero change for unlimited roles


def test_an_existing_office_user_sees_exactly_what_it_saw_before(client, actors):
    """⚠️ SETS, NOT COUNTS.

    The recorded baseline is the office user's own result set, captured with the
    guard unwired (see the A/B in the commit message). Equal counts with
    different membership is the failure this asserts against — a guard that
    refused `/customers` and started allowing `/products` would keep the count.
    """
    results = _probe(client, actors["unlimited"])
    assert not any(
        isinstance(r, dict) for r in results.values()
    )  # sanity: all plain status codes

    # The office role is NULL-areas, so the guard must return before it can
    # refuse anything. Any 403 carrying our code is a behaviour change.
    for path, status in results.items():
        if status != 403:
            continue
        r = client.get(path, headers={"Authorization": f"Bearer {actors['unlimited']}",
                                      **HEADERS_SLUG})
        body = r.json()
        detail = body.get("detail")
        assert not (isinstance(detail, dict) and detail.get("code") == "area_restricted"), (
            f"{path} was refused by the AREA guard for an unlimited role"
        )


def test_the_guard_returns_early_for_a_null_areas_role(actors):
    """The mechanism behind (b), asserted directly rather than inferred from
    endpoint behaviour."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        got = db.execute(text("SELECT limited_to_areas FROM roles WHERE id=:r"),
                         {"r": actors["office_role_id"]}).scalar()
        assert got is None
    finally:
        db.close()


def test_the_only_limited_roles_are_the_ones_declared_limited():
    """⚠️ A RATCHET OVER WHICH ROLES ARE LIMITED, not a blanket "none are".

    This asserted `non_null == 0` and was correct until the `payroll` role landed
    — the first DELIBERATELY limited role. Loosening it to "ignore payroll" would
    have made it blind to the next role that acquires areas by accident, which is
    the thing actually worth guarding: a stray `limited_to_areas` on `office` or
    `driver` would silently narrow every such user's reach across every tenant.

    So the invariant is membership: the set of limited role slugs in the database
    must equal the set declared limited in `_SYSTEM_ROLES`. Both directions fail
    loudly — an undeclared role acquiring areas, and a declared one losing them.
    """
    from app.database import SessionLocal
    from app.services.role_service import _SYSTEM_ROLES

    # ⚠️ **PHASE B MOVED WHERE "DECLARED" LIVES, AND THIS READ THE OLD PLACE.**
    # Until 2026-11-06 a role declared its limit as an explicit
    # `limited_to_areas` key on its `_SYSTEM_ROLES` entry, and only `payroll`
    # had one. Phase B's limits come from `PLANNED_ROLE_AREAS` via
    # `_planned_area_limit()` at seed time, so reading the entry dicts alone
    # found one declared slug against nine limited in the database — and the
    # ratchet fired on its own correct behaviour.
    #
    # The invariant is unchanged and still worth having: limited-in-the-database
    # must be a subset of declared-somewhere. It now reads BOTH declaration
    # sites, which is what the seed does.
    from app.core.areas import PLANNED_ROLE_AREAS

    declared = {r["slug"] for r in _SYSTEM_ROLES if r.get("limited_to_areas") is not None}
    declared |= set(PLANNED_ROLE_AREAS)
    assert declared, "no system role declares areas — this test would assert nothing"
    # ⚠️ And admin must be in NEITHER source, or an unrestricted admin has
    # quietly stopped being the decision it is recorded as.
    assert "admin" not in declared, "admin must not declare an area limit"

    db = SessionLocal()
    try:
        total = db.execute(text(
            "SELECT count(*) FROM roles WHERE id NOT LIKE 'area-probe-%'"
        )).scalar()
        limited = {r[0] for r in db.execute(text(
            "SELECT DISTINCT slug FROM roles "
            "WHERE limited_to_areas IS NOT NULL AND id NOT LIKE 'area-probe-%'"
        )).fetchall()}
    finally:
        db.close()

    assert total > 0, "no roles examined — the query is not reaching the table"
    unexpected = limited - declared
    assert unexpected == set(), (
        f"role slug(s) carry limited_to_areas without declaring it in "
        f"_SYSTEM_ROLES: {sorted(unexpected)}. A role limited by accident "
        f"narrows every user on it, at every tenant."
    )


# ------------------------------------------------- the common set works


COMMON_SMOKE = [
    ("/api/v1/auth/me", "identity, permissions and modules — nothing renders without it"),
    ("/api/v1/feature-flags/me", "FeatureFlagProvider, second in the boot chain"),
    ("/api/v1/spaces", "SpaceProvider + DotNav, per-user rows"),
]


@pytest.mark.parametrize("path,why", COMMON_SMOKE)
def test_a_limited_user_can_still_sign_in_and_render_the_shell(client, actors, path, why):
    """⚠️ IF THIS FAILS SHE CANNOT LOG IN. The whole slice is pointless if the
    guard also refuses the shell."""
    r = client.get(path, headers={"Authorization": f"Bearer {actors['limited']}", **HEADERS_SLUG})
    assert r.status_code != 403, f"{path} refused ({why}): {r.text[:200]}"
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"


def test_an_empty_area_list_is_not_the_same_as_null(client, actors):
    """`[]` means limited to nothing: common set only, everything else refused."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        db.execute(text("UPDATE roles SET limited_to_areas='[]'::jsonb WHERE id=:r"),
                   {"r": LIMITED_ROLE_ID})
        db.commit()
        r = client.get("/api/v1/auth/me",
                       headers={"Authorization": f"Bearer {actors['limited']}", **HEADERS_SLUG})
        assert r.status_code == 200, "the common set must survive an empty area list"
        r2 = client.get("/api/v1/journal-entries/entries",
                        headers={"Authorization": f"Bearer {actors['limited']}", **HEADERS_SLUG})
        assert r2.status_code == 403
        assert r2.json()["detail"]["allowed_areas"] == []
    finally:
        db.execute(text("UPDATE roles SET limited_to_areas='[\"payroll\"]'::jsonb WHERE id=:r"),
                   {"r": LIMITED_ROLE_ID})
        db.commit()
        db.close()


def test_unauthenticated_requests_are_refused_by_the_endpoint_not_the_guard(client):
    """The guard must be silent without a token, or `/auth/login` would 403 and
    nobody could sign in at all."""
    r = client.post("/api/v1/auth/login", headers=HEADERS_SLUG,
                    json={"email": "nobody@testco.example.com", "password": "wrong"})
    assert r.status_code != 403, f"login answered 403: {r.text[:200]}"
    detail = r.json().get("detail")
    assert not (isinstance(detail, dict) and detail.get("code") == "area_restricted")


# ------------------------------------------------------ registry integrity


def test_every_area_tag_in_the_app_names_a_known_area():
    """A typo'd `area:payrol` tag would make a router unreachable to every
    limited role and reachable to none — silently."""
    from fastapi.routing import APIRoute
    from app.core.areas import AREA_TAG_PREFIX, KNOWN_AREAS

    seen = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for tag in getattr(route, "tags", None) or ():
            if isinstance(tag, str) and tag.startswith(AREA_TAG_PREFIX):
                seen.add(tag[len(AREA_TAG_PREFIX):])
    unknown = seen - set(KNOWN_AREAS)
    assert unknown == set(), f"area tags naming unknown areas: {sorted(unknown)}"
    # ⚠️ NON-ZERO CONTROL: an empty `seen` would satisfy the assertion above
    # trivially, and would mean no router is tagged at all.
    assert seen, "no route carries an area: tag — the guard would deny everything"


def _route_pairs():
    """Every (method, template) the app serves under /api/v1, mount stripped."""
    from fastapi.routing import APIRoute
    from app.core.areas import strip_mount_prefix

    out = set()
    for r in app.routes:
        if not isinstance(r, APIRoute) or not r.path.startswith("/api/v1/"):
            continue
        rel = strip_mount_prefix(r.path)
        for m in (r.methods or set()) - {"HEAD", "OPTIONS"}:
            out.add((m, rel))
    return out


def test_common_routes_are_real_routes():
    """A stale entry grants nothing and reads as protection.

    ⚠️ Stricter than the prefix version it replaces: that one passed if ANY
    route merely started with the string, so a renamed endpoint left the entry
    looking alive. An exact pair either exists or it does not.
    """
    from app.core.areas import COMMON_ROUTES

    pairs = _route_pairs()
    missing = [(m, p) for m, p, _r in COMMON_ROUTES if (m, p) not in pairs]
    assert missing == [], f"common entries matching no route: {missing}"


def test_common_set_admits_only_what_it_lists():
    """⚠️ THE REGRESSION GUARD FOR THE WHOLE CLASS.

    The old form was a prefix, so every sibling route anyone added under it
    later was admitted silently — including writes. This asserts the common set
    admits EXACTLY its own listing and nothing adjacent, so a new
    `/locations/something` is denied on the day it ships rather than on the day
    somebody probes production.
    """
    from app.core.areas import COMMON_ROUTES, is_common

    listed = {(m, p) for m, p, _r in COMMON_ROUTES}
    admitted = {(m, p) for (m, p) in _route_pairs() if is_common(m, "/api/v1" + p)}
    assert admitted == listed, (
        f"admitted but not listed: {sorted(admitted - listed)}\n"
        f"listed but not admitted: {sorted(listed - admitted)}"
    )


def test_locations_users_is_not_reachable():
    """⚠️ THE DISCLOSURE, PINNED BY NAME.

    Measured on production 2026-11-06: a payroll-limited user could
    `GET /locations/users` and read another user's row with
    `access_level='admin'`. The endpoint's own docstring is "List all
    user-location access assignments for the company" and its only gate is
    `get_current_user` + company_id, so the area guard was the only thing that
    could have refused it, and the `/locations` prefix admitted it instead.

    Named rather than folded into the exactness test above because a future
    edit could satisfy that test while putting this route back on the list.
    """
    from app.core.areas import is_common

    assert not is_common("GET", "/api/v1/locations/users")
    # The control: the facility list its reason actually describes stays open,
    # so this test cannot pass by denying the whole prefix.
    assert is_common("GET", "/api/v1/locations")


def test_the_locations_writes_no_longer_reach_their_own_gate():
    """They stay `require_admin` at the endpoint; they also stop getting here.

    Defence in depth rather than a replacement for it — `require_admin` was and
    remains what refuses them, and this asserts the guard no longer waves them
    through to it.
    """
    from app.core.areas import is_common

    for method, path in (
        ("POST", "/api/v1/locations"),
        ("POST", "/api/v1/locations/users"),
        ("PATCH", "/api/v1/locations/{location_id}"),
        ("DELETE", "/api/v1/locations/{location_id}"),
        ("DELETE", "/api/v1/locations/users/{access_id}"),
    ):
        assert not is_common(method, path), f"{method} {path} is still admitted"


def test_an_exact_match_is_not_a_prefix_match():
    """The property the change buys, stated as a test rather than a comment."""
    from app.core.areas import is_common

    assert is_common("GET", "/api/v1/auth/me")
    assert not is_common("GET", "/api/v1/authorization-sneaky")
    assert not is_common("GET", "/api/v1/feature-flags/matrix")
    assert not is_common("GET", "/api/v1/journal-entries/entries")
    # ⚠️ The method matters now. Same path, different verb, different answer.
    assert is_common("PATCH", "/api/v1/edge-panel/preferences")
    assert not is_common("DELETE", "/api/v1/edge-panel/preferences")
    # And the deprecated /api alias resolves the same, or it is a way around.
    assert is_common("GET", "/api/auth/me")


def test_register_is_not_in_the_common_set():
    """It was admitted by the old `/auth` prefix and named by nothing.

    ⚠️ **THIS ASSERTION IS NOW VACUOUS ON ITS OWN AND SAYS SO RATHER THAN
    READING AS PROTECTION.** The endpoint was deleted hours after this test was
    written — `is_common` returns False for a route that does not exist, so the
    line below would pass whether or not the allowlist had been fixed. A check
    that cannot distinguish "correctly excluded" from "absent" is documentation.
    The live guard is `test_auth_register_is_gone_and_stays_gone` in
    `test_service_territories_requires_login.py`, which asserts the route is
    absent from the app and fires when it comes back.

    Kept because if the endpoint is ever reinstated, this must ALSO be false —
    and the pair of the two is what makes a reinstatement loud.
    """
    from app.core.areas import is_common

    assert not is_common("POST", "/api/v1/auth/register")

    # ⚠️ The non-vacuity control: the allowlist still admits something, so a
    # scanner returning False for everything cannot satisfy the line above.
    assert is_common("GET", "/api/v1/auth/me")


def test_the_guard_covers_both_router_mounts():
    """v1_router is mounted at /api/v1 AND at the deprecated /api alias. A guard
    on one mount would leave the other as a way around it."""
    from fastapi.routing import APIRoute

    def dep_names(dep, out, seen):
        if id(dep) in seen:
            return
        seen.add(id(dep))
        call = getattr(dep, "call", None)
        if call is not None:
            out.add(getattr(call, "__name__", repr(call)))
        for sub in getattr(dep, "dependencies", []) or []:
            dep_names(sub, out, seen)

    v1, alias, v1_g, alias_g = 0, 0, 0, 0
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        names: set[str] = set()
        dep_names(route.dependant, names, set())
        guarded = "enforce_area_limit" in names
        if route.path.startswith("/api/v1/"):
            v1 += 1
            v1_g += guarded
        elif route.path.startswith("/api/") and not route.path.startswith("/api/platform"):
            if route.path.rstrip("/") == "/api/health":
                continue
            alias += 1
            alias_g += guarded

    assert v1 > 1000, f"only {v1} /api/v1 routes seen — walker not reaching the table"
    assert v1_g == v1, f"{v1 - v1_g} of {v1} /api/v1 routes unguarded"
    assert alias > 1000, f"only {alias} alias routes seen"
    assert alias_g == alias, f"{alias - alias_g} of {alias} alias routes unguarded"


def test_a_limited_user_reaches_her_OWN_area(client, actors):
    """⚠️ THE ALLOW PATH. Without this the guard could be a blanket deny and
    every test above would still pass — a default-deny that denies everything is
    not the feature, it is an outage.

    `/payroll-reports/formats` is tagged `area:payroll`, which the probe role
    holds. It must NOT be refused by the area guard. It may still be refused by
    the endpoint's own permission gate (this role holds no payroll.view until
    commit 3) — so the assertion is specifically that the refusal, if any, does
    not come from the area guard.
    """
    r = client.get("/api/v1/payroll-reports/formats",
                   headers={"Authorization": f"Bearer {actors['limited']}", **HEADERS_SLUG})
    detail = r.json().get("detail") if r.headers.get("content-type", "").startswith("application/json") else None
    assert not (isinstance(detail, dict) and detail.get("code") == "area_restricted"), (
        f"her own area was refused by the AREA guard: {r.status_code} {r.text[:200]}"
    )


def test_a_null_area_list_is_stored_as_SQL_NULL_not_JSON_null():
    """⚠️ REGRESSION. r221 declared `limited_to_areas` as plain `JSONB`, and
    SQLAlchemy writes Python `None` into a JSONB column as the JSON VALUE `null`
    unless the column says `none_as_null=True`. So every role the seeder created
    held `'null'`, and `limited_to_areas IS NULL` was FALSE for all of them.

    The area guard was never affected — it tests the Python value, and JSON null
    reads back as `None` — so nobody gained or lost access. What broke was every
    SQL query over the column, including r223's divergence check and three
    assertions in this repo's own tests.

    ⚠️ **AND A DEV DATABASE CANNOT SEE IT.** Local roles predate the column and
    `seed_default_roles` skips roles that already exist, so nothing local was
    ever inserted with `None`. CI builds from scratch and failed on the first
    run — the "suite that has only ever run against one database state" shape.
    This test creates the row itself, so it does not depend on which database it
    runs against.
    """
    import uuid as _uuid
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role

    db = SessionLocal()
    cid = str(_uuid.uuid4())
    try:
        db.add(Company(id=cid, slug=f"jsonnull-reg-{cid[:8]}", name="JSON null regression"))
        db.flush()
        role = Role(company_id=cid, name="Unlimited", slug="unlimited-probe",
                    limited_to_areas=None)
        db.add(role)
        db.commit()

        row = db.execute(text(
            "SELECT limited_to_areas IS NULL AS sql_null, "
            "       jsonb_typeof(limited_to_areas) AS json_type "
            "FROM roles WHERE id = :i"
        ), {"i": role.id}).first()

        assert row.sql_null is True, (
            "limited_to_areas=None stored something that is not SQL NULL "
            f"(jsonb_typeof={row.json_type!r}) — the column needs "
            "JSONB(none_as_null=True), and every IS NULL query over it is wrong"
        )
        assert row.json_type is None, f"jsonb_typeof returned {row.json_type!r}"

        # And the Python read-back is None either way, which is why the guard
        # never misbehaved — asserted so the next reader does not mistake this
        # for a security bug.
        db.expire_all()
        assert db.query(Role).filter(Role.id == role.id).first().limited_to_areas is None
    finally:
        db.execute(text("DELETE FROM roles WHERE company_id=:c"), {"c": cid})
        db.execute(text("DELETE FROM companies WHERE id=:c"), {"c": cid})
        db.commit()
        db.close()


def test_an_empty_area_list_is_refused_as_area_restricted_not_as_two_step(client, actors):
    """⚠️ THE REFUSAL CODE MUST NAME THE RIGHT REMEDY.

    Payroll 2 unions `mfa_enroll` into every limited role's reach, so the
    guard's `allowed` set for a role with `limited_to_areas = []` became
    `{'mfa_enroll'}` — identical to the set a user who owes a second step gets.
    Both refusal-code discriminators compared against that set, so this user
    would have been told to finish setting up two-step when her real problem is
    that an admin granted her no areas at all. Two different remedies: one
    sends her to an enrolment page, the other to her administrator.

    ⚠️ NOTHING WAS RED WHEN THAT HAPPENED. The sibling test above asserts the
    REPORTED areas and not the code, so the collision was invisible. Found by
    reading the branch after changing the set it compares against, which is the
    one moment the question gets asked.
    """
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        db.execute(text("UPDATE roles SET limited_to_areas='[]'::jsonb WHERE id=:r"),
                   {"r": LIMITED_ROLE_ID})
        db.commit()
        r = client.get("/api/v1/journal-entries/entries",
                       headers={"Authorization": f"Bearer {actors['limited']}", **HEADERS_SLUG})
        assert r.status_code == 403, r.text
        detail = r.json()["detail"]
        assert detail["code"] == "area_restricted", (
            f"an area-restricted user was told to enrol in two-step: {detail}"
        )
        assert detail["allowed_areas"] == [], detail
    finally:
        db.execute(text("UPDATE roles SET limited_to_areas='[\"payroll\"]'::jsonb WHERE id=:r"),
                   {"r": LIMITED_ROLE_ID})
        db.commit()
        db.close()


# ─────────────────── the disclosure, at the HTTP layer (2026-11-06)


def test_locations_users_is_refused_over_http(client, actors):
    """⚠️ **THE BREAK TEST JAMES NAMED, AT THE LAYER THE LEAK HAPPENED ON.**

    Measured on production 2026-11-06: a payroll-limited user could
    `GET /locations/users` and read another user's row with
    `access_level='admin'`. The endpoint's own docstring is "List all
    user-location access assignments for the company"; its only gate is
    `get_current_user` + company_id, so the area guard was the only thing that
    could refuse it, and the `/locations` PREFIX admitted it instead.

    The `is_common` unit test next to this pins the rule. This pins the
    OUTCOME — a prefix reinstated anywhere between here and the router would
    satisfy the unit test's inputs and still serve the row.
    """
    h = {"Authorization": f"Bearer {actors['limited']}", **HEADERS_SLUG}

    refused = client.get("/api/v1/locations/users", headers=h)
    assert refused.status_code == 403, (
        f"/locations/users served {refused.status_code} to an area-limited user: "
        f"{refused.text[:300]}"
    )
    assert refused.json()["detail"]["code"] == "area_restricted"

    # ⚠️ THE CONTROL, AND IT IS WHAT MAKES THE ASSERTION ABOVE MEAN SOMETHING.
    # Denying the whole prefix would satisfy the refusal and break the boot
    # chain — `LocationProvider` sits above the route tree, so a 403 here
    # throws over every page. The facility list its stated reason actually
    # describes must still be reachable.
    allowed = client.get("/api/v1/locations", headers=h)
    assert allowed.status_code == 200, (
        f"/locations refused ({allowed.status_code}) — this test cannot pass by "
        f"denying the prefix, which would stop her signing in: {allowed.text[:200]}"
    )


@pytest.mark.parametrize("path", [
    "/api/v1/locations/users",
    "/api/v1/locations/overview",
])
def test_the_other_locations_siblings_are_refused_too(client, actors, path):
    """The prefix admitted nine siblings. Two are parameterless and probed here.

    `/locations/{id}` and `/locations/{id}/summary` need an id and are covered
    by the `is_common` unit assertions instead — a guessed id returns 404 and
    would tell us nothing about authorization.
    """
    r = client.get(path, headers={"Authorization": f"Bearer {actors['limited']}", **HEADERS_SLUG})
    assert r.status_code == 403, f"{path} -> {r.status_code}"


def test_auth_me_reports_the_area_limit(client, actors):
    """The one source of truth the frontend nav reads.

    ⚠️ Without this field the frontend has to keep its own list, which is what
    it was doing — `employee_profiles.functional_areas`, a different concept on
    a different table. Hers was `[]` and the nav read empty as "unrestricted",
    so she saw six hubs the server refused.
    """
    r = client.get("/api/v1/auth/me",
                   headers={"Authorization": f"Bearer {actors['limited']}", **HEADERS_SLUG})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "limited_to_areas" in body, "nav has nothing to filter by"
    assert body["limited_to_areas"] == ["payroll"], body["limited_to_areas"]

    # ⚠️ CONTROL: `functional_areas` is still reported and is still a DIFFERENT
    # value. If these two ever coincide the test stops discriminating, so the
    # distinction is asserted rather than assumed.
    assert "functional_areas" in body
    assert body["functional_areas"] != body["limited_to_areas"], (
        "functional_areas and limited_to_areas are indistinguishable here, so "
        "this test can no longer tell which one the nav is reading"
    )


def test_auth_me_reports_null_for_an_unlimited_user(client, actors):
    """⚠️ `null`, NOT `[]`. The frontend treats them differently and must.

    `null` means no limit and leaves the nav byte-for-byte unchanged; `[]`
    means limited to nothing. Returning `[]` here would hide every nav item
    from every ordinary user.
    """
    r = client.get("/api/v1/auth/me",
                   headers={"Authorization": f"Bearer {actors['unlimited']}", **HEADERS_SLUG})
    assert r.status_code == 200, r.text
    assert r.json()["limited_to_areas"] is None, r.json()["limited_to_areas"]


# ─────────────────────────── Phase A: the tagging inventory (2026-11-06)


def _tenant_routes():
    """Every (method, path, area-tags) under /api/v1."""
    from fastapi.routing import APIRoute

    out = []
    for r in app.routes:
        if not isinstance(r, APIRoute) or not r.path.startswith("/api/v1/"):
            continue
        areas = sorted({t[5:] for t in (r.tags or ())
                        if isinstance(t, str) and t.startswith("area:")})
        for m in sorted((r.methods or set()) - {"HEAD", "OPTIONS"}):
            out.append((m, r.path, areas))
    return out


def test_every_tenant_route_carries_exactly_one_area_or_is_declared_composed():
    """⚠️ PHASE A's RULE, AND IT IS PER ROUTE RATHER THAN PER ROUTER ON PURPOSE.

    My first version aggregated by top-level segment, and that version PASSED
    while `driver_announcements` sat untagged: it mounts with `prefix=""` and
    serves `/driver/announcements`, so the `driver` segment already carried
    `area:scheduling` from the real driver router and the untagged routes
    hid inside it. A segment-level check cannot see an untagged route in a
    tagged segment, which is precisely the case worth catching.
    """
    from app.core.areas import COMPOSED_SURFACES, KNOWN_AREAS, is_common

    composed = {name for name, _reason in COMPOSED_SURFACES}
    undeclared, multi, unknown = [], [], []
    for method, path, areas in _tenant_routes():
        if is_common(method, path):
            continue
        seg = path.split("/")[3]
        if seg in composed:
            continue
        if len(areas) > 1:
            multi.append(f"{method} {path} -> {areas}")
        elif not areas:
            undeclared.append(f"{method} {path}")
        elif areas[0] not in KNOWN_AREAS:
            unknown.append(f"{method} {path} -> {areas[0]}")

    assert undeclared == [], (
        f"{len(undeclared)} routes carry no area tag and are not in the common "
        f"set or a declared composed router:\n  " + "\n  ".join(undeclared[:40]) +
        "\n\nTag the router with one area, or declare it in COMPOSED_SURFACES."
    )
    assert multi == [], (
        f"routes carrying MORE THAN ONE area tag: {multi}. The guard takes the "
        f"first, so the rest are silently dead."
    )
    assert unknown == [], f"tags naming areas absent from KNOWN_AREAS: {unknown}"

    # ⚠️ NON-ZERO CONTROL: an empty route list would satisfy all three above.
    tagged = sum(1 for _m, _p, a in _tenant_routes() if a)
    assert tagged > 1000, f"only {tagged} routes carry an area tag — walker broken"


def test_no_router_is_mapped_to_two_areas():
    """⚠️ THE CHECK MY OWN FIRST VERIFICATION DID NOT HAVE.

    The Phase A mapping was verified three ways — every router accounted for,
    none in two lists, no ghosts — and none of those tested the map against
    ITSELF. `legacy` was listed under both `personalization` and `settings`;
    the lookup silently kept the last one, so the Legacy print generator was
    tagged as tenant administration. No route ended up with two tags, so
    nothing was conflicting — it was just quietly the wrong answer.
    """
    from app.core.areas import COMPOSED_SURFACES

    names = [name for name, _reason in COMPOSED_SURFACES]
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert dupes == [], f"COMPOSED_SURFACES lists these twice: {dupes}"

    assert any(a for _m, _p, a in _tenant_routes()), "no route carries an area tag"


def test_composed_surfaces_names_no_router_that_does_not_exist():
    """⚠️ A stale declaration pre-exempts a reinstatement — the third time this
    rule has earned its place today (the login sweep, the unauthenticated
    inventory, and now here).

    If a composed router is deleted or re-homed and its entry is left behind,
    the entry is a standing exemption from the tagging rule, waiting for
    somebody to add that path back.
    """
    from app.core.areas import COMPOSED_SURFACES

    live = {p.split("/")[3] for _m, p, _a in _tenant_routes()}
    stale = sorted(name for name, _ in COMPOSED_SURFACES if name not in live)
    assert stale == [], (
        f"COMPOSED_SURFACES names routers that do not exist: {stale}. Delete "
        f"the entry — a leftover exemption waves through whoever re-adds it."
    )


def test_the_planned_role_lists_are_well_formed_and_enforced():
    """⚠️ RENAMED FROM `..._and_not_yet_enforced` WHEN PHASE B LANDED.

    In Phase A the claim was "recorded, nothing enforcing them". Phase B is the
    ruling that turns them on, so the same test now asserts the opposite half:
    the seed limits every role in `PLANNED_ROLE_AREAS`, and admin is in neither
    declaration site. Replaced rather than deleted, so the coverage of
    well-formedness survives the regime change.
    """
    from sqlalchemy import text

    from app.core.areas import CHANGE, KNOWN_AREAS, PLANNED_ROLE_AREAS, VIEW, parse_area_grant
    from app.database import SessionLocal

    for role, grants in PLANNED_ROLE_AREAS.items():
        # ⚠️ AN EMPTY LIST IS NOW A LEGITIMATE VALUE AND THIS LINE USED TO
        # FORBID IT. When Phase A recorded the lists, `()` could only have been
        # a mistake, so this read `assert grants`. Phase B gives `employee` an
        # empty list ON PURPOSE — "limited to nothing, the common set only" —
        # and the old assertion fired on the intended value. Emptiness is
        # allowed; what is not allowed is emptiness arriving by accident, which
        # the explicit `employee == []` assertion below pins.
        assert isinstance(grants, tuple), f"{role}: grants must be a tuple, got {type(grants)}"
        for g in grants:
            area, level = parse_area_grant(g)
            assert area in KNOWN_AREAS, f"{role}: {g!r} names an unknown area"
            assert level in (VIEW, CHANGE), f"{role}: {g!r} has a bad level"

    # ⚠️ `admin` must be ABSENT, and its absence is the recorded decision that
    # an unlimited admin is deliberate rather than forgotten.
    assert "admin" not in PLANNED_ROLE_AREAS

    # ⚠️ THE INERTNESS ASSERTION, AND IT READS THE SEED DEFINITION RATHER THAN
    # THE LIVE DATABASE — BECAUSE THE DATABASE VERSION WAS ORDER-COUPLED AND I
    # ONLY FOUND OUT BY RUNNING THE WHOLE FILE.
    #
    # The first version asserted that no role row anywhere has a non-NULL
    # `limited_to_areas` except payroll. It PASSED alone and FAILED in the
    # suite, because sibling tests in this very file set `limited_to_areas` on
    # their fixture role on purpose — `test_an_empty_area_list_is_not_the_same_
    # as_null` writes `'[]'` to it. So the assertion was reading global state
    # that its neighbours legitimately mutate.
    #
    # Phase A's inertness is a claim about the CODE: the seed grants an area
    # limit to `payroll` and to nothing else. That is order-independent and it
    # is the thing actually being claimed.
    from app.services.role_service import _SYSTEM_ROLES

    # ⚠️ PHASE B: the seed now applies every planned list. Asserted through
    # `_planned_area_limit`, which is the function the seed actually calls —
    # asserting the dict alone would pass while the seed ignored it.
    from app.services.role_service import _planned_area_limit

    for slug, grants in PLANNED_ROLE_AREAS.items():
        got = _planned_area_limit(slug)
        assert got == list(grants), f"{slug}: seed would write {got}, list says {list(grants)}"

    # ⚠️ `employee` IS `[]`, NOT `None`, AND THE DISTINCTION IS THE WHOLE ROLE.
    # `()` is falsy, so an `if grants` check turns "limited to nothing" into
    # "not limited at all" — the inversion that would make an employee
    # unrestricted while the list says they reach nothing. Decided by
    # membership, and pinned here.
    assert _planned_area_limit("employee") == [], "employee must be [] (limited to nothing)"
    assert _planned_area_limit("admin") is None, "admin must be None (unrestricted)"

    # And admin must still be absent from the dict — its absence IS the decision.
    assert "admin" not in PLANNED_ROLE_AREAS
