from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ── Idempotent operation wrappers ──
# Make add_column and create_table safe for both fresh and existing databases
import sqlalchemy as _sa
from alembic import op as _op

_original_add_column = _op.add_column
_original_create_table = _op.create_table
_original_create_index = _op.create_index


def _safe_add_column(table_name, column, **kw):
    """add_column that silently skips if column already exists."""
    try:
        bind = _op.get_bind()
        inspector = _sa.inspect(bind)
        if table_name not in inspector.get_table_names():
            return  # table doesn't exist yet, skip
        existing = {c["name"] for c in inspector.get_columns(table_name)}
        col_name = column.name if hasattr(column, "name") else str(column.key)
        if col_name in existing:
            return  # column already exists, skip
    except Exception:
        pass  # on error, try the original
    return _original_add_column(table_name, column, **kw)


def _safe_create_table(table_name, *args, **kw):
    """create_table that silently skips if table already exists."""
    try:
        bind = _op.get_bind()
        inspector = _sa.inspect(bind)
        if table_name in inspector.get_table_names():
            return None  # table already exists, skip
    except Exception:
        pass
    return _original_create_table(table_name, *args, **kw)


def _safe_create_index(index_name, table_name, columns, **kw):
    """create_index that silently skips if index already exists."""
    try:
        bind = _op.get_bind()
        inspector = _sa.inspect(bind)
        if table_name not in inspector.get_table_names():
            return
        existing = {idx["name"] for idx in inspector.get_indexes(table_name)}
        if index_name in existing:
            return
    except Exception:
        pass
    return _original_create_index(index_name, table_name, columns, **kw)


# Apply monkey-patches
_op.add_column = _safe_add_column
_op.create_table = _safe_create_table
_op.create_index = _safe_create_index
# ── End idempotent wrappers ──


# ── R-3.3.1 (May 2026): widen alembic_version.version_num for long revision IDs ──
#
# Alembic 1.14 hardcodes version_num as String(32) at
# alembic/ddl/impl.py:164 in DefaultImpl.version_table_impl. The
# codebase has 10+ revision IDs longer than 32 chars (longest 47:
# r74_personalization_vocabulary_canonicalization). Fresh DBs hit
# the cap on the first long-ID UPDATE alembic_version.
#
# Production / staging / dev are all at varchar(128) — widened at
# some unknown historical moment (manual ALTER suspected; no
# migration in the codebase widens it; no env.py / alembic.ini
# override pre-R-3.3.1). This monkey-patch ensures fresh DBs
# (CI, first-time local setup) match production from the start.
#
# Production safety: this fires only at alembic_version table
# CREATION time. Existing tables at varchar(128) are untouched.
# SQLAlchemy queries don't validate column-type-vs-actual-DB-type
# at runtime — the patched Table representation is used for
# query construction, the DB enforces width on UPDATE.
#
# If alembic ever defaults to varchar(>=128), this patch becomes
# a no-op and can be removed.
from alembic.ddl import impl as _alembic_impl
from sqlalchemy import (
    Column as _Column,
    MetaData as _MetaData,
    PrimaryKeyConstraint as _PrimaryKeyConstraint,
    String as _String,
    Table as _Table,
)


def _wide_version_table_impl(
    self,
    *,
    version_table,
    version_table_schema,
    version_table_pk,
    **kw,
):
    vt = _Table(
        version_table,
        _MetaData(),
        _Column("version_num", _String(128), nullable=False),
        schema=version_table_schema,
    )
    if version_table_pk:
        vt.append_constraint(
            _PrimaryKeyConstraint(
                "version_num", name=f"{version_table}_pkc"
            )
        )
    return vt


_alembic_impl.DefaultImpl.version_table_impl = _wide_version_table_impl
# ── End alembic_version width override ──


from app.config import settings
from app.database import Base
from app.models import AuditLog, Company, EmployeeProfile, Notification, Role, RolePermission, User, UserPermissionOverride  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
