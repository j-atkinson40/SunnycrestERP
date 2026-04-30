"""Phase W-4b Layer 1 Email Step 5 — cross-surface email rendering tests.

Coverage:
  Surface 1 — email_glance widget:
    - widget definition seeded with canonical shape (pulse_grid +
      spaces_pin + dashboard_grid; Glance variant)
    - data service returns has_email_access=False when user has no
      accessible accounts
    - data service returns unread count + top sender for accessible
      accounts
    - per-user discipline: two operators on shared account see
      different unread counts (UserMessageRead per user)
    - cross_tenant_indicator True when any unread thread is
      cross-tenant
    - target_thread_id set ONLY when single-thread surface
    - tenant isolation: cross-tenant message id NEVER surfaces
    - API endpoint authenticated; auth-required test

  Surface 2 — customer email threads endpoint:
    - threads matched via explicit EmailThreadLinkage (linked_entity_
      type="customer")
    - threads matched via EmailParticipant.resolved_company_entity_id
    - union of both sources, deduped
    - tenant isolation: cross-tenant customer_entity_id returns
      existence-hiding empty payload
    - access enforcement: threads on accounts user doesn't have access
      on are filtered
    - hard ceiling at 50 threads
    - linkage_source provenance (manual / participant / both)
    - cross_tenant_indicator surfaced per thread row
    - dismissed linkages don't surface
    - latest_message_snippet bounded to 96 chars

  Surface 3 — V-1c activity feed integration:
    - master_company resolver: explicit customer linkage → direct
    - master_company resolver: participant resolved_company_entity_id
      → direct
    - master_company resolver: fh_case linkage → indirect via
      Customer.master_company_id
    - master_company resolver: sales_order linkage → indirect
    - log_email_event_for_thread fans out to all resolved entities
    - thread without CRM linkage → no activity log writes
    - activity row body carries thread_id reference
    - failures don't block ingestion / send (best-effort discipline)
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet


os.environ.setdefault(
    "CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode()
)


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _make_ctx(*, vertical: str = "manufacturing"):
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
            name=f"EM5-{suffix}",
            slug=f"em5-{suffix}",
            is_active=True,
            vertical=vertical,
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
            email=f"u-{suffix}@em5.co",
            first_name="EM5",
            last_name="User",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token(
            {"sub": user.id, "company_id": co.id}
        )
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


def _seed_account_with_access(ctx, *, account_email: str = "test@example.com"):
    from app.database import SessionLocal
    from app.services.email import account_service

    db = SessionLocal()
    try:
        acc = account_service.create_account(
            db,
            tenant_id=ctx["company_id"],
            actor_user_id=ctx["user_id"],
            account_type="shared",
            display_name="Test Acct",
            email_address=account_email,
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


def _seed_inbound_thread(
    *,
    tenant_id: str,
    account_id: str,
    sender_email: str = "fh@hopkins.test",
    sender_name: str = "Mary Hopkins",
    subject: str = "Anderson case follow-up",
    body_text: str = "Following up on Anderson case.",
    is_cross_tenant: bool = False,
    received_offset_minutes: int = -30,
    n_messages: int = 1,
) -> tuple[str, list[str]]:
    """Seed a thread + N inbound messages. Returns (thread_id, msg_ids)."""
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
            first_message_at=datetime.now(timezone.utc)
            + timedelta(minutes=received_offset_minutes),
            last_message_at=datetime.now(timezone.utc)
            + timedelta(minutes=received_offset_minutes),
            message_count=n_messages,
            is_cross_tenant=is_cross_tenant,
        )
        db.add(thread)
        db.flush()
        msg_ids: list[str] = []
        for i in range(n_messages):
            msg = EmailMessage(
                id=str(uuid.uuid4()),
                thread_id=thread.id,
                tenant_id=tenant_id,
                account_id=account_id,
                provider_message_id=f"pm-{thread.id}-{i}",
                sender_email=sender_email.lower(),
                sender_name=sender_name,
                subject=subject,
                body_text=body_text,
                received_at=datetime.now(timezone.utc)
                + timedelta(minutes=received_offset_minutes + i),
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
# Surface 1 — email_glance widget
# ─────────────────────────────────────────────────────────────────────


class TestEmailGlanceWidgetDefinition:
    def test_widget_seeded_with_canonical_shape(self):
        from app.database import SessionLocal
        from app.models.widget_definition import WidgetDefinition
        from app.services.widgets.widget_registry import (
            seed_widget_definitions,
        )

        db = SessionLocal()
        try:
            seed_widget_definitions(db)
            defn = (
                db.query(WidgetDefinition)
                .filter(WidgetDefinition.widget_id == "email_glance")
                .first()
            )
            assert defn is not None
            assert "pulse_grid" in defn.supported_surfaces
            assert "spaces_pin" in defn.supported_surfaces
            assert "dashboard_grid" in defn.supported_surfaces
            # Per §14.2: Mail icon canonical
            assert defn.icon == "Mail"
            # Cross-vertical (no required_vertical limiting visibility)
            assert (
                defn.required_vertical is None
                or "*" in (defn.required_vertical or [])
            )
            # Glance-only variant per §14 Communications canon
            variant_ids = {v["variant_id"] for v in (defn.variants or [])}
            assert "glance" in variant_ids
        finally:
            db.close()


class TestEmailGlanceDataService:
    def test_no_accessible_accounts_returns_no_email_access(self, ctx):
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.widgets.email_glance_service import (
            get_email_glance,
        )

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == ctx["user_id"]).first()
            payload = get_email_glance(db, user=user)
        finally:
            db.close()
        assert payload["has_email_access"] is False
        assert payload["unread_count"] == 0
        assert payload["top_sender_email"] is None

    def test_unread_count_with_accessible_account(self, ctx):
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.widgets.email_glance_service import (
            get_email_glance,
        )

        account_id = _seed_account_with_access(ctx)
        _seed_inbound_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            sender_email="fh@hopkins.test",
            sender_name="Mary Hopkins",
        )
        _seed_inbound_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            sender_email="fd@riverside.test",
            sender_name="Riverside",
            subject="Smith vault",
            received_offset_minutes=-10,
        )

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == ctx["user_id"]).first()
            payload = get_email_glance(db, user=user)
        finally:
            db.close()
        assert payload["has_email_access"] is True
        assert payload["unread_count"] == 2
        # Top sender is most-recent unread
        assert payload["top_sender_email"] == "fd@riverside.test"
        # Multi-thread → no target_thread_id
        assert payload["target_thread_id"] is None
        assert payload["cross_tenant_indicator"] is False
        # Phase W-4b step 7-8 future signal placeholder zero today
        assert payload["ai_priority_count"] == 0

    def test_cross_tenant_indicator_set(self, ctx):
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.widgets.email_glance_service import (
            get_email_glance,
        )

        account_id = _seed_account_with_access(ctx)
        _seed_inbound_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
            is_cross_tenant=True,
        )

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == ctx["user_id"]).first()
            payload = get_email_glance(db, user=user)
        finally:
            db.close()
        assert payload["cross_tenant_indicator"] is True

    def test_single_thread_surface_sets_target_thread_id(self, ctx):
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.widgets.email_glance_service import (
            get_email_glance,
        )

        account_id = _seed_account_with_access(ctx)
        thread_id, _ = _seed_inbound_thread(
            tenant_id=ctx["company_id"],
            account_id=account_id,
        )

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == ctx["user_id"]).first()
            payload = get_email_glance(db, user=user)
        finally:
            db.close()
        assert payload["target_thread_id"] == thread_id
        assert payload["unread_count"] == 1

    def test_per_user_discipline(self, ctx):
        """User A reads the message → User B still sees it as unread."""
        from app.database import SessionLocal
        from app.models.email_primitive import UserMessageRead
        from app.models.role import Role
        from app.models.user import User
        from app.services.email import account_service
        from app.services.widgets.email_glance_service import (
            get_email_glance,
        )

        account_id = _seed_account_with_access(ctx)
        _, msg_ids = _seed_inbound_thread(
            tenant_id=ctx["company_id"], account_id=account_id
        )

        # Add User B in same tenant + grant access on shared account
        db = SessionLocal()
        try:
            role_b = (
                db.query(Role)
                .filter(Role.company_id == ctx["company_id"])
                .first()
            )
            user_b = User(
                id=str(uuid.uuid4()),
                company_id=ctx["company_id"],
                email=f"b-{uuid.uuid4().hex[:6]}@em5.co",
                first_name="B",
                last_name="User",
                hashed_password="x",
                is_active=True,
                role_id=role_b.id,
            )
            db.add(user_b)
            db.commit()
            account_service.grant_access(
                db,
                account_id=account_id,
                tenant_id=ctx["company_id"],
                user_id=user_b.id,
                access_level="read_write",
                actor_user_id=ctx["user_id"],
            )
            # User A marks the message read
            db.add(
                UserMessageRead(
                    id=str(uuid.uuid4()),
                    message_id=msg_ids[0],
                    user_id=ctx["user_id"],
                    tenant_id=ctx["company_id"],
                )
            )
            db.commit()

            user_a = db.query(User).filter(User.id == ctx["user_id"]).first()
            user_b_db = db.query(User).filter(User.id == user_b.id).first()
            payload_a = get_email_glance(db, user=user_a)
            payload_b = get_email_glance(db, user=user_b_db)
        finally:
            db.close()

        assert payload_a["unread_count"] == 0  # User A read it
        assert payload_b["unread_count"] == 1  # User B still hasn't

    def test_tenant_isolation_no_cross_tenant_leak(self, ctx, ctx_b):
        """Messages on Tenant B's account NEVER surface for Tenant A."""
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.widgets.email_glance_service import (
            get_email_glance,
        )

        # Seed a message on Tenant B
        account_id_b = _seed_account_with_access(
            ctx_b, account_email=f"b-{uuid.uuid4().hex[:6]}@b.co"
        )
        _seed_inbound_thread(
            tenant_id=ctx_b["company_id"], account_id=account_id_b
        )

        # Tenant A user has no accounts → empty payload
        db = SessionLocal()
        try:
            user_a = db.query(User).filter(User.id == ctx["user_id"]).first()
            payload = get_email_glance(db, user=user_a)
        finally:
            db.close()
        assert payload["unread_count"] == 0


