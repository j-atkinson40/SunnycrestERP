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
    """The values actually present — the same derivation the service uses.

    ⚠️ Reads the NEW catalog since 2b-3 Commit 2. `category` and `preset` are gone:
    the vocabulary moved to `form`, which was free because the endpoint had returned
    500 on every call since 2026-03-17 and no client ever received the old values.
    """
    forms = sorted(
        v for (v,) in db.execute(
            text("SELECT DISTINCT form FROM product_templates")
        ) if v is not None
    )
    return {"forms": forms}


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
        assert known["forms"], "no forms in the catalog — tests below are vacuous"
        r = _get(client, ctx)
        assert len(r.json()) > 0


class TestAnUnknownFilterIsLoud:
    def test_unknown_form_is_422_not_an_empty_list(self, client, ctx):
        r = _get(client, ctx, form="Definitely Not A Form")
        assert r.status_code == 422, (
            f"got {r.status_code} with body {r.text[:200]} — an unknown filter "
            f"must not quietly return []"
        )
        assert r.json()["detail"]["field"] == "form"

    def test_the_OLD_vocabulary_is_now_loudly_rejected(self, client, ctx):
        """⚠️ The vocabulary move is a VISIBLE break, by design. A client still
        sending "Burial Vaults" is told so, with the accepted set, rather than
        handed an empty catalog."""
        r = _get(client, ctx, form="Burial Vaults")
        assert r.status_code == 422
        assert "burial_vault" in r.json()["detail"]["known_values"]

    def test_the_error_names_what_IS_accepted(self, client, ctx, known):
        """The whole point: a client that missed a vocabulary change is told the
        vocabulary rather than left to guess from an empty list."""
        r = _get(client, ctx, form="Definitely Not A Form")
        assert r.json()["detail"]["known_values"] == known["forms"]


class TestKnownValuesStillWork:
    def test_each_known_form_returns_rows(self, client, ctx, known):
        """⚠️ THE CONTROL ON THE REJECTIONS. A validator that rejected EVERYTHING
        would satisfy every test above. This proves it accepts what it should —
        and it is derived from the data, so it is correct in any environment."""
        for f in known["forms"]:
            r = _get(client, ctx, form=f)
            assert r.status_code == 200, f"{f!r} rejected: {r.text[:200]}"
            assert len(r.json()) > 0, f"{f!r} accepted but returned nothing"

    def test_the_library_returns_variants_not_products(self, client, ctx, db):
        """⚠️ The silent-halving guard. The old flat rows were sellable things,
        which are VARIANTS; products would offer far fewer."""
        n = len(_get(client, ctx).json())
        variants = db.execute(text("SELECT count(*) FROM product_variant_templates")).scalar_one()
        products = db.execute(text("SELECT count(*) FROM product_templates")).scalar_one()
        assert n == variants
        assert n != products
