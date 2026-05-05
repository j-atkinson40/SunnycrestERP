"""Calendar Step 3 — free/busy substrate tests.

Per §3.26.16.14 + §3.26.16.6 + §3.26.16.8:
  - query_per_account_freebusy returns event-precision windows
    (consent_level="internal") with subject + location populated.
  - query_cross_tenant_freebusy enforces bilateral PTR consent;
    "free_busy_only" omits subject + location; "full_details" populates
    subject + location + attendee_count_bucket.
  - CrossTenantConsentDenied raised when no active PTR row connects
    requesting + partner tenants.
  - Cancelled + transparent events excluded per RFC 5545 TRANSP semantics.
  - Last-sync staleness disclosed per §3.26.16.8 transparency discipline.
  - Tenant isolation: cross-tenant account access raises 404.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.database import SessionLocal
from app.models import Company, Role, User
from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarAccountSyncState,
    CalendarEvent,
    CalendarEventAttendee,
)
from app.models.platform_tenant_relationship import PlatformTenantRelationship
from app.services.calendar.account_service import CalendarAccountNotFound
from app.services.calendar.freebusy_service import (
    CrossTenantConsentDenied,
    FreebusyError,
    query_cross_tenant_freebusy,
    query_per_account_freebusy,
)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _make_tenant(db_session, *, vertical="manufacturing"):
    import uuid as _uuid

    co = Company(
        id=str(_uuid.uuid4()),
        name=f"FB {_uuid.uuid4().hex[:8]}",
        slug=f"fb{_uuid.uuid4().hex[:8]}",
        vertical=vertical,
    )
    db_session.add(co)
    db_session.flush()
    return co


def _make_user(db_session, tenant):
    import uuid as _uuid

    role = Role(
        id=str(_uuid.uuid4()),
        company_id=tenant.id,
        name="Admin",
        slug="admin",
        is_system=True,
    )
    db_session.add(role)
    db_session.flush()
    user = User(
        id=str(_uuid.uuid4()),
        email=f"u-{_uuid.uuid4().hex[:8]}@fb.test",
        hashed_password="x",
        first_name="F",
        last_name="B",
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_account(db_session, tenant):
    import uuid as _uuid

    user = _make_user(db_session, tenant)
    acc = CalendarAccount(
        id=str(_uuid.uuid4()),
        tenant_id=tenant.id,
        account_type="shared",
        display_name="FB Test",
        primary_email_address=f"fb-{_uuid.uuid4().hex[:8]}@fb.test",
        provider_type="local",
        outbound_enabled=True,
        created_by_user_id=user.id,
    )
    db_session.add(acc)
    db_session.flush()
    return acc


def _make_event(db_session, account, **kwargs):
    import uuid as _uuid

    defaults = dict(
        id=str(_uuid.uuid4()),
        tenant_id=account.tenant_id,
        account_id=account.id,
        subject="FB event",
        location="Conference Room",
        start_at=datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc),
        event_timezone="UTC",
        status="confirmed",
        transparency="opaque",
    )
    defaults.update(kwargs)
    event = CalendarEvent(**defaults)
    db_session.add(event)
    db_session.flush()
    return event


def _make_attendee(db_session, event, **kwargs):
    import uuid as _uuid

    defaults = dict(
        id=str(_uuid.uuid4()),
        event_id=event.id,
        tenant_id=event.tenant_id,
        email_address=f"a-{_uuid.uuid4().hex[:8]}@e.test",
        role="required_attendee",
        response_status="needs_action",
    )
    defaults.update(kwargs)
    att = CalendarEventAttendee(**defaults)
    db_session.add(att)
    db_session.flush()
    return att


def _make_ptr(
    db_session,
    *,
    tenant,
    supplier,
    relationship_type="customer",
    status="active",
    consent="free_busy_only",
):
    import uuid as _uuid

    ptr = PlatformTenantRelationship(
        id=str(_uuid.uuid4()),
        tenant_id=tenant.id,
        supplier_tenant_id=supplier.id,
        relationship_type=relationship_type,
        status=status,
        calendar_freebusy_consent=consent,
    )
    db_session.add(ptr)
    db_session.flush()
    return ptr


# ─────────────────────────────────────────────────────────────────────
# Per-account freebusy (internal)
# ─────────────────────────────────────────────────────────────────────


class TestPerAccountFreebusy:
    def test_internal_returns_subject_and_location(self, db_session):
        tenant = _make_tenant(db_session)
        account = _make_account(db_session, tenant)
        _make_event(
            db_session,
            account,
            subject="Internal review",
            location="HQ-Boardroom",
        )
        result = query_per_account_freebusy(
            db_session,
            tenant_id=tenant.id,
            account_id=account.id,
            range_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert len(result.windows) == 1
        w = result.windows[0]
        assert w.status == "busy"
        assert w.subject == "Internal review"
        assert w.location == "HQ-Boardroom"
        assert result.consent_level == "internal"

    def test_excludes_cancelled_events(self, db_session):
        tenant = _make_tenant(db_session)
        account = _make_account(db_session, tenant)
        _make_event(
            db_session, account, subject="Live", status="confirmed"
        )
        _make_event(
            db_session, account, subject="Killed", status="cancelled"
        )
        result = query_per_account_freebusy(
            db_session,
            tenant_id=tenant.id,
            account_id=account.id,
            range_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        subjects = {w.subject for w in result.windows}
        assert "Live" in subjects
        assert "Killed" not in subjects

    def test_excludes_transparent_events(self, db_session):
        tenant = _make_tenant(db_session)
        account = _make_account(db_session, tenant)
        _make_event(
            db_session,
            account,
            subject="Opaque",
            transparency="opaque",
        )
        _make_event(
            db_session,
            account,
            subject="Transparent",
            transparency="transparent",
        )
        result = query_per_account_freebusy(
            db_session,
            tenant_id=tenant.id,
            account_id=account.id,
            range_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        subjects = {w.subject for w in result.windows}
        assert "Opaque" in subjects
        assert "Transparent" not in subjects

    def test_tentative_status_preserved(self, db_session):
        tenant = _make_tenant(db_session)
        account = _make_account(db_session, tenant)
        _make_event(db_session, account, status="tentative")
        result = query_per_account_freebusy(
            db_session,
            tenant_id=tenant.id,
            account_id=account.id,
            range_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert len(result.windows) == 1
        assert result.windows[0].status == "tentative"

    def test_cross_tenant_account_id_returns_404(self, db_session):
        # Account exists in tenant A; caller asks against tenant B.
        tenant_a = _make_tenant(db_session)
        tenant_b = _make_tenant(db_session)
        account = _make_account(db_session, tenant_a)
        with pytest.raises(CalendarAccountNotFound):
            query_per_account_freebusy(
                db_session,
                tenant_id=tenant_b.id,
                account_id=account.id,
                range_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
                range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
            )

    def test_invalid_range_raises(self, db_session):
        tenant = _make_tenant(db_session)
        account = _make_account(db_session, tenant)
        with pytest.raises(FreebusyError):
            query_per_account_freebusy(
                db_session,
                tenant_id=tenant.id,
                account_id=account.id,
                range_start=datetime(2026, 7, 1, tzinfo=timezone.utc),
                range_end=datetime(2026, 5, 1, tzinfo=timezone.utc),
            )

    def test_last_sync_at_staleness_disclosed(self, db_session):
        import uuid as _uuid

        tenant = _make_tenant(db_session)
        account = _make_account(db_session, tenant)
        _make_event(db_session, account)

        # Stale sync state — > 10 minutes old.
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        sync_state = CalendarAccountSyncState(
            id=str(_uuid.uuid4()),
            account_id=account.id,
            last_sync_at=stale_time,
        )
        db_session.add(sync_state)
        db_session.flush()
        db_session.refresh(account)

        result = query_per_account_freebusy(
            db_session,
            tenant_id=tenant.id,
            account_id=account.id,
            range_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert result.stale is True
        assert result.last_sync_at is not None


# ─────────────────────────────────────────────────────────────────────
# Cross-tenant freebusy
# ─────────────────────────────────────────────────────────────────────


class TestCrossTenantFreebusy:
    def test_no_relationship_raises_403(self, db_session):
        requesting = _make_tenant(db_session)
        partner = _make_tenant(db_session)
        with pytest.raises(CrossTenantConsentDenied):
            query_cross_tenant_freebusy(
                db_session,
                requesting_tenant_id=requesting.id,
                partner_tenant_id=partner.id,
                range_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
                range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
            )

    def test_free_busy_only_consent_omits_content(self, db_session):
        requesting = _make_tenant(db_session)
        partner = _make_tenant(db_session)
        _make_ptr(
            db_session,
            tenant=requesting,
            supplier=partner,
            consent="free_busy_only",
        )
        partner_account = _make_account(db_session, partner)
        _make_event(
            db_session,
            partner_account,
            subject="Confidential mtg",
            location="Secret Room",
        )
        result = query_cross_tenant_freebusy(
            db_session,
            requesting_tenant_id=requesting.id,
            partner_tenant_id=partner.id,
            range_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert result.consent_level == "free_busy_only"
        assert len(result.windows) == 1
        w = result.windows[0]
        assert w.status == "busy"
        # Privacy floor — never leak content.
        assert w.subject is None
        assert w.location is None
        assert w.attendee_count_bucket is None

    def test_full_details_requires_bilateral_consent(self, db_session):
        # Only forward direction consents to full_details; reverse stays
        # at default free_busy_only — bilateral floor at free_busy_only.
        requesting = _make_tenant(db_session)
        partner = _make_tenant(db_session)
        _make_ptr(
            db_session,
            tenant=requesting,
            supplier=partner,
            consent="full_details",
        )
        _make_ptr(
            db_session,
            tenant=partner,
            supplier=requesting,
            consent="free_busy_only",
        )
        partner_account = _make_account(db_session, partner)
        _make_event(db_session, partner_account, subject="Should be hidden")
        result = query_cross_tenant_freebusy(
            db_session,
            requesting_tenant_id=requesting.id,
            partner_tenant_id=partner.id,
            range_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert result.consent_level == "free_busy_only"
        assert result.windows[0].subject is None

    def test_full_details_bilateral_populates_content(self, db_session):
        requesting = _make_tenant(db_session)
        partner = _make_tenant(db_session)
        _make_ptr(
            db_session,
            tenant=requesting,
            supplier=partner,
            consent="full_details",
        )
        _make_ptr(
            db_session,
            tenant=partner,
            supplier=requesting,
            consent="full_details",
        )
        partner_account = _make_account(db_session, partner)
        ev = _make_event(
            db_session,
            partner_account,
            subject="Joint planning",
            location="Hopkins HQ",
        )
        # Add 3 attendees → "2-5" bucket per §3.26.16.6.
        for i in range(3):
            _make_attendee(
                db_session,
                ev,
                email_address=f"a{i}@partner.test",
            )
        result = query_cross_tenant_freebusy(
            db_session,
            requesting_tenant_id=requesting.id,
            partner_tenant_id=partner.id,
            range_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert result.consent_level == "full_details"
        assert len(result.windows) == 1
        w = result.windows[0]
        assert w.subject == "Joint planning"
        assert w.location == "Hopkins HQ"
        assert w.attendee_count_bucket == "2-5"

    def test_attendee_count_buckets(self, db_session):
        requesting = _make_tenant(db_session)
        partner = _make_tenant(db_session)
        _make_ptr(
            db_session,
            tenant=requesting,
            supplier=partner,
            consent="full_details",
        )
        _make_ptr(
            db_session,
            tenant=partner,
            supplier=requesting,
            consent="full_details",
        )
        partner_account = _make_account(db_session, partner)

        # Event A: 1 attendee → "1"
        ev_a = _make_event(
            db_session,
            partner_account,
            subject="Single",
            start_at=datetime(2026, 6, 1, 9, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 1, 10, tzinfo=timezone.utc),
        )
        _make_attendee(db_session, ev_a)

        # Event B: 6 attendees → "6+"
        ev_b = _make_event(
            db_session,
            partner_account,
            subject="Big mtg",
            start_at=datetime(2026, 6, 2, 9, tzinfo=timezone.utc),
            end_at=datetime(2026, 6, 2, 10, tzinfo=timezone.utc),
        )
        for i in range(6):
            _make_attendee(
                db_session,
                ev_b,
                email_address=f"b{i}@p.test",
            )

        result = query_cross_tenant_freebusy(
            db_session,
            requesting_tenant_id=requesting.id,
            partner_tenant_id=partner.id,
            range_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        buckets = {w.subject: w.attendee_count_bucket for w in result.windows}
        assert buckets == {"Single": "1", "Big mtg": "6+"}

    def test_inactive_relationship_treated_as_no_relationship(
        self, db_session
    ):
        requesting = _make_tenant(db_session)
        partner = _make_tenant(db_session)
        _make_ptr(
            db_session,
            tenant=requesting,
            supplier=partner,
            status="terminated",
            consent="full_details",
        )
        with pytest.raises(CrossTenantConsentDenied):
            query_cross_tenant_freebusy(
                db_session,
                requesting_tenant_id=requesting.id,
                partner_tenant_id=partner.id,
                range_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
                range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
            )

    def test_partner_with_no_accounts_returns_empty(self, db_session):
        requesting = _make_tenant(db_session)
        partner = _make_tenant(db_session)
        _make_ptr(
            db_session,
            tenant=requesting,
            supplier=partner,
            consent="free_busy_only",
        )
        result = query_cross_tenant_freebusy(
            db_session,
            requesting_tenant_id=requesting.id,
            partner_tenant_id=partner.id,
            range_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
            range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert result.windows == []
        assert result.consent_level == "free_busy_only"

    def test_invalid_granularity_raises(self, db_session):
        requesting = _make_tenant(db_session)
        partner = _make_tenant(db_session)
        _make_ptr(
            db_session,
            tenant=requesting,
            supplier=partner,
        )
        with pytest.raises(FreebusyError):
            query_cross_tenant_freebusy(
                db_session,
                requesting_tenant_id=requesting.id,
                partner_tenant_id=partner.id,
                range_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
                range_end=datetime(2026, 7, 1, tzinfo=timezone.utc),
                granularity="week",  # type: ignore[arg-type]
            )
