"""What Opas filled in, what the person changed it to, and the one question worth asking.

James's dispatch of 2026-10-26, "Opas asks why?", first slice — capture only.

⚠️ THE DISPATCH CITES `docs/design/opas-understanding-plan.md` AND THAT FILE DOES NOT
EXIST. It has never existed in git history, and STATE.md records it blocked on
2026-10-20 because the dispatch that was to carry it left its paste placeholder
unfilled. Per CLAUDE.md it must not be reconstructed from conversation — "a file whose
header reads 'verbatim' and whose actual source is a conversation is worse than no file".
So this slice is built from the 2026-10-26 dispatch's own five clauses and the design
James stated above them, both quoted where they decide something here.

THE THREE WAYS A FIELD CHANGES, AND WHY ONLY ONE NEEDED STORAGE:

    a switch taken      `take_switch` writes a RESOLUTION
    a pick answered     `choose` writes a RESOLUTION
    the text retyped    nothing records what was there before

The first two are recoverable without storing anything: resolutions outrank extraction,
so Opas's own reading is what extraction says with them removed. The third is not. The
bar is the only input — by ruling, the pane "has no field of its own" — so changing the
vault means EDITING THE TEXT, and once it reads Continental nothing anywhere remembers
Opas had read Monticello. That is the case James's own walk exercises:

    "capture an order, change the vault before approving, approve, and answer the why?"

So `capture_sessions.opas_proposed` keeps Opas's reading, and `remember` below is what
maintains it.

⚠️ AND IT COSTS NO SECOND EXTRACTION, which matters because `PUT /sessions/{id}/text` is
the hot path — one call per pause, inside a p50 budget. The naive design re-extracts
without resolutions on every pause to learn "what would Opas have said"; instead
`remember` records the extraction that already ran and SKIPS any field the person has
resolved, so the value frozen for a resolved field is the one Opas proposed on the pass
BEFORE the person touched it. Same answer, no extra work.

⚠️ CHURN IS EXCLUDED BY ASKING WHETHER THE TEXT CONTINUED. "churn while typing (compare
settled values only)" — `mont` becoming `monticello` is one thought finishing;
`monticello` becoming `continental` is a different thought. The signal is whether the new
text starts with the old one. Stated as a heuristic because that is what it is: a person
who edits a word in the middle and happens to leave a prefix intact is not distinguished,
and a person who deletes a trailing character is treated as editing. Both err toward
FREEZING, which errs toward asking about a change that was really churn — a question too
many, never a silent miss.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from sqlalchemy.orm import Session

#: How Opas came to a value. Stored beside it, because James names the sources and they
#: are not interchangeable: a misread is not the same event as a default being wrong.
SOURCE_EXTRACTION = "extraction"
SOURCE_PREFILL = "prefill"
SOURCE_DEFAULT = "default"

#: Which change to ask about when there is more than one. James's order, verbatim:
#: "vault, funeral home, cemetery, service date/time, then the rest".
#:
#: ⚠️ IT IS A RANKING, NOT A FILTER. A change to any field can be asked about; this
#: decides which ONE when several moved. "At most one question per order, about the most
#: important change."
IMPORTANCE: tuple[str, ...] = (
    "vault",
    "funeral_home",
    "cemetery",
    "service_date",
    "service_time",
)


@dataclass(frozen=True)
class Change:
    """One field Opas filled that the person changed."""

    field_id: str
    label: str
    was: str
    now: str
    source: str

    @property
    def rank(self) -> int:
        """Lower is more important. Unranked fields sort after every ranked one."""
        try:
            return IMPORTANCE.index(self.field_id)
        except ValueError:
            return len(IMPORTANCE)


def display(value: object) -> str:
    """A value as the question should read it.

    ⚠️ DATES AND TIMES ARRIVE AS STRINGS FROM JSONB AND AS OBJECTS FROM EXTRACTION, and
    the same session hands over both — `values` is read back from the column on one
    request and built in memory on another. Normalising here is what stops
    "2026-10-28" and `date(2026, 10, 28)` reading as a change.
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, (date, time)):
        return value.isoformat()
    return str(value).strip()


def _same(a: object, b: object) -> bool:
    """⚠️ CASE-INSENSITIVE, BECAUSE EXTRACTION TITLE-CASES AND THE PERSON DOES NOT.

    "monticello burial vault" typed and "Monticello Burial Vault" resolved are the same
    choice, and asking why somebody changed a value to itself is the kind of question
    that teaches the office the feature is noise.
    """
    return display(a).casefold() == display(b).casefold()


