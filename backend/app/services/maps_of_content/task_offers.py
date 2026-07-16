"""Task-tier offer-reach (Tenant Ponder-Editor P3) — V-2's update lifecycle
reaching its final anticipated tier: vertical-default TASK changes offer
themselves to tenant forks. `artifact_update_offers.target_tenant_id`
finally earns its column; ZERO schema change (the table is level-generic).

SCOPE, PRECISELY: offers cover the TASK ROW'S OWN FIELDS — the trigger
foremost, plus name/description/icon/frequency/type. NOT the workflow: the
workflow is SHARED under forks by architecture; its improvements flow to
every tenant automatically — that's the fork design's whole point.

THE PUBLISH BOUNDARY (the V-2 lesson at the task tier): offers key on a
DELIBERATE "offer this change to tenant versions" moment — an explicit
admin act with a note — never on every vertical-default edit. Editing a
task creates ZERO offer rows (pinned).

VERSIONS WITHOUT A VERSION COLUMN: task rows are mutable in place, so the
publish sequence IS the version — version_to = count of prior publishes
for this task + 1; a fork's "pin" = the version_to of its last ACCEPTED
offer (0 = never accepted). Bookkeeping for display + supersede; the apply
uses the offer's own diff snapshot, never a stepwise chain.

ACCEPT NEVER PROMOTES: taking the standard's schedule replaces the fork's
schedule triggers with fresh copies at is_live=FALSE — always, regardless
of the source's state (the born-unpromoted rule, again).

PER-FIELD CHOICES: the diff is fork-current vs default-current (tasks have
no override-key ledger, so "customized since fork" isn't distinguishable —
a deliberate lightening of V-2's keep-mine default). The UI presents every
diff line take-new by default with per-field keep-mine toggles; the
service applies exactly the `choices` it's handed (unspecified = take).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.artifact_update import ArtifactPublish, ArtifactUpdateOffer
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.moc_task_trigger import MoCTaskTrigger

logger = logging.getLogger(__name__)

ARTIFACT_MOC_TASK = "moc_task"
TARGET_MOC_TASK_FORK = "moc_task_fork"

_FIELDS = ("name", "description", "icon", "frequency", "task_type")


class TaskOfferError(Exception):
    """A publish/offer/apply step failed — message names the step.
    `latest_offer_id` set when the caller should re-open a fresher offer."""

    def __init__(self, message: str, *, latest_offer_id: str | None = None):
        super().__init__(message)
        self.latest_offer_id = latest_offer_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _schedule_prose_list(task: MoCTaskCatalog) -> list[str]:
    """The task's active schedule triggers as the PROSE GRAMMAR — the diff
    renderer ('The first Monday of every month at 4:00 PM')."""
    from app.services.maps_of_content.ponder import schedule_trigger_to_prose

    return [
        schedule_trigger_to_prose(t.config or {})
        for t in sorted(task.triggers, key=lambda t: t.display_order)
        if t.is_active and t.kind == "schedule"
    ]


def _forks_of(db: Session, task_id: str) -> list[MoCTaskCatalog]:
    return (
        db.query(MoCTaskCatalog)
        .filter(
            MoCTaskCatalog.forked_from_task_id == task_id,
            MoCTaskCatalog.scope == "tenant_override",
            MoCTaskCatalog.is_active.is_(True),
        )
        .all()
    )


def _derive_task_diff(fork: MoCTaskCatalog, default: MoCTaskCatalog) -> dict:
    """Field-level diff, fork-current → default-current. Only differing
    fields ride; 'schedule' compares the prose of the active schedule
    triggers (the derivation grammar as the diff renderer). The 'to' values
    double as the APPLY SNAPSHOT — accept applies these, never re-reads a
    chain."""
    fields: dict[str, dict] = {}
    for f in _FIELDS:
        mine, theirs = getattr(fork, f), getattr(default, f)
        if mine != theirs:
            fields[f] = {"from": mine, "to": theirs}
    mine_prose = _schedule_prose_list(fork)
    std_prose = _schedule_prose_list(default)
    if mine_prose != std_prose:
        fields["schedule"] = {
            "from": mine_prose,
            "to": std_prose,
            # The apply snapshot: the default's schedule-trigger configs at
            # publish time (copied unpromoted on take).
            "to_configs": [
                {"config": dict(t.config or {}), "label": t.label,
                 "display_order": t.display_order, "is_active": t.is_active}
                for t in sorted(default.triggers, key=lambda t: t.display_order)
                if t.kind == "schedule"
            ],
        }
    summary = ", ".join(sorted(fields.keys()))
    return {"fields": fields, "summary": summary or "no differences"}


def _publish_version(db: Session, task_id: str) -> int:
    """The publish sequence for this task (the version, count-derived)."""
    n = (
        db.query(ArtifactPublish)
        .filter(
            ArtifactPublish.artifact_type == ARTIFACT_MOC_TASK,
            ArtifactPublish.source_slug == task_id,
        )
        .count()
    )
    return n + 1


def _fork_pin(db: Session, fork_id: str) -> int:
    """The fork's last-accepted publish version (0 = never accepted)."""
    row = (
        db.query(ArtifactUpdateOffer.source_version_to)
        .filter(
            ArtifactUpdateOffer.target_kind == TARGET_MOC_TASK_FORK,
            ArtifactUpdateOffer.target_slug == fork_id,
            ArtifactUpdateOffer.status == "accepted",
        )
        .order_by(ArtifactUpdateOffer.source_version_to.desc())
        .first()
    )
    return row[0] if row else 0


