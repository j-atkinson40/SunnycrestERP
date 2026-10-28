"""Set James's pill-pick modifier to Control — his ruling of 2026-10-28.

> Set James's to Control.

⚠️ DRY RUN BY DEFAULT. `--apply` writes. Rollback SQL is emitted either way.

⚠️ IT WRITES ONE KEY INTO A SHARED BLOB. `User.preferences` also holds spaces,
briefing preferences, onboarding touches and edge-panel overrides, so this merges
rather than replaces — the same reason the endpoint does.
"""
from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import text

from app.database import SessionLocal
from app.services.capture import pick_modifier as pm

EMAIL = "jim.atkinson@sunnycrest.com"
WANTED = pm.MODIFIER_CONTROL


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    db = SessionLocal()

    row = db.execute(text("""
        SELECT u.id, u.email, u.preferences, c.slug
        FROM users u JOIN companies c ON c.id = u.company_id
        WHERE u.email = :e
    """), {"e": EMAIL}).mappings().one_or_none()
    if row is None:
        print(f"no user {EMAIL!r}", file=sys.stderr)
        return 1

    # ⚠️ THE TENANT IS VERIFIED, NOT ASSUMED. An email is unique platform-wide today;
    # asserting the tenant means a future duplicate cannot send this to the wrong one.
    if row["slug"] != "sunnycrest":
        print(f"REFUSE: {EMAIL} belongs to tenant {row['slug']!r}, not sunnycrest",
              file=sys.stderr)
        return 1

    prefs = dict(row["preferences"] or {})
    prior = prefs.get(pm.PREFERENCE_KEY)
    print(f"=== {'APPLY' if args.apply else 'DRY RUN'} ===")
    print(f"  user  {row['email']} ({row['id']}) on {row['slug']}")
    print(f"  prior {pm.PREFERENCE_KEY} = {prior!r}  (reads as {pm.modifier_of(prefs)!r})")
    print(f"  new   {pm.PREFERENCE_KEY} = {WANTED!r}  (glyph {pm.GLYPHS[WANTED]})")
    print(f"  other preference keys preserved: {sorted(k for k in prefs if k != pm.PREFERENCE_KEY)}")

    if prior == WANTED:
        print("\n  NO-OP: already set")
        db.close()
        return 0

    print("\nROLLBACK SQL:")
    if prior is None:
        print(f"UPDATE users SET preferences = preferences - '{pm.PREFERENCE_KEY}' "
              f"WHERE id = '{row['id']}';")
    else:
        print(f"UPDATE users SET preferences = jsonb_set(preferences, "
              f"'{{{pm.PREFERENCE_KEY}}}', '{json.dumps(prior)}'::jsonb) "
              f"WHERE id = '{row['id']}';")

    if args.apply:
        prefs[pm.PREFERENCE_KEY] = WANTED
        db.execute(
            text("UPDATE users SET preferences = CAST(:p AS jsonb), updated_at = now() "
                 "WHERE id = :i"),
            {"p": json.dumps(prefs), "i": row["id"]},
        )
        db.commit()
        print("\nCOMMITTED")
    else:
        db.rollback()
        print("\nDRY RUN — nothing written. Re-run with --apply.")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
