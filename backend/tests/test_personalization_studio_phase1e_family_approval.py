"""Personalization Studio Phase 1E — family approval tests.

Per Phase 1E build prompt closing standards: backend tests covering
ActionTypeDescriptor registration + 2 email template registrations +
family portal Space template seed + magic-link substrate consumption +
service layer flow + per-outcome handler dispatch + 3-endpoint API
surface + JWT realm enforcement + cross-realm privilege bleed
rejection + 7 portal-extension anti-pattern guards + Anti-pattern 1.

**Anti-pattern guard tests covered**:
  - §2.5.4 Anti-pattern 13 (net-new portal substrate construction
    rejected) — Path B substrate consumption verified
  - §2.5.4 Anti-pattern 14 (portal-specific feature creep rejected)
    — Anti-pattern 14 enforced via canonical action_payload + Document
    substrate consumption (no parallel persistence)
  - §2.5.4 Anti-pattern 15 (portal authentication-substrate
    fragmentation rejected) — magic-link is sole auth factor
  - §2.5.4 Anti-pattern 16 (cross-realm privilege bleed rejected) —
    cross-tenant token rejected; cross-primitive token isolation
  - §2.5.4 Anti-pattern 17 (template-declared canonical action
    vocabulary bypassing rejected) — unknown outcome rejected
  - §2.5.4 Anti-pattern 18 (portal-as-replacement-for-tenant-UX
    rejected) — narrow scope verified at family portal Space
    template + canonical 3-outcome action vocabulary
  - §2.5.4 Anti-pattern 19 (per-portal authentication mechanism
    proliferation rejected) — magic-link is single canonical mechanism
  - §3.26.11.12.16 Anti-pattern 1 (operator agency at canonical
    commit affordance) — request_changes + decline require
    completion_note (canonical-rationale discipline)
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database import SessionLocal
from app.main import app
from app.models import Company, Role, User
from app.models.canonical_document import Document, DocumentVersion
from app.models.fh_case import FHCase
from app.models.generation_focus_instance import GenerationFocusInstance


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
def fake_r2():
    """Mock R2 upload + download with in-memory store."""
    storage: dict[str, bytes] = {}

    def fake_upload(
        data: bytes,
        r2_key: str,
        content_type: str = "application/octet-stream",
    ):
        storage[r2_key] = data
        return f"https://r2.test/{r2_key}"

    def fake_download(r2_key: str) -> bytes:
        return storage[r2_key]

    with (
        patch(
            "app.services.personalization_studio.instance_service.legacy_r2_client.upload_bytes",
            side_effect=fake_upload,
        ),
        patch(
            "app.services.personalization_studio.instance_service.legacy_r2_client.download_bytes",
            side_effect=fake_download,
        ),
        patch(
            "app.api.routes.personalization_studio_family_portal.legacy_r2_client.download_bytes",
            side_effect=fake_download,
        ),
    ):
        yield storage


def _make_tenant(db_session, *, vertical="funeral_home", name_prefix="P1E"):
    co = Company(
        id=str(uuid.uuid4()),
        name=f"{name_prefix} {uuid.uuid4().hex[:8]}",
        slug=f"p1e{uuid.uuid4().hex[:8]}",
        vertical=vertical,
    )
    db_session.add(co)
    db_session.flush()
    return co


def _make_user(db_session, tenant, *, first_name="Jane", last_name="Director"):
    role = Role(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        name="Admin",
        slug="admin",
        is_system=True,
    )
    db_session.add(role)
    db_session.flush()
    user = User(
        id=str(uuid.uuid4()),
        email=f"u-{uuid.uuid4().hex[:8]}@p1e.test",
        hashed_password="x",
        first_name=first_name,
        last_name=last_name,
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _auth_headers(db_session, user) -> dict[str, str]:
    company = (
        db_session.query(Company)
        .filter(Company.id == user.company_id)
        .first()
    )
    token = create_access_token(
        data={"sub": user.id, "company_id": user.company_id}
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Company-Slug": company.slug,
    }


def _make_fh_case(db_session, tenant, *, first="John", last="Smith"):
    from datetime import date

    case = FHCase(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        case_number=f"C-{uuid.uuid4().hex[:6]}",
        deceased_first_name=first,
        deceased_last_name=last,
        deceased_date_of_death=date(2026, 1, 15),
    )
    db_session.add(case)
    db_session.flush()
    return case


def _open_instance(
    db_session,
    tenant,
    user,
    *,
    authoring_context="funeral_home_with_family",
    linked_entity_id=None,
):
    from app.services.personalization_studio import instance_service

    instance = instance_service.open_instance(
        db_session,
        company_id=tenant.id,
        template_type="burial_vault_personalization_studio",
        authoring_context=authoring_context,
        linked_entity_id=linked_entity_id or str(uuid.uuid4()),
        opened_by_user_id=user.id,
    )
    db_session.flush()
    return instance


def _commit_canvas(db_session, instance, user, fake_r2):
    from app.services.personalization_studio import instance_service

    canvas_state = {
        "schema_version": 1,
        "template_type": "burial_vault_personalization_studio",
        "canvas_layout": {"elements": []},
        "vault_product": {
            "vault_product_id": None,
            "vault_product_name": "Bronze",
        },
        "emblem_key": None,
        "name_display": "John Smith",
        "font": "serif",
        "birth_date_display": "1950",
        "death_date_display": "2026",
        "nameplate_text": None,
        "options": {
            "legacy_print": None,
            "physical_nameplate": None,
            "physical_emblem": None,
            "vinyl": None,
        },
        "family_approval_status": "not_requested",
    }
    instance_service.commit_canvas_state(
        db_session,
        instance_id=instance.id,
        canvas_state=canvas_state,
        committed_by_user_id=user.id,
    )
    db_session.flush()
    return canvas_state


# ─────────────────────────────────────────────────────────────────────
# 1. ActionTypeDescriptor registration (Pattern A canonical)
# ─────────────────────────────────────────────────────────────────────


class TestActionTypeDescriptorRegistration:
    """Pattern A canonical-pattern-establisher: descriptor is template_
    type-agnostic. Step 2 reuses canonical descriptor."""

    def test_descriptor_registered_in_central_registry(self):
        # Side-effect-import via personalization_studio package.
        from app.services import personalization_studio  # noqa: F401
        from app.services.platform.action_registry import get_action_type

        descriptor = get_action_type(
            "personalization_studio_family_approval"
        )
        assert descriptor.primitive == "generation_focus"
        assert (
            descriptor.target_entity_type == "generation_focus_instance"
        )

    def test_canonical_3_outcome_reviewer_paths(self):
        from app.services.platform.action_registry import get_action_type

        descriptor = get_action_type(
            "personalization_studio_family_approval"
        )
        # Canonical §3.26.11.12.21 reviewer-paths.
        assert descriptor.outcomes == (
            "approve",
            "request_changes",
            "decline",
        )

    def test_request_changes_and_decline_require_completion_note(self):
        """Anti-pattern 1 + canonical-rationale discipline."""
        from app.services.platform.action_registry import get_action_type

        descriptor = get_action_type(
            "personalization_studio_family_approval"
        )
        assert "request_changes" in descriptor.requires_completion_note
        assert "decline" in descriptor.requires_completion_note
        assert "approve" not in descriptor.requires_completion_note

    def test_generation_focus_primitive_canonical_in_registry(self):
        """r77 canonical extension — generation_focus is the 5th
        canonical primitive class consuming Path B substrate."""
        from app.services.platform.action_registry import (
            PRIMITIVE_LINKED_ENTITY_TYPES,
        )

        assert "generation_focus" in PRIMITIVE_LINKED_ENTITY_TYPES
        assert (
            PRIMITIVE_LINKED_ENTITY_TYPES["generation_focus"]
            == "generation_focus_instance"
        )


# ─────────────────────────────────────────────────────────────────────
# 2. Email template registrations
# ─────────────────────────────────────────────────────────────────────


class TestEmailTemplateRegistrations:
    """Phase 1E ships 2 managed email templates per Phase 6 / 8b /
    8d.1 / Step 5.1 idempotent-seed canon."""

    def test_family_approval_request_template_seeded(self, db_session):
        from app.models.document_template import (
            DocumentTemplate,
            DocumentTemplateVersion,
        )

        tpl = (
            db_session.query(DocumentTemplate)
            .filter(
                DocumentTemplate.company_id.is_(None),
                DocumentTemplate.template_key
                == "email.personalization_studio_family_approval_request",
                DocumentTemplate.deleted_at.is_(None),
            )
            .first()
        )
        assert tpl is not None
        assert tpl.document_type == "email"
        assert tpl.output_format == "html"

        # Active v1 exists.
        version = (
            db_session.query(DocumentTemplateVersion)
            .filter(
                DocumentTemplateVersion.template_id == tpl.id,
                DocumentTemplateVersion.status == "active",
            )
            .first()
        )
        assert version is not None
        # Subject Jinja shape canonical.
        assert "decedent_name" in (version.subject_template or "")

    def test_share_granted_template_seeded(self, db_session):
        from app.models.document_template import DocumentTemplate

        tpl = (
            db_session.query(DocumentTemplate)
            .filter(
                DocumentTemplate.company_id.is_(None),
                DocumentTemplate.template_key
                == "email.personalization_studio_share_granted",
                DocumentTemplate.deleted_at.is_(None),
            )
            .first()
        )
        assert tpl is not None

    def test_seed_idempotent(self, db_session):
        """Re-running the seed produces noop_matched per canonical
        idempotent state machine."""
        from scripts.seed_personalization_studio_phase1e_email_templates import (
            seed_phase1e_email_templates,
        )

        counters = seed_phase1e_email_templates(db_session)
        # All templates should be noop_matched (already seeded by
        # session-level fixture / earlier test run).
        for key, c in counters.items():
            assert c["created"] == 0, key
            assert c["noop_matched"] >= 1, key


# ─────────────────────────────────────────────────────────────────────
# 3. Family portal Space template
# ─────────────────────────────────────────────────────────────────────


class TestFamilyPortalSpaceTemplate:
    """Anti-patterns 13 + 18 + 19: canonical Spaces config, narrow
    scope, single canonical authentication mechanism."""

    def test_canonical_modifiers(self):
        from app.services.spaces.registry import (
            FAMILY_PORTAL_SPACE_TEMPLATE,
        )

        assert FAMILY_PORTAL_SPACE_TEMPLATE.access_mode == "portal_external"
        assert FAMILY_PORTAL_SPACE_TEMPLATE.tenant_branding is True
        assert FAMILY_PORTAL_SPACE_TEMPLATE.write_mode == "limited"
        assert FAMILY_PORTAL_SPACE_TEMPLATE.session_timeout_minutes == 60

    def test_canonical_no_pin_clutter(self):
        """Anti-pattern 18 (portal-as-replacement-for-tenant-UX
        rejected): single-canvas focus; no nav affordances."""
        from app.services.spaces.registry import (
            FAMILY_PORTAL_SPACE_TEMPLATE,
        )

        assert FAMILY_PORTAL_SPACE_TEMPLATE.pins == []
        assert FAMILY_PORTAL_SPACE_TEMPLATE.is_default is True


# ─────────────────────────────────────────────────────────────────────
# 4. Service layer — request_family_approval flow
# ─────────────────────────────────────────────────────────────────────


class TestRequestFamilyApprovalService:
    def test_canonical_fh_vertical_pairing_enforced(
        self, db_session, fake_r2
    ):
        """Q3 canonical pairing: family approval canonical FH-vertical
        only. Mfg-vertical authoring contexts rejected."""
        from app.services.personalization_studio import family_approval

        tenant = _make_tenant(db_session, vertical="manufacturing")
        user = _make_user(db_session, tenant)
        instance = _open_instance(
            db_session,
            tenant,
            user,
            authoring_context="manufacturer_without_family",
        )
        db_session.commit()

        with pytest.raises(family_approval.FamilyApprovalInvalidContext):
            family_approval.request_family_approval(
                db_session,
                instance=instance,
                family_email="family@example.com",
                fh_director_user_id=user.id,
            )

    def test_appends_action_to_instance_action_payload(
        self, db_session, fake_r2
    ):
        from app.services.personalization_studio import family_approval

        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        case = _make_fh_case(db_session, tenant)
        instance = _open_instance(
            db_session,
            tenant,
            user,
            linked_entity_id=case.id,
        )
        db_session.commit()

        action_idx, token = family_approval.request_family_approval(
            db_session,
            instance=instance,
            family_email="Family@Example.com  ",
            fh_director_user_id=user.id,
            fh_director_name="Jane Director",
            decedent_name="John Smith",
            vault_product_name="Bronze",
        )
        db_session.commit()
        db_session.refresh(instance)

        assert action_idx == 0
        assert token  # token is non-empty
        # Action shape canonical per build_family_approval_action.
        actions = family_approval.get_instance_actions(instance)
        assert len(actions) == 1
        a = actions[0]
        assert (
            a["action_type"]
            == "personalization_studio_family_approval"
        )
        assert a["action_target_type"] == "generation_focus_instance"
        assert a["action_target_id"] == instance.id
        assert a["action_status"] == "pending"
        assert (
            a["action_metadata"]["decedent_name"] == "John Smith"
        )
        # Family approval status updated to "requested".
        assert instance.family_approval_status == "requested"

    def test_terminal_lifecycle_states_rejected(
        self, db_session, fake_r2
    ):
        from app.services.personalization_studio import family_approval

        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        instance = _open_instance(db_session, tenant, user)
        instance.lifecycle_state = "committed"
        db_session.commit()

        with pytest.raises(family_approval.FamilyApprovalError):
            family_approval.request_family_approval(
                db_session,
                instance=instance,
                family_email="family@example.com",
                fh_director_user_id=user.id,
            )


# ─────────────────────────────────────────────────────────────────────
# 5. Service layer — per-outcome commit handler dispatch
# ─────────────────────────────────────────────────────────────────────


class TestCommitHandlerOutcomes:
    """3-outcome reviewer-paths per §3.26.11.12.21."""

    def _setup(self, db_session, fake_r2):
        from app.services.personalization_studio import (
            family_approval,
            instance_service,
        )

        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        case = _make_fh_case(db_session, tenant)
        instance = _open_instance(
            db_session, tenant, user, linked_entity_id=case.id
        )
        _commit_canvas(db_session, instance, user, fake_r2)
        action_idx, token = family_approval.request_family_approval(
            db_session,
            instance=instance,
            family_email="family@example.com",
            fh_director_user_id=user.id,
            decedent_name="John Smith",
        )
        db_session.commit()
        return tenant, user, instance, action_idx, token

    def test_approve_lifecycle_committed(self, db_session, fake_r2):
        from app.services.personalization_studio import family_approval

        _, _, instance, _, token = self._setup(db_session, fake_r2)

        family_approval.commit_family_approval_via_token(
            db_session,
            token=token,
            outcome="approve",
        )
        db_session.commit()
        db_session.refresh(instance)

        assert instance.family_approval_status == "approved"
        assert instance.lifecycle_state == "committed"
        assert instance.committed_at is not None

    def test_request_changes_lifecycle_draft_with_rationale(
        self, db_session, fake_r2
    ):
        from app.services.personalization_studio import family_approval

        _, _, instance, _, token = self._setup(db_session, fake_r2)

        family_approval.commit_family_approval_via_token(
            db_session,
            token=token,
            outcome="request_changes",
            completion_note="Please change the font to Garamond.",
        )
        db_session.commit()
        db_session.refresh(instance)

        # Canonical: family_approval_status → 'rejected' (model enum)
        # but lifecycle_state reverts to 'draft' (FH director adjusts).
        assert instance.family_approval_status == "rejected"
        assert instance.lifecycle_state == "draft"

    def test_decline_lifecycle_abandoned_with_rationale(
        self, db_session, fake_r2
    ):
        from app.services.personalization_studio import family_approval

        _, _, instance, _, token = self._setup(db_session, fake_r2)

        family_approval.commit_family_approval_via_token(
            db_session,
            token=token,
            outcome="decline",
            completion_note="The family wants to step back from this approach.",
        )
        db_session.commit()
        db_session.refresh(instance)

        assert instance.family_approval_status == "rejected"
        assert instance.lifecycle_state == "abandoned"
        assert instance.abandoned_at is not None

    def test_request_changes_without_completion_note_rejected(
        self, db_session, fake_r2
    ):
        """Anti-pattern 1 + canonical-rationale discipline."""
        from app.services.platform.action_service import ActionError
        from app.services.personalization_studio import family_approval

        _, _, _, _, token = self._setup(db_session, fake_r2)

        with pytest.raises(ActionError):
            family_approval.commit_family_approval_via_token(
                db_session,
                token=token,
                outcome="request_changes",
                completion_note=None,
            )

    def test_decline_without_completion_note_rejected(
        self, db_session, fake_r2
    ):
        from app.services.platform.action_service import ActionError
        from app.services.personalization_studio import family_approval

        _, _, _, _, token = self._setup(db_session, fake_r2)

        with pytest.raises(ActionError):
            family_approval.commit_family_approval_via_token(
                db_session,
                token=token,
                outcome="decline",
                completion_note="   ",  # whitespace-only rejected
            )

    def test_unknown_outcome_rejected(self, db_session, fake_r2):
        """Anti-pattern 17 (canonical action vocabulary bypassing
        rejected) — unknown outcome rejected at substrate."""
        from app.services.platform.action_service import ActionError
        from app.services.personalization_studio import family_approval

        _, _, _, _, token = self._setup(db_session, fake_r2)

        with pytest.raises(ActionError):
            family_approval.commit_family_approval_via_token(
                db_session,
                token=token,
                outcome="bogus_outcome",
            )

    def test_double_commit_rejected(self, db_session, fake_r2):
        """Single-shot magic-link discipline per §3.26.11.9."""
        from app.services.platform.action_service import (
            ActionAlreadyCompleted,
            ActionTokenAlreadyConsumed,
        )
        from app.services.personalization_studio import family_approval

        _, _, _, _, token = self._setup(db_session, fake_r2)

        family_approval.commit_family_approval_via_token(
            db_session, token=token, outcome="approve"
        )
        db_session.commit()

        with pytest.raises(
            (ActionAlreadyCompleted, ActionTokenAlreadyConsumed)
        ):
            family_approval.commit_family_approval_via_token(
                db_session,
                token=token,
                outcome="approve",
            )


# ─────────────────────────────────────────────────────────────────────
# 6. API endpoints — FH director request
# ─────────────────────────────────────────────────────────────────────


class TestFhDirectorRequestEndpoint:
    @patch(
        "app.api.routes.personalization_studio.delivery_service.send_email_with_template"
    )
    def test_post_request_family_approval_dispatches_email(
        self, mock_send, db_session, fake_r2
    ):
        # Mock returns a fake DocumentDelivery-like object with an id.
        class _FakeDelivery:
            id = "fake-delivery-id"

        mock_send.return_value = _FakeDelivery()

        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        case = _make_fh_case(db_session, tenant)
        instance = _open_instance(
            db_session, tenant, user, linked_entity_id=case.id
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/personalization-studio/instances/{instance.id}"
                "/request-family-approval",
                json={
                    "family_email": "family@example.com",
                    "family_first_name": "Mary",
                },
                headers=_auth_headers(db_session, user),
            )

        assert r.status_code == 200
        body = r.json()
        assert body["instance_id"] == instance.id
        assert body["family_approval_status"] == "requested"
        assert body["delivery_id"] == "fake-delivery-id"
        # Email dispatched with canonical template_key.
        assert mock_send.called
        kwargs = mock_send.call_args.kwargs
        assert (
            kwargs["template_key"]
            == "email.personalization_studio_family_approval_request"
        )
        # Magic-link URL canonical shape per §3.26.11.9.
        approval_url = kwargs["template_context"]["approval_url"]
        assert "/portal/" in approval_url
        assert "/personalization-studio/family-approval/" in approval_url

    def test_post_request_cross_tenant_404(self, db_session, fake_r2):
        """Anti-pattern 16 (cross-realm privilege bleed): FH director
        of tenant A cannot request family approval on tenant B's
        instance — existence-hiding 404."""
        tenant_a = _make_tenant(db_session, name_prefix="A")
        tenant_b = _make_tenant(db_session, name_prefix="B")
        user_a = _make_user(db_session, tenant_a)
        user_b = _make_user(db_session, tenant_b)
        case_b = _make_fh_case(db_session, tenant_b)
        instance_b = _open_instance(
            db_session, tenant_b, user_b, linked_entity_id=case_b.id
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/personalization-studio/instances/{instance_b.id}"
                "/request-family-approval",
                json={"family_email": "family@example.com"},
                headers=_auth_headers(db_session, user_a),
            )
        assert r.status_code == 404

    def test_post_request_auth_required(self, db_session, fake_r2):
        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/personalization-studio/instances/{uuid.uuid4()}"
                "/request-family-approval",
                json={"family_email": "family@example.com"},
            )
        assert r.status_code in (401, 403)


# ─────────────────────────────────────────────────────────────────────
# 7. API endpoints — Family portal GET + POST (magic-link)
# ─────────────────────────────────────────────────────────────────────


class TestFamilyPortalEndpoints:
    def _setup(self, db_session, fake_r2):
        from app.services.personalization_studio import family_approval

        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        case = _make_fh_case(db_session, tenant)
        instance = _open_instance(
            db_session, tenant, user, linked_entity_id=case.id
        )
        _commit_canvas(db_session, instance, user, fake_r2)
        action_idx, token = family_approval.request_family_approval(
            db_session,
            instance=instance,
            family_email="family@example.com",
            fh_director_user_id=user.id,
            fh_director_name="Jane Director",
            decedent_name="John Smith",
        )
        db_session.commit()
        return tenant, instance, token

    def test_get_returns_canonical_payload(self, db_session, fake_r2):
        tenant, instance, token = self._setup(db_session, fake_r2)

        with TestClient(app) as client:
            r = client.get(
                f"/api/v1/portal/{tenant.slug}/personalization-studio/"
                f"family-approval/{token}"
            )
        assert r.status_code == 200
        body = r.json()
        assert body["instance_id"] == instance.id
        assert body["decedent_name"] == "John Smith"
        assert body["fh_director_name"] == "Jane Director"
        assert body["action_status"] == "pending"
        # 3-outcome canonical surface.
        assert tuple(body["outcomes"]) == (
            "approve",
            "request_changes",
            "decline",
        )
        # Canonical Space modifier slice surfaces canonical wash-not-
        # reskin discipline.
        assert body["space"]["access_mode"] == "portal_external"
        assert body["space"]["tenant_branding"] is True
        assert body["space"]["write_mode"] == "limited"
        # Canvas snapshot surfaces canonical canvas state.
        assert body["canvas"]["canvas_state"] is not None
        assert (
            body["canvas"]["canvas_state"]["name_display"]
            == "John Smith"
        )

    def test_get_invalid_token_401(self, db_session, fake_r2):
        tenant, _, _ = self._setup(db_session, fake_r2)

        with TestClient(app) as client:
            r = client.get(
                f"/api/v1/portal/{tenant.slug}/personalization-studio/"
                f"family-approval/bogus_invalid_token_value"
            )
        assert r.status_code == 401

    def test_get_cross_tenant_token_404(self, db_session, fake_r2):
        """Anti-pattern 16 cross-realm guard: token issued for tenant
        A consumed at tenant B's URL → existence-hiding 404."""
        tenant_a, _, token = self._setup(db_session, fake_r2)
        tenant_b = _make_tenant(db_session, name_prefix="B")
        db_session.commit()

        with TestClient(app) as client:
            r = client.get(
                f"/api/v1/portal/{tenant_b.slug}/personalization-studio/"
                f"family-approval/{token}"
            )
        assert r.status_code == 404

    def test_post_approve_consumes_token(self, db_session, fake_r2):
        tenant, instance, token = self._setup(db_session, fake_r2)

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/portal/{tenant.slug}/personalization-studio/"
                f"family-approval/{token}",
                json={"outcome": "approve"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["outcome"] == "approve"
        assert body["action_status"] == "approved"
        assert body["family_approval_status"] == "approved"
        assert body["lifecycle_state"] == "committed"

        # Re-commit returns 409 (consumed).
        with TestClient(app) as client:
            r2 = client.post(
                f"/api/v1/portal/{tenant.slug}/personalization-studio/"
                f"family-approval/{token}",
                json={"outcome": "approve"},
            )
        assert r2.status_code == 409

    def test_post_request_changes_with_rationale(
        self, db_session, fake_r2
    ):
        tenant, _, token = self._setup(db_session, fake_r2)

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/portal/{tenant.slug}/personalization-studio/"
                f"family-approval/{token}",
                json={
                    "outcome": "request_changes",
                    "completion_note": "Please change the font.",
                },
            )
        assert r.status_code == 200
        body = r.json()
        assert body["action_status"] == "changes_requested"
        assert body["lifecycle_state"] == "draft"

    def test_post_request_changes_without_rationale_rejected(
        self, db_session, fake_r2
    ):
        """Anti-pattern 1 at API substrate."""
        tenant, _, token = self._setup(db_session, fake_r2)

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/portal/{tenant.slug}/personalization-studio/"
                f"family-approval/{token}",
                json={"outcome": "request_changes"},
            )
        assert r.status_code == 400

    def test_post_decline_with_rationale(self, db_session, fake_r2):
        tenant, _, token = self._setup(db_session, fake_r2)

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/portal/{tenant.slug}/personalization-studio/"
                f"family-approval/{token}",
                json={
                    "outcome": "decline",
                    "completion_note": "We will reconsider later.",
                },
            )
        assert r.status_code == 200
        body = r.json()
        assert body["action_status"] == "declined"
        assert body["lifecycle_state"] == "abandoned"

    def test_post_unknown_outcome_rejected_by_pydantic(
        self, db_session, fake_r2
    ):
        """Anti-pattern 17 + Pydantic Literal validation."""
        tenant, _, token = self._setup(db_session, fake_r2)

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/portal/{tenant.slug}/personalization-studio/"
                f"family-approval/{token}",
                json={"outcome": "bogus_outcome"},
            )
        # Pydantic Literal validation → 422.
        assert r.status_code == 422

    def test_portal_endpoints_no_jwt_no_auth_header(
        self, db_session, fake_r2
    ):
        """Anti-pattern 16 + Anti-pattern 19: portal endpoints accept
        no JWT/auth header — magic-link is sole authentication factor.
        Portal request succeeds without any Authorization header."""
        tenant, _, token = self._setup(db_session, fake_r2)

        with TestClient(app) as client:
            r = client.get(
                f"/api/v1/portal/{tenant.slug}/personalization-studio/"
                f"family-approval/{token}"
            )
        # Portal works WITHOUT any auth header.
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────
# 8. Cross-primitive token isolation (Anti-pattern 16)
# ─────────────────────────────────────────────────────────────────────