# ── The deliberate boundary ──────────────────────────────────────────


def offer_preview(db: Session, *, task_id: str) -> dict:
    """What the publish dialog shows: the forks + each one's field diff.
    The admin sees exactly who would be offered what BEFORE the deliberate
    act."""
    task = db.get(MoCTaskCatalog, task_id)
    if task is None or not task.is_active or task.scope != "vertical_default":
        raise TaskOfferError("only an active vertical-default task can offer updates")
    forks = _forks_of(db, task_id)
    per_fork = []
    for fork in forks:
        diff = _derive_task_diff(fork, task)
        per_fork.append({
            "fork_task_id": fork.id,
            "tenant_id": fork.tenant_id,
            "differs": bool(diff["fields"]),
            "summary": diff["summary"],
        })
    return {
        "task_id": task.id,
        "task_name": task.name,
        "fork_count": len(forks),
        "offerable_count": sum(1 for f in per_fork if f["differs"]),
        "forks": per_fork,
    }


def publish_task_update(
    db: Session, *, task_id: str, patch_notes: str | None, actor_id: str | None
) -> dict:
    """THE DELIBERATE MOMENT — 'offer this change to tenant versions'.
    Records the publish, supersedes each fork's prior live offers (one live
    offer per edge, always to the latest), and creates one fresh PENDING
    offer per fork that actually differs (a fork already matching the
    standard gets nothing — no noise). Caller does NOT pre-commit; this
    commits."""
    task = db.get(MoCTaskCatalog, task_id)
    if task is None or not task.is_active or task.scope != "vertical_default":
        raise TaskOfferError("only an active vertical-default task can offer updates")
    forks = _forks_of(db, task_id)
    if not forks:
        raise TaskOfferError("no tenant versions exist — nothing to offer")

    version = _publish_version(db, task_id)
    publish = ArtifactPublish(
        artifact_type=ARTIFACT_MOC_TASK,
        source_slug=task.id,
        version=version,
        patch_notes=(patch_notes or "").strip() or None,
        derived_diff={"summary": f"standard update v{version}"},
        created_by=actor_id,
    )
    db.add(publish)
    db.flush()

    offers_created = 0
    for fork in forks:
        diff = _derive_task_diff(fork, task)
        if not diff["fields"]:
            continue  # already matching — no noise
        db.query(ArtifactUpdateOffer).filter(
            ArtifactUpdateOffer.artifact_type == ARTIFACT_MOC_TASK,
            ArtifactUpdateOffer.target_kind == TARGET_MOC_TASK_FORK,
            ArtifactUpdateOffer.target_slug == fork.id,
            ArtifactUpdateOffer.status.in_(["pending", "declined"]),
        ).update({"status": "superseded"}, synchronize_session=False)
        db.add(ArtifactUpdateOffer(
            publish_id=publish.id,
            artifact_type=ARTIFACT_MOC_TASK,
            source_slug=task.id,
            source_version_from=_fork_pin(db, fork.id),
            source_version_to=version,
            target_kind=TARGET_MOC_TASK_FORK,
            target_slug=fork.id,
            target_vertical=fork.vertical,
            target_tenant_id=fork.tenant_id,
            patch_notes=publish.patch_notes,
            derived_diff=diff,
        ))
        offers_created += 1

    db.commit()
    logger.info(
        "task offer publish: %s v%s (%d offer(s))", task.id, version, offers_created
    )
    return {
        "publish_id": publish.id,
        "task_id": task.id,
        "version": version,
        "fork_count": len(forks),
        "offers_created": offers_created,
    }


# ── The tenant side (badges, the offer, accept/decline) ──────────────


def offer_states_for_forks(
    db: Session, *, company_id: str, fork_task_ids: list[str]
) -> dict[str, dict]:
    """Per-fork live offer state for the tenant map's badges: pending →
    badge; declined → the quiet-but-recallable gap chip. THEIR offers only
    (target_tenant_id — the isolation boundary)."""
    if not fork_task_ids:
        return {}
    rows = (
        db.query(ArtifactUpdateOffer)
        .filter(
            ArtifactUpdateOffer.target_kind == TARGET_MOC_TASK_FORK,
            ArtifactUpdateOffer.target_slug.in_(fork_task_ids),
            ArtifactUpdateOffer.target_tenant_id == company_id,
            ArtifactUpdateOffer.status.in_(["pending", "declined"]),
        )
        .order_by(ArtifactUpdateOffer.created_at.desc())
        .all()
    )
    out: dict[str, dict] = {}
    for o in rows:
        if o.target_slug in out:
            continue  # newest wins (one live offer per edge by supersede)
        out[o.target_slug] = {"offer_id": o.id, "offer_status": o.status}
    return out


