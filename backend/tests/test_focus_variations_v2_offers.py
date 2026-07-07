"""Focus Variations V-2 — offered updates (publish → offer → diff → apply).

Pins, per the dispatch:
  1. Publish creates one offer per inheritor (per-target diff from THAT
     target's pin); with NO inheritors it still records the release.
  2. The pin-honoring guarantee: once a core is under the publish regime,
     an unaccepted variation resolves the core AS OF its pin — the core's
     newer chrome does NOT reach it (the whole point of the model).
     Cores never published keep the live cascade (no behavior change).
  3. Accept moves the pin (a version-bumped template row — the retained-
     snapshot discipline) + the cascade field-merges inherited fields;
     a CUSTOMIZED field is never silently overwritten (keep-mine default;
     take-new is the explicit choice that drops the override).
  4. Decline is quiet-but-recallable: badge state drops (pending only),
     the gap stays discoverable, accept-from-declined works.
  5. Chain collapse: a second publish supersedes the prior live offer and
     creates ONE fresh offer from the target's CURRENT pin to the LATEST.
  6. A failed apply is atomic — the template is never left half-merged.

State-immunity: unique-slug fixtures, fixture-scoped teardown, no wipes.
"""

from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal
from app.models.artifact_update import ArtifactPublish, ArtifactUpdateOffer
from app.models.focus_core import FocusCore
from app.models.focus_template import FocusTemplate
from app.services.artifact_updates import (
    ArtifactUpdateError,
    accept_offer,
    decline_offer,
    get_publish_preview,
    offer_states_for_targets,
    publish_core_update,
)
from app.services.focus_template_inheritance import (
    create_core,
    create_template,
    resolve_focus,
    update_core,
)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def env(db):
    """A core (chrome corner_radius=70) + a variation inheriting it, both
    unique-slugged; fixture-scoped teardown."""
    suffix = uuid.uuid4().hex[:8]
    core = create_core(
        db,
        core_slug=f"v2-core-{suffix}",
        display_name=f"V2 Core {suffix}",
        registered_component_kind="focus-core",
        registered_component_name="SchedulingKanbanCore",
        default_starting_column=0,
        default_column_span=12,
        default_row_index=0,
        min_column_span=8,
        max_column_span=12,
        canvas_config={},
        chrome={"corner_radius": 70, "elevation": 50},
    )
    tmpl = create_template(
        db,
        scope="vertical_default",
        vertical="manufacturing",
        template_slug=f"v2-var-{suffix}",
        display_name="V2 Variation",
        inherits_from_core_id=core.id,
        rows=[],
        canvas_config={},
    )
    yield {"db": db, "core": core, "tmpl": tmpl, "suffix": suffix}
    s = SessionLocal()
    try:
        s.query(ArtifactUpdateOffer).filter(
            ArtifactUpdateOffer.source_slug == f"v2-core-{suffix}"
        ).delete(synchronize_session=False)
        s.query(ArtifactPublish).filter(
            ArtifactPublish.source_slug == f"v2-core-{suffix}"
        ).delete(synchronize_session=False)
        s.query(FocusTemplate).filter(
            FocusTemplate.template_slug == f"v2-var-{suffix}"
        ).delete(synchronize_session=False)
        s.query(FocusCore).filter(
            FocusCore.core_slug == f"v2-core-{suffix}"
        ).delete(synchronize_session=False)
        s.commit()
    finally:
        s.close()


def _edit_core(db, core_id: str, **kwargs) -> FocusCore:
    """A non-session core edit → version bump (new row id)."""
    return update_core(db, core_id, **kwargs)


# ── 1. publish creates offers per inheritor; zero-inheritor still records ──


