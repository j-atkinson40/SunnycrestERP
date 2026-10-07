"""`capture_sessions` — an order being typed, between requests.

⚠️ E2 (2026-10-07): A NEW TABLE, NOT SYNTHETIC CALL-LOG ROWS. Reusing
`ringcentral_call_extractions` would mean a fake `ringcentral_call_log` row per typed
order, because that table's `call_log_id` is a NOT NULL FK. The call log records calls
that happened.

⚠️ EVERY COLUMN NULLABLE EXCEPT IDENTITY AND STATUS, AND NO DATA DEFAULTS. `typed_lines`,
`values`, `unrecognized` and `pending_picks` are NULL on a fresh session, which is
honest: nothing has been typed yet. A `server_default '[]'` would say "this session was
typed into and produced nothing", which is a different claim (CLAUDE.md §5 — a migration
must leave "not established" distinguishable from a measured value).

`status` is the one exception and it carries `'capturing'`, which is measured rather than
invented: a session that exists has been started, and `capture_sessions.py` names the
same constant. The CHECK constraint keeps the vocabulary in one place at the database
level, which `service_location` deliberately did NOT do — the difference is that
`service_location`'s vocabulary is compared against by two capture CONDITIONS, so a
database CHECK would be a second home for it. Nothing compares against `status` in a
condition.

⚠️ BOTH FKs CARRY `ON DELETE CASCADE`, AND THE SECOND ONE MUST. CLAUDE.md §5 records
r177: adding a second FK over a parent an existing key already cascades from does not
layer a check on the cascade, it REVOKES it, because `ON DELETE`'s default is NO ACTION.
`company_id` and `user_id` are different parents here, but the rule is why both are
stated rather than one being left to default.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "r203_capture_sessions"
down_revision = "r202_legacy_series_column"
branch_labels = None
depends_on = None

_TABLE = "capture_sessions"
_STATUSES = ("capturing", "review", "abandoned")


def _tables(conn) -> set[str]:
    return {
        r[0] for r in conn.execute(sa.text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ))
    }


def upgrade() -> None:
    conn = op.get_bind()

    # ⚠️ POSITIVE CONTROL BEFORE THE WRITE. An information_schema read returning nothing
    # is indistinguishable from a database with no tables, and the assertions after the
    # create would then be satisfied by a dead instrument.
    before = _tables(conn)
    assert len(before) > 100, f"saw {len(before)} tables; the reader is blind"
    assert "companies" in before and "users" in before, "FK targets are missing"
    assert _TABLE not in before, f"{_TABLE} already exists"

    op.create_table(
        _TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("object_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="capturing"),
        sa.Column("typed_lines", postgresql.JSONB(), nullable=True),
        sa.Column("values", postgresql.JSONB(), nullable=True),
        sa.Column("unrecognized", postgresql.JSONB(), nullable=True),
        sa.Column("pending_picks", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('capturing','review','abandoned')",
            name="ck_capture_sessions_status",
        ),
    )
    op.create_index(
        "ix_capture_sessions_company_user", _TABLE, ["company_id", "user_id"]
    )

    after = _tables(conn)
    assert _TABLE in after, f"{_TABLE} was not created"

    # ⚠️ ASSERTED PER COLUMN, not merely that the table exists. "The table is there" is
    # satisfied by a table whose JSONB columns are NOT NULL with `'[]'` defaults, which
    # is the exact shape this migration must not create.
    cols = {
        r[0]: (r[1], r[2])
        for r in conn.execute(sa.text(
            "SELECT column_name, is_nullable, column_default "
            "FROM information_schema.columns WHERE table_name = :t"
        ), {"t": _TABLE})
    }
    for nullable_col in ("typed_lines", "values", "unrecognized", "pending_picks"):
        is_nullable, default = cols[nullable_col]
        assert is_nullable == "YES", f"{nullable_col} is NOT NULL"
        assert default is None, f"{nullable_col} carries default {default!r}"
    assert cols["status"][0] == "NO", "status must be NOT NULL"

    # ⚠️ THE CASCADES, ASSERTED. r177's defect was an FK silently taking NO ACTION.
    rules = {
        r[0]: r[1]
        for r in conn.execute(sa.text(
            "SELECT c.conname, pg_get_constraintdef(c.oid) FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid "
            "WHERE t.relname = :t AND c.contype = 'f'"
        ), {"t": _TABLE})
    }
    assert len(rules) == 2, rules
    for name, definition in rules.items():
        assert "ON DELETE CASCADE" in definition, f"{name}: {definition}"


def downgrade() -> None:
    conn = op.get_bind()
    if _TABLE in _tables(conn):
        op.drop_index("ix_capture_sessions_company_user", table_name=_TABLE)
        op.drop_table(_TABLE)
    assert _TABLE not in _tables(conn), f"{_TABLE} survived the downgrade"
