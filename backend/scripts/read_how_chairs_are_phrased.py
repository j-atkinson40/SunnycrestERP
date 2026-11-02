"""How does anyone actually SAY "chairs"? Every free-text hit, with its source.

⚠️ READ-ONLY. Opens a read-only transaction; prints host/db only, never a credential.

    cd backend
    PYTHONPATH=$PWD railway run \
      --project <id> --environment production --service SunnycrestERP -- \
      env PROBE_SLUG=sunnycrest PROBE_WORD=chair PYTHONPATH=$PWD \
      .venv/bin/python scripts/read_how_chairs_are_phrased.py

⚠️ IT EXISTS BECAUSE A RULING TURNED ON A PHRASING QUESTION AND I HAD NO EVIDENCE FOR
IT. James, 2026-11-02: *"confirm that 'chairs' on its own means 'the normal chairs', not
'some extra chairs'. If directors actually say 'chairs' to mean extras, change the
ruling."* The honest way to answer that is to read what people have typed, and the
honest way to report it is to say how many rows there were.

⚠️ THE COLUMN LIST IS DECLARED, NOT DISCOVERED, AND THAT IS A LIMIT RATHER THAN A
CHOICE. Sweeping every text column in the schema would mean reading case notes and
contact notes that have nothing to do with equipment and do carry personal detail. The
columns below are the ones where a director's own words about an ORDER can land. A
phrasing living anywhere else will not appear here, and this script's output is
therefore a floor on the evidence, never a census.

⚠️ AND A ZERO IS REPORTED AS A ZERO, LOUDLY. The whole failure mode this guards against
is a quiet empty result read as "nobody says it that way". Each column prints its row
count whether or not it matched, so "no hits" and "no rows at all" cannot be confused —
that distinction is the one CLAUDE.md §11 calls a test passing because data is MISSING.
"""
import os
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

SLUG = os.environ.get("PROBE_SLUG", "sunnycrest")
WORD = os.environ.get("PROBE_WORD", "chair")

url = os.environ["DATABASE_URL"]
p = urlparse(url)
print(f"host={p.hostname} db={(p.path or '').lstrip('/')}  tenant={SLUG}  word={WORD!r}  READ-ONLY\n")

eng = create_engine(url, connect_args={"options": "-c default_transaction_read_only=on"})
db = sessionmaker(bind=eng)()

tid = db.execute(text("SELECT id FROM companies WHERE slug=:s"), {"s": SLUG}).scalar()
assert tid, f"no company with slug {SLUG!r}"

#: (table, text expression, tenant column or None). Declared — see the docstring.
SOURCES: list[tuple[str, str, str | None]] = [
    ("capture_sessions", "full_text", "company_id"),
    ("capture_sessions", "typed_lines::text", "company_id"),
    ("command_bar_history", "query_text", "company_id"),
    ("cemeteries", "equipment_note", "company_id"),
    ("cemeteries", "access_notes", "company_id"),
    ("sales_orders", "notes", "company_id"),
    ("sales_order_lines", "description", None),
    ("activity_log", "transcript", "company_id"),
    ("activity_log", "body", "company_id"),
    ("ringcentral_call_extractions", "raw_response::text", None),
    ("intelligence_executions", "input_payload::text", None),
]

for table, expr, tenant_col in SOURCES:
    exists = db.execute(
        text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"),
        {"t": table},
    ).scalar()
    if not exists:
        print(f"-- {table}.{expr}: TABLE ABSENT")
        continue
    col = expr.split("::")[0]
    has_col = db.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": col},
    ).scalar()
    if not has_col:
        print(f"-- {table}.{expr}: COLUMN ABSENT")
        continue

    # ⚠️ THE TENANT COLUMN IS CHECKED, NOT ASSUMED, AND A MISSING ONE WIDENS THE SWEEP
    # RATHER THAN SKIPPING THE TABLE. `activity_log` has no `company_id` and the first
    # version of this script died on it mid-run — which would have left the columns
    # after it unread while the output still looked like a report.
    if tenant_col and not db.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": tenant_col},
    ).scalar():
        print(f"   (no {tenant_col} on {table} — swept across all tenants)")
        tenant_col = None
    where_tenant = f" WHERE {tenant_col} = :t" if tenant_col else ""
    params = {"t": tid} if tenant_col else {}
    total = db.execute(
        text(f"SELECT count(*) FROM {table}{where_tenant}"), params
    ).scalar()

    joiner = " AND" if tenant_col else " WHERE"
    hits = db.execute(
        text(
            f"SELECT {expr} AS v FROM {table}{where_tenant}{joiner} "
            f"{expr} ILIKE :w ORDER BY 1 LIMIT 40"
        ),
        {**params, "w": f"%{WORD}%"},
    ).scalars().all()

    # ⚠️ THE ROW COUNT PRINTS EVEN WHEN THERE ARE NO HITS. See the docstring: a zero
    # over zero rows and a zero over nine thousand are different findings.
    print(f"-- {table}.{expr}: {len(hits)} hit(s) of {total} row(s)")
    for v in hits:
        s = " ".join(str(v).split())
        print(f"      {s[:300]!r}")

db.close()
