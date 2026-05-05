"""Calendar Step 2 — sync engine state machine tests.

Covers backfill state machine + circuit breaker + cursor advance +
tenant isolation + sync mutex.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app.models import Company, Role, User
from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarAccountSyncState,
)
from app.services.calendar import sync_engine
from app.services.calendar.providers.base import ProviderSyncResult


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def tenant(db_session):
    import uuid as _uuid

    co = Company(
        id=str(_uuid.uuid4()),
        name=f"Sync {_uuid.uuid4().hex[:8]}",
        slug=f"sync{_uuid.uuid4().hex[:8]}",
        vertical="manufacturing",
    )
    db_session.add(co)
    db_session.flush()
    return co


@pytest.fixture
def admin_user(db_session, tenant):
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
        email=f"sy-{_uuid.uuid4().hex[:8]}@sync.test",
        hashed_password="x",
        first_name="S",
        last_name="U",
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def local_account(db_session, tenant, admin_user):
    import uuid as _uuid

    acc = CalendarAccount(
        id=str(_uuid.uuid4()),
        tenant_id=tenant.id,
        account_type="shared",
        display_name="Local Sync Test",
        primary_email_address=f"loc-{_uuid.uuid4().hex[:8]}@s.test",
        provider_type="local",
        created_by_user_id=admin_user.id,
    )
    db_session.add(acc)
    db_session.flush()
    return acc


@pytest.fixture
def google_account(db_session, tenant, admin_user):
    import uuid as _uuid

    acc = CalendarAccount(
        id=str(_uuid.uuid4()),
        tenant_id=tenant.id,
        account_type="personal",
        display_name="Google Sync Test",
        primary_email_address=f"goog-{_uuid.uuid4().hex[:8]}@s.test",
        provider_type="google_calendar",
        provider_config={"access_token": "test_token"},
        created_by_user_id=admin_user.id,
    )
    db_session.add(acc)
    db_session.flush()
    return acc


# ─────────────────────────────────────────────────────────────────────
# Sync state lifecycle
# ─────────────────────────────────────────────────────────────────────


class TestSyncStateLifecycle:
    def test_ensure_sync_state_creates_lazily(
        self, db_session, local_account
    ):
        existing = (
            db_session.query(CalendarAccountSyncState)
            .filter(CalendarAccountSyncState.account_id == local_account.id)
            .first()
        )
        assert existing is None

        state = sync_engine.ensure_sync_state(
            db_session, account_id=local_account.id
        )
        assert state is not None
        assert state.account_id == local_account.id
        assert state.sync_status == "pending"
        assert state.consecutive_error_count == 0
        assert state.sync_in_progress is False

    def test_ensure_sync_state_idempotent(self, db_session, local_account):
        s1 = sync_engine.ensure_sync_state(
            db_session, account_id=local_account.id
        )
        s2 = sync_engine.ensure_sync_state(
            db_session, account_id=local_account.id
        )
        assert s1.id == s2.id


# ─────────────────────────────────────────────────────────────────────
# Backfill state machine
# ─────────────────────────────────────────────────────────────────────


class TestBackfillStateMachine:
    def test_local_provider_backfill_completes_with_zero_events(
        self, db_session, local_account
    ):
        # Local provider's sync_initial returns success + 0 events
        # (no provider-side inbox to backfill).
        result = sync_engine.run_initial_backfill(
            db_session, account=local_account
        )
        db_session.flush()
        db_session.refresh(local_account)

        assert result["events_synced"] == 0
        assert result["error"] is None
        assert local_account.backfill_status == "completed"
        assert local_account.backfill_progress_pct == 100
        assert local_account.backfill_completed_at is not None

        state = local_account.sync_state
        assert state is not None
        assert state.sync_status == "synced"
        assert state.consecutive_error_count == 0

    def test_in_progress_backfill_rejected(self, db_session, local_account):
        local_account.backfill_status = "in_progress"
        db_session.flush()
        with pytest.raises(sync_engine.SyncEngineError):
            sync_engine.run_initial_backfill(
                db_session, account=local_account
            )

    def test_provider_failure_marks_error_status(
        self, db_session, google_account
    ):
        # Mock provider.sync_initial to return failure.
        from app.services.calendar.providers.google_calendar import (
            GoogleCalendarProvider,
        )

        with patch.object(
            GoogleCalendarProvider,
            "sync_initial",
            return_value=ProviderSyncResult(
                success=False, error_message="API quota exceeded"
            ),
        ):
            result = sync_engine.run_initial_backfill(
                db_session, account=google_account
            )

        assert result["error"] is not None
        db_session.refresh(google_account)
        assert google_account.backfill_status == "error"

        state = google_account.sync_state
        assert state.sync_status == "error"
        assert state.consecutive_error_count == 1
        assert "quota" in state.sync_error_message.lower()

    def test_circuit_breaker_increments_consecutive_errors(
        self, db_session, google_account
    ):
        from app.services.calendar.providers.google_calendar import (
            GoogleCalendarProvider,
        )

        # First failure.
        with patch.object(
            GoogleCalendarProvider,
            "sync_initial",
            return_value=ProviderSyncResult(
                success=False, error_message="error 1"
            ),
        ):
            sync_engine.run_initial_backfill(
                db_session, account=google_account
            )
        google_account.backfill_status = "not_started"  # allow retry
        db_session.flush()

        # Second failure.
        with patch.object(
            GoogleCalendarProvider,
            "sync_initial",
            return_value=ProviderSyncResult(
                success=False, error_message="error 2"
            ),
        ):
            sync_engine.run_initial_backfill(
                db_session, account=google_account
            )

        state = google_account.sync_state
        assert state.consecutive_error_count == 2
        # sync_status remains "error" until next successful sync.
        assert state.sync_status == "error"


# ─────────────────────────────────────────────────────────────────────
# Cursor advance
# ─────────────────────────────────────────────────────────────────────


class TestCursorAdvance:
    def test_google_cursor_persists_sync_token(
        self, db_session, google_account
    ):
        from app.services.calendar.providers.google_calendar import (
            GoogleCalendarProvider,
        )

        with patch.object(
            GoogleCalendarProvider,
            "sync_initial",
            return_value=ProviderSyncResult(
                success=True,
                events_synced=42,
                last_sync_token="google_sync_token_xyz",
            ),
        ):
            sync_engine.run_initial_backfill(
                db_session, account=google_account
            )

        state = google_account.sync_state
        assert state.last_provider_cursor.get("sync_token") == "google_sync_token_xyz"

    def test_msgraph_cursor_persists_delta_token(
        self, db_session, tenant, admin_user
    ):
        import uuid as _uuid

        msgraph_account = CalendarAccount(
            id=str(_uuid.uuid4()),
            tenant_id=tenant.id,
            account_type="personal",
            display_name="MS Graph",
            primary_email_address=f"ms-{_uuid.uuid4().hex[:8]}@s.test",
            provider_type="msgraph",
            provider_config={"access_token": "test"},
            created_by_user_id=admin_user.id,
        )
        db_session.add(msgraph_account)
        db_session.flush()

        from app.services.calendar.providers.msgraph import (
            MicrosoftGraphCalendarProvider,
        )

        with patch.object(
            MicrosoftGraphCalendarProvider,
            "sync_initial",
            return_value=ProviderSyncResult(
                success=True,
                events_synced=10,
                last_sync_token="https://graph.microsoft.com/.../delta?token=abc",
            ),
        ):
            sync_engine.run_initial_backfill(
                db_session, account=msgraph_account
            )

        state = msgraph_account.sync_state
        assert (
            "delta?token=abc"
            in state.last_provider_cursor.get("delta_token", "")
        )


# ─────────────────────────────────────────────────────────────────────
# Sync mutex
# ─────────────────────────────────────────────────────────────────────


class TestSyncMutex:
    def test_sync_mutex_prevents_concurrent_sync(
        self, db_session, local_account
    ):
        # Set sync_in_progress=True manually + try to enter mutex.
        state = sync_engine.ensure_sync_state(
            db_session, account_id=local_account.id
        )
        state.sync_in_progress = True
        db_session.flush()

        with pytest.raises(sync_engine.SyncEngineError):
            with sync_engine._sync_mutex(db_session, local_account.id):
                pass


# ─────────────────────────────────────────────────────────────────────
# Tenant isolation
# ─────────────────────────────────────────────────────────────────────


class TestTenantIsolation:
    def test_sync_state_per_account_unique(
        self, db_session, tenant, admin_user
    ):
        import uuid as _uuid

        a1 = CalendarAccount(
            id=str(_uuid.uuid4()),
            tenant_id=tenant.id,
            account_type="shared",
            display_name="A1",
            primary_email_address=f"a1-{_uuid.uuid4().hex[:8]}@s.test",
            provider_type="local",
            created_by_user_id=admin_user.id,
        )
        a2 = CalendarAccount(
            id=str(_uuid.uuid4()),
            tenant_id=tenant.id,
            account_type="shared",
            display_name="A2",
            primary_email_address=f"a2-{_uuid.uuid4().hex[:8]}@s.test",
            provider_type="local",
            created_by_user_id=admin_user.id,
        )
        db_session.add_all([a1, a2])
        db_session.flush()

        s1 = sync_engine.ensure_sync_state(db_session, account_id=a1.id)
        s2 = sync_engine.ensure_sync_state(db_session, account_id=a2.id)
        assert s1.id != s2.id
        assert s1.account_id != s2.account_id
