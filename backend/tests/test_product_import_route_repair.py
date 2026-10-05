"""`POST /product-library/import` — the route, end to end.

⚠️ THIS ROUTE RAISED 500 ON EVERY CALL FOR 202 DAYS (2026-03-17 → 2026-10-05),
so there is no production behaviour to regress against. These tests are the
entire claim that the path works, not a safety net under a known-good one.

Four defects were fixed together because three were STACKED — repairing one
alone moves the failure rather than removing it:

1. **Arity.** Four positional arguments into a three-parameter function.
2. **The schema discarded the prices.** It declared `template_ids` alone while
   the client sent `{template_ids, products}`. ⚠️ Fixing the arity WITHOUT the
   schema yields a 201 and a catalog of priceless products — a worse failure
   than the 500, because nothing reports it. `test_the_prices_actually_land` is
   the assertion that distinguishes those two outcomes.
3. **An unknown variant id was a 500.** Now 422, naming the id.
4. **No `response_model`.**

Plus the completion trigger, which is why fixing 1-4 would still not have met
2b-3's acceptance bar: nothing fired `check_completion`, so a successful import
left `add_products` open and `setup_quick_orders` never unlocked.
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

SLUG_PREFIX = "pir-"


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def ctx():
    """A throwaway tenant + admin per test, purged afterwards.

    ⚠️ The `%` is REQUIRED — `purge_companies_by_slug` passes its argument to
    LIKE verbatim despite the parameter being named `slug_prefix`. Omitting it
    matches nothing, the purge returns without error having deleted zero rows,
    and the COMPANY LITTER tripwire fires several tests later.
    """
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    s = SessionLocal()
    try:
        sfx = uuid.uuid4().hex[:8]
        co = Company(id=str(uuid.uuid4()), name=f"PIR {sfx}", slug=f"{SLUG_PREFIX}{sfx}",
                     vertical="manufacturing")
        s.add(co); s.flush()
        role = Role(id=str(uuid.uuid4()), company_id=co.id, name="Admin", slug="admin")
        s.add(role); s.flush()
        u = User(id=str(uuid.uuid4()), company_id=co.id, email=f"u-{sfx}@pir.co",
                 first_name="P", last_name="R", hashed_password="x", is_active=True,
                 is_super_admin=True, role_id=role.id)
        s.add(u); s.commit()
        token = create_access_token({"sub": u.id, "company_id": co.id})
        yield {"token": token, "slug": co.slug, "company_id": co.id}
    finally:
        s.close()
        c = SessionLocal()
        try:
            purge_companies_by_slug(c, f"{SLUG_PREFIX}%")
        finally:
            c.close()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def variants(db):
    """Two real platform variants, read not constructed."""
    rows = list(db.execute(text(
        "SELECT id, display_name, sku FROM product_variant_templates "
        "WHERE sku IN ('BV-BTRI','BV-CON') ORDER BY sku"
    )))
    assert len(rows) == 2, f"expected 2 known variants, got {len(rows)} — catalog changed"
    return rows


def _post(client, ctx, body):
    return client.post(
        "/api/v1/tenant-onboarding/product-library/import",
        json=body,
        headers={"Authorization": f"Bearer {ctx['token']}",
                 # ⚠️ The route resolves the tenant from the REQUEST, not the
                 # token — `get_company_slug` reads X-Company-Slug or the Host
                 # subdomain. Without it every call is 404, which is a different
                 # failure from the one under test.
                 "X-Company-Slug": ctx["slug"]},
    )


def _products(db, company_id):
    return list(db.execute(text(
        "SELECT name, sku, price, variant_template_id, is_manufactured, unit_of_measure "
        "FROM products WHERE company_id = :c ORDER BY name"
    ), {"c": company_id}))


class TestTheRouteAnswersAtAll:
    def test_a_valid_import_returns_201(self, client, ctx, variants):
        """⚠️ THE ASSERTION WHOSE ABSENCE LET A 202-DAY 500 LIVE."""
        v = variants[0]
        r = _post(client, ctx, {"template_ids": [v.id],
                                "products": [{"template_id": v.id, "price": 1895, "sku": None}]})
        assert r.status_code == 201, r.text
        assert r.json() == {"imported_count": 1}

    def test_the_response_model_filters_to_exactly_one_field(self, client, ctx, variants):
        """`product_ids` was declared 2026-03-17 and never produced. The
        response_model now pins the shape, so re-adding a field is deliberate."""
        v = variants[0]
        r = _post(client, ctx, {"products": [{"template_id": v.id, "price": 10}]})
        assert sorted(r.json()) == ["imported_count"]


class TestThePricesActuallyLand:
    def test_the_prices_actually_land(self, client, ctx, db, variants):
        """⚠️ THE TEST THAT DISTINGUISHES THE FIX FROM A HALF-FIX.

        Repairing the arity alone would return 201 here and write NULL prices,
        because the schema dropped `products` silently. A licensee would import
        52 products, see a success toast, and own a priceless catalog. This
        assertion is the only thing that tells those two outcomes apart.
        """
        a, b = variants
        r = _post(client, ctx, {
            "template_ids": [a.id, b.id],
            "products": [{"template_id": a.id, "price": 1895.00, "sku": "MINE-1"},
                         {"template_id": b.id, "price": 2400.50, "sku": None}],
        })
        assert r.status_code == 201, r.text
        rows = _products(db, ctx["company_id"])
        assert len(rows) == 2
        by_vt = {row.variant_template_id: row for row in rows}
        assert float(by_vt[a.id].price) == 1895.00
        assert float(by_vt[b.id].price) == 2400.50

    def test_a_supplied_sku_wins_and_a_null_one_falls_back(self, client, ctx, db, variants):
        a, b = variants
        _post(client, ctx, {"products": [{"template_id": a.id, "price": 1, "sku": "MINE-1"},
                                         {"template_id": b.id, "price": 2, "sku": None}]})
        by_vt = {r.variant_template_id: r for r in _products(db, ctx["company_id"])}
        assert by_vt[a.id].sku == "MINE-1"
        assert by_vt[b.id].sku == b.sku, "a null sku should fall back to the variant's"

    def test_what_is_still_deliberately_not_copied(self, client, ctx, db, variants):
        """⚠️ r196's ruling survives the route. The platform `is_manufactured` is
        a PRE-FILL; the tenant value is the ANSWER. And `unit_of_measure` stays
        unset — a hardcoded "each" would be a guess wearing the old field's
        clothes."""
        v = variants[0]
        _post(client, ctx, {"products": [{"template_id": v.id, "price": 5}]})
        (row,) = _products(db, ctx["company_id"])
        assert row.is_manufactured is None
        assert row.unit_of_measure is None


class TestTheChecklistItemCompletes:
    def test_add_products_completes_on_import(self, client, ctx, db, variants):
        """⚠️ THE ACCEPTANCE BAR, and the half nothing fired before today.

        `import_product_templates` calls no trigger and the library page
        navigates away without calling the complete route, so a successful
        import used to leave this item open — and `setup_quick_orders` declares
        `depends_on: ["add_products"]`, so quick orders never unlocked.
        """
        from app.services import tenant_onboarding_service as TOS

        TOS.initialize_checklist(db, ctx["company_id"], "manufacturing")
        db.commit()
        before = db.execute(text(
            "SELECT status FROM onboarding_checklist_items "
            "WHERE tenant_id = :c AND item_key = 'add_products'"
        ), {"c": ctx["company_id"]}).scalar_one()
        assert before != "completed", "⚠️ POSITIVE CONTROL: already complete before the import"

        v = variants[0]
        r = _post(client, ctx, {"products": [{"template_id": v.id, "price": 1895}]})
        assert r.status_code == 201, r.text

        after = db.execute(text(
            "SELECT status FROM onboarding_checklist_items "
            "WHERE tenant_id = :c AND item_key = 'add_products'"
        ), {"c": ctx["company_id"]}).scalar_one()
        assert after == "completed", (
            f"add_products is {after!r} after a successful import. The import "
            f"works and the checklist does not — acceptance is not met."
        )

    def test_a_failed_import_does_not_complete_the_item(self, client, ctx, db):
        """⚠️ THE CONTROL. A trigger that fired unconditionally would pass the
        test above while completing the item for an import that wrote nothing."""
        from app.services import tenant_onboarding_service as TOS

        TOS.initialize_checklist(db, ctx["company_id"], "manufacturing")
        db.commit()
        r = _post(client, ctx, {"products": [{"template_id": "not-a-variant", "price": 1}]})
        assert r.status_code == 422
        status = db.execute(text(
            "SELECT status FROM onboarding_checklist_items "
            "WHERE tenant_id = :c AND item_key = 'add_products'"
        ), {"c": ctx["company_id"]}).scalar_one()
        assert status != "completed"


class TestAnUnknownIdIsLoudNotA500:
    def test_unknown_variant_id_is_422(self, client, ctx):
        r = _post(client, ctx, {"products": [{"template_id": "not-a-variant", "price": 1}]})
        assert r.status_code == 422, f"got {r.status_code}: {r.text[:200]}"
        assert r.json()["detail"]["value"] == "not-a-variant"

    def test_a_product_tier_id_is_rejected(self, client, ctx, db):
        """⚠️ THE DISCRIMINATING CASE. `template_id` is a VARIANT id. A PRODUCT
        id must fail rather than quietly matching — if it resolved, the whole
        repoint would be reading the wrong tier."""
        pid = db.execute(text("SELECT id FROM product_templates LIMIT 1")).scalar_one()
        r = _post(client, ctx, {"products": [{"template_id": pid, "price": 1}]})
        assert r.status_code == 422

    def test_nothing_is_written_when_one_id_is_bad(self, client, ctx, db, variants):
        """The raise happens before the commit, so a partial import cannot land."""
        v = variants[0]
        r = _post(client, ctx, {"products": [{"template_id": v.id, "price": 1},
                                             {"template_id": "nope", "price": 2}]})
        assert r.status_code == 422
        assert _products(db, ctx["company_id"]) == []


class TestTheSchemaGuards:
    def test_an_empty_selection_is_422_not_a_201_no_op(self, client, ctx):
        r = _post(client, ctx, {"products": []})
        assert r.status_code == 422

    def test_disagreeing_template_ids_are_loud(self, client, ctx, variants):
        """`products` is authoritative and `template_ids` is redundant. They
        cannot disagree from the shipped client, which derives one from the
        other — so if they ever do, that is a client defect worth a 422 rather
        than a silent preference for one list."""
        v = variants[0]
        r = _post(client, ctx, {"template_ids": ["something-else"],
                                "products": [{"template_id": v.id, "price": 1}]})
        assert r.status_code == 422

    def test_a_negative_price_is_rejected(self, client, ctx, variants):
        v = variants[0]
        r = _post(client, ctx, {"products": [{"template_id": v.id, "price": -5}]})
        assert r.status_code == 422

    def test_the_legacy_template_ids_only_payload_is_now_rejected(self, client, ctx, variants):
        """⚠️ A VISIBLE BREAK, deliberately. The pre-2026-10-05 schema accepted
        `{template_ids}` alone — and that shape is exactly the one that silently
        discarded prices. It has never succeeded (the route 500'd), so there is
        no client to break, and accepting it now would re-open the price loss."""
        v = variants[0]
        r = _post(client, ctx, {"template_ids": [v.id]})
        assert r.status_code == 422


class TestTheAcceptanceBar:
    """⚠️ 2b-3's acceptance bar, verbatim and in one test.

    *"The library loads, a selection imports, the checklist item completes, and
    quick_orders unlocks."*

    Written because the first three clauses each have their own test above and
    passing all three still would not have demonstrated the fourth. The gate on
    quick orders is computed in the FRONTEND (`onboarding-hub.tsx:147`) over the
    `depends_on` field of the checklist payload, so whether it unlocks depends on
    something no backend test was looking at: that `depends_on` is served at all.

    ⚠️ It is served as a JSON STRING (`'["add_products"]'`), not a list — the
    route carries no `response_model`, so FastAPI serialises the ORM column
    as-is. That is why the frontend has a `JSON.parse` fallback, and why this
    test parses the same way rather than asserting a list.
    """

    def test_the_whole_bar(self, client, ctx, db, variants):
        import json

        from app.services import tenant_onboarding_service as TOS

        TOS.initialize_checklist(db, ctx["company_id"], "manufacturing")
        db.commit()
        H = {"Authorization": f"Bearer {ctx['token']}", "X-Company-Slug": ctx["slug"]}

        # 1. the library loads
        lib = client.get("/api/v1/tenant-onboarding/product-library", headers=H)
        assert lib.status_code == 200, lib.text
        assert len(lib.json()) > 0

        def items():
            r = client.get("/api/v1/tenant-onboarding/checklist", headers=H)
            assert r.status_code == 200, r.text
            return {i["item_key"]: i for i in r.json()["items"]}

        def unmet(by_key, key):
            raw = by_key[key].get("depends_on")
            deps = json.loads(raw) if isinstance(raw, str) else (raw or [])
            return [d for d in deps if by_key.get(d, {}).get("status") != "completed"]

        before = items()
        # ⚠️ POSITIVE CONTROL: quick orders must be LOCKED first, or "unlocked"
        # afterwards proves nothing. This is the assertion that makes the rest
        # of the test discriminating.
        assert unmet(before, "setup_quick_orders") == ["add_products"], (
            "setup_quick_orders is not blocked on add_products before the import "
            "— the dependency is absent from the payload, so the unlock below "
            "would be vacuous"
        )

        # 2. a selection imports
        v = variants[0]
        imp = client.post(
            "/api/v1/tenant-onboarding/product-library/import",
            json={"products": [{"template_id": v.id, "price": 1895}]},
            headers=H,
        )
        assert imp.status_code == 201, imp.text
        assert imp.json()["imported_count"] == 1

        after = items()
        # 3. the checklist item completes
        assert after["add_products"]["status"] == "completed"
        # 4. quick_orders unlocks
        assert unmet(after, "setup_quick_orders") == []