def test_publish_creates_offer_per_inheritor(env):
    db, core, tmpl = env["db"], env["core"], env["tmpl"]
    v2 = _edit_core(db, core.id, chrome={"corner_radius": 50, "elevation": 50})
    result = publish_core_update(
        db, core_id=v2.id, patch_notes="Rounder no more.", actor_id=None
    )
    assert result["offers_created"] == 1
    offer = (
        db.query(ArtifactUpdateOffer)
        .filter(ArtifactUpdateOffer.target_slug == tmpl.template_slug)
        .one()
    )
    assert offer.status == "pending"
    assert offer.source_version_from == 1        # the target's pin
    assert offer.source_version_to == 2          # the published version
    assert offer.patch_notes == "Rounder no more."
    fields = {f["field"]: f for f in offer.derived_diff["fields"]}
    assert fields["corner_radius"]["from"] == 70
    assert fields["corner_radius"]["to"] == 50
    assert fields["corner_radius"]["target_state"] == "inherited"


def test_publish_with_no_inheritors_still_records_release(db):
    suffix = uuid.uuid4().hex[:8]
    core = create_core(
        db,
        core_slug=f"v2-lone-{suffix}",
        display_name="Lone Core",
        registered_component_kind="focus-core",
        registered_component_name="SchedulingKanbanCore",
        default_starting_column=0, default_column_span=12,
        default_row_index=0, min_column_span=8, max_column_span=12,
        canvas_config={},
    )
    try:
        result = publish_core_update(
            db, core_id=core.id, patch_notes="v1 ships.", actor_id=None
        )
        assert result["offers_created"] == 0
        pub = db.get(ArtifactPublish, result["publish_id"])
        assert pub is not None and pub.version == 1  # the release recorded
        # And re-publishing with nothing new refuses.
        with pytest.raises(ArtifactUpdateError):
            publish_core_update(db, core_id=core.id, patch_notes=None,
                                actor_id=None)
    finally:
        db.rollback()
        db.query(ArtifactPublish).filter(
            ArtifactPublish.source_slug == f"v2-lone-{suffix}"
        ).delete(synchronize_session=False)
        db.query(FocusCore).filter(
            FocusCore.core_slug == f"v2-lone-{suffix}"
        ).delete(synchronize_session=False)
        db.commit()


def test_publish_preview_scaffold(env):
    db, core = env["db"], env["core"]
    v2 = _edit_core(db, core.id, chrome={"corner_radius": 50, "elevation": 50})
    preview = get_publish_preview(db, core_id=v2.id)
    assert preview["already_published"] is False
    assert preview["downstream_count"] == 1
    # Never published → the whole state is the release: "First publish".
    assert preview["scaffold"].startswith("First publish")

    # AFTER a publish, the next preview's scaffold derives the field delta.
    publish_core_update(db, core_id=v2.id, patch_notes=None, actor_id=None)
    v3 = _edit_core(db, v2.id, chrome={"corner_radius": 30, "elevation": 50})
    preview2 = get_publish_preview(db, core_id=v3.id)
    assert "corner_radius" in preview2["scaffold"]      # the derived fallback
    assert preview2["published_version"] == 2


# ── 2. the pin-honoring guarantee ────────────────────────────────────


def test_unaccepted_variation_resolves_pinned_core(env):
    db, core, tmpl = env["db"], env["core"], env["tmpl"]
    slug = tmpl.template_slug

    # BEFORE any publish: live cascade (status quo) — the core edit
    # reaches the variation immediately.
    _edit_core(db, core.id, chrome={"corner_radius": 50, "elevation": 50})
    r = resolve_focus(db, template_slug=slug, vertical="manufacturing")
    assert r.resolved_chrome["corner_radius"] == 50    # live cascade pre-publish

    # PUBLISH v2 → the regime begins. Then edit to v3 (unpublished).
    active = db.query(FocusCore).filter(
        FocusCore.core_slug == core.core_slug, FocusCore.is_active.is_(True)
    ).one()
    publish_core_update(db, core_id=active.id, patch_notes=None, actor_id=None)
    v3 = _edit_core(db, active.id, chrome={"corner_radius": 30, "elevation": 50})
    assert v3.version == 3 and v3.published_version == 2  # boundary carried

    # The variation (pinned at v1) now resolves AS OF v1 — neither the
    # published v2 nor the private v3 reached it without an accept.
    r = resolve_focus(db, template_slug=slug, vertical="manufacturing")
    assert r.resolved_chrome["corner_radius"] == 70    # the software-update guarantee


