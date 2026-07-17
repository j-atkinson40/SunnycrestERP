"""Reframe R-1 pins — the job entity, the polymorphic spine, the seed.

  * OPTION A TIERS — platform/vertical only; a tenant-tier write is refused
    (B/C arrive by their own migration, not by accident).
  * THE WRITE BOUNDARY — refs existence-checked PER KIND at write; a
    dangling write refuses loudly.
  * DEAD-REF HONESTY — resolution SKIPS refs that died after writing
    (plainer, never stale) and surfaces them in dead_refs (the reclaim
    list for edit surfaces).
  * THE SEED — preserve-aware to the sunnycrest standard: an existing job
    is untouched WHOLLY (fields + refs, including deliberate removals).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text as sql_text

from app.database import SessionLocal
from app.models.moc_job import MoCJob
from app.models.moc_task_catalog import MoCTaskCatalog
from app.services.maps_of_content import jobs as jobs_svc
from app.services.maps_of_content.jobs import JobValidationError

VERT = f"reframe-{uuid.uuid4().hex[:6]}"


@pytest.fixture(scope="module")
def world():
    db = SessionLocal()
    db.execute(sql_text(
        "INSERT INTO verticals (slug, display_name) VALUES (:v, :n) "
        "ON CONFLICT (slug) DO NOTHING"
    ), {"v": VERT, "n": "Reframe Test Vertical"})
    auto = MoCTaskCatalog(
        scope="vertical_default", vertical=VERT,
        name=f"Reframe Automation {uuid.uuid4().hex[:4]}",
        description="A synthetic automation.",
    )
    db.add(auto)
    db.commit()
    ids = {"automation_id": auto.id, "automation_name": auto.name}
    db.close()
    yield ids
    db = SessionLocal()
    db.execute(sql_text(
        "DELETE FROM moc_job_ref WHERE job_id IN "
        "(SELECT id FROM moc_job WHERE vertical = :v)"
    ), {"v": VERT})
    db.execute(sql_text("DELETE FROM moc_job WHERE vertical = :v"), {"v": VERT})
    db.execute(sql_text("DELETE FROM moc_task_catalog WHERE vertical = :v"), {"v": VERT})
    db.execute(sql_text("DELETE FROM verticals WHERE slug = :v"), {"v": VERT})
    db.commit()
    db.close()


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


def _mk_job(db, name=None):
    job = jobs_svc.create_job(
        db, name=name or f"Reframe Job {uuid.uuid4().hex[:6]}",
        vertical=VERT, description="A synthetic job.",
    )
    db.commit()
    return job


# ── 1. Tiers — option A, no accidents ───────────────────────────────────


class TestTiers:
    def test_vertical_requires_vertical(self, db, world):
        with pytest.raises(JobValidationError, match="requires its vertical"):
            jobs_svc.create_job(db, name="X", scope="vertical_default", vertical=None)

    def test_platform_is_vertical_less(self, db, world):
        with pytest.raises(JobValidationError, match="vertical-less"):
            jobs_svc.create_job(db, name="X", scope="platform_default", vertical=VERT)

    def test_tenant_tier_refused_until_its_own_migration(self, db, world):
        with pytest.raises(JobValidationError, match="not a job tier"):
            jobs_svc.create_job(
                db, name="X", scope="tenant_override", vertical=VERT,
            )

    def test_duplicate_name_in_scope_refused(self, db, world):
        job = _mk_job(db)
        with pytest.raises(JobValidationError, match="already exists"):
            jobs_svc.create_job(db, name=job.name, vertical=VERT)


# ── 2. The write boundary — per-kind existence ──────────────────────────


class TestWriteBoundary:
    def test_automation_ref_must_resolve(self, db, world):
        job = _mk_job(db)
        ref = jobs_svc.add_ref(
            db, job_id=job.id, ref_kind="automation",
            ref_key=world["automation_id"],
        )
        db.commit()
        assert ref.id
        with pytest.raises(JobValidationError, match="does not resolve"):
            jobs_svc.add_ref(
                db, job_id=job.id, ref_kind="automation", ref_key="never-a-row",
            )

    def test_triage_queue_ref_must_be_a_platform_queue(self, db, world):
        job = _mk_job(db)
        ref = jobs_svc.add_ref(
            db, job_id=job.id, ref_kind="triage_queue",
            ref_key="cash_receipts_matching_triage",
        )
        db.commit()
        assert ref.id
        with pytest.raises(JobValidationError, match="does not resolve"):
            jobs_svc.add_ref(
                db, job_id=job.id, ref_kind="triage_queue", ref_key="no_such_queue",
            )

    def test_focus_ref_must_resolve_by_slug(self, db, world):
        job = _mk_job(db)
        with pytest.raises(JobValidationError, match="does not resolve"):
            jobs_svc.add_ref(
                db, job_id=job.id, ref_kind="focus", ref_key="never-a-slug",
            )

    def test_unknown_kind_refused(self, db, world):
        job = _mk_job(db)
        with pytest.raises(JobValidationError, match="ref_kind"):
            jobs_svc.add_ref(
                db, job_id=job.id, ref_kind="document", ref_key="x",
            )


# ── 3. Dead-ref honesty — skip for viewers, reclaim for editors ─────────


class TestDeadRefs:
    def test_deliberately_dangled_ref_skips_and_surfaces(self, db, world):
        # The witness: write a VALID automation ref, then kill the target —
        # decay AFTER the write is the read side's problem, handled honestly.
        auto = MoCTaskCatalog(
            scope="vertical_default", vertical=VERT,
            name=f"Reframe Doomed {uuid.uuid4().hex[:4]}",
        )
        db.add(auto)
        db.commit()
        job = _mk_job(db)
        ref = jobs_svc.add_ref(
            db, job_id=job.id, ref_kind="automation", ref_key=auto.id,
        )
        db.commit()
        auto.is_active = False  # the target dies after the fact
        db.commit()

        db.expire_all()
        resolved = jobs_svc.resolve_job(db, db.get(MoCJob, job.id))
        assert all(r["key"] != auto.id for r in resolved["refs"])  # skipped
        assert resolved["dead_refs"] == [
            {"id": ref.id, "kind": "automation", "key": auto.id}
        ]  # reclaimable

    def test_live_queue_ref_resolves_with_label_and_href(self, db, world):
        job = _mk_job(db)
        jobs_svc.add_ref(
            db, job_id=job.id, ref_kind="triage_queue",
            ref_key="month_end_close_triage",
        )
        db.commit()
        resolved = jobs_svc.resolve_job(db, db.get(MoCJob, job.id))
        q = next(r for r in resolved["refs"] if r["kind"] == "triage_queue")
        assert q["label"]
        assert q["href"] == "/triage/month_end_close_triage"


# ── 4. The seed — preserve-aware to the sunnycrest standard ─────────────


class TestSeedPreserveAware:
    def test_existing_job_wholly_untouched_including_ref_removals(self, db, monkeypatch, world):
        import scripts.seed_accounting_jobs as seed

        auto_name = world["automation_name"]
        monkeypatch.setattr(seed, "VERT", VERT)
        monkeypatch.setattr(seed, "SKELETON", [(
            "Reframe Seed Job",
            "The proposed framing.",
            [("automation", auto_name, 0),
             ("triage_queue", "ar_collections_triage", 1)],
        )])
        assert seed.main() == 0
        job = (
            db.query(MoCJob)
            .filter(MoCJob.vertical == VERT, MoCJob.name == "Reframe Seed Job")
            .one()
        )
        assert len(job.refs) == 2

        # THE OPERATOR AUTHORS: rewrite the framing + deliberately remove a ref.
        job.description = "The operator's own words."
        db.commit()
        jobs_svc.remove_ref(db, ref_id=job.refs[0].id)
        db.commit()

        assert seed.main() == 0  # the boot re-run
        db.expire_all()
        job2 = db.get(MoCJob, job.id)
        assert job2.description == "The operator's own words."  # preserved
        assert len(job2.refs) == 1  # the removal RESPECTED — not re-added

    def test_absent_automation_ref_skips_never_dangles(self, db, monkeypatch, world):
        import scripts.seed_accounting_jobs as seed

        monkeypatch.setattr(seed, "VERT", VERT)
        monkeypatch.setattr(seed, "SKELETON", [(
            "Reframe Ghost Job", "x",
            [("automation", "No Such Automation Anywhere", 0)],
        )])
        assert seed.main() == 0
        job = (
            db.query(MoCJob)
            .filter(MoCJob.vertical == VERT, MoCJob.name == "Reframe Ghost Job")
            .one()
        )
        assert job.refs == []  # skipped honestly — never a dangling write