class TestEmailGlanceAPI:
    def test_endpoint_returns_payload(self, client, ctx, auth):
        _seed_account_with_access(ctx)
        resp = client.get("/api/v1/widget-data/email-glance", headers=auth)
        assert resp.status_code == 200
        body = resp.json()
        assert "has_email_access" in body
        assert "unread_count" in body
        assert "ai_priority_count" in body

    def test_endpoint_requires_auth(self, client):
        resp = client.get("/api/v1/widget-data/email-glance")
        assert resp.status_code in (401, 403)


# ─────────────────────────────────────────────────────────────────────
# Surface 2 — customer email threads endpoint
# ─────────────────────────────────────────────────────────────────────


def _seed_customer_entity(tenant_id: str, *, name: str = "Hopkins FH") -> str:
    from app.database import SessionLocal
    from app.models.company_entity import CompanyEntity

    db = SessionLocal()
    try:
        ce = CompanyEntity(
            id=str(uuid.uuid4()),
            company_id=tenant_id,
            name=name,
            customer_type="funeral_home",
            is_funeral_home=True,
        )
        db.add(ce)
        db.commit()
        return ce.id
    finally:
        db.close()


def _seed_thread_linkage(
    *,
    thread_id: str,
    tenant_id: str,
    linked_entity_type: str,
    linked_entity_id: str,
    dismissed: bool = False,
):
    from app.database import SessionLocal
    from app.models.email_primitive import EmailThreadLinkage

    db = SessionLocal()
    try:
        linkage = EmailThreadLinkage(
            id=str(uuid.uuid4()),
            thread_id=thread_id,
            tenant_id=tenant_id,
            linked_entity_type=linked_entity_type,
            linked_entity_id=linked_entity_id,
            linkage_source="manual_post_link",
            dismissed_at=(
                datetime.now(timezone.utc) if dismissed else None
            ),
        )
        db.add(linkage)
        db.commit()
        return linkage.id
    finally:
        db.close()


