"""The Map's accounting content, corrected — match-before-update per field.

WHY A MIGRATION FOR CONTENT. `seed_accounting_jobs.py` is preserve-aware by
explicit contract — *"a job that EXISTS is not touched AT ALL, not its fields,
not its refs"* — so editing its SKELETON corrects only databases that have never
seeded. Every existing tenant would keep the wrong text. Preserve-awareness is
right (it protects operator edits); it just means a CORRECTION needs the Option A
idempotent pattern rather than a seed edit: update where the current value
byte-matches what the seed wrote, skip where it differs.

MATCHING MEANS UNTOUCHED, SO CORRECT IT. DIFFERING MEANS THE OPERATOR WROTE IT,
SO LEAVE IT — and say so, naming the field and both values. A migration that
silently skips half its work because an operator edited those fields is doing the
right thing and must not do it quietly (the AR-1 sweeper's discipline).

────────────────────────────────────────────────────────────────────────────
THE REF GUARD, which is the part that needed thinking about.

Descriptions are a single field: byte-match, replace, done. **Refs are a LIST**,
and a list that differs might differ because the operator ADDED one — an edit
orthogonal to the correction — not because they touched the refs being moved.
Guarding on "the whole ref set matches" would let one unrelated addition block a
correction that has nothing to do with it.

So the guard is PER-REF AND PRESENCE-CONDITIONAL:

  * a ref MOVES only if it is still present with the exact (kind, key) the seed
    wrote. Extra refs the operator added are neither read nor touched.
  * a ref that is ABSENT is not moved AND NOT RECREATED on the destination. If
    the operator deleted it, they have already said it does not belong; adding it
    to a new job would be re-adding something they removed, wearing a migration.
  * an add is skipped when the destination already carries that (kind, key).

Net: the migration touches exactly the rows it names, and only while they are
still what it expects.

────────────────────────────────────────────────────────────────────────────
THE SPLIT. "Bank reconciliation" was named for one process and pointed at
another: its refs are the payment→invoice matcher (`Cash Receipts Matching` +
`cash_receipts_matching_triage`), while bank reconciliation is Books Review —
unmatched bank LINES, ranked candidates, keyword and coded posting, the
reconciling difference. `reconciliation_review_triage` was referenced by ZERO
jobs: the platform's only bespoke triage display, absent from the Map, while a
card named after it taught something else.

One card teaching two processes is the failure the Map exists to prevent, so the
content MOVES rather than being rewritten — cash receipts keeps the description
that was always accurate for it, on a job that finally has its name.

Migration head: r156 → r157. No schema change; content only.
"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = "r157_map_accounting_content"
down_revision = "r156_customer_payment_returned"
branch_labels = None
depends_on = None

VERT = "manufacturing"

# ── Description corrections: (job, expected_current, corrected) ─────────────
#
# HONESTY RULES APPLIED TO EVERY SENTENCE BELOW:
#   * Say the NARROW true thing, never the general one. "Customer payments post"
#     is true; "payments post" is false — FHPayment and StatementPayment post
#     nothing.
#   * Structural claims (a coded row books before it clears) are properties of
#     the design and age well. STATE claims (three settings are configured) are
#     not written here at all — they belong in a derived ponder beat or nowhere.
#   * A workaround is dated, not disguised, so the sentence stops being wrong
#     when the workaround ends rather than becoming wrong the other way.
_DESCRIPTIONS = [
    (
        "Bank reconciliation",
        "Keep the bank and the books telling the same story — payments "
        "matched to invoices, and the ones that can't be matched reviewed "
        "by a person.",
        "Every line on the bank statement accounted for. A line the matcher "
        "recognises clears against what the books already recorded; a line you "
        "classify or code books its journal entry before it clears, so nothing "
        "leaves the statement unaccounted for. Whatever the matcher can't place "
        "waits in Books Review for a person.",
    ),
    (
        "Expense management",
        "Expenses categorized as they arrive — the uncertain ones queued "
        "for a quick confirm.",
        "Expenses categorized every fifteen minutes — until event dispatch "
        "exists, that sweep is what \"as they arrive\" means — with the "
        "uncertain ones queued for a quick confirm.",
    ),
    (
        "Handle the exceptions",
        "When money needs a correction — voids, credit memos, the write-off "
        "verb, and the credit pocket's doors, every one carrying its reason.",
        "When money needs a correction — voids, returned cheques, credit memos, "
        "the write-off verb, and the credit pocket's doors, every one carrying "
        "its reason. A void says the payment should never have been recorded; a "
        "return says it happened and the bank took it back, so the record "
        "survives carrying the reason.",
    ),
]

# ── Ref moves: (from_job, to_job, ref_kind, ref_key_or_automation_name) ─────
_MOVES = [
    ("Bank reconciliation", "Cash receipts matching", "automation", "Cash Receipts Matching"),
    ("Bank reconciliation", "Cash receipts matching", "triage_queue", "cash_receipts_matching_triage"),
]

# ── Ref adds: (job, ref_kind, ref_key, label) ──────────────────────────────
_ADDS = [
    ("Bank reconciliation", "triage_queue", "reconciliation_review_triage", "Books Review"),
]

_NEW_JOB = (
    "Cash receipts matching",
    # The description that was always accurate — for THIS process, which now has
    # its own card instead of borrowing another's name.
    "Payments matched to the invoices they settle — the confident ones applied, "
    "and the ones the matcher can't place with certainty queued for a person to "
    "confirm, override, or reject.",
    "Accounting",
)


def _log(msg: str) -> None:
    print(f"[r157] {msg}")


def upgrade() -> None:
    bind = op.get_bind()
    applied = skipped = 0

    def job_row(name):
        return bind.execute(
            sa.text(
                "SELECT id, description, display_order FROM moc_job "
                "WHERE name = :n AND vertical = :v AND task_type = 'Accounting'"
            ),
            {"n": name, "v": VERT},
        ).fetchone()

    # ── 1. Descriptions ────────────────────────────────────────────────────
    for name, expected, corrected in _DESCRIPTIONS:
        row = job_row(name)
        if row is None:
            _log(f"SKIP description '{name}': job absent on this database.")
            skipped += 1
            continue
        if row[1] == corrected:
            continue                                   # already applied
        if row[1] != expected:
            _log(
                f"SKIP description '{name}': the operator edited it. "
                f"Found {row[1]!r}; expected {expected!r}. Left as-is."
            )
            skipped += 1
            continue
        bind.execute(
            sa.text("UPDATE moc_job SET description = :d WHERE id = :i"),
            {"d": corrected, "i": row[0]},
        )
        applied += 1

    # ── 2. The dead ref ────────────────────────────────────────────────────
    # `Customer billing & statements` carried an automation ref whose
    # moc_task_catalog row no longer exists. `resolve_job` already reports it in
    # `dead_refs` and viewers see the plainer truth, so this is tidying a
    # self-declaring gap rather than fixing a visible break. Guarded on the
    # target genuinely being absent — if that automation ever comes back, the
    # ref was right all along and stays.
    dead = bind.execute(
        sa.text(
            "SELECT r.id, r.ref_key FROM moc_job_ref r "
            "JOIN moc_job j ON j.id = r.job_id "
            "WHERE j.vertical = :v AND j.task_type = 'Accounting' "
            "AND r.ref_kind = 'automation' "
            "AND NOT EXISTS (SELECT 1 FROM moc_task_catalog t WHERE t.id = r.ref_key)"
        ),
        {"v": VERT},
    ).fetchall()
    for ref_id, ref_key in dead:
        bind.execute(sa.text("DELETE FROM moc_job_ref WHERE id = :i"), {"i": ref_id})
        _log(f"removed dead automation ref {ref_key} (no such catalog row).")
        applied += 1

    # ── 3. The new job ─────────────────────────────────────────────────────
    new_name, new_desc, new_type = _NEW_JOB
    dest = job_row(new_name)
    if dest is None:
        src = job_row("Bank reconciliation")
        order = (src[2] + 1) if src else 0
        new_id = str(uuid.uuid4())
        bind.execute(
            sa.text(
                "INSERT INTO moc_job (id, scope, vertical, name, description, "
                "task_type, display_order, is_active) VALUES "
                "(:i, 'vertical_default', :v, :n, :d, :t, :o, true)"
            ),
            {"i": new_id, "v": VERT, "n": new_name, "d": new_desc,
             "t": new_type, "o": order},
        )
        applied += 1
        dest_id = new_id
    else:
        dest_id = dest[0]

    # ── 4. The ref moves ───────────────────────────────────────────────────
    for from_name, to_name, kind, key_or_auto in _MOVES:
        src = job_row(from_name)
        if src is None:
            _log(f"SKIP move '{key_or_auto}': source job '{from_name}' absent.")
            skipped += 1
            continue
        # Automation refs are keyed by ROW ID; resolve by name, as the seed does.
        if kind == "automation":
            auto = bind.execute(
                sa.text("SELECT id FROM moc_task_catalog WHERE name = :n"),
                {"n": key_or_auto},
            ).fetchone()
            if auto is None:
                _log(f"SKIP move: automation '{key_or_auto}' absent on this database.")
                skipped += 1
                continue
            key = auto[0]
        else:
            key = key_or_auto

        existing = bind.execute(
            sa.text(
                "SELECT id FROM moc_job_ref WHERE job_id = :j "
                "AND ref_kind = :k AND ref_key = :r"
            ),
            {"j": src[0], "k": kind, "r": key},
        ).fetchone()
        if existing is None:
            # ABSENT FROM THE SOURCE HAS TWO CAUSES AND THEY MUST NOT SHARE A
            # MESSAGE. Either this migration already moved it (a re-run — the
            # common path), or the operator deleted it before we got here. The
            # destination tells them apart. Reporting a completed move as an
            # operator deletion would misattribute on EVERY re-run, and a skip
            # log that lies on its most common path is one nobody reads.
            landed = bind.execute(
                sa.text(
                    "SELECT 1 FROM moc_job_ref WHERE job_id = :j "
                    "AND ref_kind = :k AND ref_key = :r"
                ),
                {"j": dest_id, "k": kind, "r": key},
            ).fetchone()
            if landed is not None:
                continue                    # already moved; nothing to report
            # Genuinely absent. Not moved, and deliberately NOT recreated on the
            # destination — re-adding what they removed, wearing a migration, is
            # worse than leaving the new card thinner.
            _log(
                f"SKIP move '{key_or_auto}': not present on '{from_name}' and not "
                f"on '{to_name}' — the operator removed it. Not recreated."
            )
            skipped += 1
            continue

        already = bind.execute(
            sa.text(
                "SELECT 1 FROM moc_job_ref WHERE job_id = :j "
                "AND ref_kind = :k AND ref_key = :r"
            ),
            {"j": dest_id, "k": kind, "r": key},
        ).fetchone()
        if already is None:
            bind.execute(
                sa.text(
                    "INSERT INTO moc_job_ref (id, job_id, ref_kind, ref_key, "
                    "display_order) VALUES (:i, :j, :k, :r, 0)"
                ),
                {"i": str(uuid.uuid4()), "j": dest_id, "k": kind, "r": key},
            )
        bind.execute(
            sa.text("DELETE FROM moc_job_ref WHERE id = :i"), {"i": existing[0]}
        )
        applied += 1

    # ── 5. The adds ────────────────────────────────────────────────────────
    for name, kind, key, label in _ADDS:
        row = job_row(name)
        if row is None:
            _log(f"SKIP add '{key}': job '{name}' absent.")
            skipped += 1
            continue
        already = bind.execute(
            sa.text(
                "SELECT 1 FROM moc_job_ref WHERE job_id = :j "
                "AND ref_kind = :k AND ref_key = :r"
            ),
            {"j": row[0], "k": kind, "r": key},
        ).fetchone()
        if already is not None:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO moc_job_ref (id, job_id, ref_kind, ref_key, label, "
                "display_order) VALUES (:i, :j, :k, :r, :l, 1)"
            ),
            {"i": str(uuid.uuid4()), "j": row[0], "k": kind, "r": key, "l": label},
        )
        applied += 1

    _log(f"done — {applied} applied, {skipped} skipped.")
    if skipped:
        _log(
            "Skips above are CORRECT behaviour, not failures: each names a field "
            "an operator edited or a row this database does not have. Read them; "
            "a silent skip would be the bug."
        )


def downgrade() -> None:
    # Content, not schema. A downgrade that restored the WRONG descriptions
    # would be re-teaching a process that does not exist — deliberately a no-op.
    # The corrections stand; re-running upgrade is idempotent.
    pass
