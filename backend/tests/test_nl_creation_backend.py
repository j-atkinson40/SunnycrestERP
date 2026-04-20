"""NL Creation — backend integration tests.

Covers:
  - entity_resolver fuzzy matching against real DB (pg_trgm + r33)
  - intent.detect_create_with_nl for all 4 entity types
  - extractor orchestration (structured + resolver + AI skip path)
  - entity_registry config validity
  - API /extract, /create, /entity-types
"""

from __future__ import annotations

import uuid

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    from app.database import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _make_tenant_user(*, role_slug: str = "admin", vertical: str = "funeral_home"):
    """Create a tenant + role + admin user with full permissions.
    Returns (user_id, company_id, token, slug)."""
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
            name=f"NL-{suffix}",
            slug=f"nl-{suffix}",
            is_active=True,
            vertical=vertical,
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
            email=f"u-{suffix}@nl.co",
            first_name="NL",
            last_name="User",
            hashed_password="x",
            is_active=True,
            is_super_admin=True,  # bypass permission gates
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        token = create_access_token({"sub": user.id, "company_id": co.id})
        return (user.id, co.id, token, co.slug)
    finally:
        db.close()


@pytest.fixture
def tenant_ctx():
    user_id, company_id, token, slug = _make_tenant_user()
    return {
        "user_id": user_id,
        "company_id": company_id,
        "token": token,
        "slug": slug,
    }


@pytest.fixture
def auth_headers(tenant_ctx):
    return {
        "Authorization": f"Bearer {tenant_ctx['token']}",
        "X-Company-Slug": tenant_ctx["slug"],
    }


def _seed_hopkins_fh(db, company_id: str) -> str:
    """Seed a Hopkins Funeral Home CompanyEntity — the demo target."""
    from app.models.company_entity import CompanyEntity

    ent = CompanyEntity(
        id=str(uuid.uuid4()),
        company_id=company_id,
        name="Hopkins Funeral Home",
        is_funeral_home=True,
        is_active=True,
    )
    db.add(ent)
    db.commit()
    return ent.id


# ── Entity registry ──────────────────────────────────────────────────


class TestEntityRegistry:
    def test_four_entity_types_registered(self):
        from app.services.nl_creation import list_entity_types

        types = set(list_entity_types())
        # Phase 4 registered: case, event, contact.
        # Phase 5 added: task.
        # sales_order is DELIBERATELY excluded from the entity registry
        # per Phase 4 plan — it continues to use the workflow-scoped
        # NaturalLanguageOverlay via wf_create_order.
        assert types == {"case", "event", "contact", "task"}

    def test_case_has_required_fields(self):
        from app.services.nl_creation import get_entity_config

        c = get_entity_config("case")
        required = set(c.required_fields)
        assert "deceased_name" in required
        assert "date_of_death" in required

    def test_fh_case_alias_resolves_to_case(self):
        """The Phase 1 command-bar registry uses entity_type='fh_case'
        for the case create action. Phase 4 accepts both."""
        from app.services.nl_creation import get_entity_config

        assert get_entity_config("fh_case") is get_entity_config("case")

    def test_event_has_title_and_start_required(self):
        from app.services.nl_creation import get_entity_config

        c = get_entity_config("event")
        required = set(c.required_fields)
        assert "title" in required
        assert "event_start" in required

    def test_contact_requires_name_and_company(self):
        from app.services.nl_creation import get_entity_config

        c = get_entity_config("contact")
        required = set(c.required_fields)
        assert "name" in required
        assert "company" in required


# ── Entity resolver (real DB, pg_trgm) ───────────────────────────────


class TestEntityResolverCompanyEntity:
    def test_resolves_funeral_home_by_partial_name(
        self, db_session, tenant_ctx
    ):
        from app.services.nl_creation.entity_resolver import (
            resolve_company_entity,
        )

        _seed_hopkins_fh(db_session, tenant_ctx["company_id"])
        hit = resolve_company_entity(
            db_session,
            query="Hopkins FH",
            tenant_id=tenant_ctx["company_id"],
            filters={"is_funeral_home": True},
        )
        assert hit is not None
        assert hit.display_name == "Hopkins Funeral Home"
        assert hit.similarity > 0.3

    def test_returns_none_below_threshold(self, db_session, tenant_ctx):
        from app.services.nl_creation.entity_resolver import (
            resolve_company_entity,
        )

        _seed_hopkins_fh(db_session, tenant_ctx["company_id"])
        hit = resolve_company_entity(
            db_session,
            query="xyz123 nothing matches",
            tenant_id=tenant_ctx["company_id"],
            filters={"is_funeral_home": True},
        )
        assert hit is None

    def test_tenant_isolation(self, db_session, tenant_ctx):
        """Resolver MUST NOT leak entities from another tenant."""
        from app.services.nl_creation.entity_resolver import (
            resolve_company_entity,
        )

        _seed_hopkins_fh(db_session, tenant_ctx["company_id"])

        # Different tenant
        other_uid, other_cid, _, _ = _make_tenant_user()

        hit = resolve_company_entity(
            db_session,
            query="Hopkins",
            tenant_id=other_cid,  # wrong tenant
        )
        assert hit is None

    def test_filter_whitelist_rejects_unknown_flag(
        self, db_session, tenant_ctx
    ):
        """Safety: unknown filter keys should be silently dropped,
        not expose a SQL-injection surface."""
        from app.services.nl_creation.entity_resolver import (
            resolve_company_entity,
        )

        _seed_hopkins_fh(db_session, tenant_ctx["company_id"])
        # Should not raise; should ignore the bad key and still find
        # the seeded entity by trigram match alone.
        hit = resolve_company_entity(
            db_session,
            query="Hopkins",
            tenant_id=tenant_ctx["company_id"],
            filters={"evil_col; DROP TABLE": True},
        )
        assert hit is not None  # filter was ignored, match by name

    def test_empty_query(self, db_session, tenant_ctx):
        from app.services.nl_creation.entity_resolver import (
            resolve_company_entity,
        )

        assert resolve_company_entity(
            db_session, query="", tenant_id=tenant_ctx["company_id"]
        ) is None


