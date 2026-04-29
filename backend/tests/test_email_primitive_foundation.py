"""Phase W-4b Layer 1 Step 1 — entity foundation tests.

Coverage:
  - Entity creation + relationships + soft-delete behavior
  - Per-tenant isolation
  - EmailAccountAccess CRUD + access-level rank ordering
  - Provider abstraction registry + 4 stub provider behavior
  - Service layer (account_service.create/get/update/delete + grant/revoke)
  - API endpoints (admin gating, tenant isolation, OAuth scaffolding shape)
  - Audit log discipline (every CRUD writes EmailAuditLog rows)
  - Cross-tenant masking hook present (placeholder per §3.25.x)
"""

from __future__ import annotations

import uuid

import pytest


# ─────────────────────────────────────────────────────────────────────
# Fixtures (match test_spaces_api.py pattern)
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _make_ctx(*, role_slug: str = "admin", vertical: str = "manufacturing"):
    from app.core.security import create_access_token
    from app.database import SessionLocal
    from app.models.company import Company
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        co = Company(
            id=str(uuid.uuid4()),
            name=f"EM-{suffix}",
            slug=f"em-{suffix}",
            is_active=True,
            vertical=vertical,
        )
        db.add(co)
        db.flush()
        role = Role(
            id=str(uuid.uuid4()),
            company_id=co.id,
            name=role_slug.title(),
            slug=role_slug,
            is_system=True,
        )
        db.add(role)
        db.flush()
        user = User(
            id=str(uuid.uuid4()),
            company_id=co.id,
            email=f"u-{suffix}@em.co",
            first_name="EM",
            last_name="User",
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
            "company_id": co.id,
            "token": token,
            "slug": co.slug,
        }
    finally:
        db.close()


@pytest.fixture
def ctx():
    return _make_ctx(role_slug="admin", vertical="manufacturing")


@pytest.fixture
def ctx_b():
    return _make_ctx(role_slug="admin", vertical="funeral_home")


@pytest.fixture
def auth(ctx):
    return {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Company-Slug": ctx["slug"],
    }


@pytest.fixture
def auth_b(ctx_b):
    return {
        "Authorization": f"Bearer {ctx_b['token']}",
        "X-Company-Slug": ctx_b["slug"],
    }


def _second_user(*, company_id: str, role_slug: str = "office"):
    """Create a second user in a tenant for access-grant tests."""
    from app.database import SessionLocal
    from app.models.role import Role
    from app.models.user import User

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:6]
        # Reuse existing role for the tenant if present, else create.
        role = (
            db.query(Role)
            .filter(Role.company_id == company_id, Role.slug == role_slug)
            .first()
        )
        if not role:
            role = Role(
                id=str(uuid.uuid4()),
                company_id=company_id,
                name=role_slug.title(),
                slug=role_slug,
                is_system=False,
            )
            db.add(role)
            db.flush()
        u = User(
            id=str(uuid.uuid4()),
            company_id=company_id,
            email=f"u2-{suffix}@em.co",
            first_name="EM2",
            last_name="User2",
            hashed_password="x",
            is_active=True,
            role_id=role.id,
        )
        db.add(u)
        db.commit()
        return u.id
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────
# 1. Migration — table existence
# ─────────────────────────────────────────────────────────────────────


class TestMigrationSchema:
    def test_all_17_tables_exist(self):
        from sqlalchemy import inspect

        from app.database import engine

        insp = inspect(engine)
        tables = set(insp.get_table_names())
        expected = {
            "email_accounts",
            "email_account_access",
            "email_account_sync_state",
            "email_threads",
            "email_messages",
            "email_attachments",
            "email_participants",
            "message_participants",
            "user_message_read",
            "email_thread_status",
            "internal_comments",
            "email_thread_assignment_log",
            "email_thread_linkages",
            "cross_tenant_thread_pairing",
            "email_labels",
            "email_thread_labels",
            "email_audit_log",
        }
        missing = expected - tables
        assert not missing, f"Missing tables: {missing}"

    def test_email_accounts_check_constraints_present(self):
        # Sanity: the CHECK constraints we declared in the migration
        # are visible via SQL introspection — guards against silent
        # drop during refactor.
        from sqlalchemy import text

        from app.database import SessionLocal

        db = SessionLocal()
        try:
            r = db.execute(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid = 'email_accounts'::regclass "
                    "AND contype = 'c'"
                )
            ).fetchall()
            names = {row[0] for row in r}
            assert "ck_email_accounts_account_type" in names
            assert "ck_email_accounts_provider_type" in names
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 2. Provider registry + 4 stubs
# ─────────────────────────────────────────────────────────────────────


