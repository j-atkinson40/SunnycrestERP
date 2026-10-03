"""`import_product_templates` copies a platform VARIANT into a tenant product.

⚠️ THIS IS A COLD PATH, SO THESE TESTS ARE THE ENTIRE CLAIM. Measured 2026-10-03:
the function has never provisioned a tenant in either environment — no product
carries the copy's fingerprint, `add_products` is incomplete for every tenant, and
its only UI route returned 500 from 2026-03-17. There is no production behaviour to
compare against, so nothing here is a safety net under a known-good path. It is the
only evidence the path is good at all.

Every assertion below has a named break recorded in the commit body.

WHAT IT PINS:

1. **A variant id in, a tenant product out**, carrying the variant's exact display
   name — the sellable name a licensee ticked, not the product-tier grouping.

2. **`variant_template_id` IS SET.** r186 added the column and nothing could write
   it (no ORM attribute until r196), so every tenant product was an orphan with no
   route back to its platform definition. This is the link that lets a supplier
   price increase or a corrected spec find the rows it should reach.

3. ⚠️ **`is_manufactured` IS NOT COPIED.** The platform value is the onboarding
   PRE-FILL; the tenant value is the ANSWER. Copying would convert a proposal into
   a measurement silently and reinstate the defect r196 removed, this time with a
   provenance trail making it look measured.

4. ⚠️ **`unit_of_measure` IS NOT SET.** Ruled a precast-vertical concern — all 37
   production rows are `each` and a hardcoded "each" would be a guess wearing the
   old field's clothes.

5. **An unknown id RAISES** instead of being skipped. It used to `continue`, so a
   caller sending five ids and receiving three products had no way to learn which
   two were dropped.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.services.onboarding_service import (
    UnknownTemplate,
    import_product_templates,
)
from tests._cleanup import purge_companies_by_slug

SLUG_PREFIX = "impt-"


class _Item:
    """Shaped like the request object the service reads attributes from."""

    def __init__(self, template_id, price=None, sku=None):
        self.template_id = template_id
        self.price = price
        self.sku = sku


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def tenant():
    """A throwaway company per test, purged afterwards.

    ⚠️ The `%` is REQUIRED — `purge_companies_by_slug` passes its argument to LIKE
    verbatim despite the parameter being named `slug_prefix`. Omitting it matches
    nothing, the purge returns without error having deleted zero rows, and the
    COMPANY LITTER tripwire fires several tests later.
    """
    from app.models.company import Company

    s = SessionLocal()
    try:
        sfx = uuid.uuid4().hex[:8]
        co = Company(id=str(uuid.uuid4()), name=f"Imp {sfx}", slug=f"{SLUG_PREFIX}{sfx}")
        s.add(co)
        s.commit()
        cid = co.id
    finally:
        s.close()
    yield cid
    c = SessionLocal()
    try:
        purge_companies_by_slug(c, f"{SLUG_PREFIX}%")
    finally:
        c.close()


@pytest.fixture(scope="module")
def variant(db):
    """A real platform variant, read not constructed."""
    row = db.execute(
        text(
            "SELECT v.id, v.display_name, v.sku, t.display_name AS product_name "
            "FROM product_variant_templates v "
            "JOIN product_templates t ON t.id = v.product_template_id "
            "WHERE v.sku = 'BV-BTRI'"
        )
    ).one()
    return row


def _products(db, company_id):
    return list(
        db.execute(
            text(
                "SELECT name, sku, price, unit_of_measure, variant_template_id, "
                "is_manufactured FROM products WHERE company_id = :c"
            ),
            {"c": company_id},
        )
    )


class TestItCopiesAVariant:
    def test_one_item_creates_one_product(self, db, tenant, variant):
        n = import_product_templates(db, tenant, [_Item(variant.id)])
        assert n == 1
        assert len(_products(db, tenant)) == 1

    def test_the_name_is_the_VARIANT_name_not_the_product_name(self, db, tenant, variant):
        """⚠️ The licensee ticked "Bronze Triune Burial Vault". Writing the product
        tier's "Triune Burial Vault" would name their catalog after a grouping."""
        import_product_templates(db, tenant, [_Item(variant.id)])
        (row,) = _products(db, tenant)
        assert row.name == variant.display_name
        assert row.name != variant.product_name

    def test_the_sku_defaults_to_the_variants(self, db, tenant, variant):
        import_product_templates(db, tenant, [_Item(variant.id)])
        (row,) = _products(db, tenant)
        assert row.sku == variant.sku

    def test_a_supplied_sku_wins(self, db, tenant, variant):
        import_product_templates(db, tenant, [_Item(variant.id, sku="MINE-1")])
        (row,) = _products(db, tenant)
        assert row.sku == "MINE-1"

    def test_the_price_is_carried(self, db, tenant, variant):
        import_product_templates(db, tenant, [_Item(variant.id, price=3864)])
        (row,) = _products(db, tenant)
        assert row.price is not None and int(row.price) == 3864


