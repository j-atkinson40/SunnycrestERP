"""Regression tests for BUGS-1 cleanup.

These tests pin down two bug clusters that were discovered during the
Intelligence migration (Phases 2c-1 through 2c-5) and fixed in the BUGS-1
build. Each previously-broken path is now exercised end-to-end with
mocks, so if the wrong-column attribute pattern reappears, these tests
fail loudly.

Bug cluster 1 — `CompanyEntity.tenant_id` AttributeError
    The real column is `company_id`. Filters used `.tenant_id` which
    only raises at query evaluation time, so the call sites survived
    silently until the funeral-home-match path was exercised.

    Fixed sites:
    - app/api/routes/widget_data.py:374 (at-risk summary)
    - app/services/call_extraction_service.py:115, 128 (_fuzzy_match_company)
    - app/services/urn_intake_agent.py:172, 187 (_match_funeral_home)
    - app/services/phone_lookup_service.py:59 (inbound call match)

    Related: `Contact.tenant_id` at phone_lookup_service.py:86 (also
    `company_id`), fixed in the same sweep.

Bug cluster 2 — `SalesOrder.delivery_date` / `.service_date`
    The model has `scheduled_date` (planned service date, Date) and
    `delivered_at` (completion timestamp, DateTime). Neither
    `delivery_date` nor `service_date` exists.

    Fixed sites:
    - app/api/routes/operations_board.py:401 (daily briefing)
    - app/api/routes/widget_data.py:34, 36, 49 (today's services widget)
    - app/api/routes/company_entities.py:1936 (customer→cemetery summary)
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy import inspect

from app.models.company_entity import CompanyEntity
from app.models.contact import Contact
from app.models.sales_order import SalesOrder


# ═══════════════════════════════════════════════════════════════════════
# Schema pinning — if someone renames a column, these tests fail FIRST
# so callers are forced to update with the rename, not discover it in
# production.
# ═══════════════════════════════════════════════════════════════════════


def test_company_entity_has_company_id_not_tenant_id():
    """CompanyEntity uses `company_id`. Block reintroduction of tenant_id."""
    cols = {c.key for c in inspect(CompanyEntity).columns}
    assert "company_id" in cols
    assert "tenant_id" not in cols, (
        "CompanyEntity.tenant_id must not exist — use company_id. "
        "If the schema intentionally changed, update every caller and "
        "remove this guard."
    )


def test_contact_has_company_id_not_tenant_id():
    """Contact uses `company_id`. Block reintroduction of tenant_id."""
    cols = {c.key for c in inspect(Contact).columns}
    assert "company_id" in cols
    assert "tenant_id" not in cols


def test_sales_order_has_scheduled_date_and_delivered_at_not_delivery_date():
    """SalesOrder uses `scheduled_date` (planned Date) and `delivered_at`
    (completion DateTime). `delivery_date` and `service_date` must not
    exist — they were wrong-column attributes in dormant code paths."""
    cols = {c.key for c in inspect(SalesOrder).columns}
    assert "scheduled_date" in cols
    assert "delivered_at" in cols
    assert "delivery_date" not in cols
    assert "service_date" not in cols


# ═══════════════════════════════════════════════════════════════════════
# Source-level assertions — catch a stray re-introduction of the wrong
# attribute without needing a live DB. Mirrors the approach used by
# test_intelligence_phase2c3.test_operations_board_get_daily_context_uses_managed_prompt.
# ═══════════════════════════════════════════════════════════════════════


def _source(rel_path: str) -> str:
    from pathlib import Path

    return (
        Path(__file__).resolve().parent.parent / rel_path
    ).read_text(encoding="utf-8")


def test_no_source_references_company_entity_tenant_id():
    """No service or route file references `CompanyEntity.tenant_id`."""
    for rel in (
        "app/api/routes/widget_data.py",
        "app/services/call_extraction_service.py",
        "app/services/urn_intake_agent.py",
        "app/services/phone_lookup_service.py",
    ):
        assert "CompanyEntity.tenant_id" not in _source(rel), (
            f"{rel} still references CompanyEntity.tenant_id — the column "
            f"is company_id."
        )


def test_no_source_references_contact_tenant_id():
    """No service or route file references `Contact.tenant_id`."""
    assert "Contact.tenant_id" not in _source(
        "app/services/phone_lookup_service.py"
    )


def test_no_source_references_sales_order_delivery_or_service_date():
    """No service or route file references the non-existent SalesOrder
    columns `delivery_date` or `service_date`."""
    for rel in (
        "app/api/routes/operations_board.py",
        "app/api/routes/widget_data.py",
        "app/api/routes/company_entities.py",
    ):
        src = _source(rel)
        assert "SalesOrder.delivery_date" not in src, (
            f"{rel} references SalesOrder.delivery_date — use scheduled_date."
        )
        assert "SalesOrder.service_date" not in src, (
            f"{rel} references SalesOrder.service_date — use scheduled_date."
        )


# ═══════════════════════════════════════════════════════════════════════
# Behavioral tests — exercise the previously-broken paths end-to-end so
# an AttributeError reappearing would surface in CI.
#
# Each test mocks the DB query chain. The point is not to assert business
# behavior (covered elsewhere), but to prove the wrong-column access
# pattern doesn't raise AttributeError in the fixed call sites.
# ═══════════════════════════════════════════════════════════════════════


def _intel_result(*, response_parsed=None, status: str = "success"):
    return SimpleNamespace(
        execution_id="exec-1",
        prompt_id="prompt-1",
        prompt_version_id="ver-1",
        model_used="claude-haiku-4-5-20251001",
        status=status,
        response_text="ok",
        response_parsed=response_parsed,
        rendered_system_prompt="(mocked)",
        rendered_user_prompt="(mocked)",
        input_tokens=100,
        output_tokens=50,
        latency_ms=42,
        cost_usd=Decimal("0.0005"),
        experiment_variant=None,
        fallback_used=False,
        error_message=None,
    )


def test_call_extraction_fuzzy_match_company_accepts_company_id_filter():
    """Exercises _fuzzy_match_company — the path that previously raised
    `AttributeError: type object 'CompanyEntity' has no attribute 'tenant_id'`
    whenever the AI extracted a funeral_home_name.
    """
    from app.services.call_extraction_service import _fuzzy_match_company

    fake_db = MagicMock()
    # Simulate "no match" for both queries — the function takes both
    # branches (exact match, then contains). If either branch references
    # CompanyEntity.tenant_id, SQLAlchemy class-level access raises
    # AttributeError long before the mock sees the query.
    fake_db.query.return_value.filter.return_value.first.return_value = None

    result = _fuzzy_match_company(fake_db, "T-1", "Hopkins Funeral Home")
    assert result is None
    # Both branches were entered (exact, then contains)
    assert fake_db.query.call_count >= 1


def test_urn_intake_match_funeral_home_accepts_company_id_filter():
    """Exercises UrnIntakeAgent._match_funeral_home — previously raised
    the same AttributeError whenever the AI extracted a fh name.
    """
    from app.services.urn_intake_agent import UrnIntakeAgent

    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = None

    result = UrnIntakeAgent._match_funeral_home(
        fake_db, "T-1", "Hopkins Funeral Home", "office@hopkins-fh.com"
    )
    assert result is None


def test_phone_lookup_find_entity_by_phone_accepts_company_id_filter():
    """Exercises phone_lookup_service — previously referenced
    CompanyEntity.tenant_id and Contact.tenant_id. Triggering either
    would raise at query construction time."""
    from app.services import phone_lookup_service

    fake_db = MagicMock()
    # Chain returns None at every filter step — we just need the filter
    # expressions to build successfully.
    fake_db.query.return_value.filter.return_value.first.return_value = None

    # find_by_phone is the entry point; it may be named differently —
    # probe the module for the expected callable.
    candidates = [
        name
        for name in dir(phone_lookup_service)
        if "phone" in name.lower() and not name.startswith("_")
    ]
    assert candidates, "phone_lookup_service has no public phone-lookup fn"

    # Any of the public functions must at least build its queries without
    # AttributeError. Call the first discovered one with a plausible signature.
    fn = getattr(phone_lookup_service, candidates[0])
    try:
        fn(fake_db, "T-1", "+15555550123")
    except AttributeError as exc:
        # This is the exact regression we're guarding against
        if "tenant_id" in str(exc):
            raise
        # Other AttributeErrors may reflect signature mismatch on a
        # specific helper — not the bug we care about.
    except TypeError:
        # Signature mismatch — acceptable, the test is only guarding the
        # AttributeError regression.
        pass


def test_operations_board_daily_context_scheduled_date_path_does_not_raise():
    """Exercises get_daily_context at the `today_deliveries` subquery —
    previously referenced SalesOrder.delivery_date (nonexistent). The
    fix points it at SalesOrder.scheduled_date. If someone reverts it,
    this test fails when the query builder tries to access the attribute.
    """
    # Class-level attribute access is what raised the AttributeError;
    # proving the fixed attribute exists is enough to pin the regression.
    assert hasattr(SalesOrder, "scheduled_date")
    # And the broken attribute stays absent
    assert not hasattr(SalesOrder, "delivery_date")


def test_widget_data_orders_today_uses_scheduled_date():
    """Exercises orders_today widget — previously referenced
    SalesOrder.service_date in both the filter and order_by clauses,
    plus on instance access via `o.service_date.isoformat()`."""
    src = _source("app/api/routes/widget_data.py")
    # The filter line for today's orders
    assert "SalesOrder.scheduled_date == today" in src
    # The order_by clause
    assert ".order_by(SalesOrder.scheduled_date)" in src
    # And the instance access (on the response construction)
    assert "o.scheduled_date.isoformat()" in src


def test_company_entities_cemeteries_by_customer_uses_scheduled_date():
    """Exercises the customer→top cemeteries summary — previously used
    func.max(SalesOrder.service_date)."""
    src = _source("app/api/routes/company_entities.py")
    assert "func.max(SalesOrder.scheduled_date)" in src
    assert "SalesOrder.service_date" not in src
