"""Phase 5c precondition — retroactively apply 5b's supersede rule to the backlog.

⚠️ THIS IS NOT A STALENESS MARK, AND THE DISTINCTION IS THE WHOLE POINT.

The dispatch that asked for this called the population "stale rows" and put the
count near 2,021. Measured against production 2026-09-08, THE DOMINANT SUBSET IS
NOT STALE. The 1,825 `expense_no_gl_mapping` rows all say

    "Category 'vehicle_expense' has no GL account mapping for this tenant."

and `vehicle_expense` is STILL UNMAPPED for that tenant today. The condition
holds. The agent went quiet on 2026-08-31 for an unrelated reason — it finds no
uncategorized lines to classify, so it never reaches the mapping check — and an
agent's silence is not the same fact as a condition being resolved. Marking
those rows "stale" would delete the only record of a live problem.

WHAT THIS SCRIPT DOES INSTEAD, on a basis that needs no staleness claim:
**keeps the NEWEST open row for each key and supersedes the older ones.** That is
exactly the rule the 5b listener applies going forward, applied backwards. It is
honest for every row it touches — an older duplicate WAS replaced by a later
occurrence of the same finding — and it leaves every distinct condition still
visible as one open row. Nothing is hidden; 1,825 copies of one sentence become
one copy of that sentence.

It is also precisely what 5c's unique index requires, and no more.

SAFETY PROPERTIES
- Population is a PREDICATE, never an id list. An id list captured at authoring
  time goes stale before running, and the nightly drain moves rows in between.
- Order-independent with respect to the drain. `ar_collections` supersedes its
  own duplicates on its next run; if that happens first, those keys hold one row
  and this script is a no-op on them. If this runs first, it produces the same
  end state the drain would have. Either order, same result.
- Writes `superseded_at` and NOTHING else. Never `resolved`, `resolved_at`,
  `resolved_by` or `resolution_note` — marking a row resolved would claim a
  human acted on it, which is a false statement in the audit trail.
- Idempotent. Re-running supersedes nothing new.
- Dry-run by default. `--apply` is required to write.

⚠️ DISTINGUISHABILITY — UNRESOLVED, AND THIS SHOULD NOT RUN UNTIL IT IS.

`superseded_at` alone does NOT carry enough to tell these rows from
agent-driven supersedes. The only separator is an ARTIFACT: every row this
script writes shares one transaction timestamp to the microsecond, while the
listener stamps each row with its own `datetime.now()`. That works, and it is
inference from a coincidence of implementation rather than a recorded fact.
Nobody querying "what did the machine replace" in three months will know to
exclude a magic timestamp, and the answer they get will include ~2,000 rows no
machine replaced.

Two ways to close it, both James's to choose, NEITHER done here:
  (a) accept the shared timestamp as the discriminator and write it into
      STATE.md so the exclusion is discoverable; or
  (b) record the operation in `audit_logs`, so the discriminator is a row
      somebody wrote rather than a pattern somebody notices.

A third option -- a `superseded_reason` column -- is the honest schema fix and
is NOT taken here, because adding a column unilaterally is exactly what the
dispatch forbade.
"""

from __future__ import annotations

import argparse
import json
import os
import uuid
from urllib.parse import urlparse

from sqlalchemy import create_engine, text

# Keys are grouped exactly as the 5b listener groups them: NULL subject columns
# MATCH each other (IS NOT DISTINCT FROM). A default unique index disagrees --
# it treats NULLs as distinct -- which is why 5c must use NULLS NOT DISTINCT.
# If these two ever diverge, this script and the index mean different things by
# "duplicate", and the 1,825 NULL-subject rows are the entire difference.
_SELECT_DOOMED = """
    WITH ranked AS (
        SELECT id,
               row_number() OVER (
                   PARTITION BY tenant_id, anomaly_type, entity_type, entity_id
                   ORDER BY created_at DESC, id DESC
               ) AS rn
        FROM agent_anomalies
        WHERE resolved = false AND superseded_at IS NULL
    )
    SELECT id FROM ranked WHERE rn > 1
"""


