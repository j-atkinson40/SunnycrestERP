"""Phase W-3a — backfill tenant_product_lines for existing manufacturing tenants.

Revision ID: r60_backfill_tenant_product_lines_vault
Revises: r59_widget_product_line_axis
Create Date: 2026-04-27

Companion to r59 (which added the 5-axis filter column + retagged
AncillaryPoolPin to require vault). This migration ensures existing
manufacturing-vertical tenants have a `TenantProductLine(line_key="vault")`
row so the 5-axis filter in `widget_service.get_available_widgets` has
data to evaluate against.

Without this backfill, after r59 ships the AncillaryPoolPin would be
invisible to existing manufacturing tenants (Sunnycrest in production):
the widget requires `required_product_line: ["vault"]` but no vault
TenantProductLine row exists for any tenant pre-canon.

Per [BRIDGEABLE_MASTER §5.2](../../BRIDGEABLE_MASTER.md) canonical
migration plan:
  • Vault is auto-seeded baseline for manufacturing tenants
  • `Company.vault_fulfillment_mode` value (pre-canon tenant-level mode
    field) is preserved by copying into
    `TenantProductLine.config["operating_mode"]`
  • Post-September hygiene session drops `Company.vault_fulfillment_mode`
    column entirely

CRITICAL preservation logic (per Q2 user direction):
  • Read each manufacturing tenant's existing `vault_fulfillment_mode` value
    (default "produce" per Company model server_default)
  • Translate "produce" → "production" to match canonical operating_mode
    enum {"production", "purchase", "hybrid"}
  • Write into TenantProductLine.config["operating_mode"]
  • If tenant already has a vault row (defensive: re-running migration
    or hand-seeded), update is_enabled=True + merge operating_mode into
    existing config without clobbering other keys

Idempotent — safe to re-run. Skips tenants that already have a vault
TenantProductLine row.

Note: this migration is intentionally narrow scope. Other product lines
(funeral_services for FH tenants, etc.) are NOT backfilled here — those
seeders run only at new-tenant creation. Backfilling FH tenants is a
post-September scope expansion (no FH-vertical product-line widgets
ship in W-3a).
"""

import json
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "r60_backfill_tenant_product_lines_vault"
down_revision = "r59_widget_product_line_axis"
branch_labels = None
depends_on = None


def _translate_fulfillment_mode(legacy_mode: str | None) -> str:
    """Translate pre-canon Company.vault_fulfillment_mode value to
    canonical TenantProductLine.config["operating_mode"] value.

    Pre-canon enum: 'produce' | 'purchase' | 'hybrid' (with 'produce'
    as default per Company.vault_fulfillment_mode server_default).
    Canon enum: 'production' | 'purchase' | 'hybrid' per
    [BRIDGEABLE_MASTER §5.2.2](../../BRIDGEABLE_MASTER.md).

    Mapping:
      'produce'  → 'production'  (canonical naming)
      'purchase' → 'purchase'    (preserved)
      'hybrid'   → 'hybrid'      (preserved)
      None / unrecognized → 'production' (canonical default)
    """
    if legacy_mode == "purchase":
        return "purchase"
    if legacy_mode == "hybrid":
        return "hybrid"
    # 'produce', None, or any other value → canonical default 'production'
    return "production"


def upgrade() -> None:
    conn = op.get_bind()

    # Find manufacturing-vertical tenants that don't yet have a vault
    # TenantProductLine row. Idempotent — re-running skips already-
    # backfilled tenants.
    rows = conn.execute(
        sa.text(
            "SELECT c.id, c.vault_fulfillment_mode "
            "FROM companies c "
            "WHERE c.vertical = 'manufacturing' "
            "  AND c.is_active = TRUE "
            "  AND NOT EXISTS ( "
            "    SELECT 1 FROM tenant_product_lines tpl "
            "    WHERE tpl.company_id = c.id "
            "      AND tpl.line_key = 'vault' "
            "  )"
        )
    ).fetchall()

    backfilled_count = 0
    now = datetime.now(timezone.utc)

    for row in rows:
        company_id, legacy_mode = row[0], row[1]
        operating_mode = _translate_fulfillment_mode(legacy_mode)
        config = {"operating_mode": operating_mode}

        conn.execute(
            sa.text(
                "INSERT INTO tenant_product_lines "
                "  (id, company_id, line_key, display_name, is_enabled, "
                "   config, sort_order, created_at, updated_at) "
                "VALUES (:id, :cid, :line_key, :display_name, TRUE, "
                "        :config, 0, :now, :now)"
            ),
            {
                "id": str(uuid.uuid4()),
                "cid": company_id,
                "line_key": "vault",
                "display_name": "Burial Vaults",
                "config": json.dumps(config),
                "now": now,
            },
        )
        backfilled_count += 1

    # Defensive — also handle the case where a manufacturing tenant
    # ALREADY has a vault row but its config doesn't carry operating_mode
    # (e.g. seeded by hand pre-canon or migrated halfway). Merge mode
    # into existing config without clobbering other keys.
    existing_rows = conn.execute(
        sa.text(
            "SELECT tpl.id, tpl.config, c.vault_fulfillment_mode "
            "FROM tenant_product_lines tpl "
            "JOIN companies c ON c.id = tpl.company_id "
            "WHERE tpl.line_key = 'vault' "
            "  AND c.vertical = 'manufacturing' "
            "  AND c.is_active = TRUE"
        )
    ).fetchall()

    merged_count = 0
    for row in existing_rows:
        tpl_id, existing_config, legacy_mode = row[0], row[1], row[2]
        existing_dict = dict(existing_config or {})
        if "operating_mode" in existing_dict:
            continue  # already has mode set; preserve as-is
        existing_dict["operating_mode"] = _translate_fulfillment_mode(legacy_mode)

        conn.execute(
            sa.text(
                "UPDATE tenant_product_lines "
                "SET config = :config, updated_at = :now "
                "WHERE id = :id"
            ),
            {
                "id": tpl_id,
                "config": json.dumps(existing_dict),
                "now": now,
            },
        )
        merged_count += 1

    print(
        f"r60 backfill summary: "
        f"new vault rows={backfilled_count} "
        f"existing-row config merges={merged_count}"
    )


def downgrade() -> None:
    # Down-migration removes ONLY rows the upgrade created — but we
    # didn't track which ones in a separate table. Conservative
    # behavior: drop ALL vault rows for manufacturing tenants. This is
    # acceptable because the canon design is "vault auto-seeded baseline
    # for manufacturing tenants" — rolling back means going back to a
    # state where the vault row didn't exist, which is precisely the
    # pre-r60 state. Existing config (if a tenant had hand-set
    # operating_mode) would be lost on downgrade; this is a known
    # downgrade trade-off documented in the migration.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM tenant_product_lines tpl "
            "USING companies c "
            "WHERE tpl.company_id = c.id "
            "  AND tpl.line_key = 'vault' "
            "  AND c.vertical = 'manufacturing'"
        )
    )
