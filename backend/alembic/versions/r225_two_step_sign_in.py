"""Two-step sign-in for tenant users: TOTP enrolment and recovery codes.

Payroll 2. James's ruling of 2026-11-03: any user whose permissions include a
payroll key must use two-step sign-in, enforced on every token path.

### Why two tables and not columns on `users`

Recovery codes are one-to-many and each is consumed independently, so they need a
row each. Keeping the TOTP secret beside them rather than on `users` means the
whole of a user's second factor is one cascade away from deletion and nothing
about two-step widens the `users` row for the 13 users who will never enrol.

### `user_two_step`

    user_id                 UNIQUE — one second factor per user.
    totp_secret_encrypted   Fernet, reversible: TOTP cannot verify against a
                            hash, so this is encryption and not hashing, and it
                            is the one secret here that must be recoverable.
    enrolled_at             ⚠️ NULL means "a secret was issued and the user has
                            not yet proved they can read it". That is a real
                            state, not a missing value: `begin` creates the row,
                            `verify` stamps this column, and only a stamped row
                            satisfies the requirement. A user who abandons
                            enrolment mid-way holds a row that grants nothing.

### `user_recovery_codes`

    code_hash               bcrypt, per the ruling. These are compared, never
                            displayed again, so hashing is correct where the
                            TOTP secret needed encryption.
    used_at                 NULL = unused. Single-use is enforced by stamping
                            this rather than by deleting the row, so "she used
                            her last code on the 4th" stays answerable.

### `admin_impersonation_sessions.mfa_satisfied_by_admin`

Impersonation mints a tenant token directly (`impersonation_service.py:65`) and,
per the ruling, that token is marked MFA-satisfied so support can still reach a
payroll user. ⚠️ **That is a deliberate bypass, so it is RECORDED rather than
implied** — this column is how a reader later learns that a payroll-reaching
token existed without anybody passing a second step. Nullable, because every row
that predates this migration was created before the bypass existed and nobody
measured it for them.

### On DELETE

Both new FKs to `users.id` are ON DELETE CASCADE: a deleted user's second factor
and recovery codes have no meaning on their own, and leaving them would block the
delete the way `audit_logs.user_id` does. That is the opposite choice from
`payroll_weeks.approved_by`, and deliberately so — an approval is a record ABOUT
a user, while a TOTP secret is a property OF one.
"""
from alembic import op
import sqlalchemy as sa

revision = "r225_two_step_sign_in"
down_revision = "r224_normalize_limited_to_areas_null"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_two_step",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("totp_secret_encrypted", sa.Text(), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=True,
                  comment="NULL = secret issued, enrolment not yet proved. Only a "
                          "stamped row satisfies the two-step requirement."),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_user_two_step_user"),
    )
    op.create_index("ix_user_two_step_user_id", "user_two_step", ["user_id"])

    op.create_table(
        "user_recovery_codes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True,
                  comment="NULL = unused. Stamped rather than deleted so the "
                          "history of which codes were spent stays answerable."),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_user_recovery_codes_user_id", "user_recovery_codes", ["user_id"])
    op.create_index("ix_user_recovery_codes_user_unused", "user_recovery_codes",
                    ["user_id"], postgresql_where=sa.text("used_at IS NULL"))

    op.add_column(
        "admin_impersonation_sessions",
        sa.Column(
            "mfa_satisfied_by_admin", sa.Boolean(), nullable=True,
            comment="TRUE when this session's tenant token was marked "
                    "MFA-satisfied without a second step being passed — the "
                    "deliberate support bypass, recorded so it is auditable. "
                    "NULL on rows predating r225.",
        ),
    )


def downgrade() -> None:
    op.drop_column("admin_impersonation_sessions", "mfa_satisfied_by_admin")
    op.drop_index("ix_user_recovery_codes_user_unused", table_name="user_recovery_codes")
    op.drop_index("ix_user_recovery_codes_user_id", table_name="user_recovery_codes")
    op.drop_table("user_recovery_codes")
    op.drop_index("ix_user_two_step_user_id", table_name="user_two_step")
    op.drop_table("user_two_step")
