"""Multi-location support: locations, user_location_access, location_id on key tables."""

import uuid
from alembic import op
import sqlalchemy as sa

revision = "vault_04_multi_location"
down_revision = "vault_03_core_ui"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- locations table ---
    op.create_table(
        "locations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("location_type", sa.String(50), nullable=False, server_default="plant"),
        sa.Column("wilbert_territory_id", sa.String(100), nullable=True),
        sa.Column("address_line1", sa.String(255), nullable=True),
        sa.Column("address_line2", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(50), nullable=True),
        sa.Column("zip_code", sa.String(20), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_locations_company_id", "locations", ["company_id"])
    op.create_index("ix_locations_company_active", "locations", ["company_id", "is_active"])

    # --- user_location_access table ---
    op.create_table(
        "user_location_access",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_id", sa.String(36), sa.ForeignKey("locations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("access_level", sa.String(50), nullable=False, server_default="operator"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_user_location_access_user", "user_location_access", ["user_id"])
    op.create_index("ix_user_location_access_company_user", "user_location_access", ["company_id", "user_id"])

    # --- Add location_id FK to existing tables ---
    op.add_column("sales_orders", sa.Column("location_id", sa.String(36), sa.ForeignKey("locations.id"), nullable=True))
    op.create_index("ix_sales_orders_location_id", "sales_orders", ["location_id"])

    op.add_column("deliveries", sa.Column("origin_location_id", sa.String(36), sa.ForeignKey("locations.id"), nullable=True))

    op.add_column("vault_items", sa.Column("location_id", sa.String(36), sa.ForeignKey("locations.id"), nullable=True))
    op.create_index("ix_vault_items_location_id", "vault_items", ["location_id"])

    op.add_column("work_orders", sa.Column("location_id", sa.String(36), sa.ForeignKey("locations.id"), nullable=True))

    op.add_column("equipment", sa.Column("location_id", sa.String(36), sa.ForeignKey("locations.id"), nullable=True))

    op.add_column("employee_profiles", sa.Column("location_id", sa.String(36), sa.ForeignKey("locations.id"), nullable=True))

    op.add_column("production_log_entries", sa.Column("location_id", sa.String(36), sa.ForeignKey("locations.id"), nullable=True))

    # --- Data migration: create primary location for each company ---
    connection = op.get_bind()
    companies = connection.execute(
        sa.text("SELECT id, name FROM companies WHERE is_active = true")
    ).fetchall()

    # Pre-check which tables/columns exist — avoid failed SQL in PostgreSQL transactional DDL
    inspector = sa.inspect(connection)
    existing_tables = set(inspector.get_table_names())
    table_columns = {}
    for tbl in ["sales_orders", "vault_items", "deliveries", "work_orders", "equipment", "employee_profiles", "production_log_entries"]:
        if tbl in existing_tables:
            table_columns[tbl] = {c["name"] for c in inspector.get_columns(tbl)}

    for company in companies:
        location_id = str(uuid.uuid4())

        # Create primary location
        connection.execute(
            sa.text("""
                INSERT INTO locations (id, company_id, name, location_type, is_primary, is_active, display_order)
                VALUES (:id, :company_id, :name, 'primary', true, true, 0)
            """),
            {"id": location_id, "company_id": company.id, "name": company.name},
        )

        # Assign existing records to primary location
        # Check table+column existence first — PostgreSQL transactional DDL means
        # a failed UPDATE aborts the entire transaction (try/except won't help)
        for table, col in [
            ("sales_orders", "location_id"),
            ("vault_items", "location_id"),
            ("deliveries", "origin_location_id"),
            ("work_orders", "location_id"),
            ("equipment", "location_id"),
            ("employee_profiles", "location_id"),
            ("production_log_entries", "location_id"),
        ]:
            if table not in table_columns:
                continue
            if col not in table_columns[table]:
                continue
            connection.execute(
                sa.text(f"UPDATE {table} SET {col} = :loc WHERE company_id = :cid AND {col} IS NULL"),
                {"loc": location_id, "cid": company.id},
            )

        # Grant all existing users all-location access
        users = connection.execute(
            sa.text("SELECT id FROM users WHERE company_id = :cid AND is_active = true"),
            {"cid": company.id},
        ).fetchall()

        for user in users:
            connection.execute(
                sa.text("""
                    INSERT INTO user_location_access (id, user_id, company_id, location_id, access_level)
                    VALUES (:id, :uid, :cid, NULL, 'admin')
                    ON CONFLICT DO NOTHING
                """),
                {"id": str(uuid.uuid4()), "uid": user.id, "cid": company.id},
            )


def downgrade() -> None:
    op.drop_column("production_log_entries", "location_id")
    op.drop_column("employee_profiles", "location_id")
    op.drop_column("equipment", "location_id")
    op.drop_column("work_orders", "location_id")
    op.drop_index("ix_vault_items_location_id")
    op.drop_column("vault_items", "location_id")
    op.drop_column("deliveries", "origin_location_id")
    op.drop_index("ix_sales_orders_location_id")
    op.drop_column("sales_orders", "location_id")
    op.drop_table("user_location_access")
    op.drop_table("locations")