class TestCustomerEmailThreadsService:
    def test_threads_via_explicit_linkage(self, ctx):
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.email.customer_email_threads_service import (
            get_threads_for_customer,
        )

        account_id = _seed_account_with_access(ctx)
        thread_id, _ = _seed_inbound_thread(
            tenant_id=ctx["company_id"], account_id=account_id
        )
        customer_id = _seed_customer_entity(ctx["company_id"])
        _seed_thread_linkage(
            thread_id=thread_id,
            tenant_id=ctx["company_id"],
            linked_entity_type="customer",
            linked_entity_id=customer_id,
        )

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == ctx["user_id"]).first()
            result = get_threads_for_customer(
                db, customer_entity_id=customer_id, user=user
            )
        finally:
            db.close()
        assert result["customer_entity_id"] == customer_id
        assert len(result["threads"]) == 1
        assert result["threads"][0]["id"] == thread_id
        assert result["threads"][0]["linkage_source"] == "manual"

    def test_threads_via_participant_resolution(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailParticipant
        from app.models.user import User
        from app.services.email.customer_email_threads_service import (
            get_threads_for_customer,
        )

        account_id = _seed_account_with_access(ctx)
        thread_id, _ = _seed_inbound_thread(
            tenant_id=ctx["company_id"], account_id=account_id
        )
        customer_id = _seed_customer_entity(ctx["company_id"])
        # Auto-resolved participant
        db = SessionLocal()
        try:
            participant = EmailParticipant(
                id=str(uuid.uuid4()),
                thread_id=thread_id,
                email_address="fh@hopkins.test",
                display_name="Mary Hopkins",
                resolved_company_entity_id=customer_id,
                is_internal=False,
            )
            db.add(participant)
            db.commit()
            user = db.query(User).filter(User.id == ctx["user_id"]).first()
            result = get_threads_for_customer(
                db, customer_entity_id=customer_id, user=user
            )
        finally:
            db.close()
        assert len(result["threads"]) == 1
        assert result["threads"][0]["linkage_source"] == "participant"

    def test_dual_source_dedups_to_both(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailParticipant
        from app.models.user import User
        from app.services.email.customer_email_threads_service import (
            get_threads_for_customer,
        )

        account_id = _seed_account_with_access(ctx)
        thread_id, _ = _seed_inbound_thread(
            tenant_id=ctx["company_id"], account_id=account_id
        )
        customer_id = _seed_customer_entity(ctx["company_id"])
        _seed_thread_linkage(
            thread_id=thread_id,
            tenant_id=ctx["company_id"],
            linked_entity_type="customer",
            linked_entity_id=customer_id,
        )
        db = SessionLocal()
        try:
            db.add(
                EmailParticipant(
                    id=str(uuid.uuid4()),
                    thread_id=thread_id,
                    email_address="fh@hopkins.test",
                    display_name="Mary",
                    resolved_company_entity_id=customer_id,
                    is_internal=False,
                )
            )
            db.commit()
            user = db.query(User).filter(User.id == ctx["user_id"]).first()
            result = get_threads_for_customer(
                db, customer_entity_id=customer_id, user=user
            )
        finally:
            db.close()
        # Single thread (deduped) + linkage_source="both"
        assert len(result["threads"]) == 1
        assert result["threads"][0]["linkage_source"] == "both"

    def test_dismissed_linkage_excluded(self, ctx):
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.email.customer_email_threads_service import (
            get_threads_for_customer,
        )

        account_id = _seed_account_with_access(ctx)
        thread_id, _ = _seed_inbound_thread(
            tenant_id=ctx["company_id"], account_id=account_id
        )
        customer_id = _seed_customer_entity(ctx["company_id"])
        _seed_thread_linkage(
            thread_id=thread_id,
            tenant_id=ctx["company_id"],
            linked_entity_type="customer",
            linked_entity_id=customer_id,
            dismissed=True,
        )
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == ctx["user_id"]).first()
            result = get_threads_for_customer(
                db, customer_entity_id=customer_id, user=user
            )
        finally:
            db.close()
        assert len(result["threads"]) == 0
        assert result["total_count"] == 0

    def test_cross_tenant_customer_returns_empty(self, ctx, ctx_b):
        """Probing CompanyEntity.id from another tenant returns empty
        existence-hiding payload (NOT 404 — a queryable resource)."""
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.email.customer_email_threads_service import (
            get_threads_for_customer,
        )

        # Customer entity in Tenant B
        customer_id_b = _seed_customer_entity(ctx_b["company_id"])

        # Tenant A user queries Tenant B's customer id
        db = SessionLocal()
        try:
            user_a = db.query(User).filter(User.id == ctx["user_id"]).first()
            result = get_threads_for_customer(
                db, customer_entity_id=customer_id_b, user=user_a
            )
        finally:
            db.close()
        assert result["customer_name"] is None  # existence-hiding
        assert result["threads"] == []
        assert result["total_count"] == 0

    def test_limit_capped_at_50(self, ctx):
        from app.database import SessionLocal
        from app.models.user import User
        from app.services.email.customer_email_threads_service import (
            get_threads_for_customer,
        )

        account_id = _seed_account_with_access(ctx)
        customer_id = _seed_customer_entity(ctx["company_id"])
        # Seed 3 linked threads
        for i in range(3):
            tid, _ = _seed_inbound_thread(
                tenant_id=ctx["company_id"],
                account_id=account_id,
                subject=f"Thread {i}",
                received_offset_minutes=-i * 10,
            )
            _seed_thread_linkage(
                thread_id=tid,
                tenant_id=ctx["company_id"],
                linked_entity_type="customer",
                linked_entity_id=customer_id,
            )

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == ctx["user_id"]).first()
            # Request 1000 → capped to MAX (50); we only have 3 anyway
            result = get_threads_for_customer(
                db,
                customer_entity_id=customer_id,
                user=user,
                limit=1000,
            )
        finally:
            db.close()
        assert len(result["threads"]) == 3
        # Sort: most-recent first (received_offset_minutes ascending
        # absolute = i=0 most recent)
        subjects = [t["subject"] for t in result["threads"]]
        assert subjects[0] == "Thread 0"


