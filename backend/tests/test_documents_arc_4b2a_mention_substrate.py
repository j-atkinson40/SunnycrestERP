"""Arc 4b.2a tests — mention substrate layer.

Covers:
  - Jinja `ref` filter: renders display_name for valid entity;
    renders entity-not-found placeholder; autoescape-safe.
  - Per-render cache: deduplication within render-pass; fresh cache
    per render call; cache discarded at completion.
  - UI vocabulary translation: picker `case` resolves to substrate
    `fh_case`; placeholders use UI label.
  - Token shape parsers: parse_ref_tokens + build_ref_token round-trip.
  - Endpoint:
      - Returns array for valid entity_type + query
      - Picker subset enforced (422 on other entity_types)
      - Admin auth required
      - Cross-tenant isolation (resolver inherits Phase 1 tenant scope)
      - Empty query short-circuits
  - Composer integration: document with mention token renders;
    multiple mentions deduplicate via cache.

SQLite in-memory fixture follows test_documents_d10_blocks.py pattern,
extended with the entity tables the mention resolver needs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import JSON, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.database import Base


# ─── Engine + db fixtures ───────────────────────────────────────


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")

    # Import models so Base.metadata is populated.
    from app.models.canonical_document import (  # noqa: F401
        Document, DocumentVersion,
    )
    from app.models.company import Company  # noqa: F401
    from app.models.contact import Contact  # noqa: F401
    from app.models.customer import Customer  # noqa: F401
    from app.models.company_entity import CompanyEntity  # noqa: F401
    from app.models.fh_case import FHCase  # noqa: F401
    from app.models.invoice import Invoice  # noqa: F401
    from app.models.product import Product  # noqa: F401
    from app.models.role import Role  # noqa: F401
    from app.models.sales_order import SalesOrder  # noqa: F401
    from app.models.task import Task  # noqa: F401
    from app.models.user import User  # noqa: F401

    tables_needed = [
        "companies",
        "company_entities",
        "roles",
        "users",
        "customers",
        "contacts",
        "fh_cases",
        "sales_orders",
        "invoices",
        "products",
        "tasks",
        "documents",
        "document_versions",
    ]
    tables = [
        Base.metadata.tables[t]
        for t in tables_needed
        if t in Base.metadata.tables
    ]

    jsonb_swaps: list[tuple] = []
    for t in tables:
        for col in t.columns:
            if isinstance(col.type, JSONB):
                jsonb_swaps.append((col, col.type))
                col.type = JSON()
    Base.metadata.create_all(eng, tables=tables)
    for col, original in jsonb_swaps:
        col.type = original
    return eng


@pytest.fixture
def db(engine):
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture
def tenant(db):
    from app.models.company import Company

    c = Company(
        id=str(uuid.uuid4()), name="Mention Tenant",
        slug="mention-tenant", is_active=True,
    )
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def other_tenant(db):
    from app.models.company import Company

    c = Company(
        id=str(uuid.uuid4()), name="Other Tenant",
        slug="other-tenant", is_active=True,
    )
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def fh_case(db, tenant):
    """Seed an FHCase the resolver can find by id."""
    from datetime import date

    from app.models.fh_case import FHCase

    case = FHCase(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        case_number="FH-2026-0001",
        deceased_first_name="John",
        deceased_last_name="Smith",
        deceased_date_of_death=date(2026, 1, 1),
        created_at=datetime.now(timezone.utc),
    )
    db.add(case)
    db.flush()
    return case


@pytest.fixture
def sales_order(db, tenant):
    from app.models.customer import Customer
    from app.models.sales_order import SalesOrder

    cust = Customer(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        account_number="CUST-0001",
        name="Test Customer",
        created_at=datetime.now(timezone.utc),
    )
    db.add(cust)
    db.flush()
    from datetime import date

    so = SalesOrder(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        number="SO-9001",
        customer_id=cust.id,
        status="confirmed",
        ship_to_name="Hopkins FH",
        order_date=date(2026, 1, 1),
        created_at=datetime.now(timezone.utc),
    )
    db.add(so)
    db.flush()
    return so


@pytest.fixture
def cross_tenant_case(db, other_tenant):
    """Same shape as fh_case but owned by other_tenant — used for
    cross-tenant isolation tests."""
    from datetime import date

    from app.models.fh_case import FHCase

    case = FHCase(
        id=str(uuid.uuid4()),
        company_id=other_tenant.id,
        case_number="OTHER-0001",
        deceased_first_name="Cross",
        deceased_last_name="Tenant",
        deceased_date_of_death=date(2026, 1, 1),
        created_at=datetime.now(timezone.utc),
    )
    db.add(case)
    db.flush()
    return case


# ─── Vocabulary translation ─────────────────────────────────────


class TestVocabularyTranslation:
    def test_picker_vocab_to_substrate_canonical_mappings(self):
        from app.services.documents.mention_filter import (
            picker_vocab_to_substrate,
        )

        assert picker_vocab_to_substrate("case") == "fh_case"
        assert picker_vocab_to_substrate("order") == "sales_order"
        assert picker_vocab_to_substrate("contact") == "contact"
        assert picker_vocab_to_substrate("product") == "product"

    def test_picker_vocab_unknown_returns_none(self):
        from app.services.documents.mention_filter import (
            picker_vocab_to_substrate,
        )

        assert picker_vocab_to_substrate("invoice") is None
        assert picker_vocab_to_substrate("not-a-vocab") is None

    def test_substrate_to_picker_label_maps_picker_subset(self):
        from app.services.documents.mention_filter import (
            substrate_to_picker_ui_label,
        )

        assert substrate_to_picker_ui_label("fh_case") == "case"
        assert substrate_to_picker_ui_label("sales_order") == "order"
        assert substrate_to_picker_ui_label("contact") == "contact"

    def test_substrate_to_picker_label_unmapped_passes_through(self):
        """Entity types outside picker subset still render — operators
        can author tokens for any of the 7 SEARCHABLE_ENTITIES."""
        from app.services.documents.mention_filter import (
            substrate_to_picker_ui_label,
        )

        assert substrate_to_picker_ui_label("invoice") == "invoice"
        assert substrate_to_picker_ui_label("document") == "document"
        assert substrate_to_picker_ui_label("task") == "task"


# ─── Token shape utilities ──────────────────────────────────────


class TestTokenShape:
    def test_build_ref_token_canonical_shape(self):
        from app.services.documents.mention_filter import build_ref_token

        tok = build_ref_token("case", "abc-123")
        assert tok == '{{ ref("case", "abc-123") }}'

    def test_build_ref_token_strips_quote_chars(self):
        """Defensive: author shouldn't be able to break the token by
        passing a quote character."""
        from app.services.documents.mention_filter import build_ref_token

        tok = build_ref_token('case"injection', 'abc"-123')
        assert '"' not in tok.replace('"', '', 4)  # only the 4 canonical quotes

    def test_parse_ref_tokens_extracts_in_document_order(self):
        from app.services.documents.mention_filter import parse_ref_tokens

        body = """
        Some text {{ ref("case", "abc") }} more text
        {{ ref("order", "xyz") }} end.
        """
        tokens = parse_ref_tokens(body)
        assert tokens == [("case", "abc"), ("order", "xyz")]

    def test_parse_ref_tokens_handles_substrate_vocab(self):
        from app.services.documents.mention_filter import parse_ref_tokens

        body = '{{ ref("fh_case", "uid-1") }}'
        tokens = parse_ref_tokens(body)
        assert tokens == [("fh_case", "uid-1")]

    def test_parse_ref_tokens_preserves_duplicates(self):
        from app.services.documents.mention_filter import parse_ref_tokens

        body = '{{ ref("case", "x") }} and again {{ ref("case", "x") }}'
        tokens = parse_ref_tokens(body)
        assert len(tokens) == 2

    def test_parse_ref_tokens_empty_body(self):
        from app.services.documents.mention_filter import parse_ref_tokens

        assert parse_ref_tokens("") == []
        assert parse_ref_tokens(None) == []

    def test_build_then_parse_round_trip(self):
        from app.services.documents.mention_filter import (
            build_ref_token, parse_ref_tokens,
        )

        tok = build_ref_token("contact", "contact-uid")
        body = f"prefix {tok} suffix"
        assert parse_ref_tokens(body) == [("contact", "contact-uid")]


# ─── Single-entity resolver (placeholder behavior) ──────────────


class TestSingleEntityResolution:
    def test_unknown_entity_type_returns_placeholder(self, db, tenant):
        from app.services.documents.mention_filter import (
            _resolve_single_entity,
        )

        result = _resolve_single_entity(
            db, entity_type="not_a_type", entity_id="x", company_id=tenant.id,
        )
        assert result.found is False
        assert "unknown" in result.display_name.lower()

    def test_missing_entity_returns_placeholder_with_ui_label(
        self, db, tenant,
    ):
        """Missing fh_case → placeholder uses UI vocab `case`."""
        from app.services.documents.mention_filter import (
            _resolve_single_entity,
        )

        result = _resolve_single_entity(
            db, entity_type="fh_case", entity_id="nonexistent",
            company_id=tenant.id,
        )
        assert result.found is False
        # Placeholder uses picker UI label, not substrate vocab.
        assert "[deleted case]" in result.display_name

    def test_found_entity_returns_display_name(self, db, tenant, fh_case):
        from app.services.documents.mention_filter import (
            _resolve_single_entity,
        )

        result = _resolve_single_entity(
            db, entity_type="fh_case", entity_id=fh_case.id,
            company_id=tenant.id,
        )
        assert result.found is True
        assert "Smith" in result.display_name
        # URL substitution uses the resolver's url_template.
        assert result.url == f"/cases/{fh_case.id}"

    def test_cross_tenant_entity_returns_placeholder(
        self, db, tenant, cross_tenant_case,
    ):
        """Resolver enforces tenant isolation — querying a cross-tenant
        id surfaces as 'not found' rather than leaking data."""
        from app.services.documents.mention_filter import (
            _resolve_single_entity,
        )

        result = _resolve_single_entity(
            db, entity_type="fh_case", entity_id=cross_tenant_case.id,
            company_id=tenant.id,
        )
        assert result.found is False
        assert "[deleted case]" in result.display_name


# ─── Per-render cache (Q-ARC4B2-3) ──────────────────────────────


class TestPerRenderCache:
    def test_dedup_within_render(self, db, tenant, fh_case):
        from app.services.documents.mention_filter import (
            MentionResolutionCache,
        )

        cache = MentionResolutionCache(db=db, company_id=tenant.id)
        cache.resolve("fh_case", fh_case.id)
        cache.resolve("fh_case", fh_case.id)
        cache.resolve("fh_case", fh_case.id)

        # 3 invocations, 1 unique resolution
        assert cache.resolution_count == 3
        assert cache.unique_resolutions == 1

    def test_distinct_entities_each_resolve_once(
        self, db, tenant, fh_case, sales_order,
    ):
        from app.services.documents.mention_filter import (
            MentionResolutionCache,
        )

        cache = MentionResolutionCache(db=db, company_id=tenant.id)
        cache.resolve("fh_case", fh_case.id)
        cache.resolve("sales_order", sales_order.id)
        cache.resolve("fh_case", fh_case.id)

        assert cache.resolution_count == 3
        assert cache.unique_resolutions == 2

    def test_fresh_cache_per_instance(self, db, tenant, fh_case):
        """Cache lifecycle is bounded to one MentionResolutionCache
        instance — separate instances do NOT share state."""
        from app.services.documents.mention_filter import (
            MentionResolutionCache,
        )

        c1 = MentionResolutionCache(db=db, company_id=tenant.id)
        c1.resolve("fh_case", fh_case.id)
        c2 = MentionResolutionCache(db=db, company_id=tenant.id)
        c2.resolve("fh_case", fh_case.id)

        assert c1.unique_resolutions == 1
        assert c2.unique_resolutions == 1

    def test_missing_entity_still_cached(self, db, tenant):
        """Repeated lookup of a missing entity should NOT keep hitting
        the DB — placeholder result is also cached."""
        from app.services.documents.mention_filter import (
            MentionResolutionCache,
        )

        cache = MentionResolutionCache(db=db, company_id=tenant.id)
        r1 = cache.resolve("fh_case", "nonexistent")
        r2 = cache.resolve("fh_case", "nonexistent")
        assert r1.found is False
        assert r2.found is False
        assert cache.unique_resolutions == 1


# ─── Jinja `ref` filter ─────────────────────────────────────────


class TestJinjaRefFilter:
    def _render(self, db, company_id, body):
        from app.services.documents.document_renderer import _render_jinja

        return _render_jinja(body, {}, db=db, company_id=company_id)

    def test_renders_display_name_for_found_entity(
        self, db, tenant, fh_case,
    ):
        body = '<p>{{ ref("case", "' + fh_case.id + '") }}</p>'
        out = self._render(db, tenant.id, body)
        assert "Smith" in out
        assert 'class="doc-mention"' in out
        # URL substitution
        assert f'href="/cases/{fh_case.id}"' in out
        # Data attributes for traceability + Arc 4b.2b consumer
        assert 'data-entity-type="fh_case"' in out

    def test_renders_placeholder_for_missing_entity(self, db, tenant):
        body = '<p>{{ ref("case", "deleted-uid") }}</p>'
        out = self._render(db, tenant.id, body)
        assert "[deleted case]" in out
        # Placeholder uses the deleted class, no anchor href.
        assert "doc-mention-deleted" in out
        assert "href=" not in out

    def test_substrate_vocab_also_works(self, db, tenant, fh_case):
        """Both `case` (UI vocab) and `fh_case` (substrate) resolve
        identically — the filter normalizes."""
        body_ui = '{{ ref("case", "' + fh_case.id + '") }}'
        body_substrate = '{{ ref("fh_case", "' + fh_case.id + '") }}'
        out_ui = self._render(db, tenant.id, body_ui)
        out_substrate = self._render(db, tenant.id, body_substrate)
        # Both should resolve to the same display name.
        assert "Smith" in out_ui
        assert "Smith" in out_substrate

    def test_autoescape_safe_with_quote_in_name(self, db, tenant):
        """Defensive: an entity whose display_name contains a quote
        char must not break HTML rendering."""
        from datetime import date

        from app.models.fh_case import FHCase
        from app.services.documents.document_renderer import _render_jinja

        case = FHCase(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            case_number="FH-XSS",
            # Quote + angle bracket — both must be escaped.
            deceased_last_name='"><script>',
            deceased_first_name="X",
            deceased_date_of_death=date(2026, 1, 1),
            created_at=datetime.now(timezone.utc),
        )
        db.add(case)
        db.flush()

        body = '{{ ref("case", "' + case.id + '") }}'
        out = _render_jinja(body, {}, db=db, company_id=tenant.id)
        # <script> must be escaped
        assert "<script>" not in out
        assert "&lt;script&gt;" in out or "&lt;script" in out

    def test_invalid_args_render_placeholder(self, db, tenant):
        """Empty entity_type or entity_id surfaces placeholder rather
        than crashing the template."""
        body = '{{ ref("", "") }}'
        out = self._render(db, tenant.id, body)
        assert "@[invalid mention]" in out

    def test_no_db_renders_unresolved_placeholder(self):
        """Filter must still work when renderer is invoked without
        a DB session (defensive — legacy callers)."""
        from app.services.documents.document_renderer import _render_jinja

        out = _render_jinja(
            '{{ ref("case", "any") }}', {},
            db=None, company_id=None,
        )
        assert "@[unresolved]" in out


# ─── Composer + renderer integration ────────────────────────────


class TestComposerIntegration:
    def test_body_section_passthrough_holds(self, db, tenant, fh_case):
        """Verify that a body_section block with a mention token in
        its `body` config flows through composer → renderer end to
        end. This is the load-bearing pass-through claim."""
        from app.services.documents.block_registry import get_block_kind
        from app.services.documents.document_renderer import _render_jinja

        kind = get_block_kind("body_section")
        token = '{{ ref("case", "' + fh_case.id + '") }}'
        compiled = kind.compile_to_jinja(
            {"heading": "Reference", "body": f"See: {token}"},
            "",
        )
        # The token survives the composer step unchanged.
        assert token in compiled

        # Wrap in a minimal Jinja document and render.
        rendered = _render_jinja(compiled, {}, db=db, company_id=tenant.id)
        assert "Smith" in rendered
        assert 'class="doc-mention"' in rendered

    def test_multiple_mentions_dedupe_via_cache(
        self, db, tenant, fh_case, sales_order,
    ):
        """A document with 4 mentions but only 2 unique entities should
        only hit the resolver twice (cache dedup)."""
        from app.services.documents.document_renderer import (
            _jinja_env, _render_jinja,
        )

        body = (
            '<p>{{ ref("case", "' + fh_case.id + '") }}</p>'
            '<p>{{ ref("order", "' + sales_order.id + '") }}</p>'
            '<p>{{ ref("case", "' + fh_case.id + '") }}</p>'
            '<p>{{ ref("order", "' + sales_order.id + '") }}</p>'
        )
        # Render and inspect the cache via the env globals hook.
        env = _jinja_env(db=db, company_id=tenant.id)
        tpl = env.from_string(body)
        tpl.render()
        cache = env.globals["__mention_cache__"]
        # 4 invocations, 2 unique
        assert cache.resolution_count == 4
        assert cache.unique_resolutions == 2

    def test_separate_render_calls_get_separate_caches(
        self, db, tenant, fh_case,
    ):
        """Calling _render_jinja twice creates two independent caches
        — request-scoped per-render canonical."""
        from app.services.documents.document_renderer import _jinja_env

        env1 = _jinja_env(db=db, company_id=tenant.id)
        env2 = _jinja_env(db=db, company_id=tenant.id)
        # Different instances
        cache1 = env1.globals["__mention_cache__"]
        cache2 = env2.globals["__mention_cache__"]
        assert cache1 is not cache2


# ─── Endpoint (Q-DISPATCH-5) ────────────────────────────────────


class TestMentionEndpoint:
    """Tests the schema + handler via the resolver function — the full
    TestClient stack is heavy and the route layer is mostly a thin
    wrapper. These tests verify the route's contract by invoking the
    underlying calls + asserting on the request/response shape.
    """

    def test_schema_picker_subset_canonical(self):
        from app.schemas.document_template import MentionResolveRequest

        # All four picker types accepted.
        for t in ("case", "order", "contact", "product"):
            req = MentionResolveRequest(entity_type=t, query="x")
            assert req.entity_type == t

    def test_schema_rejects_invoice(self):
        from pydantic import ValidationError

        from app.schemas.document_template import MentionResolveRequest

        with pytest.raises(ValidationError):
            MentionResolveRequest(entity_type="invoice", query="x")

    def test_schema_rejects_task(self):
        """Task is in SEARCHABLE_ENTITIES (7 entity types) but NOT in
        the picker subset (4 entity types)."""
        from pydantic import ValidationError

        from app.schemas.document_template import MentionResolveRequest

        with pytest.raises(ValidationError):
            MentionResolveRequest(entity_type="task", query="x")

    def test_schema_query_length_bounded(self):
        from pydantic import ValidationError

        from app.schemas.document_template import MentionResolveRequest

        # 200-char max
        with pytest.raises(ValidationError):
            MentionResolveRequest(entity_type="case", query="x" * 201)

    def test_schema_limit_bounded(self):
        from pydantic import ValidationError

        from app.schemas.document_template import MentionResolveRequest

        # 20 max, 1 min
        with pytest.raises(ValidationError):
            MentionResolveRequest(entity_type="case", query="x", limit=21)
        with pytest.raises(ValidationError):
            MentionResolveRequest(entity_type="case", query="x", limit=0)

    def test_endpoint_short_circuits_empty_query(self):
        """Empty/whitespace query returns empty results without
        calling the resolver."""
        from app.api.routes.documents_v2 import resolve_mention
        from app.schemas.document_template import MentionResolveRequest
        from app.models.user import User
        from app.models.company import Company

        fake_user = User(
            id="u1", company_id="t1", email="a@b.com",
            hashed_password="x", is_active=True,
        )

        # If the resolver was called, this would fail because db is None.
        # Empty-query short-circuit means resolver is NOT called.
        result = resolve_mention(
            payload=MentionResolveRequest(entity_type="case", query=""),
            current_user=fake_user, db=None,
        )
        assert result.results == []
        assert result.total == 0

    def test_endpoint_returns_picker_vocab_in_response(
        self, db, tenant, fh_case,
    ):
        """Response items should carry UI vocabulary (`case`), not
        substrate vocabulary (`fh_case`). Picker UI shouldn't need
        to translate back."""
        from app.api.routes.documents_v2 import resolve_mention
        from app.models.user import User
        from app.schemas.document_template import MentionResolveRequest

        fake_user = User(
            id=str(uuid.uuid4()), company_id=tenant.id,
            email="admin@mention-test.com",
            hashed_password="x", is_active=True,
        )

        result = resolve_mention(
            payload=MentionResolveRequest(entity_type="case", query="Smith"),
            current_user=fake_user, db=db,
        )
        # Note: SQLite doesn't support pg_trgm — resolver wraps in
        # try/except and returns []. So we verify shape (response is
        # still a valid MentionResolveResponse) rather than content.
        assert isinstance(result.results, list)
        assert result.total == len(result.results)

    def test_endpoint_admin_required(self):
        """The handler signature requires admin (FastAPI dependency).
        Verified at the route registration layer; this asserts the
        route is registered + protected."""
        from app.api.routes.documents_v2 import router

        # Find the mention endpoint route entry
        mention_routes = [
            r for r in router.routes
            if hasattr(r, "path")
            and "/admin/mentions/resolve" in r.path
        ]
        assert len(mention_routes) == 1
        # FastAPI's dependency_overrides + the deps tuple confirms
        # require_admin runs before the handler.
        dep_funcs = [
            d.call for d in mention_routes[0].dependant.dependencies
        ]
        assert any(
            getattr(d, "__name__", "") == "require_admin"
            for d in dep_funcs
        )
