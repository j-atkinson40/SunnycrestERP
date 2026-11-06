"""Phase B: write each system role's planned area limit onto existing tenants.

James's rulings of 2026-11-06. `seed_default_roles` covers roles created from
now on; this covers the role rows that already exist.

⚠️ **A SEED, NOT AN ALEMBIC MIGRATION, AND THE REASON IS A LIVE HAZARD RATHER
THAN A PREFERENCE.** The capture session's `r228_capture_prefix_offers` chains
off `r227` and sits unmerged on `capture-slice2-gate`. A migration of mine
chaining off the same `r227` would make a SECOND HEAD the moment theirs lands,
and `railway-prep.sh:84` aborts the deploy on `alembic upgrade head` failure —
its own comment at line 74 records that exact outcome happening before, where
two heads let a deploy continue with stale schema until Playwright found it.
The change is idempotent data rather than schema, so a seed is also the
honest shape for it.

⚠️ **ONLY WHERE THE COLUMN IS NULL. NEVER OVERWRITE A VALUE SOMEBODY SET.**
That is what makes this safe to re-run on every deploy, and it is also the
rule that keeps an admin's per-tenant widening (Phase B step 5) from being
reverted by the next boot. A role an admin has narrowed or widened is a
decision; this seed does not have an opinion about it.

⚠️ **NO ENVIRONMENT GUARD, DELIBERATELY, AND THAT IS UNUSUAL FOR A SEED HERE.**
The demo seeds refuse to run on production because they write fake data. This
writes the authorization lists James approved, and production is precisely
where they are needed — Sunnycrest is live. The protection is the NULL check,
not an environment check.
"""
from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text  # noqa: E402

from app.core.areas import PLANNED_ROLE_AREAS  # noqa: E402
from app.database import SessionLocal  # noqa: E402

log = logging.getLogger("seed_role_area_limits")

#: ⚠️ `payroll` is in PLANNED_ROLE_AREAS and is ALREADY limited everywhere, so
#: the NULL check makes it a no-op. Left in rather than excluded, because an
#: exclusion list is a second place to forget something.
#: `admin` is absent from PLANNED_ROLE_AREAS, which is the recorded decision
#: that an admin stays unrestricted.


def main() -> int:
    db = SessionLocal()
    written = skipped_set = 0
    try:
        for slug, grants in sorted(PLANNED_ROLE_AREAS.items()):
            import json

            payload = json.dumps(list(grants))
            res = db.execute(text("""
                UPDATE roles
                   SET limited_to_areas = CAST(:areas AS jsonb),
                       updated_at = now()
                 WHERE slug = :slug
                   AND is_system IS TRUE
                   AND limited_to_areas IS NULL
            """), {"areas": payload, "slug": slug})
            already = db.execute(text("""
                SELECT count(*) FROM roles
                 WHERE slug = :slug AND is_system IS TRUE
                   AND limited_to_areas IS NOT NULL
            """), {"slug": slug}).scalar()
            db.commit()
            written += res.rowcount or 0
            skipped_set += (already or 0) - (res.rowcount or 0)
            print(f"  {slug:<14}wrote={res.rowcount or 0:<3} "
                  f"already-set-and-left-alone={(already or 0) - (res.rowcount or 0)}")

        # ⚠️ POSITIVE CONTROL. A run that wrote nothing AND found nothing set
        # would mean the roles are missing or the slugs do not match — which
        # reads identically to "already done". Refuse to report success on it.
        total_rows = db.execute(text("""
            SELECT count(*) FROM roles
             WHERE is_system IS TRUE AND slug = ANY(:slugs)
        """), {"slugs": list(PLANNED_ROLE_AREAS)}).scalar() or 0
        if total_rows == 0:
            print("  ✗ no matching system roles found at all — slugs or seed order wrong")
            return 1

        print(f"  rows written: {written}; rows already set and left alone: {skipped_set}; "
              f"matching role rows: {total_rows}")

        # ⚠️ And admin must still be unrestricted afterwards.
        admin_limited = db.execute(text("""
            SELECT count(*) FROM roles
             WHERE slug = 'admin' AND limited_to_areas IS NOT NULL
        """)).scalar()
        if admin_limited:
            print(f"  ✗ {admin_limited} admin role(s) are limited — admin must stay NULL")
            return 1
        print("  admin rows limited: 0 (correct — an unrestricted admin is the decision)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
