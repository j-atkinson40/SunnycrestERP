"""D-11 U-1 — the tax resolution carries its WHY (quotes.tax_reason).

One tax resolution, both faces: derived (jurisdiction engine), exempt
(documented), or explicitly overridden — never a silent default. The
reason renders wherever tax shows. Nullable; historical rows stay NULL
(carry-not-recompute — stored history is never rewritten).

(The investigation's conditional vocabulary migration stays slotted in
U-2 and will take the next number.)
"""

from alembic import op
import sqlalchemy as sa

revision = "r139_quote_tax_reason"
down_revision = "r138_document_number_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quotes",
        sa.Column("tax_reason", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("quotes", "tax_reason")
