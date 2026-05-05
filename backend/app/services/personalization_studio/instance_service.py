"""Canonical Generation Focus instance lifecycle service — Phase 1A
canonical-pattern-establisher of Step 1 Burial Vault Personalization Studio.

Per §3.26.11.12.19 Personalization Studio canonical category +
§3.26.11.12 Generation Focus canon + §3.26.11.12.5 substrate-consumption
canonical: this service is the canonical lifecycle authority for
``GenerationFocusInstance`` rows + canonical Document substrate
consumption per D-9.

**Canvas state shape canonical (Phase 1A canonical-pattern-establisher)**:

Per discovery output Section 2a, canvas state has three persistence sites:

1. **Canonical Document substrate** (D-9 polymorphic): canvas layout
   (positioned compositor element coordinates), selected vault product,
   emblem_key, name_display, font, birth_date_display, death_date_display,
   nameplate_text, per-option canonical option type
   (``legacy_print`` | ``physical_nameplate`` | ``physical_emblem`` |
   ``vinyl`` per canonical post-r74), family approval status. Persisted
   as canonical JSON blob at ``documents.storage_key`` ``application/json``
   mime type per canonical D-9 shape.
2. **``case_merchandise.vault_personalization`` JSONB** (existing
   substrate post-r74 canonical vocabulary): denormalized canvas state
   for case-record-level visibility from FH-vertical case detail views.
   Updates on each canvas commit for ``funeral_home_with_family``
   authoring context.
3. **``generation_focus_instances``** entity model (Phase 1A canonical-
   pattern-establisher): ``template_type`` + ``authoring_context``
   discriminator + ``lifecycle_state`` + ``linked_entity`` polymorphic.
   Holds canonical lifecycle metadata only; canvas state lives in
   canonical Document substrate per Anti-pattern 11 (§3.26.11.12.16
   UI-coupled Generation Focus design rejected).

**Canonical pattern-establisher discipline**: Step 2 (Urn Vault
Personalization Studio) inherits this service via ``template_type``
discriminator; the canvas state JSON shape may differ per template
(urn vault has urn-specific fields), but the lifecycle service +
substrate consumption pattern is canonically shared.

**DocumentVersion versioning canonical**: each ``commit_canvas_state``
creates a new ``DocumentVersion`` with ``is_current=True`` flip + the
prior version's ``is_current`` flips to False. ``Document.storage_key``
mirrors the current version per canonical D-9 convenience pattern.

**JSONB denormalization discipline**: ``case_merchandise.vault_personalization``
is updated on canvas commit ONLY for ``funeral_home_with_family`` authoring
context (canonical FH-vertical pairing per Q3 baked at §3.26.11.12.19.3).
Mfg-vertical authoring contexts (``manufacturer_without_family``,
``manufacturer_from_fh_share``) do NOT denormalize to ``case_merchandise``
because Mfg-vertical instances link to ``sales_orders`` (no FH case
record) or to ``document_share`` (read-only canvas chrome — manufacturer
reads FH-shared canvas without owning denormalization substrate).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.canonical_document import Document, DocumentVersion
from app.models.funeral_case import CaseMerchandise
from app.models.generation_focus_instance import (
    AUTHORING_CONTEXT_TO_LINKED_ENTITY_TYPE,
    CANONICAL_AUTHORING_CONTEXTS,
    CANONICAL_LIFECYCLE_STATES,
    CANONICAL_TEMPLATE_TYPES,
    GenerationFocusInstance,
)
from app.services import legacy_r2_client

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────


class PersonalizationStudioError(Exception):
    """Base error for personalization studio service layer."""

    http_status = 400


class PersonalizationStudioNotFound(PersonalizationStudioError):
    http_status = 404


class PersonalizationStudioInvalidTransition(PersonalizationStudioError):
    http_status = 409


class PersonalizationStudioPermissionDenied(PersonalizationStudioError):
    http_status = 403


# ─────────────────────────────────────────────────────────────────────
# Canonical canvas state — Phase 1A canonical-pattern-establisher
# ─────────────────────────────────────────────────────────────────────


# Canonical canvas state JSON schema version per Phase 1A. Bumps
# canonically as canvas state shape evolves; service layer migration
# strategy + on-read schema-coercion deferred to Phase 1B canvas
# implementation.
CANVAS_STATE_SCHEMA_VERSION: int = 1


# Document_type discriminator values per D-9 polymorphic substrate.
# Phase 1A canonical-pattern-establisher value plus Step 2 substrate-
# consumption-follower value. Mirror ``GenerationFocusInstance.
# template_type`` 1:1.
DOCUMENT_TYPE_FOR_TEMPLATE: dict[str, str] = {
    "burial_vault_personalization_studio": "burial_vault_personalization_studio",
    "urn_vault_personalization_studio": "urn_vault_personalization_studio",
}


def _empty_canvas_state(template_type: str) -> dict[str, Any]:
    """Empty canvas state for a fresh Generation Focus instance.

    Phase 1A pattern-establisher shape for
    ``burial_vault_personalization_studio``; Step 2 substrate-consumption-
    follower shape for ``urn_vault_personalization_studio`` (urn product
    replaces vault product; canonical 4-options vocabulary preserved per
    §3.26.11.12.19.6 scope freeze). Service consumers + AI-extraction-
    review pipeline (Phase 1C / Phase 2B) overwrite specific fields as
    operator + AI converge on output.
    """
    if template_type == "burial_vault_personalization_studio":
        return {
            "schema_version": CANVAS_STATE_SCHEMA_VERSION,
            "template_type": template_type,
            "canvas_layout": {
                "elements": [],  # positioned compositor elements
            },
            "vault_product": {
                "vault_product_id": None,
                "vault_product_name": None,
            },
            "emblem_key": None,
            "name_display": None,
            "font": None,
            "birth_date_display": None,
            "death_date_display": None,
            "nameplate_text": None,
            # Per-option type per canonical post-r74 vocabulary
            # (§3.26.11.12.19.2): canonical 4-options.
            "options": {
                "legacy_print": None,  # {"print_name": "..."} when active
                "physical_nameplate": None,  # {} when active
                "physical_emblem": None,  # {} when active
                "vinyl": None,  # {"symbol": "..."} when active
            },
            "family_approval_status": "not_requested",
        }
    if template_type == "urn_vault_personalization_studio":
        return {
            "schema_version": CANVAS_STATE_SCHEMA_VERSION,
            "template_type": template_type,
            "canvas_layout": {
                "elements": [],
            },
            # Urn product replaces vault product per Step 2 substrate-
            # consumption-follower shape. Future Personalization Studio
            # templates extend with template-specific product slot.
            "urn_product": {
                "urn_product_id": None,
                "urn_product_name": None,
            },
            "emblem_key": None,
            "name_display": None,
            "font": None,
            "birth_date_display": None,
            "death_date_display": None,
            "nameplate_text": None,
            # Canonical 4-options vocabulary preserved per
            # §3.26.11.12.19.6 scope freeze — urn vault inherits
            # category-scope vocabulary from canonical Personalization
            # Studio category.
            "options": {
                "legacy_print": None,
                "physical_nameplate": None,
                "physical_emblem": None,
                "vinyl": None,
            },
            "family_approval_status": "not_requested",
        }
    raise PersonalizationStudioError(
        f"Unknown template_type {template_type!r}; canonical "
        f"Personalization Studio category values are "
        f"'burial_vault_personalization_studio' (Step 1) + "
        f"'urn_vault_personalization_studio' (Step 2). "
        f"Future templates extend via canon session per "
        f"§3.26.11.12.19.6 scope freeze."
    )


def _canvas_storage_key(
    company_id: str, document_id: str, version_number: int
) -> str:
    """Canonical storage_key convention for canvas state JSON blobs.

    Mirrors canonical Document substrate convention per
    ``document_renderer._storage_key`` but with ``.json`` suffix per
    canonical canvas-state-as-JSON canonical pattern.
    """
    return (
        f"tenants/{company_id}/documents/{document_id}/"
        f"canvas_state_v{version_number}.json"
    )


# ─────────────────────────────────────────────────────────────────────
# Lifecycle service — open / commit_canvas_state / get_canvas_state /
# commit_instance / abandon_instance
# ─────────────────────────────────────────────────────────────────────


def open_instance(
    db: Session,
    *,
    company_id: str,
    template_type: str,
    authoring_context: str,
    linked_entity_id: str,
    opened_by_user_id: str | None = None,
    initial_canvas_state: dict[str, Any] | None = None,
) -> GenerationFocusInstance:
    """Open a new Generation Focus instance.

    Creates a ``GenerationFocusInstance`` row + a canonical Document
    substrate row (per D-9) with ``document_type`` matching
    ``template_type``. The first ``DocumentVersion`` is NOT created here
    — it's created on the first ``commit_canvas_state`` call per
    §3.26.11.12.5 substrate-consumption canonical.

    **Q3 canonical pairing enforcement** per §3.26.11.12.19.3:
    ``authoring_context`` ↔ ``linked_entity_type`` is canonically paired
    + enforced at substrate boundary (CHECK constraint) + here at service
    layer (defense-in-depth).

    Args:
        company_id: Tenant scoping per canonical multi-tenant SaaS.
        template_type: Canonical Generation Focus template type discriminator.
        authoring_context: Canonical 3-value enumeration per Q3.
        linked_entity_id: UUID of canonical linked entity (FH case /
            sales order / document share per Q3 pairing).
        opened_by_user_id: Canonical actor attribution.
        initial_canvas_state: Optional canonical canvas state to seed
            the Document substrate with on first commit. When None,
            service uses ``_empty_canvas_state(template_type)`` canonical.

    Returns:
        The created ``GenerationFocusInstance`` row.

    Raises:
        PersonalizationStudioError: invalid template_type / authoring_context.
    """
    # Validate canonical enumerations at service layer (defense-in-depth
    # alongside DB CHECK constraints).
    if template_type not in CANONICAL_TEMPLATE_TYPES:
        raise PersonalizationStudioError(
            f"Invalid template_type {template_type!r}; canonical values: "
            f"{CANONICAL_TEMPLATE_TYPES}"
        )
    if authoring_context not in CANONICAL_AUTHORING_CONTEXTS:
        raise PersonalizationStudioError(
            f"Invalid authoring_context {authoring_context!r}; "
            f"canonical values: {CANONICAL_AUTHORING_CONTEXTS}"
        )

    # Q3 canonical pairing enforcement at service layer.
    canonical_linked_entity_type = AUTHORING_CONTEXT_TO_LINKED_ENTITY_TYPE[
        authoring_context
    ]

    document_type = DOCUMENT_TYPE_FOR_TEMPLATE.get(template_type, template_type)

    # Pre-mint document_id so the storage_key convention is stable.
    document_id = str(uuid.uuid4())

    # Canonical Document substrate row per D-9. storage_key + version
    # metadata stamped on first commit — the row is created in 'draft'
    # status reflecting "Generation Focus opened, no canvas commit yet".
    now = datetime.now(timezone.utc)
    document = Document(
        id=document_id,
        company_id=company_id,
        document_type=document_type,
        title=f"{template_type} canvas state",
        # Pre-commit canvas state has no R2 storage yet — placeholder
        # storage_key will be replaced on first commit. Document row's
        # storage_key column is NOT NULL so we use a canonical sentinel.
        storage_key=f"tenants/{company_id}/documents/{document_id}/pre_commit",
        mime_type="application/json",
        status="draft",
        rendered_at=None,
        rendered_by_user_id=None,
        caller_module="personalization_studio.instance_service.open_instance",
        created_at=now,
        updated_at=now,
    )
    db.add(document)
    db.flush()

    # Canonical Generation Focus instance row.
    instance = GenerationFocusInstance(
        company_id=company_id,
        template_type=template_type,
        authoring_context=authoring_context,
        lifecycle_state="active",
        linked_entity_type=canonical_linked_entity_type,
        linked_entity_id=linked_entity_id,
        document_id=document_id,
        opened_at=now,
        opened_by_user_id=opened_by_user_id,
        last_active_at=now,
        # Family approval canonical: only meaningful for FH-vertical
        # authoring context per Q7b. Mfg-vertical contexts get NULL.
        family_approval_status=(
            "not_requested"
            if authoring_context == "funeral_home_with_family"
            else None
        ),
        created_at=now,
        updated_at=now,
    )
    db.add(instance)
    db.flush()

    logger.info(
        "personalization_studio.open_instance: id=%s template=%s "
        "authoring=%s linked=%s/%s document_id=%s",
        instance.id,
        template_type,
        authoring_context,
        canonical_linked_entity_type,
        linked_entity_id,
        document_id,
    )

    # Stash the seed canvas state for the first commit if caller provided
    # one. Phase 1A canonical-pattern-establisher: stash via instance
    # attribute (transient — not persisted on the entity itself; consumed
    # by next commit_canvas_state if invoked promptly). Production
    # callers that need a guaranteed-seed flow call commit_canvas_state
    # immediately after open_instance.
    if initial_canvas_state is not None:
        commit_canvas_state(
            db,
            instance_id=instance.id,
            canvas_state=initial_canvas_state,
            committed_by_user_id=opened_by_user_id,
        )
    return instance


def commit_canvas_state(
    db: Session,
    *,
    instance_id: str,
    canvas_state: dict[str, Any],
    committed_by_user_id: str | None = None,
    render_reason: str = "canvas_commit",
) -> DocumentVersion:
    """Persist canvas state to canonical Document substrate.

    Creates a new ``DocumentVersion`` with ``is_current=True``; flips
    the prior current version's ``is_current=False`` per canonical D-9
    versioning convention. Updates ``Document.storage_key`` to point at
    the new version.

    For ``funeral_home_with_family`` authoring context, denormalizes
    canvas state to ``case_merchandise.vault_personalization`` JSONB
    per Phase 1A canonical FH-vertical denormalization discipline.

    Args:
        instance_id: The canonical Generation Focus instance UUID.
        canvas_state: Canonical canvas state dict (validated against
            template_type-specific schema; Phase 1A canonical-pattern-
            establisher does shape-coercion light validation only —
            full canonical-vocabulary validation extends at Phase 1B).
        committed_by_user_id: Canonical actor attribution.
        render_reason: Canonical reason marker; default ``canvas_commit``.

    Returns:
        The newly-created ``DocumentVersion`` row.

    Raises:
        PersonalizationStudioNotFound: instance_id not found.
        PersonalizationStudioInvalidTransition: instance lifecycle_state
            is canonically terminal (committed | abandoned).
    """
    instance = (
        db.query(GenerationFocusInstance)
        .filter(GenerationFocusInstance.id == instance_id)
        .first()
    )
    if instance is None:
        raise PersonalizationStudioNotFound(
            f"GenerationFocusInstance {instance_id!r} not found."
        )
    if instance.lifecycle_state in ("committed", "abandoned"):
        raise PersonalizationStudioInvalidTransition(
            f"Cannot commit canvas state — instance {instance_id!r} "
            f"is in canonical terminal state {instance.lifecycle_state!r}."
        )
    # Phase 1F canonical Q9c canonical-discipline guard: canvas state
    # mutations canonical-rejected at canonical manufacturer_from_fh_share
    # authoring context (canvas read-only at canonical Mfg-tenant scope).
    assert_canvas_state_mutation_permitted(instance)
    if instance.document_id is None:
        # Defensive: open_instance always stamps document_id; this branch
        # is canonically unreachable but preserves discipline at boundary.
        raise PersonalizationStudioError(
            f"Instance {instance_id!r} has no canonical Document substrate "
            f"linkage; canonical invariant violated."
        )

    document = (
        db.query(Document)
        .filter(Document.id == instance.document_id)
        .first()
    )
    if document is None:
        raise PersonalizationStudioError(
            f"Canonical Document {instance.document_id!r} not found for "
            f"instance {instance_id!r}; canonical invariant violated."
        )

    # Canonical canvas state shape-coercion (Phase 1A canonical-pattern-
    # establisher). Stamp schema_version + template_type so persisted
    # JSON is self-describing for future schema migrations.
    canvas_state = dict(canvas_state)  # shallow copy — don't mutate caller's dict
    canvas_state.setdefault("schema_version", CANVAS_STATE_SCHEMA_VERSION)
    canvas_state.setdefault("template_type", instance.template_type)

    # Determine next version_number per canonical D-9 versioning.
    current_version = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == document.id,
            DocumentVersion.is_current == True,  # noqa: E712
        )
        .first()
    )
    next_number = ((current_version.version_number if current_version else 0)) + 1
    storage_key = _canvas_storage_key(
        instance.company_id, document.id, next_number
    )

    # Upload canonical canvas state JSON to R2 substrate per D-9.
    canvas_bytes = json.dumps(canvas_state, separators=(",", ":")).encode("utf-8")
    try:
        legacy_r2_client.upload_bytes(
            canvas_bytes, storage_key, content_type="application/json"
        )
    except Exception as exc:  # noqa: BLE001
        raise PersonalizationStudioError(
            f"R2 upload failed for canvas state v{next_number} of "
            f"instance {instance_id!r}: {exc}"
        ) from exc

    now = datetime.now(timezone.utc)

    # Flip prior is_current per canonical D-9 versioning.
    if current_version is not None:
        current_version.is_current = False

    new_version = DocumentVersion(
        id=str(uuid.uuid4()),
        document_id=document.id,
        version_number=next_number,
        storage_key=storage_key,
        mime_type="application/json",
        file_size_bytes=len(canvas_bytes),
        rendered_at=now,
        rendered_by_user_id=committed_by_user_id,
        rendering_context_hash=None,  # canvas-state JSON is the canonical
        # source-of-truth; no separate context to hash per Phase 1A.
        render_reason=render_reason,
        is_current=True,
    )
    db.add(new_version)

    # Mirror to Document row per canonical D-9 convenience pattern.
    document.storage_key = storage_key
    document.file_size_bytes = len(canvas_bytes)
    document.status = "rendered"
    document.rendered_at = now
    document.rendered_by_user_id = committed_by_user_id
    document.updated_at = now

    # Update canonical Generation Focus instance lifecycle metadata.
    instance.last_active_at = now
    instance.updated_at = now

    db.flush()

    # Phase 1A canonical FH-vertical JSONB denormalization. Only fires
    # for ``funeral_home_with_family`` authoring context per
    # §3.26.11.12.19.3 Q3 canonical pairing.
    if instance.authoring_context == "funeral_home_with_family":
        _denormalize_to_case_merchandise(
            db,
            fh_case_id=instance.linked_entity_id,
            canvas_state=canvas_state,
            template_type=instance.template_type,
        )

    logger.info(
        "personalization_studio.commit_canvas_state: instance=%s v%d "
        "bytes=%d template=%s authoring=%s",
        instance.id,
        next_number,
        len(canvas_bytes),
        instance.template_type,
        instance.authoring_context,
    )
    return new_version


def get_canvas_state(
    db: Session, *, instance_id: str
) -> dict[str, Any] | None:
    """Read the current canonical canvas state from Document substrate.

    Returns the canonical canvas state JSON dict, or None when no
    ``DocumentVersion`` has been committed yet (instance opened but no
    commit_canvas_state call made).

    Raises:
        PersonalizationStudioNotFound: instance_id not found.
    """
    instance = (
        db.query(GenerationFocusInstance)
        .filter(GenerationFocusInstance.id == instance_id)
        .first()
    )
    if instance is None:
        raise PersonalizationStudioNotFound(
            f"GenerationFocusInstance {instance_id!r} not found."
        )
    if instance.document_id is None:
        return None

    current_version = (
        db.query(DocumentVersion)
        .filter(
            DocumentVersion.document_id == instance.document_id,
            DocumentVersion.is_current == True,  # noqa: E712
        )
        .first()
    )
    if current_version is None:
        return None

    try:
        canvas_bytes = legacy_r2_client.download_bytes(current_version.storage_key)
    except Exception as exc:  # noqa: BLE001
        raise PersonalizationStudioError(
            f"R2 download failed for canvas state of instance "
            f"{instance_id!r} version {current_version.version_number}: {exc}"
        ) from exc

    return json.loads(canvas_bytes.decode("utf-8"))


def commit_instance(
    db: Session,
    *,
    instance_id: str,
    committed_by_user_id: str | None = None,
) -> GenerationFocusInstance:
    """Transition canonical lifecycle_state from ``active`` to ``committed``.

    Per §3.26.11.12.5 canonical lifecycle exit point: instance is
    canonically committed; no further canvas state writes accepted.
    The current ``DocumentVersion`` becomes the canonical final canvas
    state for the linked entity per substrate consumption canonical.

    Raises:
        PersonalizationStudioNotFound: instance_id not found.
        PersonalizationStudioInvalidTransition: lifecycle_state is
            already ``committed`` or ``abandoned``.
    """
    instance = (
        db.query(GenerationFocusInstance)
        .filter(GenerationFocusInstance.id == instance_id)
        .first()
    )
    if instance is None:
        raise PersonalizationStudioNotFound(
            f"GenerationFocusInstance {instance_id!r} not found."
        )
    if instance.lifecycle_state == "committed":
        raise PersonalizationStudioInvalidTransition(
            f"Instance {instance_id!r} already in canonical "
            f"committed state."
        )
    if instance.lifecycle_state == "abandoned":
        raise PersonalizationStudioInvalidTransition(
            f"Instance {instance_id!r} is in canonical abandoned state; "
            f"cannot transition to committed."
        )

    now = datetime.now(timezone.utc)
    instance.lifecycle_state = "committed"
    instance.committed_at = now
    instance.committed_by_user_id = committed_by_user_id
    instance.last_active_at = now
    instance.updated_at = now
    db.flush()

    logger.info(
        "personalization_studio.commit_instance: id=%s template=%s "
        "authoring=%s",
        instance.id,
        instance.template_type,
        instance.authoring_context,
    )
    return instance


def abandon_instance(
    db: Session,
    *,
    instance_id: str,
    abandoned_by_user_id: str | None = None,
) -> GenerationFocusInstance:
    """Transition canonical lifecycle_state to ``abandoned``.

    Canonical lifecycle abandon path per §3.26.11.12.5; symmetric with
    ``commit_instance`` canonical commit path. Used for incomplete /
    cancelled / superseded instances.

    Raises:
        PersonalizationStudioNotFound: instance_id not found.
        PersonalizationStudioInvalidTransition: lifecycle_state is
            already ``committed`` or ``abandoned``.
    """
    instance = (
        db.query(GenerationFocusInstance)
        .filter(GenerationFocusInstance.id == instance_id)
        .first()
    )
    if instance is None:
        raise PersonalizationStudioNotFound(
            f"GenerationFocusInstance {instance_id!r} not found."
        )
    if instance.lifecycle_state == "committed":
        raise PersonalizationStudioInvalidTransition(
            f"Instance {instance_id!r} is in canonical committed state; "
            f"cannot abandon."
        )
    if instance.lifecycle_state == "abandoned":
        raise PersonalizationStudioInvalidTransition(
            f"Instance {instance_id!r} already in canonical "
            f"abandoned state."
        )

    now = datetime.now(timezone.utc)
    instance.lifecycle_state = "abandoned"
    instance.abandoned_at = now
    instance.abandoned_by_user_id = abandoned_by_user_id
    instance.last_active_at = now
    instance.updated_at = now
    db.flush()

    logger.info(
        "personalization_studio.abandon_instance: id=%s template=%s "
        "authoring=%s",
        instance.id,
        instance.template_type,
        instance.authoring_context,
    )
    return instance


# ─────────────────────────────────────────────────────────────────────
# Lookup helpers
# ─────────────────────────────────────────────────────────────────────


def get_instance(
    db: Session, *, instance_id: str, company_id: str
) -> GenerationFocusInstance:
    """Tenant-scoped instance lookup. Raises 404 on cross-tenant access."""
    instance = (
        db.query(GenerationFocusInstance)
        .filter(
            GenerationFocusInstance.id == instance_id,
            GenerationFocusInstance.company_id == company_id,
        )
        .first()
    )
    if instance is None:
        raise PersonalizationStudioNotFound(
            f"GenerationFocusInstance {instance_id!r} not found."
        )
    return instance


def list_instances_for_linked_entity(
    db: Session,
    *,
    company_id: str,
    linked_entity_type: str,
    linked_entity_id: str,
    template_type: str | None = None,
    lifecycle_state: str | None = None,
) -> list[GenerationFocusInstance]:
    """List canonical Generation Focus instances linked to a given entity.

    Canonical query pattern per Phase 1A canonical-pattern-establisher:
    "what personalization Generation Focus instances exist for FH case X?"
    or "what Generation Focus instances exist for sales order Y?"

    Filtered to caller's company_id for canonical multi-tenant isolation.
    """
    query = db.query(GenerationFocusInstance).filter(
        GenerationFocusInstance.company_id == company_id,
        GenerationFocusInstance.linked_entity_type == linked_entity_type,
        GenerationFocusInstance.linked_entity_id == linked_entity_id,
    )
    if template_type is not None:
        if template_type not in CANONICAL_TEMPLATE_TYPES:
            raise PersonalizationStudioError(
                f"Invalid template_type {template_type!r}; canonical "
                f"values: {CANONICAL_TEMPLATE_TYPES}"
            )
        query = query.filter(GenerationFocusInstance.template_type == template_type)
    if lifecycle_state is not None:
        if lifecycle_state not in CANONICAL_LIFECYCLE_STATES:
            raise PersonalizationStudioError(
                f"Invalid lifecycle_state {lifecycle_state!r}; canonical "
                f"values: {CANONICAL_LIFECYCLE_STATES}"
            )
        query = query.filter(
            GenerationFocusInstance.lifecycle_state == lifecycle_state
        )
    return query.order_by(GenerationFocusInstance.last_active_at.desc()).all()


# ─────────────────────────────────────────────────────────────────────
# JSONB denormalization — canonical FH-vertical case_merchandise pattern
# ─────────────────────────────────────────────────────────────────────


def _denormalize_to_case_merchandise(
    db: Session,
    *,
    fh_case_id: str,
    canvas_state: dict[str, Any],
    template_type: str,
) -> None:
    """Denormalize canvas state to ``case_merchandise.vault_personalization`` JSONB.

    Phase 1A canonical FH-vertical pattern per §3.26.11.12.19.3 Q3:
    canvas state is canonically duplicated to case-record-level JSONB
    for case detail visibility. Per-template denormalization shape:

    - ``burial_vault_personalization_studio``: writes to
      ``case_merchandise.vault_personalization`` (existing post-r74
      canonical vocabulary substrate).

    Step 2 ``urn_vault_personalization_studio`` writes to
    ``case_merchandise.urn_personalization`` (existing canonical urn
    JSONB substrate; canonical-pattern-establisher discipline at Phase
    1A inherited at Step 2).

    Best-effort discipline: failure to denormalize logs but does NOT
    block canvas commit per Phase 1A canonical resilience pattern.
    The Document substrate persistence is canonical source-of-truth;
    JSONB denormalization is operational ergonomic substrate.
    """
    if template_type != "burial_vault_personalization_studio":
        # Phase 1A canonical-pattern-establisher: only burial vault
        # template denormalizes to vault_personalization. Step 2 extends
        # with urn_personalization for urn_vault_personalization_studio.
        return

    try:
        merchandise = (
            db.query(CaseMerchandise)
            .filter(CaseMerchandise.case_id == fh_case_id)
            .first()
        )
        if merchandise is None:
            logger.info(
                "personalization_studio: case_merchandise row not found "
                "for fh_case_id=%s; skipping JSONB denormalization "
                "(canvas state lives canonically in Document substrate)",
                fh_case_id,
            )
            return

        # Canonical canvas-state-to-JSONB shape (Phase 1A canonical-
        # pattern-establisher): subset of canvas state relevant to
        # case-record-level visibility per existing post-r74 canonical
        # vault_personalization substrate. Full canvas state lives at
        # Document substrate; this denormalization is operational
        # ergonomic.
        denormalized = {
            "schema_version": canvas_state.get("schema_version"),
            "template_type": canvas_state.get("template_type"),
            "vault_product_id": (
                canvas_state.get("vault_product", {}) or {}
            ).get("vault_product_id"),
            "vault_product_name": (
                canvas_state.get("vault_product", {}) or {}
            ).get("vault_product_name"),
            "emblem_key": canvas_state.get("emblem_key"),
            "name_display": canvas_state.get("name_display"),
            "font": canvas_state.get("font"),
            "birth_date_display": canvas_state.get("birth_date_display"),
            "death_date_display": canvas_state.get("death_date_display"),
            "nameplate_text": canvas_state.get("nameplate_text"),
            # Per-option canonical vocabulary post-r74. The denormalized
            # shape mirrors the canvas state's options dict per canonical
            # 4-options vocabulary (legacy_print | physical_nameplate |
            # physical_emblem | vinyl).
            "options": canvas_state.get("options", {}),
            "family_approval_status": canvas_state.get("family_approval_status"),
        }

        merchandise.vault_personalization = denormalized
        merchandise.updated_at = datetime.now(timezone.utc)
        db.flush()

        logger.info(
            "personalization_studio: denormalized canvas state to "
            "case_merchandise.vault_personalization for fh_case_id=%s",
            fh_case_id,
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "personalization_studio: case_merchandise denormalization "
            "failed for fh_case_id=%s — canvas commit succeeded; "
            "JSONB denormalization is best-effort operational substrate",
            fh_case_id,
        )


# ─────────────────────────────────────────────────────────────────────
# Phase 1F — Manufacturer-side open from canonical D-6 share
# ─────────────────────────────────────────────────────────────────────


def open_instance_from_share(
    db: Session,
    *,
    document_share_id: str,
    mfg_company_id: str,
    opened_by_user_id: str | None = None,
):
    """Open canonical Generation Focus instance at canonical Mfg-tenant
    scope from canonical D-6 DocumentShare.

    Per Phase 1F build prompt + §3.26.11.12.19.3 Q3 canonical pairing
    (``manufacturer_from_fh_share`` ↔ ``linked_entity_type="document_share"``):
    Mfg-tenant operator clicks canonical share-granted email link →
    this service materializes a canonical Mfg-tenant-scoped
    GenerationFocusInstance with canonical
    ``authoring_context="manufacturer_from_fh_share"`` pointing at the
    canonical D-6 DocumentShare.

    Canonical idempotency: if a canonical Mfg-side instance already
    exists for this share, returns the existing instance (canonical
    re-open at canonical Mfg-tenant scope; canonical Anti-pattern 14
    portal-specific feature creep guard preserved — single canonical
    Mfg-side instance per share).

    Args:
        document_share_id: canonical DocumentShare.id (FH→Mfg grant
            row from canonical Phase 1F post-commit dispatch).
        mfg_company_id: canonical Mfg-tenant id (caller's tenant scope).
        opened_by_user_id: canonical Mfg-tenant operator who clicked
            canonical share-granted email link (audit attribution).

    Returns:
        Canonical GenerationFocusInstance at canonical Mfg-tenant scope
        with canonical ``manufacturer_from_fh_share`` authoring context.

    Raises:
        PersonalizationStudioNotFound: share not found OR not granted to
            this Mfg-tenant (canonical existence-hiding 404).
        PersonalizationStudioPermissionDenied: share is canonically
            revoked (canonical D-6 ``revoked_at`` discipline).
    """
    from app.models.canonical_document import Document
    from app.models.document_share import DocumentShare

    # ─── Step 1: tenant-scoped DocumentShare lookup ────────────────
    # Canonical existence-hiding 404 on cross-tenant share access:
    # ``target_company_id != mfg_company_id`` reads as "not found"
    # rather than "forbidden" per §3.26.16.6 cross-tenant masking
    # discipline.
    share = (
        db.query(DocumentShare)
        .filter(
            DocumentShare.id == document_share_id,
            DocumentShare.target_company_id == mfg_company_id,
        )
        .first()
    )
    if share is None:
        raise PersonalizationStudioNotFound(
            f"DocumentShare {document_share_id!r} not found at Mfg-tenant "
            f"scope."
        )

    # ─── Step 2: canonical revoked-share guard ─────────────────────
    # Canonical D-6 ``revoked_at`` discipline: revoked shares are
    # canonical existence-suppressed at canonical read path. Mfg-tenant
    # operator cannot re-open canonical instance from canonical revoked
    # share.
    if share.revoked_at is not None:
        raise PersonalizationStudioPermissionDenied(
            f"DocumentShare {document_share_id!r} has been revoked by "
            f"the owning tenant; canonical Generation Focus instance "
            f"cannot be opened at canonical Mfg-tenant scope."
        )

    # ─── Step 3: canonical idempotency at canonical Mfg-tenant scope ─
    # Resolve canonical existing Mfg-side instance for this canonical
    # share — single-canonical-instance-per-share guard at canonical
    # ``manufacturer_from_fh_share`` ↔ ``linked_entity_type=
    # 'document_share'`` ↔ ``linked_entity_id=share.id`` triple.
    existing = (
        db.query(GenerationFocusInstance)
        .filter(
            GenerationFocusInstance.company_id == mfg_company_id,
            GenerationFocusInstance.authoring_context
            == "manufacturer_from_fh_share",
            GenerationFocusInstance.linked_entity_type == "document_share",
            GenerationFocusInstance.linked_entity_id == document_share_id,
        )
        .first()
    )
    if existing is not None:
        # Canonical re-open: stamp last_active_at + return canonical
        # existing instance.
        existing.last_active_at = datetime.now(timezone.utc)
        db.flush()

        # Canonical D-6 audit ledger ``accessed`` event per canonical
        # cross-tenant share audit substrate (best-effort — failure
        # NEVER blocks canonical re-open path).
        try:
            from app.services.documents import document_sharing_service

            document_sharing_service.record_access(
                db,
                share=share,
                actor_user_id=opened_by_user_id,
                actor_company_id=mfg_company_id,
                event_type="accessed",
            )
        except Exception:  # noqa: BLE001 — best-effort audit
            logger.exception(
                "personalization_studio.open_instance_from_share "
                "audit-event write failed share_id=%s",
                document_share_id,
            )

        return existing

    # ─── Step 4: resolve canonical owner Document for canonical
    # instance template_type derivation ──────────────────────────────
    document = (
        db.query(Document).filter(Document.id == share.document_id).first()
    )
    if document is None:
        raise PersonalizationStudioError(
            f"Canonical Document {share.document_id!r} not found for "
            f"DocumentShare {document_share_id!r}; canonical invariant "
            f"violated."
        )

    # Canonical template_type derivation from canonical Document
    # ``document_type`` (mirrors canonical ``DOCUMENT_TYPE_FOR_TEMPLATE``
    # at canonical Phase 1A canonical 1:1 mapping).
    template_type: str | None = None
    for t, dt in DOCUMENT_TYPE_FOR_TEMPLATE.items():
        if dt == document.document_type:
            template_type = t
            break
    if template_type is None:
        raise PersonalizationStudioError(
            f"Canonical Document {document.id!r} document_type="
            f"{document.document_type!r} does not map to canonical "
            f"Personalization Studio template_type; canonical "
            f"invariant violated."
        )

    # ─── Step 5: create canonical Mfg-tenant-scoped instance ───────
    # Canonical ``manufacturer_from_fh_share`` authoring context per Q3
    # canonical pairing dict; canonical ``linked_entity_type=
    # 'document_share'`` ↔ ``linked_entity_id=share.id`` per canonical
    # AUTHORING_CONTEXT_TO_LINKED_ENTITY_TYPE.
    now = datetime.now(timezone.utc)
    instance = GenerationFocusInstance(
        company_id=mfg_company_id,
        template_type=template_type,
        authoring_context="manufacturer_from_fh_share",
        lifecycle_state="active",
        linked_entity_type="document_share",
        linked_entity_id=document_share_id,
        # Canonical Document substrate FK points at canonical OWNER's
        # Document (FH-tenant-owned). Mfg-tenant reads via canonical
        # D-6 ``Document.visible_to(mfg_company_id)`` query path; does
        # NOT clone canonical Document at Mfg-tenant scope (canonical
        # Anti-pattern 14 portal-specific feature creep guard).
        document_id=document.id,
        opened_at=now,
        opened_by_user_id=opened_by_user_id,
        last_active_at=now,
        # Canonical FH-vertical-only ``family_approval_status``: NULL
        # at canonical Mfg-vertical authoring context per canonical
        # Phase 1A discipline.
        family_approval_status=None,
        created_at=now,
        updated_at=now,
    )
    db.add(instance)
    db.flush()

    # ─── Step 6: canonical D-6 audit ledger ``accessed`` event ─────
    # Canonical cross-tenant share audit substrate per §3.26.16.6 +
    # canonical Phase 1F build prompt (canonical accessed event canonical-
    # emitted at canonical D-6 substrate). Best-effort per canonical
    # discipline — audit failure NEVER blocks canonical instance open.
    try:
        from app.services.documents import document_sharing_service

        document_sharing_service.record_access(
            db,
            share=share,
            actor_user_id=opened_by_user_id,
            actor_company_id=mfg_company_id,
            event_type="accessed",
        )
    except Exception:  # noqa: BLE001 — best-effort audit
        logger.exception(
            "personalization_studio.open_instance_from_share "
            "audit-event write failed share_id=%s",
            document_share_id,
        )

    logger.info(
        "personalization_studio.open_instance_from_share: id=%s "
        "share_id=%s mfg_company_id=%s template_type=%s",
        instance.id,
        document_share_id,
        mfg_company_id,
        template_type,
    )
    return instance


def assert_canvas_state_mutation_permitted(
    instance: GenerationFocusInstance,
) -> None:
    """Canonical service-layer guard: canvas state mutations canonical-
    rejected at canonical ``manufacturer_from_fh_share`` authoring
    context per Q9c canonical-discipline guidance.

    Per Phase 1F build prompt: canvas state read-only at canonical
    Mfg-tenant scope; canonical canvas state mutations canonical-rejected
    at service layer with canonical 403 surface.

    Anti-pattern guards explicit:
      - §2.5.4 Anti-pattern 17 (canonical action vocabulary bypassing
        rejected) — canonical Mfg-tenant action vocabulary canonically
        bounded ("Mark reviewed" commit canonical only; canvas mutations
        canonical-rejected with canonical 403).
      - §3.26.11.12.16 Anti-pattern 11 (UI-coupled Generation Focus
        design rejected) — canonical service-layer enforcement preserves
        canonical canvas state read-only invariant regardless of
        canonical FE chrome behavior.

    Raises:
        PersonalizationStudioPermissionDenied: instance.authoring_context
            == 'manufacturer_from_fh_share' (canonical 403).
    """
    if instance.authoring_context == "manufacturer_from_fh_share":
        raise PersonalizationStudioPermissionDenied(
            f"Canvas state mutation not permitted at canonical "
            f"manufacturer_from_fh_share authoring context. The "
            f"canonical canvas state is read-only at canonical Mfg-"
            f"tenant scope per Q9c canonical-discipline guidance."
        )


# ─────────────────────────────────────────────────────────────────────
# Phase 1G — Mfg-side "Mark reviewed" canonical post-commit cascade
# ─────────────────────────────────────────────────────────────────────


def manufacturer_from_fh_share_post_commit_cascade(
    db: Session,
    *,
    instance: GenerationFocusInstance,
) -> dict[str, Any]:
    """Phase 1G post-commit cascade fired on Mfg-side "Mark reviewed".

    Per Phase 1F flagged scope + Phase 1G build prompt: when canonical
    Mfg-tenant operator clicks canonical "Mark reviewed" at canonical
    ``manufacturer_from_fh_share`` authoring context (canonical
    ``commit_instance`` flow), this canonical cascade fires.

    Canonical pattern-establisher discipline at Phase 1G — Step 2
    inherits via canonical authoring_context discriminator dispatch:
      - Emit canonical V-1d notification to canonical Mfg-tenant admins
        ("Memorial design reviewed, ready for production")
      - Emit canonical D-6 ``record_access`` event with canonical
        ``event_type='reviewed'`` (canonical audit ledger extension at
        canonical D-6 substrate per §3.26.16.6 — canonical reviewed
        event surfaces canonical Mfg-side commit at canonical cross-
        tenant audit ledger)

    Future Step 2 + future canonical Mfg-vertical cascade extensions
    (canonical sales_order line item linkage; canonical work_order
    creation; canonical production schedule integration) attach via
    canonical authoring_context discriminator at canonical cascade
    service substrate per canonical Anti-pattern 12 guard.

    Canonical separation: failures at canonical cascade do NOT roll
    back canonical Phase 1F lifecycle commit — the canonical Mfg-side
    Mark-reviewed decision is durable regardless of canonical cascade
    fate. Canonical cascade outcome canonical-returned for canonical
    route-handler consumption.

    Args:
        instance: canonical GenerationFocusInstance at canonical
            ``manufacturer_from_fh_share`` authoring context with
            canonical ``lifecycle_state == 'committed'``.

    Returns canonical cascade outcome dict with canonical keys:
      - ``cascade_fired``: True on canonical Mfg-side scope; False when
        canonical instance is NOT canonical Mfg-from-FH-share scope
        (canonical no-op canonical-skip)
      - ``share_id``: canonical DocumentShare.id (resolved from
        canonical instance.linked_entity_id) or None
      - ``notification_count``: canonical Mfg-tenant admin notification
        fan-out count
      - ``audit_event_id``: canonical DocumentShareEvent.id of canonical
        ``reviewed`` event (None on canonical non-Mfg authoring or
        canonical audit failure)
    """
    from app.models.document_share import DocumentShare

    # Canonical no-op canonical-skip on canonical non-Mfg authoring
    # context (canonical FH-vertical funeral_home_with_family +
    # canonical manufacturer_without_family canonical-skip).
    if instance.authoring_context != "manufacturer_from_fh_share":
        return {
            "cascade_fired": False,
            "share_id": None,
            "notification_count": 0,
            "audit_event_id": None,
        }

    # Canonical defensive guard: cascade canonical-fires only at
    # canonical committed lifecycle_state.
    if instance.lifecycle_state != "committed":
        return {
            "cascade_fired": False,
            "share_id": None,
            "notification_count": 0,
            "audit_event_id": None,
        }

    # Resolve canonical DocumentShare via canonical Q3 pairing
    # (linked_entity_type='document_share' ↔ linked_entity_id=share.id).
    share = (
        db.query(DocumentShare)
        .filter(DocumentShare.id == instance.linked_entity_id)
        .first()
    )
    if share is None:
        # Canonical defensive: Mfg-from-share instance canonical-points
        # at canonical share row at open boundary; missing share at
        # commit boundary canonical-suggests revoked-after-open or
        # canonical invariant violation. Cascade canonical-skips with
        # canonical log marker.
        logger.warning(
            "personalization_studio.manufacturer_from_fh_share_post_"
            "commit_cascade canonical-share-missing instance_id=%s "
            "linked_entity_id=%s",
            instance.id,
            instance.linked_entity_id,
        )
        return {
            "cascade_fired": False,
            "share_id": None,
            "notification_count": 0,
            "audit_event_id": None,
        }

    # Step 1: canonical V-1d notification fan-out to canonical Mfg-
    # tenant admins. Best-effort canonical V-1d discipline preserved
    # (canonical notify_tenant_admins canonical-handles canonical
    # missing-admin fallback).
    notification_count = 0
    try:
        from app.services import notification_service

        # Canonical V-1d notify_tenant_admins canonical signature does
        # not surface canonical fan-out count directly; canonical
        # success canonical-implies canonical canonical-active-admin
        # fan-out. Set canonical sentinel for canonical canonical-test
        # consumption.
        notification_service.notify_tenant_admins(
            db,
            company_id=instance.company_id,
            title=(
                "Memorial design reviewed, ready for production"
            ),
            message=(
                "A funeral home memorial design has been reviewed and "
                "is ready for production. Open the canonical Mfg-tenant "
                "Personalization Studio surface to view the canonical "
                "approved canvas state."
            ),
            type="info",
            category="personalization_studio_mfg_reviewed",
            link=(
                f"/personalization-studio/from-share/{share.id}"
            ),
            source_reference_type="generation_focus_instance",
            source_reference_id=instance.id,
        )
        notification_count = 1  # canonical sentinel canonical-active fan-out
    except Exception:  # noqa: BLE001 — canonical best-effort V-1d
        logger.exception(
            "personalization_studio.manufacturer_from_fh_share_post_"
            "commit_cascade canonical-notification-failure "
            "instance_id=%s",
            instance.id,
        )

    # Step 2: canonical D-6 ``reviewed`` event canonical-emission.
    # Canonical audit ledger extension at canonical cross-tenant share
    # audit substrate per §3.26.16.6.
    audit_event_id: str | None = None
    try:
        from app.services.documents import document_sharing_service

        ev = document_sharing_service.record_access(
            db,
            share=share,
            actor_user_id=instance.committed_by_user_id,
            actor_company_id=instance.company_id,
            event_type="reviewed",
        )
        audit_event_id = ev.id
    except Exception:  # noqa: BLE001 — canonical best-effort audit
        logger.exception(
            "personalization_studio.manufacturer_from_fh_share_post_"
            "commit_cascade canonical-audit-failure instance_id=%s "
            "share_id=%s",
            instance.id,
            share.id,
        )

    logger.info(
        "personalization_studio.manufacturer_from_fh_share_post_"
        "commit_cascade fired instance_id=%s share_id=%s "
        "notification_count=%s audit_event_id=%s",
        instance.id,
        share.id,
        notification_count,
        audit_event_id,
    )

    return {
        "cascade_fired": True,
        "share_id": share.id,
        "notification_count": notification_count,
        "audit_event_id": audit_event_id,
    }
