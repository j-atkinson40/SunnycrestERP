"""`GET /settings/service-territories` must require a signed-in user of that company.

⚠️ **WHY THIS ENDPOINT AND NOT A SWEEP.** Measured 2026-11-03: this was the ONLY
tenant endpoint that resolved a company and returned its data with no
authentication dependency at all. It depended on `get_current_company` — which
resolves from the `X-Company-Slug` HEADER (`app/api/company_resolver.py:8`) — and
not on `get_current_user`. Anyone who knew a tenant slug could read that tenant's
service territories, its `delivery_area_configured` flag and its
`facility_state`. Proven live before the fix: 200, no `Authorization` header,
against two different tenants.

What it discloses is thin. That is not the point: a cross-company read with no
login should not exist anywhere in Bridgeable (James, 2026-11-03).

The fix is one dependency. `get_current_user` already enforces the same-company
half — it 401s when `token_company_id != company.id` (`app/api/deps.py:63-67`)
and loads the user filtered on `User.company_id == company.id` (:72-76) — so
adding it yields "an authenticated user of THIS company" with no new logic.

The ratchet at the bottom is the part that outlives this fix.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests._two_step import tenant_token
from app.main import app
from app.models.role import Role
from app.models.user import User
from tests._tenant import TESTCO_ID, make_canonical_tenant_fixture

_canonical_tenant = make_canonical_tenant_fixture()

PATH = "/api/v1/settings/service-territories"
OTHER_SLUG = "svcterr-other-tenant"
USER_ID = "svcterr-probe-user"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def other_tenant():
    """A second company, so "another tenant's slug" is a real case and not a 404.

    Without this the no-auth probe could 404 on an unknown slug and look like a
    refusal — a green that came from the wrong mechanism.
    """
    from app.database import SessionLocal
    from app.models.company import Company

    db = SessionLocal()
    cid = str(uuid.uuid4())
    try:
        db.execute(text("DELETE FROM companies WHERE slug = :s"), {"s": OTHER_SLUG})
        db.add(Company(id=cid, slug=OTHER_SLUG, name="Service Territory Other Co",
                       facility_state="PA"))
        db.commit()
        yield {"id": cid, "slug": OTHER_SLUG}
    finally:
        db.execute(text("DELETE FROM manufacturer_service_territories WHERE company_id = :c"),
                   {"c": cid})
        db.execute(text("DELETE FROM companies WHERE id = :c"), {"c": cid})
        db.commit()
        db.close()


@pytest.fixture(scope="module")
def testco_token():
    """A REAL token for a real testco user.

    Deliberately not a `dependency_overrides` of `get_current_user` — that is the
    dependency under test, and overriding it would assert the fix by removing it.
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        role_id = db.execute(text(
            "SELECT id FROM roles WHERE company_id = :c AND slug = 'admin' LIMIT 1"
        ), {"c": TESTCO_ID}).scalar()
        if role_id is None:
            pytest.skip("testco has no admin role — run the role seed")
        db.execute(text("DELETE FROM users WHERE id = :u"), {"u": USER_ID})
        db.add(User(id=USER_ID, email="svcterr-probe@testco.example.com",
                    hashed_password="not-a-credential", first_name="Svc",
                    last_name="Probe", role_id=role_id, company_id=TESTCO_ID))
        db.commit()
        yield tenant_token(USER_ID, TESTCO_ID)
    finally:
        db.execute(text("DELETE FROM users WHERE id = :u"), {"u": USER_ID})
        db.commit()
        db.close()


# ---------------------------------------------------------------- the refusals


def test_unauthenticated_read_of_own_tenant_is_refused(client):
    """⚠️ THE BREAK TEST. Returned 200 before the fix."""
    r = client.get(PATH, headers={"X-Company-Slug": "testco"})
    assert r.status_code in (401, 403), (
        f"expected a refusal, got {r.status_code}: {r.text[:200]}"
    )


def test_unauthenticated_read_of_another_tenant_is_refused(client, other_tenant):
    """The cross-company form, which is the one that actually mattered.

    Before the fix this returned 200 with that company's `facility_state`.
    """
    r = client.get(PATH, headers={"X-Company-Slug": other_tenant["slug"]})
    assert r.status_code in (401, 403), (
        f"expected a refusal, got {r.status_code}: {r.text[:200]}"
    )
    assert "PA" not in r.text, "the other tenant's facility_state leaked in the body"