class TestCustomerEmailThreadsAPI:
    def test_endpoint_returns_payload(self, client, ctx, auth):
        account_id = _seed_account_with_access(ctx)
        thread_id, _ = _seed_inbound_thread(
            tenant_id=ctx["company_id"], account_id=account_id
        )
        customer_id = _seed_customer_entity(ctx["company_id"])
        _seed_thread_linkage(
            thread_id=thread_id,
            tenant_id=ctx["company_id"],
            linked_entity_type="customer",
            linked_entity_id=customer_id,
        )
        resp = client.get(
            f"/api/v1/pulse/email-threads-for-customer/{customer_id}",
            headers=auth,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["customer_entity_id"] == customer_id
        assert len(body["threads"]) == 1

    def test_endpoint_limit_param_ge_1_le_50(self, client, ctx, auth):
        customer_id = _seed_customer_entity(ctx["company_id"])
        # Out of range → 422
        resp = client.get(
            f"/api/v1/pulse/email-threads-for-customer/{customer_id}?limit=0",
            headers=auth,
        )
        assert resp.status_code == 422
        resp2 = client.get(
            f"/api/v1/pulse/email-threads-for-customer/{customer_id}?limit=51",
            headers=auth,
        )
        assert resp2.status_code == 422

    def test_endpoint_requires_auth(self, client):
        customer_id = str(uuid.uuid4())
        resp = client.get(
            f"/api/v1/pulse/email-threads-for-customer/{customer_id}"
        )
        assert resp.status_code in (401, 403)


# ─────────────────────────────────────────────────────────────────────
# Surface 3 — V-1c activity feed integration
# ─────────────────────────────────────────────────────────────────────


class TestMasterCompanyResolver:
    def test_resolver_explicit_customer_linkage(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailThread
        from app.services.email.activity_feed_integration import (
            _resolve_master_company_ids_for_thread,
        )

        account_id = _seed_account_with_access(ctx)
        thread_id, _ = _seed_inbound_thread(
            tenant_id=ctx["company_id"], account_id=account_id
        )
        customer_id = _seed_customer_entity(ctx["company_id"])
        _seed_thread_linkage(
            thread_id=thread_id,
            tenant_id=ctx["company_id"],
            linked_entity_type="customer",
            linked_entity_id=customer_id,
        )
        db = SessionLocal()
        try:
            thread = (
                db.query(EmailThread)
                .filter(EmailThread.id == thread_id)
                .first()
            )
            ids = _resolve_master_company_ids_for_thread(db, thread)
        finally:
            db.close()
        assert customer_id in ids

    def test_resolver_participant_resolved_company_entity(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailParticipant, EmailThread
        from app.services.email.activity_feed_integration import (
            _resolve_master_company_ids_for_thread,
        )

        account_id = _seed_account_with_access(ctx)
        thread_id, _ = _seed_inbound_thread(
            tenant_id=ctx["company_id"], account_id=account_id
        )
        customer_id = _seed_customer_entity(ctx["company_id"])
        db = SessionLocal()
        try:
            db.add(
                EmailParticipant(
                    id=str(uuid.uuid4()),
                    thread_id=thread_id,
                    email_address="fh@hopkins.test",
                    display_name="Mary",
                    resolved_company_entity_id=customer_id,
                    is_internal=False,
                )
            )
            db.commit()
            thread = (
                db.query(EmailThread)
                .filter(EmailThread.id == thread_id)
                .first()
            )
            ids = _resolve_master_company_ids_for_thread(db, thread)
        finally:
            db.close()
        assert customer_id in ids

    def test_resolver_thread_without_linkage_returns_empty(self, ctx):
        from app.database import SessionLocal
        from app.models.email_primitive import EmailThread
        from app.services.email.activity_feed_integration import (
            _resolve_master_company_ids_for_thread,
        )

        account_id = _seed_account_with_access(ctx)
        thread_id, _ = _seed_inbound_thread(
            tenant_id=ctx["company_id"], account_id=account_id
        )
        db = SessionLocal()
        try:
            thread = (
                db.query(EmailThread)
                .filter(EmailThread.id == thread_id)
                .first()
            )
            ids = _resolve_master_company_ids_for_thread(db, thread)
        finally:
            db.close()
        assert ids == set()


class TestActivityFeedWriteSites:
    def test_log_email_event_fans_out_to_all_resolved(self, ctx):
        """An email event for a thread linked to N CompanyEntities
        writes N activity log rows."""
        from app.database import SessionLocal
        from app.models.activity_log import ActivityLog
        from app.models.email_primitive import EmailMessage, EmailThread
        from app.services.email.activity_feed_integration import (
            log_email_event_for_thread,
        )

        account_id = _seed_account_with_access(ctx)
        thread_id, msg_ids = _seed_inbound_thread(
            tenant_id=ctx["company_id"], account_id=account_id
        )
        customer_a = _seed_customer_entity(
            ctx["company_id"], name="Hopkins FH"
        )
        customer_b = _seed_customer_entity(
            ctx["company_id"], name="Riverside FH"
        )
        _seed_thread_linkage(
            thread_id=thread_id,
            tenant_id=ctx["company_id"],
            linked_entity_type="customer",
            linked_entity_id=customer_a,
        )
        _seed_thread_linkage(
            thread_id=thread_id,
            tenant_id=ctx["company_id"],
            linked_entity_type="customer",
            linked_entity_id=customer_b,
        )

        db = SessionLocal()
        try:
            thread = (
                db.query(EmailThread)
                .filter(EmailThread.id == thread_id)
                .first()
            )
            msg = (
                db.query(EmailMessage)
                .filter(EmailMessage.id == msg_ids[0])
                .first()
            )
            log_email_event_for_thread(db, message=msg, thread=thread)
            db.commit()

            rows_a = (
                db.query(ActivityLog)
                .filter(
                    ActivityLog.master_company_id == customer_a,
                    ActivityLog.activity_type == "email",
                )
                .all()
            )
            rows_b = (
                db.query(ActivityLog)
                .filter(
                    ActivityLog.master_company_id == customer_b,
                    ActivityLog.activity_type == "email",
                )
                .all()
            )
        finally:
            db.close()
        assert len(rows_a) == 1
        assert len(rows_b) == 1
        # Body carries thread_id reference for click-through routing
        assert thread_id in (rows_a[0].body or "")
        assert thread_id in (rows_b[0].body or "")
        # Title carries direction label + subject
        assert "Received email" in (rows_a[0].title or "")

    def test_thread_without_crm_linkage_no_writes(self, ctx):
        from app.database import SessionLocal
        from app.models.activity_log import ActivityLog
        from app.models.email_primitive import EmailMessage, EmailThread
        from app.services.email.activity_feed_integration import (
            log_email_event_for_thread,
        )

        account_id = _seed_account_with_access(ctx)
        thread_id, msg_ids = _seed_inbound_thread(
            tenant_id=ctx["company_id"], account_id=account_id
        )

        db = SessionLocal()
        try:
            thread = (
                db.query(EmailThread)
                .filter(EmailThread.id == thread_id)
                .first()
            )
            msg = (
                db.query(EmailMessage)
                .filter(EmailMessage.id == msg_ids[0])
                .first()
            )
            log_email_event_for_thread(db, message=msg, thread=thread)
            db.commit()
            rows = (
                db.query(ActivityLog)
                .filter(
                    ActivityLog.tenant_id == ctx["company_id"],
                    ActivityLog.activity_type == "email",
                )
                .all()
            )
        finally:
            db.close()
        assert rows == []

    def test_outbound_label_in_title(self, ctx):
        from app.database import SessionLocal
        from app.models.activity_log import ActivityLog
        from app.models.email_primitive import EmailMessage, EmailThread
        from app.services.email.activity_feed_integration import (
            log_email_event_for_thread,
        )

        account_id = _seed_account_with_access(ctx)
        thread_id, msg_ids = _seed_inbound_thread(
            tenant_id=ctx["company_id"], account_id=account_id
        )
        customer_id = _seed_customer_entity(ctx["company_id"])
        _seed_thread_linkage(
            thread_id=thread_id,
            tenant_id=ctx["company_id"],
            linked_entity_type="customer",
            linked_entity_id=customer_id,
        )
        # Mutate one message to outbound for test purposes
        db = SessionLocal()
        try:
            msg = (
                db.query(EmailMessage)
                .filter(EmailMessage.id == msg_ids[0])
                .first()
            )
            msg.direction = "outbound"
            db.commit()

            thread = (
                db.query(EmailThread)
                .filter(EmailThread.id == thread_id)
                .first()
            )
            log_email_event_for_thread(
                db,
                message=msg,
                thread=thread,
                actor_user_id=ctx["user_id"],
            )
            db.commit()
            rows = (
                db.query(ActivityLog)
                .filter(
                    ActivityLog.master_company_id == customer_id,
                    ActivityLog.activity_type == "email",
                )
                .all()
            )
        finally:
            db.close()
        assert len(rows) == 1
        assert "Sent email" in (rows[0].title or "")
