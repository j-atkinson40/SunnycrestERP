"""rename burial_time -> service_time; add eta, service_location, service_location_other

⚠️ A RENAME, NOT A DROP-AND-ADD. `ALTER TABLE ... RENAME COLUMN` preserves whatever
rows hold; dropping and re-adding would discard them silently. Production holds ZERO
rows in this table (pre-flight 2026-10-06, read-only), so nothing is at risk either
way — but the operation should be right for the environments that do have rows.

WHY: an order carries TWO time facts — a SERVICE time and an ETA. This column held the
first under the second's name, and `create_draft_order_from_extraction` wrote
`service_time = extraction.burial_time`, which on 2026-10-05 I read as evidence the two
were the same fact. The prototype shows service at 10:00 and cemetery arrival at 11:30.
The writer was conflating; a defect was read as the specification.

Renamed rather than added alongside so NO THIRD NAME EXISTS for anyone to conflate.

PRE-FLIGHT, production, read-only, 2026-10-06:
    instrument: railway run --environment production -- python <script>, with
                create_engine(connect_args={"options": "-c default_transaction_read_only=on"})
    head                                   r198_vault_resolution
    ringcentral_call_extractions rows      0
    sales_orders rows                      37, of which service_time non-null 0, eta non-null 0
    control                                19 matching columns, 18 prompt-version rows
                                           (both non-zero, so an empty read would have
                                            meant absence rather than blindness)

Revision ID: r199_service_time_and_eta
Revises: r198_vault_resolution
"""
from alembic import op
import sqlalchemy as sa

revision = "r199_service_time_and_eta"
down_revision = "r198_vault_resolution"
branch_labels = None
depends_on = None

_TABLE = "ringcentral_call_extractions"


def _column_names(conn) -> set[str]:
    return {
        r[0]
        for r in conn.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :t"
            ),
            {"t": _TABLE},
        )
    }


def upgrade() -> None:
    conn = op.get_bind()

    # ⚠️ POSITIVE CONTROL BEFORE THE WRITE. A zero-length column list would mean the
    # query cannot see this table, and every assertion below would pass vacuously on
    # an absence that is really blindness.
    before = _column_names(conn)
    assert len(before) > 5, (
        f"only {len(before)} columns visible on {_TABLE} — the catalogue read is "
        f"blind, so nothing below can be trusted"
    )
    assert "burial_time" in before, (
        f"{_TABLE}.burial_time is absent, so this migration's premise does not hold; "
        f"columns: {sorted(before)}"
    )
    assert "service_time" not in before, "service_time already exists — already applied?"

    op.alter_column(_TABLE, "burial_time", new_column_name="service_time")
    op.add_column(_TABLE, sa.Column("eta", sa.Time(), nullable=True))
    # ⚠️ THESE TWO ARE WHY THE OTHER TWO ARE NOT DEAD. `service_location` has been a
    # capture field since 2026-10-05 with no column here, so the call path could never
    # answer it — and BOTH new conditions read it (`service_location_other` on
    # `== "other"`, `eta` on `!= "graveside"`). Without these, both would resolve
    # INDETERMINATE forever and neither feature would exist.
    op.add_column(_TABLE, sa.Column("service_location", sa.String(20), nullable=True))
    op.add_column(_TABLE, sa.Column("service_location_other", sa.String(100), nullable=True))

    # ⚠️ ASSERT WHAT WAS CREATED, not that the calls returned.
    after = _column_names(conn)
    assert "burial_time" not in after, "the rename did not take"
    assert "service_time" in after, "service_time was not created"
    assert "eta" in after, "eta was not created"
    assert "service_location" in after, "service_location was not created"
    assert "service_location_other" in after, "service_location_other was not created"

    # ⚠️ BOTH MUST BE NULLABLE WITH NO DEFAULT. A non-null default would assert a time
    # for every row nobody measured — CLAUDE.md §5, "not established is a value".
    for col in ("service_time", "eta", "service_location", "service_location_other"):
        nullable, default = conn.execute(
            sa.text(
                "SELECT is_nullable, column_default FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": _TABLE, "c": col},
        ).one()
        assert nullable == "YES", f"{col} is NOT NULL"
        assert default is None, f"{col} carries default {default!r}"


def downgrade() -> None:
    conn = op.get_bind()
    cols = _column_names(conn)
    for col in ("eta", "service_location", "service_location_other"):
        if col in cols:
            op.drop_column(_TABLE, col)
    if "service_time" in cols:
        op.alter_column(_TABLE, "service_time", new_column_name="burial_time")
