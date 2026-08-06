"""The AREA OVERVIEW PONDER + onboarding compositions (The Map Home
campaign, commit sets 1 + 5) — the composition deriver born.

A new deriver feeding the SAME overlay (its source-agnostic contract
cashing): the script shape is byte-compatible with `build_ponder_script`'s
(beats with key/kind/text/derived_text/authored). Beat kinds are NEW —
`opening` (the authored philosophy), `task` (one short derived beat per
task: name · essence · prose frequency — the card content as story,
live-derived, never baked), `closing` (the deep link to the area page).

LARGE-AREA HONESTY: beyond `_TASK_BEAT_CAP` tasks the tail clusters into
one honest beat ("…and N more — explore the area page") — a shorter true
story beats an exhaustive slog.

AUTHORING: the philosophy layer is platform pedagogy — captions on the
`MoCComposition(kind='area')` row, edited in-ponder via the caption-editor
pattern, PLATFORM-ADMIN ONLY (tenants view, never author). Fallbacks are
derived-honest placeholders (plainer, never stale). Orphaned captions
surface via the same orphan block the task ponder uses.

ONBOARDING (kind='onboarding'): fully-authored beat sequences — a
curriculum LIST ordered by `sequence`, deliberately not an engine.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.moc_composition import MoCComposition

logger = logging.getLogger(__name__)

_TASK_BEAT_CAP = 10


# ── Cadence (MAP-3) ────────────────────────────────────────────────────────
#
# CADENCE WAS ALREADY DERIVED AND THE JOB BRANCH DROPPED IT. The
# automation branch below renders `when` per beat (the three-tier chain in
# `task_catalog.py`: the mirrored runtime Workflow's trigger when
# `schedule_authority == "runtime_scheduler"`, else the first active
# MoCTaskTrigger, else the manual `frequency` string). When Reframe R-2 made
# JOBS the map's face, the job branch was written without it — so an area
# whose jobs lead teaches WHAT runs and never WHEN.
#
# Grouping by grain rather than listing per job is also THE CAP FIX, not a
# side benefit: `_TASK_BEAT_CAP = 10` against Accounting's ELEVEN jobs means
# the area story already truncates one into "…and N more". Four grains fit.

_GRAIN_ORDER = ("continuous", "nightly", "weekly", "monthly", "other")

_GRAIN_LABEL = {
    "continuous": "Through the day",
    "nightly": "Overnight",
    "weekly": "Weekly",
    "monthly": "Monthly",
    "other": "On its own schedule",
}


def _job_cadences(db: Session, job) -> list[tuple[str, str]]:
    """Every `(grain, when_text)` this job's automations run on.

    Reads the SAME precedence the automation beat uses — one expression, two
    consumers, so a job's rhythm and its automation's rhythm cannot disagree.
    """
    from app.services.maps_of_content.jobs import resolve_job

    out: list[tuple[str, str]] = []
    for ref in resolve_job(db, job)["refs"]:
        if ref["kind"] != "automation":
            continue
        t = ref["automation"]
        when = (
            t.get("runtime_schedule_summary")
            if t.get("schedule_authority") == "runtime_scheduler"
            else (t.get("derived_frequency") or t.get("frequency"))
        )
        if when:
            out.append((_grain_of(str(when)), str(when).rstrip(".")))
    return out


def _grain_of(when: str) -> str:
    """Bucket a humanized schedule string into a rhythm an operator thinks in.

    DELIBERATELY COARSE. The clock times matter for one automation; the GRAIN
    is what a person plans around — "I work the queues in the morning" is a
    fact about overnight, not about 11:30 PM. Nine distinct times across the
    accounting jobs collapse to four grains.
    """
    w = when.lower()
    if "minute" in w or "hour" in w:
        return "continuous"
    if "monthly" in w or "1st" in w or "month" in w:
        return "monthly"
    if "weekly" in w or "week" in w:
        return "weekly"
    if "daily" in w or "every day" in w:
        return "nightly"
    return "other"


def _join_names(names: list[str]) -> str:
    """Oxford-comma join. A beat that reads as a sentence, at any count."""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def check_area_drift(beats: list[dict], captions: dict) -> list[str]:
    """Named divergences for the AREA generator — `check_mirror_drift`'s job,
    pointed at the one generator that had none.

    WHY THIS GENERATOR NEEDED IT MOST. `check_mirror_drift` (`ponder.py:288`)
    exists because "a mirror teaches its runtime source's story; if the runtime
    shape changes under the mirror, the ponder would silently teach the old
    story." It is called from exactly one site — the per-automation builder —
    and the AREA generator watched nothing. Cadence is the most
    schedule-coupled claim the Map can make, so authored prose sitting over
    derived times is precisely that failure shape, on the surface that was
    unguarded.

    ⚠️ THIS SURFACES FOR REVIEW; IT DOES NOT AUTO-DETECT STALENESS, and the
    distinction is the honest part. Detecting "this caption was written when the
    schedule said something else" needs the derived text AS OF AUTHORING, and
    captions store only the text. So the check reports every authored caption
    that sits on a schedule-derived beat, WITH the current derived text beside
    it — which is what a human comparing them actually needs. Claiming
    automatic detection here would be the same over-claim the cadence beat is
    disciplined against.

    Storing a derived-text hash alongside each caption would make it automatic
    and is a caption-shape change; deliberately not taken here.

    WARN, NEVER FAIL — `check_mirror_drift`'s contract. A stale caption is a
    content bug, not an outage, and a ponder that refused to render would
    replace a possibly-stale story with no story.
    """
    drift: list[str] = []
    live = {b["key"]: b for b in beats}

    for key in captions:
        if key not in live:
            drift.append(
                f"orphaned caption {key!r} — its beat no longer exists "
                "(reclaimable in the editor; never rendered to viewers)"
            )

    for key, beat in live.items():
        if not key.startswith("cadence:") or not beat.get("authored"):
            continue
        drift.append(
            f"schedule-coupled caption on {key!r} — authored text overrides a "
            f"DERIVED rhythm, which now reads: {beat.get('derived_text')!r}. "
            "Compare; the schedule may have moved under it."
        )
    return drift

class AreaPonderError(ValueError):
    pass


def _area_row(db: Session, *, vertical: str | None, area: str) -> MoCComposition | None:
    return (
        db.query(MoCComposition)
        .filter(
            MoCComposition.kind == "area",
            MoCComposition.key == area,
            MoCComposition.vertical == vertical,
            MoCComposition.is_active.is_(True),
        )
        .first()
    )


def _first_sentence(text: str | None, limit: int = 140) -> str | None:
    if not text:
        return None
    head = text.strip().split(". ")[0].strip().rstrip(".")
    if not head:
        return None
    if len(head) > limit:
        head = head[: limit - 1].rstrip() + "…"
    return head


def build_area_ponder_script(
    db: Session, *, vertical: str | None, area: str, company_id: str | None = None
) -> dict[str, Any]:
    """The area's staged walkthrough — philosophy → the tasks as story →
    the deep link. Live-derived from the SAME merged catalog the map reads
    (company_id scopes the merged view: their forks yield)."""
    from app.services.maps_of_content.task_catalog import resolve_task_catalog

    tasks = [
        t for t in resolve_task_catalog(db, vertical=vertical, tenant_id=company_id)
        if (t.get("task_type") or "General") == area
    ]
    if not tasks:
        raise AreaPonderError(f"No tasks in the {area} area")

    row = _area_row(db, vertical=vertical, area=area)
    captions: dict = dict((row.captions or {}) if row else {})

    beats: list[dict] = []

    def _beat(key: str, kind: str, derived: str, **extra) -> None:
        authored = captions.get(key)
        beats.append({
            "key": key, "kind": kind,
            "text": authored or derived,
            "derived_text": derived,
            "authored": bool(authored),
            **extra,
        })

    live_count = sum(
        1 for t in tasks
        if any(tr.get("is_live") for tr in (t.get("triggers") or []))
    )
    # THE MIDDLE'S population decides the OPENING's vocabulary too (Reframe
    # R-2: where jobs exist, the work leads — the opening speaks tasks with
    # the automations as the serving count; areas without jobs keep the
    # per-automation story as the honest fallback).
    from app.services.maps_of_content.jobs import list_jobs, resolve_job

    area_jobs = [
        j for j in list_jobs(db, vertical=vertical)
        if (j.task_type or "General") == area
    ]

    # THE OPENING — the philosophy (authored by the operator; shipped with a
    # derived-honest placeholder that never pretends to be pedagogy).
    if area_jobs:
        n_jobs = len(area_jobs)
        _beat(
            "opening", "opening",
            f"{area} — {n_jobs} task{'s' if n_jobs != 1 else ''} here, "
            f"worked by {len(tasks)} "
            f"{'automation' if len(tasks) == 1 else 'automations'}"
            + (f" ({live_count} live)" if live_count else "")
            + ". Bridgeable brings the work to one place; each task below "
            "can walk you through itself.",
        )
    else:
        _beat(
            "opening", "opening",
            f"{area} — {len(tasks)} "
            f"{'automation' if len(tasks) == 1 else 'automations'} run here"
            + (f", {live_count} live" if live_count else "")
            + ". Bridgeable brings the work to one place; each automation "
            "below can walk you through itself.",
        )
    if area_jobs:
        head_jobs = area_jobs[:_TASK_BEAT_CAP]
        for j in head_jobs:
            rj = resolve_job(db, j)
            n_auto = sum(1 for r in rj["refs"] if r["kind"] == "automation")
            n_surf = sum(1 for r in rj["refs"] if r["kind"] != "automation")
            parts = [j.name]
            essence = _first_sentence(j.description)
            if essence:
                parts.append(essence)
            glance = []
            if n_auto:
                glance.append(f"{n_auto} automation{'s' if n_auto != 1 else ''}")
            if n_surf:
                glance.append(f"{n_surf} surface{'s' if n_surf != 1 else ''}")
            if glance:
                parts.append(", ".join(glance))
            _beat(f"job:{j.id}", "task", ". ".join(parts) + ".")
        rest_jobs = len(area_jobs) - len(head_jobs)
        if rest_jobs > 0:
            _beat(
                "task_cluster", "task",
                f"…and {rest_jobs} more — the area page holds the whole list.",
            )

        # THE CADENCE BEATS — the area's RHYTHM, derived. One beat per grain
        # the jobs actually occupy, never per grain we think they should.
        #
        # ⚠️ WHAT IS DERIVED IS **WHEN**, AND ONLY WHEN. The beat says what runs
        # and how often, because both are read. It does NOT say what the
        # operator does with the result, and it does NOT say the month closes on
        # a clean queue — NOTHING ENFORCES THAT. Month-end close gates on the
        # PeriodLock and the statement-run conflict check, not on queue state.
        # A teaching surface asserting an unenforced constraint is the exact
        # failure the authored prose here is disciplined against, and it is the
        # easiest one to commit because the arc makes it feel true. Where a
        # story about consequence is wanted, it is AUTHORED over these beats
        # (captions) or DERIVED as a live count — never asserted.
        #
        # Jobs with NO derivable cadence are NAMED, not omitted. Four of
        # Accounting's eleven have no automations at all; they are things an
        # operator does rather than things the platform runs, and that is a fact
        # about the area worth teaching rather than a gap to paper over.
        by_grain: dict[str, list[str]] = {}
        rhythmless: list[str] = []
        for j in area_jobs:
            cadences = _job_cadences(db, j)
            if not cadences:
                rhythmless.append(j.name)
                continue
            for grain, _when in cadences:
                by_grain.setdefault(grain, [])
                if j.name not in by_grain[grain]:
                    by_grain[grain].append(j.name)

        for grain in _GRAIN_ORDER:
            names = by_grain.get(grain)
            if not names:
                continue
            _beat(
                f"cadence:{grain}", "task",
                f"{_GRAIN_LABEL[grain]} — {_join_names(names)}.",
            )

        if rhythmless:
            _beat(
                "cadence:none", "task",
                f"{_join_names(rhythmless)} run on no schedule — they are work "
                "you pick up, not work that arrives.",
            )
        # THE ENGINE ROOM'S collective mention — the automations, counted.
        _beat(
            "engine_room", "task",
            f"{len(tasks)} automation{'s' if len(tasks) != 1 else ''} serve "
            "these tasks — the engine room on the area page holds them.",
        )
    else:
        # ONE SHORT DERIVED BEAT PER AUTOMATION — the card content as story.
        head = tasks[:_TASK_BEAT_CAP]
        for t in head:
            essence = _first_sentence(t.get("description"))
            when = t.get("runtime_schedule_summary") if (
                t.get("schedule_authority") == "runtime_scheduler"
            ) else (t.get("derived_frequency") or t.get("frequency"))
            parts = [t["name"]]
            if essence:
                parts.append(essence)
            if when:
                parts.append(str(when).rstrip("."))
            _beat(f"task:{t['id']}", "task", ". ".join(parts) + ".")

        # LARGE-AREA HONESTY — the tail clusters, plainly counted.
        rest = len(tasks) - len(head)
        if rest > 0:
            _beat(
                "task_cluster", "task",
                f"…and {rest} more — the area page holds the whole list.",
            )

    # THE CLOSING — the deep link (the overlay renders `link`).
    _beat(
        "closing", "closing",
        f"Everything here lives on the {area} page — cards, schedules, and "
        "the walkthroughs.",
        link={
            "href": f"/bridgeable-map/{area}",
            "label": f"Open the {area} page",
        },
    )

    live_keys = {b["key"] for b in beats}
    orphaned = {k: v for k, v in captions.items() if k not in live_keys}

    # MAP-3 — the drift check the area generator never had. Warn + ride the
    # payload, exactly as the per-automation builder does with mirror drift.
    area_drift = check_area_drift(beats, captions)
    if area_drift:
        logger.warning(
            "[map] area ponder drift for %s/%s: %s", vertical, area,
            "; ".join(area_drift),
        )

    return {
        "task_id": f"area:{area}",
        "task_name": area,
        "workflow_name": "",
        "beats": beats,
        "orphaned_captions": orphaned,
        "drift": area_drift,
        "mirror_drift": [],
        "is_live": False,
        "vertical": vertical,
        "workflow_id": None,
        "fires": None,
        "task_scope": "platform_default",
        "owned": False,
        "schedule_authority": "moc",
    }


def save_area_caption(
    db: Session, *, vertical: str | None, area: str, beat_key: str, text: str | None
) -> dict[str, str]:
    """Author (or clear) one philosophy caption — platform pedagogy, stored
    on the composition row (created on first authoring). The task-ponder
    caption semantics verbatim: cleared falls back to derived; orphans
    reclaim via the same block. Caller is the ADMIN route only."""
    row = _area_row(db, vertical=vertical, area=area)
    if row is None:
        row = MoCComposition(
            id=str(uuid.uuid4()), kind="area", key=area, vertical=vertical,
        )
        db.add(row)
    captions = dict(row.captions or {})
    if text is None or not text.strip():
        captions.pop(beat_key, None)
    else:
        captions[beat_key] = text.strip()
    row.captions = captions  # reassign — JSONB change detection
    db.commit()
    return captions


# ── Onboarding compositions (the curriculum LIST) ────────────────────────


def list_onboarding(db: Session) -> list[MoCComposition]:
    return (
        db.query(MoCComposition)
        .filter(MoCComposition.kind == "onboarding", MoCComposition.is_active.is_(True))
        .order_by(MoCComposition.sequence, MoCComposition.key)
        .all()
    )


def build_onboarding_script(db: Session, *, key: str) -> dict[str, Any]:
    """An onboarding composition as a ponder script — beats fully authored
    on the row (`beats` JSONB), rendered through the same overlay."""
    row = (
        db.query(MoCComposition)
        .filter(
            MoCComposition.kind == "onboarding",
            MoCComposition.key == key,
            MoCComposition.is_active.is_(True),
        )
        .first()
    )
    if row is None or not row.beats:
        raise AreaPonderError("Onboarding composition not found")
    beats = [
        {
            "key": b.get("key", f"beat:{i}"),
            "kind": b.get("kind", "opening"),
            "text": b["text"],
            "derived_text": b["text"],
            "authored": True,
            **({"link": b["link"]} if b.get("link") else {}),
        }
        for i, b in enumerate(row.beats)
    ]
    return {
        "task_id": f"onboarding:{key}",
        "task_name": row.title or key,
        "workflow_name": "",
        "beats": beats,
        "orphaned_captions": {},
        "mirror_drift": [],
        "is_live": False,
        "vertical": None,
        "workflow_id": None,
        "fires": None,
        "task_scope": "platform_default",
        "owned": False,
        "schedule_authority": "moc",
    }