# ── Intent detector ──────────────────────────────────────────────────


class TestIntentDetectCreateWithNL:
    @pytest.fixture(autouse=True)
    def _reset_registry(self):
        # The registry is a module-level singleton; ensure it's
        # seeded fresh so create.event is available.
        from app.services.command_bar import registry as reg

        reg.reset_registry()

    def test_demo_case_sentence(self):
        from app.services.command_bar.intent import detect_create_with_nl

        out = detect_create_with_nl(
            "new case John Smith DOD tonight daughter Mary wants "
            "Thursday service Hopkins FH"
        )
        assert out is not None
        entity_type, nl_content = out
        assert entity_type == "fh_case"
        assert "John Smith" in nl_content

    def test_empty_invocation_returns_none(self):
        from app.services.command_bar.intent import detect_create_with_nl

        assert detect_create_with_nl("new case") is None
        assert detect_create_with_nl("new case ") is None

    def test_event_detected(self):
        from app.services.command_bar.intent import detect_create_with_nl

        out = detect_create_with_nl("new event lunch with Jim tomorrow 2pm")
        assert out is not None
        assert out[0] == "event"

    def test_contact_detected(self):
        from app.services.command_bar.intent import detect_create_with_nl

        out = detect_create_with_nl(
            "new contact Bob Smith at Acme 555-1234"
        )
        assert out is not None
        assert out[0] == "contact"

    def test_non_create_query_returns_none(self):
        from app.services.command_bar.intent import detect_create_with_nl

        assert detect_create_with_nl("show me cases") is None
        assert detect_create_with_nl("") is None

    def test_too_short_content_returns_none(self):
        from app.services.command_bar.intent import detect_create_with_nl

        # Less than 3 chars after entity keyword
        assert detect_create_with_nl("new case a") is None


# ── Extractor (full orchestration, NO AI) ────────────────────────────
# AI extraction is gated behind the Intelligence service; we mock it
# off by asserting that when structured + resolver cover all required
# fields, the extractor succeeds without touching AI. A separate
# suite (`test_nl_creation_ai.py`, skipped-by-default) exercises AI.