class TestTheLinkIsFinallyWritten:
    def test_variant_template_id_is_set(self, db, tenant, variant):
        """⚠️ r186 added this column and nothing could write it until r196 gave it
        an ORM attribute. Without it a tenant product is an orphan and a corrected
        spec can never reach it."""
        import_product_templates(db, tenant, [_Item(variant.id)])
        (row,) = _products(db, tenant)
        assert row.variant_template_id == variant.id

    def test_it_resolves_back_to_the_platform_definition(self, db, tenant, variant):
        """The point of the link, exercised rather than asserted structurally."""
        import_product_templates(db, tenant, [_Item(variant.id)])
        back = db.execute(
            text(
                "SELECT t.display_name, t.form FROM products p "
                "JOIN product_variant_templates v ON v.id = p.variant_template_id "
                "JOIN product_templates t ON t.id = v.product_template_id "
                "WHERE p.company_id = :c"
            ),
            {"c": tenant},
        ).one()
        assert back.display_name == variant.product_name
        assert back.form == "burial_vault"


class TestWhatIsDeliberatelyNotCopied:
    def test_is_manufactured_stays_NULL(self, db, tenant, variant):
        """⚠️ Pre-fill is not an answer. Copying the platform value would convert a
        proposal into a measurement silently — the r196 defect with a provenance
        trail making it look measured."""
        import_product_templates(db, tenant, [_Item(variant.id)])
        (row,) = _products(db, tenant)
        assert row.is_manufactured is None

    def test_unit_of_measure_stays_NULL(self, db, tenant, variant):
        """⚠️ Ruled a precast-vertical concern. A hardcoded "each" would be correct
        for all 37 production rows and wrong the first time a paver appears."""
        import_product_templates(db, tenant, [_Item(variant.id)])
        (row,) = _products(db, tenant)
        assert row.unit_of_measure is None


class TestAnUnknownIdIsLoud:
    def test_it_raises_rather_than_skipping(self, db, tenant):
        with pytest.raises(UnknownTemplate):
            import_product_templates(db, tenant, [_Item("not-a-real-variant-id")])

    def test_nothing_is_written_when_one_id_is_bad(self, db, tenant, variant):
        """⚠️ THE CONTROL ON THE RAISE. Raising after writing the good rows would
        leave a half-finished import; the commit only happens at the end."""
        with pytest.raises(UnknownTemplate):
            import_product_templates(
                db, tenant, [_Item(variant.id), _Item("not-a-real-variant-id")]
            )
        db.rollback()
        assert _products(db, tenant) == []

    def test_a_product_template_id_is_NOT_accepted(self, db, tenant):
        """⚠️ THE DISCRIMINATING CASE. `template_id` is a VARIANT id now. Passing a
        PRODUCT id must fail rather than quietly matching — if it resolved, the
        repoint would be reading the wrong tier."""
        pid = db.execute(
            text("SELECT id FROM product_templates LIMIT 1")
        ).scalar_one()
        with pytest.raises(UnknownTemplate):
            import_product_templates(db, tenant, [_Item(pid)])
