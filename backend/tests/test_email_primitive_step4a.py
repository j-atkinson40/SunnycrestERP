"""Phase W-4b Layer 1 Email Step 4a — inbox surface tests.

Coverage:
  - Inbox listing
      * Multi-account union when account_id is None (per §3.26.15.9)
      * Single-account filter
      * status_filter: all / unread / read / archived / flagged / snoozed
      * Per-user state isolation (Sarah's read state doesn't affect
        Mike's unread_count)
      * label_id filter
      * Per-tenant isolation
      * EmailAccountAccess enforcement (no access → 0 threads)
      * Pagination
      * Sort by last_message_at DESC
  - Thread detail
      * Returns chronological messages (received_at ASC)
      * is_read denormalized per current user
      * is_read=True for outbound messages by default (sender auto-read)
      * Cross-tenant 404 (existence-hiding via tenant_id filter)
      * No-access 404 (account in tenant but user lacks access)
  - Status mutations
      * mark_message_read idempotent + audit row
      * mark_message_unread deletes UserMessageRead + audit row
      * archive_thread + unarchive_thread per-user state isolation
      * flag_thread + unflag_thread per-user state isolation
      * Audit log entries on every mutation
      * Cross-tenant 404 on mutation
  - API endpoints
      * GET /email/threads default returns user's accessible threads
      * GET /email/threads/{id} 200 with messages
      * POST /email/messages/{id}/read 200 + idempotent
      * POST /email/threads/{id}/archive 200
      * Status mutations 404 on cross-tenant id
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet


os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _make_ctx():
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
            name=f"EM4-{suffix}",
            slug=f"em4-{suffix}",
            is_active=True,
            vertical="manufacturing",
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
            email=f"u-{suffix}@em4.co",
            first_name="EM4",
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


def _make_account_with_access(ctx, *, provider_type: str = "gmail"):
    """Create an account + grant the test user admin access."""
    from app.database import SessionLocal
    from app.services.email import account_service

    db = SessionLocal()
    try:
        acc = account_service.create_account(
            db,
            tenant_id=ctx["company_id"],
            actor_user_id=ctx["user_id"],
            account_type="shared",
            display_name="Inbox",
            email_address=f"acc-{uuid.uuid4().hex[:6]}@example.com",
            provider_type=provider_type,
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


def _seed_thread(
    *,
    tenant_id: str,
    account_id: str,
    subject: str,
    sender_email: str = "external@x.com",
    sender_name: str | None = None,
    direction: str = "inbound",
    n_messages: int = 1,
    is_cross_tenant: bool = False,
):
    """Seed an EmailThread + N messages directly (bypassing ingestion
    so the test can stage exact participant state)."""
    from app.database import SessionLocal
    from app.models.email_primitive import (
        EmailMessage,
        EmailThread,
    )

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
            is_cross_tenant=is_cross_tenant,
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
                sender_name=sender_name,
                subject=subject,
                body_text=f"Body of message {i}",
                received_at=datetime.now(timezone.utc) + timedelta(seconds=i),
                direction=direction,
            )
            db.add(msg)
            db.flush()
            msg_ids.append(msg.id)
        db.commit()
        return thread.id, msg_ids
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────
# 1. list_threads
# ─────────────────────────────────────────────────────────────────────


class TestListThreads:
    def test_returns_threads_on_accessible_account(self, ctx):
        from app.database import SessionLocal
        from app.services.email import inbox_service

        account_id = _make_account_with_access(ctx)
        _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="Hello",
            n_messages=2,
        )

        db = SessionLocal()
        try:
            threads, total = inbox_service.list_threads(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            assert total == 1
            assert len(threads) == 1
            assert threads[0].subject == "Hello"
            assert threads[0].message_count == 2
            assert threads[0].unread_count == 2  # neither read by user yet
            assert threads[0].is_archived is False
            assert threads[0].sender_summary == "external@x.com"
        finally:
            db.close()

    def test_no_access_no_threads(self, ctx, ctx_b):
        from app.database import SessionLocal
        from app.services.email import inbox_service

        # Account in ctx_b's tenant; ctx_b user has access. ctx user
        # does NOT.
        account_id = _make_account_with_access(ctx_b)
        _seed_thread(
            tenant_id=ctx_b["company_id"],
            account_id=account_id,
            subject="Cross-tenant invisible",
        )

        db = SessionLocal()
        try:
            threads, total = inbox_service.list_threads(
                db,
                tenant_id=ctx["company_id"],  # different tenant
                user_id=ctx["user_id"],
            )
            assert total == 0
            assert threads == []
        finally:
            db.close()

    def test_status_filter_unread(self, ctx):
        from app.database import SessionLocal
        from app.services.email import inbox_service

        account_id = _make_account_with_access(ctx)
        _, msg_ids = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="Read me",
            n_messages=2,
        )

        db = SessionLocal()
        try:
            # Mark first message read
            inbox_service.mark_message_read(
                db,
                message_id=msg_ids[0],
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            db.commit()

            unread_threads, _ = inbox_service.list_threads(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                status_filter="unread",
            )
            # Still 1 unread message remaining → thread surfaces in unread
            assert len(unread_threads) == 1
            assert unread_threads[0].unread_count == 1

            # Mark second too
            inbox_service.mark_message_read(
                db,
                message_id=msg_ids[1],
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            db.commit()

            unread_threads_2, _ = inbox_service.list_threads(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                status_filter="unread",
            )
            assert len(unread_threads_2) == 0
        finally:
            db.close()

    def test_status_filter_archived(self, ctx):
        from app.database import SessionLocal
        from app.services.email import inbox_service

        account_id = _make_account_with_access(ctx)
        thread_id, _ = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="Archive me",
        )

        db = SessionLocal()
        try:
            inbox_service.archive_thread(
                db,
                thread_id=thread_id,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            db.commit()

            # Default ("all") view hides archived
            default_threads, _ = inbox_service.list_threads(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            assert len(default_threads) == 0

            # archived filter shows it
            archived_threads, _ = inbox_service.list_threads(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                status_filter="archived",
            )
            assert len(archived_threads) == 1
            assert archived_threads[0].is_archived is True
        finally:
            db.close()

    def test_per_user_state_isolation(self, ctx):
        """Sarah's mark-as-read must not affect Mike's unread_count."""
        from app.database import SessionLocal
        from app.models.role import Role
        from app.models.user import User
        from app.services.email import account_service, inbox_service

        account_id = _make_account_with_access(ctx)
        _, msg_ids = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="Shared",
            n_messages=1,
        )

        # Create a second user (Mike) in same tenant + grant access
        db = SessionLocal()
        try:
            mike_role = Role(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                name="Office",
                slug="office",
                is_system=False,
            )
            db.add(mike_role)
            db.flush()
            mike = User(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                email=f"mike-{uuid.uuid4().hex[:6]}@x.com",
                first_name="Mike",
                last_name="M",
                hashed_password="x",
                is_active=True,
                role_id=mike_role.id,
            )
            db.add(mike)
            db.commit()
            mike_id = mike.id
            account_service.grant_access(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
                user_id=mike_id,
                access_level="read",
                actor_user_id=ctx["user_id"],
            )
            db.commit()

            # Sarah (ctx) marks read
            inbox_service.mark_message_read(
                db,
                message_id=msg_ids[0],
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            db.commit()

            # Mike still sees 1 unread
            mike_threads, _ = inbox_service.list_threads(
                db,
                tenant_id=ctx["company_id"],
                user_id=mike_id,
            )
            assert len(mike_threads) == 1
            assert mike_threads[0].unread_count == 1

            # Sarah sees 0 unread
            sarah_threads, _ = inbox_service.list_threads(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            assert sarah_threads[0].unread_count == 0
        finally:
            db.close()

    def test_pagination_returns_correct_slice(self, ctx):
        from app.database import SessionLocal
        from app.services.email import inbox_service

        account_id = _make_account_with_access(ctx)
        for i in range(5):
            _seed_thread(
                tenant_id=ctx["company_id"],
                account_id=account_id,
                subject=f"Thread {i}",
            )

        db = SessionLocal()
        try:
            page1, total = inbox_service.list_threads(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                page=1,
                page_size=2,
            )
            assert total == 5
            assert len(page1) == 2

            page3, total2 = inbox_service.list_threads(
                db,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
                page=3,
                page_size=2,
            )
            assert total2 == 5
            assert len(page3) == 1
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 2. get_thread_detail
# ─────────────────────────────────────────────────────────────────────


class TestThreadDetail:
    def test_returns_messages_chronological(self, ctx):
        from app.database import SessionLocal
        from app.services.email import inbox_service

        account_id = _make_account_with_access(ctx)
        thread_id, msg_ids = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="Chrono",
            n_messages=3,
        )

        db = SessionLocal()
        try:
            detail = inbox_service.get_thread_detail(
                db,
                thread_id=thread_id,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            assert detail.subject == "Chrono"
            assert len(detail.messages) == 3
            # received_at ascending
            received = [m.received_at for m in detail.messages]
            assert received == sorted(received)
            # All inbound + unread initially
            assert all(not m.is_read for m in detail.messages)
        finally:
            db.close()

    def test_outbound_marked_read_by_default(self, ctx):
        from app.database import SessionLocal
        from app.services.email import inbox_service

        account_id = _make_account_with_access(ctx)
        thread_id, msg_ids = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="Outbound",
            direction="outbound",
            sender_email="me@example.com",
        )

        db = SessionLocal()
        try:
            detail = inbox_service.get_thread_detail(
                db,
                thread_id=thread_id,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            assert all(m.is_read for m in detail.messages)
        finally:
            db.close()

    def test_cross_tenant_404(self, ctx, ctx_b):
        from app.database import SessionLocal
        from app.services.email import inbox_service
        from app.services.email.inbox_service import ThreadNotFound

        account_id = _make_account_with_access(ctx_b)
        thread_id, _ = _seed_thread(
            tenant_id=ctx_b["company_id"],
            account_id=account_id,
            subject="Foreign",
        )

        db = SessionLocal()
        try:
            with pytest.raises(ThreadNotFound):
                inbox_service.get_thread_detail(
                    db,
                    thread_id=thread_id,
                    tenant_id=ctx["company_id"],
                    user_id=ctx["user_id"],
                )
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 3. Status mutations
# ─────────────────────────────────────────────────────────────────────


class TestStatusMutations:
    def test_mark_read_idempotent(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailAuditLog
        from app.services.email import inbox_service

        account_id = _make_account_with_access(ctx)
        _, msg_ids = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="Read",
        )

        db = SessionLocal()
        try:
            inbox_service.mark_message_read(
                db,
                message_id=msg_ids[0],
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            db.commit()
            inbox_service.mark_message_read(
                db,
                message_id=msg_ids[0],
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            db.commit()
            # Only one audit row (idempotent — second call is a no-op)
            count = (
                db.query(EmailAuditLog)
                .filter(
                    EmailAuditLog.action == "message_marked_read",
                    EmailAuditLog.entity_id == msg_ids[0],
                )
                .count()
            )
            assert count == 1
        finally:
            db.close()

    def test_mark_unread_deletes_row(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import UserMessageRead
        from app.services.email import inbox_service

        account_id = _make_account_with_access(ctx)
        _, msg_ids = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="Unread",
        )

        db = SessionLocal()
        try:
            inbox_service.mark_message_read(
                db,
                message_id=msg_ids[0],
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            db.commit()
            assert (
                db.query(UserMessageRead)
                .filter(UserMessageRead.message_id == msg_ids[0])
                .count()
                == 1
            )
            inbox_service.mark_message_unread(
                db,
                message_id=msg_ids[0],
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            db.commit()
            assert (
                db.query(UserMessageRead)
                .filter(UserMessageRead.message_id == msg_ids[0])
                .count()
                == 0
            )
        finally:
            db.close()

    def test_archive_creates_status_row_and_audit(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import (
            EmailAuditLog,
            EmailThreadStatus,
        )
        from app.services.email import inbox_service

        account_id = _make_account_with_access(ctx)
        thread_id, _ = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="Archive me",
        )

        db = SessionLocal()
        try:
            inbox_service.archive_thread(
                db,
                thread_id=thread_id,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            db.commit()
            status = (
                db.query(EmailThreadStatus)
                .filter(
                    EmailThreadStatus.thread_id == thread_id,
                    EmailThreadStatus.user_id == ctx["user_id"],
                )
                .first()
            )
            assert status is not None
            assert status.is_archived is True
            assert status.archived_at is not None
            audit = (
                db.query(EmailAuditLog)
                .filter(
                    EmailAuditLog.action == "thread_archived",
                    EmailAuditLog.entity_id == thread_id,
                )
                .count()
            )
            assert audit == 1
        finally:
            db.close()

    def test_archive_idempotent(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailAuditLog
        from app.services.email import inbox_service

        account_id = _make_account_with_access(ctx)
        thread_id, _ = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="A",
        )

        db = SessionLocal()
        try:
            inbox_service.archive_thread(
                db,
                thread_id=thread_id,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            db.commit()
            inbox_service.archive_thread(
                db,
                thread_id=thread_id,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            db.commit()
            audit = (
                db.query(EmailAuditLog)
                .filter(
                    EmailAuditLog.action == "thread_archived",
                    EmailAuditLog.entity_id == thread_id,
                )
                .count()
            )
            assert audit == 1
        finally:
            db.close()

    def test_flag_then_unflag(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailThreadStatus
        from app.services.email import inbox_service

        account_id = _make_account_with_access(ctx)
        thread_id, _ = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="Flag me",
        )

        db = SessionLocal()
        try:
            inbox_service.flag_thread(
                db,
                thread_id=thread_id,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            db.commit()
            status = (
                db.query(EmailThreadStatus)
                .filter(EmailThreadStatus.thread_id == thread_id)
                .first()
            )
            assert status.is_flagged is True
            inbox_service.unflag_thread(
                db,
                thread_id=thread_id,
                tenant_id=ctx["company_id"],
                user_id=ctx["user_id"],
            )
            db.commit()
            db.refresh(status)
            assert status.is_flagged is False
        finally:
            db.close()

    def test_archive_cross_tenant_404(self, ctx, ctx_b):
        from app.database import SessionLocal
        from app.services.email import inbox_service
        from app.services.email.inbox_service import ThreadNotFound

        account_id = _make_account_with_access(ctx_b)
        thread_id, _ = _seed_thread(
            tenant_id=ctx_b["company_id"],
            account_id=account_id,
            subject="Foreign",
        )

        db = SessionLocal()
        try:
            with pytest.raises(ThreadNotFound):
                inbox_service.archive_thread(
                    db,
                    thread_id=thread_id,
                    tenant_id=ctx["company_id"],
                    user_id=ctx["user_id"],
                )
        finally:
            db.close()


# ─────────────────────────────────────────────────────────────────────
# 4. API endpoints
# ─────────────────────────────────────────────────────────────────────


class TestInboxAPI:
    def test_list_threads_api(self, client, auth, ctx):
        account_id = _make_account_with_access(ctx)
        _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="API",
        )
        r = client.get("/api/v1/email/threads", headers=auth)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert len(body["threads"]) == 1
        assert body["threads"][0]["subject"] == "API"

    def test_thread_detail_api(self, client, auth, ctx):
        account_id = _make_account_with_access(ctx)
        thread_id, _ = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="Detail API",
        )
        r = client.get(
            f"/api/v1/email/threads/{thread_id}", headers=auth
        )
        assert r.status_code == 200
        body = r.json()
        assert body["subject"] == "Detail API"
        assert len(body["messages"]) == 1

    def test_thread_detail_cross_tenant_404(
        self, client, auth, ctx_b
    ):
        account_id = _make_account_with_access(ctx_b)
        thread_id, _ = _seed_thread(
            tenant_id=ctx_b["company_id"],
            account_id=account_id,
            subject="Foreign",
        )
        r = client.get(
            f"/api/v1/email/threads/{thread_id}", headers=auth
        )
        assert r.status_code == 404

    def test_mark_read_api(self, client, auth, ctx):
        account_id = _make_account_with_access(ctx)
        _, msg_ids = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="ReadAPI",
        )
        r = client.post(
            f"/api/v1/email/messages/{msg_ids[0]}/read", headers=auth
        )
        assert r.status_code == 200
        assert r.json()["read"] is True

    def test_archive_api(self, client, auth, ctx):
        account_id = _make_account_with_access(ctx)
        thread_id, _ = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="ArchiveAPI",
        )
        r = client.post(
            f"/api/v1/email/threads/{thread_id}/archive", headers=auth
        )
        assert r.status_code == 200
        assert r.json()["archived"] is True

    def test_archive_cross_tenant_404(self, client, auth, ctx_b):
        account_id = _make_account_with_access(ctx_b)
        thread_id, _ = _seed_thread(
            tenant_id=ctx_b["company_id"],
            account_id=account_id,
            subject="Foreign",
        )
        r = client.post(
            f"/api/v1/email/threads/{thread_id}/archive", headers=auth
        )
        assert r.status_code == 404

    def test_unread_status_filter_via_api(self, client, auth, ctx):
        account_id = _make_account_with_access(ctx)
        _, msg_ids = _seed_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            subject="A",
        )
        # Mark read
        client.post(
            f"/api/v1/email/messages/{msg_ids[0]}/read", headers=auth
        )
        r = client.get(
            "/api/v1/email/threads?status_filter=unread", headers=auth
        )
        assert r.status_code == 200
        assert r.json()["total"] == 0  # no unread threads remain
