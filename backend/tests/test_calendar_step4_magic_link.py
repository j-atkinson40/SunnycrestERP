"""Calendar Step 4 — magic-link surface tests.

Per §3.26.16.17 + §3.26.11.9 + §14.10.5:
  - Token issuance via substrate (linked_entity_type='calendar_event')
  - 7-day expiry per Email r66 precedent
  - Single-action consumption per Email r66 precedent
  - recipient_email validation
  - Cross-primitive token isolation (calendar token can't be consumed
    against email_message linkage)
  - Magic-link landing GET surface returns canonical action context
  - Magic-link POST commit consumes token + propagates state
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

# Ensure Calendar package init runs.
from app.services import calendar as _cal_pkg  # noqa: F401
from app.services.calendar import calendar_action_service
from app.services.calendar.calendar_action_service import (
    ActionTokenAlreadyConsumed,
    ActionTokenExpired,
    ActionTokenInvalid,
    CrossPrimitiveTokenMismatch,
    TOKEN_TTL_DAYS,
    append_action_to_event,
    build_service_date_acceptance_action,
    consume_action_token,
    issue_action_token,
    lookup_action_token,
    lookup_token_row_raw,
)
from app.services.platform.action_service import (
    issue_action_token as platform_issue,
)

from tests._calendar_step4_fixtures import (
    db_session,  # noqa: F401
    make_account,
    make_event,
    make_tenant,
    make_user,
)


# ─────────────────────────────────────────────────────────────────────
# Token issuance against the substrate
# ─────────────────────────────────────────────────────────────────────


class TestTokenIssuance:
    def test_issue_calendar_token_uses_substrate(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account)
        # Append a pending action so the magic-link has a target.
        action = build_service_date_acceptance_action(
            fh_case_id=str(uuid.uuid4()),
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location=None,
            proposing_tenant_name="Sunnycrest",
        )
        idx = append_action_to_event(event, action)

        token = issue_action_token(
            db_session,
            tenant_id=tenant.id,
            event_id=event.id,
            action_idx=idx,
            action_type="service_date_acceptance",
            recipient_email="external@partner.test",
        )
        assert token  # 43-char URL-safe base64
        row = lookup_action_token(db_session, token=token)
        assert row["linked_entity_type"] == "calendar_event"
        assert row["linked_entity_id"] == event.id
        assert row["action_idx"] == idx
        assert row["action_type"] == "service_date_acceptance"

    def test_invalid_action_type_rejected(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account)
        with pytest.raises(Exception):  # ActionError surface
            issue_action_token(
                db_session,
                tenant_id=tenant.id,
                event_id=event.id,
                action_idx=0,
                action_type="not_a_calendar_action_type",
                recipient_email="x@y.test",
            )

    def test_token_default_ttl_seven_days(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account)
        action = build_service_date_acceptance_action(
            fh_case_id="c",
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location=None,
            proposing_tenant_name="T",
        )
        idx = append_action_to_event(event, action)

        token = issue_action_token(
            db_session,
            tenant_id=tenant.id,
            event_id=event.id,
            action_idx=idx,
            action_type="service_date_acceptance",
            recipient_email="x@y.test",
        )
        row = lookup_action_token(db_session, token=token)
        # Per Email r66 precedent: 7-day expiry.
        assert TOKEN_TTL_DAYS == 7
        delta = row["expires_at"] - datetime.now(timezone.utc)
        assert 6 <= delta.days <= 7  # tolerate clock skew


class TestTokenLifecycle:
    def test_consume_marks_consumed_at(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account)
        action = build_service_date_acceptance_action(
            fh_case_id="c",
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location=None,
            proposing_tenant_name="T",
        )
        idx = append_action_to_event(event, action)
        token = issue_action_token(
            db_session,
            tenant_id=tenant.id,
            event_id=event.id,
            action_idx=idx,
            action_type="service_date_acceptance",
            recipient_email="x@y.test",
        )
        consume_action_token(db_session, token=token)
        with pytest.raises(ActionTokenAlreadyConsumed):
            lookup_action_token(db_session, token=token)
        # Raw lookup surfaces the consumed row for terminal state rendering.
        row = lookup_token_row_raw(db_session, token=token)
        assert row is not None
        assert row["consumed_at"] is not None

    def test_expired_token_raises_410(self, db_session):
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account)
        action = build_service_date_acceptance_action(
            fh_case_id="c",
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location=None,
            proposing_tenant_name="T",
        )
        idx = append_action_to_event(event, action)
        token = issue_action_token(
            db_session,
            tenant_id=tenant.id,
            event_id=event.id,
            action_idx=idx,
            action_type="service_date_acceptance",
            recipient_email="x@y.test",
        )
        # Backdate
        db_session.execute(
            text(
                "UPDATE platform_action_tokens SET expires_at = :past "
                "WHERE token = :t"
            ),
            {
                "past": datetime.now(timezone.utc) - timedelta(days=1),
                "t": token,
            },
        )
        db_session.flush()
        with pytest.raises(ActionTokenExpired):
            lookup_action_token(db_session, token=token)

    def test_invalid_token_raises_401(self, db_session):
        with pytest.raises(ActionTokenInvalid):
            lookup_action_token(db_session, token="not-a-real-token")


# ─────────────────────────────────────────────────────────────────────
# Cross-primitive token isolation
# ─────────────────────────────────────────────────────────────────────


class TestCrossPrimitiveIsolation:
    def test_calendar_action_type_with_email_linkage_rejected(
        self, db_session
    ):
        tenant = make_tenant(db_session)
        # service_date_acceptance is canonically a Calendar primitive
        # action_type → expected linked_entity_type='calendar_event'.
        # Issuing against linked_entity_type='email_message' must reject
        # at the substrate.
        with pytest.raises(CrossPrimitiveTokenMismatch):
            platform_issue(
                db_session,
                tenant_id=tenant.id,
                linked_entity_type="email_message",  # WRONG
                linked_entity_id=str(uuid.uuid4()),
                action_idx=0,
                action_type="service_date_acceptance",
                recipient_email="x@y.test",
            )

    def test_email_action_type_with_calendar_linkage_rejected(
        self, db_session
    ):
        # Email's quote_approval should not be issuable against a
        # calendar_event linkage.
        # First ensure email package is loaded so quote_approval registers.
        from app.services import email as _email_pkg  # noqa: F401

        tenant = make_tenant(db_session)
        with pytest.raises(CrossPrimitiveTokenMismatch):
            platform_issue(
                db_session,
                tenant_id=tenant.id,
                linked_entity_type="calendar_event",  # WRONG for quote_approval
                linked_entity_id=str(uuid.uuid4()),
                action_idx=0,
                action_type="quote_approval",
                recipient_email="x@y.test",
            )

    def test_lookup_returns_correct_linked_entity_type(self, db_session):
        # Lookup must surface linked_entity_type so cross-primitive
        # routing checks (in routes) can reject mismatched routes.
        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account)
        action = build_service_date_acceptance_action(
            fh_case_id="c",
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location=None,
            proposing_tenant_name="T",
        )
        idx = append_action_to_event(event, action)
        token = issue_action_token(
            db_session,
            tenant_id=tenant.id,
            event_id=event.id,
            action_idx=idx,
            action_type="service_date_acceptance",
            recipient_email="x@y.test",
        )
        row = lookup_action_token(db_session, token=token)
        assert row["linked_entity_type"] == "calendar_event"
        # Email primitive's email_actions route would reject this token.


# ─────────────────────────────────────────────────────────────────────
# Magic-link API endpoint surface
# ─────────────────────────────────────────────────────────────────────


class TestMagicLinkAPI:
    def test_get_returns_canonical_shape(self, db_session):
        from fastapi.testclient import TestClient
        from app.main import app

        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account, subject="Joint review")

        action = build_service_date_acceptance_action(
            fh_case_id=str(uuid.uuid4()),
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location="Hopkins chapel",
            proposing_tenant_name="Sunnycrest Vault",
            deceased_name="Anderson",
        )
        idx = append_action_to_event(event, action)
        token = issue_action_token(
            db_session,
            tenant_id=tenant.id,
            event_id=event.id,
            action_idx=idx,
            action_type="service_date_acceptance",
            recipient_email="fh@hopkins.test",
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.get(f"/api/v1/calendar/actions/{token}")

        assert r.status_code == 200
        body = r.json()
        assert body["event_subject"] == "Joint review"
        assert body["action_type"] == "service_date_acceptance"
        assert body["recipient_email"] == "fh@hopkins.test"
        assert body["consumed"] is False
        assert body["action_status"] == "pending"
        assert body["organizer_name"] == "Sunnycrest Vault"

    def test_get_404_for_invalid_token(self, db_session):
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            r = client.get("/api/v1/calendar/actions/not-a-real-token")
        assert r.status_code == 401  # ActionTokenInvalid

    def test_get_400_for_email_token_against_calendar_route(
        self, db_session
    ):
        # Defensive cross-primitive guard at route level: email-primitive
        # tokens cannot be consumed via /api/v1/calendar/actions/...
        from fastapi.testclient import TestClient
        from app.main import app
        from app.services import email as _email_pkg  # noqa: F401

        tenant = make_tenant(db_session)
        # Issue an email-primitive token via substrate.
        email_token = platform_issue(
            db_session,
            tenant_id=tenant.id,
            linked_entity_type="email_message",
            linked_entity_id=str(uuid.uuid4()),
            action_idx=0,
            action_type="quote_approval",
            recipient_email="x@y.test",
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.get(f"/api/v1/calendar/actions/{email_token}")
        assert r.status_code == 400

    def test_post_commit_consumes_token(self, db_session):
        from fastapi.testclient import TestClient
        from app.main import app

        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account, status="tentative")
        action = build_service_date_acceptance_action(
            fh_case_id=str(uuid.uuid4()),
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location="loc",
            proposing_tenant_name="Sunnycrest",
        )
        idx = append_action_to_event(event, action)
        token = issue_action_token(
            db_session,
            tenant_id=tenant.id,
            event_id=event.id,
            action_idx=idx,
            action_type="service_date_acceptance",
            recipient_email="recipient@test.io",
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/calendar/actions/{token}/commit",
                json={"outcome": "accept"},
            )

        assert r.status_code == 200
        body = r.json()
        assert body["action_status"] == "accepted"

        # Re-GET surfaces consumed=True terminal state.
        with TestClient(app) as client:
            r2 = client.get(f"/api/v1/calendar/actions/{token}")
        assert r2.status_code == 200
        assert r2.json()["consumed"] is True

    def test_post_counter_propose_creates_chained_action(self, db_session):
        from fastapi.testclient import TestClient
        from app.main import app

        tenant = make_tenant(db_session)
        user = make_user(db_session, tenant)
        account = make_account(db_session, tenant, user=user)
        event = make_event(db_session, account)
        action = build_service_date_acceptance_action(
            fh_case_id=str(uuid.uuid4()),
            proposed_start_at=event.start_at,
            proposed_end_at=event.end_at,
            proposed_location="loc",
            proposing_tenant_name="Sunnycrest",
        )
        idx = append_action_to_event(event, action)
        token = issue_action_token(
            db_session,
            tenant_id=tenant.id,
            event_id=event.id,
            action_idx=idx,
            action_type="service_date_acceptance",
            recipient_email="r@p.test",
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/calendar/actions/{token}/commit",
                json={
                    "outcome": "counter_propose",
                    "completion_note": "Friday morning works better",
                    "counter_proposed_start_at": "2026-06-05T09:00:00+00:00",
                    "counter_proposed_end_at": "2026-06-05T10:00:00+00:00",
                },
            )
        assert r.status_code == 200
        body = r.json()
        assert body["action_status"] == "counter_proposed"
        assert body["counter_action_idx"] == idx + 1
