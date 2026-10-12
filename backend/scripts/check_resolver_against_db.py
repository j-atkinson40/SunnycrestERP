"""READ-ONLY: run the real resolver against whatever DATABASE_URL names.

    railway run --project ad95792e-6625-4bf5-ad61-ead9c291bdf9 \
      --environment production --service SunnycrestERP \
      -- .venv/bin/python scripts/check_resolver_against_db.py


⚠️ THE RESOLVER IS A PURE READ. `build_index` selects from
product_variant_templates + product_templates + platform_product_aliases;
`resolve` is a dict lookup. Nothing here writes, and the engine is opened
read-only at the connection level anyway.

⚠️ WHY NOT JUST TRUST THE DEV TESTS. Dev and production are different catalogs and
different alias tables. The two behaviours James is about to type into the pane —
"oversized" and an urn vault by name — were measured on dev. This measures them
where he will see them.
"""
import os
import sys
from urllib.parse import urlparse

# ⚠️ cwd ON sys.path, BECAUSE THE FIRST RUN OF THIS FAILED WITHOUT IT. Python puts
# the SCRIPT'S directory on the path, not the working directory, so `from app...`
# raised ModuleNotFoundError when the file sat in /tmp. It lives in scripts/ now and
# is run from `backend/`, which is what this line makes work.
sys.path.insert(0, os.getcwd())
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.services.product_name_resolver import build_index, resolve

url = os.environ["DATABASE_URL"]; u = urlparse(url)
print(f"TARGET: host={u.hostname} port={u.port} db={(u.path or '').lstrip('/')} (read-only)")
e = create_engine(url, connect_args={"options": "-c default_transaction_read_only=on"})
with Session(e) as db:
    idx = build_index(db)
    print(f"[control] surface forms indexed: {len(idx.by_form)}   alias rows read: {idx.alias_count}")
    assert len(idx.by_form) > 100, "the index is blind; nothing below means anything"
    cases = [
        ("oversized", "the walk, line 6"),
        ("OS", None), ("O/S", None), ("OVS", None),
        ("oversized Continental", None),
        ("oversized graveliner", None),
        ("Continental 34", "a bare number"),
        ("34 inch Continental", "the pre-existing form"),
        ("Veteran urn vault", "the bug James wanted gone"),
        ("SST urn vault", None), ("Cameo Rose urn vault", None),
        ("Veteran burial vault", "the other direction"),
        ("Veteran", "now ASKS"),
        ("oversized urn vault", "must be NO MATCH"),
        ("Continental urn vault", "must be NO MATCH"),
        ("Boston", "word-boundary control"),
        ("cosmos", None), ("Rosewood", None),
        ("graveliner", "bare family word keeps UV-GL"),
    ]
    for phrase, note in cases:
        r = resolve(idx, phrase)
        skus = sorted(c.sku for c in r.candidates)
        disc = [d.value for d in r.discriminators]
        tail = f"   <- {note}" if note else ""
        print(f"  {phrase!r:26s} n={len(skus)} {skus} disc={disc}{tail}")
