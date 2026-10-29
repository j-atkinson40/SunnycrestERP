"""Which personal names prefix-match this tenant's records, and would displace a field?

⚠️ READ-ONLY. Run it against production; it opens a read-only transaction and prints
host/port/db only — never a credential.

    cd backend
    PYTHONPATH=$PWD PROBE_SLUG=sunnycrest railway run \
      --project <id> --environment production --service SunnycrestERP -- \
      env PROBE_SLUG=sunnycrest .venv/bin/python scripts/check_prefix_name_collisions.py

    # or locally
    PROBE_SLUG=testco PYTHONPATH=$PWD .venv/bin/python scripts/check_prefix_name_collisions.py

⚠️ KEPT AS A SCRIPT BY RULING (James, 2026-10-29) BECAUSE IT MUST BE RE-RUN AT THE
ONBOARDING CUTOVER. The 2026-10-29 measurement found `river`/`rivers` displacing
*Riverside Memorial Chapel* — but Riverside is DEMO SEED. Sunnycrest's real funeral
homes, cemeteries and products arrive at the cutover, and that is the run that counts.
It is on the cutover checklist in STATE.md.

⚠️ ALWAYS READ THE POSITIVE CONTROL BEFORE THE RESULT. Run it against `testco` FIRST and
confirm it reports displacements (6 at the time of writing: green, john, johnson, river,
rivers, smith). A zero from this script means nothing on its own — two earlier versions
of it returned zero on BOTH tenants while the defect was live:

  v1 asked `resolve_funeral_home(tid, word)`, which returns NO candidates for "john"
     while the extractor demonstrably sets the funeral home from it. Wrong component,
     well-formed zero, worthless. Caught only because the control failed to fire.
  v2 drove `extract_text` over ~107 candidates — correct, but seven minutes against the
     production proxy, so it timed out.

This is v3: it enumerates every prefix of every word in every record — a small closed set
derived from the data itself — intersects that with personal names, and only then drives
`extract_text` for the overlap. Same question, sides swapped. It reproduces v2's testco
result exactly, which is the cross-check that it asks the right thing.

⚠️ THE NAME LIST BELOW IS NOT AUTHORITATIVE AND MUST NOT BE READ AS A CENSUS. Two
declared sources: name-words that ACTUALLY OCCUR in this database (deceased names,
contact names), plus a list of common US first names and surnames written by hand. A
name outside it that prefixes a record will not appear in the output. Widen the list, or
read the full first-word listing the script prints at the end.
"""
import os
from urllib.parse import urlparse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.services.capture.prefix_resolve import GENERIC_WORDS, MIN_PREFIX
from app.services.capture.typed_extraction import extract_text
from app.services.party_resolver import cemetery_rows, funeral_home_rows

MY_FIRST_NAMES = """james john robert michael william david richard joseph thomas charles
mary patricia jennifer linda elizabeth barbara susan jessica sarah karen
christopher daniel matthew anthony mark donald steven paul andrew joshua
nancy lisa margaret betty sandra ashley dorothy kimberly emily donna
ann anna rose grace ruth jean joan carol alice helen""".split()
MY_SURNAMES = """smith johnson williams brown jones garcia miller davis rodriguez martinez
hernandez lopez gonzalez wilson anderson thomas taylor moore jackson martin
lee perez thompson white harris sanchez clark ramirez lewis robinson
walker young allen king wright scott torres nguyen hill flores
hopkins rivers river mary marys stone hart ward cross bell""".split()

SLUG = os.environ.get("PROBE_SLUG", "sunnycrest")
url = os.environ["DATABASE_URL"]; p = urlparse(url)
print(f"host={p.hostname} db={(p.path or '').lstrip('/')}  tenant={SLUG}  READ-ONLY\n")
eng = create_engine(url, connect_args={"options": "-c default_transaction_read_only=on"})
db = sessionmaker(bind=eng)()
tid = db.execute(text("SELECT id FROM companies WHERE slug=:s"), {"s": SLUG}).scalar()
assert tid, SLUG

fhs = [n for _i, n, _c in funeral_home_rows(db, tid)]
cems = [n for _i, n, _c in cemetery_rows(db, tid)]
prods = db.execute(text("SELECT name FROM products WHERE company_id=:t AND is_active"),
                   {"t": tid}).scalars().all()
records = [("funeral_home", n) for n in fhs] + [("cemetery", n) for n in cems] \
        + [("product", n) for n in prods]
print(f"records: {len(fhs)} funeral homes, {len(cems)} cemeteries, {len(prods)} products")

occurring = set()
for row in db.execute(text("SELECT DISTINCT deceased_name FROM sales_orders WHERE deceased_name IS NOT NULL")).scalars():
    occurring.update(w.casefold() for w in str(row).split())
for row in db.execute(text("SELECT DISTINCT name FROM contacts WHERE name IS NOT NULL")).scalars():
    occurring.update(w.casefold() for w in str(row).split())
names = {c for c in (occurring | set(MY_FIRST_NAMES) | set(MY_SURNAMES)) if c.isalpha()}
print(f"personal-name words: {len(names)}  (db-occurring {len(occurring)} + my supplied list)")

# every prefix of every non-generic word in every record, at or above MIN_PREFIX
prefixes: dict[str, list[tuple[str, str]]] = {}
total = 0
for kind, rec in records:
    for word in str(rec).replace('"', " ").split():
        w = "".join(ch for ch in word.casefold() if ch.isalpha())
        if not w or w in GENERIC_WORDS:
            continue
        for n in range(MIN_PREFIX, len(w) + 1):
            total += 1
            prefixes.setdefault(w[:n], []).append((kind, rec))
print(f"distinct prefixes derived from the records: {len(prefixes)} (from {total} generated)")

overlap = sorted(set(prefixes) & names)
print(f"\n=== THE LIST: record prefixes that are also personal names ===")
if not overlap:
    print("  NONE.")
for pre in overlap:
    where = sorted({f"{k}:{r}" for k, r in prefixes[pre]})
    exact = any("".join(ch for ch in str(r).casefold() if ch.isalpha()) == pre
                for _k, r in prefixes[pre])
    print(f"  {pre!r:12} prefixes {where}   whole-record-name={exact}")

print(f"\n  overlap: {len(overlap)}")

if overlap and fhs:
    anchor_word = str(fhs[0]).split()[0]
    base = extract_text(db, tenant_id=tid, text=f"order for {anchor_word} thursday")
    settled = base.values.get("funeral_home")
    print(f"\n=== end-to-end, only for the overlap (baseline funeral_home={settled!r}) ===")
    for pre in overlap:
        if pre == anchor_word.casefold():
            print(f"  {pre!r:12} skipped — it IS the anchor")
            continue
        ex = extract_text(db, tenant_id=tid, text=f"order for {anchor_word}, {pre}, thursday")
        got = ex.values.get("funeral_home")
        print(f"  {pre!r:12} funeral_home -> {got!r}  "
              f"{'DISPLACED' if got != settled else 'kept'}   "
              f"deceased={ex.values.get('deceased_name')!r} held={ex.unrecognized}")
