"""Reframe R-2 pins — the job ponder, the area re-point, the rail's 3b.

  * THE FEEDER — framing (derived-honest, caption-overlayable) →
    automation beats (essence + honest WHEN + the ponder deep-link) →
    queue beats (label + count clause + the /triage link) → closing;
    dead refs skip the story plainer (R-1's read semantics).
  * QUEUE-COUNT HONESTY — no user → no number (never a lie); the count
    clause only renders when the read was permission-honest.
  * THE AREA RE-POINT — jobs lead the beats where jobs exist (per-job
    lines + the engine-room mention + the carried cluster cap); areas
    without jobs keep the per-automation story (the honest fallback —
    test_map_home's suite pins it unchanged).
  * RULE 3b — job recency fires only where honest: a WALKED job whose
    linked automation changed since; the why names WHICH automation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.moc_job import MoCJob
from app.models.moc_task_catalog import MoCTaskCatalog
from app.services.maps_of_content import engagement as eng
from app.services.maps_of_content import jobs as jobs_svc
from app.services.maps_of_content.area_ponder import build_area_ponder_script
from app.services.maps_of_content.jobs import (
    build_job_ponder_script,
    save_job_caption,
)

VERT = f"reframe2-{uuid.uuid4().hex[:6]}"


@pytest.fixture(scope="module")
def world():
    db = SessionLocal()
    db.execute(sql_text(
        "INSERT INTO verticals (slug, display_name) VALUES (:v, :n) "
        "ON CONFLICT (slug) DO NOTHING"
    ), {"v": VERT, "n": "Reframe2 Test Vertical"})
    autos = []
    for i in range(2):
        t = MoCTaskCatalog(
            scope="vertical_default", vertical=VERT,
            name=f"R2 Automation {i} {uuid.uuid4().hex[:4]}",
            task_type="Accounting",
            description=f"Does thing {i} nightly. More detail follows.",
            frequency="Daily",
        )
        db.add(t)
        autos.append(t)
    db.flush()
    job = jobs_svc.create_job(
        db, name=f"R2 Job {uuid.uuid4().hex[:4]}", vertical=VERT,
        description="Keep the thing done. The person decides the edges.",
        task_type="Accounting",
    )
    jobs_svc.add_ref(db, job_id=job.id, ref_kind="automation", ref_key=autos[0].id)
    jobs_svc.add_ref(
        db, job_id=job.id, ref_kind="triage_queue",
        ref_key="cash_receipts_matching_triage", display_order=1,
    )
    db.commit()
    ids = {
        "job_id": job.id, "job_name": job.name,
        "auto_ids": [a.id for a in autos], "auto0_name": autos[0].name,
    }
    db.close()
    yield ids
    db = SessionLocal()
    db.execute(sql_text(
        "DELETE FROM moc_job_ref WHERE job_id IN (SELECT id FROM moc_job WHERE vertical = :v)"
    ), {"v": VERT})
    db.execute(sql_text("DELETE FROM moc_job WHERE vertical = :v"), {"v": VERT})
    db.execute(sql_text("DELETE FROM moc_task_catalog WHERE vertical = :v"), {"v": VERT})
    db.execute(sql_text("DELETE FROM ponder_engagement WHERE ponder_key LIKE 'job:%' AND company_id = 'r2-co'"))
    db.execute(sql_text("DELETE FROM verticals WHERE slug = :v"), {"v": VERT})
    db.commit()
    db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


# ── 1. The feeder ───────────────────────────────────────────────────────


class TestJobPonderFeeder:
    def test_composition_and_beat_kinds(self, db, world):
        s = build_job_ponder_script(db, job_id=world["job_id"])
        kinds = [b["kind"] for b in s["beats"]]
        assert kinds[0] == "opening"
        assert "task" in kinds          # the automation beat
        assert "downstream" in kinds    # the queue beat
        assert kinds[-1] == "closing"
        assert s["task_id"] == f"job:{world['job_id']}"

    def test_framing_placeholder_counts_honestly(self, db, world):
        s = build_job_ponder_script(db, job_id=world["job_id"])
        opening = s["beats"][0]
        assert "1 automation and 1 review surface work this job" in opening["derived_text"]
        assert "Keep the thing done" in opening["derived_text"]

    def test_automation_beat_carries_the_ponder_deep_link(self, db, world):
        s = build_job_ponder_script(db, job_id=world["job_id"])
        auto_beat = next(b for b in s["beats"] if b["key"].startswith("automation:"))
        assert world["auto0_name"] in auto_beat["text"]
        assert "Does thing 0 nightly" in auto_beat["text"]   # essence
        assert "Daily" in auto_beat["text"]                  # honest WHEN
        assert auto_beat["ponder_ref"]["overlay_id"] == world["auto_ids"][0]

    def test_queue_beat_no_user_no_count_clause(self, db, world):
        # PERMISSION HONESTY: without a user the count is unknowable — the
        # beat says where exceptions land, never a number it can't stand by.
        s = build_job_ponder_script(db, job_id=world["job_id"])
        q = next(b for b in s["beats"] if b["key"].startswith("queue:"))
        assert "where the exceptions land" in q["text"]
        assert "waiting" not in q["text"]
        assert q["link"]["href"] == "/triage/cash_receipts_matching_triage"

    def test_framing_caption_overlays_and_clears(self, db, world):
        save_job_caption(db, job_id=world["job_id"], beat_key="opening",
                         text="The operator's framing.")
        s = build_job_ponder_script(db, job_id=world["job_id"])
        assert s["beats"][0]["text"] == "The operator's framing."
        assert s["beats"][0]["authored"] is True
        save_job_caption(db, job_id=world["job_id"], beat_key="opening", text=None)
        s2 = build_job_ponder_script(db, job_id=world["job_id"])
        assert s2["beats"][0]["authored"] is False  # plainer, never stale

    def test_dead_ref_skips_the_story(self, db, world):
        # Kill the second automation after linking it — the beat vanishes
        # plainer; the closing still stands.
        doomed = db.get(MoCTaskCatalog, world["auto_ids"][1])
        ref = jobs_svc.add_ref(
            db, job_id=world["job_id"], ref_kind="automation", ref_key=doomed.id,
        )
        db.commit()
        doomed.is_active = False
        db.commit()
        db.expire_all()
        s = build_job_ponder_script(db, job_id=world["job_id"])
        assert all(
            b["key"] != f"automation:{doomed.id}" for b in s["beats"]
        )
        # restore for the other tests — the target AND the fixture's ref
        # census (order-decoupled: later tests count this job's refs).
        doomed.is_active = True
        jobs_svc.remove_ref(db, ref_id=ref.id)
        db.commit()


# ── 2. The area re-point ────────────────────────────────────────────────


class TestAreaRePoint:
    def test_jobs_lead_the_area_beats_with_the_engine_room_mention(self, db, world):
        s = build_area_ponder_script(db, vertical=VERT, area="Accounting")
        keys = [b["key"] for b in s["beats"]]
        assert f"job:{world['job_id']}" in keys
        assert "engine_room" in keys
        assert not any(k.startswith("task:") for k in keys)  # jobs lead
        job_beat = next(b for b in s["beats"] if b["key"] == f"job:{world['job_id']}")
        assert world["job_name"] in job_beat["text"]
        assert "1 automation" in job_beat["text"]
        assert "1 surface" in job_beat["text"]
        engine = next(b for b in s["beats"] if b["key"] == "engine_room")
        assert "2 automations serve these tasks" in engine["text"]
        # THE OPENING re-points too — tasks lead the vocabulary; the
        # automations are the serving count (witness-caught: it used to
        # keep the pure-automation line while the beats spoke jobs).
        opening = s["beats"][0]
        assert "1 task here" in opening["derived_text"]
        assert "worked by 2 automations" in opening["derived_text"]
        assert "each task below" in opening["derived_text"]

    def test_the_cluster_cap_carries_to_jobs(self, db, world):
        extra = []
        for i in range(12):
            j = jobs_svc.create_job(
                db, name=f"R2 Bulk Job {i} {uuid.uuid4().hex[:4]}",
                vertical=VERT, task_type="Accounting",
            )
            extra.append(j)
        db.commit()
        try:
            s = build_area_ponder_script(db, vertical=VERT, area="Accounting")
            job_beats = [b for b in s["beats"] if b["key"].startswith("job:")]
            assert len(job_beats) == 10  # the cap
            cluster = next(b for b in s["beats"] if b["key"] == "task_cluster")
            assert "3 more" in cluster["text"]  # 13 jobs − 10
        finally:
            for j in extra:
                db.execute(sql_text("DELETE FROM moc_job WHERE id = :i"), {"i": j.id})
            db.commit()


# ── 3. Rule 3b — job recency, only where honest ─────────────────────────


class TestJobRecency:
    def test_walked_job_with_changed_automation_suggests_naming_it(self, db, world):
        uid = str(uuid.uuid4())
        eng.record(db, user_id=uid, company_id="r2-co",
                   ponder_key=f"job:{world['job_id']}", event="viewed")
        db.execute(sql_text(
            "UPDATE ponder_engagement SET viewed_at = :t WHERE user_id = :u"
        ), {"t": datetime.now(timezone.utc) - timedelta(days=2), "u": uid})
        db.execute(sql_text(
            "UPDATE moc_task_catalog SET updated_at = :t WHERE id = :i"
        ), {"t": datetime.now(timezone.utc), "i": world["auto_ids"][0]})
        db.commit()
        out = eng.build_suggestions(
            db, user_id=uid, company_id="r2-co", vertical=VERT,
            role_slug="office", is_admin=False,
        )
        card = next(s for s in out if s["rule"] == "job_recency")
        assert card["ponder_key"] == f"job:{world['job_id']}"
        assert world["auto0_name"] in card["why"]  # WHICH automation, named

    def test_unwalked_job_never_nudges(self, db, world):
        out = eng.build_suggestions(
            db, user_id=str(uuid.uuid4()), company_id="r2-co", vertical=VERT,
            role_slug="office", is_admin=False,
        )
        assert all(s["rule"] != "job_recency" for s in out)
