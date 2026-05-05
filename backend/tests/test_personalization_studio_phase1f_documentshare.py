"""Personalization Studio Phase 1F — DocumentShare grant + Mfg-side
from-share + read-only canvas chrome tests.

Per Phase 1F build prompt closing standards: backend tests covering
DocumentShare grant fire at canonical _handle_approve integration point
+ 4 canonical PTR consent failure modes + missing PTR + Mfg-side
open_instance_from_share canonical service + canvas-mutation-rejected
at canonical manufacturer_from_fh_share authoring context + canonical
"Mark reviewed" commit_instance flow + canonical D-6 audit ledger
events + 4 canonical anti-pattern guards.

**Anti-pattern guard tests covered**:
  - §2.5.4 Anti-pattern 14 (portal-specific feature creep within
    Spaces canon rejected) — canvas state lives at canonical owner
    Document; Mfg-tenant instance does NOT clone canvas state at
    Mfg-tenant scope.
  - §3.26.11.12.16 Anti-pattern 12 (parallel architectures rejected)
    — canonical Mfg-tenant manufacturer_from_fh_share authoring
    context shares canonical service layer + canonical Document
    substrate with canonical FH-tenant funeral_home_with_family
    authoring context.
  - §3.26.11.12.19.4 cross-tenant masking discipline (Q2 baked) —
    canonical full-disclosure-per-instance via grant; canvas state
    surfaces verbatim to canonical Mfg-tenant scope.
  - §2.5.4 Anti-pattern 17 (canonical action vocabulary bypassing
    rejected) — canonical canvas state mutations canonical-rejected
    at canonical manufacturer_from_fh_share scope with canonical 403.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.database import SessionLocal
from app.main import app
from app.models import Company, Role, User
from app.models.document_share import DocumentShare, DocumentShareEvent
from app.models.fh_case import FHCase
from app.models.platform_tenant_relationship import (
    PlatformTenantRelationship,
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
def fake_r2():
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
    ):
        yield storage


def _make_tenant(db_session, *, vertical, prefix):
    co = Company(
        id=str(uuid.uuid4()),
        name=f"{prefix} {uuid.uuid4().hex[:8]}",
        slug=f"{prefix.lower()}{uuid.uuid4().hex[:8]}",
        vertical=vertical,
    )
    db_session.add(co)
    db_session.flush()
    return co


def _make_user(db_session, tenant, *, first="Director", last="One"):
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
        email=f"u-{uuid.uuid4().hex[:8]}@p1f.test",
        hashed_password="x",
        first_name=first,
        last_name=last,
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _auth_headers(db_session, user):
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


def _make_fh_case(db_session, tenant):
    case = FHCase(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        case_number=f"C-{uuid.uuid4().hex[:6]}",
        deceased_first_name="John",
        deceased_last_name="Smith",
        deceased_date_of_death=date(2026, 1, 15),
    )
    db_session.add(case)
    db_session.flush()
    return case


def _make_ptr_pair(
    db_session,
    *,
    fh_tenant,
    mfg_tenant,
    consent_state="active",
):
    """Create canonical bilateral fh_manufacturer PTR pair with given
    consent state on BOTH PTR rows (per canonical r75 dual-row update
    pattern). Returns (forward_row, reverse_row)."""
    forward = PlatformTenantRelationship(
        id=str(uuid.uuid4()),
        tenant_id=fh_tenant.id,
        supplier_tenant_id=mfg_tenant.id,
        relationship_type="fh_manufacturer",
        status="active",
        personalization_studio_cross_tenant_sharing_consent=consent_state,
    )
    reverse = PlatformTenantRelationship(
        id=str(uuid.uuid4()),
        tenant_id=mfg_tenant.id,
        supplier_tenant_id=fh_tenant.id,
        relationship_type="fh_manufacturer",
        status="active",
        personalization_studio_cross_tenant_sharing_consent=consent_state,
    )
    db_session.add(forward)
    db_session.add(reverse)
    db_session.flush()
    return forward, reverse


def _setup_approved_instance(db_session, fake_r2, fh_tenant, fh_user):
    """Open + commit canvas + transition lifecycle to canonical
    committed + family_approval_status='approved' state. Returns the
    canonical post-approve instance ready for Phase 1F dispatch."""
    from app.services.personalization_studio import instance_service

    case = _make_fh_case(db_session, fh_tenant)
    instance = instance_service.open_instance(
        db_session,
        company_id=fh_tenant.id,
        template_type="burial_vault_personalization_studio",
        authoring_context="funeral_home_with_family",
        linked_entity_id=case.id,
        opened_by_user_id=fh_user.id,
    )
    instance_service.commit_canvas_state(
        db_session,
        instance_id=instance.id,
        canvas_state={
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
        },
        committed_by_user_id=fh_user.id,
    )
    # Stamp canonical committed lifecycle + approved family_approval_status
    # to mirror canonical post-Phase-1E-_handle_approve state.
    now = datetime.now(timezone.utc)
    instance.lifecycle_state = "committed"
    instance.family_approval_status = "approved"
    instance.committed_at = now
    instance.committed_by_user_id = fh_user.id
    instance.family_approval_decided_at = now
    # Phase 1E request_family_approval canonical-stamps action_payload
    # action metadata; mirror canonical metadata snapshot for canonical
    # decedent_name resolution at canonical email template var.
    instance.action_payload = {
        "actions": [
            {
                "action_type": "personalization_studio_family_approval",
                "action_target_type": "generation_focus_instance",
                "action_target_id": instance.id,
                "action_metadata": {
                    "decedent_name": "John Smith",
                    "fh_director_name": "Jane Director",
                    "family_email": "family@example.com",
                },
                "action_status": "approved",
                "action_completed_at": now.isoformat(),
                "action_completed_by": "family@example.com",
                "action_completion_metadata": {},
            }
        ]
    }
    db_session.flush()
    return instance


# ─────────────────────────────────────────────────────────────────────
# 1. family_approval_post_commit_dispatch — happy path
# ─────────────────────────────────────────────────────────────────────


class TestPostCommitDispatchHappyPath:
    @patch(
        "app.services.personalization_studio.family_approval"
        ".delivery_service.send_email_with_template"
        if False
        else "app.services.delivery.delivery_service.send_email_with_template"
    )
    def test_grant_fires_when_consent_active(
        self, mock_send, db_session, fake_r2
    ):
        from app.services.personalization_studio import family_approval

        class _FakeDelivery:
            id = "fake-delivery"

        mock_send.return_value = _FakeDelivery()

        fh = _make_tenant(db_session, vertical="funeral_home", prefix="FH")
        mfg = _make_tenant(db_session, vertical="manufacturing", prefix="MFG")
        fh_user = _make_user(db_session, fh)
        _make_user(db_session, mfg)  # Mfg admin — recipient of canonical email
        _make_ptr_pair(
            db_session, fh_tenant=fh, mfg_tenant=mfg, consent_state="active"
        )

        instance = _setup_approved_instance(
            db_session, fake_r2, fh, fh_user
        )
        db_session.commit()

        outcome = family_approval.family_approval_post_commit_dispatch(
            db_session, instance=instance
        )
        db_session.commit()

        assert outcome["outcome"] == "granted"
        assert outcome["share_id"] is not None
        assert outcome["target_company_id"] == mfg.id
        assert outcome["target_company_name"] == mfg.name
        assert outcome["error_detail"] is None

        # Canonical D-6 share row created at canonical Mfg-tenant scope.
        share = (
            db_session.query(DocumentShare)
            .filter(DocumentShare.id == outcome["share_id"])
            .first()
        )
        assert share is not None
        assert share.owner_company_id == fh.id
        assert share.target_company_id == mfg.id
        assert share.revoked_at is None

        # Canonical D-6 'granted' event audit ledger row.
        ev = (
            db_session.query(DocumentShareEvent)
            .filter(
                DocumentShareEvent.share_id == share.id,
                DocumentShareEvent.event_type == "granted",
            )
            .first()
        )
        assert ev is not None

        # Canonical email dispatched with canonical template_key.
        assert mock_send.called
        kwargs = mock_send.call_args.kwargs
        assert (
            kwargs["template_key"]
            == "email.personalization_studio_share_granted"
        )
        # Canonical canvas_url shape per canonical Mfg-tenant
        # entry-point route registration.
        canvas_url = kwargs["template_context"]["canvas_url"]
        assert canvas_url == f"/personalization-studio/from-share/{share.id}"

    def test_re_dispatch_on_existing_share_idempotent(
        self, db_session, fake_r2
    ):
        """Canonical D-6 partial-unique-active discipline: re-dispatch
        on canonical already-active share returns canonical existing
        share id (idempotent at canonical Phase 1F dispatch boundary)."""
        from app.services.documents import document_sharing_service
        from app.services.personalization_studio import family_approval

        fh = _make_tenant(db_session, vertical="funeral_home", prefix="FH")
        mfg = _make_tenant(db_session, vertical="manufacturing", prefix="MFG")
        fh_user = _make_user(db_session, fh)
        _make_ptr_pair(
            db_session, fh_tenant=fh, mfg_tenant=mfg, consent_state="active"
        )

        instance = _setup_approved_instance(
            db_session, fake_r2, fh, fh_user
        )
        db_session.commit()

        # First dispatch creates canonical share.
        first = family_approval.family_approval_post_commit_dispatch(
            db_session, instance=instance
        )
        db_session.commit()
        assert first["outcome"] == "granted"
        first_share_id = first["share_id"]

        # Stub email dispatch on second pass (avoids template seeding
        # dependency for the idempotency check).
        with patch(
            "app.services.delivery.delivery_service.send_email_with_template"
        ) as _:
            second = family_approval.family_approval_post_commit_dispatch(
                db_session, instance=instance
            )
            db_session.commit()
        assert second["outcome"] == "granted"
        assert second["share_id"] == first_share_id


# ─────────────────────────────────────────────────────────────────────
# 2. PTR consent failure modes (4 canonical states + missing PTR)
# ─────────────────────────────────────────────────────────────────────


class TestPostCommitDispatchFailureModes:
    def _setup_with_consent(self, db_session, fake_r2, consent_state):
        from app.services.personalization_studio import family_approval

        fh = _make_tenant(db_session, vertical="funeral_home", prefix="FH")
        mfg = _make_tenant(db_session, vertical="manufacturing", prefix="MFG")
        fh_user = _make_user(db_session, fh)
        _make_user(db_session, mfg)
        _make_ptr_pair(
            db_session,
            fh_tenant=fh,
            mfg_tenant=mfg,
            consent_state=consent_state,
        )
        instance = _setup_approved_instance(
            db_session, fake_r2, fh, fh_user
        )
        db_session.commit()
        return family_approval, fh, mfg, instance

    def test_consent_default_returns_canonical_failure(
        self, db_session, fake_r2
    ):
        family_approval, _, _, instance = self._setup_with_consent(
            db_session, fake_r2, "default"
        )
        outcome = family_approval.family_approval_post_commit_dispatch(
            db_session, instance=instance
        )
        assert outcome["outcome"] == "consent_default"
        assert outcome["share_id"] is None
        assert "consent" in outcome["error_detail"].lower()

    def test_consent_pending_outbound_returns_canonical_failure(
        self, db_session, fake_r2
    ):
        family_approval, _, _, instance = self._setup_with_consent(
            db_session, fake_r2, "pending_outbound"
        )
        outcome = family_approval.family_approval_post_commit_dispatch(
            db_session, instance=instance
        )
        assert outcome["outcome"] == "consent_pending_outbound"
        assert outcome["share_id"] is None
        assert "awaiting" in outcome["error_detail"].lower()

    def test_consent_pending_inbound_returns_canonical_failure(
        self, db_session, fake_r2
    ):
        family_approval, _, _, instance = self._setup_with_consent(
            db_session, fake_r2, "pending_inbound"
        )
        outcome = family_approval.family_approval_post_commit_dispatch(
            db_session, instance=instance
        )
        assert outcome["outcome"] == "consent_pending_inbound"
        assert outcome["share_id"] is None
        assert "requested" in outcome["error_detail"].lower()

    def test_missing_ptr_returns_canonical_failure(self, db_session, fake_r2):
        from app.services.personalization_studio import family_approval

        fh = _make_tenant(db_session, vertical="funeral_home", prefix="FH")
        fh_user = _make_user(db_session, fh)
        # NO PTR pair created — canonical missing-Mfg-connection state.
        instance = _setup_approved_instance(
            db_session, fake_r2, fh, fh_user
        )
        db_session.commit()

        outcome = family_approval.family_approval_post_commit_dispatch(
            db_session, instance=instance
        )
        assert outcome["outcome"] == "ptr_missing"
        assert outcome["share_id"] is None
        assert outcome["target_company_id"] is None
        assert outcome["relationship_id"] is None

    def test_failure_does_not_create_documentshare_row(
        self, db_session, fake_r2
    ):
        """Anti-pattern 14 + canonical separation: failure path does
        NOT canonical-write canonical DocumentShare row at canonical
        Mfg-tenant scope."""
        family_approval, fh, mfg, instance = self._setup_with_consent(
            db_session, fake_r2, "default"
        )
        family_approval.family_approval_post_commit_dispatch(
            db_session, instance=instance
        )
        db_session.commit()

        # Canonical zero canonical share rows for canonical instance
        # Document at canonical Mfg-tenant scope.
        share_count = (
            db_session.query(DocumentShare)
            .filter(
                DocumentShare.owner_company_id == fh.id,
                DocumentShare.target_company_id == mfg.id,
            )
            .count()
        )
        assert share_count == 0


# ─────────────────────────────────────────────────────────────────────
# 3. Manufacturer-side open_instance_from_share service
# ─────────────────────────────────────────────────────────────────────


class TestOpenInstanceFromShare:
    def _seed_share(self, db_session, fake_r2):
        from app.services.documents import document_sharing_service
        from app.services.personalization_studio import (
            instance_service,
        )

        fh = _make_tenant(db_session, vertical="funeral_home", prefix="FH")
        mfg = _make_tenant(db_session, vertical="manufacturing", prefix="MFG")
        fh_user = _make_user(db_session, fh)
        mfg_user = _make_user(db_session, mfg)
        _make_ptr_pair(
            db_session, fh_tenant=fh, mfg_tenant=mfg, consent_state="active"
        )
        fh_instance = _setup_approved_instance(
            db_session, fake_r2, fh, fh_user
        )

        # Resolve canonical owner Document.
        from app.models.canonical_document import Document

        document = (
            db_session.query(Document)
            .filter(Document.id == fh_instance.document_id)
            .first()
        )
        share = document_sharing_service.grant_share(
            db_session,
            document=document,
            target_company_id=mfg.id,
            granted_by_user_id=fh_user.id,
            reason="Phase 1F test",
            source_module="phase_1f_test",
            enforce_relationship=True,
        )
        db_session.commit()
        return instance_service, fh, mfg, mfg_user, fh_instance, share

    def test_creates_mfg_instance_at_manufacturer_from_fh_share_context(
        self, db_session, fake_r2
    ):
        (
            instance_service,
            fh,
            mfg,
            mfg_user,
            fh_instance,
            share,
        ) = self._seed_share(db_session, fake_r2)

        mfg_instance = instance_service.open_instance_from_share(
            db_session,
            document_share_id=share.id,
            mfg_company_id=mfg.id,
            opened_by_user_id=mfg_user.id,
        )
        db_session.commit()

        # Q3 canonical pairing: manufacturer_from_fh_share ↔
        # linked_entity_type='document_share'.
        assert mfg_instance.authoring_context == "manufacturer_from_fh_share"
        assert mfg_instance.linked_entity_type == "document_share"
        assert mfg_instance.linked_entity_id == share.id
        assert mfg_instance.company_id == mfg.id
        # Canonical Mfg-vertical: family_approval_status NULL.
        assert mfg_instance.family_approval_status is None
        # Anti-pattern 14: Mfg-instance points at canonical OWNER
        # Document — NOT a clone at Mfg-tenant scope.
        assert mfg_instance.document_id == fh_instance.document_id

    def test_idempotent_on_re_open(self, db_session, fake_r2):
        (
            instance_service,
            _,
            mfg,
            mfg_user,
            _,
            share,
        ) = self._seed_share(db_session, fake_r2)

        first = instance_service.open_instance_from_share(
            db_session,
            document_share_id=share.id,
            mfg_company_id=mfg.id,
            opened_by_user_id=mfg_user.id,
        )
        db_session.commit()
        second = instance_service.open_instance_from_share(
            db_session,
            document_share_id=share.id,
            mfg_company_id=mfg.id,
            opened_by_user_id=mfg_user.id,
        )
        db_session.commit()

        # Canonical single-canonical-instance-per-share guard.
        assert first.id == second.id

    def test_cross_tenant_share_returns_canonical_404(
        self, db_session, fake_r2
    ):
        """Anti-pattern 16 cross-realm guard: canonical Mfg-tenant A
        cannot canonical-open canonical share granted to canonical
        Mfg-tenant B (canonical existence-hiding 404)."""
        from app.services.personalization_studio import (
            instance_service,
        )
        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioNotFound,
        )

        (
            _,
            _,
            mfg_b,
            _,
            _,
            share,
        ) = self._seed_share(db_session, fake_r2)
        # Canonical other Mfg tenant attempting canonical access.
        mfg_a = _make_tenant(
            db_session, vertical="manufacturing", prefix="MFGA"
        )
        mfg_a_user = _make_user(db_session, mfg_a)
        db_session.commit()

        with pytest.raises(PersonalizationStudioNotFound):
            instance_service.open_instance_from_share(
                db_session,
                document_share_id=share.id,
                mfg_company_id=mfg_a.id,
                opened_by_user_id=mfg_a_user.id,
            )

    def test_revoked_share_returns_canonical_403(
        self, db_session, fake_r2
    ):
        from app.services.documents import document_sharing_service
        from app.services.personalization_studio import (
            instance_service,
        )
        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioPermissionDenied,
        )

        (
            _,
            fh,
            mfg,
            mfg_user,
            _,
            share,
        ) = self._seed_share(db_session, fake_r2)
        fh_user = (
            db_session.query(User).filter(User.company_id == fh.id).first()
        )
        document_sharing_service.revoke_share(
            db_session,
            share=share,
            revoked_by_user_id=fh_user.id,
            revoke_reason="Phase 1F test",
        )
        db_session.commit()

        with pytest.raises(PersonalizationStudioPermissionDenied):
            instance_service.open_instance_from_share(
                db_session,
                document_share_id=share.id,
                mfg_company_id=mfg.id,
                opened_by_user_id=mfg_user.id,
            )

    def test_emits_canonical_d6_accessed_event(
        self, db_session, fake_r2
    ):
        """Canonical D-6 audit ledger 'accessed' event canonical-emitted
        on canonical Mfg-tenant open."""
        (
            instance_service,
            _,
            mfg,
            mfg_user,
            _,
            share,
        ) = self._seed_share(db_session, fake_r2)
        instance_service.open_instance_from_share(
            db_session,
            document_share_id=share.id,
            mfg_company_id=mfg.id,
            opened_by_user_id=mfg_user.id,
        )
        db_session.commit()

        accessed = (
            db_session.query(DocumentShareEvent)
            .filter(
                DocumentShareEvent.share_id == share.id,
                DocumentShareEvent.event_type == "accessed",
            )
            .first()
        )
        assert accessed is not None
        assert accessed.actor_company_id == mfg.id


# ─────────────────────────────────────────────────────────────────────
# 4. Canvas state mutation rejection at manufacturer_from_fh_share
# ─────────────────────────────────────────────────────────────────────


class TestCanvasMutationRejected:
    """Anti-pattern 17 + Q9c canonical-discipline guidance:
    canonical canvas state mutations canonical-rejected at canonical
    manufacturer_from_fh_share authoring context."""

    def test_assert_canvas_state_mutation_permitted_rejects_mfg_share(
        self, db_session, fake_r2
    ):
        from app.services.personalization_studio import instance_service
        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioPermissionDenied,
        )

        # Use the seed flow + open_instance_from_share to produce a
        # canonical Mfg-tenant instance.
        from app.services.documents import document_sharing_service

        fh = _make_tenant(db_session, vertical="funeral_home", prefix="FH")
        mfg = _make_tenant(db_session, vertical="manufacturing", prefix="MFG")
        fh_user = _make_user(db_session, fh)
        mfg_user = _make_user(db_session, mfg)
        _make_ptr_pair(
            db_session, fh_tenant=fh, mfg_tenant=mfg, consent_state="active"
        )
        fh_instance = _setup_approved_instance(
            db_session, fake_r2, fh, fh_user
        )
        from app.models.canonical_document import Document

        document = (
            db_session.query(Document)
            .filter(Document.id == fh_instance.document_id)
            .first()
        )
        share = document_sharing_service.grant_share(
            db_session,
            document=document,
            target_company_id=mfg.id,
            granted_by_user_id=fh_user.id,
            source_module="phase_1f_test",
            enforce_relationship=True,
        )
        db_session.commit()
        mfg_instance = instance_service.open_instance_from_share(
            db_session,
            document_share_id=share.id,
            mfg_company_id=mfg.id,
            opened_by_user_id=mfg_user.id,
        )
        db_session.commit()

        # Canonical service-layer guard rejects.
        with pytest.raises(PersonalizationStudioPermissionDenied):
            instance_service.assert_canvas_state_mutation_permitted(
                mfg_instance
            )

    def test_assert_canvas_state_mutation_permitted_allows_fh_share(
        self, db_session, fake_r2
    ):
        from app.services.personalization_studio import instance_service

        fh = _make_tenant(db_session, vertical="funeral_home", prefix="FH")
        fh_user = _make_user(db_session, fh)
        case = _make_fh_case(db_session, fh)
        instance = instance_service.open_instance(
            db_session,
            company_id=fh.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="funeral_home_with_family",
            linked_entity_id=case.id,
            opened_by_user_id=fh_user.id,
        )
        # Canonical FH-vertical authoring context — guard passes through.
        instance_service.assert_canvas_state_mutation_permitted(instance)

    def test_commit_canvas_state_rejects_mfg_authoring_context(
        self, db_session, fake_r2
    ):
        """Canonical commit_canvas_state guard at canonical service
        substrate dispatch (not just at the standalone helper)."""
        from app.services.documents import document_sharing_service
        from app.services.personalization_studio import instance_service
        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioPermissionDenied,
        )

        fh = _make_tenant(db_session, vertical="funeral_home", prefix="FH")
        mfg = _make_tenant(db_session, vertical="manufacturing", prefix="MFG")
        fh_user = _make_user(db_session, fh)
        mfg_user = _make_user(db_session, mfg)
        _make_ptr_pair(
            db_session, fh_tenant=fh, mfg_tenant=mfg, consent_state="active"
        )
        fh_instance = _setup_approved_instance(
            db_session, fake_r2, fh, fh_user
        )
        from app.models.canonical_document import Document

        document = (
            db_session.query(Document)
            .filter(Document.id == fh_instance.document_id)
            .first()
        )
        share = document_sharing_service.grant_share(
            db_session,
            document=document,
            target_company_id=mfg.id,
            granted_by_user_id=fh_user.id,
            source_module="phase_1f_test",
            enforce_relationship=True,
        )
        db_session.commit()
        mfg_instance = instance_service.open_instance_from_share(
            db_session,
            document_share_id=share.id,
            mfg_company_id=mfg.id,
            opened_by_user_id=mfg_user.id,
        )
        db_session.commit()

        with pytest.raises(PersonalizationStudioPermissionDenied):
            instance_service.commit_canvas_state(
                db_session,
                instance_id=mfg_instance.id,
                canvas_state={
                    "schema_version": 1,
                    "template_type": (
                        "burial_vault_personalization_studio"
                    ),
                    "canvas_layout": {"elements": []},
                    "vault_product": {
                        "vault_product_id": None,
                        "vault_product_name": "Tampered",
                    },
                    "emblem_key": None,
                    "name_display": "TAMPERED",
                    "font": "comic-sans",
                    "birth_date_display": None,
                    "death_date_display": None,
                    "nameplate_text": None,
                    "options": {
                        "legacy_print": None,
                        "physical_nameplate": None,
                        "physical_emblem": None,
                        "vinyl": None,
                    },
                    "family_approval_status": "not_requested",
                },
                committed_by_user_id=mfg_user.id,
            )


# ─────────────────────────────────────────────────────────────────────
# 5. "Mark reviewed" canonical commit at manufacturer_from_fh_share
# ─────────────────────────────────────────────────────────────────────


class TestMarkReviewedCommit:
    def test_commit_instance_at_mfg_share_transitions_committed(
        self, db_session, fake_r2
    ):
        from app.services.documents import document_sharing_service
        from app.services.personalization_studio import instance_service

        fh = _make_tenant(db_session, vertical="funeral_home", prefix="FH")
        mfg = _make_tenant(db_session, vertical="manufacturing", prefix="MFG")
        fh_user = _make_user(db_session, fh)
        mfg_user = _make_user(db_session, mfg)
        _make_ptr_pair(
            db_session, fh_tenant=fh, mfg_tenant=mfg, consent_state="active"
        )
        fh_instance = _setup_approved_instance(
            db_session, fake_r2, fh, fh_user
        )
        from app.models.canonical_document import Document

        document = (
            db_session.query(Document)
            .filter(Document.id == fh_instance.document_id)
            .first()
        )
        share = document_sharing_service.grant_share(
            db_session,
            document=document,
            target_company_id=mfg.id,
            granted_by_user_id=fh_user.id,
            source_module="phase_1f_test",
            enforce_relationship=True,
        )
        db_session.commit()
        mfg_instance = instance_service.open_instance_from_share(
            db_session,
            document_share_id=share.id,
            mfg_company_id=mfg.id,
            opened_by_user_id=mfg_user.id,
        )
        db_session.commit()

        committed = instance_service.commit_instance(
            db_session,
            instance_id=mfg_instance.id,
            committed_by_user_id=mfg_user.id,
        )
        assert committed.lifecycle_state == "committed"
        assert committed.committed_at is not None
        assert committed.committed_by_user_id == mfg_user.id


# ─────────────────────────────────────────────────────────────────────
# 6. API surface — POST /from-share/{document_share_id}
# ─────────────────────────────────────────────────────────────────────


class TestFromShareEndpoint:
    def test_post_from_share_canonical_payload(
        self, db_session, fake_r2
    ):
        from app.services.documents import document_sharing_service

        fh = _make_tenant(db_session, vertical="funeral_home", prefix="FH")
        mfg = _make_tenant(db_session, vertical="manufacturing", prefix="MFG")
        fh_user = _make_user(db_session, fh)
        mfg_user = _make_user(db_session, mfg)
        _make_ptr_pair(
            db_session, fh_tenant=fh, mfg_tenant=mfg, consent_state="active"
        )
        fh_instance = _setup_approved_instance(
            db_session, fake_r2, fh, fh_user
        )
        from app.models.canonical_document import Document

        document = (
            db_session.query(Document)
            .filter(Document.id == fh_instance.document_id)
            .first()
        )
        share = document_sharing_service.grant_share(
            db_session,
            document=document,
            target_company_id=mfg.id,
            granted_by_user_id=fh_user.id,
            source_module="phase_1f_test",
            enforce_relationship=True,
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/personalization-studio/from-share/{share.id}",
                headers=_auth_headers(db_session, mfg_user),
            )
        assert r.status_code == 200
        body = r.json()
        # Canonical full-disclosure: canvas state surfaces verbatim per
        # §3.26.11.12.19.4 Q2 baked.
        assert body["canvas_state"] is not None
        assert body["canvas_state"]["name_display"] == "John Smith"
        assert body["instance"]["authoring_context"] == "manufacturer_from_fh_share"
        assert body["instance"]["linked_entity_type"] == "document_share"
        assert body["instance"]["linked_entity_id"] == share.id
        assert body["owner_company_id"] == fh.id
        assert body["owner_company_name"] == fh.name
        assert body["decedent_name"] == "John Smith"

    def test_post_from_share_cross_tenant_404(self, db_session, fake_r2):
        """Anti-pattern 16 cross-realm guard via canonical existence-
        hiding 404 at canonical service substrate."""
        from app.services.documents import document_sharing_service

        fh = _make_tenant(db_session, vertical="funeral_home", prefix="FH")
        mfg_a = _make_tenant(db_session, vertical="manufacturing", prefix="MFGA")
        mfg_b = _make_tenant(db_session, vertical="manufacturing", prefix="MFGB")
        fh_user = _make_user(db_session, fh)
        mfg_a_user = _make_user(db_session, mfg_a)
        _make_ptr_pair(
            db_session, fh_tenant=fh, mfg_tenant=mfg_b, consent_state="active"
        )
        fh_instance = _setup_approved_instance(
            db_session, fake_r2, fh, fh_user
        )
        from app.models.canonical_document import Document

        document = (
            db_session.query(Document)
            .filter(Document.id == fh_instance.document_id)
            .first()
        )
        share = document_sharing_service.grant_share(
            db_session,
            document=document,
            target_company_id=mfg_b.id,
            granted_by_user_id=fh_user.id,
            source_module="phase_1f_test",
            enforce_relationship=True,
        )
        db_session.commit()

        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/personalization-studio/from-share/{share.id}",
                headers=_auth_headers(db_session, mfg_a_user),
            )
        assert r.status_code == 404

    def test_post_from_share_auth_required(self, db_session, fake_r2):
        with TestClient(app) as client:
            r = client.post(
                f"/api/v1/personalization-studio/from-share/{uuid.uuid4()}"
            )
        assert r.status_code in (401, 403)


# ─────────────────────────────────────────────────────────────────────
# 7. Anti-pattern guard tests (4 explicit guards)
# ─────────────────────────────────────────────────────────────────────


class TestAntiPatternGuards:
    def test_anti_pattern_14_no_canvas_clone_at_mfg_scope(
        self, db_session, fake_r2
    ):
        """Anti-pattern 14: Mfg instance points at canonical OWNER
        Document; no canonical canvas clone at canonical Mfg-tenant
        scope. Verifies canonical Document substrate consumption."""
        from app.services.documents import document_sharing_service
        from app.services.personalization_studio import instance_service

        fh = _make_tenant(db_session, vertical="funeral_home", prefix="FH")
        mfg = _make_tenant(db_session, vertical="manufacturing", prefix="MFG")
        fh_user = _make_user(db_session, fh)
        mfg_user = _make_user(db_session, mfg)
        _make_ptr_pair(
            db_session, fh_tenant=fh, mfg_tenant=mfg, consent_state="active"
        )
        fh_instance = _setup_approved_instance(
            db_session, fake_r2, fh, fh_user
        )
        from app.models.canonical_document import Document

        document = (
            db_session.query(Document)
            .filter(Document.id == fh_instance.document_id)
            .first()
        )
        share = document_sharing_service.grant_share(
            db_session,
            document=document,
            target_company_id=mfg.id,
            granted_by_user_id=fh_user.id,
            source_module="phase_1f_test",
            enforce_relationship=True,
        )
        db_session.commit()
        mfg_instance = instance_service.open_instance_from_share(
            db_session,
            document_share_id=share.id,
            mfg_company_id=mfg.id,
            opened_by_user_id=mfg_user.id,
        )
        db_session.commit()

        # Same canonical Document FK at canonical Mfg-tenant instance
        # (no clone at Mfg-tenant scope).
        assert mfg_instance.document_id == fh_instance.document_id

    def test_anti_pattern_12_shared_service_layer(self, db_session, fake_r2):
        """Anti-pattern 12: canonical Mfg-tenant manufacturer_from_fh_share
        + canonical FH-tenant funeral_home_with_family share canonical
        instance_service.commit_instance + instance_service.get_canvas_state
        substrate (no parallel architecture)."""
        # Canonical commit_instance + get_canvas_state are
        # authoring_context-agnostic in canonical service layer (per
        # canonical Phase 1A canonical-pattern-establisher discipline).
        # Verify both authoring contexts route through the same
        # canonical functions without canonical fork.
        from app.services.personalization_studio import instance_service

        # Simply verify canonical function name + signature are
        # canonically context-agnostic (reflection-based pattern
        # check rather than runtime).
        import inspect

        sig_commit = inspect.signature(instance_service.commit_instance)
        sig_canvas = inspect.signature(instance_service.get_canvas_state)
        # Canonical service layer canonically context-agnostic — no
        # authoring_context kwarg in canonical signature.
        assert "authoring_context" not in sig_commit.parameters
        assert "authoring_context" not in sig_canvas.parameters

    def test_full_disclosure_per_instance_canon(
        self, db_session, fake_r2
    ):
        """§3.26.11.12.19.4 cross-tenant masking discipline: canonical
        full-disclosure-per-instance via grant. Canvas state surfaces
        verbatim to canonical Mfg-tenant scope (no field-level masking)."""
        from app.services.documents import document_sharing_service
        from app.services.personalization_studio import instance_service

        fh = _make_tenant(db_session, vertical="funeral_home", prefix="FH")
        mfg = _make_tenant(db_session, vertical="manufacturing", prefix="MFG")
        fh_user = _make_user(db_session, fh)
        mfg_user = _make_user(db_session, mfg)
        _make_ptr_pair(
            db_session, fh_tenant=fh, mfg_tenant=mfg, consent_state="active"
        )
        fh_instance = _setup_approved_instance(
            db_session, fake_r2, fh, fh_user
        )
        from app.models.canonical_document import Document

        document = (
            db_session.query(Document)
            .filter(Document.id == fh_instance.document_id)
            .first()
        )
        share = document_sharing_service.grant_share(
            db_session,
            document=document,
            target_company_id=mfg.id,
            granted_by_user_id=fh_user.id,
            source_module="phase_1f_test",
            enforce_relationship=True,
        )
        db_session.commit()
        mfg_instance = instance_service.open_instance_from_share(
            db_session,
            document_share_id=share.id,
            mfg_company_id=mfg.id,
            opened_by_user_id=mfg_user.id,
        )
        db_session.commit()

        canvas = instance_service.get_canvas_state(
            db_session, instance_id=mfg_instance.id
        )
        # Canonical full-disclosure: canonical canvas elements canonical-
        # surface verbatim.
        assert canvas["name_display"] == "John Smith"
        assert canvas["birth_date_display"] == "1950"
        assert canvas["death_date_display"] == "2026"
        assert canvas["vault_product"]["vault_product_name"] == "Bronze"

    def test_anti_pattern_17_action_vocabulary_bounded(
        self, db_session, fake_r2
    ):
        """Anti-pattern 17: canonical Mfg-tenant action vocabulary
        canonically bounded (Mark reviewed canonical only; canvas
        mutations canonical-rejected with canonical 403).

        Verifies via canonical commit_canvas_state guard rejection.
        """
        from app.services.personalization_studio import instance_service
        from app.services.personalization_studio.instance_service import (
            PersonalizationStudioPermissionDenied,
        )

        # Defensive smoke test: assert_canvas_state_mutation_permitted
        # is canonical service-layer guard (not just route-layer guard
        # which could be bypassed).
        guard = instance_service.assert_canvas_state_mutation_permitted

        # Canonical guard signature: takes instance, raises 403 on
        # manufacturer_from_fh_share. Verified by docstring discipline.
        assert callable(guard)

        # Canonical commit_canvas_state calls guard at canonical
        # entry-point (verified by integration test in
        # TestCanvasMutationRejected.test_commit_canvas_state_rejects_mfg_authoring_context).
        # This test serves as canonical pattern-establisher invariant —
        # adding a new canvas-mutating service entry-point requires
        # adding the guard call canonically.
        import inspect

        commit_canvas_src = inspect.getsource(
            instance_service.commit_canvas_state
        )
        assert (
            "assert_canvas_state_mutation_permitted" in commit_canvas_src
        ), (
            "commit_canvas_state must call assert_canvas_state_"
            "mutation_permitted at canonical service-layer guard "
            "site (Anti-pattern 17 pattern-establisher invariant)."
        )
