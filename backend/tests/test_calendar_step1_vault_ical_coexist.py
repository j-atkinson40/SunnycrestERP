"""Vault iCal feed coexistence regression — Phase W-4b Calendar Step 1.

Verifies the legacy Vault iCal feed at ``GET /api/v1/vault/calendar.ics``
continues to function after the Calendar primitive substrate ships.

Per Q5 confirmed pre-build architectural decision: the canonical
Calendar primitive (§3.26.16) coexists indefinitely with the existing
Vault iCal feed. The two surfaces serve different operator needs:

  - Vault iCal feed: token-protected one-way export from Bridgeable to
    external calendar clients (operator subscribes phone calendar to
    their feed URL); read-only from external clients' perspective.

  - Canonical Calendar primitive: bidirectional sync with provider
    accounts (Google Calendar, Microsoft 365, Bridgeable-native local);
    attendee modeling; cross-tenant joint scheduling.

This regression test exists to catch any future change that
inadvertently breaks the legacy iCal feed when Calendar primitive
work touches shared infrastructure (e.g. shared model imports, shared
auth dependencies, shared route registration).

Per CLAUDE.md coexist-with-legacy discipline + DEBT.md long-tail
adoption convention — neither surface migrates the other; both ship
forever (or until operator signal warrants a migration plan).
"""

from __future__ import annotations

import uuid

from app.database import SessionLocal
from app.main import app
from app.models import Company, User, Vault, VaultItem


def test_vault_ical_route_still_registered():
    """The /vault/calendar.ics route remains registered post-Calendar
    Step 1 ship."""
    routes = [r for r in app.routes if hasattr(r, "path")]
    paths = [r.path for r in routes]
    assert "/api/v1/vault/calendar.ics" in paths


def test_vault_ical_endpoint_serves_ical_with_valid_token(tmp_path):
    """End-to-end smoke: existing Vault iCal feed responds 200 with
    iCalendar content-type when given a valid calendar_token.

    Uses a self-contained DB fixture rather than the global staging
    fixture so this test is hermetic.
    """
    from fastapi.testclient import TestClient
    from app.core.security import hash_password
    from app.models import Role

    db = SessionLocal()
    try:
        company = Company(
            id=str(uuid.uuid4()),
            name=f"VaultCoexist {uuid.uuid4().hex[:8]}",
            slug=f"vc{uuid.uuid4().hex[:8]}",
            vertical="manufacturing",
        )
        db.add(company)
        db.flush()

        role = Role(
            id=str(uuid.uuid4()),
            company_id=company.id,
            name="Admin",
            slug="admin",
            is_system=True,
        )
        db.add(role)
        db.flush()

        token = uuid.uuid4().hex
        user = User(
            id=str(uuid.uuid4()),
            email=f"vc-{uuid.uuid4().hex[:8]}@vctest.test",
            hashed_password=hash_password("VCAdmin123!"),
            first_name="Vault Coexist",
            last_name="User",
            company_id=company.id,
            role_id=role.id,
            calendar_token=token,
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.commit()

        client = TestClient(app)
        resp = client.get(f"/api/v1/vault/calendar.ics?token={token}")
        assert resp.status_code == 200, (
            f"Vault iCal feed should respond 200, got {resp.status_code} — "
            f"this indicates Calendar Step 1 broke legacy coexistence."
        )
        # iCal content-type per RFC 5545.
        ctype = resp.headers.get("content-type", "")
        assert "text/calendar" in ctype.lower() or "text/plain" in ctype.lower(), (
            f"Expected iCal content-type, got {ctype!r}"
        )
        body = resp.text
        assert "BEGIN:VCALENDAR" in body
        assert "END:VCALENDAR" in body

        # Cleanup.
        db.delete(user)
        db.delete(role)
        db.delete(company)
        db.commit()
    finally:
        db.close()


def test_vault_ical_rejects_invalid_token():
    """Invalid calendar_token still rejected post-Calendar Step 1."""
    from fastapi.testclient import TestClient

    client = TestClient(app)
    resp = client.get("/api/v1/vault/calendar.ics?token=does-not-exist")
    assert resp.status_code == 401


def test_calendar_primitive_routes_distinct_from_vault_routes():
    """Calendar primitive routes live under /calendar-accounts and
    /calendar-events; they do NOT collide with the Vault iCal route at
    /vault/calendar.ics. This test pins the route-namespace boundary."""
    routes = [r for r in app.routes if hasattr(r, "path")]
    paths = [r.path for r in routes]

    # Vault route preserved.
    assert "/api/v1/vault/calendar.ics" in paths

    # Calendar primitive routes registered under their own prefixes.
    calendar_account_prefixes = [
        p for p in paths if p.startswith("/api/v1/calendar-accounts")
    ]
    calendar_event_prefixes = [
        p for p in paths if p.startswith("/api/v1/calendar-events")
    ]
    assert len(calendar_account_prefixes) > 0, (
        "Calendar account routes should be registered under "
        "/api/v1/calendar-accounts"
    )
    assert len(calendar_event_prefixes) > 0, (
        "Calendar event routes should be registered under "
        "/api/v1/calendar-events"
    )