class TestCrossPrimitiveTokenIsolation:
    """Anti-pattern 16 cross-realm privilege bleed guard at substrate
    boundary. A calendar/email/etc. token cannot be consumed at the
    family-approval portal endpoint."""

    def test_email_token_rejected_at_family_approval_endpoint(
        self, db_session, fake_r2
    ):
        from app.services.platform.action_service import (
            issue_action_token,
        )

        tenant = _make_tenant(db_session)
        db_session.commit()

        # Issue an email-primitive token (canonical quote_approval
        # action_type per Email Step 4c r66 substrate).
        email_token = issue_action_token(
            db_session,
            tenant_id=tenant.id,
            linked_entity_type="email_message",
            linked_entity_id=str(uuid.uuid4()),
            action_idx=0,
            action_type="quote_approval",
            recipient_email="recipient@example.com",
        )
        db_session.commit()

        # GET at family-approval portal with email-primitive token →
        # cross-primitive isolation rejection.
        with TestClient(app) as client:
            r = client.get(
                f"/api/v1/portal/{tenant.slug}/personalization-studio/"
                f"family-approval/{email_token}"
            )
        assert r.status_code == 401


# ─────────────────────────────────────────────────────────────────────
# 9. Anti-pattern 13 + 14 — Path B substrate consumption
# ─────────────────────────────────────────────────────────────────────