class TestProviderAbstraction:
    def test_all_4_providers_registered(self):
        from app.services.email.providers import PROVIDER_REGISTRY

        assert set(PROVIDER_REGISTRY.keys()) == {
            "gmail",
            "msgraph",
            "imap",
            "transactional",
        }

    def test_provider_classes_implement_abc(self):
        from app.services.email.providers import (
            EmailProvider,
            GmailAPIProvider,
            IMAPProvider,
            MicrosoftGraphProvider,
            TransactionalSendOnlyProvider,
        )

        for cls in (
            GmailAPIProvider,
            MicrosoftGraphProvider,
            IMAPProvider,
            TransactionalSendOnlyProvider,
        ):
            assert issubclass(cls, EmailProvider)
            # provider_type matches registry key
            assert cls.provider_type
            # display_label is set
            assert cls.display_label

    def test_get_provider_class_resolution(self):
        from app.services.email.providers import (
            GmailAPIProvider,
            get_provider_class,
        )

        assert get_provider_class("gmail") is GmailAPIProvider

    def test_get_provider_class_unknown_raises(self):
        from app.services.email.providers import get_provider_class

        with pytest.raises(KeyError):
            get_provider_class("nope")

    def test_imap_connect_validates_required_fields(self):
        from app.services.email.providers import IMAPProvider

        # Missing fields → success=False
        p = IMAPProvider({})
        result = p.connect()
        assert result.success is False
        assert "missing required fields" in (result.error_message or "").lower()

        # All required fields → success=True (stub-level)
        p2 = IMAPProvider(
            {
                "imap_server": "imap.example.com",
                "imap_port": 993,
                "smtp_server": "smtp.example.com",
                "smtp_port": 587,
                "username": "u@example.com",
            }
        )
        result2 = p2.connect()
        assert result2.success is True
        assert "step 2" in (result2.error_message or "").lower()

    def test_transactional_connect_succeeds_immediately(self):
        from app.services.email.providers import TransactionalSendOnlyProvider

        p = TransactionalSendOnlyProvider({"email_address": "send@example.com"})
        result = p.connect()
        assert result.success is True
        assert result.config_to_persist["routes_through"] == "delivery_service"

    def test_transactional_supports_inbound_false(self):
        from app.services.email.providers import TransactionalSendOnlyProvider

        assert TransactionalSendOnlyProvider.supports_inbound is False

    def test_transactional_sync_initial_raises_not_applicable(self):
        from app.services.email.providers import TransactionalSendOnlyProvider

        p = TransactionalSendOnlyProvider({})
        with pytest.raises(NotImplementedError, match="outbound-only"):
            p.sync_initial()

    def test_oauth_authorize_url_shape(self):
        from app.services.email.providers import (
            GmailAPIProvider,
            MicrosoftGraphProvider,
        )

        gmail_url = GmailAPIProvider.oauth_authorize_url(
            state="abc", redirect_uri="https://app/cb"
        )
        assert gmail_url.startswith("https://accounts.google.com/")
        assert "state=abc" in gmail_url
        assert "redirect_uri=https://app/cb" in gmail_url

        ms_url = MicrosoftGraphProvider.oauth_authorize_url(
            state="xyz", redirect_uri="https://app/cb2"
        )
        assert ms_url.startswith("https://login.microsoftonline.com/")
        assert "state=xyz" in ms_url


