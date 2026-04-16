"""Reset Sunnycrest onboarding state so James can complete the new onboarding flow.

SAFETY: This only resets the onboarding status and clears partial program
enrollments that may have been created during migration. It does NOT touch
orders, CRM, products, vault items, users, or any real business data.

Usage (from backend/ dir):
    python -m scripts.reset_sunnycrest_onboarding            # dry-run — shows what would change
    python -m scripts.reset_sunnycrest_onboarding --apply    # actually apply changes
    python -m scripts.reset_sunnycrest_onboarding --slug=foo --apply  # different tenant

Refuses to run if the matched company doesn't look like Sunnycrest
and --force is not passed.
"""

import argparse
import sys

from sqlalchemy import text as sql_text

from app.database import SessionLocal


def _find_company(db, slug: str | None):
    if slug:
        rows = db.execute(
            sql_text("SELECT id, slug, name FROM companies WHERE slug = :s"),
            {"s": slug},
        ).fetchall()
    else:
        rows = db.execute(
            sql_text("SELECT id, slug, name FROM companies WHERE slug = 'sunnycrest' OR name ILIKE '%sunnycrest%'")
        ).fetchall()
    return rows


def _summary(db, company_id: str) -> dict:
    def count(q: str, param_name: str = "cid") -> int:
        return db.execute(sql_text(q), {param_name: company_id}).scalar() or 0

    return {
        "orders": count("SELECT COUNT(*) FROM sales_orders WHERE company_id = :cid"),
        "company_entities": count("SELECT COUNT(*) FROM company_entities WHERE company_id = :cid"),
        "products": count("SELECT COUNT(*) FROM products WHERE company_id = :cid"),
        "vault_items": count("SELECT COUNT(*) FROM vault_items WHERE company_id = :cid"),
        "users": count("SELECT COUNT(*) FROM users WHERE company_id = :cid AND is_active = true"),
        "locations": count("SELECT COUNT(*) FROM locations WHERE company_id = :cid"),
        "program_enrollments": count(
            "SELECT COUNT(*) FROM wilbert_program_enrollments WHERE company_id = :cid"
        ),
        "tenant_item_configs": count(
            "SELECT COUNT(*) FROM tenant_item_config WHERE company_id = :cid"
        ),
        # Legacy checklist system (drives the "X of Y complete" progress bar)
        "checklist_items_completed": count(
            "SELECT COUNT(*) FROM onboarding_checklist_items "
            "WHERE tenant_id = :cid AND status = 'completed'"
        ),
        "checklist_items_in_progress": count(
            "SELECT COUNT(*) FROM onboarding_checklist_items "
            "WHERE tenant_id = :cid AND status = 'in_progress'"
        ),
        "checklist_items_total": count(
            "SELECT COUNT(*) FROM onboarding_checklist_items WHERE tenant_id = :cid"
        ),
        "tenant_onboarding_checklist_rows": count(
            "SELECT COUNT(*) FROM tenant_onboarding_checklists WHERE tenant_id = :cid"
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", type=str, default=None, help="Tenant slug (defaults to 'sunnycrest')")
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (default: dry-run)")
    parser.add_argument("--force", action="store_true", help="Skip Sunnycrest-name safety check")
    parser.add_argument(
        "--clear-program-enrollments",
        action="store_true",
        help="Also DELETE wilbert_program_enrollments for this tenant (recreated in new onboarding)",
    )
    parser.add_argument(
        "--reset-legacy-checklist",
        action="store_true",
        default=True,
        help="Reset onboarding_checklist_items to not_started + tenant_onboarding_checklists "
             "progress to 0 (the system driving the 'X of Y complete' UI). Default: True.",
    )
    parser.add_argument(
        "--keep-legacy-checklist",
        action="store_false",
        dest="reset_legacy_checklist",
        help="Skip legacy checklist reset (leaves the 'X of Y complete' progress as-is).",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = _find_company(db, args.slug)
        if not rows:
            print(f"No company found for slug='{args.slug or 'sunnycrest (default)'}'.")
            sys.exit(1)
        if len(rows) > 1 and not args.slug:
            print(f"Multiple companies matched. Pass --slug=<slug> to disambiguate.")
            for r in rows:
                print(f"  slug={r[1]!r:30s} name={r[2]!r}")
            sys.exit(1)

        company_id, slug, name = rows[0]
        print(f"Matched company: name={name!r} slug={slug!r} id={company_id}")

        # Safety check
        if "sunnycrest" not in (slug or "").lower() and "sunnycrest" not in (name or "").lower():
            if not args.force:
                print("SAFETY: matched company does not look like Sunnycrest. Pass --force to override.")
                sys.exit(2)

        print("\n=== Current data summary (PRESERVED — not touched) ===")
        summary = _summary(db, company_id)
        for k, v in summary.items():
            print(f"  {k}: {v}")

        print("\n=== Onboarding state (BEFORE) ===")
        # Cast settings_json to jsonb in case it's stored as TEXT (production)
        state = db.execute(
            sql_text(
                "SELECT onboarding_status, onboarding_completed_at, "
                "(settings_json::jsonb -> 'onboarding_flow') as flow "
                "FROM companies WHERE id = :cid"
            ),
            {"cid": company_id},
        ).fetchone()
        print(f"  onboarding_status     = {state[0]!r}")
        print(f"  onboarding_completed_at = {state[1]}")
        flow_val = state[2]
        if flow_val is None:
            print(f"  settings.onboarding_flow = (not set)")
        else:
            # Truncate for readability
            flow_str = str(flow_val)
            print(f"  settings.onboarding_flow = {flow_str[:200]}{'...' if len(flow_str) > 200 else ''}")

        print("\n=== Planned changes ===")
        print("  1. companies.onboarding_status -> 'pending'")
        print("  2. companies.onboarding_completed_at -> NULL")
        print("  3. companies.onboarding_metadata -> NULL")
        print("  4. companies.settings_json.onboarding_flow -> cleared")
        if args.clear_program_enrollments:
            print(f"  5. DELETE {summary['program_enrollments']} wilbert_program_enrollments rows")
            print(f"     (they will be recreated through the new onboarding)")
        else:
            print("  5. wilbert_program_enrollments: KEPT "
                  "(pass --clear-program-enrollments to delete)")
        if args.reset_legacy_checklist:
            print(f"  6. Legacy checklist reset: "
                  f"{summary['checklist_items_completed']} completed + "
                  f"{summary['checklist_items_in_progress']} in_progress "
                  f"→ all {summary['checklist_items_total']} items to 'not_started'")
            print(f"     {summary['tenant_onboarding_checklist_rows']} tenant_onboarding_checklists "
                  f"row(s) → status='pending', percent=0")
        else:
            print("  6. Legacy checklist: KEPT "
                  "(pass --reset-legacy-checklist to reset, or remove --keep-legacy-checklist)")

        if not args.apply:
            print("\nDRY-RUN: pass --apply to actually execute these changes.")
            return

        # Execute
        print("\n=== Applying ===")
        # Detect the actual column type of settings_json so the UPDATE works
        # whether it's TEXT (some deploys) or JSONB (others).
        col_type = db.execute(
            sql_text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'companies' AND column_name = 'settings_json'"
            )
        ).scalar()
        is_jsonb = (col_type or "").lower() in ("jsonb", "json")

        if is_jsonb:
            db.execute(
                sql_text(
                    "UPDATE companies "
                    "SET onboarding_status = 'pending', "
                    "    onboarding_completed_at = NULL, "
                    "    onboarding_metadata = NULL, "
                    "    settings_json = COALESCE(settings_json, '{}'::jsonb) - 'onboarding_flow' "
                    "WHERE id = :cid"
                ),
                {"cid": company_id},
            )
        else:
            db.execute(
                sql_text(
                    "UPDATE companies "
                    "SET onboarding_status = 'pending', "
                    "    onboarding_completed_at = NULL, "
                    "    onboarding_metadata = NULL, "
                    "    settings_json = ("
                    "      COALESCE(settings_json::jsonb, '{}'::jsonb) - 'onboarding_flow'"
                    "    )::text "
                    "WHERE id = :cid"
                ),
                {"cid": company_id},
            )
        print("  ✓ Reset companies.onboarding_status and cleared settings_json.onboarding_flow")

        if args.clear_program_enrollments:
            result = db.execute(
                sql_text("DELETE FROM wilbert_program_enrollments WHERE company_id = :cid"),
                {"cid": company_id},
            )
            print(f"  ✓ Deleted {result.rowcount} wilbert_program_enrollments rows")

        if args.reset_legacy_checklist:
            # Reset per-item status (this drives the "X of Y complete" UI)
            r1 = db.execute(
                sql_text(
                    "UPDATE onboarding_checklist_items "
                    "SET status = 'not_started', "
                    "    completed_at = NULL, "
                    "    completed_by = NULL "
                    "WHERE tenant_id = :cid "
                    "AND status IN ('completed', 'in_progress', 'skipped')"
                ),
                {"cid": company_id},
            )
            print(f"  ✓ Reset {r1.rowcount} onboarding_checklist_items to 'not_started'")

            # Reset the aggregate row
            r2 = db.execute(
                sql_text(
                    "UPDATE tenant_onboarding_checklists "
                    "SET status = 'pending', "
                    "    overall_percent = 0, "
                    "    must_complete_percent = 0 "
                    "WHERE tenant_id = :cid"
                ),
                {"cid": company_id},
            )
            print(f"  ✓ Reset {r2.rowcount} tenant_onboarding_checklists row(s)")

        db.commit()
        print("\n✓ Done. Sunnycrest onboarding reset to 'pending'.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
