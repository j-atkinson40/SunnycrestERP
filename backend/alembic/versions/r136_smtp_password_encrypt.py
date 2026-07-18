"""The SMTP hardening — encrypt-in-place; the column's name made true.

`platform_email_settings.smtp_password_encrypted` held LIVE PLAINTEXT
under an _encrypted name (the third sibling of the QBO decommission's
scan: dead columns lied about a capability; this one lied about a value).
Each plaintext value is read and its Fernet ciphertext written back.

IDEMPOTENT: already-ciphertext rows (the gAAAA Fernet prefix) are
recognized and skipped. A census line prints (N encrypted, M already
clean) — the receipt.

FAIL-LOUD PREREQUISITE: if plaintext rows exist and
CREDENTIAL_ENCRYPTION_KEY is absent, this migration RAISES — deploying
it to an environment without the key configured must stop the boot, not
silently strand plaintext (the r-1.6.3 fail-loud canon). Production
needs the key set BEFORE this deploys there.

Reversible IN FORM ONLY: the downgrade is a no-op — the plaintext is
DELIBERATELY unrecoverable from the migration's side (the one-way heal;
ciphertext decrypts at use for as long as the key lives).

Revision ID: r136_smtp_password_encrypt
Revises: r135_recon_bank_txn_link
Create Date: 2026-07-18
"""

import os

from alembic import op
import sqlalchemy as sa

revision = "r136_smtp_password_encrypt"
down_revision = "r135_recon_bank_txn_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id, smtp_password_encrypted FROM platform_email_settings "
        "WHERE smtp_password_encrypted IS NOT NULL "
        "AND smtp_password_encrypted != ''"
    )).fetchall()

    plaintext = [(r[0], r[1]) for r in rows if not r[1].startswith("gAAAA")]
    already = len(rows) - len(plaintext)

    if plaintext:
        key = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
        if not key:
            raise RuntimeError(
                "r136: plaintext SMTP passwords exist but "
                "CREDENTIAL_ENCRYPTION_KEY is not set — set the key before "
                "deploying this migration (fail-loud beats stranded plaintext)."
            )
        from cryptography.fernet import Fernet
        f = Fernet(key.encode())
        for row_id, value in plaintext:
            conn.execute(sa.text(
                "UPDATE platform_email_settings "
                "SET smtp_password_encrypted = :c WHERE id = :i"
            ), {"c": f.encrypt(value.encode("utf-8")).decode("utf-8"),
                "i": row_id})

    print(f"[r136 census] smtp passwords encrypted: {len(plaintext)}, "
          f"already ciphertext: {already}, unset: skipped")


def downgrade() -> None:
    # No-op by design — the one-way heal. The plaintext does not return.
    pass