def remember(
    row,
    values: dict,
    *,
    source: str = SOURCE_EXTRACTION,
    continuing: bool = True,
    switch_fields: frozenset[str] = frozenset(),
) -> None:
    """Record what Opas proposed. Refresh while still typing; freeze on an edit.

    `continuing` is whether the new text CONTINUES the old one. True refreshes the
    record, because the person is still finishing a thought. False leaves it, because
    whatever Opas had read before the edit is the thing the person changed.

    ⚠️ A FIELD THE PERSON HAS RESOLVED IS NEVER OVERWRITTEN. `values` here is the
    extraction WITH resolutions applied, so for a resolved field it already holds the
    person's own choice — writing that in would make Opas the author of the change and
    there would be nothing to ask about. The entry frozen from the pass before the
    resolution is the one that matters.

    ⚠️ AND IT MUTATES `row.opas_proposed` BY REPLACEMENT, NOT IN PLACE. SQLAlchemy does
    not track mutation inside a JSONB dict, so `row.opas_proposed[k] = v` is a write
    that silently does not persist — the defect this codebase has recorded on
    `values`, `resolutions` and `prefill` in turn.
    """
    proposed = dict(row.opas_proposed or {})
    resolved = set(row.resolutions or {})
    for field_id, value in (values or {}).items():
        if field_id in resolved:
            continue
        if not continuing and field_id in proposed:
            continue
        rendered = display(value)
        if not rendered:
            continue
        proposed[field_id] = {
            "value": rendered,
            # A field the extractor chose a FORM for — burial vault vs urn vault — is a
            # default rather than a reading, and James names those separately.
            "source": SOURCE_DEFAULT if field_id in switch_fields else source,
        }
    if proposed != (row.opas_proposed or {}):
        row.opas_proposed = proposed


def is_continuation(old: str | None, new: str | None) -> bool:
    """Did the person keep typing, rather than go back and change something?

    ⚠️ WHITESPACE-INSENSITIVE AT THE JOIN, because the bar sends a trailing space the
    moment a word completes and "order hopkins" -> "order hopkins " is not an edit.
    """
    before = (old or "").strip()
    after = (new or "").strip()
    if not before:
        return True
    return after.startswith(before)


def _labels(object_type: str) -> dict[str, str]:
    """field_id -> the label the office sees, from the capture template."""
    from app.services.capture.schema import template_for

    try:
        return {f.field_id: f.label for f in template_for(object_type)}
    except KeyError:
        return {}


def changes(row) -> list[Change]:
    """Every field Opas proposed that the approved value differs from.

    ⚠️ IT READS ONLY THE SESSION — no extraction, no database. Called inside `approve`,
    which is one transaction that creates an order and fires the delivery hook; a read
    that could fail there would make the question's machinery able to break the approve
    it rides on.

    NOT A CHANGE, and each falls out of the data rather than needing a rule:

        a field the person filled first   Opas never proposed it -> no entry
        an answer to a pick               Opas had no value -> no entry
        a switch the person kept          proposal == approved value
        churn while typing                the proposal was refreshed as they typed
    """
    proposed = row.opas_proposed or {}
    approved = row.values or {}
    labels = _labels(row.object_type)
    out: list[Change] = []
    for field_id, record in proposed.items():
        was = (record or {}).get("value")
        now = approved.get(field_id)
        if was is None or now is None:
            # ⚠️ A FIELD THAT ENDED UP EMPTY IS NOT A CHANGE TO ASK ABOUT. Deleting a
            # value is a different event from replacing one, and "You changed the vault
            # from Monticello to nothing. Why?" is not a sentence worth sending.
            continue
        if _same(was, now):
            continue
        out.append(Change(
            field_id=field_id,
            label=labels.get(field_id, field_id.replace("_", " ")),
            was=display(was),
            now=display(now),
            source=(record or {}).get("source") or SOURCE_EXTRACTION,
        ))
    return sorted(out, key=lambda c: (c.rank, c.field_id))


def top_change(row) -> Change | None:
    """The one change worth a question, or None. "At most one question per order"."""
    found = changes(row)
    return found[0] if found else None


def prompt_for(change: Change) -> str:
    """"You changed the vault from Monticello to Continental. Why?"

    ⚠️ THE DISPATCH'S OWN SENTENCE, including the lower-cased field. The label from the
    template is "Vault" because it heads a column; mid-sentence it is "the vault".
    """
    return (
        f"You changed the {change.label.lower()} from {change.was} "
        f"to {change.now}. Why?"
    )


def ask_payload(row) -> dict | None:
    """What the capture state carries so the bar can ask. None when there is nothing.

    ⚠️ ASKED ONCE PER ORDER, AND THE DECISION ROW IS WHAT REMEMBERS THAT. A session that
    has already recorded a `reason_scope` is not asked again — including after a page
    reload, which re-reads this same state. "never asks twice for one order."
    """
    if row.sales_order_id is None:
        return None
    change = top_change(row)
    if change is None:
        return None
    return {
        "field": change.field_id,
        "label": change.label,
        "was": change.was,
        "now": change.now,
        "source": change.source,
        "prompt": prompt_for(change),
    }


def already_answered(db: Session, row) -> bool:
    """Has this capture's question already been answered or skipped?

    ⚠️ READ FROM THE DECISION ROW, NOT FROM A FLAG ON THE SESSION. The answer is the
    record; a second place saying whether it exists is a second thing to keep in step.
    """
    if row.decision_id is None:
        return False
    try:
        from app.models.opas_decision import OpasDecision

        scope = (
            db.query(OpasDecision.reason_scope)
            .filter(OpasDecision.id == row.decision_id)
            .scalar()
        )
        return scope is not None
    except Exception:
        # ⚠️ FAIL TOWARD ASKING NOTHING. A log read that breaks must not break the
        # capture state, and an extra question is worse than a missing one here: the
        # dispatch's hard rule is "never asks twice".
        return True
