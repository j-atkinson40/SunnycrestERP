"""Which products can the VAULT slot reach from a phrase, and which of them are vaults?

⚠️ READ-ONLY. Opens a read-only transaction; prints host/db only, never a credential.

    cd backend
    PYTHONPATH=$PWD railway run \
      --project <id> --environment production --service SunnycrestERP -- \
      env PROBE_SLUG=sunnycrest PROBE_PHRASE=chairs PYTHONPATH=/app \
      .venv/bin/python scripts/read_vault_candidates_for_phrase.py

    # or locally
    PROBE_SLUG=testco PROBE_PHRASE=chairs PYTHONPATH=$PWD \
      .venv/bin/python scripts/read_vault_candidates_for_phrase.py

⚠️ IT ASKS THE RESOLVER, NOT A `LIKE` QUERY, because the question is what the VAULT SLOT
can reach and that is the resolver's answer rather than the database's. A hand-written
`name ILIKE '%chairs%'` would list products the resolver never offers and miss ones it
reaches by alias or by trigram.

⚠️ AND IT PRINTS THE FORM BESIDE EVERY CANDIDATE, which is the entire diagnostic. A
candidate list is not wrong for containing a chairs product; it is wrong for OFFERING one
to a field that can only hold a vault. Form comes from the same `vault_form` reading the
capture uses, so what prints here is what the capture would have seen.
"""
import os
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

SLUG = os.environ.get("PROBE_SLUG", "sunnycrest")
PHRASES = [p for p in os.environ.get("PROBE_PHRASE", "chairs").split("|") if p]

url = os.environ["DATABASE_URL"]
p = urlparse(url)
print(f"host={p.hostname} db={(p.path or '').lstrip('/')}  tenant={SLUG}  READ-ONLY\n")

eng = create_engine(url, connect_args={"options": "-c default_transaction_read_only=on"})
db = sessionmaker(bind=eng)()

tid = db.execute(text("SELECT id FROM companies WHERE slug=:s"), {"s": SLUG}).scalar()
assert tid, f"no company with slug {SLUG!r}"

from app.services.product_name_resolver import build_index, resolve  # noqa: E402

rows = db.execute(
    text(
        "SELECT id, name, sku, variant_template_id, is_active "
        "FROM products WHERE company_id = :t ORDER BY name"
    ),
    {"t": tid},
).mappings().all()
print(f"{len(rows)} products on this tenant\n")

# ⚠️ EVERY PRODUCT WHOSE NAME CONTAINS A CHAIR WORD, LISTED FIRST AND UNCONDITIONALLY.
# The screenshot named one ("Graveside Chairs") and the price list has another ("Extra
# Chairs (Over 8)"); a fix aimed at one name would leave the other reachable.
print("-- products whose name mentions chairs --")
for r in rows:
    if "chair" in (r["name"] or "").casefold():
        print(f"   {r['name']!r:36} sku={r['sku']!r:16} "
              f"variant_template_id={r['variant_template_id']} active={r['is_active']}")

print("\n-- platform_product_aliases mentioning chairs --")
for a in db.execute(
    text(
        "SELECT alias_text, variant_template_id, source, is_confirmed "
        "FROM platform_product_aliases WHERE alias_text ILIKE '%chair%'"
    )
).mappings().all():
    print(f"   {a['alias_text']!r:24} template={a['variant_template_id']} "
          f"source={a['source']} confirmed={a['is_confirmed']}")

print("\n-- product_templates mentioning chairs --")
for t in db.execute(
    text("SELECT id, display_name, form, family_slug FROM product_templates "
         "WHERE display_name ILIKE '%chair%' OR family_slug ILIKE '%chair%'")
).mappings().all():
    print(f"   {t['display_name']!r:36} form={t['form']!r} family={t['family_slug']!r}")

# ⚠️ NO TENANT ARGUMENT, AND THAT IS ITSELF PART OF THE FINDING. `build_index`
# reads `product_variant_templates` JOIN `product_templates` with no company
# filter, so the vault slot's candidate set is the WHOLE PLATFORM CATALOG — every
# form, every family, on every tenant.
index = build_index(db)
for phrase in PHRASES:
    print(f"\n{'=' * 74}\nresolve(vault phrase={phrase!r})")
    res = resolve(index, phrase)
    print(f"   variant_template_id = {getattr(res, 'variant_template_id', None)}")
    cands = list(getattr(res, "candidates", ()) or ())
    print(f"   candidates ({len(cands)}):")
    for c in cands:
        # ⚠️ THE FORM IS LOOKED UP PER CANDIDATE RATHER THAN TRUSTED FROM THE CANDIDATE
        # OBJECT, so this probe reports what the database says and not what the
        # resolver's own dataclass happens to carry.
        form = db.execute(
            text(
                "SELECT pt.form FROM products pr "
                "LEFT JOIN product_templates pt ON pt.id = pr.variant_template_id "
                "WHERE pr.company_id = :t AND lower(btrim(pr.name)) = lower(btrim(:n)) "
                "LIMIT 1"
            ),
            {"t": tid, "n": getattr(c, "name", "")},
        ).scalar()
        print(f"      name={getattr(c, 'name', None)!r:36} sku={getattr(c, 'sku', None)!r:16} form={form!r}")
    print(f"   discriminators = {[getattr(d, 'value', d) for d in (getattr(res, 'discriminators', ()) or ())]}")

db.close()
