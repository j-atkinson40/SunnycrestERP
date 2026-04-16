"""Core UI tables: user_actions — command bar action history per user."""

from alembic import op
import sqlalchemy as sa

revision = "vault_03_core_ui"
down_revision = "vault_02_data_migration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_actions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id'), nullable=False),
        sa.Column('action_id', sa.String(100)),
        sa.Column('raw_input', sa.Text),
        sa.Column('result_title', sa.String(255)),
        sa.Column('result_type', sa.String(50)),
        sa.Column('action_data', sa.JSON),
        sa.Column('input_method', sa.String(20)),
        sa.Column('executed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('is_active', sa.Boolean, default=True, server_default='true'),
    )
    op.create_index('ix_user_actions_user_recent', 'user_actions', ['user_id', 'executed_at'])
    op.create_index('ix_user_actions_company', 'user_actions', ['company_id'])


def downgrade() -> None:
    op.drop_index('ix_user_actions_company')
    op.drop_index('ix_user_actions_user_recent')
    op.drop_table('user_actions')
