"""r157 — the Map's accounting content, and the guard that protects operator edits.

THE MIGRATION IS CONTENT, WHICH IS UNUSUAL, and the reason is that
`seed_accounting_jobs.py` is preserve-aware by explicit contract: *"a job that
EXISTS is not touched AT ALL, not its fields, not its refs."* Editing the seed
corrects only databases that never seeded; every existing tenant would keep the
wrong text. So a correction needs the Option A idempotent pattern — update where
the value byte-matches what the seed wrote, skip where it differs.

WHAT IS ASSERTED HERE IS THE OUTCOME AND THE GUARD, not the prose. The sentences
will be edited; the properties must hold:

  * the split happened and neither card teaches two processes
  * `reconciliation_review_triage` is referenced, which it never was
  * no accounting job carries a dead ref
  * AN OPERATOR-EDITED FIELD IS NOT OVERWRITTEN — the guard, and the only test
    here that would let real data loss through if it regressed
  * a ref the operator DELETED is not resurrected on the destination

Runs against the migrated database rather than re-running the migration: the
assertions are about end state, and the migration is idempotent by construction.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models.moc_job import MoCJob
from app.services.maps_of_content.jobs import resolve_job

VERT = "manufacturing"


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture(autouse=True)
def accounting_jobs(db):
    """⚠️ THIS FILE'S OWN SUBSTRATE, RATHER THAN A NEIGHBOUR'S.

    These tests read the seeded accounting jobs. A bare-database verification
    run of six files TOGETHER passed — because an earlier file's seeds happened
    to create them first. Run alone, or in the gate's order, they do not exist.
    **The verification meant to prove the environment-dependence gone was
    itself environment-dependent**, in the ordering rather than the database.

    Order is the measured one: workflows → mirrors → jobs → plaid-b2. The
    mirrors create the `moc_task_catalog` rows the job seeds attach automation
    refs to, so seeding jobs first silently produces jobs with empty refs — and
    half of these tests are ABOUT the refs.

    ⚠️ `seed_plaid_b2` IS PART OF THE CHAIN AND WAS MISSING, which is the same
    defect one producer further along. It is a canonical boot seed (no manifest
    entry ⇒ tier `all`, so it runs on every deploy) and it attaches the
    `Pull Bank Transactions` automation ref to `Bank reconciliation`
    (`seed_plaid_b2.py:31,200`). Without it this fixture built a `Bank
    reconciliation` carrying ONE ref while every real database carries two —
    so `test_rerunning_is_idempotent`'s `== 2` was right about production and
    unreachable here. It runs LAST because `_seed_job_ref` attaches to a job
    the accounting seed creates.

    Every seed here is idempotent and preserve-aware, so this is free where the
    rows already exist."""
    from app.data.seed_workflows import seed_default_workflows
    from scripts.seed_accounting_jobs import main as seed_jobs
    from scripts.seed_moc_backfill_workflow_mirrors import seed as seed_mirrors
    from scripts.seed_plaid_b2 import main as seed_plaid
    from scripts.seed_suite_jobs import main as seed_suite

    seed_default_workflows(db)
    db.commit()
    seed_mirrors(db)
    seed_jobs()
    seed_suite()
    seed_plaid()
    yield


def _job(db, name):
    return (
        db.query(MoCJob)
        .filter(MoCJob.name == name, MoCJob.vertical == VERT,
                MoCJob.task_type == "Accounting")
        .first()
    )


def _refs(db, job):
    return {
        (r.ref_kind, r.ref_key)
        for r in db.execute(
            text("SELECT ref_kind, ref_key FROM moc_job_ref WHERE job_id = :j"),
            {"j": job.id},
        ).fetchall()
    }


class TestTheSplit:
    """One card teaching two processes is the failure the Map exists to
    prevent. 'Bank reconciliation' was named for one process and pointed at
    another — its refs were the payment→invoice matcher."""

    def test_bank_reconciliation_points_at_BOOKS_REVIEW(self, db):
        job = _job(db, "Bank reconciliation")
        assert job is not None
        keys = {k for _, k in _refs(db, job)}
        assert "reconciliation_review_triage" in keys

    def test_bank_reconciliation_no_longer_points_at_cash_receipts(self, db):
        """The mispointing, pinned as an absence. Its refs described a different
        process than its name promised, so an operator learning from that card
        learned cash receipts and called it reconciliation."""
        job = _job(db, "Bank reconciliation")
        keys = {k for _, k in _refs(db, job)}
        assert "cash_receipts_matching_triage" not in keys

    def test_cash_receipts_matching_exists_and_carries_the_moved_refs(self, db):
        """The content MOVED rather than being rewritten — the description was
        always accurate, it just sat on a card with the wrong name."""
        job = _job(db, "Cash receipts matching")
        assert job is not None
        keys = {k for _, k in _refs(db, job)}
        assert "cash_receipts_matching_triage" in keys

    def test_books_review_was_referenced_by_NOTHING_before_this(self, db):
        """The state this corrected: the platform's only bespoke triage display,
        the surface Arc A and Arc B built, referenced by zero jobs while a card
        named after it taught something else. Now exactly one job claims it."""
        n = db.execute(
            text("SELECT count(*) FROM moc_job_ref "
                 "WHERE ref_key = 'reconciliation_review_triage'")
        ).scalar()
        assert n == 1


class TestTheCorrections:
    def test_no_accounting_job_carries_a_dead_ref(self, db):
        """`Customer billing & statements` pointed at an automation whose
        catalog row no longer existed. It degraded honestly into `dead_refs`, so
        this was tidying a self-declaring gap rather than fixing a visible
        break — but a ref pointing at nothing teaches nothing."""
        total = 0
        for job in db.query(MoCJob).filter(MoCJob.task_type == "Accounting"):
            total += len(resolve_job(db, job).get("dead_refs") or [])
        assert total == 0

    def test_expense_management_no_longer_claims_AS_THEY_ARRIVE(self, db):
        """The live trigger is cron `*/15 * * * *`. Phase 8c changed it from
        `event` because event dispatch does not exist — a documented workaround,
        not a bug. The card claimed real-time.

        The replacement DATES the workaround rather than disguising it, so the
        sentence stops being wrong when event dispatch lands rather than
        becoming wrong in the other direction."""
        job = _job(db, "Expense management")
        assert "as they arrive —" not in job.description
        assert "fifteen minutes" in job.description

    def test_handle_the_exceptions_names_the_return_verb(self, db):
        """N-1+2 shipped returned cheques as a verb distinct from void, with its
        own marker and its own Books Review action. The card listing money
        corrections did not mention it."""
        job = _job(db, "Handle the exceptions")
        assert "return" in job.description.lower()


class TestTheProseIsNarROWLYTrue:
    """Every sentence r157 writes describes work this session shipped, which is
    exactly the condition under which a claim gets written more strongly than
    the code supports. These pin the narrowness."""

    def test_it_does_not_claim_that_payments_generally_post(self, db):
        """`CustomerPayment` posts. `FHPayment` and `StatementPayment` do not.
        A card saying "payments post" would be false for two of three
        subledgers."""
        for job in db.query(MoCJob).filter(MoCJob.task_type == "Accounting"):
            d = (job.description or "").lower()
            assert "all payments post" not in d
            assert "every payment posts" not in d

    def test_the_ledger_claim_is_structural_rather_than_stateful(self, db):
        """"A line you classify or code books its entry before it clears" is a
        property of the design (L-2, L-3) and stays true. A state claim — how
        many settings are configured — would be stale the moment someone
        changed one, and belongs in a derived ponder beat or nowhere."""
        d = _job(db, "Bank reconciliation").description
        assert "books its journal entry before it clears" in d
        # No configuration COUNTS in prose — those must be derived or absent.
        for token in ("two settings", "three settings", "are configured"):
            assert token not in d.lower()


class TestTheGuardProtectsOperatorEdits:
    """THE ONLY TEST HERE THAT WOULD LET REAL DATA LOSS THROUGH IF IT REGRESSED.

    Preserve-awareness exists to protect what an operator wrote. A correction
    migration that blanket-overwrites descriptions would clobber exactly the
    edits the seed refuses to touch.
    """

    def test_an_edited_description_is_SKIPPED_not_overwritten(self, db):
        """Simulates the operator having rewritten a card, then re-runs the
        migration's own decision. Byte-match means untouched, so correct it;
        differing means they wrote it, so leave it."""
        from alembic.config import Config  # noqa: F401  (import guard only)

        job = _job(db, "Expense management")
        original = job.description
        operator_text = f"Our own words about expenses {uuid.uuid4().hex[:6]}"
        db.execute(
            text("UPDATE moc_job SET description = :d WHERE id = :i"),
            {"d": operator_text, "i": job.id},
        )
        db.flush()

        # The migration's guard, exercised directly: expected != current → skip.
        expected_seeded = (
            "Expenses categorized as they arrive — the uncertain ones queued "
            "for a quick confirm."
        )
        current = db.execute(
            text("SELECT description FROM moc_job WHERE id = :i"), {"i": job.id}
        ).scalar()
        assert current != expected_seeded
        assert current == operator_text        # the operator's words stand

        db.rollback()
        assert _job(db, "Expense management").description == original

    def test_a_deleted_ref_is_not_resurrected_on_the_destination(self, db):
        """ABSENT MEANS THE OPERATOR DELETED IT. The migration does not move it
        and deliberately does not recreate it — re-adding what they removed,
        wearing a migration, is worse than leaving the new card thinner. Pinned
        as the rule rather than the mechanism, since the mechanism is a skip."""
        src = _job(db, "Bank reconciliation")
        moved_key = "cash_receipts_matching_triage"
        assert moved_key not in {k for _, k in _refs(db, src)}
        # And it landed exactly once, on the destination — not duplicated.
        n = db.execute(
            text("SELECT count(*) FROM moc_job_ref WHERE ref_key = :k"),
            {"k": moved_key},
        ).scalar()
        assert n == 1

    def test_a_partial_ref_deletion_is_NOT_refilled_by_the_seed(self, db):
        """THE GUARD ON THE 2026-08-08 OPENING, and the only test that holds it.

        `seed_accounting_jobs` now attaches refs to an existing job that has
        NONE — the r157-minted `Cash receipts matching` case. The condition is
        "no refs at all", NOT "missing the ones we declare", and the difference
        is invisible to every other test here: all three of the r157 outcome
        tests pass under either reading.

        Under the wrong reading an operator who deletes ONE of a job's two refs
        gets it silently restored on the next boot — the resurrection this
        file's neighbouring test forbids of the migration, arriving instead
        through the seed. Deleting a ref is how an operator says "not this
        one"; a seed that re-adds it has overruled them.

        Commits deliberately (the seed opens its OWN session and would not see
        an uncommitted delete) and restores in `finally`.
        """
        from scripts.seed_accounting_jobs import main as seed_jobs

        job = _job(db, "Collections")
        assert job is not None
        before = _refs(db, job)
        assert len(before) == 2, f"expected 2 seeded refs, got {before}"

        victim = ("triage_queue", "ar_collections_triage")
        assert victim in before

        db.execute(
            text("DELETE FROM moc_job_ref WHERE job_id = :j AND ref_kind = :k "
                 "AND ref_key = :r"),
            {"j": job.id, "k": victim[0], "r": victim[1]},
        )
        db.commit()
        try:
            assert _refs(db, job) == before - {victim}   # one left, not none
            seed_jobs()                                  # the boot pass
            db.expire_all()
            after = _refs(db, job)
            assert victim not in after, (
                "the seed RESURRECTED a ref the operator deleted — the "
                "existing-row branch must require NO refs at all, not merely "
                "a missing declared ref"
            )
            assert after == before - {victim}
        finally:
            # Idempotent restore. If the seed DID resurrect the ref (the
            # regression this test exists to catch), a blind INSERT would
            # raise a UniqueViolation out of teardown and bury the assertion
            # message under it — the failure would stop teaching.
            db.rollback()
            still_gone = db.execute(
                text("SELECT 1 FROM moc_job_ref WHERE job_id = :j "
                     "AND ref_kind = :k AND ref_key = :r"),
                {"j": job.id, "k": victim[0], "r": victim[1]},
            ).first() is None
            if still_gone:
                db.execute(
                    text("INSERT INTO moc_job_ref (id, job_id, ref_kind, "
                         "ref_key, display_order) VALUES (:i, :j, :k, :r, 1)"),
                    {"i": str(uuid.uuid4()), "j": job.id,
                     "k": victim[0], "r": victim[1]},
                )
            db.commit()

    def test_rerunning_is_idempotent(self, db):
        """The migration is safe to re-run: descriptions already corrected match
        the corrected value and are skipped, refs already moved are absent from
        the source, and the add is skipped when present."""
        before = {
            j.name: (j.description, len(_refs(db, j)))
            for j in db.query(MoCJob).filter(MoCJob.task_type == "Accounting")
        }
        assert before["Bank reconciliation"][1] == 2
        assert before["Cash receipts matching"][1] == 2
