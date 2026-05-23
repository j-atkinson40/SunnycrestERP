"""(c) build arc Phase A — notify_users_with_permission helper unit tests.

Tests the new permission-gated fan-out helper that closes the
11/11 triage-queue silent-by-default dispatch gap. Substrate-only;
producer-site integration tests land in Phase B.

Test cohort (Phase A portion of audit Q4):
- test_dispatches_to_permission_cohort (happy path)
- test_respects_tenant_isolation (cross-tenant defense)
- test_skips_inactive_users (edge case)
- test_admin_role_short_circuits (admin shortcircuit consistent with substrate)
- test_suppresses_self_assignment (Lock 3 behavior)
- test_returns_empty_when_no_qualifying_users
- test_validates_category_at_entry
"""

from __future__ import annotations

import uuid

import pytest

from app.models.notification import Notification
from app.services import notification_service
from app.services.notifications.category_types import (
    UnknownNotificationCategoryError,
)


# ── Fixtures (reuse the pattern from test_vault_v1d_notifications.py) ─


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def make_tenant(db_session):
    """Create a tenant with seeded system roles. Returns dict with
    company_id + role lookups."""
    from app.models.company import Company
    from app.services.role_service import seed_default_roles

    def _factory():
        suffix = uuid.uuid4().hex[:6]
        company = Company(
            id=str(uuid.uuid4()),
            name=f"ctest-{suffix}",
            slug=f"ctest-{suffix}",
            is_active=True,
        )
        db_session.add(company)
        db_session.flush()
        seed_default_roles(db_session, company.id)
        db_session.commit()
        return {"company_id": company.id, "slug": company.slug}

    return _factory


@pytest.fixture
def make_user(db_session):
    """Create a user in a tenant with given role.slug + active flag.
    Reuses existing system role seeded by make_tenant."""
    from app.models.role import Role
    from app.models.user import User

    def _factory(*, company_id: str, role_slug: str, active: bool = True):
        suffix = uuid.uuid4().hex[:6]
        role = (
            db_session.query(Role)
            .filter(Role.company_id == company_id, Role.slug == role_slug)
            .first()
        )
        assert role is not None, (
            f"Role {role_slug!r} not seeded for company {company_id} — "
            "make_tenant must run seed_default_roles first"
        )
        user = User(
            id=str(uuid.uuid4()),
            company_id=company_id,
            email=f"u-{suffix}@cbuild.test",
            first_name="U",
            last_name=suffix,
            hashed_password="x",
            is_active=active,
            is_super_admin=(role_slug == "admin"),
            role_id=role.id,
        )
        db_session.add(user)
        db_session.commit()
        return user

    return _factory


# ── Helper tests ──


class TestDispatchesToPermissionCohort:
    """Happy path — helper dispatches to users with the permission."""

    def test_dispatches_to_users_with_permission(
        self, db_session, make_tenant, make_user
    ):
        """invoice.approve cohort: accountant should receive, driver should not."""
        t = make_tenant()
        accountant = make_user(company_id=t["company_id"], role_slug="accountant")
        driver = make_user(company_id=t["company_id"], role_slug="driver")

        created = notification_service.notify_users_with_permission(
            db_session,
            company_id=t["company_id"],
            permission_key="invoice.approve",
            title="Test",
            message="Msg",
            category="agent_anomaly_pending",
        )
        db_session.commit()

        recipients = {n.user_id for n in created}
        assert accountant.id in recipients
        assert driver.id not in recipients

    def test_returns_list_of_notifications(
        self, db_session, make_tenant, make_user
    ):
        t = make_tenant()
        make_user(company_id=t["company_id"], role_slug="accountant")

        out = notification_service.notify_users_with_permission(
            db_session,
            company_id=t["company_id"],
            permission_key="invoice.approve",
            title="T",
            message="M",
            category="agent_anomaly_pending",
        )
        assert isinstance(out, list)
        assert all(isinstance(n, Notification) for n in out)
        assert len(out) >= 1


class TestAdminShortCircuit:
    """Admin role passes any permission check via permission_service shortcircuit."""

    def test_admin_receives_arbitrary_permission(
        self, db_session, make_tenant, make_user
    ):
        t = make_tenant()
        admin = make_user(company_id=t["company_id"], role_slug="admin")

        # Use a permission_key admin's role doesn't explicitly grant —
        # admin shortcircuit at permission_service.user_has_permission
        # makes admin pass any check.
        created = notification_service.notify_users_with_permission(
            db_session,
            company_id=t["company_id"],
            permission_key="safety.trainer.approve",
            title="T",
            message="M",
            category="safety_program_pending_review",
        )
        db_session.commit()

        assert admin.id in {n.user_id for n in created}