class TestExtractorOrchestration:
    def test_case_sentence_resolves_funeral_home(
        self, db_session, tenant_ctx
    ):
        """When AI is unavailable, the case path should STILL pill
        Hopkins Funeral Home via the entity resolver (capitalized
        token scan → pg_trgm match). Date fields are deliberately
        AI-only for cases (multi-date sentences need semantic
        disambiguation — one structured parser can't tell DOD 'tonight'
        apart from service-date 'Thursday')."""
        from app.models.user import User
        from app.services.nl_creation import ExtractionRequest, extract

        user = db_session.query(User).filter(
            User.id == tenant_ctx["user_id"]
        ).one()
        _seed_hopkins_fh(db_session, tenant_ctx["company_id"])

        # Disable AI — the Intelligence factory raises RuntimeError
        # which `run_ai_extraction` catches and returns empty.
        import os
        prev = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = ""
        try:
            result = extract(
                db_session,
                request=ExtractionRequest(
                    entity_type="case",
                    natural_language=(
                        "new case John Smith DOD tonight daughter Mary "
                        "wants Thursday service Hopkins FH"
                    ),
                    tenant_id=tenant_ctx["company_id"],
                    user_id=tenant_ctx["user_id"],
                ),
                user=user,
            )
        finally:
            if prev is not None:
                os.environ["ANTHROPIC_API_KEY"] = prev
            else:
                os.environ.pop("ANTHROPIC_API_KEY", None)

        # Funeral home resolved from "Hopkins FH" via entity resolver
        # on capitalized-token candidates — works even when AI is off.
        fh_hit = next(
            (e for e in result.extractions if e.field_key == "funeral_home"),
            None,
        )
        assert fh_hit is not None, (
            f"Expected funeral_home pill; got fields "
            f"{[e.field_key for e in result.extractions]}"
        )
        assert fh_hit.resolved_entity_id is not None
        assert "Hopkins" in fh_hit.display_value
        assert fh_hit.source == "entity_resolver"

        # Required fields that need AI (deceased_name + date_of_death)
        # show up in missing_required when AI is disabled.
        assert "deceased_name" in result.missing_required
        assert "date_of_death" in result.missing_required

    def test_empty_input_returns_empty_result(self, db_session, tenant_ctx):
        from app.models.user import User
        from app.services.nl_creation import ExtractionRequest, extract

        user = db_session.query(User).filter(
            User.id == tenant_ctx["user_id"]
        ).one()
        result = extract(
            db_session,
            request=ExtractionRequest(
                entity_type="case",
                natural_language="",
                tenant_id=tenant_ctx["company_id"],
                user_id=tenant_ctx["user_id"],
            ),
            user=user,
        )
        assert result.extractions == []
        assert result.raw_input == ""

    def test_unknown_entity_type_raises(self, db_session, tenant_ctx):
        from app.models.user import User
        from app.services.nl_creation import (
            ExtractionRequest,
            UnknownEntityType,
            extract,
        )

        user = db_session.query(User).filter(
            User.id == tenant_ctx["user_id"]
        ).one()
        with pytest.raises(UnknownEntityType):
            extract(
                db_session,
                request=ExtractionRequest(
                    entity_type="mystery",  # type: ignore[arg-type]
                    natural_language="blah",
                    tenant_id=tenant_ctx["company_id"],
                    user_id=tenant_ctx["user_id"],
                ),
                user=user,
            )


# ── API ──────────────────────────────────────────────────────────────


class TestAPI:
    def test_list_entity_types(self, client, auth_headers):
        r = client.get("/api/v1/nl-creation/entity-types", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        types = {e["entity_type"] for e in body}
        assert {"case", "event", "contact"}.issubset(types)

    def test_extract_returns_200(self, client, auth_headers, tenant_ctx, db_session):
        _seed_hopkins_fh(db_session, tenant_ctx["company_id"])

        import os
        prev = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = ""
        try:
            r = client.post(
                "/api/v1/nl-creation/extract",
                json={
                    "entity_type": "case",
                    "natural_language": (
                        "new case John Smith DOD tonight Hopkins FH"
                    ),
                },
                headers=auth_headers,
            )
        finally:
            if prev is not None:
                os.environ["ANTHROPIC_API_KEY"] = prev
            else:
                os.environ.pop("ANTHROPIC_API_KEY", None)

        assert r.status_code == 200
        body = r.json()
        assert body["entity_type"] == "case"
        assert body["raw_input"].startswith("new case")
        # Extractions key present (list may be empty if Anthropic key unset)
        assert isinstance(body["extractions"], list)

    def test_extract_auth_required(self, client):
        r = client.post(
            "/api/v1/nl-creation/extract",
            json={"entity_type": "case", "natural_language": "test"},
        )
        assert r.status_code in (401, 403)

    def test_create_unknown_entity_type_404(self, client, auth_headers):
        r = client.post(
            "/api/v1/nl-creation/create",
            json={
                "entity_type": "mystery",
                "extractions": [],
                "raw_input": "",
            },
            headers=auth_headers,
        )
        # Pydantic literal validation kicks in first → 422
        # (Literal["case","event","contact"] rejects "mystery")
        assert r.status_code in (404, 422)

    def test_create_event_happy_path(
        self, client, auth_headers, tenant_ctx
    ):
        """Event creation exercises the simplest creator path —
        title + start are required, rest optional."""
        r = client.post(
            "/api/v1/nl-creation/create",
            json={
                "entity_type": "event",
                "raw_input": "new event lunch with Jim tomorrow 2pm",
                "extractions": [
                    {
                        "field_key": "title",
                        "field_label": "Title",
                        "extracted_value": "Lunch with Jim",
                        "display_value": "Lunch with Jim",
                        "confidence": 0.95,
                        "source": "ai_extraction",
                    },
                    {
                        "field_key": "event_start",
                        "field_label": "Event start",
                        "extracted_value": "2026-04-21T14:00:00+00:00",
                        "display_value": "Tomorrow 2:00 PM",
                        "confidence": 0.92,
                        "source": "structured_parser",
                    },
                ],
            },
            headers=auth_headers,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["entity_type"] == "event"
        assert body["navigate_url"].startswith("/vault/calendar")
        assert body["entity_id"]

    def test_create_missing_required_400(
        self, client, auth_headers
    ):
        """Creating an event with NO title should 400."""
        r = client.post(
            "/api/v1/nl-creation/create",
            json={
                "entity_type": "event",
                "raw_input": "no title",
                "extractions": [],
            },
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert "Title" in r.json()["detail"] or "required" in r.json()["detail"].lower()
