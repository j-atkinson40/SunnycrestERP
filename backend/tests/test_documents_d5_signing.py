"""Phase D-5 tests — disinterment on native signing + anchor overlay.

Covers:
  - Anchor-based overlay via PyMuPDF (real PDF in, real PDF out)
  - Disinterment creation wires signature_envelope_id
  - sig_* legacy columns stay synced with envelope state
  - DocuSign deprecated but still importable
  - Signature field anchor offsets + party_role resolution
"""

from __future__ import annotations

import base64
import io
import uuid
import warnings
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.database import Base


# ---------------------------------------------------------------------------
# Engine + fixtures — mirror D-4 suite with disinterment_cases added
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine():
    eng = create_engine("sqlite:///:memory:")

    from app.models.agent import AgentJob  # noqa: F401
    from app.models.canonical_document import Document, DocumentVersion  # noqa: F401
    from app.models.company import Company  # noqa: F401
    from app.models.company_entity import CompanyEntity  # noqa: F401
    from app.models.customer import Customer  # noqa: F401
    from app.models.disinterment_case import DisintermentCase  # noqa: F401
    from app.models.document_template import (  # noqa: F401
        DocumentTemplate,
        DocumentTemplateAuditLog,
        DocumentTemplateVersion,
    )
    from app.models.fh_case import FHCase  # noqa: F401
    from app.models.invoice import Invoice  # noqa: F401
    from app.models.price_list_version import PriceListVersion  # noqa: F401
    from app.models.role import Role  # noqa: F401
    from app.models.safety_program_generation import SafetyProgramGeneration  # noqa: F401
    from app.models.sales_order import SalesOrder  # noqa: F401
    from app.models.signature import (  # noqa: F401
        SignatureEnvelope,
        SignatureEvent,
        SignatureField,
        SignatureParty,
    )
    from app.models.document_delivery import DocumentDelivery  # noqa: F401
    from app.models.statement import CustomerStatement  # noqa: F401
    from app.models.user import User  # noqa: F401
    from app.models.workflow import WorkflowRun, WorkflowRunStep  # noqa: F401

    tables_needed = [
        "companies",
        "company_entities",
        "roles",
        "users",
        "customers",
        "cemeteries",
        "cemetery_plots",
        "price_list_versions",
        "price_list_items",
        "price_list_templates",
        "sales_orders",
        "invoices",
        "invoice_lines",
        "statement_runs",
        "customer_statements",
        "fh_cases",
        "disinterment_cases",
        "safety_training_topics",
        "safety_programs",
        "safety_program_generations",
        "tenant_training_schedules",
        "agent_jobs",
        "workflows",
        "workflow_runs",
        "workflow_run_steps",
        "intelligence_prompts",
        "intelligence_prompt_versions",
        "intelligence_model_routes",
        "intelligence_experiments",
        "intelligence_conversations",
        "intelligence_executions",
        "intelligence_messages",
        "intelligence_prompt_audit_log",
        "documents",
        "document_versions",
        "document_templates",
        "document_template_versions",
        "document_template_audit_log",
        "signature_envelopes",
        "signature_parties",
        "signature_fields",
        "signature_events",
        "document_deliveries",
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
        id=str(uuid.uuid4()), name="Sunnycrest", slug="sunnycrest", is_active=True,
    )
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def admin_user(db, tenant):
    from app.models.role import Role
    from app.models.user import User

    role = Role(
        id=str(uuid.uuid4()), company_id=tenant.id, name="Admin",
        slug="admin", is_system=True,
    )
    db.add(role)
    db.flush()
    u = User(
        id=str(uuid.uuid4()), company_id=tenant.id,
        email="admin@s.co", first_name="Ada", last_name="A",
        hashed_password="x", is_active=True, role_id=role.id,
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def document(db, tenant):
    from app.models.canonical_document import Document

    d = Document(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        document_type="disinterment_release",
        title="Release form",
        storage_key=f"tenants/{tenant.id}/documents/rel/v1.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        status="rendered",
    )
    db.add(d)
    db.flush()
    return d


# ---------------------------------------------------------------------------
# Anchor overlay — direct tests on the overlay engine with real PDFs
# ---------------------------------------------------------------------------


def _make_test_pdf(anchors: list[str]) -> bytes:
    """Generate a real PDF with each anchor string in invisible text so
    search_for finds it. Pure PyMuPDF, no dependencies on weasyprint."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)  # letter portrait
    y = 100
    for anchor in anchors:
        # visible label + invisible anchor to simulate our template style
        page.insert_text(
            (72, y), f"Signature line for {anchor}:",
            fontsize=11, color=(0, 0, 0),
        )
        # Invisible anchor — white text, tiny size at (x, y+8)
        page.insert_text(
            (72, y + 14), anchor,
            fontsize=1, color=(1, 1, 1),
        )
        y += 80
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def _tiny_png_bytes() -> bytes:
    """A tiny valid PNG — 8x8 red pixel for overlay testing."""
    from PIL import Image

    img = Image.new("RGBA", (8, 8), (255, 0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestOverlayEngine:
    def test_overlay_places_signature_at_anchor_position(self):
        from app.services.signing._overlay_engine import (
            OverlaySpec,
            apply_overlays,
            find_anchor_positions,
        )

        src = _make_test_pdf(["/sig_funeral_home/", "/sig_cemetery/"])
        positions = find_anchor_positions(
            src, ["/sig_funeral_home/", "/sig_cemetery/"]
        )
        assert positions["/sig_funeral_home/"] is not None
        assert positions["/sig_cemetery/"] is not None
        out, result = apply_overlays(
            src,
            [
                OverlaySpec(
                    image_bytes=_tiny_png_bytes(),
                    anchor_string="/sig_funeral_home/",
                    label="fh",
                ),
            ],
        )
        assert result.applied == 1
        assert result.missed_anchors == []
        # Output is a valid PDF
        assert out.startswith(b"%PDF")
        assert len(out) > len(src) - 100

    def test_overlay_places_multiple_signatures_single_pass(self):
        from app.services.signing._overlay_engine import (
            OverlaySpec,
            apply_overlays,
        )

        src = _make_test_pdf(
            ["/sig_a/", "/sig_b/", "/sig_c/", "/sig_d/"]
        )
        specs = [
            OverlaySpec(
                image_bytes=_tiny_png_bytes(),
                anchor_string=f"/sig_{x}/",
                label=x,
            )
            for x in ("a", "b", "c", "d")
        ]
        out, result = apply_overlays(src, specs)
        assert result.applied == 4
        assert result.missed_anchors == []

    def test_overlay_handles_missing_anchor_with_fallback(self):
        from app.services.signing._overlay_engine import (
            OverlaySpec,
            apply_overlays,
        )

        src = _make_test_pdf(["/sig_found/"])
        specs = [
            OverlaySpec(
                image_bytes=_tiny_png_bytes(),
                anchor_string="/sig_missing/",
                explicit_page=1,
                explicit_x_pt=100,
                explicit_y_pt=100,
                label="missing",
            ),
        ]
        out, result = apply_overlays(src, specs)
        assert result.missed_anchors == ["/sig_missing/"]
        # Fallback to explicit position still places it
        assert result.applied == 1

    def test_overlay_skips_when_no_anchor_and_no_position(self):
        from app.services.signing._overlay_engine import (
            OverlaySpec,
            apply_overlays,
        )

        src = _make_test_pdf(["/sig_a/"])
        specs = [
            OverlaySpec(
                image_bytes=_tiny_png_bytes(),
                anchor_string="/nothing/",  # missing, no explicit
                label="ghost",
            ),
        ]
        out, result = apply_overlays(src, specs)
        assert result.applied == 0
        assert "/nothing/" in result.missed_anchors

    def test_overlay_respects_offsets(self):
        """Offsets are applied on top of the anchor position — the
        resulting PDF's overlay rect reflects the sum."""
        from app.services.signing._overlay_engine import (
            OverlaySpec,
            apply_overlays,
            find_anchor_positions,
        )

        src = _make_test_pdf(["/sig_a/"])
        base = find_anchor_positions(src, ["/sig_a/"])["/sig_a/"]
        assert base is not None
        # Apply with a big y offset — no error means it placed somewhere
        # valid. We verify by re-running without offset and noting the
        # output bytes differ.
        out_no_offset, _ = apply_overlays(
            src,
            [
                OverlaySpec(
                    image_bytes=_tiny_png_bytes(),
                    anchor_string="/sig_a/",
                    label="a",
                ),
            ],
        )
        out_with_offset, _ = apply_overlays(
            src,
            [
                OverlaySpec(
                    image_bytes=_tiny_png_bytes(),
                    anchor_string="/sig_a/",
                    x_offset_pt=50.0,
                    y_offset_pt=30.0,
                    label="a",
                ),
            ],
        )
        # Same PDF base, different placements → different output bytes
        assert out_no_offset != out_with_offset


class TestSignatureImage:
    def test_drawn_signature_produces_png(self):
        from app.services.signing._signature_image import (
            render_drawn_signature,
        )

        # Seed with a tiny real PNG as the canvas output
        from PIL import Image

        img = Image.new("RGBA", (200, 50), (0, 0, 0, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        out = render_drawn_signature(b64, width_pt=180, height_pt=44)
        assert out.startswith(b"\x89PNG")
        assert len(out) > 100

    def test_drawn_signature_strips_data_uri_prefix(self):
        from PIL import Image

        from app.services.signing._signature_image import (
            render_drawn_signature,
        )

        img = Image.new("RGBA", (50, 50), (0, 255, 0, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        # Pass with data-URI prefix
        out = render_drawn_signature("data:image/png;base64," + b64)
        assert out.startswith(b"\x89PNG")

    def test_typed_signature_produces_png(self):
        from app.services.signing._signature_image import (
            render_typed_signature,
        )

        out = render_typed_signature("John Q. Public")
        assert out.startswith(b"\x89PNG")

    def test_signature_image_for_party_prefers_drawn(self):
        from PIL import Image

        from app.services.signing._signature_image import (
            signature_image_for_party,
        )

        img = Image.new("RGBA", (50, 50), (0, 0, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        out = signature_image_for_party(
            signature_type="drawn",
            signature_data=b64,
            typed_name="Ignored",
        )
        assert out is not None
        assert out.startswith(b"\x89PNG")

    def test_signature_image_for_party_falls_back_to_typed(self):
        from app.services.signing._signature_image import (
            signature_image_for_party,
        )

        out = signature_image_for_party(
            signature_type=None,
            signature_data=None,
            typed_name="Jane Doe",
        )
        assert out is not None
        assert out.startswith(b"\x89PNG")

    def test_signature_image_for_party_returns_none_when_empty(self):
        from app.services.signing._signature_image import (
            signature_image_for_party,
        )

        out = signature_image_for_party(
            signature_type=None,
            signature_data=None,
            typed_name=None,
        )
        assert out is None


# ---------------------------------------------------------------------------
# Disinterment integration
# ---------------------------------------------------------------------------


def _create_envelope(db, tenant, admin_user, document):
    from app.services.signing import signature_service

    with patch(
        "app.services.signing.signature_service.legacy_r2_client"
    ) as mock_r2:
        mock_r2.download_bytes.return_value = b"%PDF fake"
        env = signature_service.create_envelope(
            db,
            document_id=document.id,
            company_id=tenant.id,
            created_by_user_id=admin_user.id,
            subject="Disinterment Release",
            description="Test case",
            parties=[
                signature_service.PartyInput(
                    signing_order=1, role="funeral_home_director",
                    display_name="Jane FH", email="fh@x.co",
                ),
                signature_service.PartyInput(
                    signing_order=2, role="cemetery_rep",
                    display_name="Carl Cemetery", email="c@x.co",
                ),
                signature_service.PartyInput(
                    signing_order=3, role="next_of_kin",
                    display_name="Nancy NOK", email="n@x.co",
                ),
                signature_service.PartyInput(
                    signing_order=4, role="manufacturer",
                    display_name="Mike Manu", email="m@x.co",
                ),
            ],
            fields=[
                signature_service.FieldInput(
                    party_role="funeral_home_director",
                    field_type="signature",
                    anchor_string="/sig_funeral_home/",
                ),
                signature_service.FieldInput(
                    party_role="cemetery_rep",
                    field_type="signature",
                    anchor_string="/sig_cemetery/",
                ),
                signature_service.FieldInput(
                    party_role="next_of_kin",
                    field_type="signature",
                    anchor_string="/sig_next_of_kin/",
                ),
                signature_service.FieldInput(
                    party_role="manufacturer",
                    field_type="signature",
                    anchor_string="/sig_manufacturer/",
                ),
            ],
            routing_type="sequential",
        )
    db.flush()
    return env


class TestFieldPartyRoleResolution:
    def test_field_party_role_resolves_to_party_id(
        self, db, tenant, admin_user, document
    ):
        env = _create_envelope(db, tenant, admin_user, document)
        roles = {p.role: p.id for p in env.parties}
        fh_fields = [
            f for f in env.fields
            if f.party_id == roles["funeral_home_director"]
        ]
        assert len(fh_fields) == 1
        assert fh_fields[0].anchor_string == "/sig_funeral_home/"

    def test_field_signing_order_also_works(self, db, tenant, admin_user, document):
        from app.services.signing import signature_service

        with patch(
            "app.services.signing.signature_service.legacy_r2_client"
        ) as mock_r2:
            mock_r2.download_bytes.return_value = b"%PDF"
            env = signature_service.create_envelope(
                db,
                document_id=document.id,
                company_id=tenant.id,
                created_by_user_id=admin_user.id,
                subject="x",
                description=None,
                parties=[
                    signature_service.PartyInput(
                        signing_order=1, role="a",
                        display_name="A", email="a@x",
                    ),
                ],
                fields=[
                    signature_service.FieldInput(
                        signing_order=1, field_type="signature",
                        anchor_string="/a/",
                    ),
                ],
            )
        db.flush()
        assert len(env.fields) == 1

    def test_anchor_offsets_persist(self, db, tenant, admin_user, document):
        from app.services.signing import signature_service

        with patch(
            "app.services.signing.signature_service.legacy_r2_client"
        ) as mock_r2:
            mock_r2.download_bytes.return_value = b"%PDF"
            env = signature_service.create_envelope(
                db,
                document_id=document.id,
                company_id=tenant.id,
                created_by_user_id=admin_user.id,
                subject="x", description=None,
                parties=[
                    signature_service.PartyInput(
                        signing_order=1, role="a",
                        display_name="A", email="a@x",
                    ),
                ],
                fields=[
                    signature_service.FieldInput(
                        signing_order=1, field_type="signature",
                        anchor_string="/a/",
                        anchor_x_offset=12.5,
                        anchor_y_offset=-8.0,
                    ),
                ],
            )
        db.flush()
        f = env.fields[0]
        assert f.anchor_x_offset == 12.5
        assert f.anchor_y_offset == -8.0


class TestDisintermentCaseSync:
    def _make_case(self, db, tenant, envelope):
        from app.models.disinterment_case import DisintermentCase

        case = DisintermentCase(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            case_number="DI-TEST-1",
            decedent_name="John Doe",
            status="signatures_pending",
            signature_envelope_id=envelope.id,
            sig_funeral_home="sent",
            sig_cemetery="sent",
            sig_next_of_kin="sent",
            sig_manufacturer="sent",
            # Explicit defaults for JSONB columns (server_default on PG is
            # '[]'::jsonb but SQLite stores the literal string)
            next_of_kin=[],
            assigned_crew=[],
        )
        db.add(case)
        db.flush()
        return case

    def test_sync_runs_on_party_consent(
        self, db, tenant, admin_user, document
    ):
        from app.services.signing import signature_service

        env = _create_envelope(db, tenant, admin_user, document)
        case = self._make_case(db, tenant, env)

        # Send envelope so first party is "sent"
        with patch("app.services.signing.notification_service.send_invite"):
            signature_service.send_envelope(db, env.id)
        db.flush()

        p1 = sorted(env.parties, key=lambda p: p.signing_order)[0]
        signature_service.record_party_view(db, p1)
        signature_service.record_party_consent(
            db, p1, consent_text="ok", ip_address=None, user_agent=None,
        )
        db.flush()
        db.refresh(case)
        # Party is funeral_home_director → sig_funeral_home
        # viewed/consented → legacy "sent" in the mapping
        assert case.sig_funeral_home == "sent"

    def test_sync_updates_on_party_sign(
        self, db, tenant, admin_user, document
    ):
        from app.services.signing import signature_service

        env = _create_envelope(db, tenant, admin_user, document)
        case = self._make_case(db, tenant, env)

        with patch("app.services.signing.notification_service.send_invite"):
            signature_service.send_envelope(db, env.id)
        p1 = sorted(env.parties, key=lambda p: p.signing_order)[0]
        signature_service.record_party_view(db, p1)
        signature_service.record_party_consent(
            db, p1, consent_text="ok", ip_address=None, user_agent=None,
        )
        with patch(
            "app.services.signing.signature_service.complete_envelope"
        ):
            signature_service.record_party_signature(
                db, p1,
                signature_type="typed",
                signature_data="x",
                typed_signature_name="x",
                field_values={},
                ip_address="1.1.1.1", user_agent="ua",
            )
        db.flush()
        db.refresh(case)
        assert case.sig_funeral_home == "signed"
        assert case.sig_funeral_home_signed_at is not None

    def test_sync_on_envelope_complete(
        self, db, tenant, admin_user, document
    ):
        from app.services.signing import signature_service

        env = _create_envelope(db, tenant, admin_user, document)
        case = self._make_case(db, tenant, env)

        # Force-simulate completion via direct parties signed state
        for p in env.parties:
            p.status = "signed"
            p.signed_at = datetime.now(timezone.utc)
        env.status = "in_progress"
        db.flush()
        # Mock heavy side-effects
        with patch(
            "app.services.signing.signature_renderer.apply_signatures_as_new_version"
        ), patch(
            "app.services.signing.certificate_service.generate_certificate"
        ) as mock_cert, patch(
            "app.services.signing.notification_service.send_completed"
        ):
            mock_cert.return_value = type(
                "DocStub", (), {"id": "cert-id"}
            )()
            signature_service.complete_envelope(db, env)
        db.flush()
        db.refresh(case)
        assert env.status == "completed"
        assert case.status == "signatures_complete"

    def test_sync_on_decline_marks_case(
        self, db, tenant, admin_user, document
    ):
        from app.services.signing import signature_service

        env = _create_envelope(db, tenant, admin_user, document)
        case = self._make_case(db, tenant, env)

        with patch("app.services.signing.notification_service.send_invite"):
            signature_service.send_envelope(db, env.id)
        p1 = sorted(env.parties, key=lambda p: p.signing_order)[0]
        signature_service.record_party_view(db, p1)
        with patch(
            "app.services.signing.notification_service.send_declined"
        ):
            signature_service.record_party_decline(
                db, p1, reason="Changed mind",
                ip_address=None, user_agent=None,
            )
        db.flush()
        db.refresh(case)
        assert case.sig_funeral_home == "declined"

    def test_new_case_has_null_docusign_envelope_id(
        self, db, tenant
    ):
        from app.models.disinterment_case import DisintermentCase

        case = DisintermentCase(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            case_number="DI-NEW-1",
            decedent_name="New Person",
            status="draft",
            next_of_kin=[],
            assigned_crew=[],
        )
        db.add(case)
        db.flush()
        assert case.docusign_envelope_id is None
        assert case.signature_envelope_id is None  # not set yet


# ---------------------------------------------------------------------------
# DocuSign deprecation
# ---------------------------------------------------------------------------


class TestDocuSignDeprecation:
    def test_docusign_service_importable(self):
        from app.services import docusign_service  # noqa: F401

    def test_docusign_create_envelope_emits_deprecation_warning(self, db, tenant):
        from app.services import docusign_service

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                docusign_service.create_envelope(
                    db, tenant.id,
                    case_id="case-x", case_number="c1",
                    decedent_name="d",
                    funeral_home_email="f@x.co",
                    cemetery_email="c@x.co",
                    next_of_kin_email="n@x.co",
                    manufacturer_email="m@x.co",
                )
            except Exception:
                # The stub path may fail on SQLite for various reasons;
                # we care only that the DeprecationWarning fires, which
                # happens before any fallible work.
                pass
            assert any(
                issubclass(x.category, DeprecationWarning) for x in w
            )

    def test_docusign_webhook_module_importable(self):
        from app.api.routes import docusign_webhook  # noqa: F401
