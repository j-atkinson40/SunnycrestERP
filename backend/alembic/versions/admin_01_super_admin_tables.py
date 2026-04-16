"""Super admin portal tables: deployments, audit runs, staging tenants, feature flags, saved prompts, smoke tests."""

from alembic import op
import sqlalchemy as sa

revision = "admin_01_super_admin_tables"
down_revision = "vault_05_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- admin_impersonation_sessions ---
    # Note: platform_users already exists — we extend behavior, not replace
    op.create_table(
        "admin_impersonation_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("admin_user_id", sa.String(36), sa.ForeignKey("platform_users.id"), nullable=False),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("impersonated_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("source_ip", sa.String(50), nullable=True),
        sa.Column("environment", sa.String(20), nullable=False, server_default="production"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )
    op.create_index("ix_admin_impersonation_admin", "admin_impersonation_sessions", ["admin_user_id"])
    op.create_index("ix_admin_impersonation_tenant", "admin_impersonation_sessions", ["tenant_id"])
    op.create_index("ix_admin_impersonation_active", "admin_impersonation_sessions", ["is_active"])

    # --- admin_audit_runs ---
    op.create_table(
        "admin_audit_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("admin_user_id", sa.String(36), sa.ForeignKey("platform_users.id"), nullable=False),
        sa.Column("scope", sa.String(50), nullable=False),           # all | vertical | tenant | feature
        sa.Column("scope_value", sa.String(255), nullable=True),
        sa.Column("environment", sa.String(20), nullable=False),     # staging | production
        sa.Column("total_tests", sa.Integer, nullable=True),
        sa.Column("passed", sa.Integer, nullable=True),
        sa.Column("failed", sa.Integer, nullable=True),
        sa.Column("skipped", sa.Integer, nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("full_output", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),  # running | passed | failed | cancelled
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_admin_audit_runs_admin", "admin_audit_runs", ["admin_user_id"])
    op.create_index("ix_admin_audit_runs_started", "admin_audit_runs", ["started_at"])

    # --- admin_staging_tenants (tracks created staging tenants) ---
    op.create_table(
        "admin_staging_tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("created_by_admin_id", sa.String(36), sa.ForeignKey("platform_users.id"), nullable=False),
        sa.Column("vertical", sa.String(50), nullable=False),
        sa.Column("preset", sa.String(100), nullable=False),
        sa.Column("temp_admin_email", sa.String(255), nullable=False),
        sa.Column("temp_admin_password", sa.String(255), nullable=True),   # cleared after first use
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default="false"),
    )
    op.create_index("ix_admin_staging_tenants_company", "admin_staging_tenants", ["company_id"])

    # --- admin_feature_flags (seeded) ---
    op.create_table(
        "admin_feature_flags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("flag_key", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("default_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("category", sa.String(50), nullable=True),   # vertical | feature | experimental
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "admin_feature_flag_overrides",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("flag_key", sa.String(100), sa.ForeignKey("admin_feature_flags.flag_key"), nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False),
        sa.Column("set_by_admin_id", sa.String(36), sa.ForeignKey("platform_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("uq_admin_flag_company", "admin_feature_flag_overrides", ["flag_key", "company_id"], unique=True)

    # --- admin_saved_prompts (Claude chat saved prompts) ---
    op.create_table(
        "admin_saved_prompts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("admin_user_id", sa.String(36), sa.ForeignKey("platform_users.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("vertical", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_admin_saved_prompts_admin", "admin_saved_prompts", ["admin_user_id"])

    # --- admin_deployments (Part 14) ---
    op.create_table(
        "admin_deployments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("affected_verticals", sa.JSON, nullable=False),
        sa.Column("affected_features", sa.JSON, nullable=True),
        sa.Column("git_commit", sa.String(40), nullable=True),
        sa.Column("deployed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("logged_by_admin_id", sa.String(36), sa.ForeignKey("platform_users.id"), nullable=True),
        sa.Column("is_tested", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("test_run_id", sa.String(36), sa.ForeignKey("admin_audit_runs.id"), nullable=True),
    )
    op.create_index("ix_admin_deployments_untested", "admin_deployments", ["is_tested", "deployed_at"])
    op.create_index("ix_admin_deployments_commit", "admin_deployments", ["git_commit"])

    # --- admin_smoke_test_results (Part 14) ---
    op.create_table(
        "admin_smoke_test_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("deployment_id", sa.String(36), sa.ForeignKey("admin_deployments.id"), nullable=True),
        sa.Column("triggered_by_admin_id", sa.String(36), sa.ForeignKey("platform_users.id"), nullable=True),
        sa.Column("trigger", sa.String(50), nullable=False),   # post_deployment | manual | scheduled
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),  # running | passed | failed | skipped
        sa.Column("checks_total", sa.Integer, nullable=True),
        sa.Column("checks_passed", sa.Integer, nullable=True),
        sa.Column("checks_failed", sa.Integer, nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("failures", sa.JSON, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_smoke_results_company", "admin_smoke_test_results", ["company_id"])
    op.create_index("ix_smoke_results_deployment", "admin_smoke_test_results", ["deployment_id"])

    # --- tenant_product_lines (Part 11 — replacing extensions) ---
    op.create_table(
        "tenant_product_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("line_key", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("config", sa.JSON, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("uq_tenant_product_line", "tenant_product_lines", ["company_id", "line_key"], unique=True)

    # --- Seed core feature flags ---
    connection = op.get_bind()
    import uuid
    seed_flags = [
        ("funeral_home_vertical",    "Enables funeral home vertical features",      False, "vertical"),
        ("cemetery_vertical",        "Enables cemetery vertical features",          False, "vertical"),
        ("crematory_vertical",       "Enables crematory vertical features",         False, "vertical"),
        ("personalization_studio",   "Enhanced personalization features",           False, "feature"),
        ("ai_arrangement_scribe",    "AI arrangement scribe for funeral homes",     False, "experimental"),
        ("cross_tenant_network",     "Cross-tenant network visibility",             False, "feature"),
        ("legacy_vault_print",       "Legacy vault print features",                 False, "feature"),
        ("admin_claude_chat",        "Claude chat in admin command bar",            True,  "feature"),
        ("admin_environment_toggle", "Environment toggle in admin portal",          True,  "feature"),
    ]
    for flag_key, desc, default, category in seed_flags:
        connection.execute(
            sa.text("""
                INSERT INTO admin_feature_flags (id, flag_key, description, default_enabled, category)
                VALUES (:id, :k, :d, :v, :c)
                ON CONFLICT (flag_key) DO NOTHING
            """),
            {"id": str(uuid.uuid4()), "k": flag_key, "d": desc, "v": default, "c": category},
        )

    # --- Seed default product lines for existing companies ---
    # Every company gets "burial_vaults" as a default product line
    companies = connection.execute(sa.text("SELECT id FROM companies WHERE is_active = true")).fetchall()
    for company in companies:
        connection.execute(
            sa.text("""
                INSERT INTO tenant_product_lines (id, company_id, line_key, display_name, is_enabled, sort_order)
                VALUES (:id, :cid, 'burial_vaults', 'Burial Vaults', true, 0)
                ON CONFLICT (company_id, line_key) DO NOTHING
            """),
            {"id": str(uuid.uuid4()), "cid": company.id},
        )


def downgrade() -> None:
    op.drop_index("uq_tenant_product_line", table_name="tenant_product_lines")
    op.drop_table("tenant_product_lines")
    op.drop_index("ix_smoke_results_deployment", table_name="admin_smoke_test_results")
    op.drop_index("ix_smoke_results_company", table_name="admin_smoke_test_results")
    op.drop_table("admin_smoke_test_results")
    op.drop_index("ix_admin_deployments_commit", table_name="admin_deployments")
    op.drop_index("ix_admin_deployments_untested", table_name="admin_deployments")
    op.drop_table("admin_deployments")
    op.drop_index("ix_admin_saved_prompts_admin", table_name="admin_saved_prompts")
    op.drop_table("admin_saved_prompts")
    op.drop_index("uq_admin_flag_company", table_name="admin_feature_flag_overrides")
    op.drop_table("admin_feature_flag_overrides")
    op.drop_table("admin_feature_flags")
    op.drop_index("ix_admin_staging_tenants_company", table_name="admin_staging_tenants")
    op.drop_table("admin_staging_tenants")
    op.drop_index("ix_admin_audit_runs_started", table_name="admin_audit_runs")
    op.drop_index("ix_admin_audit_runs_admin", table_name="admin_audit_runs")
    op.drop_table("admin_audit_runs")
    op.drop_index("ix_admin_impersonation_active", table_name="admin_impersonation_sessions")
    op.drop_index("ix_admin_impersonation_tenant", table_name="admin_impersonation_sessions")
    op.drop_index("ix_admin_impersonation_admin", table_name="admin_impersonation_sessions")
    op.drop_table("admin_impersonation_sessions")