# ─────────────────────────────────────────────────────────────────────
# 3. Service layer — EmailAccount CRUD
# ─────────────────────────────────────────────────────────────────────


class TestAccountServiceCRUD:
    def test_create_account_basic(self, ctx):
        from app.database import SessionLocal
        from app.services.email import account_service

        db = SessionLocal()
        try:
            account = account_service.create_account(
                db,
                tenant_id=ctx["company_id"],
                actor_user_id=ctx["user_id"],
                account_type="shared",
                display_name="Sales Inbox",
                email_address="sales@example.com",
                provider_type="gmail",
            )
            db.commit()
            assert account.id
            assert account.email_address == "sales@example.com"
            assert account.is_active is True
            assert account.is_default is False
            # Sync state row created
            assert account.sync_state is not None
            assert account.sync_state.sync_status == "pending"
        finally:
            db.close()

    def test_create_account_first_is_default_when_explicit(self, ctx):
        from app.database import SessionLocal
        from app.services.email import account_service

        db = SessionLocal()
        try:
            a = account_service.create_account(
                db,
                tenant_id=ctx["company_id"],
                actor_user_id=ctx["user_id"],
                account_type="shared",
                display_name="A",
                email_address="a@x.com",
                provider_type="gmail",
                is_default=True,
            )
            db.commit()
            assert a.is_default is True

            # Second account with is_default=True demotes the first
            b = account_service.create_account(
                db,
                tenant_id=ctx["company_id"],
                actor_user_id=ctx["user_id"],
                account_type="shared",
                display_name="B",
                email_address="b@x.com",
                provider_type="imap",
                is_default=True,
            )
            db.commit()
            db.refresh(a)
            assert a.is_default is False
            assert b.is_default is True
        finally:
            db.close()

    def test_create_account_duplicate_email_conflict(self, ctx):
        from app.database import SessionLocal
        from app.services.email import account_service
        from app.services.email.account_service import EmailAccountConflict

        db = SessionLocal()
        try:
            account_service.create_account(
                db,
                tenant_id=ctx["company_id"],
                actor_user_id=ctx["user_id"],
                account_type="shared",
                display_name="A",
                email_address="dup@x.com",
                provider_type="gmail",
            )
            db.commit()
            with pytest.raises(EmailAccountConflict):
                account_service.create_account(
                    db,
                    tenant_id=ctx["company_id"],
                    actor_user_id=ctx["user_id"],
                    account_type="shared",
                    display_name="B",
                    email_address="dup@x.com",
                    provider_type="imap",
                )
        finally:
            db.rollback()
            db.close()

    def test_create_account_invalid_provider_type(self, ctx):
        from app.database import SessionLocal
        from app.services.email import account_service
        from app.services.email.account_service import EmailAccountValidation

        db = SessionLocal()
        try:
            with pytest.raises(EmailAccountValidation):
                account_service.create_account(
                    db,
                    tenant_id=ctx["company_id"],
                    actor_user_id=ctx["user_id"],
                    account_type="shared",
                    display_name="A",
                    email_address="x@x.com",
                    provider_type="bogus",
                )
        finally:
            db.close()

    def test_get_account_cross_tenant_404(self, ctx, ctx_b):
        from app.database import SessionLocal
        from app.services.email import account_service
        from app.services.email.account_service import EmailAccountNotFound

        db = SessionLocal()
        try:
            account = account_service.create_account(
                db,
                tenant_id=ctx["company_id"],
                actor_user_id=ctx["user_id"],
                account_type="shared",
                display_name="A",
                email_address="a@x.com",
                provider_type="gmail",
            )
            db.commit()
            # Same ID, different tenant → not found
            with pytest.raises(EmailAccountNotFound):
                account_service.get_account(
                    db,
                    account_id=account.id,
                    tenant_id=ctx_b["company_id"],
                )
        finally:
            db.close()

    def test_update_account_partial_patch(self, ctx):
        from app.database import SessionLocal
        from app.services.email import account_service

        db = SessionLocal()
        try:
            account = account_service.create_account(
                db,
                tenant_id=ctx["company_id"],
                actor_user_id=ctx["user_id"],
                account_type="shared",
                display_name="A",
                email_address="a@x.com",
                provider_type="gmail",
            )
            db.commit()

            updated = account_service.update_account(
                db,
                account_id=account.id,
                tenant_id=ctx["company_id"],
                actor_user_id=ctx["user_id"],
                display_name="A renamed",
            )
            db.commit()
            assert updated.display_name == "A renamed"
            assert updated.email_address == "a@x.com"  # unchanged
        finally:
            db.close()

    def test_delete_account_soft(self, ctx):
        from app.database import SessionLocal
        from app.services.email import account_service

        db = SessionLocal()
        try:
            account = account_service.create_account(
                db,
                tenant_id=ctx["company_id"],
                actor_user_id=ctx["user_id"],
                account_type="shared",
                display_name="A",
                email_address="a@x.com",
                provider_type="gmail",
            )
            db.commit()
            account_id = account.id

            account_service.delete_account(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
                actor_user_id=ctx["user_id"],
            )
            db.commit()

            # Row still exists (soft-delete)
            refetched = account_service.get_account(
                db, account_id=account_id, tenant_id=ctx["company_id"]
            )
            assert refetched.is_active is False
            assert refetched.is_default is False
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 4. Service layer — EmailAccountAccess CRUD + access control
# ─────────────────────────────────────────────────────────────────────


