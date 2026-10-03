"""`GET /product-library` rejects an unknown filter instead of returning `[]`.

⚠️ THIS SUITE EXISTS BECAUSE THE ENDPOINT WAS RETURNING 500 ON EVERY CALL AND
NOTHING NOTICED. Found 2026-10-03 while adding the validation below: the route
called `get_product_library(db, company.id, preset=..., category=...)` against a
service whose signature is `(db, preset, category)`, so `company.id` bound
positionally to `preset` and the keyword re-bound it —
`TypeError: got multiple values for argument 'preset'`, on a live route, with no
test anywhere covering it.

So this file pins two different things, and the first is the one that would have
caught the outage:

1. **The endpoint answers at all.** A plain call returns 200 with a list. That is
   the assertion whose absence let a 500 live.

2. **An unknown filter is LOUD.** Until 2026-10-03 an unrecognised `category` or
   `preset` filtered everything out and returned `[]`. A client that missed a
   vocabulary change saw an empty catalog and no signal — indistinguishable from
   "we stock nothing", silent on both sides.

   It matters now because 2b-3 is about to move that vocabulary: the old
   `category` has three values, the new catalog's `form` has six, and the old
   "Burial Vaults" covers what are now `burial_vault`, `grave_liner` and `infant`.

⚠️ THE VALID SET IS DERIVED FROM THE DATA, NOT HARDCODED, and these tests must be
too. Dev holds categories written by the `x1y2z3a4b5c6` migration; production holds
different ones written by `catalog_template_seeder`, which has never run on dev
because it is gated on `PLATFORM_ADMIN_*`. Neither population is the other's
subset, so a literal expectation would pass in one environment and fail in the
other for no good reason.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import create_access_token
from app.database import SessionLocal
from app.main import app
from tests._cleanup import purge_companies_by_slug

SLUG_PREFIX = "plfv-"


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture(scope="module")
def ctx():
    """A real tenant + admin user, because the route is auth-gated.

    Cleaned up via the shared FK-safe purge; the slug prefix is unique to this
    file so the purge cannot reach another suite's rows.
    """
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    s = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"PLFV {suffix}",
            slug=f"{SLUG_PREFIX}{suffix}",
        )
        s.add(co)
        s.flush()
        role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin")
        s.add(role)
        s.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@plfv.co",
            first_name="PL",
            last_name="FV",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        s.add(user)
        s.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        yield {"token": token, "slug": co.slug, "company_id": co.id}
    finally:
        s.close()
        cleanup = SessionLocal()
        try:
            # ⚠️ THE `%` IS REQUIRED. `purge_companies_by_slug` passes its
            # argument to `LIKE` VERBATIM despite the parameter being named
            # `slug_prefix` — it appends no wildcard. Omitting it matches nothing,
            # the purge returns WITHOUT ERROR having deleted zero rows, and the
            # COMPANY LITTER tripwire fires several tests later. All ~49 other
            # callers pass it; this one did not, and the tripwire caught it.
            purge_companies_by_slug(cleanup, f"{SLUG_PREFIX}%")
        finally:
            cleanup.close()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _get(client, ctx, **params):
    return client.get(
        "/api/v1/tenant-onboarding/product-library",
        params=params,
        headers={
            "Authorization": f"Bearer {ctx['token']}",
            # ⚠️ The route resolves the tenant from the REQUEST, not the token —
            # `get_company_slug` reads `X-Company-Slug` or falls back to the Host
            # subdomain. Without it every call is 404 "Company not found", which
            # is a different failure from the one under test.
            "X-Company-Slug": ctx["slug"],
        },
    )


@pytest.fixture(scope="module")
def known(db):
    """The values actually present — the same derivation the service uses."""
    cats = sorted(
        v for (v,) in db.execute(
            text("SELECT DISTINCT category FROM product_catalog_templates")
        ) if v is not None
    )
    presets = sorted(
        v for (v,) in db.execute(
            text("SELECT DISTINCT preset FROM product_catalog_templates")
        ) if v is not None
    )
    return {"categories": cats, "presets": presets}


class TestTheEndpointAnswersAtAll:
    def test_an_unfiltered_call_returns_200(self, client, ctx):
        """⚠️ THE ASSERTION WHOSE ABSENCE LET A 500 LIVE. The route passed an extra
        positional argument and raised TypeError on every call; nothing covered
        it."""
        r = _get(client, ctx)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_it_returns_something(self, client, ctx, known):
        """⚠️ POSITIVE CONTROL. Every rejection test below asserts a NON-200. If
        the catalog were empty they would still pass while proving nothing about
        filtering."""
        assert known["categories"], "no categories in the catalog — tests below are vacuous"
        r = _get(client, ctx)
        assert len(r.json()) > 0


class TestAnUnknownFilterIsLoud:
    def test_unknown_category_is_422_not_an_empty_list(self, client, ctx):
        r = _get(client, ctx, category="Definitely Not A Category")
        assert r.status_code == 422, (
            f"got {r.status_code} with body {r.text[:200]} — an unknown filter "
            f"must not quietly return []"
        )
        assert r.json()["detail"]["field"] == "category"

    def test_unknown_preset_is_422(self, client, ctx):
        r = _get(client, ctx, preset="not-a-preset")
        assert r.status_code == 422
        assert r.json()["detail"]["field"] == "preset"

    def test_the_error_names_what_IS_accepted(self, client, ctx, known):
        """The whole point: a client that missed a vocabulary change is told the
        vocabulary rather than left to guess from an empty list."""
        r = _get(client, ctx, category="Definitely Not A Category")
        assert r.json()["detail"]["known_values"] == known["categories"]


class TestKnownValuesStillWork:
    def test_each_known_category_returns_rows(self, client, ctx, known):
        """⚠️ THE CONTROL ON THE REJECTIONS. A validator that rejected EVERYTHING
        would satisfy every test above. This proves it accepts what it should —
        and it is derived from the data, so it is correct in any environment."""
        for cat in known["categories"]:
            r = _get(client, ctx, category=cat)
            assert r.status_code == 200, f"{cat!r} rejected: {r.text[:200]}"
            assert len(r.json()) > 0, f"{cat!r} accepted but returned nothing"

    def test_each_known_preset_returns_rows(self, client, ctx, known):
        for p in known["presets"]:
            r = _get(client, ctx, preset=p)
            assert r.status_code == 200, f"{p!r} rejected: {r.text[:200]}"
            assert len(r.json()) > 0
