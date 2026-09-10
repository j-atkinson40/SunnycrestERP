"""The live-to-settled transition.

At a tenant-configured settling hour, consumed prompts are replaced by
past-tense records of the action taken. Per DECISIONS 2026-09-04 ("The note has
a live phase and a settled phase").

──────────────────────────────────────────────────────────────────────────
THE RECORD SAYS WHAT HAPPENED

Not that something was completed. A cancelled task produces "you cancelled 1
task due today" — not "you completed", and not silence. That is why
`EndTransition` carries one `Outcome` per ending, and why this module groups
events BY OUTCOME rather than counting resolutions.

⚠️ OUTCOMES COME FROM STRUCTURED FIELDS, NEVER FROM PROSE. A task's outcome is
the terminal state it reached, read out of the transition's own `changes`
payload. A collections finding's outcome is `resolution_outcome`, the column
r180 added for this. A resolving act that recorded no outcome is REPORTED as
unsettleable — never recovered by matching text a human typed.

──────────────────────────────────────────────────────────────────────────
IDEMPOTENCE

Settling fires from a sweep and will evaluate the same tenant-local day many
times. Identity is (note, fragment, instance, outcome) — the SUBJECT and the
ending, never the run. The second evaluation writes nothing.

⚠️ AND THE WORDING IS FROZEN. A record that already exists is not rewritten,
even if its count would now be higher — a later event appends a NEW record
rather than editing the old one, because the settled note is append-only with
visible timestamps and a note that re-words itself is worse than one that says
nothing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable, Sequence
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.daily_note import DailyNote
from app.models.note_fragment_render import NoteFragmentRender
from app.models.note_settled_record import NoteSettledRecord
from app.models.user import User
from app.services.fragments.registry import get_fragment
from app.services.fragments.synthesis import measured, plain
from app.services.fragments.types import ReferencedItem
from app.services.note.spans import serialise_spans

logger = logging.getLogger(__name__)

#: Mirrors the briefings precedent — tenant timezone with the same fallback.
_DEFAULT_TZ = "America/New_York"


@dataclass(frozen=True)
class OutcomeTally:
    """N of one ending occurred, and when the last one did."""

    outcome_key: str
    count: int
    latest: datetime


@dataclass(frozen=True)
class Unsettleable:
    """A resolution that happened and cannot be written down."""

    fragment_id: str
    instance_key: str
    reason: str


@dataclass
class SettleResult:
    note_id: str
    written: int = 0
    already_present: int = 0
    unsettleable: list[Unsettleable] = field(default_factory=list)
    #: Fragments whose declaration has no resolver for its `resolved_when`.
    unresolvable: list[str] = field(default_factory=list)


def tenant_day_window(
    db: Session, *, company_id: str, day: date
) -> tuple[datetime, datetime]:
    """[local midnight, next local midnight) as UTC instants.

    ⚠️ THE WINDOW IS TENANT-LOCAL AND THAT IS THE POINT. An 11pm action belongs
    to the day the person was living, not to whatever UTC calendar date it
    landed on. Resolving this per tenant is what lets one tenant's Tuesday end
    while another's is still running.
    """
    from app.models.company import Company

    tzname = (
        db.execute(select(Company.timezone).where(Company.id == company_id))
        .scalars()
        .first()
    ) or _DEFAULT_TZ
    try:
        tz = ZoneInfo(tzname)
    except Exception:
        logger.warning("unknown tenant timezone %r; falling back", tzname)
        tz = ZoneInfo(_DEFAULT_TZ)

    start_local = datetime.combine(day, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def split_instance_key(instance_key: str) -> tuple[str, str, str]:
    """`fragment_id:subject_kind:subject_id` -> its three parts.

    ⚠️ `maxsplit=2`, because the SUBJECT may itself contain colons — `user_day`
    is `"{user_id}:{date}"`. Splitting naively would silently truncate the
    subject to a UUID and settle the wrong thing.
    """
    parts = instance_key.split(":", 2)
    if len(parts) != 3:
        raise ValueError(f"malformed instance_key {instance_key!r}")
    return parts[0], parts[1], parts[2]


# ── Resolvers: recorded events -> tallies, per `resolved_when` ───────


def _tally_task_terminals(
    db: Session, *, user: User, subject_id: str, window: tuple[datetime, datetime],
) -> tuple[list[OutcomeTally], list[str]]:
    """Terminal states this user drove, for tasks due on the note's day.

    Read from `task.transition` audit rows — the ACTION written directly by
    `lifecycle.apply_transition`, whose `changes` payload carries `from`/`to`
    structurally. Not from the event name: two of the four terminal states
    (`acknowledged`, `dismissed`) emit no dedicated event, so the payload is the
    only place all four are legible, and it is structured data either way.
    """
    from app.models.task_details import TaskDetails
    from app.services.fragments.platform_defaults import _TERMINAL_TASK_STATES

    start, end = window
    # subject is "{user_id}:{iso date}" — the day the prompt was about.
    try:
        _, due_iso = subject_id.rsplit(":", 1)
        due = date.fromisoformat(due_iso)
    except ValueError:
        return [], [f"task subject {subject_id!r} is not user:date"]

    rows = db.execute(
        select(AuditLog.changes, AuditLog.created_at)
        .join(TaskDetails, TaskDetails.id == AuditLog.entity_id)
        .where(
            AuditLog.action == "task.transition",
            AuditLog.user_id == user.id,
            AuditLog.created_at >= start,
            AuditLog.created_at < end,
            TaskDetails.due_date == due,
        )
    ).all()

    by_outcome: dict[str, list[datetime]] = {}
    for changes, at in rows:
        try:
            to_state = json.loads(changes or "{}").get("to")
        except (TypeError, ValueError):
            continue
        if to_state in _TERMINAL_TASK_STATES:
            by_outcome.setdefault(to_state, []).append(at)

    return (
        [OutcomeTally(k, len(v), max(v)) for k, v in sorted(by_outcome.items())],
        [],
    )


def _tally_collections(
    db: Session, *, user: User, subject_id: str, window: tuple[datetime, datetime],
) -> tuple[list[OutcomeTally], list[str]]:
    """Findings for this customer that this user resolved, by declared outcome."""
    from app.models.agent_anomaly import AgentAnomaly

    start, end = window
    rows = db.execute(
        select(AgentAnomaly.resolution_outcome, AgentAnomaly.resolved_at)
        .where(
            AgentAnomaly.entity_type == "customer",
            AgentAnomaly.entity_id == subject_id,
            AgentAnomaly.resolved.is_(True),
            AgentAnomaly.resolved_by == user.id,
            AgentAnomaly.resolved_at >= start,
            AgentAnomaly.resolved_at < end,
        )
    ).all()

    by_outcome: dict[str, list[datetime]] = {}
    undeclared = 0
    for outcome, at in rows:
        if not outcome:
            # ⚠️ REPORTED, NOT PARSED. `resolution_note` says which act it was,
            # in a sentence. Recovering the outcome from it would put the
            # settled record downstream of matching prose a human typed.
            undeclared += 1
            continue
        by_outcome.setdefault(outcome, []).append(at)

    problems = []
    if undeclared:
        problems.append(
            f"{undeclared} resolution(s) recorded no outcome — the resolving act "
            "must declare one before they can be settled"
        )
    return (
        [OutcomeTally(k, len(v), max(v)) for k, v in sorted(by_outcome.items())],
        problems,
    )


#: `resolved_when` -> the resolver that reads its recorded events.
#: A fragment whose key is absent here is REPORTED as unresolvable, not skipped
#: silently — settling that quietly ignores a prompt looks identical to a day
#: on which nothing happened.
RESOLVERS: dict[str, Callable[..., tuple[list[OutcomeTally], list[str]]]] = {
    "task_reaches_terminal_state": _tally_task_terminals,
    "collections_finding_resolved": _tally_collections,
}


def _render(past_tense: str, *, count: int, instance_key: str) -> tuple[str, str]:
    """Interpolate one ending's words, and build its spans.

    The count is MEASURED — it was counted from recorded events — and carries no
    href: there is no single page that is "the 2 tasks you completed". Rendering
    it unlinked keeps the provenance claim honest rather than inventing a
    destination, the same call the collections amount got at operator review.
    """
    text = past_tense.format(count=count, plural="" if count == 1 else "s")
    head, _, tail = text.partition(str(count))
    spans = [
        plain(head),
        measured(
            str(count),
            ReferencedItem(
                kind="settled_count", entity_id=instance_key,
                label="counted from recorded events", href=None,
            ),
        ),
        plain(tail),
    ] if str(count) in text else [plain(text)]
    return text, json.dumps(serialise_spans(spans))


def settle_note(db: Session, *, user: User, note: DailyNote) -> SettleResult:
    """Write past-tense records for what this user's prompts resolved into.

    Caller commits. Pure of scheduling — this is a function, not a job.
    """
    result = SettleResult(note_id=note.id)
    window = tenant_day_window(db, company_id=note.company_id, day=note.note_date)

    rendered = db.execute(
        select(NoteFragmentRender).where(
            NoteFragmentRender.daily_note_id == note.id,
            NoteFragmentRender.kind == "prompt",
        )
    ).scalars().all()

    for r in rendered:
        decl = get_fragment(r.fragment_id)
        if decl is None or decl.end_transition is None:
            result.unresolvable.append(r.fragment_id)
            continue

        resolver = RESOLVERS.get(decl.end_transition.resolved_when)
        if resolver is None:
            result.unresolvable.append(
                f"{r.fragment_id} ({decl.end_transition.resolved_when})"
            )
            continue

        try:
            _, _, subject_id = split_instance_key(r.instance_key)
        except ValueError as exc:
            result.unsettleable.append(
                Unsettleable(r.fragment_id, r.instance_key, str(exc))
            )
            continue

        tallies, problems = resolver(
            db, user=user, subject_id=subject_id, window=window
        )
        for p in problems:
            result.unsettleable.append(
                Unsettleable(r.fragment_id, r.instance_key, p)
            )

        for t in tallies:
            outcome = decl.end_transition.outcome(t.outcome_key)
            if outcome is None:
                # The world produced an ending the fragment never declared.
                result.unsettleable.append(Unsettleable(
                    r.fragment_id, r.instance_key,
                    f"outcome {t.outcome_key!r} is not declared on this fragment",
                ))
                continue

            existing = db.execute(
                select(NoteSettledRecord).where(
                    NoteSettledRecord.daily_note_id == note.id,
                    NoteSettledRecord.fragment_id == r.fragment_id,
                    NoteSettledRecord.instance_key == r.instance_key,
                    NoteSettledRecord.outcome_key == t.outcome_key,
                )
            ).scalars().first()
            if existing is not None:
                # ⚠️ NOT REWRITTEN, even if the count would now be higher. The
                # settled note is append-only; re-wording it is the failure.
                result.already_present += 1
                continue

            text, spans = _render(
                outcome.past_tense, count=t.count, instance_key=r.instance_key
            )
            db.add(NoteSettledRecord(
                daily_note_id=note.id,
                company_id=note.company_id,
                user_id=user.id,
                note_date=note.note_date,
                fragment_id=r.fragment_id,
                instance_key=r.instance_key,
                outcome_key=t.outcome_key,
                count=t.count,
                text=text,
                spans=spans,
                occurred_through=t.latest,
            ))
            result.written += 1

    if note.settled_at is None:
        note.settled_at = datetime.now(timezone.utc)
    return result