def test_the_other_tenant_exists_so_the_refusal_is_not_a_404(client, other_tenant):
    """⚠️ POSITIVE CONTROL ON THE FIXTURE, not on the code.

    A refusal is only evidence if the slug resolves. If this company were absent
    the probe above would 404 and read as a refusal produced by the wrong
    mechanism entirely.
    """
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        got = db.execute(text("SELECT facility_state FROM companies WHERE slug = :s"),
                         {"s": other_tenant["slug"]}).scalar()
    finally:
        db.close()
    assert got == "PA", "fixture company missing or has no facility_state to leak"


def test_a_token_for_another_company_is_refused(client, other_tenant):
    """A valid testco token must not read the other tenant by swapping the slug."""
    token = tenant_token(USER_ID, TESTCO_ID)
    r = client.get(PATH, headers={"Authorization": f"Bearer {token}",
                                  "X-Company-Slug": other_tenant["slug"]})
    assert r.status_code == 401, f"got {r.status_code}: {r.text[:200]}"


# ------------------------------------------------------------ still works


def test_an_authenticated_user_of_the_company_still_reads_it(client, testco_token):
    """The fix must not break the legitimate caller — the frontend uses this."""
    r = client.get(PATH, headers={"Authorization": f"Bearer {testco_token}",
                                  "X-Company-Slug": "testco"})
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
    body = r.json()
    assert set(body) >= {"counties", "total", "delivery_area_configured", "facility_state"}


def test_the_post_was_already_guarded_and_still_is(client):
    r = client.post(PATH, headers={"X-Company-Slug": "testco"}, json={"counties": []})
    assert r.status_code in (401, 403)


# ----------------------------------------------------------------- the ratchet


def test_no_tenant_route_resolves_a_company_without_requiring_a_user():
    """⚠️ THE PART THAT OUTLIVES THE FIX.

    Walks FastAPI's `Dependant` tree — not a grep — because a dependency attached
    at `include_router()` level or inherited through a nested router is invisible
    to a text search, which is exactly the population this asserts over.

    `login` / `refresh` / `register` are excluded BY NAME: they must resolve the
    company to authenticate against it, and they cannot require a user because
    producing one is their job.
    """
    from fastapi.routing import APIRoute

    ALLOWED_WITHOUT_USER = {
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/register",
    }

    def dep_names(dep, out, seen):
        if id(dep) in seen:
            return
        seen.add(id(dep))
        call = getattr(dep, "call", None)
        if call is not None:
            out.add(getattr(call, "__name__", repr(call)))
        for sub in getattr(dep, "dependencies", []) or []:
            dep_names(sub, out, seen)

    company_resolvers = {"get_current_company", "get_optional_company"}
    user_requirers = {
        "get_current_user", "require_admin", "require_super_admin",
        "_check_permission", "get_current_platform_user", "_check_platform_role",
        "get_current_portal_user", "get_current_portal_user_for_tenant",
        "get_api_key_auth", "_check_scope",
    }

    offenders, seen_allowed, scanned = [], set(), 0
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/v1/"):
            continue
        names: set[str] = set()
        dep_names(route.dependant, names, set())
        if not (names & company_resolvers):
            continue
        scanned += 1
        if names & user_requirers:
            continue
        if route.path in ALLOWED_WITHOUT_USER:
            seen_allowed.add(route.path)
            continue
        offenders.append(
            f"{','.join(sorted(m for m in route.methods if m not in ('HEAD','OPTIONS')))} "
            f"{route.path}"
        )

    # ⚠️ TWO POSITIVE CONTROLS, because this asserts an ABSENCE and an absence
    # looks identical whether the instrument works or not (CLAUDE.md §11).
    #
    #   (1) the scanner SEES: it must have examined a non-trivial population.
    assert scanned > 100, (
        f"only {scanned} company-resolving routes examined — the walker is not "
        f"reaching the route table, so 'no offenders' would mean nothing"
    )
    #   (2) the EXCLUSIONS are real: every allowlisted path must actually have
    #       been hit as an exclusion. If login stopped resolving a company, this
    #       test would quietly stop proving anything about it.
    assert seen_allowed == ALLOWED_WITHOUT_USER, (
        f"allowlist did not match reality — expected to exclude "
        f"{sorted(ALLOWED_WITHOUT_USER)}, actually excluded {sorted(seen_allowed)}"
    )

    assert offenders == [], (
        "tenant route(s) resolve a company but require no user:\n  "
        + "\n  ".join(offenders)
    )
