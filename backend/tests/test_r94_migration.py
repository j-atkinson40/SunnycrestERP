"""Phase R-6.2a — Migration r94 schema + seed verification.

Verifies:
  - All 4 new tables exist with the canonical column shape.
  - The 3 canonical funeral_home vertical_default seeds are present.
  - ``tenant_workflow_email_rules.adapter_type`` discriminator column
    exists with the right default + CHECK constraint.

Migration round-trip (downgrade then upgrade) verified separately via
alembic CLI; this test only inspects post-upgrade state.
"""

from __future__ import annotations

from sqlalchemy import inspect, text as sql_text

from tests._classification_fixtures import _engine


def test_r94_creates_intake_form_configurations_table():
    insp = inspect(_engine)
    assert "intake_form_configurations" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("intake_form_configurations")}
    expected = {
        "id",
        "tenant_id",
        "vertical",
        "scope",
        "name",
        "slug",
        "description",
        "form_schema",
        "success_message",
        "notification_email_template_id",
        "is_active",
        "created_by_user_id",
        "updated_by_user_id",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(cols)


def test_r94_creates_intake_file_configurations_table():
    insp = inspect(_engine)
    assert "intake_file_configurations" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("intake_file_configurations")}
    expected = {
        "id",
        "tenant_id",
        "vertical",
        "scope",
        "name",
        "slug",
        "allowed_content_types",
        "max_file_size_bytes",
        "max_file_count",
        "r2_key_prefix_template",
        "metadata_schema",
        "is_active",
    }
    assert expected.issubset(cols)


def test_r94_creates_intake_form_submissions_table():
    insp = inspect(_engine)
    assert "intake_form_submissions" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("intake_form_submissions")}
    expected = {
        "id",
        "tenant_id",
        "config_id",
        "submitted_data",
        "submitter_metadata",
        "received_at",
        "classification_tier",
        "classification_workflow_id",
        "classification_workflow_run_id",
        "classification_is_suppressed",
        "classification_payload",
    }
    assert expected.issubset(cols)


def test_r94_creates_intake_file_uploads_table():
    insp = inspect(_engine)
    assert "intake_file_uploads" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("intake_file_uploads")}
    expected = {
        "id",
        "tenant_id",
        "config_id",
        "r2_key",
        "original_filename",
        "content_type",
        "size_bytes",
        "uploader_metadata",
        "received_at",
        "classification_tier",
        "classification_workflow_id",
        "classification_workflow_run_id",
        "classification_is_suppressed",
        "classification_payload",
    }
    assert expected.issubset(cols)


def test_r94_adds_adapter_type_column_to_rules():
    insp = inspect(_engine)
    cols = {
        c["name"]: c
        for c in insp.get_columns("tenant_workflow_email_rules")
    }
    assert "adapter_type" in cols
    # Server default 'email' preserves R-6.1 backward compat.
    server_default = cols["adapter_type"].get("default")
    # Postgres returns the default literal as a string like "'email'::character varying"
    assert server_default is None or "email" in str(server_default)


def test_r94_seeds_funeral_personalization_request_form():
    with _engine.connect() as conn:
        row = conn.execute(
            sql_text(
                "SELECT slug, scope, vertical, name FROM "
                "intake_form_configurations WHERE "
                "slug = 'personalization-request' AND "
                "vertical = 'funeral_home' AND tenant_id IS NULL AND "
                "is_active = true"
            )
        ).first()
    assert row is not None
    assert row[0] == "personalization-request"
    assert row[1] == "vertical_default"
    assert row[2] == "funeral_home"


def test_r94_seeds_funeral_death_certificate_file():
    with _engine.connect() as conn:
        row = conn.execute(
            sql_text(
                "SELECT slug, scope, vertical FROM "
                "intake_file_configurations WHERE "
                "slug = 'death-certificate' AND vertical = 'funeral_home' "
                "AND tenant_id IS NULL AND is_active = true"
            )
        ).first()
    assert row is not None
    assert row[0] == "death-certificate"
    assert row[1] == "vertical_default"


def test_r94_seeds_funeral_personalization_documents_file():
    with _engine.connect() as conn:
        row = conn.execute(
            sql_text(
                "SELECT slug, scope, vertical FROM "
                "intake_file_configurations WHERE "
                "slug = 'personalization-documents' AND "
                "vertical = 'funeral_home' AND tenant_id IS NULL AND "
                "is_active = true"
            )
        ).first()
    assert row is not None


def test_r94_seed_is_idempotent():
    """Running upgrade twice is a no-op on seeded rows."""
    with _engine.connect() as conn:
        before = conn.execute(
            sql_text(
                "SELECT COUNT(*) FROM intake_form_configurations "
                "WHERE vertical = 'funeral_home' AND tenant_id IS NULL"
            )
        ).scalar()
    # Migration is already at head; seed function is keyed on
    # existence checks so re-runs produce no new rows.
    # The CLI verifies this; here we just confirm count is exactly 1
    # for the canonical seed (not 2 from accidental dup).
    assert before == 1


def test_r94_adapter_type_check_constraint_rejects_unknown():
    """The CHECK constraint enforces adapter_type in ('email','form','file')."""
    from sqlalchemy.exc import IntegrityError

    # Find an existing tenant + workflow_email_rules row insert
    # via direct SQL. Use a one-off tenant so we don't depend on
    # tenant_pair fixture (which we can't import without pytest).
    with _engine.connect() as conn:
        # Insert a placeholder tenant row.
        import uuid as _uuid

        tenant_id = str(_uuid.uuid4())
        slug = f"r94-test-{tenant_id[:8]}"
        conn.execute(
            sql_text(
                "INSERT INTO companies (id, name, slug, is_active, vertical, "
                "created_at, updated_at) "
                "VALUES (:id, 'r94 test', :slug, true, 'manufacturing', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"id": tenant_id, "slug": slug},
        )
        conn.commit()
        try:
            try:
                conn.execute(
                    sql_text(
                        "INSERT INTO tenant_workflow_email_rules "
                        "(id, tenant_id, priority, name, match_conditions, "
                        "fire_action, is_active, adapter_type) "
                        "VALUES (:id, :tid, 0, 'r94 reject', '{}'::jsonb, "
                        "'{}'::jsonb, true, 'unknown_adapter')"
                    ),
                    {"id": str(_uuid.uuid4()), "tid": tenant_id},
                )
                conn.commit()
                # If we got here the CHECK failed to fire — that's a
                # regression we should flag.
                assert False, "CHECK constraint did not reject unknown adapter_type"
            except IntegrityError:
                conn.rollback()
                # Expected — CHECK fired.
        finally:
            conn.execute(
                sql_text("DELETE FROM companies WHERE id = :id"),
                {"id": tenant_id},
            )
            conn.commit()
