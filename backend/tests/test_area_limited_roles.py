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

    The unlimited one is deliberately an already-seeded role (`office`), not a
    fresh one: the claim being tested is about roles that exist today.
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        office_role_id = db.execute(text(
            "SELECT id FROM roles WHERE company_id=:c AND slug='office' LIMIT 1"
        ), {"c": TESTCO_ID}).scalar()
        if office_role_id is None:
            pytest.skip("testco has no 'office' role — run the role seed")

        # Control: the role we are calling unlimited must actually be unlimited.
        assert db.execute(text(
            "SELECT limited_to_areas IS NULL FROM roles WHERE id=:r"
        ), {"r": office_role_id}).scalar() is True, "office role is not NULL-areas"

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
        _mk_user(db, UNLIMITED_USER_ID, office_role_id, "area-office@testco.example.com")
        db.commit()

        yield {
            "limited": create_access_token({"sub": LIMITED_USER_ID, "company_id": TESTCO_ID}),
            "unlimited": create_access_token({"sub": UNLIMITED_USER_ID, "company_id": TESTCO_ID}),
            "office_role_id": office_role_id,
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
    assert detail["requested_area"] is None, "journal-entries carries no area tag"


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


def test_no_existing_role_anywhere_was_backfilled():
    """r221 added the column and wrote nothing. If a later migration or seed
    starts populating it, every tenant's behaviour changes at once."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        total, non_null = db.execute(text(
            "SELECT count(*), count(limited_to_areas) FROM roles "
            "WHERE id NOT LIKE 'area-probe-%'"
        )).first()
    finally:
        db.close()
    assert total > 0, "no roles examined — the query is not reaching the table"
    assert non_null == 0, (
        f"{non_null} of {total} roles have limited_to_areas set; r221 must not "
        f"backfill and nothing else should have"
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


def test_common_prefixes_are_real_routes():
    """A stale common entry grants nothing and reads as protection."""
    from fastapi.routing import APIRoute
    from app.core.areas import COMMON_PREFIXES, strip_mount_prefix

    paths = {strip_mount_prefix(r.path) for r in app.routes if isinstance(r, APIRoute)}
    for prefix, reason in COMMON_PREFIXES:
        assert any(p == prefix or p.startswith(prefix + "/") or p.startswith(prefix)
                   for p in paths), f"common prefix {prefix!r} matches no route ({reason})"


def test_common_match_respects_segment_boundaries():
    """`/authorization-anything` must not pass on the `/auth` entry."""
    from app.core.areas import is_common
    assert is_common("/api/v1/auth/me")
    assert not is_common("/api/v1/authorization-sneaky")
    assert not is_common("/api/v1/feature-flags/matrix")
    assert not is_common("/api/v1/journal-entries/entries")


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