def _report(c) -> None:
    print("\n-- open rows (resolved = false AND superseded_at IS NULL)")
    print("   ", c.execute(text(
        "SELECT count(*) FROM agent_anomalies "
        "WHERE resolved = false AND superseded_at IS NULL")).scalar())
    for label, extra in (
        ("listener grouping (NULLs MATCH)", ""),
        ("default-index grouping (NULLs DISTINCT)",
         "AND entity_type IS NOT NULL AND entity_id IS NOT NULL"),
    ):
        r = c.execute(text(f"""
            SELECT count(*), coalesce(sum(n - 1), 0) FROM (
              SELECT count(*) AS n FROM agent_anomalies
              WHERE resolved = false AND superseded_at IS NULL {extra}
              GROUP BY tenant_id, anomaly_type, entity_type, entity_id
              HAVING count(*) > 1) z""")).fetchone()
        print(f"-- colliding keys, {label}: {r[0]}  excess rows: {r[1]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="actually write. Without it, nothing is modified.")
    args = ap.parse_args()

    url = os.environ["DATABASE_URL"]
    u = urlparse(url)
    print(f"target: host={u.hostname} port={u.port} db={(u.path or '/')[1:]}")

    eng = create_engine(url) if args.apply else create_engine(
        url, connect_args={"options": "-c default_transaction_read_only=on"})

    with eng.connect() as c:
        print("\n=== BEFORE ===")
        _report(c)
        doomed = c.execute(text(f"SELECT count(*) FROM ({_SELECT_DOOMED}) d")).scalar()
        print(f"\nrows this would supersede: {doomed}")
        print("per key, newest open row is KEPT; older open rows are superseded.")
        print("\nbreakdown by anomaly_type:")
        for r in c.execute(text(f"""
            SELECT anomaly_type, count(*) FROM agent_anomalies
            WHERE id IN ({_SELECT_DOOMED}) GROUP BY 1 ORDER BY 2 DESC""")):
            print(f"   {r[0]:<34} {r[1]}")

    if not args.apply:
        print("\nDRY RUN — nothing written. Re-run with --apply to write.")
        return 0

    with eng.begin() as c:
        # Per-tenant breakdown must be captured BEFORE the UPDATE — afterwards
        # the predicate no longer matches these rows.
        breakdown: dict[str, dict[str, int]] = {}
        for r in c.execute(text(f"""
            SELECT tenant_id, anomaly_type, count(*) FROM agent_anomalies
            WHERE id IN ({_SELECT_DOOMED}) GROUP BY 1, 2""")):
            breakdown.setdefault(r[0], {})[r[1]] = r[2]

        # now() is the TRANSACTION timestamp, so every row written by this run
        # shares it to the microsecond. That is what makes the reversal below a
        # single exact-match UPDATE.
        stamp = c.execute(text("SELECT now()")).scalar()
        n = c.execute(text(f"""
            UPDATE agent_anomalies SET superseded_at = :stamp
            WHERE id IN ({_SELECT_DOOMED})"""), {"stamp": stamp}).rowcount
        print(f"\nsuperseded {n} rows across {len(breakdown)} tenant(s)")

        # ── The audit record. One row per tenant, deliberately TENANT-VISIBLE.
        #
        # `GET /api/v1/audit` scopes to the caller's company, so each tenant
        # sees the operation on THEIR data and no one else's. That visibility is
        # the point: a tenant admin who later finds rows superseded with nothing
        # in the audit log has been handed a mystery, and a log that omits what
        # the platform did is a partial record that reads as a complete one.
        #
        # ⚠️ THE ACTION NAME NAMES THE ACTOR. `anomaly_resolved` (the existing
        # entry in this vocabulary) means a person decided something. This did
        # not resolve anything, and a reader who conflates the two will believe
        # decisions were made on their books. `platform_maintenance.*` says
        # Bridgeable operated on their data.
        #
        # ⚠️ AND `changes` IS WRITTEN FOR SOMEONE WHO HAS NEVER HEARD OF THIS
        # ARC. It is the only explanation they will ever get.
        for tenant_id, by_type in breakdown.items():
            retired = sum(by_type.values())
            still_open = c.execute(text("""
                SELECT count(*) FROM (
                  SELECT 1 FROM agent_anomalies
                  WHERE tenant_id = :t AND resolved = false AND superseded_at IS NULL
                  GROUP BY anomaly_type, entity_type, entity_id) z"""),
                {"t": tenant_id}).scalar()
            payload = {
                "summary": (
                    "Bridgeable removed duplicate copies of accounting-agent "
                    "findings on this account. Nothing was resolved, deleted or "
                    "edited. Every distinct finding is still open and unchanged; "
                    "only repeated copies of the same finding were retired."
                ),
                "why": (
                    "Until now the accounting agents created a new finding every "
                    "time they ran, instead of updating the one already there, so "
                    "a single unresolved issue could appear hundreds of times. The "
                    "agents now update in place. This is a one-time cleanup of the "
                    "copies made before that change."
                ),
                "what_you_may_notice": (
                    "Anomaly counts, badges and review queues will be lower. No "
                    "issue has gone away: each distinct one still has exactly one "
                    "open entry, and any issue that is still true is still shown."
                ),
                "performed_by": (
                    "Bridgeable platform maintenance — not a user on this account."
                ),
                "duplicate_rows_retired": retired,
                "distinct_findings_still_open": still_open,
                "retired_by_finding_type": by_type,
                "marked_at": stamp.isoformat(),
                "reversible": (
                    "Yes. These rows were marked superseded, not deleted, and the "
                    "mark can be undone."
                ),
            }
            c.execute(text("""
                INSERT INTO audit_logs
                    (id, company_id, user_id, actor_type, action, entity_type,
                     entity_id, changes, created_at)
                VALUES (:id, :cid, NULL, 'tenant_user',
                        'platform_maintenance.anomalies_deduplicated',
                        'agent_anomaly', NULL, :changes, :ts)"""),
                {"id": str(uuid.uuid4()), "cid": tenant_id,
                 "changes": json.dumps(payload), "ts": stamp})
            print(f"  audit_logs row written for tenant {tenant_id}: "
                  f"{retired} retired, {still_open} distinct findings left open")

        print("\n" + "=" * 68)
        print("⚠️ RECORD THIS TIMESTAMP. IT IS THE HANDLE ON THIS OPERATION.")
        print(f"   superseded_at = {stamp!r}")
        print("   It is also recorded in audit_logs.changes.marked_at, which is")
        print("   the discriminator: a row somebody wrote, not a pattern to spot.")
        print("   Reversal (restores the prior state exactly):")
        print("     UPDATE agent_anomalies SET superseded_at = NULL")
        print(f"      WHERE superseded_at = '{stamp}';")
        print(f"     DELETE FROM audit_logs WHERE created_at = '{stamp}'")
        print("       AND action = 'platform_maintenance.anomalies_deduplicated';")
        print("=" * 68)

    with eng.connect() as c:
        print("\n=== AFTER ===")
        _report(c)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
