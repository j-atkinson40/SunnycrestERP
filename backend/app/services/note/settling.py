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
    """N of one ending occurred, when the last one did, and who did them.

    ⚠️ `actor_ids` IS A SET, NOT A TALLY, DELIBERATELY (2026-09-10). Per
    DECISIONS 2026-09-04, attribution "is never aggregated into per-user
    resolution counts; the moment such a number exists, someone will look at
    it." A `dict[user_id, int]` here would be that number, and the record's
    unique key — (note, fragment, instance, outcome) — would then have to grow
    an actor column to hold it. Keeping this a set means the sentence can say
    WHO without ever being able to say HOW MANY EACH.
    """

    outcome_key: str
    count: int
    latest: datetime
    #: Everyone whose recorded act contributed to this ending. Often one.
    actor_ids: frozenset[str] = frozenset()


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
    """Terminal states reached by the SUBJECT's tasks, whoever drove them.

    Read from `task.transition` audit rows — the ACTION written directly by
    `lifecycle.apply_transition`, whose `changes` payload carries `from`/`to`
    structurally. Not from the event name: two of the four terminal states
    (`acknowledged`, `dismissed`) emit no dedicated event, so the payload is the
    only place all four are legible, and it is structured data either way.

    ──────────────────────────────────────────────────────────────────────
    ⚠️ THE FILTER MOVED FROM THE ACTOR TO THE SUBJECT (2026-09-10, §2).

    This filtered `AuditLog.user_id == user.id` and did NOT filter on the task's
    assignee. Two defects in one clause:

      MISSED — a prompt resolved by a colleague settled onto nobody's note. The
        holder watched it vanish, which is the failure the note arc ruled
        against at the start: prompts leave by resolution or dated deferral,
        never silently.
      WRONG — transitioning a COLLEAGUE'S task that happened to be due today
        settled onto YOUR note, because due_date matched and assignee was never
        checked. Your note claimed work about someone else's task.

    The prompt's subject is `{user_id}:{date}` — it is about that user's tasks
    on that day. So the scope is the ASSIGNEE, and the actor is free.
    """
    from app.models.task_details import TaskDetails
    from app.services.fragments.platform_defaults import _TERMINAL_TASK_STATES

    start, end = window
    # subject is "{user_id}:{iso date}" — the day the prompt was about.
    try:
        subject_user_id, due_iso = subject_id.rsplit(":", 1)
        due = date.fromisoformat(due_iso)
    except ValueError:
        return [], [f"task subject {subject_id!r} is not user:date"]

    rows = db.execute(
        select(AuditLog.changes, AuditLog.created_at, AuditLog.user_id)
        .join(TaskDetails, TaskDetails.id == AuditLog.entity_id)
        .where(
            AuditLog.action == "task.transition",
            AuditLog.created_at >= start,
            AuditLog.created_at < end,
            TaskDetails.due_date == due,
            # The subject's tasks — see the docstring. Whoever moved them.
            TaskDetails.assignee_user_id == subject_user_id,
        )
    ).all()

    by_outcome: dict[str, list[datetime]] = {}
    actors: dict[str, set[str]] = {}
    for changes, at, actor_id in rows:
        try:
            to_state = json.loads(changes or "{}").get("to")
        except (TypeError, ValueError):
            continue
        if to_state in _TERMINAL_TASK_STATES:
            by_outcome.setdefault(to_state, []).append(at)
            if actor_id:
                actors.setdefault(to_state, set()).add(actor_id)

    return (
        [
            OutcomeTally(k, len(v), max(v), frozenset(actors.get(k, ())))
            for k, v in sorted(by_outcome.items())
        ],
        [],
    )


