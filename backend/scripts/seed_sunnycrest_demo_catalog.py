"""Give the canonical dev/CI Sunnycrest the demo catalogue it is tested against.

⚠️ WHY THIS EXISTS. Backend CI failed on every commit from 2026-10-16 to 2026-10-21 for
ONE cause, reproduced on a database built exactly the way CI builds it (createdb →
`alembic upgrade head` → `scripts/seed_dev.sh`, 53 seeds, 53 succeeded, 0 failed):

    sunnycrest id: 7e81fe69-…
       company_entities: 0
       cemeteries:       0
       products:         0

The canonical seed set creates the sunnycrest COMPANY and none of its operational data.
Four tests are written against that data and had been passing on developers' machines
only — on an accumulated row nothing reproducible had put there. CLAUDE.md names the
shape twice over: "a test can pass because data is MISSING" and "before concluding a gate
would have caught something, check its environment can contain it".

⚠️ THE TESTS ARE NOT THE DEFECT, AND THAT IS WHY THIS IS A SEED RATHER THAN A TEST EDIT.
`test_declining_is_never_a_conflict` says so in terms: "Using Sunnycrest's own data rather
than a fixture is the point: this bug was invisible to every synthetic tenant because the
synthetic vaults all offer something." Replacing that with a fixture would delete the
property it exists to hold. The missing half is the environment.

⚠️ TIER `local-only`, WHICH IS THE WHOLE SAFETY ARGUMENT. `run_canonical_seeds.sh` runs
on EVERY production deploy through `railway-start.sh`, and production's sunnycrest holds
the real company's real catalogue. A seed writing demo products there would be a
production write nobody asked for. `local-only` is skipped whenever the runner sees a
deployed environment, so this reaches CI and developer machines and never production.

⚠️ THE NAMES AND PRICES MIRROR WHAT PRODUCTION ACTUALLY CARRIES, measured read-only on
2026-10-21: ten products, spelled as full display names. James's own description —
"Sunnycrest only carries the demo catalog: Monticello, Continental and the urn vault" —
is the shape reproduced here. Prices are plausible demo figures, NOT production's; no
figure was copied out of the real company's price list.

Option A idempotent: create / no-op / update-if-stale. Safe to re-run.
"""

from __future__ import annotations

import logging
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402

log = logging.getLogger("seed_sunnycrest_demo_catalog")

SLUG = "sunnycrest"

#: The one funeral home the capture tests name, and its customer record. Both are
#: needed: the ENTITY is what the extractor resolves "hopkins" against, and the CUSTOMER
#: is what `approval.assess` requires before an order can be approved — two tables, one
#: counterparty, and the blockers name them separately.
FUNERAL_HOME = "Hopkins Funeral Home"

