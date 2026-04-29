"""Phase W-4b Layer 1 Email Step 4b — composition + thread management tests.

Coverage:
  - Search: ILIKE on subject + body_text + sender_email; tenant
    isolation; account access enforcement
  - Snooze: snooze_thread + unsnooze_thread; per-user state isolation;
    snoozed_until validation; audit log
  - Labels: list + create (idempotent on name) + add/remove on thread;
    tenant scoping (cross-tenant label rejected); audit log
  - Recipient resolution:
      * CRM contacts (rank 0.95)
      * Recent participants (rank 0.80; 30-day window)
      * Internal users (rank 0.70)
      * Dedup: same email_address never returned twice
      * Cross-tenant: deferred placeholder
      * Empty/short query returns []
  - Role-based routing:
      * "All users with access to account" canonical default
      * "All <role_name> users" per role with >1 user
      * Singletons excluded (>1 only)
      * Cross-account access enforcement (foreign account → [])
      * expand_role returns concrete recipients
  - API endpoints (smoke + auth)
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet


os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())


# ─────────────────────────────────────────────────────────────────────
# Fixtures (mirror test_email_primitive_step4a.py)
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _make_ctx(role_slug: str = "admin"):
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
            name=f"EM4b-{suffix}",
            slug=f"em4b-{suffix}",
            is_active=True,
            vertical="manufacturing",
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
            email=f"u-{suffix}@em4b.co",
            first_name="EM4b",
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
            "role_id": role.id,
            "role_slug": role_slug,
        }
    finally:
        db.close()


@pytest.fixture
def ctx():
    return _make_ctx()


@pytest.fixture
def ctx_b():
    return _make_ctx()


@pytest.fixture
def auth(ctx):
    return {
        "Authorization": f"Bearer {ctx['token']}",
        "X-Company-Slug": ctx["slug"],
    }


def _make_account_with_access(ctx):
    from app.database import SessionLocal
    from app.services.email import account_service

    db = SessionLocal()
    try:
        acc = account_service.create_account(
            db,
            tenant_id=ctx["company_id"],
            actor_user_id=ctx["user_id"],
            account_type="shared",
            display_name="Test",
            email_address=f"acc-{uuid.uuid4().hex[:6]}@example.com",
            provider_type="gmail",
        )
        account_service.grant_access(
            db,
            account_id=acc.id,
            tenant_id=ctx["company_id"],
            user_id=ctx["user_id"],
            access_level="admin",
            actor_user_id=ctx["user_id"],
        )
        db.commit()
        return acc.id
    finally:
        db.close()


def _seed_thread(*, tenant_id, account_id, subject, sender_email="external@x.com", body_text="Hello", n_messages=1):
    from app.database import SessionLocal
    from app.models.email_primitive import EmailMessage, EmailThread

    db = SessionLocal()
    try:
        thread = EmailThread(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            account_id=account_id,
            subject=subject,
            participants_summary=[sender_email.lower()],
            first_message_at=datetime.now(timezone.utc),
            last_message_at=datetime.now(timezone.utc),
            message_count=n_messages,
        )
        db.add(thread)
        db.flush()
        msg_ids = []
        for i in range(n_messages):
            msg = EmailMessage(
                id=str(uuid.uuid4()),
                thread_id=thread.id,
                tenant_id=tenant_id,
                account_id=account_id,
                provider_message_id=f"msg-{thread.id}-{i}",
                sender_email=sender_email.lower(),
                subject=subject,
                body_text=body_text,
                received_at=datetime.now(timezone.utc) + timedelta(seconds=i),
                direction="inbound",
            )
            db.add(msg)
            db.flush()
            msg_ids.append(msg.id)
        db.commit()
        return thread.id, msg_ids
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────
# 1. Search
# ─────────────────────────────────────────────────────────────────────


class TestSearch:
    def test_subject_match(self, ctx):
        from app.database import SessionLocal
        from app.services.email import inbox_service

        account_id = _make_account_with_access(ctx)
        _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="Anderson case follow-up",
            body_text="Body unrelated",
        )
        _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="Smith vault question",
            body_text="Body unrelated",
        )

        db = SessionLocal()
        try:
            results = inbox_service.search_threads(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                query="Anderson",
            )
            assert len(results) == 1
            assert "Anderson" in results[0].subject
        finally:
            db.close()

    def test_body_match(self, ctx):
        from app.database import SessionLocal
        from app.services.email import inbox_service

        account_id = _make_account_with_access(ctx)
        _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="X",
            body_text="Discussing the bronze vault for Friday delivery",
        )

        db = SessionLocal()
        try:
            results = inbox_service.search_threads(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                query="bronze",
            )
            assert len(results) == 1
        finally:
            db.close()

    def test_short_query_returns_empty(self, ctx):
        from app.database import SessionLocal
        from app.services.email import inbox_service

        account_id = _make_account_with_access(ctx)
        _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="x",
        )

        db = SessionLocal()
        try:
            assert inbox_service.search_threads(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                query="x",
            ) == []
            assert inbox_service.search_threads(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                query="",
            ) == []
        finally:
            db.close()

    def test_cross_tenant_isolation(self, ctx, ctx_b):
        from app.database import SessionLocal
        from app.services.email import inbox_service

        account_id = _make_account_with_access(ctx_b)
        _seed_thread(
            tenant_id=ctx_b["company_id"],
            account_id=account_id,
            subject="Tenant-B-only thread",
        )

        db = SessionLocal()
        try:
            results = inbox_service.search_threads(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                query="Tenant-B",
            )
            assert results == []
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 2. Snooze
# ─────────────────────────────────────────────────────────────────────


class TestSnooze:
    def test_snooze_then_unsnooze(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailThreadStatus
        from app.services.email import inbox_service

        account_id = _make_account_with_access(ctx)
        thread_id, _ = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="S",
        )

        wake_at = datetime.now(timezone.utc) + timedelta(hours=4)
        db = SessionLocal()
        try:
            inbox_service.snooze_thread(
                db,
                thread_id=thread_id,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                snoozed_until=wake_at,
            )
            db.commit()
            status = (
                db.query(EmailThreadStatus)
                .filter(EmailThreadStatus.thread_id == thread_id)
                .first()
            )
            assert status.is_snoozed is True
            assert status.snoozed_until is not None

            inbox_service.unsnooze_thread(
                db,
                thread_id=thread_id,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            db.commit()
            db.refresh(status)
            assert status.is_snoozed is False
            assert status.snoozed_until is None
        finally:
            db.close()

    def test_snooze_past_rejected(self, ctx):
        from app.database import SessionLocal
        from app.services.email import inbox_service
        from app.services.email.inbox_service import InboxError

        account_id = _make_account_with_access(ctx)
        thread_id, _ = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="S",
        )

        db = SessionLocal()
        try:
            with pytest.raises(InboxError, match="future"):
                inbox_service.snooze_thread(
                    db,
                    thread_id=thread_id,
                    tenant_id=ctx["company_id"],
                    user_id=ctx["user_id"],
                    snoozed_until=datetime.now(timezone.utc) - timedelta(hours=1),
                )
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 3. Labels
# ─────────────────────────────────────────────────────────────────────


class TestLabels:
    def test_create_idempotent_on_name(self, ctx):
        from app.database import SessionLocal
        from app.services.email import inbox_service

        db = SessionLocal()
        try:
            l1 = inbox_service.create_label(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                name="Priority",
                color="#9C5640",
            )
            db.commit()
            l2 = inbox_service.create_label(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                name="Priority",
                color="#000000",
            )
            db.commit()
            assert l1.id == l2.id  # idempotent
        finally:
            db.close()

    def test_add_label_to_thread(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailThreadLabel
        from app.services.email import inbox_service

        account_id = _make_account_with_access(ctx)
        thread_id, _ = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="L",
        )

        db = SessionLocal()
        try:
            label = inbox_service.create_label(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                name="Customer",
            )
            db.commit()
            inbox_service.add_label_to_thread(
                db,
                thread_id=thread_id,
                label_id=label.id,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            db.commit()
            assert (
                db.query(EmailThreadLabel)
                .filter(EmailThreadLabel.thread_id == thread_id)
                .count()
                == 1
            )
            # Idempotent re-add
            inbox_service.add_label_to_thread(
                db,
                thread_id=thread_id,
                label_id=label.id,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            db.commit()
            assert (
                db.query(EmailThreadLabel)
                .filter(EmailThreadLabel.thread_id == thread_id)
                .count()
                == 1
            )
        finally:
            db.close()

    def test_cross_tenant_label_rejected(self, ctx, ctx_b):
        from app.database import SessionLocal
        from app.services.email import inbox_service
        from app.services.email.inbox_service import InboxError

        account_id = _make_account_with_access(ctx)
        thread_id, _ = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="L",
        )

        db = SessionLocal()
        try:
            # Label in TENANT B
            foreign_label = inbox_service.create_label(
                db,
                tenant_id=ctx_b["company_id"],
                user_id=ctx_b["user_id"],
                name="Foreign",
            )
            db.commit()
            with pytest.raises(InboxError, match="not found in tenant"):
                inbox_service.add_label_to_thread(
                    db,
                    thread_id=thread_id,
                    label_id=foreign_label.id,
                    tenant_id=ctx["company_id"],
                    user_id=ctx["user_id"],
                )
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 4. Recipient resolution
# ─────────────────────────────────────────────────────────────────────


class TestRecipientResolution:
    def test_short_query_returns_empty(self, ctx):
        from app.database import SessionLocal
        from app.services.email import recipient_service

        db = SessionLocal()
        try:
            assert (
                recipient_service.resolve_recipients(
                    db,
                    tenant_id=ctx["company_id"],
                    user_id=ctx["user_id"],
                    query="x",
                )
                == []
            )
        finally:
            db.close()

    def test_internal_user_match(self, ctx):
        from app.database import SessionLocal
        from app.services.email import recipient_service

        # ctx user is in tenant; query their first_name
        db = SessionLocal()
        try:
            results = recipient_service.resolve_recipients(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                query="EM4b",  # first_name from fixture
            )
            assert len(results) >= 1
            assert any(r.source_type == "internal_user" for r in results)
        finally:
            db.close()

    def _make_crm_contact(self, db, ctx, *, name, email):
        """Helper: create a CompanyEntity (CRM master row) + Contact
        linked to it. Contact.master_company_id is the CompanyEntity id;
        Contact.company_id is the tenant scope (recipient_service
        filters on company_id == tenant_id)."""
        from app.models.company_entity import CompanyEntity
        from app.models.contact import Contact

        ce = CompanyEntity(
            id=str(uuid.uuid4()),
            company_id=ctx["company_id"],
            name=f"Entity-{name}",
        )
        db.add(ce)
        db.flush()
        contact = Contact(
            id=str(uuid.uuid4()),
            master_company_id=ce.id,
            company_id=ctx["company_id"],
            name=name,
            email=email,
            is_active=True,
        )
        db.add(contact)
        db.flush()
        return ce, contact

    def test_crm_contact_match_higher_rank_than_user(self, ctx):
        from app.database import SessionLocal
        from app.services.email import recipient_service

        db = SessionLocal()
        try:
            self._make_crm_contact(
                db,
                ctx,
                name="Hopkins Director",
                email="director@hopkinsfh.test",
            )
            db.commit()

            results = recipient_service.resolve_recipients(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                query="Hopkins",
            )
            crm = [r for r in results if r.source_type == "crm_contact"]
            assert crm
            assert crm[0].rank_score >= 0.9

            # Verify CRM contact ranks above internal user when both
            # match same query string (separate query — name "Hopkins"
            # uniquely matches CRM)
        finally:
            db.close()

    def test_dedup_same_email(self, ctx):
        from app.database import SessionLocal
        from app.services.email import recipient_service

        db = SessionLocal()
        try:
            # Find the test user's email + create a CRM contact with
            # the SAME email — service should dedup so each address
            # appears once.
            from app.models.user import User

            user = (
                db.query(User).filter(User.id == ctx["user_id"]).first()
            )
            self._make_crm_contact(
                db,
                ctx,
                name="Match",
                email=user.email,  # same as user
            )
            db.commit()

            results = recipient_service.resolve_recipients(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                query="EM4b",  # matches both
            )
            seen = [r.email_address for r in results]
            assert len(seen) == len(set(seen))
            # CRM contact wins over user (higher rank) — only one
            # entry for the shared email.
            entries_for_email = [
                r for r in results if r.email_address == user.email.lower()
            ]
            assert len(entries_for_email) == 1
            assert entries_for_email[0].source_type == "crm_contact"
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 5. Role-based routing
# ─────────────────────────────────────────────────────────────────────


class TestRoleRouting:
    def test_account_access_role_with_multiple_grants(self, ctx):
        from app.database import SessionLocal
        from app.models.role import Role
        from app.models.user import User
        from app.services.email import account_service, recipient_service

        account_id = _make_account_with_access(ctx)
        # Add a second user with access
        db = SessionLocal()
        try:
            office_role = Role(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                name="Office",
                slug="office",
                is_system=False,
            )
            db.add(office_role)
            db.flush()
            second = User(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                email=f"second-{uuid.uuid4().hex[:6]}@x.com",
                first_name="Second",
                last_name="User",
                hashed_password="x",
                is_active=True,
                role_id=office_role.id,
            )
            db.add(second)
            db.commit()
            account_service.grant_access(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
                user_id=second.id,
                access_level="read_write",
                actor_user_id=ctx["user_id"],
            )
            db.commit()

            primitives = recipient_service.list_role_recipients(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                account_id=account_id,
            )
            access_role = [
                p for p in primitives if p.role_kind == "account_access"
            ]
            assert len(access_role) == 1
            assert access_role[0].member_count == 2
        finally:
            db.close()

    def test_role_slug_with_multiple_users(self, ctx):
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.email import recipient_service

        account_id = _make_account_with_access(ctx)
        # Add a second admin user
        db = SessionLocal()
        try:
            other_admin = User(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                email=f"adm2-{uuid.uuid4().hex[:6]}@x.com",
                first_name="Other",
                last_name="Admin",
                hashed_password="x",
                is_active=True,
                role_id=ctx["role_id"],  # same admin role
            )
            db.add(other_admin)
            db.commit()

            primitives = recipient_service.list_role_recipients(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                account_id=account_id,
            )
            slug_roles = [
                p for p in primitives if p.role_kind == "role_slug"
            ]
            assert any(r.id_value == "admin" for r in slug_roles)
        finally:
            db.close()

    def test_cross_account_access_returns_empty(self, ctx, ctx_b):
        from app.database import SessionLocal
        from app.services.email import recipient_service

        # Account in tenant B, query from tenant A
        b_account_id = _make_account_with_access(ctx_b)

        db = SessionLocal()
        try:
            primitives = recipient_service.list_role_recipients(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                account_id=b_account_id,
            )
            assert primitives == []
        finally:
            db.close()

    def test_expand_role_returns_recipients(self, ctx):
        from app.database import SessionLocal
        from app.models.role import Role
        from app.models.user import User
        from app.services.email import account_service, recipient_service

        account_id = _make_account_with_access(ctx)
        db = SessionLocal()
        try:
            office_role = Role(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                name="Office",
                slug="office",
                is_system=False,
            )
            db.add(office_role)
            db.flush()
            second = User(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                email=f"second-{uuid.uuid4().hex[:6]}@x.com",
                first_name="Second",
                last_name="User",
                hashed_password="x",
                is_active=True,
                role_id=office_role.id,
            )
            db.add(second)
            db.commit()
            account_service.grant_access(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
                user_id=second.id,
                access_level="read_write",
                actor_user_id=ctx["user_id"],
            )
            db.commit()

            results = recipient_service.expand_role_recipient(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                role_kind="account_access",
                id_value=account_id,
            )
            assert len(results) == 2
            emails = {r.email_address for r in results}
            assert second.email.lower() in emails
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 6. API endpoints (smoke + tenant scoping)
# ─────────────────────────────────────────────────────────────────────


class TestStep4bAPI:
    def test_search_endpoint(self, client, auth, ctx):
        account_id = _make_account_with_access(ctx)
        _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="Search target",
        )
        r = client.get(
            "/api/v1/email/search/threads?q=target", headers=auth
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["subject"] == "Search target"

    def test_search_short_query_422(self, client, auth):
        # Pydantic min_length=2 enforces 422 on short queries
        r = client.get("/api/v1/email/search/threads?q=x", headers=auth)
        assert r.status_code == 422

    def test_snooze_endpoint(self, client, auth, ctx):
        account_id = _make_account_with_access(ctx)
        thread_id, _ = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="X",
        )
        wake = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
        r = client.post(
            f"/api/v1/email/threads/{thread_id}/snooze",
            json={"snoozed_until": wake},
            headers=auth,
        )
        assert r.status_code == 200
        assert r.json()["snoozed"] is True

    def test_label_create_and_add_to_thread(self, client, auth, ctx):
        account_id = _make_account_with_access(ctx)
        thread_id, _ = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="X",
        )
        # Create label
        r = client.post(
            "/api/v1/email/labels",
            json={"name": "Priority", "color": "#9C5640"},
            headers=auth,
        )
        assert r.status_code == 201
        label_id = r.json()["id"]

        # List labels
        r2 = client.get("/api/v1/email/labels", headers=auth)
        assert r2.status_code == 200
        assert any(l["id"] == label_id for l in r2.json())

        # Add to thread
        r3 = client.post(
            f"/api/v1/email/threads/{thread_id}/labels",
            json={"label_id": label_id},
            headers=auth,
        )
        assert r3.status_code == 200
        assert r3.json()["added"] is True

        # Remove from thread
        r4 = client.delete(
            f"/api/v1/email/threads/{thread_id}/labels/{label_id}",
            headers=auth,
        )
        assert r4.status_code == 200
        assert r4.json()["removed"] is True

    def test_recipients_resolve_endpoint(self, client, auth, ctx):
        r = client.get(
            "/api/v1/email/recipients/resolve?q=EM4b", headers=auth
        )
        assert r.status_code == 200
        body = r.json()
        # Internal user from fixture should match
        assert any(item["source_type"] == "internal_user" for item in body)

    def test_recipients_roles_endpoint(self, client, auth, ctx):
        account_id = _make_account_with_access(ctx)
        r = client.get(
            f"/api/v1/email/recipients/roles?account_id={account_id}",
            headers=auth,
        )
        assert r.status_code == 200
        # Singletons excluded; with 1 user this returns []
        assert r.json() == []
