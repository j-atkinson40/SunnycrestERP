"""The Map Home campaign pins.

  * THE DERIVER — composition (opening → task beats → closing), per-task
    beat content as story, the large-area cluster cap, the closing deep
    link, authored philosophy overlaying derived-honest placeholders
    (never stale), orphans surfacing.
  * ONBOARDING — the curriculum LIST (sequence-ordered; a list, not an
    engine); the seeded exemplar renders through the same script shape.
  * ENGAGEMENT — the quiet write: timestamps set ONCE (a re-view is not a
    new first view); one keyspace; per-user isolation.
  * SUGGESTIONS — each rule fires with its honest WHY (load-bearing,
    pinned present); dismissal respected (no resurrection); viewing
    advances/retires; the cap; empty-honest.

Hermetic: own companies/users/tasks/compositions, torn down by pattern.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.company import Company
from app.models.moc_composition import MoCComposition, PonderEngagement
from app.models.moc_task_catalog import MoCTaskCatalog
from app.models.user import User
from app.services.maps_of_content import engagement as eng
from app.services.maps_of_content.area_ponder import (
    AreaPonderError,
    build_area_ponder_script,
    build_onboarding_script,
    save_area_caption,
)

VERT = f"maphome-{uuid.uuid4().hex[:6]}"  # a synthetic vertical — hermetic ground


@pytest.fixture(scope="module")
def world():
    db = SessionLocal()
    # moc_task_catalog.vertical is FK'd to verticals.slug (post-r95) — the
    # hermetic vertical needs its row.
    db.execute(sql_text(
        "INSERT INTO verticals (slug, display_name) VALUES (:v, :n) "
        "ON CONFLICT (slug) DO NOTHING"
    ), {"v": VERT, "n": "MapHome Test Vertical"})
    db.commit()
    co_a = Company(id=str(uuid.uuid4()), name="MapHome A", slug=f"maphome-a-{uuid.uuid4().hex[:5]}",
                   is_active=True, vertical=VERT)
    co_b = Company(id=str(uuid.uuid4()), name="MapHome B", slug=f"maphome-b-{uuid.uuid4().hex[:5]}",
                   is_active=True, vertical=VERT)
    db.add_all([co_a, co_b])
    tasks = []
    for i in range(3):
        t = MoCTaskCatalog(
            scope="vertical_default", vertical=VERT,
            name=f"MapHome Task {i} {uuid.uuid4().hex[:4]}",
            task_type="Accounting",
            description=f"Does the number-{i} thing. And more detail after.",
            frequency="Daily",
        )
        db.add(t)
        tasks.append(t)
    db.commit()
    ids = {"co_a": co_a.id, "co_b": co_b.id, "task_ids": [t.id for t in tasks]}
    db.close()
    yield ids
    db = SessionLocal()
    db.execute(sql_text("DELETE FROM ponder_engagement WHERE company_id IN (:a, :b)"),
               {"a": ids["co_a"], "b": ids["co_b"]})
    db.execute(sql_text("DELETE FROM moc_task_catalog WHERE vertical = :v"), {"v": VERT})
    db.execute(sql_text("DELETE FROM moc_composition WHERE vertical = :v"), {"v": VERT})
    db.execute(sql_text("DELETE FROM moc_composition WHERE key LIKE 'maphome-onb-%'"))
    db.execute(sql_text("DELETE FROM users WHERE company_id IN (:a, :b)"),
               {"a": ids["co_a"], "b": ids["co_b"]})
    db.execute(sql_text("DELETE FROM companies WHERE id IN (:a, :b)"),
               {"a": ids["co_a"], "b": ids["co_b"]})
    db.execute(sql_text("DELETE FROM verticals WHERE slug = :v"), {"v": VERT})
    db.commit()
    db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


# ── 1. The deriver ──────────────────────────────────────────────────────


class TestAreaDeriver:
    def test_composition_opening_tasks_closing(self, db, world):
        s = build_area_ponder_script(db, vertical=VERT, area="Accounting")
        kinds = [b["kind"] for b in s["beats"]]
        assert kinds[0] == "opening"
        assert kinds[-1] == "closing"
        assert all(k == "task" for k in kinds[1:-1])
        assert len(kinds) == 2 + 3  # opening + 3 tasks + closing
        # The opening's derived-honest placeholder counts truthfully.
        assert "3 automations" in s["beats"][0]["derived_text"]

    def test_task_beat_is_the_card_as_story(self, db, world):
        s = build_area_ponder_script(db, vertical=VERT, area="Accounting")
        beat = s["beats"][1]
        assert "MapHome Task" in beat["text"]
        assert "Does the number-" in beat["text"]      # the essence (first sentence)
        assert "And more detail" not in beat["text"]   # honestly clipped
        assert "Daily" in beat["text"]                 # the prose frequency

    def test_closing_deep_links_the_area_page(self, db, world):
        s = build_area_ponder_script(db, vertical=VERT, area="Accounting")
        link = s["beats"][-1]["link"]
        assert link["href"] == "/bridgeable-map/Accounting"
        assert "Accounting" in link["label"]

    def test_large_area_clusters_honestly(self, db, world):
        extra_ids = []
        for i in range(12):
            t = MoCTaskCatalog(
                scope="vertical_default", vertical=VERT,
                name=f"MapHome Bulk {i} {uuid.uuid4().hex[:4]}", task_type="Bulk",
            )
            db.add(t)
            extra_ids.append(t)
        db.commit()
        try:
            s = build_area_ponder_script(db, vertical=VERT, area="Bulk")
            task_beats = [b for b in s["beats"] if b["kind"] == "task"]
            assert len(task_beats) == 11  # 10 + the cluster
            cluster = task_beats[-1]
            assert cluster["key"] == "task_cluster"
            assert "2 more" in cluster["text"]
        finally:
            db.execute(sql_text(
                "DELETE FROM moc_task_catalog WHERE vertical = :v AND task_type = 'Bulk'"
            ), {"v": VERT})
            db.commit()

    def test_authored_philosophy_overlays_and_clears(self, db, world):
        save_area_caption(db, vertical=VERT, area="Accounting",
                          beat_key="opening", text="The operator's philosophy.")
        s = build_area_ponder_script(db, vertical=VERT, area="Accounting")
        assert s["beats"][0]["text"] == "The operator's philosophy."
        assert s["beats"][0]["authored"] is True
        assert "3 automations" in s["beats"][0]["derived_text"]  # never stale
        save_area_caption(db, vertical=VERT, area="Accounting",
                          beat_key="opening", text=None)
        s2 = build_area_ponder_script(db, vertical=VERT, area="Accounting")
        assert s2["beats"][0]["authored"] is False  # plainer, never stale

    def test_orphaned_captions_surface(self, db, world):
        save_area_caption(db, vertical=VERT, area="Accounting",
                          beat_key="task:gone-task-id", text="orphan")
        s = build_area_ponder_script(db, vertical=VERT, area="Accounting")
        assert "task:gone-task-id" in s["orphaned_captions"]
        save_area_caption(db, vertical=VERT, area="Accounting",
                          beat_key="task:gone-task-id", text=None)

    def test_empty_area_refuses_honestly(self, db, world):
        with pytest.raises(AreaPonderError):
            build_area_ponder_script(db, vertical=VERT, area="Nothing Here")


# ── 2. Onboarding — the curriculum LIST ─────────────────────────────────


class TestOnboarding:
    def test_exemplar_renders_through_the_script_shape(self, db):
        s = build_onboarding_script(db, key="welcome-map")
        assert s["task_name"] == "Welcome to your Bridgeable Map"
        assert len(s["beats"]) == 5
        assert s["beats"][-1]["link"]["href"] == "/bridgeable-map"
        assert all(b["authored"] for b in s["beats"])

    def test_missing_composition_404_shaped(self, db):
        with pytest.raises(AreaPonderError):
            build_onboarding_script(db, key="never-authored")


# ── 3. Engagement — the quiet write ─────────────────────────────────────


class TestEngagement:
    def test_timestamps_set_once(self, db, world):
        uid = str(uuid.uuid4())
        r1 = eng.record(db, user_id=uid, company_id=world["co_a"],
                        ponder_key="task:x", event="viewed")
        first = r1.viewed_at
        r2 = eng.record(db, user_id=uid, company_id=world["co_a"],
                        ponder_key="task:x", event="viewed")
        assert r2.viewed_at == first  # a re-view is NOT a new first view
        assert r2.id == r1.id         # one row per (user, key)
        eng.record(db, user_id=uid, company_id=world["co_a"],
                   ponder_key="task:x", event="completed")
        db.refresh(r2)
        assert r2.completed_at is not None

    def test_invalid_event_rejected(self, db, world):
        with pytest.raises(eng.EngagementError):
            eng.record(db, user_id="u", company_id=world["co_a"],
                       ponder_key="k", event="glanced")


# ── 4. Suggestions — rules, whys, restraint ─────────────────────────────


def _mk_onb(db, sequence=-1):
    key = f"maphome-onb-{uuid.uuid4().hex[:6]}"
    db.add(MoCComposition(
        id=str(uuid.uuid4()), kind="onboarding", key=key,
        title="MapHome Exemplar", sequence=sequence,
        beats=[{"key": "a", "kind": "opening", "text": "hi"}],
    ))
    db.commit()
    return key


class TestSuggestions:
    def test_fresh_admin_sees_onboarding_first_with_why(self, db, world):
        key = _mk_onb(db)
        uid = str(uuid.uuid4())
        out = eng.build_suggestions(
            db, user_id=uid, company_id=world["co_a"], vertical=VERT,
            role_slug="admin", is_admin=True,
        )
        assert out[0]["rule"] == "onboarding"
        assert out[0]["ponder_key"] == f"onboarding:{key}"
        assert out[0]["why"]  # LOAD-BEARING — always present
        # every card carries a why
        assert all(s["why"] for s in out)

    def test_viewing_advances_the_onboarding_suggestion(self, db, world):
        key = _mk_onb(db)
        uid = str(uuid.uuid4())
        eng.record(db, user_id=uid, company_id=world["co_a"],
                   ponder_key=f"onboarding:{key}", event="viewed")
        out = eng.build_suggestions(
            db, user_id=uid, company_id=world["co_a"], vertical=VERT,
            role_slug="admin", is_admin=True,
        )
        assert all(s["ponder_key"] != f"onboarding:{key}" for s in out)

    def test_dismissal_respected_no_resurrection(self, db, world):
        key = _mk_onb(db)
        uid = str(uuid.uuid4())
        eng.record(db, user_id=uid, company_id=world["co_a"],
                   ponder_key=f"onboarding:{key}", event="dismissed")
        out = eng.build_suggestions(
            db, user_id=uid, company_id=world["co_a"], vertical=VERT,
            role_slug="admin", is_admin=True,
        )
        assert all(s["ponder_key"] != f"onboarding:{key}" for s in out)

    def test_non_admin_gets_no_onboarding_card(self, db, world):
        _mk_onb(db)
        out = eng.build_suggestions(
            db, user_id=str(uuid.uuid4()), company_id=world["co_a"],
            vertical=VERT, role_slug="office", is_admin=False,
        )
        assert all(s["rule"] != "onboarding" for s in out)

    def test_role_area_rule_with_honest_why(self, db, world):
        uid = str(uuid.uuid4())
        out = eng.build_suggestions(
            db, user_id=uid, company_id=world["co_a"], vertical=VERT,
            role_slug="accountant", is_admin=False,
        )
        card = next(s for s in out if s["rule"] == "role_area")
        assert card["ponder_key"] == f"area:{VERT}:Accounting"
        assert "Accounting" in card["why"]
        # viewed → retires
        eng.record(db, user_id=uid, company_id=world["co_a"],
                   ponder_key=f"area:{VERT}:Accounting", event="viewed")
        out2 = eng.build_suggestions(
            db, user_id=uid, company_id=world["co_a"], vertical=VERT,
            role_slug="accountant", is_admin=False,
        )
        assert all(s["rule"] != "role_area" for s in out2)

    def test_recency_rule_fires_on_change_since_view(self, db, world):
        uid = str(uuid.uuid4())
        task_id = world["task_ids"][0]
        eng.record(db, user_id=uid, company_id=world["co_a"],
                   ponder_key=f"task:{task_id}", event="viewed")
        # backdate the view, then bump the task — "changed since".
        db.execute(sql_text(
            "UPDATE ponder_engagement SET viewed_at = :t WHERE ponder_key = :k AND user_id = :u"
        ), {"t": datetime.now(timezone.utc) - timedelta(days=3),
            "k": f"task:{task_id}", "u": uid})
        db.execute(sql_text(
            "UPDATE moc_task_catalog SET updated_at = :t WHERE id = :i"
        ), {"t": datetime.now(timezone.utc), "i": task_id})
        db.commit()
        out = eng.build_suggestions(
            db, user_id=uid, company_id=world["co_a"], vertical=VERT,
            role_slug="office", is_admin=False,
        )
        card = next(s for s in out if s["rule"] == "recency")
        assert card["ponder_key"] == f"task:{task_id}"
        assert "changed" in card["why"]  # the honest why, weekday included

    def test_the_cap_and_empty_honesty(self, db, world):
        # A user who has seen everything: no onboarding (viewed), area viewed,
        # nothing changed → EMPTY, honestly.
        uid = str(uuid.uuid4())
        for comp in db.query(MoCComposition).filter(
            MoCComposition.kind == "onboarding"
        ).all():
            eng.record(db, user_id=uid, company_id=world["co_a"],
                       ponder_key=f"onboarding:{comp.key}", event="viewed")
        eng.record(db, user_id=uid, company_id=world["co_a"],
                   ponder_key=f"area:{VERT}:Accounting", event="viewed")
        out = eng.build_suggestions(
            db, user_id=uid, company_id=world["co_a"], vertical=VERT,
            role_slug="admin", is_admin=True,
        )
        assert out == []  # an empty rail beats a stretched one
        # and the cap holds structurally
        assert eng._MAX_SUGGESTIONS <= 5

    def test_engagement_is_per_user(self, db, world):
        key = _mk_onb(db)
        u1, u2 = str(uuid.uuid4()), str(uuid.uuid4())
        eng.record(db, user_id=u1, company_id=world["co_a"],
                   ponder_key=f"onboarding:{key}", event="viewed")
        out_u2 = eng.build_suggestions(
            db, user_id=u2, company_id=world["co_a"], vertical=VERT,
            role_slug="admin", is_admin=True,
        )
        # u1's view is u1's alone — u2 still gets an onboarding card (the
        # rule picks THEIR first unviewed; earlier tests may have seeded
        # sibling comps, so pin the rule, not the specific key).
        assert any(s["rule"] == "onboarding" for s in out_u2)
