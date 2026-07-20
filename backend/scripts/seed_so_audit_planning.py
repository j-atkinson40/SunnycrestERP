"""Seed the Sales & Orders audit #2 D-list into the operator's Planning
section (S&O Session One rider).

The 14 items land verbatim-from-the-ledger as owner-scoped planned
features under (vertical_default, manufacturing) — the operator's board,
his ordering. PRESERVE-AWARE: an existing item with the same owner +
title is left exactly as he has it (status, edits, all of it).

Owner resolution: the platform user who already owns Planning items on
this database (dev: dev-admin@bridgeable.internal); overridable via
--owner-email.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.services.maps_of_content import planning  # noqa: E402

# Verbatim-from-the-ledger (docs/investigations/mfg_area_audit_02_sales_orders.md,
# "The decision list"). Session One already closed D-1/3-partial/4/8/10 —
# they land as items anyway so the board tells the whole story; the
# operator marks done what he verifies done.
D_ITEMS: list[tuple[str, str]] = [
    ("S&O D-1 — Delivery double-count",
     "quote_service.py:320: stop re-adding delivery_charge; decide tax-base "
     "policy (delivery taxed or not) explicitly; pin with the hand-worked "
     "example; check historical quotes/orders for the overcharge (a data "
     "census rides the fix). [Session One: fixed + pinned; census = 0 rows]"),
    ("S&O D-2 — Double AR-post",
     "Pick ONE posting moment (approval, per the docstring's own claim), "
     "delete the other; fix the sweeper's alert copy to name what it finds; "
     "pin the single-post."),
    ("S&O D-3 — completed into the batch filter",
     "Add `completed` to the batch filter + decide the backfill for the 3 "
     "stranded orders; surface (not swallow) per-order invoice failures "
     "(draft_invoice_service.py:307,416)."),
    ("S&O D-4 — Order-Station convert swallow",
     "Raise + honest response — no 201-with-no-order. "
     "[Session One: fixed — 502 with the quote number named]"),
    ("S&O D-5 — Manual invoice guards",
     "Already-invoiced check + refuse `draft`."),
    ("S&O D-6 — Status vocabulary heal",
     "Retire dead processing/shipped from filters (or implement them "
     "deliberately); document/route spring_burial; unify declined→rejected; "
     "fix the `cancelled` spelling; THEN ship cancellation (List 3.1) as "
     "the missing verb."),
    ("S&O D-7 — Confirm-on-INSERT hook bypass",
     "Route all confirms through one transition fn so on_order_confirmed "
     "fires (Beats 4/8)."),
    ("S&O D-8 — Numbering",
     "Unique constraint per tenant + retry-on-conflict; kill count(*)+1; "
     "decide the SO-LEGACY convention. [Session One: advisory-lock "
     "allocator + r138 unique indexes; LEGACY ignored by convention]"),
    ("S&O D-9 — Zero-money creation paths",
     "Beat 7 (customer-required crash + no lines), Beat 8 (quantize + tax), "
     "Beat 9 (numbering + money) — each small, batchable."),
    ("S&O D-10 — d3-* test-residue purge",
     "16 dead companies riding every fan-out — the opener's finding. "
     "[Session One: purged — d3-* remaining 0; 36 Bare/SCHED catalog rows "
     "deactivated]"),
    ("S&O D-11 — THE QUOTE UNIFICATION",
     "The structural root: one money path, one tax path, one converter, one "
     "number lineage, conditional pricing applied at QUOTE time — absorbs "
     "the leftovers of D-1/1.5/1.6/List-4.1/4.5/4.6. ARC (2–3 sessions)."),
    ("S&O D-12 — Serializer honesty",
     "List 3.7/3.8 — surface what's written."),
    ("S&O D-13 — NL sales-order",
     "Wire it or retire the declaration (honest never-face until then)."),
    ("S&O D-14 — Seed truthfulness",
     "Quote→order lineage + product_line + lined orders in seeds."),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner-email", default=None)
    args = ap.parse_args()

    db = SessionLocal()
    try:
        from sqlalchemy import text
        if args.owner_email:
            row = db.execute(
                text("SELECT id FROM platform_users WHERE email = :e"),
                {"e": args.owner_email},
            ).fetchone()
        else:
            # The user who already owns Planning items here IS the operator.
            row = db.execute(text(
                "SELECT owner_user_id FROM moc_planning_item "
                "GROUP BY owner_user_id ORDER BY count(*) DESC LIMIT 1"
            )).fetchone()
        if not row:
            print("No Planning owner found — pass --owner-email. Nothing seeded.")
            return
        owner_id = row[0]

        existing = {
            r[0]
            for r in db.execute(text(
                "SELECT title FROM moc_planning_item WHERE owner_user_id = :o"
            ), {"o": owner_id}).fetchall()
        }
        created = skipped = 0
        for order, (title, description) in enumerate(D_ITEMS):
            if title in existing:
                skipped += 1  # PRESERVED — his edits stand
                continue
            planning.create_item(
                db,
                owner_user_id=owner_id,
                scope="vertical_default",
                vertical="manufacturing",
                kind="feature",
                title=title,
                description=description,
                status="planned",
                display_order=order,
            )
            created += 1
        db.commit()
        print(f"Planning D-list: {created} created, {skipped} preserved "
              f"(owner {owner_id}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