def _tally_collections(
    db: Session, *, user: User, subject_id: str, window: tuple[datetime, datetime],
) -> tuple[list[OutcomeTally], list[str]]:
    """Findings for this customer, by declared outcome, whoever resolved them.

    ⚠️ The actor filter (`resolved_by == user.id`) was dropped 2026-09-10 for
    §2. This fragment's audience is every `invoice.approve` holder, so a finding
    resolved by any one of them is resolved for all of them. Subject scoping is
    already correct here — `entity_id == subject_id` is the customer — so unlike
    the task resolver, only the actor clause had to go.
    """
    from app.models.agent_anomaly import AgentAnomaly

    start, end = window
    rows = db.execute(
        select(
            AgentAnomaly.resolution_outcome,
            AgentAnomaly.resolved_at,
            AgentAnomaly.resolved_by,
        )
        .where(
            AgentAnomaly.entity_type == "customer",
            AgentAnomaly.entity_id == subject_id,
            AgentAnomaly.resolved.is_(True),
            AgentAnomaly.resolved_at >= start,
            AgentAnomaly.resolved_at < end,
        )
    ).all()

    by_outcome: dict[str, list[datetime]] = {}
    actors: dict[str, set[str]] = {}
    undeclared = 0
    for outcome, at, actor_id in rows:
        if not outcome:
            # ⚠️ REPORTED, NOT PARSED. `resolution_note` says which act it was,
            # in a sentence. Recovering the outcome from it would put the
            # settled record downstream of matching prose a human typed.
            undeclared += 1
            continue
        by_outcome.setdefault(outcome, []).append(at)
        if actor_id:
            actors.setdefault(outcome, set()).add(actor_id)

    problems = []
    if undeclared:
        problems.append(
            f"{undeclared} resolution(s) recorded no outcome — the resolving act "
            "must declare one before they can be settled"
        )
    return (
        [
            OutcomeTally(k, len(v), max(v), frozenset(actors.get(k, ())))
            for k, v in sorted(by_outcome.items())
        ],
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


def _actor_phrase(
    db: Session, *, actor_ids: frozenset[str], viewer_id: str
) -> str:
    """Who did it, from the reader's seat. "you", a name, or a combination.

    ⚠️ NO PER-ACTOR COUNTS, BY CONSTRUCTION. `actor_ids` is a set, so this
    cannot say "Sarah did 3" even if asked to — the number in the sentence is
    always the count of THINGS RESOLVED, never of anyone's output. Per DECISIONS
    2026-09-04, "the moment such a number exists, someone will look at it."

    ⚠️ AND NO TIMING. "you completed 2 tasks", never "you completed 2 tasks at
    4:55pm" or "late in the day". Time belongs in the record — `occurred_through`
    is a visible column on the row — not in the sentence. Same entry.

    The viewer is always named first and always as "you", because this is the
    resolution of a fragment they were holding, not news about a colleague. A
    line that opened with someone else's name would read as a feed item, and
    the activity feed is a separate channel.

    Beyond two named actors it degrades to "and N others" — a headcount, which
    is not a per-user resolution count.
    """
    if not actor_ids:
        # Nothing recorded an actor. Say so rather than implying the reader.
        return "someone"

    others = sorted(actor_ids - {viewer_id})
    mine = viewer_id in actor_ids

    names: list[str] = []
    if others:
        rows = db.execute(
            select(User.id, User.first_name, User.last_name).where(
                User.id.in_(others)
            )
        ).all()
        by_id = {
            r[0]: f"{r[1]} {r[2]}".strip() or "a colleague" for r in rows
        }
        names = [by_id.get(uid, "a colleague") for uid in others]

    parts: list[str] = (["you"] if mine else []) + names
    if not parts:
        return "someone"
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    head = ", ".join(parts[:2])
    return f"{head} and {len(parts) - 2} other{'' if len(parts) == 3 else 's'}"


def _render(
    past_tense: str, *, count: int, instance_key: str, actor: str
) -> tuple[str, str]:
    """Interpolate one ending's words, and build its spans.

    The count is MEASURED — it was counted from recorded events — and carries no
    href: there is no single page that is "the 2 tasks you completed". Rendering
    it unlinked keeps the provenance claim honest rather than inventing a
    destination, the same call the collections amount got at operator review.

    ⚠️ RE-RULED 2026-09-10, IN FAVOUR OF THE REVIEW. The §2 dispatch asked that
    the resolution line carry "a link to what was done", which would have meant
    linking this count. It stays unlinked: the dispatch was written BEFORE the
    2026-09-09 operator review, the review is later evidence about the same
    span, and it found that linking a measured number pulled the eye harder than
    the entity beside it.

    The way in is the SUBJECT, not the number — you click the customer, not the
    "2". That entity link is not built here yet and is the honest next step for
    this line; it is recorded as owed rather than left as a gap nobody named.
    """
    text = past_tense.format(
        count=count, plural="" if count == 1 else "s", actor=actor
    )
    # Sentence-initial actor: "you completed…" reads as a sentence, not a log.
    text = text[:1].upper() + text[1:] if text else text
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
    """Write past-tense records for what this holder's prompts resolved into.

    Caller commits. Pure of scheduling — this is a function, not a job.

    ⚠️ HOLDERS ONLY, AND THAT IS STRUCTURAL RATHER THAN CHECKED (§2, 2026-09-10).
    The loop iterates `note_fragment_renders` for THIS note. A user who never
    held the prompt has no render row, so no record is written for them and no
    filter has to say so. Routed any wider this would be a feed; the activity
    feed is a separate channel and stays one.

    What changed in §2 is the other half: the resolvers no longer require the
    reader to be the actor, so a prompt resolved by any authorized party settles
    for everyone who held it, attributed. Before, a colleague's resolution
    settled onto nobody's note and the holder watched the prompt vanish.
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
                outcome.past_tense,
                count=t.count,
                instance_key=r.instance_key,
                actor=_actor_phrase(
                    db, actor_ids=t.actor_ids, viewer_id=user.id
                ),
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