def _migration_constants() -> tuple[list, list, str, str]:
    """The equipment names, prices and cemetery from `r211`/`r212` themselves.

    ⚠️ IMPORTED RATHER THAN RETYPED, AND A TEST CAUGHT ME RETYPING THEM. My first
    version carried its own price list and priced `Full Equipment` at 275.00; the ruled
    figure is **300.00**, written in `r211.EQUIPMENT`. The full gate went red on
    `test_the_summary_carries_a_priced_line_per_billable_thing`, because
    `approval._product_by_exact_name` takes the OLDEST row by `created_at` — so a seeded
    row at the wrong price silently outranked the fixture's own.

    ⚠️ AND A THIRD COPY OF A PRICE LIST IS THE "TWO LISTS" DEFECT THIS CODEBASE KEEPS
    RECORDING. r211 and r212 are the authority; this reads them.

    ⚠️ BY PATH, BECAUSE `alembic/versions/` IS NOT AN IMPORTABLE PACKAGE. A revision file
    has no `__init__.py` above it and its module name is not a legal dotted path, so
    `importlib.util.spec_from_file_location` is the only way in. Loading it executes
    only module-level code — the constants — never `upgrade()`.
    """
    import importlib.util

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vers = os.path.join(here, "alembic", "versions")
    out = {}
    for key, fname in (
        ("r211", "r211_sunnycrest_cemetery_and_equipment.py"),
        ("r212", "r212_sunnycrest_price_list_alignment.py"),
    ):
        path = os.path.join(vers, fname)
        spec = importlib.util.spec_from_file_location(f"_seedref_{key}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out[key] = mod

    r211, r212 = out["r211"], out["r212"]
    equipment = [(n, str(p)) for _sku, n, p in r211.EQUIPMENT]
    equipment += [(n, str(p)) for _sku, n, p in r212.EQUIPMENT]
    # ⚠️ THE `after` COLUMN, NOT `before`. r212 exists to move these prices; seeding the
    # pre-reprice figure would plant the exact row r212 was written to correct.
    vaults = [(n, str(after)) for n, _before, after in r212.REPRICE]
    return equipment, vaults, r211.CEMETERY_NAME, r211.CEMETERY_CITY


#: ⚠️ THE ONE PRODUCT NO MIGRATION OWNS. `Urn Vault - Standard` is on production and in
#: James's description of the demo catalogue ("Monticello, Continental and the urn
#: vault"), but r211/r212 do not carry it and no runnable seed creates it, so its price
#: is this file's own — a plausible demo figure, not production's.
URN_VAULT = ("Urn Vault - Standard", "395.00")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    db = SessionLocal()
    try:
        tid = db.execute(
            text("SELECT id FROM companies WHERE slug = :s"), {"s": SLUG}
        ).scalar()
        if not tid:
            # ⚠️ NOT AN ERROR. On a database where sunnycrest has not been created this
            # seed has nothing to do, and the runner must not fail for that.
            log.info("no %s tenant on this database — nothing to do", SLUG)
            return 0

        created = updated = 0

        # ── the funeral home, as an entity and as a customer ───────────────
        ent = db.execute(
            text("SELECT id FROM company_entities "
                 "WHERE company_id = :t AND lower(btrim(name)) = lower(:n)"),
            {"t": tid, "n": FUNERAL_HOME},
        ).scalar()
        if not ent:
            db.execute(
                text("INSERT INTO company_entities (id, company_id, name, city, "
                     "created_at, updated_at) "
                     "VALUES (:i, :t, :n, :c, now(), now())"),
                {"i": str(uuid.uuid4()), "t": tid, "n": FUNERAL_HOME, "c": "Auburn"},
            )
            created += 1

        cust = db.execute(
            text("SELECT id FROM customers "
                 "WHERE company_id = :t AND lower(btrim(name)) = lower(:n)"),
            {"t": tid, "n": FUNERAL_HOME},
        ).first()
        if cust is None:
            db.execute(
                text("INSERT INTO customers (id, company_id, name, account_number, "
                     "is_active, created_at) "
                     "VALUES (:i, :t, :n, :a, true, now())"),
                {"i": str(uuid.uuid4()), "t": tid, "n": FUNERAL_HOME,
                 "a": "DEMO-HOPKINS"},
            )
            created += 1
        else:
            # ⚠️ `is_active = true` IS PART OF THE LOOKUP, so a deactivated row would
            # read as absent and the blocker would return with the record present.
            db.execute(
                text("UPDATE customers SET is_active = true WHERE id = :i "
                     "AND is_active IS NOT true"),
                {"i": cust.id},
            )

        # ── the cemetery, named by r211 ────────────────────────────────────
        _eq, _v, name, city = _migration_constants()
        cem = db.execute(
            text("SELECT id FROM cemeteries "
                 "WHERE company_id = :t AND lower(btrim(name)) = lower(:n)"),
            {"t": tid, "n": name},
        ).scalar()
        if not cem:
            db.execute(
                text("INSERT INTO cemeteries (id, company_id, name, city, is_active, "
                     "created_at) VALUES (:i, :t, :n, :c, true, now())"),
                {"i": str(uuid.uuid4()), "t": tid, "n": name, "c": city},
            )
            created += 1

        # ── the catalogue ──────────────────────────────────────────────────
        equipment, vaults, _cn, _cc = _migration_constants()
        for pname, price in [*vaults, URN_VAULT, *equipment]:
            row = db.execute(
                text("SELECT id, price, is_active FROM products "
                     "WHERE company_id = :t AND lower(btrim(name)) = lower(:n)"),
                {"t": tid, "n": pname},
            ).first()
            if row is None:
                db.execute(
                    text("INSERT INTO products (id, company_id, name, price, "
                         "is_active, created_at) "
                         "VALUES (:i, :t, :n, :p, true, now())"),
                    {"i": str(uuid.uuid4()), "t": tid, "n": pname, "p": price},
                )
                created += 1
            elif row.price is None or not row.is_active:
                # ⚠️ A PRICELESS ROW IS AS BLOCKING AS A MISSING ONE — `assess` says
                # "has no price" for exactly that case — so a half-made row is repaired
                # rather than left.
                db.execute(
                    text("UPDATE products SET price = COALESCE(price, :p), "
                         "is_active = true WHERE id = :i"),
                    {"i": row.id, "p": price},
                )
                updated += 1

        db.commit()
        log.info("%s demo catalogue: %d created, %d updated", SLUG, created, updated)
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
