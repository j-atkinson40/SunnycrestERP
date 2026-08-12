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
import re as _re
import uuid
from typing import Any, NamedTuple

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


class _Cadence(NamedTuple):
    """One automation's rhythm, plus what liveness needs to judge it. MAP-5.

    A NAMED shape rather than more tuple positions, because the fields serve two
    concerns — the first two describe WHEN, the rest describe WHETHER — and a
    five-position tuple would hide that at every call site.
    """

    grain: str
    when: str
    automation: str
    runtime_workflow_id: str | None
    live_whens: tuple[str, ...]
    dry_whens: tuple[str, ...]


def _job_cadences(db: Session, job) -> list[_Cadence]:
    """Every rhythm this job's automations run on, with liveness inputs.

    ⚠️ THIS DOCSTRING USED TO CLAIM "one expression, two consumers, so a job's
    rhythm and its automation's rhythm cannot disagree." THAT WAS FALSE, and it
    was believed — the precedence below is COPY-PASTED IN THREE PLACES:

        area_ponder.py::_job_cadences   (here)
        area_ponder.py                  (the automation beat)
        jobs.py                         (the job's own refs)

    Semantically identical, textually different: three formattings, two variable
    names. So the invariant that comment named is MANUAL, not mechanical —
    nothing detects the three drifting apart, and whoever updates one gets no
    signal that two others exist.

    A false claim in the place someone would look to check it is the same shape
    as `_deliberately_broken` asserting bulk dispatch did not exist. Recorded
    rather than quietly fixed: consolidating the three is its own pass, and it
    wants a TEST asserting they agree, not a comment claiming they do.

    ⚠️ ONLY THIS SITE IS WIDENED. The other two build a `when` string for a beat
    line and need none of the liveness fields — widening them would hand unused
    data to consumers that never read it.
    """
    from app.services.maps_of_content.jobs import resolve_job

    out: list[_Cadence] = []
    for ref in resolve_job(db, job)["refs"]:
        if ref["kind"] != "automation":
            continue
        t = ref["automation"]
        when = (
            t.get("runtime_schedule_summary")
            if t.get("schedule_authority") == "runtime_scheduler"
            else (t.get("derived_frequency") or t.get("frequency"))
        )
        if not when:
            continue
        # Per-trigger promotion, already resolved in the task payload — the
        # split that lets a card name WHICH schedule is a preview rather than
        # flagging the whole member. No extra query.
        triggers = [x for x in (t.get("triggers") or []) if x.get("summary")]
        wf = t.get("workflow") or {}
        out.append(
            _Cadence(
                grain=_grain_of(str(when)),
                when=str(when).rstrip("."),
                automation=str(t.get("name") or ""),
                runtime_workflow_id=wf.get("runtime_workflow_id"),
                live_whens=tuple(x["summary"] for x in triggers if x.get("is_live")),
                dry_whens=tuple(
                    x["summary"] for x in triggers if not x.get("is_live")
                ),
            )
        )
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
        # ⚠️ THE FIRST VERSION OF THIS FIRED ON PROSE EXISTING, AND MAP-4 MADE
        # PROSE THE NORM. Shipping five seeded cadence captions turned every
        # render into five warnings — a check that cries wolf on the expected
        # state, which trains people to stop reading the log. The premise was
        # wrong, not the intent.
        #
        # THE REAL HAZARD IS NARROWER: prose that RESTATES something derived.
        # "Morning is for the queues" cannot go stale; "the matcher runs at
        # 11:30 PM" goes stale the moment someone re-crons it, and "Bank
        # reconciliation and Collections" goes stale when membership changes.
        # A caption that says what the OPERATOR DOES is durable; one that
        # repeats WHEN or WHICH has baked a derived fact into authored text.
        #
        # So the check now looks for derived content INSIDE the caption rather
        # than for the caption itself.
        text = str(beat.get("text") or "")
        echoes: list[str] = []

        cadence = beat.get("cadence") or {}
        for when in cadence.get("whens") or []:
            # The humanized time carries its own separators; compare the parts
            # that would actually appear in prose (a clock time, a weekday).
            for token in _re.findall(r"\d{1,2}:\d{2}\s*(?:AM|PM)|\b1st\b", str(when)):
                if token.lower() in text.lower():
                    echoes.append(f"the time {token!r}")
        for job in cadence.get("jobs") or []:
            if job.get("name") and job["name"].lower() in text.lower():
                echoes.append(f"the job name {job['name']!r}")

        # ⚠️ MAP-5 — LIVENESS IS DERIVED, AND PROSE RESTATING IT GOES STALE
        # FASTER THAN A CLOCK TIME DOES.
        # "the matcher runs at 11:30 PM" rots when someone re-crons it; "and it
        # has never fired" rots THE FIRST TIME IT FIRES. A caption is authored
        # once and read for months, so baking a run state into it is the same
        # hazard as baking a schedule in, only quicker.
        #
        # This is why liveness is a SIBLING of `whens` and `jobs` on the cadence
        # payload and never merged into `text`: the card says WHETHER, the
        # caption says what the operator DOES.
        if cadence.get("liveness"):
            for phrase in (
                "never run", "hasn't run", "has not run", "last ran",
                "preview only", "nothing was saved", "switched off",
                "not built", "didn't finish", "waiting on you",
            ):
                if phrase in text.lower():
                    echoes.append(f"the liveness phrase {phrase!r}")

        if echoes:
            drift.append(
                f"caption on {key!r} restates derived content — it contains "
                f"{', '.join(sorted(set(echoes)))}, which the card already "
                "shows and which moves when the schedule does. Say what the "
                "operator DOES; let the card say when and which."
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
        # STRUCTURED, NOT JUST A SENTENCE (MAP-4). The beat carries its parts —
        # grain, the actual TIMES, and the member jobs with ids — so a CARD can
        # render them separately while the STORY still reads the sentence.
        # `_beat(**extra)` already carries structure this way (the closing beat's
        # `link`); one beat list, two altitudes.
        #
        # ⚠️ THE TIMES ARE THE QUIET IMPROVEMENT. "Overnight" loses that it is
        # 10:30 PM to 3:00 AM, and someone deciding when to sit down with the
        # queue needs the number rather than the adjective. The story keeps the
        # adjective; the card shows both.
        by_grain: dict[str, dict] = {}
        rhythmless: list[dict] = []
        for j in area_jobs:
            cadences = _job_cadences(db, j)
            if not cadences:
                rhythmless.append({"id": j.id, "name": j.name})
                continue
            for c in cadences:
                slot = by_grain.setdefault(
                    grain := c.grain, {"jobs": [], "whens": [], "_members": []}
                )
                if not any(x["name"] == j.name for x in slot["jobs"]):
                    slot["jobs"].append({"id": j.id, "name": j.name})
                if c.when not in slot["whens"]:
                    slot["whens"].append(c.when)
                # MAP-5: carried per grain so liveness can be resolved in ONE
                # hoisted query after the loop rather than per member. Private
                # (`_members`) because it is an input to the liveness pass, not
                # part of the beat's payload — the rendered `liveness` list
                # replaces it.
                slot["_members"].append(
                    {
                        "job": j.name,
                        # ⚠️ THE AUTOMATION NAME, NOT JUST THE JOB'S. A job can
                        # contribute SEVERAL automations to one grain — the
                        # weekly card carries two from "Compliance & records
                        # upkeep" — and keying the line on the job renders two
                        # identical labels with different states, which reads as
                        # a rendering bug rather than two facts.
                        "automation": c.automation,
                        "workflow_id": c.runtime_workflow_id,
                        "live_whens": list(c.live_whens),
                        "dry_whens": list(c.dry_whens),
                    }
                )

        # ── MAP-5 — LIVENESS, HOISTED ────────────────────────────────────
        # Two queries total for every member across every grain, against a
        # render that currently issues 262. Derived here and never stored: a
        # cached last-ran column is a write-time status claim with no reader.
        #
        # ⚠️ OMITTED ENTIRELY WITHOUT A TENANT. `company_id` is optional on this
        # builder, and `workflow_runs` is tenant-scoped. Rendering a
        # platform-wide last-run on a tenant's card would be a scope error
        # dressed as a fact — the same class as reading a platform count as one
        # tenant's. No tenant, no claim.
        from datetime import datetime, timezone

        from app.services.maps_of_content import liveness as _liveness

        _runs: dict[str, tuple] = {}
        _flags: dict[str, dict] = {}
        if company_id:
            _wids = [
                m["workflow_id"]
                for s in by_grain.values()
                for m in s["_members"]
                if m["workflow_id"]
            ]
            if _wids:
                _runs = _liveness.for_workflows(
                    db, workflow_ids=_wids, company_id=company_id
                )
                _flags = _liveness.workflow_flags(db, _wids)
        _now = datetime.now(timezone.utc)

        for grain in _GRAIN_ORDER:
            slot = by_grain.get(grain)
            if not slot:
                continue
            names = [x["name"] for x in slot["jobs"]]
            cadence: dict[str, Any] = {
                "grain": grain,
                "label": _GRAIN_LABEL[grain],
                "whens": sorted(slot["whens"]),
                "jobs": slot["jobs"],
            }
            if company_id:
                # A SIBLING OF `whens` AND `jobs`, NEVER MERGED INTO `text`.
                # `check_area_drift` flags an authored caption that restates
                # derived content, and liveness is derived — baking "and it has
                # never fired" into prose goes stale the moment it fires.
                cadence["liveness"] = []
                for m in slot["_members"]:
                    _status, _at = _runs.get(m["workflow_id"], (None, None))
                    _f = _flags.get(m["workflow_id"] or "", {})
                    _lv = _liveness.classify(
                        workflow_known=bool(m["workflow_id"]) and bool(_f),
                        is_coming_soon=_f.get("is_coming_soon", False),
                        is_active=_f.get("is_active", True),
                        has_tenant_ledger=True,
                        last_status=_status,
                        last_run_at=_at,
                        now=_now,
                        live_whens=m["live_whens"],
                        dry_whens=m["dry_whens"],
                    )
                    cadence["liveness"].append(
                        {
                            "job": m["job"],
                            "automation": m["automation"],
                            "state": _lv.state,
                            "label": _lv.label,
                            "last_run_at": (
                                _lv.last_run_at.isoformat() if _lv.last_run_at else None
                            ),
                        }
                    )
            # ── B-1 — A GRAIN WHOSE MEMBERS ARE ALL DEAD RENDERS, MARKED ──
            # Not suppressed: hiding it removes a declared capability from the
            # rhythm view, which is what r164 refused to do by deleting rows.
            # Not demoted to "on your schedule": that says work you pick up, and
            # nobody can pick this up. Not left alone: the card would keep
            # teaching a 7am Monday rhythm that is neither running nor built.
            #
            # So the times are replaced by what is true. The grain stays visible
            # because the DECLARATION is real even when the running is not.
            _dead = {_liveness.NOT_BUILT, _liveness.SWITCHED_OFF, _liveness.UNKNOWN_JOB}
            _lv = cadence.get("liveness") or []
            if _lv and all(x["state"] in _dead for x in _lv):
                cadence["all_dead"] = True
                cadence["whens"] = []
                cadence["dead_label"] = "Not running here — declared, not built yet"
            _beat(
                f"cadence:{grain}", "task",
                f"{_GRAIN_LABEL[grain]} — {_join_names(names)}.",
                cadence=cadence,
            )

        if rhythmless:
            # NAMED FOR WHAT THE WORK IS, NOT FOR WHAT IT LACKS. "On your
            # schedule" rather than "No schedule" — a category defined by
            # absence still describes real work, and four of eleven is far too
            # many to drop. It is also the group an operator actually asks
            # about: what do I do that isn't automatic.
            _beat(
                "cadence:none", "task",
                f"{_join_names([x['name'] for x in rhythmless])} run on no "
                "schedule — they are work you pick up, not work that arrives.",
                cadence={
                    "grain": "none",
                    "label": "On your schedule",
                    "whens": [],
                    "jobs": rhythmless,
                },
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
