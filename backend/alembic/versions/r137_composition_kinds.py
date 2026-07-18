"""The map completes itself — composition kinds widen.

The moc_composition CHECK grows three kinds: 'platform' (the Platform
area's card ponders), 'tip' (per-area tips on the full stage), 'module'
(the showroom's never-face ponders). The list-not-engine shape carries —
same table, same beats, new rooms.

Revision ID: r137_composition_kinds
Revises: r136_smtp_password_encrypt
Create Date: 2026-07-18
"""

from alembic import op

revision = "r137_composition_kinds"
down_revision = "r136_smtp_password_encrypt"
branch_labels = None
depends_on = None

_OLD = "kind IN ('area', 'onboarding')"
_NEW = "kind IN ('area', 'onboarding', 'platform', 'tip', 'module')"


def upgrade() -> None:
    op.drop_constraint("ck_moc_composition_kind", "moc_composition", type_="check")
    op.create_check_constraint("ck_moc_composition_kind", "moc_composition", _NEW)


def downgrade() -> None:
    op.drop_constraint("ck_moc_composition_kind", "moc_composition", type_="check")
    op.create_check_constraint("ck_moc_composition_kind", "moc_composition", _OLD)
