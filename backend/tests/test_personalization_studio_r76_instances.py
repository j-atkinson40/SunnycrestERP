"""Personalization Studio Phase 1A canonical-pattern-establisher tests
— ``generation_focus_instances`` substrate + ``personalization_studio``
service module.

Per Step 1 Phase 1A canonical-pattern-establisher boundary:

- Canonical entity model schema (template_type discriminator + authoring_context
  3-value enumeration + lifecycle_state 4-state enumeration + polymorphic
  linked_entity per Q3 canonical pairing per §3.26.11.12.19.3 baked)
- Canonical Document substrate consumption per D-9 (document_type
  ``burial_vault_personalization_studio`` discriminator + DocumentVersion
  versioning at canvas commit + canonical R2 storage convention)
- Canonical case_merchandise.vault_personalization JSONB denormalization
  for FH-vertical authoring context (post-r74 canonical 4-options vocabulary)
- Canonical-pattern-establisher discipline: schema + service patterns
  Step 2 (Urn Vault Personalization Studio) inherits via discriminator
  differentiation
- Canonical anti-pattern guards explicit (§2.4.4 + §3.26.11.12.16):
  vertical-specific code creep + primitive proliferation +
  UI-coupled Generation Focus design rejected at substrate boundary
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import (
    CanonicalDocument,
    Company,
    DocumentVersion,
    GenerationFocusInstance,
    Role,
    User,
)
from app.models.fh_case import FHCase
from app.models.funeral_case import (
    CaseDeceased,
    CaseInformant,
    CaseMerchandise,
    CaseService,
    FuneralCase,
)
from app.models.generation_focus_instance import (
    AUTHORING_CONTEXT_TO_LINKED_ENTITY_TYPE,
    CANONICAL_AUTHORING_CONTEXTS,
    CANONICAL_FAMILY_APPROVAL_STATUSES,
    CANONICAL_LIFECYCLE_STATES,
    CANONICAL_LINKED_ENTITY_TYPES,
    CANONICAL_TEMPLATE_TYPES,
)
from app.services.personalization_studio import instance_service
from app.services.personalization_studio.instance_service import (
    CANVAS_STATE_SCHEMA_VERSION,
    DOCUMENT_TYPE_FOR_TEMPLATE,
    PersonalizationStudioError,
    PersonalizationStudioInvalidTransition,
    PersonalizationStudioNotFound,
    _canvas_storage_key,
    _empty_canvas_state,
    abandon_instance,
    commit_canvas_state,
    commit_instance,
    get_canvas_state,
    get_instance,
    list_instances_for_linked_entity,
    open_instance,
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
    """Mock R2 upload + download with in-memory store. Returns the
    captured upload list + the storage dict.
    """
    storage: dict[str, bytes] = {}

    def fake_upload(data: bytes, r2_key: str, content_type: str = "application/octet-stream"):
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


def _make_tenant(db_session, *, vertical="manufacturing", name_prefix="R76"):
    co = Company(
        id=str(uuid.uuid4()),
        name=f"{name_prefix} {uuid.uuid4().hex[:8]}",
        slug=f"r76{uuid.uuid4().hex[:8]}",
        vertical=vertical,
    )
    db_session.add(co)
    db_session.flush()
    return co


def _make_user(db_session, tenant):
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
        email=f"u-{uuid.uuid4().hex[:8]}@r76.test",
        hashed_password="x",
        first_name="A",
        last_name="U",
        company_id=tenant.id,
        role_id=role.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_funeral_case_with_merchandise(db_session, tenant):
    """Create a canonical FuneralCase row + its CaseMerchandise satellite
    so the FH-vertical denormalization path has a target row to update.
    """
    case = FuneralCase(
        id=str(uuid.uuid4()),
        company_id=tenant.id,
        case_number=f"FC-{uuid.uuid4().hex[:6].upper()}",
        status="active",
    )
    db_session.add(case)
    db_session.flush()
    merchandise = CaseMerchandise(
        id=str(uuid.uuid4()),
        case_id=case.id,
        company_id=tenant.id,
    )
    db_session.add(merchandise)
    db_session.flush()
    return case, merchandise


# ─────────────────────────────────────────────────────────────────────
# 1. Schema verification — Phase 1A canonical-pattern-establisher
# ─────────────────────────────────────────────────────────────────────


class TestEntityModelSchema:
    """Canonical entity model schema per Phase 1A canonical-pattern-establisher."""

    def test_table_exists(self, db_session):
        assert "generation_focus_instances" in inspect(
            db_session.bind
        ).get_table_names()

    def test_canonical_columns_present(self, db_session):
        cols = {
            c["name"]
            for c in inspect(db_session.bind).get_columns(
                "generation_focus_instances"
            )
        }
        canonical_required = {
            "id",
            "company_id",
            "template_type",
            "authoring_context",
            "lifecycle_state",
            "linked_entity_type",
            "linked_entity_id",
            "document_id",
            "opened_at",
            "opened_by_user_id",
            "last_active_at",
            "committed_at",
            "committed_by_user_id",
            "abandoned_at",
            "abandoned_by_user_id",
            "family_approval_status",
            "family_approval_requested_at",
            "family_approval_decided_at",
            "created_at",
            "updated_at",
        }
        missing = canonical_required - cols
        assert not missing, f"Missing canonical columns: {missing}"

    def test_canonical_check_constraints_present(self, db_session):
        result = db_session.execute(
            text(
                """
                SELECT conname FROM pg_constraint
                WHERE conrelid = 'generation_focus_instances'::regclass
                AND contype = 'c'
                """
            )
        )
        constraints = {row[0] for row in result}
        canonical_check_constraints = {
            "ck_gen_focus_template_type",
            "ck_gen_focus_authoring_context",
            "ck_gen_focus_lifecycle_state",
            "ck_gen_focus_linked_entity_type",
            "ck_gen_focus_authoring_linked_entity_pair",
            "ck_gen_focus_family_approval_status",
        }
        missing = canonical_check_constraints - constraints
        assert not missing, f"Missing canonical CHECK constraints: {missing}"

    def test_canonical_indexes_present(self, db_session):
        idxes = {
            i["name"]
            for i in inspect(db_session.bind).get_indexes(
                "generation_focus_instances"
            )
        }
        canonical_indexes = {
            "ix_gen_focus_company_template_lifecycle",
            "ix_gen_focus_linked_entity",
            "ix_gen_focus_document_id",
            "ix_gen_focus_user_active",
        }
        missing = canonical_indexes - idxes
        assert not missing, f"Missing canonical indexes: {missing}"


# ─────────────────────────────────────────────────────────────────────
# 2. Canonical enumerations enforced at substrate boundary
# ─────────────────────────────────────────────────────────────────────


class TestCanonicalEnumerations:
    """Q3 canonical enumerations enforced via CHECK constraints."""

    def test_template_type_canonical_value_accepted(self, db_session):
        tenant = _make_tenant(db_session)
        instance = GenerationFocusInstance(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            lifecycle_state="active",
            linked_entity_type="sales_order",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.add(instance)
        db_session.flush()

    def test_template_type_invalid_value_rejected(self, db_session):
        tenant = _make_tenant(db_session)
        instance = GenerationFocusInstance(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            template_type="bogus_template",
            authoring_context="manufacturer_without_family",
            lifecycle_state="active",
            linked_entity_type="sales_order",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.add(instance)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_authoring_context_canonical_3_values(self):
        """§3.26.11.12.19.3 Q3 canonical 3-value enumeration."""
        assert set(CANONICAL_AUTHORING_CONTEXTS) == {
            "funeral_home_with_family",
            "manufacturer_without_family",
            "manufacturer_from_fh_share",
        }

    def test_authoring_context_invalid_value_rejected(self, db_session):
        tenant = _make_tenant(db_session)
        instance = GenerationFocusInstance(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="bogus_context",
            lifecycle_state="active",
            linked_entity_type="sales_order",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.add(instance)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_lifecycle_state_canonical_4_states(self):
        assert set(CANONICAL_LIFECYCLE_STATES) == {
            "active",
            "draft",
            "committed",
            "abandoned",
        }

    def test_lifecycle_state_invalid_value_rejected(self, db_session):
        tenant = _make_tenant(db_session)
        instance = GenerationFocusInstance(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            lifecycle_state="bogus_state",
            linked_entity_type="sales_order",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.add(instance)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_linked_entity_type_canonical_values(self):
        assert set(CANONICAL_LINKED_ENTITY_TYPES) == {
            "fh_case",
            "sales_order",
            "document_share",
        }

    def test_family_approval_status_canonical_4_states(self):
        assert set(CANONICAL_FAMILY_APPROVAL_STATUSES) == {
            "not_requested",
            "requested",
            "approved",
            "rejected",
        }


# ─────────────────────────────────────────────────────────────────────
# 3. Q3 canonical authoring_context ↔ linked_entity_type pairing
# ─────────────────────────────────────────────────────────────────────


class TestQ3CanonicalPairing:
    """§3.26.11.12.19.3 baked: authoring_context ↔ linked_entity_type pairing."""

    def test_canonical_pairing_table_complete(self):
        assert AUTHORING_CONTEXT_TO_LINKED_ENTITY_TYPE == {
            "funeral_home_with_family": "fh_case",
            "manufacturer_without_family": "sales_order",
            "manufacturer_from_fh_share": "document_share",
        }

    def test_funeral_home_with_family_paired_with_fh_case(self, db_session):
        tenant = _make_tenant(db_session)
        instance = GenerationFocusInstance(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="funeral_home_with_family",
            lifecycle_state="active",
            linked_entity_type="fh_case",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.add(instance)
        db_session.flush()

    def test_funeral_home_with_family_with_sales_order_rejected(self, db_session):
        """Canonical pairing CHECK constraint blocks invalid pairings."""
        tenant = _make_tenant(db_session)
        instance = GenerationFocusInstance(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="funeral_home_with_family",
            lifecycle_state="active",
            linked_entity_type="sales_order",  # canonical mismatch
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.add(instance)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_manufacturer_without_family_with_fh_case_rejected(self, db_session):
        tenant = _make_tenant(db_session)
        instance = GenerationFocusInstance(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            lifecycle_state="active",
            linked_entity_type="fh_case",  # canonical mismatch
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.add(instance)
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_manufacturer_from_fh_share_paired_with_document_share(
        self, db_session
    ):
        tenant = _make_tenant(db_session)
        instance = GenerationFocusInstance(
            id=str(uuid.uuid4()),
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_from_fh_share",
            lifecycle_state="active",
            linked_entity_type="document_share",
            linked_entity_id=str(uuid.uuid4()),
        )
        db_session.add(instance)
        db_session.flush()


# ─────────────────────────────────────────────────────────────────────
# 4. Service layer — open_instance + canonical Document substrate
# ─────────────────────────────────────────────────────────────────────


class TestOpenInstance:
    def test_open_instance_creates_entity_and_document(
        self, db_session, fake_r2
    ):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)

        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
            opened_by_user_id=user.id,
        )

        assert instance.id is not None
        assert instance.template_type == "burial_vault_personalization_studio"
        assert instance.authoring_context == "manufacturer_without_family"
        assert instance.linked_entity_type == "sales_order"  # Q3 derived
        assert instance.lifecycle_state == "active"
        assert instance.document_id is not None

        # Canonical Document substrate per D-9 created with canonical
        # document_type discriminator.
        doc = (
            db_session.query(CanonicalDocument)
            .filter(CanonicalDocument.id == instance.document_id)
            .first()
        )
        assert doc is not None
        assert doc.document_type == "burial_vault_personalization_studio"
        assert doc.mime_type == "application/json"
        assert doc.status == "draft"  # no canvas commit yet
        assert doc.caller_module == (
            "personalization_studio.instance_service.open_instance"
        )

    def test_open_instance_q3_pairing_derived_from_authoring_context(
        self, db_session, fake_r2
    ):
        """Service layer derives canonical linked_entity_type from authoring_context."""
        tenant = _make_tenant(db_session)
        for ctx, expected_type in AUTHORING_CONTEXT_TO_LINKED_ENTITY_TYPE.items():
            instance = open_instance(
                db_session,
                company_id=tenant.id,
                template_type="burial_vault_personalization_studio",
                authoring_context=ctx,
                linked_entity_id=str(uuid.uuid4()),
            )
            assert instance.linked_entity_type == expected_type

    def test_open_instance_fh_vertical_seeds_family_approval_status(
        self, db_session, fake_r2
    ):
        """FH-vertical authoring context seeds family_approval_status canonical default."""
        tenant = _make_tenant(db_session, vertical="funeral_home")
        case, _ = _make_funeral_case_with_merchandise(db_session, tenant)
        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="funeral_home_with_family",
            linked_entity_id=case.id,
        )
        assert instance.family_approval_status == "not_requested"

    def test_open_instance_mfg_vertical_family_approval_null(
        self, db_session, fake_r2
    ):
        """Mfg-vertical authoring contexts canonical family_approval_status NULL."""
        tenant = _make_tenant(db_session)
        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        assert instance.family_approval_status is None

    def test_open_instance_invalid_template_type_rejected(self, db_session):
        tenant = _make_tenant(db_session)
        with pytest.raises(PersonalizationStudioError):
            open_instance(
                db_session,
                company_id=tenant.id,
                template_type="bogus_template",
                authoring_context="manufacturer_without_family",
                linked_entity_id=str(uuid.uuid4()),
            )

    def test_open_instance_invalid_authoring_context_rejected(self, db_session):
        tenant = _make_tenant(db_session)
        with pytest.raises(PersonalizationStudioError):
            open_instance(
                db_session,
                company_id=tenant.id,
                template_type="burial_vault_personalization_studio",
                authoring_context="bogus_context",
                linked_entity_id=str(uuid.uuid4()),
            )

    def test_open_instance_with_initial_canvas_state_commits_v1(
        self, db_session, fake_r2
    ):
        """Caller-supplied initial canvas state triggers first commit canonical."""
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        seed_state = _empty_canvas_state("burial_vault_personalization_studio")
        seed_state["nameplate_text"] = "John Smith"

        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
            opened_by_user_id=user.id,
            initial_canvas_state=seed_state,
        )

        # Canonical first DocumentVersion canonical at v1 with is_current.
        versions = (
            db_session.query(DocumentVersion)
            .filter(DocumentVersion.document_id == instance.document_id)
            .all()
        )
        assert len(versions) == 1
        assert versions[0].version_number == 1
        assert versions[0].is_current is True


# ─────────────────────────────────────────────────────────────────────
# 5. Canvas state shape — Phase 1A canonical-pattern-establisher
# ─────────────────────────────────────────────────────────────────────


class TestCanvasStateShape:
    """Canonical canvas state shape per discovery output Section 2a."""

    def test_empty_canvas_state_includes_all_canonical_fields(self):
        state = _empty_canvas_state("burial_vault_personalization_studio")
        required = {
            "schema_version",
            "template_type",
            "canvas_layout",
            "vault_product",
            "emblem_key",
            "name_display",
            "font",
            "birth_date_display",
            "death_date_display",
            "nameplate_text",
            "options",
            "family_approval_status",
        }
        assert required <= set(state.keys())

    def test_empty_canvas_state_options_canonical_4_post_r74(self):
        """Canonical 4-options vocabulary per §3.26.11.12.19.2 post-r74."""
        state = _empty_canvas_state("burial_vault_personalization_studio")
        assert set(state["options"].keys()) == {
            "legacy_print",
            "physical_nameplate",
            "physical_emblem",
            "vinyl",
        }

    def test_empty_canvas_state_no_legacy_vocabulary(self):
        """Canvas state shape canonically excludes legacy pre-r74 vocabulary."""
        state = _empty_canvas_state("burial_vault_personalization_studio")
        legacy_vocab = {"nameplate", "cover_emblem", "lifes_reflections"}
        assert not (set(state["options"].keys()) & legacy_vocab)

    def test_empty_canvas_state_schema_version_canonical(self):
        state = _empty_canvas_state("burial_vault_personalization_studio")
        assert state["schema_version"] == CANVAS_STATE_SCHEMA_VERSION

    def test_empty_canvas_state_unknown_template_rejected(self):
        with pytest.raises(PersonalizationStudioError):
            _empty_canvas_state("unknown_template_type")

    def test_canvas_storage_key_canonical_convention(self):
        key = _canvas_storage_key("co1", "doc1", 3)
        assert key == "tenants/co1/documents/doc1/canvas_state_v3.json"


# ─────────────────────────────────────────────────────────────────────
# 6. DocumentVersion versioning canonical at canvas commit
# ─────────────────────────────────────────────────────────────────────


class TestCommitCanvasStateVersioning:
    def test_first_commit_creates_v1_with_is_current(self, db_session, fake_r2):
        tenant = _make_tenant(db_session)
        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        state = _empty_canvas_state("burial_vault_personalization_studio")
        state["nameplate_text"] = "First Commit"

        version = commit_canvas_state(
            db_session,
            instance_id=instance.id,
            canvas_state=state,
        )
        assert version.version_number == 1
        assert version.is_current is True
        assert version.mime_type == "application/json"

    def test_second_commit_increments_version_and_flips_is_current(
        self, db_session, fake_r2
    ):
        tenant = _make_tenant(db_session)
        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        state1 = _empty_canvas_state("burial_vault_personalization_studio")
        state1["nameplate_text"] = "First"
        commit_canvas_state(
            db_session, instance_id=instance.id, canvas_state=state1
        )

        state2 = _empty_canvas_state("burial_vault_personalization_studio")
        state2["nameplate_text"] = "Second"
        v2 = commit_canvas_state(
            db_session, instance_id=instance.id, canvas_state=state2
        )

        # Canonical D-9 versioning: monotonic version_number + is_current flip.
        assert v2.version_number == 2
        assert v2.is_current is True

        all_versions = (
            db_session.query(DocumentVersion)
            .filter(DocumentVersion.document_id == instance.document_id)
            .order_by(DocumentVersion.version_number)
            .all()
        )
        assert len(all_versions) == 2
        assert all_versions[0].version_number == 1
        assert all_versions[0].is_current is False  # flipped
        assert all_versions[1].version_number == 2
        assert all_versions[1].is_current is True

    def test_commit_updates_document_storage_key(self, db_session, fake_r2):
        """Canonical D-9 convenience pattern: Document.storage_key mirrors current version."""
        tenant = _make_tenant(db_session)
        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        state = _empty_canvas_state("burial_vault_personalization_studio")
        version = commit_canvas_state(
            db_session, instance_id=instance.id, canvas_state=state
        )

        doc = (
            db_session.query(CanonicalDocument)
            .filter(CanonicalDocument.id == instance.document_id)
            .first()
        )
        assert doc.storage_key == version.storage_key
        assert "canvas_state_v1.json" in doc.storage_key
        assert doc.status == "rendered"

    def test_commit_uploads_canvas_state_json_to_r2(self, db_session, fake_r2):
        """Canvas state persists to R2 substrate per D-9 canonical pattern."""
        tenant = _make_tenant(db_session)
        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        state = _empty_canvas_state("burial_vault_personalization_studio")
        state["nameplate_text"] = "Upload Test"
        version = commit_canvas_state(
            db_session, instance_id=instance.id, canvas_state=state
        )

        # fake_r2 captures the upload.
        assert version.storage_key in fake_r2
        uploaded = json.loads(fake_r2[version.storage_key].decode("utf-8"))
        assert uploaded["nameplate_text"] == "Upload Test"
        assert uploaded["schema_version"] == CANVAS_STATE_SCHEMA_VERSION
        assert uploaded["template_type"] == "burial_vault_personalization_studio"

    def test_get_canvas_state_returns_current_version(
        self, db_session, fake_r2
    ):
        tenant = _make_tenant(db_session)
        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        state = _empty_canvas_state("burial_vault_personalization_studio")
        state["nameplate_text"] = "Roundtrip"
        commit_canvas_state(
            db_session, instance_id=instance.id, canvas_state=state
        )

        loaded = get_canvas_state(db_session, instance_id=instance.id)
        assert loaded is not None
        assert loaded["nameplate_text"] == "Roundtrip"

    def test_get_canvas_state_returns_none_pre_first_commit(
        self, db_session, fake_r2
    ):
        tenant = _make_tenant(db_session)
        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        # No commit yet → canonical None per substrate-consumption contract.
        assert get_canvas_state(db_session, instance_id=instance.id) is None


# ─────────────────────────────────────────────────────────────────────
# 7. case_merchandise.vault_personalization JSONB denormalization
#    (FH-vertical authoring context per Q3 canonical pairing)
# ─────────────────────────────────────────────────────────────────────


class TestJsonbDenormalization:
    def test_fh_vertical_commit_denormalizes_to_case_merchandise(
        self, db_session, fake_r2
    ):
        tenant = _make_tenant(db_session, vertical="funeral_home")
        case, merchandise = _make_funeral_case_with_merchandise(
            db_session, tenant
        )
        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="funeral_home_with_family",
            linked_entity_id=case.id,
        )
        state = _empty_canvas_state("burial_vault_personalization_studio")
        state["nameplate_text"] = "Smith Family"
        state["emblem_key"] = "rose"
        state["options"]["vinyl"] = {"symbol": "Cross"}

        commit_canvas_state(
            db_session, instance_id=instance.id, canvas_state=state
        )

        db_session.refresh(merchandise)
        assert merchandise.vault_personalization is not None
        assert merchandise.vault_personalization["nameplate_text"] == "Smith Family"
        assert merchandise.vault_personalization["emblem_key"] == "rose"
        assert merchandise.vault_personalization["options"]["vinyl"] == {
            "symbol": "Cross"
        }

    def test_fh_vertical_denormalization_post_r74_canonical_vocabulary(
        self, db_session, fake_r2
    ):
        """JSONB denormalization preserves canonical 4-options vocabulary post-r74."""
        tenant = _make_tenant(db_session, vertical="funeral_home")
        case, merchandise = _make_funeral_case_with_merchandise(
            db_session, tenant
        )
        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="funeral_home_with_family",
            linked_entity_id=case.id,
        )
        state = _empty_canvas_state("burial_vault_personalization_studio")
        state["options"]["physical_nameplate"] = {}
        state["options"]["physical_emblem"] = {}

        commit_canvas_state(
            db_session, instance_id=instance.id, canvas_state=state
        )

        db_session.refresh(merchandise)
        denormalized_options = merchandise.vault_personalization["options"]
        # Canonical post-r74 vocabulary present.
        assert set(denormalized_options.keys()) == {
            "legacy_print",
            "physical_nameplate",
            "physical_emblem",
            "vinyl",
        }
        # Legacy pre-r74 vocabulary canonically absent.
        assert "nameplate" not in denormalized_options
        assert "cover_emblem" not in denormalized_options
        assert "lifes_reflections" not in denormalized_options

    def test_mfg_vertical_does_not_denormalize_to_case_merchandise(
        self, db_session, fake_r2
    ):
        """Mfg-vertical authoring contexts canonically skip JSONB denormalization."""
        tenant = _make_tenant(db_session)
        # Synthesize a case_merchandise row that should NOT be touched.
        # (Use a different case linked to a different funeral_home tenant.)
        fh_tenant = _make_tenant(db_session, vertical="funeral_home")
        case, merchandise = _make_funeral_case_with_merchandise(
            db_session, fh_tenant
        )
        original_personalization = merchandise.vault_personalization

        # Mfg tenant opens instance linked to sales_order (canonical
        # Q3 pairing) — has no canonical denormalization target.
        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        state = _empty_canvas_state("burial_vault_personalization_studio")
        state["nameplate_text"] = "Should not touch case_merchandise"
        commit_canvas_state(
            db_session, instance_id=instance.id, canvas_state=state
        )

        db_session.refresh(merchandise)
        # Untouched canonical: case_merchandise belongs to FH tenant, not
        # mfg tenant; mfg authoring_context canonically skips denormalization.
        assert merchandise.vault_personalization == original_personalization


# ─────────────────────────────────────────────────────────────────────
# 8. Lifecycle state transitions — commit_instance + abandon_instance
# ─────────────────────────────────────────────────────────────────────


class TestLifecycleTransitions:
    def test_commit_instance_active_to_committed(self, db_session, fake_r2):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
            opened_by_user_id=user.id,
        )
        result = commit_instance(
            db_session, instance_id=instance.id, committed_by_user_id=user.id
        )
        assert result.lifecycle_state == "committed"
        assert result.committed_at is not None
        assert result.committed_by_user_id == user.id

    def test_abandon_instance_active_to_abandoned(self, db_session, fake_r2):
        tenant = _make_tenant(db_session)
        user = _make_user(db_session, tenant)
        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
            opened_by_user_id=user.id,
        )
        result = abandon_instance(
            db_session, instance_id=instance.id, abandoned_by_user_id=user.id
        )
        assert result.lifecycle_state == "abandoned"
        assert result.abandoned_at is not None
        assert result.abandoned_by_user_id == user.id

    def test_commit_canvas_state_rejected_on_committed_instance(
        self, db_session, fake_r2
    ):
        tenant = _make_tenant(db_session)
        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        commit_instance(db_session, instance_id=instance.id)

        state = _empty_canvas_state("burial_vault_personalization_studio")
        with pytest.raises(PersonalizationStudioInvalidTransition):
            commit_canvas_state(
                db_session, instance_id=instance.id, canvas_state=state
            )

    def test_double_commit_rejected(self, db_session, fake_r2):
        tenant = _make_tenant(db_session)
        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        commit_instance(db_session, instance_id=instance.id)
        with pytest.raises(PersonalizationStudioInvalidTransition):
            commit_instance(db_session, instance_id=instance.id)

    def test_abandon_after_commit_rejected(self, db_session, fake_r2):
        tenant = _make_tenant(db_session)
        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        commit_instance(db_session, instance_id=instance.id)
        with pytest.raises(PersonalizationStudioInvalidTransition):
            abandon_instance(db_session, instance_id=instance.id)


# ─────────────────────────────────────────────────────────────────────
# 9. Lookup helpers — tenant-scoped + canonical query patterns
# ─────────────────────────────────────────────────────────────────────


class TestLookupHelpers:
    def test_get_instance_tenant_scoped(self, db_session, fake_r2):
        tenant_a = _make_tenant(db_session, name_prefix="A")
        tenant_b = _make_tenant(db_session, name_prefix="B")
        instance = open_instance(
            db_session,
            company_id=tenant_a.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        # Owner can fetch.
        fetched = get_instance(
            db_session, instance_id=instance.id, company_id=tenant_a.id
        )
        assert fetched.id == instance.id

        # Cross-tenant fetch returns canonical 404.
        with pytest.raises(PersonalizationStudioNotFound):
            get_instance(
                db_session, instance_id=instance.id, company_id=tenant_b.id
            )

    def test_list_instances_for_linked_entity(self, db_session, fake_r2):
        tenant = _make_tenant(db_session)
        order_id = str(uuid.uuid4())

        i1 = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=order_id,
        )
        i2 = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),  # different order
        )

        results = list_instances_for_linked_entity(
            db_session,
            company_id=tenant.id,
            linked_entity_type="sales_order",
            linked_entity_id=order_id,
        )
        ids = {r.id for r in results}
        assert i1.id in ids
        assert i2.id not in ids


# ─────────────────────────────────────────────────────────────────────
# 10. Canonical-pattern-establisher discipline tests
#     (verify Phase 1A patterns Step 2 will inherit)
# ─────────────────────────────────────────────────────────────────────


class TestCanonicalPatternEstablisherDiscipline:
    """Phase 1A canonical-pattern-establisher: verify the patterns Step 2
    (Urn Vault Personalization Studio) inherits via discriminator
    differentiation are canonically encoded at Phase 1A boundary."""

    def test_template_type_constant_is_extension_point(self):
        """Step 2 extended CANONICAL_TEMPLATE_TYPES via r80 migration +
        entity model extension. The constant is the extension point for
        new Generation Focus templates per single-entity-with-discriminator
        meta-pattern §3.26.11.12.20. Post-Step-2: Burial + Urn Vault
        Personalization Studio templates registered.
        """
        assert CANONICAL_TEMPLATE_TYPES == (
            "burial_vault_personalization_studio",
            "urn_vault_personalization_studio",
        )

    def test_document_type_for_template_canonical_mapping(self):
        """1:1 mapping between template_type and Document.document_type
        per D-9 substrate. Step 2 extended this dict via Phase 2A
        substrate-consumption-follower discipline."""
        assert DOCUMENT_TYPE_FOR_TEMPLATE == {
            "burial_vault_personalization_studio": "burial_vault_personalization_studio",
            "urn_vault_personalization_studio": "urn_vault_personalization_studio",
        }

    def test_authoring_context_3_values_are_canonical_and_template_independent(
        self,
    ):
        """Authoring_context canonical 3-value enumeration is canonically shared
        across all Generation Focus templates per Q3 baked at §3.26.11.12.19.3.
        Step 2 inherits the same 3 canonical values."""
        assert len(CANONICAL_AUTHORING_CONTEXTS) == 3

    def test_lifecycle_state_4_values_are_canonical_and_template_independent(
        self,
    ):
        """Lifecycle_state canonical 4-state enumeration is canonically shared
        across all Generation Focus templates. Step 2 + future templates
        inherit per single-entity-with-discriminator §3.26.11.12.20."""
        assert len(CANONICAL_LIFECYCLE_STATES) == 4

    def test_canvas_state_template_type_dispatch_open_for_step2(self):
        """``_empty_canvas_state`` dispatches per template_type. Step 2
        extended the factory with urn_vault_personalization_studio shape
        per Phase 2A substrate-consumption-follower. Unknown templates
        raise canonical error preserving extension-point discipline.
        """
        # Phase 1A pattern-establisher value succeeds.
        burial = _empty_canvas_state("burial_vault_personalization_studio")
        assert burial["template_type"] == "burial_vault_personalization_studio"
        # Step 2 substrate-consumption-follower value succeeds.
        urn = _empty_canvas_state("urn_vault_personalization_studio")
        assert urn["template_type"] == "urn_vault_personalization_studio"
        # Unknown template raises — extension-point discipline preserved
        # for future Step 3+.
        with pytest.raises(PersonalizationStudioError):
            _empty_canvas_state("future_unknown_template")


# ─────────────────────────────────────────────────────────────────────
# 11. Anti-pattern guards explicit at Phase 1A canonical-pattern-establisher boundary
# ─────────────────────────────────────────────────────────────────────


class TestAntiPatternGuards:
    """Canonical anti-pattern guards verified at Phase 1A boundary.

    Per build prompt:
    - §2.4.4 Anti-pattern 8 (vertical-specific code creep)
    - §2.4.4 Anti-pattern 9 (primitive proliferation under composition pressure)
    - §3.26.11.12.16 Anti-pattern 11 (UI-coupled Generation Focus design rejected)
    """

    def test_no_vertical_specific_columns_in_entity_model(self, db_session):
        """§2.4.4 Anti-pattern 8: entity model carries canonical Generation Focus
        substrate columns ONLY — no FH-vertical-specific or Mfg-vertical-specific
        columns. Vertical-specific behavior canonicalized via authoring_context
        discriminator dispatch at service layer."""
        cols = {
            c["name"]
            for c in inspect(db_session.bind).get_columns(
                "generation_focus_instances"
            )
        }
        # Canonical anti-pattern guards:
        forbidden_vertical_specific = {
            # FH-vertical-specific columns would violate Anti-pattern 8.
            "fh_case_id",  # use polymorphic linked_entity_id instead
            "casket_id",
            "monument_id",
            # Mfg-vertical-specific columns would violate Anti-pattern 8.
            "sales_order_id",  # use polymorphic linked_entity_id instead
            "vault_product_id",
        }
        leaked = cols & forbidden_vertical_specific
        assert not leaked, (
            f"Anti-pattern 8 violated: vertical-specific columns leaked into "
            f"canonical Generation Focus instance entity: {leaked}"
        )

    def test_no_ui_state_columns_in_entity_model(self, db_session):
        """§3.26.11.12.16 Anti-pattern 11: entity model output schema
        independent from interactive UI. Canvas state lives in canonical
        Document substrate (D-9), NOT on the entity row.
        """
        cols = {
            c["name"]
            for c in inspect(db_session.bind).get_columns(
                "generation_focus_instances"
            )
        }
        forbidden_ui_state = {
            # UI-coupled state columns would violate Anti-pattern 11.
            "canvas_layout",
            "canvas_state",
            "current_canvas_json",
            "render_state",
            "interactive_state",
        }
        leaked = cols & forbidden_ui_state
        assert not leaked, (
            f"Anti-pattern 11 violated: UI-coupled state columns leaked into "
            f"canonical Generation Focus instance entity: {leaked}"
        )

    def test_canvas_state_lives_in_document_substrate_not_entity(
        self, db_session, fake_r2
    ):
        """§3.26.11.12.5 substrate-consumption canonical: canvas state lives
        canonically in Document substrate (DocumentVersion.storage_key →
        canonical R2 JSON blob), NOT on the GenerationFocusInstance entity row."""
        tenant = _make_tenant(db_session)
        instance = open_instance(
            db_session,
            company_id=tenant.id,
            template_type="burial_vault_personalization_studio",
            authoring_context="manufacturer_without_family",
            linked_entity_id=str(uuid.uuid4()),
        )
        state = _empty_canvas_state("burial_vault_personalization_studio")
        state["nameplate_text"] = "Substrate Test"
        commit_canvas_state(
            db_session, instance_id=instance.id, canvas_state=state
        )

        # Canvas state lives in R2 substrate via DocumentVersion canonical.
        version = (
            db_session.query(DocumentVersion)
            .filter(
                DocumentVersion.document_id == instance.document_id,
                DocumentVersion.is_current == True,  # noqa: E712
            )
            .first()
        )
        assert version is not None
        assert version.storage_key in fake_r2
        canvas_blob = json.loads(fake_r2[version.storage_key].decode("utf-8"))
        assert canvas_blob["nameplate_text"] == "Substrate Test"

        # Entity row carries canonical lifecycle metadata only — NO canvas
        # state JSON column on the instance itself per Anti-pattern 11.
        instance_dict = {
            c.name: getattr(instance, c.name)
            for c in instance.__table__.columns
        }
        assert "canvas_state" not in instance_dict
        assert "canvas_layout" not in instance_dict
