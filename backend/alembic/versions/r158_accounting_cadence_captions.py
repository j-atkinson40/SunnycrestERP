"""The accounting cadence prose — what the operator does in each rhythm.

MAP-3 derived the GRAINS from trigger schedules. "What you do at month-end" is
not derivable from anything, so it is authored — and it ships seeded, because a
card rendering four rhythms with empty prose is worse than one that arrives with
a sentence. The derived-honest fallback would only repeat the job list the card
already shows.

MATCH-BEFORE-UPDATE, r157's pattern. `MoCComposition.captions` is a flat dict
keyed on beat key, and an operator may have authored over any of these through
the in-ponder caption editor. So each caption is written ONLY when the key is
absent — present means someone chose those words, and a migration overwriting
them would clobber exactly what the caption mechanism exists to protect.

⚠️ WHAT THE MONTHLY CAPTION DELIBERATELY DOES NOT SAY. An earlier draft ended
"…the close locks the period when you approve it." True, and the closest the Map
has come to the clean-queue claim — a mechanism sentence sitting beside a queue
list invites the reader to infer an ordering NOTHING ENFORCES. Month-end close
gates on the PeriodLock and the statement-run conflict check, not on queue
state. The lock is the close's own business and is taught on that task's card.

The same reasoning kept LIVE STATE off these cards entirely: a pending count
next to "the close stages its anomalies" would say *clear this first* without
saying it. Proximity does argumentative work that prose would be held
accountable for.

Migration head: r157 → r158. Content only; no schema change.
"""
from alembic import op
import sqlalchemy as sa
import json
import uuid

revision = "r158_accounting_cadence_captions"
down_revision = "r157_map_accounting_content"
branch_labels = None
depends_on = None

VERT = "manufacturing"
AREA = "Accounting"

# Keyed on the beat key the area generator emits. Authored prose ONLY — the
# grain label, the times and the job list are all derived and must never be
# duplicated here, or they would drift the moment a cron moved.
_CAPTIONS = {
    "cadence:nightly": (
        "The feed pulls, the matcher does what it can, and what it can't goes "
        "to Books Review. Morning is for the queues."
    ),
    "cadence:monthly": (
        "Statements generate and the close stages its anomalies. Both wait "
        "for you."
    ),
    "cadence:continuous": (
        "Expenses are categorised as the sweep finds them. Until event "
        "dispatch exists, that sweep is what \"as they arrive\" means."
    ),
    "cadence:weekly": (
        "Training currency and document reviews, checked at the start of "
        "the week."
    ),
    "cadence:none": (
        "Work you pick up rather than work that arrives. Nothing queues "
        "these; you come to them."
    ),
}


def _log(msg: str) -> None:
    print(f"[r158] {msg}")


def upgrade() -> None:
    bind = op.get_bind()

    row = bind.execute(
        sa.text(
            "SELECT id, captions FROM moc_composition "
            "WHERE kind = 'area' AND key = :k AND vertical = :v"
        ),
        {"k": AREA, "v": VERT},
    ).fetchone()

    if row is None:
        # The area composition row is the philosophy layer and may not exist on
        # a database that has never authored one. Create it carrying only these
        # captions — the generator treats a missing row and an empty row
        # identically, so this is additive either way.
        bind.execute(
            sa.text(
                "INSERT INTO moc_composition (id, kind, key, vertical, captions) "
                "VALUES (:i, 'area', :k, :v, CAST(:c AS jsonb))"
            ),
            {"i": str(uuid.uuid4()), "k": AREA, "v": VERT,
             "c": json.dumps(_CAPTIONS)},
        )
        _log(f"created the {AREA} area composition with {len(_CAPTIONS)} captions.")
        return

    existing = dict(row[1] or {})
    written = skipped = 0
    for key, text in _CAPTIONS.items():
        if key in existing:
            # PRESENT MEANS SOMEONE CHOSE THOSE WORDS. Skip loudly — a silent
            # skip reads as "nothing to do" when what happened is "the operator
            # already wrote this."
            _log(
                f"SKIP {key}: an operator authored it. Found "
                f"{existing[key]!r}; left as-is."
            )
            skipped += 1
            continue
        existing[key] = text
        written += 1

    if written:
        bind.execute(
            sa.text(
                "UPDATE moc_composition SET captions = CAST(:c AS jsonb) "
                "WHERE id = :i"
            ),
            {"c": json.dumps(existing), "i": row[0]},
        )

    _log(f"done — {written} written, {skipped} skipped.")


def downgrade() -> None:
    # Removing the prose would leave cards rendering their derived fallback —
    # the job list twice, once as a sentence and once as chips. Content, not
    # schema; deliberately a no-op. Re-running upgrade is idempotent.
    pass