class TestAccessControl:
    def test_grant_and_check_access_basic(self, ctx):
        from app.database import SessionLocal
        from app.services.email import account_service

        db = SessionLocal()
        try:
            account = account_service.create_account(
                db,
                tenant_id=ctx["company_id"],
                actor_user_id=ctx["user_id"],
                account_type="shared",
                display_name="A",
                email_address="a@x.com",
                provider_type="gmail",
            )
            db.commit()

            other_user_id = _second_user(company_id=ctx["company_id"])
            account_service.grant_access(
                db,
                account_id=account.id,
                tenant_id=ctx["company_id"],
                user_id=other_user_id,
                access_level="read_write",
                actor_user_id=ctx["user_id"],
            )
            db.commit()

            assert (
                account_service.user_has_access(
                    db,
                    account_id=account.id,
                    user_id=other_user_id,
                    required_level="read",
                )
                is True
            )
            assert (
                account_service.user_has_access(
                    db,
                    account_id=account.id,
                    user_id=other_user_id,
                    required_level="read_write",
                )
                is True
            )
            assert (
                account_service.user_has_access(
                    db,
                    account_id=account.id,
                    user_id=other_user_id,
                    required_level="admin",
                )
                is False
            )
        finally:
            db.close()

    def test_grant_idempotent_same_level(self, ctx):
        from app.database import SessionLocal
        from app.services.email import account_service

        db = SessionLocal()
        try:
            account = account_service.create_account(
                db,
                tenant_id=ctx["company_id"],
                actor_user_id=ctx["user_id"],
                account_type="shared",
                display_name="A",
                email_address="a@x.com",
                provider_type="gmail",
            )
            db.commit()

            other_user_id = _second_user(company_id=ctx["company_id"])
            g1 = account_service.grant_access(
                db,
                account_id=account.id,
                tenant_id=ctx["company_id"],
                user_id=other_user_id,
                access_level="read",
                actor_user_id=ctx["user_id"],
            )
            db.commit()

            g2 = account_service.grant_access(
                db,
                account_id=account.id,
                tenant_id=ctx["company_id"],
                user_id=other_user_id,
                access_level="read",
                actor_user_id=ctx["user_id"],
            )
            db.commit()
            assert g1.id == g2.id  # same row reused
        finally:
            db.close()

    def test_grant_change_level_updates_existing(self, ctx):
        from app.database import SessionLocal
        from app.services.email import account_service

        db = SessionLocal()
        try:
            account = account_service.create_account(
                db,
                tenant_id=ctx["company_id"],
                actor_user_id=ctx["user_id"],
                account_type="shared",
                display_name="A",
                email_address="a@x.com",
                provider_type="gmail",
            )
            db.commit()

            other_user_id = _second_user(company_id=ctx["company_id"])
            g1 = account_service.grant_access(
                db,
                account_id=account.id,
                tenant_id=ctx["company_id"],
                user_id=other_user_id,
                access_level="read",
                actor_user_id=ctx["user_id"],
            )
            db.commit()

            g2 = account_service.grant_access(
                db,
                account_id=account.id,
                tenant_id=ctx["company_id"],
                user_id=other_user_id,
                access_level="admin",
                actor_user_id=ctx["user_id"],
            )
            db.commit()
            assert g1.id == g2.id  # same row updated, not new row
            assert g2.access_level == "admin"
        finally:
            db.close()

    def test_revoke_access_idempotent(self, ctx):
        from app.database import SessionLocal
        from app.services.email import account_service

        db = SessionLocal()
        try:
            account = account_service.create_account(
                db,
                tenant_id=ctx["company_id"],
                actor_user_id=ctx["user_id"],
                account_type="shared",
                display_name="A",
                email_address="a@x.com",
                provider_type="gmail",
            )
            db.commit()
            other_user_id = _second_user(company_id=ctx["company_id"])
            account_service.grant_access(
                db,
                account_id=account.id,
                tenant_id=ctx["company_id"],
                user_id=other_user_id,
                access_level="read",
                actor_user_id=ctx["user_id"],
            )
            db.commit()

            assert (
                account_service.revoke_access(
                    db,
                    account_id=account.id,
                    tenant_id=ctx["company_id"],
                    user_id=other_user_id,
                    actor_user_id=ctx["user_id"],
                )
                is True
            )
            db.commit()

            # Second revoke is idempotent: returns False, no error.
            assert (
                account_service.revoke_access(
                    db,
                    account_id=account.id,
                    tenant_id=ctx["company_id"],
                    user_id=other_user_id,
                    actor_user_id=ctx["user_id"],
                )
                is False
            )
        finally:
            db.close()

    def test_require_access_403_when_no_grant(self, ctx):
        from app.database import SessionLocal
        from app.services.email import account_service
        from app.services.email.account_service import (
            EmailAccountPermissionDenied,
        )

        db = SessionLocal()
        try:
            account = account_service.create_account(
                db,
                tenant_id=ctx["company_id"],
                actor_user_id=ctx["user_id"],
                account_type="shared",
                display_name="A",
                email_address="a@x.com",
                provider_type="gmail",
            )
            db.commit()
            other_user_id = _second_user(company_id=ctx["company_id"])
            with pytest.raises(EmailAccountPermissionDenied):
                account_service.require_access(
                    db,
                    account_id=account.id,
                    user_id=other_user_id,
                    tenant_id=ctx["company_id"],
                    required_level="read",
                )
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 5. Audit log discipline (§3.26.15.8)
# ─────────────────────────────────────────────────────────────────────


