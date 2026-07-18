"""The QBO decommission — the plaintext purge (hardening rider, 2026-07-18).

QBO is dead; Bridgeable IS the accounting system. This migration PURGES —
it does not protect:

1. Strips the three PLAINTEXT CREDENTIAL keys from every
   ``companies.accounting_config`` JSON blob: ``qbo_access_token``,
   ``qbo_refresh_token``, ``qbo_client_secret`` (the exact keys the Plaid
   investigation named — written plaintext by the retired
   qbo_oauth_service since its birth). Surgical: non-credential qbo_*
   metadata (realm id, connected_at, environment) is left in place — its
   readers are deleted in the same commit, so it is inert residue, not a
   capability.
2. Flips ``companies.accounting_provider`` from 'quickbooks_online' to
   NULL so no tenant points at the deleted provider (honest "no
   integration" rather than an error into a void).
3. DROPS the AccountingConnection vestige columns
   ``qbo_access_token_encrypted`` / ``qbo_refresh_token_encrypted`` /
   ``sage_api_key_encrypted`` — never written (except to None), never
   read; dead schema that lied about an encryption capability.

THE ONE-WAY HEAL: the purged plaintext is DELIBERATELY unrecoverable —
that is the point. The downgrade restores the columns (empty, as they
always were) but cannot and must not resurrect credentials. The
operator's parallel step (Intuit-side deauthorization/rotation) kills
the copies this migration cannot reach: older backups + any production
row until this deploys there.

A census line prints per-step (rows touched) — the receipt.

Revision ID: r134_qbo_credential_purge
Revises: r133_plaid_foundation
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa

revision = "r134_qbo_credential_purge"
down_revision = "r133_plaid_foundation"
branch_labels = None
depends_on = None

_CREDENTIAL_KEYS = ("qbo_access_token", "qbo_refresh_token", "qbo_client_secret")


def upgrade() -> None:
    conn = op.get_bind()

    # 1) Strip the credential trio from accounting_config (TEXT holding
    #    JSON — parse via jsonb, delete keys, write back; only rows that
    #    actually carry one of the keys are touched). Idempotent.
    result = conn.execute(sa.text(
        """
        UPDATE companies
        SET accounting_config = (
            accounting_config::jsonb - 'qbo_access_token'
                - 'qbo_refresh_token' - 'qbo_client_secret'
        )::text
        WHERE accounting_config IS NOT NULL
          AND accounting_config != ''
          AND (
            accounting_config::jsonb ? 'qbo_access_token'
            OR accounting_config::jsonb ? 'qbo_refresh_token'
            OR accounting_config::jsonb ? 'qbo_client_secret'
          )
        """
    ))
    print(f"[r134 census] accounting_config credential purge: {result.rowcount} row(s)")

    # 2) No tenant points at the deleted provider.
    result = conn.execute(sa.text(
        "UPDATE companies SET accounting_provider = NULL "
        "WHERE accounting_provider = 'quickbooks_online'"
    ))
    print(f"[r134 census] accounting_provider reset: {result.rowcount} row(s)")

    # 3) The vestige columns settle.
    op.drop_column("accounting_connections", "qbo_access_token_encrypted")
    op.drop_column("accounting_connections", "qbo_refresh_token_encrypted")
    op.drop_column("accounting_connections", "sage_api_key_encrypted")
    print("[r134 census] vestige columns dropped: 3")


def downgrade() -> None:
    # Columns return (empty — as they always were). The purged plaintext
    # does NOT return; the one-way heal is deliberate.
    op.add_column(
        "accounting_connections",
        sa.Column("qbo_access_token_encrypted", sa.Text, nullable=True),
    )
    op.add_column(
        "accounting_connections",
        sa.Column("qbo_refresh_token_encrypted", sa.Text, nullable=True),
    )
    op.add_column(
        "accounting_connections",
        sa.Column("sage_api_key_encrypted", sa.Text, nullable=True),
    )
