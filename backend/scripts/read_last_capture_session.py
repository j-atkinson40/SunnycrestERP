"""What did the director actually type? The most recent capture sessions, verbatim.

⚠️ READ-ONLY. It opens a read-only transaction and prints host/db only — never a
credential.

    cd backend
    PYTHONPATH=$PWD railway run \
      --project <id> --environment production --service SunnycrestERP -- \
      env PROBE_SLUG=sunnycrest PROBE_LIMIT=5 .venv/bin/python \
      scripts/read_last_capture_session.py

    # or locally
    PROBE_SLUG=testco PYTHONPATH=$PWD .venv/bin/python scripts/read_last_capture_session.py

⚠️ IT PRINTS THE STORED EXTRACTION BESIDE THE TEXT, AND THAT PAIRING IS THE WHOLE
POINT. A bug report from a screenshot says what a row DISPLAYED; `values` says what the
engine CONCLUDED and `unrecognized` says what it could not place. Reading the text alone
would send the next reader back to re-derive the extraction from a sentence, which is
how a reproduction ends up testing a sentence nobody typed.

⚠️ `full_text` AND `typed_lines` ARE BOTH PRINTED BECAUSE THEY CAN DISAGREE, and the
difference decides which door the session came through. `set_text` replaces `full_text`
on every keystroke and is the typed pane's source of truth; `add_line` appends to
`typed_lines` and accumulates. A reproduction driven through the wrong one can measure
different extraction from the same words — measured 2026-10-30 on
"full equipment, 12 chairs, 6 extra chairs", where the two doors disagree about whether
`chairs_total` is captured at all.

⚠️ NO DECEASED NAME IS PRINTED IN FULL. `values` and the typed text carry a real
person's name, their funeral home, their cemetery and their service date. The typed text
is what the bug is about so it is printed as typed; `deceased_name` is reduced to its
shape (length and word count) because the reproduction needs the SHAPE of the field, not
the family's name. Set `PROBE_FULL_NAMES=1` only if a name is itself the subject.
"""
import json
import os
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

SLUG = os.environ.get("PROBE_SLUG", "sunnycrest")
LIMIT = int(os.environ.get("PROBE_LIMIT", "5"))
FULL_NAMES = os.environ.get("PROBE_FULL_NAMES") == "1"

url = os.environ["DATABASE_URL"]
p = urlparse(url)
print(f"host={p.hostname} db={(p.path or '').lstrip('/')}  tenant={SLUG}  READ-ONLY\n")

eng = create_engine(url, connect_args={"options": "-c default_transaction_read_only=on"})
db = sessionmaker(bind=eng)()

tid = db.execute(text("SELECT id FROM companies WHERE slug=:s"), {"s": SLUG}).scalar()
assert tid, f"no company with slug {SLUG!r}"


def redact(values: dict) -> dict:
    if FULL_NAMES:
        return values
    out = dict(values)
    raw = out.get("deceased_name")
    if isinstance(raw, str) and raw:
        out["deceased_name"] = f"<{len(raw)} chars, {len(raw.split())} words>"
    return out


rows = db.execute(
    text(
        "SELECT id, status, object_type, created_at, updated_at, full_text, "
        "       typed_lines, values, unrecognized, pending_picks, resolutions, "
        "       sales_order_id "
        "FROM capture_sessions WHERE company_id = :t "
        "ORDER BY updated_at DESC NULLS LAST LIMIT :n"
    ),
    {"t": tid, "n": LIMIT},
).mappings().all()

print(f"{len(rows)} most recently updated capture sessions\n")

for i, r in enumerate(rows, 1):
    print("=" * 78)
    print(f"[{i}] session {r['id']}  status={r['status']}  type={r['object_type']}")
    print(f"    created={r['created_at']}  updated={r['updated_at']}")
    print(f"    sales_order_id={r['sales_order_id']}")

    # ⚠️ `repr`, NOT bare printing. A trailing space, a double space or a newline
    # inside the typed text changes how the extractor clauses it, and a bug about
    # which field a word landed in can turn on exactly that.
    print(f"\n    full_text = {r['full_text']!r}")

    lines = r["typed_lines"] or []
    print(f"    typed_lines ({len(lines)}):")
    for ln in lines:
        if isinstance(ln, dict):
            print(f"        {ln.get('at')}  {ln.get('line')!r}")
        else:
            print(f"        {ln!r}")

    print(f"\n    values = {json.dumps(redact(r['values'] or {}), indent=8, default=str)}")
    print(f"    unrecognized = {r['unrecognized']!r}")
    print(f"    pending_picks = {json.dumps(r['pending_picks'] or [], default=str)}")
    print(f"    resolutions = {json.dumps(r['resolutions'] or {}, default=str)}")
    print()

db.close()