class TestAuditLog:
    def test_create_writes_audit_row(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailAuditLog
        from app.services.email import account_service

        db = SessionLocal()
        try:
            account = account_service.create_account(
                db,
                tenant_id=ctx["company_id"],
                actor_user_id=ctx["user_id"],
                account_type="shared",
                display_name="Audit Test",
                email_address="audit@x.com",
                provider_type="gmail",
            )
            db.commit()
            entries = (
                db.query(EmailAuditLog)
                .filter(
                    EmailAuditLog.tenant_id == ctx["company_id"],
                    EmailAuditLog.entity_type == "email_account",
                    EmailAuditLog.entity_id == account.id,
                )
                .all()
            )
            assert len(entries) == 1
            assert entries[0].action == "account_created"
            assert entries[0].actor_user_id == ctx["user_id"]
        finally:
            db.close()

    def test_grant_revoke_writes_audit_rows(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailAuditLog
        from app.services.email import account_service

        db = SessionLocal()
        try:
            account = account_service.create_account(
                db,
                tenant_id=ctx["company_id"],
                actor_user_id=ctx["user_id"],
                account_type="shared",
                display_name="A",
                email_address="a@x.com",
                provider_type="gmail",
            )
            db.commit()
            other = _second_user(company_id=ctx["company_id"])
            account_service.grant_access(
                db,
                account_id=account.id,
                tenant_id=ctx["company_id"],
                user_id=other,
                access_level="read",
                actor_user_id=ctx["user_id"],
            )
            db.commit()
            account_service.revoke_access(
                db,
                account_id=account.id,
                tenant_id=ctx["company_id"],
                user_id=other,
                actor_user_id=ctx["user_id"],
            )
            db.commit()

            actions = [
                e.action
                for e in db.query(EmailAuditLog)
                .filter(
                    EmailAuditLog.tenant_id == ctx["company_id"],
                    EmailAuditLog.entity_type == "email_account_access",
                )
                .all()
            ]
            assert "access_granted" in actions
            assert "access_revoked" in actions
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 6. Cross-tenant masking hook (placeholder per §3.25.x)
# ─────────────────────────────────────────────────────────────────────


class TestCrossTenantMaskingHook:
    def test_thread_has_masking_method(self):
        from app.models.email_primitive import EmailThread

        # The hook exists; Step 1 always returns False (no masking
        # enforced yet). Subsequent steps wire real masking.
        assert hasattr(EmailThread, "is_field_masked_for")
        # Static check: signature accepts (field, caller_tenant_id)
        # via test instantiation against a stub.
        thread = EmailThread.__new__(EmailThread)
        assert thread.is_field_masked_for("subject", "any-tenant") is False


# ─────────────────────────────────────────────────────────────────────
# 7. API endpoints
# ─────────────────────────────────────────────────────────────────────


class TestEmailAccountsAPI:
    def test_list_providers(self, client, auth):
        r = client.get("/api/v1/email-accounts/providers", headers=auth)
        assert r.status_code == 200
        data = r.json()
        provider_types = {p["provider_type"] for p in data}
        assert provider_types == {"gmail", "msgraph", "imap", "transactional"}

    def test_list_accounts_empty_then_create(self, client, auth):
        r = client.get("/api/v1/email-accounts", headers=auth)
        assert r.status_code == 200
        assert r.json() == []

        r2 = client.post(
            "/api/v1/email-accounts",
            json={
                "account_type": "shared",
                "display_name": "Sales",
                "email_address": "sales@example.com",
                "provider_type": "gmail",
            },
            headers=auth,
        )
        assert r2.status_code == 201
        body = r2.json()
        assert body["email_address"] == "sales@example.com"
        # Creator was auto-granted admin access → /mine returns it
        rm = client.get("/api/v1/email-accounts/mine", headers=auth)
        assert rm.status_code == 200
        assert any(a["id"] == body["id"] for a in rm.json())

    def test_get_account_cross_tenant_404(self, client, auth, auth_b):
        r = client.post(
            "/api/v1/email-accounts",
            json={
                "account_type": "shared",
                "display_name": "X",
                "email_address": "x@a.com",
                "provider_type": "gmail",
            },
            headers=auth,
        )
        account_id = r.json()["id"]
        r2 = client.get(
            f"/api/v1/email-accounts/{account_id}", headers=auth_b
        )
        assert r2.status_code == 404

    def test_update_account_via_api(self, client, auth):
        r = client.post(
            "/api/v1/email-accounts",
            json={
                "account_type": "shared",
                "display_name": "Old",
                "email_address": "a@x.com",
                "provider_type": "gmail",
            },
            headers=auth,
        )
        account_id = r.json()["id"]
        r2 = client.patch(
            f"/api/v1/email-accounts/{account_id}",
            json={"display_name": "New", "is_default": True},
            headers=auth,
        )
        assert r2.status_code == 200
        assert r2.json()["display_name"] == "New"
        assert r2.json()["is_default"] is True

    def test_delete_account_via_api(self, client, auth):
        r = client.post(
            "/api/v1/email-accounts",
            json={
                "account_type": "shared",
                "display_name": "ToDelete",
                "email_address": "del@x.com",
                "provider_type": "gmail",
            },
            headers=auth,
        )
        account_id = r.json()["id"]
        r2 = client.delete(
            f"/api/v1/email-accounts/{account_id}", headers=auth
        )
        assert r2.status_code == 200
        assert r2.json() == {"deleted": True}
        # Default include_inactive=False hides it
        r3 = client.get("/api/v1/email-accounts", headers=auth)
        assert all(a["id"] != account_id for a in r3.json())
        r4 = client.get(
            "/api/v1/email-accounts?include_inactive=true", headers=auth
        )
        assert any(
            a["id"] == account_id and a["is_active"] is False for a in r4.json()
        )

    def test_grant_and_revoke_access_via_api(self, client, auth, ctx):
        r = client.post(
            "/api/v1/email-accounts",
            json={
                "account_type": "shared",
                "display_name": "S",
                "email_address": "s@x.com",
                "provider_type": "gmail",
            },
            headers=auth,
        )
        account_id = r.json()["id"]
        other = _second_user(company_id=ctx["company_id"])
        r2 = client.post(
            f"/api/v1/email-accounts/{account_id}/access",
            json={"user_id": other, "access_level": "read_write"},
            headers=auth,
        )
        assert r2.status_code == 201
        # List shows 2 grants (creator admin + new read_write)
        r3 = client.get(
            f"/api/v1/email-accounts/{account_id}/access", headers=auth
        )
        assert r3.status_code == 200
        levels = {g["access_level"] for g in r3.json()}
        assert "admin" in levels and "read_write" in levels
        # Revoke
        r4 = client.delete(
            f"/api/v1/email-accounts/{account_id}/access/{other}",
            headers=auth,
        )
        assert r4.status_code == 200
        assert r4.json() == {"revoked": True}

    def test_oauth_authorize_url_shape(self, client, auth):
        r = client.get(
            "/api/v1/email-accounts/oauth/gmail/authorize-url"
            "?redirect_uri=https://app.example.com/cb",
            headers=auth,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["authorize_url"].startswith("https://accounts.google.com/")
        assert body["state"]
        assert "REPLACE_IN_STEP_2" in body["authorize_url"]

    def test_oauth_authorize_url_rejects_unknown_provider(self, client, auth):
        r = client.get(
            "/api/v1/email-accounts/oauth/bogus/authorize-url"
            "?redirect_uri=https://app/cb",
            headers=auth,
        )
        assert r.status_code == 400

    def test_oauth_authorize_url_rejects_non_oauth_provider(self, client, auth):
        # transactional + imap don't use OAuth
        r = client.get(
            "/api/v1/email-accounts/oauth/transactional/authorize-url"
            "?redirect_uri=https://app/cb",
            headers=auth,
        )
        assert r.status_code == 400

    def test_create_requires_admin(self, client, ctx):
        # Create a non-admin user in the same tenant
        from app.core.security import create_access_token
        from app.database import SessionLocal
        from app.models.role import Role
        from app.models.user import User

        db = SessionLocal()
        try:
            suffix = uuid.uuid4().hex[:6]
            office_role = Role(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                name="Office",
                slug="office",
                is_system=False,
            )
            db.add(office_role)
            db.flush()
            office_user = User(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                email=f"office-{suffix}@em.co",
                first_name="O",
                last_name="U",
                hashed_password="x",
                is_active=True,
                is_super_admin=False,
                role_id=office_role.id,
            )
            db.add(office_user)
            db.commit()
            office_token = create_access_token(
                {"sub": office_user.id, "company_id": ctx["company_id"]}
            )
        finally:
            db.close()

        office_auth = {
            "Authorization": f"Bearer {office_token}",
            "X-Company-Slug": ctx["slug"],
        }
        r = client.post(
            "/api/v1/email-accounts",
            json={
                "account_type": "shared",
                "display_name": "T",
                "email_address": "t@x.com",
                "provider_type": "gmail",
            },
            headers=office_auth,
        )
        assert r.status_code in (401, 403)
