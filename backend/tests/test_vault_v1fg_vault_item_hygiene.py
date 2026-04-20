"""Phase V-1f+g — VaultItem dual-write hygiene.

Covers:
  - Migration r30_delivery_caller_vault_item: caller_vault_item_id
    column + partial index on document_deliveries
  - DeliveryService.SendParams accepts caller_vault_item_id
  - Delivery row persists caller_vault_item_id
  - Default None behavior (additive; existing callers unchanged)
  - Quote.create writes a VaultItem with item_type="quote"
  - Quote VaultItem carries correct metadata_json
  - Quote conversion updates the VaultItem status → completed
  - Quote conversion records converted_to_order_id on the VaultItem
  - Quote status change (update_quote_status) refreshes metadata
  - VaultItem-failure does NOT block Quote create (best-effort)

JE dual-write: investigation determined **Case A** — JEs do not
currently write any VaultItem anywhere in the codebase. V-1f+g ships
no JE fix; future decision tracked in DEBT.md. A regression test
below (test_je_posts_do_not_write_vault_item) asserts Case A so a
future JE-VaultItem write doesn't slip in unnoticed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect


# ── Migration r30 shape ───────────────────────────────────────────────


class TestMigrationR30Schema:
    def test_caller_vault_item_id_column_exists(self, db_session):
        insp = inspect(db_session.bind)
        cols = {
            c["name"] for c in insp.get_columns("document_deliveries")
        }
        assert "caller_vault_item_id" in cols

    def test_caller_vault_item_id_is_nullable(self, db_session):
        insp = inspect(db_session.bind)
        col = next(
            c
            for c in insp.get_columns("document_deliveries")
            if c["name"] == "caller_vault_item_id"
        )
        assert col["nullable"] is True

    def test_partial_index_exists(self, db_session):
        insp = inspect(db_session.bind)
        names = {i["name"] for i in insp.get_indexes("document_deliveries")}
        assert "ix_document_deliveries_caller_vault_item_id" in names


# ── DeliveryService.SendParams accepts the new field ─────────────────


class TestSendParamsCallerVaultItemId:
    def test_send_params_accepts_caller_vault_item_id(self):
        from app.services.delivery.delivery_service import (
            RecipientInput,
            SendParams,
        )

        p = SendParams(
            company_id="co-1",
            channel="email",
            recipient=RecipientInput(type="email_address", value="x@y.co"),
            body="hi",
            caller_vault_item_id="vault-item-xyz",
        )
        assert p.caller_vault_item_id == "vault-item-xyz"

    def test_send_params_caller_vault_item_defaults_none(self):
        from app.services.delivery.delivery_service import (
            RecipientInput,
            SendParams,
        )

        p = SendParams(
            company_id="co-1",
            channel="email",
            recipient=RecipientInput(type="email_address", value="x@y.co"),
            body="hi",
        )
        assert p.caller_vault_item_id is None


# ── Delivery row persistence ─────────────────────────────────────────


class TestDeliveryCallerVaultItemPersistence:
    def test_delivery_persists_caller_vault_item_id(
        self, db_session, admin_ctx, make_vault_item
    ):
        """Create a DocumentDelivery row directly with
        caller_vault_item_id set; verify it round-trips via the ORM."""
        from app.models.document_delivery import DocumentDelivery

        vi = make_vault_item(
            company_id=admin_ctx["company_id"],
            item_type="quote",
            title="Quote X",
        )
        d = DocumentDelivery(
            id=str(uuid.uuid4()),
            company_id=admin_ctx["company_id"],
            channel="email",
            recipient_type="email_address",
            recipient_value="a@b.co",
            status="sent",
            caller_vault_item_id=vi.id,
        )
        db_session.add(d)
        db_session.commit()
        db_session.expire_all()
        fresh = (
            db_session.query(DocumentDelivery)
            .filter(DocumentDelivery.id == d.id)
            .one()
        )
        assert fresh.caller_vault_item_id == vi.id
        # Relationship resolves.
        assert fresh.caller_vault_item is not None
        assert fresh.caller_vault_item.id == vi.id

    def test_delivery_without_caller_vault_item_id_unchanged(
        self, db_session, admin_ctx
    ):
        from app.models.document_delivery import DocumentDelivery

        d = DocumentDelivery(
            id=str(uuid.uuid4()),
            company_id=admin_ctx["company_id"],
            channel="email",
            recipient_type="email_address",
            recipient_value="a@b.co",
            status="sent",
        )
        db_session.add(d)
        db_session.commit()
        assert d.caller_vault_item_id is None


# ── Quote VaultItem dual-write ───────────────────────────────────────
# (BUGS.md #7 was resolved 2026-04-20 — the audit_service.log shim
# fixture that used to live here is gone; quote_service now calls
# log_action correctly. Regression coverage lives in
# TestQuoteAuditLogging below.)


class TestQuoteVaultItemDualWrite:
    def test_create_quote_writes_vault_item(
        self, db_session, admin_ctx, make_minimal_company_for_quote
    ):
        from app.models.vault_item import VaultItem
        from app.services import quote_service

        co = admin_ctx["company_id"]
        user = admin_ctx["user_id"]
        result = quote_service.create_quote(
            db_session,
            tenant_id=co,
            user_id=user,
            customer_name="Acme Funeral",
            product_line="funeral_vaults",
            line_items=[
                {"description": "Bronze vault", "quantity": 1, "unit_price": 1000},
            ],
        )
        quote_id = result["id"]
        vi = (
            db_session.query(VaultItem)
            .filter(
                VaultItem.company_id == co,
                VaultItem.item_type == "quote",
                VaultItem.source_entity_id == quote_id,
            )
            .first()
        )
        assert vi is not None
        assert vi.related_entity_type == "quote"
        assert vi.related_entity_id == quote_id
        assert vi.source == "system_generated"
        # Quote number appears in the title.
        assert result["quote_number"] in vi.title
        # Customer name in metadata.
        md = vi.metadata_json or {}
        assert md.get("customer_name") == "Acme Funeral"
        assert md.get("status") == "draft"
        assert md.get("product_line") == "funeral_vaults"

    def test_create_quote_vault_metadata_serializes_decimals(
        self, db_session, admin_ctx, make_minimal_company_for_quote
    ):
        from app.models.vault_item import VaultItem
        from app.services import quote_service

        co = admin_ctx["company_id"]
        result = quote_service.create_quote(
            db_session,
            tenant_id=co,
            user_id=admin_ctx["user_id"],
            customer_name="X Co",
            product_line="wastewater",
            line_items=[
                {"description": "Septic", "quantity": 1, "unit_price": 2500.50},
            ],
        )
        vi = (
            db_session.query(VaultItem)
            .filter(VaultItem.source_entity_id == result["id"])
            .one()
        )
        md = vi.metadata_json or {}
        # Total is stringified so JSONB doesn't trip on Decimal.
        assert isinstance(md.get("total"), str)
        assert md.get("total") == "2500.50"

    def test_convert_quote_updates_vault_item(
        self, db_session, admin_ctx, make_minimal_company_for_quote, make_customer
    ):
        from app.models.vault_item import VaultItem
        from app.services import quote_service

        co = admin_ctx["company_id"]
        user = admin_ctx["user_id"]
        customer = make_customer(company_id=co, name="Convert Co")
        q = quote_service.create_quote(
            db_session,
            tenant_id=co,
            user_id=user,
            customer_name="Convert Co",
            customer_id=customer.id,
            product_line="funeral_vaults",
            line_items=[
                {"description": "Vault", "quantity": 1, "unit_price": 500},
            ],
        )
        order_resp = quote_service.convert_quote_to_order(
            db_session, co, user, q["id"]
        )
        vi = (
            db_session.query(VaultItem)
            .filter(VaultItem.source_entity_id == q["id"])
            .one()
        )
        md = vi.metadata_json or {}
        assert md.get("status") == "converted"
        assert md.get("converted_to_order_id") == order_resp["id"]
        # VaultItem status flipped to completed + completed_at stamped.
        assert vi.status == "completed"
        assert vi.completed_at is not None

    def test_update_quote_status_refreshes_vault_item(
        self, db_session, admin_ctx, make_minimal_company_for_quote
    ):
        from app.models.vault_item import VaultItem
        from app.services import quote_service

        co = admin_ctx["company_id"]
        user = admin_ctx["user_id"]
        q = quote_service.create_quote(
            db_session,
            tenant_id=co,
            user_id=user,
            customer_name="Status Co",
            product_line="wastewater",
            line_items=[
                {"description": "Tank", "quantity": 1, "unit_price": 100},
            ],
        )
        quote_service.update_quote_status(
            db_session, co, user, q["id"], "sent"
        )
        vi = (
            db_session.query(VaultItem)
            .filter(VaultItem.source_entity_id == q["id"])
            .one()
        )
        assert (vi.metadata_json or {}).get("status") == "sent"
        # Not yet converted — status still "active" on VaultItem.
        assert vi.status == "active"
        assert vi.completed_at is None

    def test_vault_item_failure_does_not_block_quote_creation(
        self, db_session, admin_ctx, make_minimal_company_for_quote, monkeypatch
    ):
        """Simulate a VaultItem write failure (e.g. DB hiccup). Quote
        creation must still succeed — the dual-write is best-effort."""
        from app.models.quote import Quote
        from app.services import quote_service
        from app.services import vault_service as vs_module

        def _boom(*args, **kwargs):
            raise RuntimeError("simulated VaultItem failure")

        monkeypatch.setattr(vs_module, "create_vault_item", _boom)
        co = admin_ctx["company_id"]
        user = admin_ctx["user_id"]
        result = quote_service.create_quote(
            db_session,
            tenant_id=co,
            user_id=user,
            customer_name="Resilient Co",
            product_line="funeral_vaults",
            line_items=[
                {"description": "Vault", "quantity": 1, "unit_price": 100},
            ],
        )
        # Quote row persists.
        row = db_session.query(Quote).filter(Quote.id == result["id"]).one()
        assert row.customer_name == "Resilient Co"


# ── JE Case A regression guard ───────────────────────────────────────


class TestJEDualWriteCaseA:
    """V-1f+g investigation concluded Case A: no JE → VaultItem
    dual-write exists. This test guards against a future slip where
    someone adds one without updating the calendar filter (V-2).

    If someone intentionally adds JE VaultItem coverage in a future
    phase, they should delete this test + replace with the correct
    regression for the chosen item_type."""

    def test_je_posts_do_not_write_vault_item_today(self, db_session):
        """Run a grep-equivalent: no source file under
        `app/services/` references both `journal_entry` and
        `create_vault_item` within the same module scope. This is a
        lint-style check; failure means someone added JE dual-write
        and this test needs to be replaced with a real behavioral
        assertion."""
        import pathlib

        services_root = pathlib.Path(__file__).resolve().parent.parent / "app" / "services"
        offending = []
        for p in services_root.rglob("*.py"):
            # Skip vault_service.py itself (defines create_vault_item).
            if p.name == "vault_service.py":
                continue
            # Skip vault_compliance_sync — doesn't touch JEs.
            text = p.read_text()
            if "create_vault_item" in text and (
                "journal_entry" in text.lower()
                or "journalentry" in text.lower()
            ):
                offending.append(str(p.relative_to(services_root)))
        assert offending == [], (
            "Case A assumption broken — JE + VaultItem coexist in: "
            + ", ".join(offending)
            + ". Replace this test with a real regression assertion "
            "for the chosen item_type semantics."
        )


# ── BUGS.md #7 regression: quote audit-log writes ─────────────────────


class TestQuoteAuditLogging:
    """Regression coverage for BUGS.md #7 (resolved 2026-04-20).

    Before the fix, `quote_service` called `audit_service.log(...)` —
    a function that doesn't exist. All three Quote operations
    (create, convert, status change) crashed with AttributeError at
    the audit-log line (post-commit, so DB state persisted but the
    response raised).

    These tests exercise the three call sites end-to-end and verify
    an AuditLog row lands with the expected action string. Match
    the platform-wide convention used by sales_service.py:
    past-participle verbs scoped by entity_type="quote".
    """

    def test_create_quote_writes_created_audit(
        self, db_session, admin_ctx, make_minimal_company_for_quote
    ):
        from app.models.audit_log import AuditLog
        from app.services import quote_service

        co = admin_ctx["company_id"]
        result = quote_service.create_quote(
            db_session,
            tenant_id=co,
            user_id=admin_ctx["user_id"],
            customer_name="Audit-Create Co",
            product_line="wastewater",
            line_items=[
                {"description": "Tank", "quantity": 1, "unit_price": 100},
            ],
        )
        rows = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.company_id == co,
                AuditLog.entity_type == "quote",
                AuditLog.entity_id == result["id"],
                AuditLog.action == "created",
            )
            .all()
        )
        assert len(rows) == 1
        # changes field preserved as JSON.
        assert rows[0].changes is not None
        assert result["quote_number"] in rows[0].changes

    def test_convert_quote_writes_converted_audit(
        self,
        db_session,
        admin_ctx,
        make_minimal_company_for_quote,
        make_customer,
    ):
        from app.models.audit_log import AuditLog
        from app.services import quote_service

        co = admin_ctx["company_id"]
        user = admin_ctx["user_id"]
        customer = make_customer(company_id=co, name="Audit-Convert Co")
        q = quote_service.create_quote(
            db_session,
            tenant_id=co,
            user_id=user,
            customer_name="Audit-Convert Co",
            customer_id=customer.id,
            product_line="funeral_vaults",
            line_items=[
                {"description": "Vault", "quantity": 1, "unit_price": 500},
            ],
        )
        order_resp = quote_service.convert_quote_to_order(
            db_session, co, user, q["id"]
        )
        rows = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.company_id == co,
                AuditLog.entity_type == "quote",
                AuditLog.entity_id == q["id"],
                AuditLog.action == "converted",
            )
            .all()
        )
        assert len(rows) == 1
        assert order_resp["id"] in (rows[0].changes or "")

    def test_update_quote_status_writes_status_changed_audit(
        self, db_session, admin_ctx, make_minimal_company_for_quote
    ):
        from app.models.audit_log import AuditLog
        from app.services import quote_service

        co = admin_ctx["company_id"]
        user = admin_ctx["user_id"]
        q = quote_service.create_quote(
            db_session,
            tenant_id=co,
            user_id=user,
            customer_name="Audit-Status Co",
            product_line="wastewater",
            line_items=[
                {"description": "Tank", "quantity": 1, "unit_price": 100},
            ],
        )
        quote_service.update_quote_status(
            db_session, co, user, q["id"], "sent"
        )
        rows = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.company_id == co,
                AuditLog.entity_type == "quote",
                AuditLog.entity_id == q["id"],
                AuditLog.action == "status_changed",
            )
            .all()
        )
        assert len(rows) == 1
        changes = rows[0].changes or ""
        assert "draft" in changes
        assert "sent" in changes


# ── conftest-ish fixtures ─────────────────────────────────────────────


def _make_tenant_and_admin():
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        slug = f"v1fg-{suffix}"
        co = Company(
            id=str(uuid.uuid4()),
            name=f"V1FG-{suffix}",
            slug=slug,
            is_active=True,
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"admin-{suffix}@v1fg.co",
            first_name="V",
            last_name="FG",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return {
            "user_id": user.id,
            "token": token,
            "company_id": co.id,
            "slug": slug,
        }
    finally:
        db.close()


@pytest.fixture
def admin_ctx():
    return _make_tenant_and_admin()


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def make_vault_item(db_session):
    from app.services.vault_service import create_vault_item

    def _factory(*, company_id: str, item_type: str, title: str):
        vi = create_vault_item(
            db_session,
            company_id=company_id,
            item_type=item_type,
            title=title,
            source="user_upload",
        )
        db_session.commit()
        return vi

    return _factory


@pytest.fixture
def make_minimal_company_for_quote(db_session, admin_ctx):
    """Quote creation touches quote_number sequencing but doesn't
    require any extra setup beyond the Company — fixture exists to
    make the dependency explicit + give us a hook if setup grows."""
    return admin_ctx["company_id"]


@pytest.fixture
def make_customer(db_session):
    """Create a Customer tied to the given company. Needed for the
    convert_quote_to_order path because SalesOrder.customer_id is
    NOT NULL."""
    from app.models.customer import Customer

    def _factory(*, company_id: str, name: str):
        c = Customer(
            id=str(uuid.uuid4()),
            company_id=company_id,
            name=name,
            is_active=True,
        )
        db_session.add(c)
        db_session.commit()
        return c

    return _factory