class TestPathBSubstrateConsumption:
    """Anti-pattern 13 (net-new portal substrate construction
    rejected) + Anti-pattern 14 (portal-specific feature creep
    rejected): family approval consumes Path B platform_action_tokens
    + canonical Document substrate; no parallel persistence tables."""

    def test_token_persists_to_platform_action_tokens(
        self, db_session, fake_r2
    ):
        """Tokens go to canonical platform_action_tokens table — NOT
        a separate family_portal_action_tokens (Anti-pattern 13)."""
        from sqlalchemy import text

        from app.services.personalization_studio import family_approval

        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        case = _make_fh_case(db_session, tenant)
        instance = _open_instance(
            db_session, tenant, user, linked_entity_id=case.id
        )
        db_session.commit()

        _, token = family_approval.request_family_approval(
            db_session,
            instance=instance,
            family_email="family@example.com",
            fh_director_user_id=user.id,
        )
        db_session.commit()

        # Canonical platform_action_tokens row exists.
        row = db_session.execute(
            text(
                "SELECT linked_entity_type, action_type, tenant_id "
                "FROM platform_action_tokens WHERE token = :t"
            ),
            {"t": token},
        ).mappings().first()
        assert row is not None
        assert row["linked_entity_type"] == "generation_focus_instance"
        assert (
            row["action_type"]
            == "personalization_studio_family_approval"
        )
        assert row["tenant_id"] == tenant.id

    def test_action_persists_to_action_payload_jsonb(
        self, db_session, fake_r2
    ):
        """Action shape lives at action_payload['actions'][] on
        generation_focus_instances — NOT a parallel persistence
        location (Anti-pattern 14)."""
        from app.services.personalization_studio import family_approval

        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        case = _make_fh_case(db_session, tenant)
        instance = _open_instance(
            db_session, tenant, user, linked_entity_id=case.id
        )
        db_session.commit()

        family_approval.request_family_approval(
            db_session,
            instance=instance,
            family_email="family@example.com",
            fh_director_user_id=user.id,
        )
        db_session.commit()
        db_session.refresh(instance)

        assert "actions" in (instance.action_payload or {})
        actions = instance.action_payload["actions"]
        assert len(actions) == 1
        # Canonical shape mirrors email_messages.message_payload +
        # calendar_events.action_payload precedents (no parallel shape).
        assert "action_type" in actions[0]
        assert "action_status" in actions[0]
        assert "action_metadata" in actions[0]
        assert "action_completion_metadata" in actions[0]
