"""BUILD AN AREA FROM NOTHING, so a cadence test tests the DERIVATION.

⚠️ WHY THIS EXISTS. MAP-3 and MAP-4's cadence tests originally asserted against
the seeded Accounting area — "overnight contains Bank reconciliation", "the
no-schedule group holds four jobs". Those pass on a database where someone once
adopted a schedule and fail everywhere else, which makes them a test of
`moc_task_trigger` having rows, NOT a test of the three-tier chain that turns a
schedule into a grain. It is the Cemetery Triage class exactly: a test that
depends on a runtime flow having run.

The distinction is not academic. The old shape **could not tell a broken
derivation from an empty one** — both render as no cards. That is the one thing
a derivation test has to distinguish.

WHAT THIS BUILDS AND WHY IT NEEDS NO RUNTIME STATE. `_job_cadences` reads a
three-step precedence:

    runtime_schedule_summary  (when schedule_authority == "runtime_scheduler")
    derived_frequency         (the first ACTIVE MoCTaskTrigger — ADOPT-PRODUCED)
    frequency                 (a plain column — last resort, and SEEDED)

Driving the third rung needs only rows. So these fixtures set `frequency`
explicitly, and the resulting test says: given THIS schedule string, the chain
produces THIS grain, on THIS card, with THIS clock time. No adopt, no
scheduler, no seeded content — the same result on any machine.

The area name is per-test and random, so a synthetic area can never collide
with real content or with another test running beside it.
"""
from __future__ import annotations

import uuid

from app.models.moc_job import MoCJob, MoCJobRef
from app.models.moc_task_catalog import MoCTaskCatalog

VERT = "manufacturing"


class SyntheticArea:
    """An area with jobs whose automations run on schedules YOU chose."""

    def __init__(self, db):
        self.db = db
        self.name = f"ZZTest-{uuid.uuid4().hex[:8]}"
        self._jobs: list[str] = []
        self._tasks: list[str] = []

    def job(self, name: str, *, schedules: list[str] | None = None) -> MoCJob:
        """A job carrying one automation per schedule string.

        `schedules=None` or `[]` makes a job NOTHING runs — the input to the
        "On your schedule" grouping, which otherwise can only be observed on a
        database that happens to have unautomated jobs.
        """
        job = MoCJob(
            scope="vertical_default", vertical=VERT, name=name,
            task_type=self.name, description=f"{name} — synthetic.",
            display_order=len(self._jobs), is_active=True,
        )
        self.db.add(job)
        self.db.flush()
        self._jobs.append(job.id)

        for i, when in enumerate(schedules or []):
            task = MoCTaskCatalog(
                scope="vertical_default", vertical=VERT,
                name=f"{name} automation {i}", task_type=self.name,
                # THE LEVER: the last rung of the precedence chain, and the only
                # one that is a plain column rather than runtime state.
                frequency=when,
                display_order=i, is_active=True,
            )
            self.db.add(task)
            self.db.flush()
            self._tasks.append(task.id)
            self.db.add(MoCJobRef(
                job_id=job.id, ref_kind="automation", ref_key=task.id,
                display_order=i,
            ))
        self.db.flush()
        return job

    def teardown(self) -> None:
        """Refs first — they FK both sides. Ordered, not cascaded, because this
        schema's cascade behaviour is uneven (the ratchet's own lesson)."""
        if self._jobs:
            self.db.query(MoCJobRef).filter(
                MoCJobRef.job_id.in_(self._jobs)
            ).delete(synchronize_session=False)
            self.db.query(MoCJob).filter(
                MoCJob.id.in_(self._jobs)
            ).delete(synchronize_session=False)
        if self._tasks:
            self.db.query(MoCTaskCatalog).filter(
                MoCTaskCatalog.id.in_(self._tasks)
            ).delete(synchronize_session=False)
        self.db.commit()


def representative(area, db) -> str:
    """One area spanning EVERY grain the vocabulary can produce, plus a job
    nothing runs.

    The seeded Accounting area happens to span four grains; this asserts the
    span instead of inheriting it, so a test about the collapse cannot pass
    because content coincidentally covered the cases. Nine distinct clock
    times, deliberately — that is the claim MAP-3 makes."""
    area.job("Sweeper", schedules=["Every 15 minutes"])
    area.job("Matcher", schedules=["Every day at 10:30 PM",
                                   "Every day at 11:00 PM"])
    area.job("Chaser", schedules=["Every day at 11:05 PM",
                                  "Every day at 11:30 PM"])
    area.job("Nightly", schedules=["Every day at 3:00 AM"])
    area.job("Weekly upkeep", schedules=["Weekly on Monday at 7:00 AM",
                                         "Weekly on Monday at 8:00 AM"])
    area.job("Close", schedules=["Monthly on the 1st at 6:00 AM"])
    area.job("Statements", schedules=["Monthly on the 1st at 6:30 AM"])
    area.job("By hand")
    db.commit()
    return area.name
