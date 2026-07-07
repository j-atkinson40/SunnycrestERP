"""Offered updates — publish / offer / accept / decline (Focus Variations V-2).

The software-update model: editing a default is PRIVATE until an explicit
PUBLISH; publishing creates one OFFER per downstream variation (per-target
diff from THAT target's pin); the owner reviews and ACCEPTS (pin-move
apply — atomic, never silently overwriting a customization) or DECLINES
(recallable, not nagging; superseded by the next publish).

V-2 scope: artifact_type='focus_core' → target_kind='focus_template'
(vertical variations). The table + this module's shape are level-generic;
future sources/targets register additional walkers, not schema.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.artifact_update import ArtifactPublish, ArtifactUpdateOffer
from app.models.focus_core import FocusCore
from app.models.focus_template import FocusTemplate
from app.services.artifact_updates.diff import derive_core_diff
from app.services.focus_template_inheritance import (
    get_core_by_id,
    get_core_by_slug_and_version,
)

logger = logging.getLogger(__name__)

ARTIFACT_FOCUS_CORE = "focus_core"
TARGET_FOCUS_TEMPLATE = "focus_template"


class ArtifactUpdateError(Exception):
    """A publish/offer/apply step failed — message names the step.
    `latest_offer_id` set when the caller should re-open a fresher offer."""

    def __init__(self, message: str, *, latest_offer_id: str | None = None):
        super().__init__(message)
        self.latest_offer_id = latest_offer_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Publish ──────────────────────────────────────────────────────────


def _core_lineage_ids(db: Session, core_slug: str):
    return (
        db.query(FocusCore.id)
        .filter(FocusCore.core_slug == core_slug)
        .scalar_subquery()
    )


def _downstream_templates(db: Session, core_slug: str) -> list[FocusTemplate]:
    return (
        db.query(FocusTemplate)
        .filter(
            FocusTemplate.inherits_from_core_id.in_(
                _core_lineage_ids(db, core_slug)
            ),
            FocusTemplate.is_active.is_(True),
        )
        .all()
    )


def get_publish_preview(db: Session, *, core_id: str) -> dict:
    """The unpublished delta (last published version → current) + the
    derived scaffold the publish dialog prefills for the author to edit."""
    core = get_core_by_id(db, core_id)
    if core is None or not core.is_active:
        raise ArtifactUpdateError(f"core {core_id!r} not found or inactive")
    prev = (
        get_core_by_slug_and_version(db, core.core_slug, core.published_version)
        if core.published_version is not None
        else None
    )
    diff = derive_core_diff(prev, core)
    downstream = _downstream_templates(db, core.core_slug)
    return {
        "core_slug": core.core_slug,
        "current_version": core.version,
        "published_version": core.published_version,
        "already_published": core.published_version == core.version,
        "derived_diff": diff,
        "scaffold": diff["summary"],
        "downstream_count": len(downstream),
    }


def publish_core_update(
    db: Session, *, core_id: str, patch_notes: str | None, actor_id: str | None
) -> dict:
    """The explicit release. Records the publish (even with zero
    inheritors — the boundary exists regardless), stamps the boundary on
    the active core row, supersedes prior live offers, and creates one
    fresh PENDING offer per downstream template still behind (from THAT
    target's pin — the chain-collapse rule: always offer the latest)."""
    core = get_core_by_id(db, core_id)
    if core is None or not core.is_active:
        raise ArtifactUpdateError(f"core {core_id!r} not found or inactive")
    if core.published_version == core.version:
        raise ArtifactUpdateError(
            f"nothing to publish — v{core.version} is already published"
        )

    prev = (
        get_core_by_slug_and_version(db, core.core_slug, core.published_version)
        if core.published_version is not None
        else None
    )
    publish = ArtifactPublish(
        artifact_type=ARTIFACT_FOCUS_CORE,
        source_slug=core.core_slug,
        version=core.version,
        patch_notes=(patch_notes or "").strip() or None,
        derived_diff=derive_core_diff(prev, core),
        created_by=actor_id,
    )
    db.add(publish)
    db.flush()  # materialize publish.id (flush-time default) for the offers
    core.published_version = core.version
    db.add(core)

    offers_created = 0
    for tmpl in _downstream_templates(db, core.core_slug):
        if tmpl.inherits_from_core_version >= core.version:
            continue  # already at (or somehow past) the release
        # Supersede the target's prior live offers — one live offer per
        # edge, always from the CURRENT pin to the LATEST publish.
        db.query(ArtifactUpdateOffer).filter(
            ArtifactUpdateOffer.artifact_type == ARTIFACT_FOCUS_CORE,
            ArtifactUpdateOffer.source_slug == core.core_slug,
            ArtifactUpdateOffer.target_kind == TARGET_FOCUS_TEMPLATE,
            ArtifactUpdateOffer.target_slug == tmpl.template_slug,
            ArtifactUpdateOffer.status.in_(["pending", "declined"]),
        ).update({"status": "superseded"}, synchronize_session=False)

        pinned = get_core_by_slug_and_version(
            db, core.core_slug, tmpl.inherits_from_core_version
        )
        db.add(
            ArtifactUpdateOffer(
                publish_id=publish.id,
                artifact_type=ARTIFACT_FOCUS_CORE,
                source_slug=core.core_slug,
                source_version_from=tmpl.inherits_from_core_version,
                source_version_to=core.version,
                target_kind=TARGET_FOCUS_TEMPLATE,
                target_slug=tmpl.template_slug,
                target_vertical=tmpl.vertical,
                patch_notes=publish.patch_notes,
                derived_diff=derive_core_diff(pinned, core, template=tmpl),
            )
        )
        offers_created += 1

    db.commit()
    logger.info(
        "published %s v%s (%d offer(s) created)",
        core.core_slug, core.version, offers_created,
    )
    return {
        "publish_id": publish.id,
        "source_slug": core.core_slug,
        "version": core.version,
        "offers_created": offers_created,
    }


# ── The map's offer state (badges + gap chips) ───────────────────────


def offer_states_for_targets(db: Session, *, target_slugs: list[str]) -> dict:
    """Per-slug offer state for the map's Focuses pills: the live offer
    (pending → badge; declined → quiet-but-recallable) + the version gap
    (pin vs the core's active version, shown when behind)."""
    out: dict[str, dict] = {}
    if not target_slugs:
        return out
    templates = (
        db.query(FocusTemplate)
        .filter(
            FocusTemplate.template_slug.in_(target_slugs),
            FocusTemplate.is_active.is_(True),
        )
        .all()
    )
    for tmpl in templates:
        offer = (
            db.query(ArtifactUpdateOffer)
            .filter(
                ArtifactUpdateOffer.target_kind == TARGET_FOCUS_TEMPLATE,
                ArtifactUpdateOffer.target_slug == tmpl.template_slug,
                ArtifactUpdateOffer.status.in_(["pending", "declined"]),
            )
            .order_by(ArtifactUpdateOffer.created_at.desc())
            .first()
        )
        core = None
        if offer is not None:
            core_version = offer.source_version_to
        else:
            # No live offer — still surface a gap if the core has moved
            # past the pin AND is under the publish regime.
            from app.services.focus_template_inheritance import (
                get_core_slug_by_id,
            )
            from app.services.focus_template_inheritance.focus_cores_service import (
                get_core_by_slug,
            )

            slug = get_core_slug_by_id(db, tmpl.inherits_from_core_id)
            core = get_core_by_slug(db, slug) if slug else None
            if core is None or core.published_version is None:
                continue
            core_version = core.published_version
        if (
            offer is None
            and core is not None
            and tmpl.inherits_from_core_version >= core_version
        ):
            continue
        out[tmpl.template_slug] = {
            "target_slug": tmpl.template_slug,
            "pinned_version": tmpl.inherits_from_core_version,
            "core_version": core_version,
            "offer_id": offer.id if offer else None,
            "offer_status": offer.status if offer else None,
        }
    return out


def get_offer(db: Session, offer_id: str) -> dict:
    offer = db.get(ArtifactUpdateOffer, offer_id)
    if offer is None:
        raise ArtifactUpdateError(f"offer {offer_id!r} not found")
    return _offer_payload(offer)


def _offer_payload(offer: ArtifactUpdateOffer) -> dict:
    return {
        "id": offer.id,
        "artifact_type": offer.artifact_type,
        "source_slug": offer.source_slug,
        "source_version_from": offer.source_version_from,
        "source_version_to": offer.source_version_to,
        "target_kind": offer.target_kind,
        "target_slug": offer.target_slug,
        "target_vertical": offer.target_vertical,
        "patch_notes": offer.patch_notes,
        "derived_diff": offer.derived_diff,
        "status": offer.status,
        "created_at": offer.created_at.isoformat(),
        "decided_at": offer.decided_at.isoformat() if offer.decided_at else None,
    }


# ── Accept / decline ─────────────────────────────────────────────────


def accept_offer(
    db: Session,
    *,
    offer_id: str,
    choices: dict[str, str] | None = None,
    actor_id: str | None = None,
) -> dict:
    """The pin-move apply — ATOMIC (one transaction: the template's new
    version row + the offer decision commit together or not at all).

    The cascade keeps the target's own overrides winning after the pin
    moves, so a customized field defaults to KEEP-MINE with zero writes;
    `choices` ({chrome_field: "take"}) is the explicit opt-in that drops
    the override key. Applying never silently overwrites a customization.

    Accepting a DECLINED offer is allowed (the recall path). Accepting a
    SUPERSEDED offer errors with the latest live offer's id (the chain
    collapsed — never stepwise applies)."""
    choices = choices or {}
    offer = db.get(ArtifactUpdateOffer, offer_id)
    if offer is None:
        raise ArtifactUpdateError(f"offer {offer_id!r} not found")
    if offer.status == "accepted":
        raise ArtifactUpdateError("offer already accepted")
    if offer.status == "superseded":
        latest = (
            db.query(ArtifactUpdateOffer)
            .filter(
                ArtifactUpdateOffer.target_kind == offer.target_kind,
                ArtifactUpdateOffer.target_slug == offer.target_slug,
                ArtifactUpdateOffer.status.in_(["pending", "declined"]),
            )
            .order_by(ArtifactUpdateOffer.created_at.desc())
            .first()
        )
        raise ArtifactUpdateError(
            "offer superseded by a newer publish",
            latest_offer_id=latest.id if latest else None,
        )

    tmpl = (
        db.query(FocusTemplate)
        .filter(
            FocusTemplate.template_slug == offer.target_slug,
            FocusTemplate.is_active.is_(True),
        )
        .first()
    )
    if tmpl is None:
        raise ArtifactUpdateError(
            f"target template {offer.target_slug!r} has no active row"
        )
    if tmpl.inherits_from_core_version >= offer.source_version_to:
        raise ArtifactUpdateError(
            f"template already at v{tmpl.inherits_from_core_version} — "
            "nothing to apply"
        )
    target_core = get_core_by_slug_and_version(
        db, offer.source_slug, offer.source_version_to
    )
    if target_core is None:
        raise ArtifactUpdateError(
            f"core snapshot {offer.source_slug} "
            f"v{offer.source_version_to} not found"
        )

    # take-new choices drop the override key so the new default shows
    # through the cascade; keep-mine (the default) touches nothing.
    new_overrides = dict(tmpl.chrome_overrides or {})
    for field, choice in choices.items():
        if choice == "take":
            new_overrides.pop(field, None)

    # ── ATOMIC apply: version-bump the template (B-1 semantics — the
    # prior row is the retained snapshot) with the moved pin. NO commits
    # until the offer decision is staged too — a failure anywhere rolls
    # the whole apply back (never half-merged).
    tmpl.is_active = False
    new_row = FocusTemplate(
        scope=tmpl.scope,
        vertical=tmpl.vertical,
        template_slug=tmpl.template_slug,
        display_name=tmpl.display_name,
        description=tmpl.description,
        inherits_from_core_id=target_core.id,
        inherits_from_core_version=offer.source_version_to,
        rows=list(tmpl.rows or []),
        canvas_config=dict(tmpl.canvas_config or {}),
        chrome_overrides=new_overrides,
        substrate=dict(tmpl.substrate or {}),
        typography=dict(getattr(tmpl, "typography", None) or {}),
        version=tmpl.version + 1,
        is_active=True,
        created_by=tmpl.created_by,
        updated_by=actor_id,
    )
    db.add(new_row)
    offer.status = "accepted"
    offer.decided_at = _now()
    offer.decided_by = actor_id
    db.add(offer)
    db.commit()
    db.refresh(new_row)
    return {
        "template_id": new_row.id,
        "template_version": new_row.version,
        "pinned_version": new_row.inherits_from_core_version,
        "dropped_overrides": [f for f, c in choices.items() if c == "take"],
    }


def decline_offer(
    db: Session, *, offer_id: str, actor_id: str | None = None
) -> dict:
    """Quiet-but-recallable: the badge drops (badges read PENDING only);
    the version gap stays discoverable on the pill; the offer reopens
    from there (accept works on declined). A later publish supersedes."""
    offer = db.get(ArtifactUpdateOffer, offer_id)
    if offer is None:
        raise ArtifactUpdateError(f"offer {offer_id!r} not found")
    if offer.status != "pending":
        raise ArtifactUpdateError(f"offer is {offer.status}, not pending")
    offer.status = "declined"
    offer.decided_at = _now()
    offer.decided_by = actor_id
    db.add(offer)
    db.commit()
    return _offer_payload(offer)
