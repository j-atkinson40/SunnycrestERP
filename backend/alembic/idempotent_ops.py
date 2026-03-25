"""Idempotent migration operations — safe to run on both fresh and existing databases."""

import sqlalchemy as sa
from alembic import op


def safe_create_table(table_name, *columns, **kwargs):
    """Create a table only if it doesn't already exist."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        op.create_table(table_name, *columns, **kwargs)
        return True
    return False


def safe_add_column(table_name, column):
    """Add a column only if it doesn't already exist."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    existing = {c["name"] for c in inspector.get_columns(table_name)}
    col_name = column.name if hasattr(column, "name") else column.key
    if col_name not in existing:
        op.add_column(table_name, column)
        return True
    return False


def safe_add_columns(table_name, columns):
    """Add multiple columns, skipping any that already exist."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns(table_name)}
    for col_name, col_def in columns:
        if col_name not in existing:
            op.add_column(table_name, col_def)


def safe_create_index(index_name, table_name, columns, **kwargs):
    """Create an index only if it doesn't already exist."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return
    existing_indexes = {idx["name"] for idx in inspector.get_indexes(table_name)}
    if index_name not in existing_indexes:
        op.create_index(index_name, table_name, columns, **kwargs)
