"""Migrate existing data into vault_items.

Revision ID: vault_02_data_migration
Revises: vault_01_core_tables
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "vault_02_data_migration"
down_revision = "vault_01_core_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Get all companies
    companies = conn.execute(text("SELECT id FROM companies WHERE is_active = true")).fetchall()

    for (company_id,) in companies:
        # Create company vault if not exists
        existing_vault = conn.execute(
            text("SELECT id FROM vaults WHERE company_id = :cid AND vault_type = 'company' LIMIT 1"),
            {"cid": company_id}
        ).fetchone()

        if existing_vault:
            vault_id = existing_vault[0]
        else:
            import uuid
            vault_id = str(uuid.uuid4())
            conn.execute(
                text("""
                    INSERT INTO vaults (id, company_id, vault_type, name, is_active)
                    VALUES (:id, :cid, 'company', 'Company Vault', true)
                """),
                {"id": vault_id, "cid": company_id}
            )

        # Migrate deliveries
        conn.execute(text("""
            INSERT INTO vault_items (id, vault_id, company_id, item_type, title, description,
                event_start, event_location, event_type, status, source, source_entity_id,
                created_by, created_at, metadata_json)
            SELECT
                gen_random_uuid()::text,
                :vault_id,
                d.company_id,
                'event',
                COALESCE('Delivery #' || LEFT(d.id, 8), 'Delivery'),
                d.special_instructions,
                COALESCE(d.scheduled_at, d.requested_date::timestamp AT TIME ZONE 'UTC'),
                d.delivery_address,
                'delivery',
                CASE WHEN d.status = 'completed' THEN 'completed'
                     WHEN d.status = 'cancelled' THEN 'cancelled'
                     ELSE 'active' END,
                'migrated',
                d.id,
                d.created_by,
                d.created_at,
                jsonb_build_object(
                    'delivery_type', d.delivery_type,
                    'priority', d.priority,
                    'customer_id', d.customer_id,
                    'order_id', d.order_id,
                    'scheduling_type', d.scheduling_type
                )
            FROM deliveries d
            WHERE d.company_id = :cid
              AND NOT EXISTS (
                  SELECT 1 FROM vault_items vi
                  WHERE vi.source_entity_id = d.id
                    AND vi.company_id = :cid
                    AND vi.event_type = 'delivery'
              )
        """), {"vault_id": vault_id, "cid": company_id})

        # Migrate delivery routes
        conn.execute(text("""
            INSERT INTO vault_items (id, vault_id, company_id, item_type, title, description,
                event_start, event_type, related_entity_type, related_entity_id,
                status, source, source_entity_id, created_by, created_at, metadata_json)
            SELECT
                gen_random_uuid()::text,
                :vault_id,
                r.company_id,
                'event',
                'Route ' || r.route_date::text,
                r.notes,
                r.route_date::timestamp AT TIME ZONE 'UTC',
                'route',
                'employee',
                r.driver_id,
                CASE WHEN r.status = 'completed' THEN 'completed'
                     WHEN r.status = 'cancelled' THEN 'cancelled'
                     ELSE 'active' END,
                'migrated',
                r.id,
                r.created_by,
                r.created_at,
                jsonb_build_object(
                    'driver_id', r.driver_id,
                    'vehicle_id', r.vehicle_id,
                    'total_stops', r.total_stops,
                    'route_status', r.status
                )
            FROM delivery_routes r
            WHERE r.company_id = :cid
              AND NOT EXISTS (
                  SELECT 1 FROM vault_items vi
                  WHERE vi.source_entity_id = r.id
                    AND vi.company_id = :cid
                    AND vi.event_type = 'route'
              )
        """), {"vault_id": vault_id, "cid": company_id})

        # Migrate pour events
        conn.execute(text("""
            INSERT INTO vault_items (id, vault_id, company_id, item_type, title, description,
                event_start, event_type, status, source, source_entity_id,
                created_by, created_at, metadata_json)
            SELECT
                gen_random_uuid()::text,
                :vault_id,
                pe.company_id,
                'event',
                'Pour ' || pe.pour_event_number,
                pe.crew_notes,
                pe.pour_date::timestamp AT TIME ZONE 'UTC',
                'production_pour',
                CASE WHEN pe.status IN ('completed', 'stripped') THEN 'completed'
                     WHEN pe.status = 'cancelled' THEN 'cancelled'
                     ELSE 'active' END,
                'migrated',
                pe.id,
                pe.created_by,
                pe.created_at,
                jsonb_build_object(
                    'pour_event_number', pe.pour_event_number,
                    'pour_time', pe.pour_time,
                    'status', pe.status,
                    'batch_ticket_id', pe.batch_ticket_id,
                    'cure_schedule_id', pe.cure_schedule_id
                )
            FROM pour_events pe
            WHERE pe.company_id = :cid
              AND NOT EXISTS (
                  SELECT 1 FROM vault_items vi
                  WHERE vi.source_entity_id = pe.id
                    AND vi.company_id = :cid
                    AND vi.event_type = 'production_pour'
              )
        """), {"vault_id": vault_id, "cid": company_id})

        # Migrate production log entries
        conn.execute(text("""
            INSERT INTO vault_items (id, vault_id, company_id, item_type, title,
                event_start, event_type, status, source, source_entity_id,
                created_by, created_at, metadata_json)
            SELECT
                gen_random_uuid()::text,
                :vault_id,
                ple.tenant_id,
                'production_record',
                'Production: ' || ple.quantity_produced || 'x ' || ple.product_name,
                ple.log_date::timestamp AT TIME ZONE 'UTC',
                'production_pour',
                'completed',
                'migrated',
                ple.id,
                ple.entered_by,
                ple.created_at,
                jsonb_build_object(
                    'product_id', ple.product_id,
                    'product_name', ple.product_name,
                    'quantity', ple.quantity_produced,
                    'entry_method', ple.entry_method,
                    'mix_design_id', ple.mix_design_id
                )
            FROM production_log_entries ple
            WHERE ple.tenant_id = :cid
              AND NOT EXISTS (
                  SELECT 1 FROM vault_items vi
                  WHERE vi.source_entity_id = ple.id
                    AND vi.company_id = :cid
                    AND vi.item_type = 'production_record'
              )
        """), {"vault_id": vault_id, "cid": company_id})

        # Migrate safety training events
        conn.execute(text("""
            INSERT INTO vault_items (id, vault_id, company_id, item_type, title, description,
                event_start, event_type, status, source, source_entity_id,
                created_by, created_at, metadata_json)
            SELECT
                gen_random_uuid()::text,
                :vault_id,
                ste.company_id,
                'event',
                'Training: ' || ste.training_topic,
                ste.content_summary,
                ste.training_date::timestamp AT TIME ZONE 'UTC',
                'safety_training',
                'completed',
                'migrated',
                ste.id,
                ste.created_by,
                ste.created_at,
                jsonb_build_object(
                    'osha_standard_code', ste.osha_standard_code,
                    'training_type', ste.training_type,
                    'trainer_name', ste.trainer_name,
                    'trainer_type', ste.trainer_type,
                    'duration_minutes', ste.duration_minutes
                )
            FROM safety_training_events ste
            WHERE ste.company_id = :cid
              AND NOT EXISTS (
                  SELECT 1 FROM vault_items vi
                  WHERE vi.source_entity_id = ste.id
                    AND vi.company_id = :cid
                    AND vi.event_type = 'safety_training'
              )
        """), {"vault_id": vault_id, "cid": company_id})

        # Migrate employee training records → documents
        conn.execute(text("""
            INSERT INTO vault_items (id, vault_id, company_id, item_type, title,
                document_type, related_entity_type, related_entity_id,
                status, source, source_entity_id, created_at, metadata_json)
            SELECT
                gen_random_uuid()::text,
                :vault_id,
                etr.company_id,
                'document',
                'Training Completion: ' || COALESCE(ste.training_topic, 'Unknown'),
                'training_completion',
                'employee',
                etr.employee_id,
                'active',
                'migrated',
                etr.id,
                etr.created_at,
                jsonb_build_object(
                    'training_event_id', etr.training_event_id,
                    'training_topic', ste.training_topic,
                    'completion_status', etr.completion_status,
                    'test_score', etr.test_score,
                    'expiry_date', etr.expiry_date::text
                )
            FROM employee_training_records etr
            JOIN safety_training_events ste ON ste.id = etr.training_event_id
            WHERE etr.company_id = :cid
              AND NOT EXISTS (
                  SELECT 1 FROM vault_items vi
                  WHERE vi.source_entity_id = etr.id
                    AND vi.company_id = :cid
                    AND vi.document_type = 'training_completion'
              )
        """), {"vault_id": vault_id, "cid": company_id})


def downgrade() -> None:
    # Remove all migrated vault items (source = 'migrated')
    op.execute("DELETE FROM vault_items WHERE source = 'migrated'")
    # Remove company vaults that have no non-migrated items
    op.execute("""
        DELETE FROM vaults v
        WHERE v.vault_type = 'company'
          AND NOT EXISTS (
              SELECT 1 FROM vault_items vi
              WHERE vi.vault_id = v.id AND vi.source != 'migrated'
          )
    """)