# ── 3. accept: pin-move + merge + never silently overwrite ──────────


def test_accept_moves_pin_and_merges_inherited_fields(env):
    db, core, tmpl = env["db"], env["core"], env["tmpl"]
    v2 = _edit_core(db, core.id, chrome={"corner_radius": 50, "elevation": 50})
    publish_core_update(db, core_id=v2.id, patch_notes=None, actor_id=None)
    offer = db.query(ArtifactUpdateOffer).filter(
        ArtifactUpdateOffer.target_slug == tmpl.template_slug
    ).one()

    result = accept_offer(db, offer_id=offer.id, choices={}, actor_id=None)
    assert result["pinned_version"] == 2
    # The template version-bumped (retained-snapshot discipline).
    assert result["template_version"] == tmpl.version + 1
    # The inherited field merged FREE via the cascade.
    r = resolve_focus(db, template_slug=tmpl.template_slug,
                      vertical="manufacturing")
    assert r.resolved_chrome["corner_radius"] == 50


def test_accept_never_silently_overwrites_customized_field(env):
    db, core, tmpl = env["db"], env["core"], env["tmpl"]
    from app.services.focus_template_inheritance import update_template

    # The owner customized corner_radius=90 on the variation.
    tmpl2 = update_template(db, tmpl.id, chrome_overrides={"corner_radius": 90})
    v2 = _edit_core(db, core.id, chrome={"corner_radius": 50, "elevation": 50})
    publish_core_update(db, core_id=v2.id, patch_notes=None, actor_id=None)
    offer = db.query(ArtifactUpdateOffer).filter(
        ArtifactUpdateOffer.target_slug == tmpl.template_slug,
        ArtifactUpdateOffer.status == "pending",
    ).one()
    # The offer's diff MARKS the conflict.
    conflict = [f for f in offer.derived_diff["fields"]
                if f["field"] == "corner_radius"][0]
    assert conflict["target_state"] == "customized"
    assert conflict["target_value"] == 90

    # KEEP-MINE (the default — no choices): the customization survives.
    accept_offer(db, offer_id=offer.id, choices={}, actor_id=None)
    r = resolve_focus(db, template_slug=tmpl.template_slug,
                      vertical="manufacturing")
    assert r.resolved_chrome["corner_radius"] == 90     # NEVER silently overwritten
    assert r.resolved_chrome["elevation"] == 50         # inherited fields still merge


def test_accept_take_new_drops_the_override(env):
    db, core, tmpl = env["db"], env["core"], env["tmpl"]
    from app.services.focus_template_inheritance import update_template

    update_template(db, tmpl.id, chrome_overrides={"corner_radius": 90})
    v2 = _edit_core(db, core.id, chrome={"corner_radius": 50, "elevation": 50})
    publish_core_update(db, core_id=v2.id, patch_notes=None, actor_id=None)
    offer = db.query(ArtifactUpdateOffer).filter(
        ArtifactUpdateOffer.target_slug == tmpl.template_slug,
        ArtifactUpdateOffer.status == "pending",
    ).one()

    result = accept_offer(db, offer_id=offer.id,
                          choices={"corner_radius": "take"}, actor_id=None)
    assert result["dropped_overrides"] == ["corner_radius"]
    r = resolve_focus(db, template_slug=tmpl.template_slug,
                      vertical="manufacturing")
    assert r.resolved_chrome["corner_radius"] == 50     # the explicit take-new


# ── 4. decline: quiet but recallable ─────────────────────────────────