def _owned_offer(db: Session, offer_id: str, company_id: str) -> ArtifactUpdateOffer:
    offer = db.get(ArtifactUpdateOffer, offer_id)
    if (
        offer is None
        or offer.target_kind != TARGET_MOC_TASK_FORK
        or offer.target_tenant_id != company_id
    ):
        # Not theirs → not found (the ownership semantics — never a hint).
        raise TaskOfferError("offer not found")
    return offer


def get_offer(db: Session, *, offer_id: str, company_id: str) -> dict:
    offer = _owned_offer(db, offer_id, company_id)
    return {
        "id": offer.id,
        "task_id": offer.target_slug,
        "source_task_id": offer.source_slug,
        "version_from": offer.source_version_from,
        "version_to": offer.source_version_to,
        "patch_notes": offer.patch_notes,
        "diff": offer.derived_diff,
        "status": offer.status,
        "created_at": offer.created_at.isoformat(),
        "decided_at": offer.decided_at.isoformat() if offer.decided_at else None,
    }


def accept_offer(
    db: Session,
    *,
    offer_id: str,
    company_id: str,
    choices: dict[str, str] | None = None,
    actor_id: str | None = None,
) -> dict:
    """Apply the standard's update to THEIR row — atomic; per-field
    keep-mine ({field: 'keep'}) leaves their value; everything else in the
    diff applies from the offer's snapshot. Taking 'schedule' REPLACES their
    schedule triggers with copies BORN UNPROMOTED (accepting never
    promotes). Accepting a declined offer is the recall path; a superseded
    offer errors with the latest live offer's id."""
    choices = choices or {}
    offer = _owned_offer(db, offer_id, company_id)
    if offer.status == "accepted":
        raise TaskOfferError("offer already accepted")
    if offer.status == "superseded":
        latest = (
            db.query(ArtifactUpdateOffer)
            .filter(
                ArtifactUpdateOffer.target_kind == TARGET_MOC_TASK_FORK,
                ArtifactUpdateOffer.target_slug == offer.target_slug,
                ArtifactUpdateOffer.target_tenant_id == company_id,
                ArtifactUpdateOffer.status.in_(["pending", "declined"]),
            )
            .order_by(ArtifactUpdateOffer.created_at.desc())
            .first()
        )
        raise TaskOfferError(
            "offer superseded by a newer update",
            latest_offer_id=latest.id if latest else None,
        )

    fork = db.get(MoCTaskCatalog, offer.target_slug)
    if fork is None or not fork.is_active:
        raise TaskOfferError("your version of this task no longer exists")

    fields = (offer.derived_diff or {}).get("fields") or {}
    applied, kept = [], []
    for field, delta in fields.items():
        if choices.get(field) == "keep":
            kept.append(field)
            continue
        if field == "schedule":
            # Replace their SCHEDULE triggers with the snapshot's — copies
            # BORN UNPROMOTED, always.
            for t in list(fork.triggers):
                if t.kind == "schedule":
                    db.delete(t)
            db.flush()
            for spec in delta.get("to_configs") or []:
                db.add(MoCTaskTrigger(
                    task_catalog_id=fork.id,
                    kind="schedule",
                    config=dict(spec.get("config") or {}),
                    label=spec.get("label"),
                    display_order=spec.get("display_order", 0),
                    is_active=spec.get("is_active", True),
                    is_live=False,  # accept NEVER promotes
                    created_by=actor_id,
                    updated_by=actor_id,
                ))
        else:
            setattr(fork, field, delta.get("to"))
        applied.append(field)
    fork.updated_by = actor_id

    offer.status = "accepted"
    offer.decided_at = _now()
    offer.decided_by = actor_id
    db.add(offer)
    db.commit()
    return {"task_id": fork.id, "applied": applied, "kept": kept}


def decline_offer(
    db: Session, *, offer_id: str, company_id: str, actor_id: str | None = None
) -> dict:
    """Quiet-but-recallable: the badge drops; the gap chip ('yours ·
    standard updated') stays discoverable; accept still works from here.
    A later publish supersedes."""
    offer = _owned_offer(db, offer_id, company_id)
    if offer.status != "pending":
        raise TaskOfferError(f"offer is {offer.status}, not pending")
    offer.status = "declined"
    offer.decided_at = _now()
    offer.decided_by = actor_id
    db.add(offer)
    db.commit()
    return {"id": offer.id, "status": offer.status}
