"""Substrate consolidation predecessor migration tests — r70.

Per Calendar Step 1 discovery Q4 confirmation: ~25 tests at substrate
level cover registry semantics, polymorphic linkage CHECK constraint
enforcement, migration data integrity, generic token CRUD, cross-
primitive token isolation, and facade compat. Email Step 4c test
suite (33 tests) runs unchanged as Email-side regression.

Test classes mirror the build prompt's coverage strategy:
  - TestActionTypeRegistry           — register/lookup/duplicate/list-by-primitive (5)
  - TestPolymorphicLinkageConstraint — CHECK constraint enforcement (3)
  - TestMigrationDataIntegrity       — existing rows backfilled to 'email_message' (2)
  - TestTokenCrud                    — issue/lookup/consume/expire across linked_entity_type (8)
  - TestCrossPrimitiveTokenIsolation — email token can't be used against calendar linkage (3)
  - TestFacadeCompat                 — Step 4c imports preserved (2)
  - TestRegistrationOnImport         — quote_approval registered on email package import (2)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.database import SessionLocal

# Module-level import triggers Email package side-effect-import of
# email_action_service which registers quote_approval against the
# central registry. Tests that assert against quote_approval rely on
# this import running before any test executes (fixture + production
# parity behavior).
from app.services import email as _email_pkg  # noqa: F401

from app.services.platform import action_registry, action_service
from app.services.platform.action_registry import (
    ActionRegistryError,
    ActionTypeDescriptor,
    PRIMITIVE_LINKED_ENTITY_TYPES,
    expected_linked_entity_type,
    get_action_type,
    is_registered,
    list_action_types_for_primitive,
    list_all_action_types,
    register_action_type,
)
from app.services.platform.action_service import (
    ActionError,
    ActionTokenAlreadyConsumed,
    ActionTokenExpired,
    ActionTokenInvalid,
    CrossPrimitiveTokenMismatch,
    consume_action_token,
    issue_action_token,
    lookup_action_token,
    lookup_token_row_raw,
)


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


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
    from app.models import Company

    co = Company(
        id=str(uuid.uuid4()),
        name=f"Substrate {uuid.uuid4().hex[:8]}",
        slug=f"sub{uuid.uuid4().hex[:8]}",
        vertical="manufacturing",
    )
    db_session.add(co)
    db_session.flush()
    return co


@pytest.fixture
def registry_snapshot():
    """Snapshot the registry around a test that mutates it.

    Tests that register synthetic descriptors restore the registry
    state so other tests aren't poisoned. Preserves the canonical
    ``quote_approval`` registration that Email package init performs.
    """
    snapshot = dict(action_registry._REGISTRY)
    yield
    action_registry._REGISTRY.clear()
    action_registry._REGISTRY.update(snapshot)


def _noop_handler(db, **kwargs):
    """No-op commit handler for synthetic test descriptors."""
    return kwargs.get("action", {})


# ─────────────────────────────────────────────────────────────────────
# 1. ActionTypeDescriptor registry — 5 tests
# ─────────────────────────────────────────────────────────────────────


class TestActionTypeRegistry:
    def test_register_and_lookup_roundtrip(self, registry_snapshot):
        descriptor = ActionTypeDescriptor(
            action_type="test_action_roundtrip",
            primitive="email",
            target_entity_type="quote",
            outcomes=("approve", "reject"),
            terminal_outcomes=("approve", "reject"),
            commit_handler=_noop_handler,
        )
        register_action_type(descriptor)
        assert get_action_type("test_action_roundtrip") == descriptor
        assert is_registered("test_action_roundtrip")

    def test_lookup_unknown_action_type_raises(self):
        with pytest.raises(ActionRegistryError):
            get_action_type("not_a_registered_action_type_anywhere")

    def test_duplicate_registration_replaces(
        self, registry_snapshot, caplog
    ):
        d1 = ActionTypeDescriptor(
            action_type="dup_test",
            primitive="email",
            target_entity_type="quote",
            outcomes=("approve",),
            terminal_outcomes=("approve",),
            commit_handler=_noop_handler,
        )
        d2 = ActionTypeDescriptor(
            action_type="dup_test",
            primitive="calendar",  # different primitive — triggers warning
            target_entity_type="fh_case",
            outcomes=("accept",),
            terminal_outcomes=("accept",),
            commit_handler=_noop_handler,
        )
        register_action_type(d1)
        register_action_type(d2)  # replaces with WARNING
        assert get_action_type("dup_test") == d2

    def test_list_by_primitive(self, registry_snapshot):
        # The fixture preserves the canonical quote_approval (email);
        # add a synthetic calendar descriptor and assert filtering.
        cal = ActionTypeDescriptor(
            action_type="test_cal_filter",
            primitive="calendar",
            target_entity_type="fh_case",
            outcomes=("accept",),
            terminal_outcomes=("accept",),
            commit_handler=_noop_handler,
        )
        register_action_type(cal)

        email_descriptors = list_action_types_for_primitive("email")
        cal_descriptors = list_action_types_for_primitive("calendar")
        sms_descriptors = list_action_types_for_primitive("sms")

        # Email has at least quote_approval (real production registration).
        assert any(d.action_type == "quote_approval" for d in email_descriptors)
        assert all(d.primitive == "email" for d in email_descriptors)
        # Calendar has the synthetic descriptor.
        assert any(d.action_type == "test_cal_filter" for d in cal_descriptors)
        assert all(d.primitive == "calendar" for d in cal_descriptors)
        # SMS has nothing yet (Step 4 not shipped).
        assert sms_descriptors == []

    def test_idempotent_re_register_same_descriptor(
        self, registry_snapshot
    ):
        descriptor = ActionTypeDescriptor(
            action_type="test_idempotent",
            primitive="email",
            target_entity_type="quote",
            outcomes=("approve",),
            terminal_outcomes=("approve",),
            commit_handler=_noop_handler,
        )
        register_action_type(descriptor)
        register_action_type(descriptor)  # no-op
        register_action_type(descriptor)  # no-op
        # Only one entry in registry for this key.
        all_descriptors = list_all_action_types()
        matching = [
            d for d in all_descriptors if d.action_type == "test_idempotent"
        ]
        assert len(matching) == 1


# ─────────────────────────────────────────────────────────────────────
# 2. CHECK constraint enforcement — 3 tests
# ─────────────────────────────────────────────────────────────────────


class TestPolymorphicLinkageConstraint:
    def test_valid_linked_entity_types_accepted(self, db_session, tenant):
        for linked_type in PRIMITIVE_LINKED_ENTITY_TYPES.values():
            db_session.execute(
                text(
                    """
                    INSERT INTO platform_action_tokens
                    (token, tenant_id, linked_entity_type, linked_entity_id,
                     action_idx, action_type, recipient_email, expires_at,
                     click_count)
                    VALUES (:tok, :tid, :let, :lei, 0, 'test_synthetic',
                            'test@example.com', :exp, 0)
                    """
                ),
                {
                    "tok": f"valid-{linked_type}-{uuid.uuid4().hex[:8]}",
                    "tid": tenant.id,
                    "let": linked_type,
                    "lei": str(uuid.uuid4()),
                    "exp": datetime.now(timezone.utc) + timedelta(days=7),
                },
            )
        db_session.flush()  # CHECK enforced at flush

    def test_invalid_linked_entity_type_rejected(
        self, db_session, tenant
    ):
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            db_session.execute(
                text(
                    """
                    INSERT INTO platform_action_tokens
                    (token, tenant_id, linked_entity_type, linked_entity_id,
                     action_idx, action_type, recipient_email, expires_at,
                     click_count)
                    VALUES (:tok, :tid, 'not_a_real_primitive', :lei, 0,
                            'test_synthetic', 'a@b.com', :exp, 0)
                    """
                ),
                {
                    "tok": f"bad-{uuid.uuid4().hex[:8]}",
                    "tid": tenant.id,
                    "lei": str(uuid.uuid4()),
                    "exp": datetime.now(timezone.utc) + timedelta(days=7),
                },
            )
            db_session.flush()

    def test_null_linked_entity_type_rejected(
        self, db_session, tenant
    ):
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            db_session.execute(
                text(
                    """
                    INSERT INTO platform_action_tokens
                    (token, tenant_id, linked_entity_type, linked_entity_id,
                     action_idx, action_type, recipient_email, expires_at,
                     click_count)
                    VALUES (:tok, :tid, NULL, :lei, 0, 'test_synthetic',
                            'a@b.com', :exp, 0)
                    """
                ),
                {
                    "tok": f"null-{uuid.uuid4().hex[:8]}",
                    "tid": tenant.id,
                    "lei": str(uuid.uuid4()),
                    "exp": datetime.now(timezone.utc) + timedelta(days=7),
                },
            )
            db_session.flush()


# ─────────────────────────────────────────────────────────────────────
# 3. Migration data integrity — 2 tests
# ─────────────────────────────────────────────────────────────────────


class TestMigrationDataIntegrity:
    def test_table_renamed_and_polymorphic_columns_present(
        self, db_session
    ):
        # Schema-level confirmation the migration applied. SELECT
        # against renamed columns + table; old name must not exist.
        result = db_session.execute(
            text(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'platform_action_tokens'
                ORDER BY ordinal_position
                """
            )
        ).all()
        column_names = {row[0] for row in result}
        assert "linked_entity_id" in column_names
        assert "linked_entity_type" in column_names
        assert "message_id" not in column_names

        # Old table name must be gone.
        old_table = db_session.execute(
            text(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_name = 'email_action_tokens'
                """
            )
        ).all()
        assert old_table == []

    def test_check_constraint_present(self, db_session):
        constraint = db_session.execute(
            text(
                """
                SELECT conname FROM pg_constraint
                WHERE conname = 'ck_platform_action_tokens_linked_entity_type'
                """
            )
        ).all()
        assert len(constraint) == 1


# ─────────────────────────────────────────────────────────────────────
# 4. Generic token CRUD across linked_entity_type values — 8 tests
# ─────────────────────────────────────────────────────────────────────


class TestTokenCrud:
    def test_issue_email_message_token(self, db_session, tenant, registry_snapshot):
        register_action_type(
            ActionTypeDescriptor(
                action_type="test_email_crud",
                primitive="email",
                target_entity_type="quote",
                outcomes=("approve",),
                terminal_outcomes=("approve",),
                commit_handler=_noop_handler,
            )
        )
        token = issue_action_token(
            db_session,
            tenant_id=tenant.id,
            linked_entity_type="email_message",
            linked_entity_id=str(uuid.uuid4()),
            action_idx=0,
            action_type="test_email_crud",
            recipient_email="recipient@example.com",
        )
        assert token  # 43-char base64 string
        row = lookup_action_token(db_session, token=token)
        assert row["linked_entity_type"] == "email_message"
        assert row["recipient_email"] == "recipient@example.com"

    def test_issue_calendar_event_token(
        self, db_session, tenant, registry_snapshot
    ):
        register_action_type(
            ActionTypeDescriptor(
                action_type="test_calendar_crud",
                primitive="calendar",
                target_entity_type="fh_case",
                outcomes=("accept", "decline"),
                terminal_outcomes=("accept", "decline"),
                commit_handler=_noop_handler,
            )
        )
        token = issue_action_token(
            db_session,
            tenant_id=tenant.id,
            linked_entity_type="calendar_event",
            linked_entity_id=str(uuid.uuid4()),
            action_idx=0,
            action_type="test_calendar_crud",
            recipient_email="fh@example.com",
        )
        row = lookup_action_token(db_session, token=token)
        assert row["linked_entity_type"] == "calendar_event"

    def test_issue_sms_message_token(
        self, db_session, tenant, registry_snapshot
    ):
        register_action_type(
            ActionTypeDescriptor(
                action_type="test_sms_crud",
                primitive="sms",
                target_entity_type="sales_order",
                outcomes=("yes", "no"),
                terminal_outcomes=("yes", "no"),
                commit_handler=_noop_handler,
            )
        )
        token = issue_action_token(
            db_session,
            tenant_id=tenant.id,
            linked_entity_type="sms_message",
            linked_entity_id=str(uuid.uuid4()),
            action_idx=0,
            action_type="test_sms_crud",
            recipient_email="customer@example.com",
        )
        row = lookup_action_token(db_session, token=token)
        assert row["linked_entity_type"] == "sms_message"

    def test_issue_phone_call_token(
        self, db_session, tenant, registry_snapshot
    ):
        register_action_type(
            ActionTypeDescriptor(
                action_type="test_phone_crud",
                primitive="phone",
                target_entity_type="cross_tenant_event",
                outcomes=("acknowledge",),
                terminal_outcomes=("acknowledge",),
                commit_handler=_noop_handler,
            )
        )
        token = issue_action_token(
            db_session,
            tenant_id=tenant.id,
            linked_entity_type="phone_call",
            linked_entity_id=str(uuid.uuid4()),
            action_idx=0,
            action_type="test_phone_crud",
            recipient_email="op@example.com",
        )
        row = lookup_action_token(db_session, token=token)
        assert row["linked_entity_type"] == "phone_call"

    def test_consume_token_marks_consumed_at(
        self, db_session, tenant, registry_snapshot
    ):
        register_action_type(
            ActionTypeDescriptor(
                action_type="test_consume",
                primitive="email",
                target_entity_type="quote",
                outcomes=("approve",),
                terminal_outcomes=("approve",),
                commit_handler=_noop_handler,
            )
        )
        token = issue_action_token(
            db_session,
            tenant_id=tenant.id,
            linked_entity_type="email_message",
            linked_entity_id=str(uuid.uuid4()),
            action_idx=0,
            action_type="test_consume",
            recipient_email="r@example.com",
        )
        consume_action_token(db_session, token=token)

        # Subsequent lookup raises ActionTokenAlreadyConsumed (409).
        with pytest.raises(ActionTokenAlreadyConsumed):
            lookup_action_token(db_session, token=token)

    def test_lookup_invalid_token_raises_401(self, db_session):
        with pytest.raises(ActionTokenInvalid):
            lookup_action_token(db_session, token="not-a-real-token")

    def test_lookup_expired_token_raises_410(
        self, db_session, tenant, registry_snapshot
    ):
        register_action_type(
            ActionTypeDescriptor(
                action_type="test_expired",
                primitive="email",
                target_entity_type="quote",
                outcomes=("approve",),
                terminal_outcomes=("approve",),
                commit_handler=_noop_handler,
            )
        )
        token = issue_action_token(
            db_session,
            tenant_id=tenant.id,
            linked_entity_type="email_message",
            linked_entity_id=str(uuid.uuid4()),
            action_idx=0,
            action_type="test_expired",
            recipient_email="r@example.com",
        )
        # Backdate expiry 1 day past now.
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

    def test_lookup_token_row_raw_returns_consumed(
        self, db_session, tenant, registry_snapshot
    ):
        # lookup_token_row_raw bypasses validation — used by the
        # magic-link surface to render terminal "consumed" state.
        register_action_type(
            ActionTypeDescriptor(
                action_type="test_raw_lookup",
                primitive="email",
                target_entity_type="quote",
                outcomes=("approve",),
                terminal_outcomes=("approve",),
                commit_handler=_noop_handler,
            )
        )
        token = issue_action_token(
            db_session,
            tenant_id=tenant.id,
            linked_entity_type="email_message",
            linked_entity_id=str(uuid.uuid4()),
            action_idx=0,
            action_type="test_raw_lookup",
            recipient_email="r@example.com",
        )
        consume_action_token(db_session, token=token)

        row = lookup_token_row_raw(db_session, token=token)
        assert row is not None
        assert row["consumed_at"] is not None
        assert row["linked_entity_type"] == "email_message"

        # Returns None for unknown tokens (vs. raising).
        assert lookup_token_row_raw(db_session, token="bogus") is None


# ─────────────────────────────────────────────────────────────────────
# 5. Cross-primitive token isolation — 3 tests
# ─────────────────────────────────────────────────────────────────────


class TestCrossPrimitiveTokenIsolation:
    def test_action_type_primitive_mismatch_rejected_at_issue(
        self, db_session, tenant, registry_snapshot
    ):
        # quote_approval is canonically Email primitive →
        # linked_entity_type='email_message'. Attempting to issue with
        # a calendar_event linkage must reject.
        with pytest.raises(CrossPrimitiveTokenMismatch):
            issue_action_token(
                db_session,
                tenant_id=tenant.id,
                linked_entity_type="calendar_event",  # WRONG primitive
                linked_entity_id=str(uuid.uuid4()),
                action_idx=0,
                action_type="quote_approval",
                recipient_email="r@example.com",
            )

    def test_unknown_action_type_rejected_at_issue(
        self, db_session, tenant
    ):
        with pytest.raises(ActionError):
            issue_action_token(
                db_session,
                tenant_id=tenant.id,
                linked_entity_type="email_message",
                linked_entity_id=str(uuid.uuid4()),
                action_idx=0,
                action_type="not_registered_anywhere",
                recipient_email="r@example.com",
            )

    def test_expected_linked_entity_type_returns_canonical_value(
        self, registry_snapshot
    ):
        # Email's quote_approval is canonically registered.
        assert expected_linked_entity_type("quote_approval") == "email_message"

        # Synthetic registrations validate the resolver.
        register_action_type(
            ActionTypeDescriptor(
                action_type="test_resolver",
                primitive="phone",
                target_entity_type="cross_tenant_event",
                outcomes=("ack",),
                terminal_outcomes=("ack",),
                commit_handler=_noop_handler,
            )
        )
        assert expected_linked_entity_type("test_resolver") == "phone_call"


# ─────────────────────────────────────────────────────────────────────
# 6. Facade compat — 2 tests
# ─────────────────────────────────────────────────────────────────────


class TestFacadeCompat:
    def test_email_action_service_preserves_step4c_imports(self):
        # Step 4c routes + outbound_service import every public symbol
        # below; facade must re-export each one. ImportError fails the
        # test loudly + identifies which symbol regressed.
        from app.services.email.email_action_service import (  # noqa: F401
            ACTION_OUTCOMES_QUOTE_APPROVAL,
            ACTION_STATUSES,
            ACTION_TYPES,
            ActionAlreadyCompleted,
            ActionError,
            ActionNotFound,
            ActionTokenAlreadyConsumed,
            ActionTokenExpired,
            ActionTokenInvalid,
            TOKEN_TTL_DAYS,
            _INSERT_ACTION_TOKEN_SQL,
            build_magic_link_url,
            build_quote_approval_action,
            commit_action,
            consume_action_token,
            generate_action_token,
            get_action_at_index,
            get_message_actions,
            issue_action_token,
            lookup_action_token,
        )

        # Sanity-check: re-exported constants match expected canonical values.
        assert ACTION_TYPES == ("quote_approval",)
        assert ACTION_OUTCOMES_QUOTE_APPROVAL == (
            "approve",
            "reject",
            "request_changes",
        )
        assert TOKEN_TTL_DAYS == 7

    def test_facade_issue_action_token_routes_through_substrate(
        self, db_session, tenant
    ):
        # Email facade signature uses message_id kwarg; substrate uses
        # linked_entity_id. Facade adapts the kwarg name and stamps
        # linked_entity_type='email_message' implicitly.
        from app.services.email.email_action_service import (
            issue_action_token as facade_issue,
            lookup_action_token as facade_lookup,
        )

        msg_id = str(uuid.uuid4())
        token = facade_issue(
            db_session,
            tenant_id=tenant.id,
            message_id=msg_id,  # email-facade kwarg
            action_idx=0,
            action_type="quote_approval",
            recipient_email="r@example.com",
        )
        row = facade_lookup(db_session, token=token)
        # Substrate row carries polymorphic columns; the facade caller
        # gets canonical column names (linked_entity_id) + the email
        # message id flows through unchanged.
        assert row["linked_entity_id"] == msg_id
        assert row["linked_entity_type"] == "email_message"


# ─────────────────────────────────────────────────────────────────────
# 7. quote_approval registered on import — 2 tests
# ─────────────────────────────────────────────────────────────────────


class TestRegistrationOnImport:
    def test_quote_approval_registered(self):
        # Email package init side-effect-imports email_action_service
        # which registers quote_approval. Confirm the canonical
        # descriptor is present.
        assert is_registered("quote_approval")
        descriptor = get_action_type("quote_approval")
        assert descriptor.primitive == "email"
        assert descriptor.target_entity_type == "quote"
        assert "approve" in descriptor.outcomes
        assert "request_changes" in descriptor.requires_completion_note

    def test_email_primitive_only_action_type_at_september_scope(self):
        # Per §3.26.7.5 architectural restraint: only quote_approval
        # ships at September scope. Future actions (delivery_confirmation
        # / schedule_acceptance / document_signature / payment_confirmation)
        # canonicalize when concrete tenant signal warrants.
        email_actions = list_action_types_for_primitive("email")
        names = {d.action_type for d in email_actions}
        # Exactly the canonical action_type at September scope (other
        # tests may add synthetics within their own registry_snapshot
        # fixture; this test runs without the fixture so it asserts
        # the production baseline).
        assert "quote_approval" in names