def test_decline_quiet_gap_discoverable_and_recallable(env):
    db, core, tmpl = env["db"], env["core"], env["tmpl"]
    v2 = _edit_core(db, core.id, chrome={"corner_radius": 50, "elevation": 50})
    publish_core_update(db, core_id=v2.id, patch_notes=None, actor_id=None)
    offer = db.query(ArtifactUpdateOffer).filter(
        ArtifactUpdateOffer.target_slug == tmpl.template_slug
    ).one()

    decline_offer(db, offer_id=offer.id, actor_id=None)
    state = offer_states_for_targets(
        db, target_slugs=[tmpl.template_slug]
    )[tmpl.template_slug]
    assert state["offer_status"] == "declined"   # NOT pending → no badge
    assert state["pinned_version"] == 1
    assert state["core_version"] == 2            # the gap stays discoverable

    # RECALL: accepting the declined offer works.
    result = accept_offer(db, offer_id=offer.id, choices={}, actor_id=None)
    assert result["pinned_version"] == 2


# ── 5. chain collapse on stacked publishes ───────────────────────────


def test_second_publish_supersedes_and_offers_latest(env):
    db, core, tmpl = env["db"], env["core"], env["tmpl"]
    v2 = _edit_core(db, core.id, chrome={"corner_radius": 50, "elevation": 50})
    publish_core_update(db, core_id=v2.id, patch_notes="first", actor_id=None)
    first = db.query(ArtifactUpdateOffer).filter(
        ArtifactUpdateOffer.target_slug == tmpl.template_slug
    ).one()

    v3 = _edit_core(db, v2.id, chrome={"corner_radius": 30, "elevation": 50})
    publish_core_update(db, core_id=v3.id, patch_notes="second", actor_id=None)

    db.expire_all()
    offers = db.query(ArtifactUpdateOffer).filter(
        ArtifactUpdateOffer.target_slug == tmpl.template_slug
    ).order_by(ArtifactUpdateOffer.created_at).all()
    assert [o.status for o in offers] == ["superseded", "pending"]
    latest = offers[-1]
    assert latest.source_version_from == 1       # the target's CURRENT pin
    assert latest.source_version_to == 3         # straight to the LATEST

    # Accepting the stale offer errors, pointing at the live one.
    with pytest.raises(ArtifactUpdateError) as exc:
        accept_offer(db, offer_id=first.id, choices={}, actor_id=None)
    assert exc.value.latest_offer_id == latest.id

    # Accepting the live one lands on v3 in ONE move (no stepwise).
    accept_offer(db, offer_id=latest.id, choices={}, actor_id=None)
    r = resolve_focus(db, template_slug=tmpl.template_slug,
                      vertical="manufacturing")
    assert r.resolved_chrome["corner_radius"] == 30


# ── 6. a failed apply is atomic ──────────────────────────────────────


def test_failed_apply_is_atomic(env, monkeypatch):
    db, core, tmpl = env["db"], env["core"], env["tmpl"]
    v2 = _edit_core(db, core.id, chrome={"corner_radius": 50, "elevation": 50})
    publish_core_update(db, core_id=v2.id, patch_notes=None, actor_id=None)
    offer = db.query(ArtifactUpdateOffer).filter(
        ArtifactUpdateOffer.target_slug == tmpl.template_slug
    ).one()

    # Force the commit to fail AFTER the apply staged its writes.
    real_commit = db.commit
    def boom():
        raise RuntimeError("simulated commit failure")
    monkeypatch.setattr(db, "commit", boom)
    with pytest.raises(RuntimeError):
        accept_offer(db, offer_id=offer.id, choices={}, actor_id=None)
    monkeypatch.setattr(db, "commit", real_commit)
    db.rollback()

    # NOTHING half-merged: the template's active row is unchanged at v1
    # pin, and the offer is still pending (retryable).
    db.expire_all()
    active = db.query(FocusTemplate).filter(
        FocusTemplate.template_slug == tmpl.template_slug,
        FocusTemplate.is_active.is_(True),
    ).one()
    assert active.inherits_from_core_version == 1
    assert active.version == tmpl.version
    fresh = db.get(ArtifactUpdateOffer, offer.id)
    assert fresh.status == "pending"