class TestTenantIsolation:
    """Helper never crosses tenant boundary."""

    def test_does_not_dispatch_to_other_tenant_users(
        self, db_session, make_tenant, make_user
    ):
        tenant_a = make_tenant()
        tenant_b = make_tenant()
        accountant_a = make_user(company_id=tenant_a["company_id"], role_slug="accountant")
        accountant_b = make_user(company_id=tenant_b["company_id"], role_slug="accountant")

        created = notification_service.notify_users_with_permission(
            db_session,
            company_id=tenant_a["company_id"],
            permission_key="invoice.approve",
            title="T",
            message="M",
            category="agent_anomaly_pending",
        )
        db_session.commit()

        recipients = {n.user_id for n in created}
        assert accountant_a.id in recipients
        assert accountant_b.id not in recipients


class TestSkipsInactiveUsers:
    """Inactive users are excluded from dispatch."""

    def test_inactive_user_does_not_receive(
        self, db_session, make_tenant, make_user
    ):
        t = make_tenant()
        active_acct = make_user(
            company_id=t["company_id"], role_slug="accountant", active=True
        )
        inactive_acct = make_user(
            company_id=t["company_id"], role_slug="accountant", active=False
        )

        created = notification_service.notify_users_with_permission(
            db_session,
            company_id=t["company_id"],
            permission_key="invoice.approve",
            title="T",
            message="M",
            category="agent_anomaly_pending",
        )
        db_session.commit()

        recipients = {n.user_id for n in created}
        assert active_acct.id in recipients
        assert inactive_acct.id not in recipients


class TestSelfAssignmentSuppression:
    """Lock 3 — actor_user_id matching a recipient is filtered out."""

    def test_actor_user_id_suppresses_self_dispatch(
        self, db_session, make_tenant, make_user
    ):
        t = make_tenant()
        actor = make_user(company_id=t["company_id"], role_slug="accountant")
        other = make_user(company_id=t["company_id"], role_slug="accountant")

        created = notification_service.notify_users_with_permission(
            db_session,
            company_id=t["company_id"],
            permission_key="invoice.approve",
            title="T",
            message="M",
            category="agent_anomaly_pending",
            actor_user_id=actor.id,
        )
        db_session.commit()

        recipients = {n.user_id for n in created}
        assert actor.id not in recipients
        assert other.id in recipients

    def test_actor_user_id_none_dispatches_to_all(
        self, db_session, make_tenant, make_user
    ):
        """When actor_user_id is None (default), no self-suppression."""
        t = make_tenant()
        acct1 = make_user(company_id=t["company_id"], role_slug="accountant")
        acct2 = make_user(company_id=t["company_id"], role_slug="accountant")

        created = notification_service.notify_users_with_permission(
            db_session,
            company_id=t["company_id"],
            permission_key="invoice.approve",
            title="T",
            message="M",
            category="agent_anomaly_pending",
        )
        db_session.commit()

        recipients = {n.user_id for n in created}
        assert acct1.id in recipients
        assert acct2.id in recipients


class TestNoQualifyingUsers:
    """Return value when no users match permission filter."""

    def test_returns_empty_list_when_no_match(
        self, db_session, make_tenant, make_user
    ):
        t = make_tenant()
        # Only a driver; no one has invoice.approve in this tenant
        # (and we exclude admins by not seeding one — actually admins
        # exist as system role but no user bound to admin role).
        make_user(company_id=t["company_id"], role_slug="driver")

        out = notification_service.notify_users_with_permission(
            db_session,
            company_id=t["company_id"],
            permission_key="invoice.approve",
            title="T",
            message="M",
            category="agent_anomaly_pending",
        )
        assert out == []


class TestCategoryValidation:
    """Category validated at entry — malformed fails fast."""

    def test_rejects_unknown_category(self, db_session, make_tenant):
        t = make_tenant()
        with pytest.raises(UnknownNotificationCategoryError):
            notification_service.notify_users_with_permission(
                db_session,
                company_id=t["company_id"],
                permission_key="invoice.approve",
                title="T",
                message="M",
                category="ghost_category",
            )

    def test_accepts_none_category(self, db_session, make_tenant, make_user):
        """None is canonical valid (matches notify_tenant_admins)."""
        t = make_tenant()
        make_user(company_id=t["company_id"], role_slug="accountant")
        # No exception
        notification_service.notify_users_with_permission(
            db_session,
            company_id=t["company_id"],
            permission_key="invoice.approve",
            title="T",
            message="M",
            category=None,
        )
        db_session.commit()
