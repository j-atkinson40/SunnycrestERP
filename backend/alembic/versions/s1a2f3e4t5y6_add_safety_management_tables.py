"""add safety_programs, safety_training_requirements, safety_training_events,
employee_training_records, safety_inspection_templates, safety_inspection_items,
safety_inspections, safety_inspection_results, safety_chemicals,
safety_incidents, safety_loto_procedures, safety_alerts tables and seed data

Revision ID: s1a2f3e4t5y6
Revises: k0l1m2n3o4p5
Create Date: 2026-03-17

"""
import json
import uuid
from datetime import datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa

revision = "s1a2f3e4t5y6"
down_revision = "k0l1m2n3o4p5"
branch_labels = None
depends_on = None

DEFAULT_COMPANY_ID = "65ef982b-5bee-4fc8-a8bb-19096b58ff3d"


def upgrade() -> None:
    # -- 1. safety_programs
    op.create_table(
        "safety_programs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("program_name", sa.String(200), nullable=False),
        sa.Column("osha_standard", sa.String(200), nullable=True),
        sa.Column("osha_standard_code", sa.String(50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "version", sa.Integer(), nullable=False, server_default="1"
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviewed_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("applicable_job_roles", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 2. safety_training_requirements
    op.create_table(
        "safety_training_requirements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("training_topic", sa.String(200), nullable=False),
        sa.Column("osha_standard_code", sa.String(50), nullable=True),
        sa.Column("applicable_roles", sa.Text(), nullable=True),
        sa.Column(
            "initial_training_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("refresher_frequency_months", sa.Integer(), nullable=True),
        sa.Column("new_hire_deadline_days", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 3. safety_training_events
    op.create_table(
        "safety_training_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("training_topic", sa.String(200), nullable=False),
        sa.Column("osha_standard_code", sa.String(50), nullable=True),
        sa.Column("training_type", sa.String(30), nullable=False),
        sa.Column("trainer_name", sa.String(200), nullable=False),
        sa.Column("trainer_type", sa.String(30), nullable=False),
        sa.Column("training_date", sa.Date(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("content_summary", sa.Text(), nullable=True),
        sa.Column("training_materials_url", sa.String(500), nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # -- 4. employee_training_records
    op.create_table(
        "employee_training_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "employee_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "training_event_id",
            sa.String(36),
            sa.ForeignKey("safety_training_events.id"),
            nullable=False,
        ),
        sa.Column("completion_status", sa.String(20), nullable=False),
        sa.Column("test_score", sa.Float(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("certificate_url", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # -- 5. safety_inspection_templates
    op.create_table(
        "safety_inspection_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("template_name", sa.String(200), nullable=False),
        sa.Column("inspection_type", sa.String(20), nullable=False),
        sa.Column("equipment_type", sa.String(100), nullable=True),
        sa.Column("frequency_days", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 6. safety_inspection_items
    op.create_table(
        "safety_inspection_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("safety_inspection_templates.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("item_order", sa.Integer(), nullable=False),
        sa.Column("item_text", sa.Text(), nullable=False),
        sa.Column("response_type", sa.String(20), nullable=False),
        sa.Column(
            "required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("failure_action", sa.Text(), nullable=True),
        sa.Column("osha_reference", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # -- 7. safety_inspections
    op.create_table(
        "safety_inspections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("safety_inspection_templates.id"),
            nullable=False,
        ),
        sa.Column("equipment_id", sa.String(36), nullable=True),
        sa.Column("equipment_identifier", sa.String(200), nullable=True),
        sa.Column(
            "inspector_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("inspection_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="in_progress",
        ),
        sa.Column("overall_result", sa.String(30), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 8. safety_inspection_results
    op.create_table(
        "safety_inspection_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "inspection_id",
            sa.String(36),
            sa.ForeignKey("safety_inspections.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "item_id",
            sa.String(36),
            sa.ForeignKey("safety_inspection_items.id"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("result", sa.String(50), nullable=True),
        sa.Column("finding_notes", sa.Text(), nullable=True),
        sa.Column(
            "corrective_action_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("corrective_action_description", sa.Text(), nullable=True),
        sa.Column("corrective_action_due_date", sa.Date(), nullable=True),
        sa.Column(
            "corrective_action_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "corrective_action_completed_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("photo_urls", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # -- 9. safety_chemicals
    op.create_table(
        "safety_chemicals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("chemical_name", sa.String(200), nullable=False),
        sa.Column("manufacturer", sa.String(200), nullable=True),
        sa.Column("product_number", sa.String(100), nullable=True),
        sa.Column("cas_number", sa.String(50), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("quantity_on_hand", sa.Float(), nullable=True),
        sa.Column("unit_of_measure", sa.String(50), nullable=True),
        sa.Column("hazard_class", sa.Text(), nullable=True),
        sa.Column("ppe_required", sa.Text(), nullable=True),
        sa.Column("sds_url", sa.String(500), nullable=True),
        sa.Column("sds_date", sa.Date(), nullable=True),
        sa.Column("sds_review_due_at", sa.Date(), nullable=True),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 10. safety_incidents
    op.create_table(
        "safety_incidents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("incident_type", sa.String(30), nullable=False),
        sa.Column("incident_date", sa.Date(), nullable=False),
        sa.Column("incident_time", sa.Time(), nullable=True),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column(
            "involved_employee_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("witnesses", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("immediate_cause", sa.Text(), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("body_part_affected", sa.String(100), nullable=True),
        sa.Column("injury_type", sa.String(100), nullable=True),
        sa.Column(
            "medical_treatment",
            sa.String(30),
            nullable=False,
            server_default="none",
        ),
        sa.Column(
            "days_away_from_work",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "days_on_restricted_duty",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "osha_recordable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("osha_300_case_number", sa.Integer(), nullable=True),
        sa.Column(
            "reported_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "investigated_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("corrective_actions", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="reported",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 11. safety_loto_procedures
    op.create_table(
        "safety_loto_procedures",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("machine_name", sa.String(200), nullable=False),
        sa.Column("machine_location", sa.String(200), nullable=True),
        sa.Column("machine_id", sa.String(36), nullable=True),
        sa.Column("procedure_number", sa.String(50), nullable=False),
        sa.Column("energy_sources", sa.Text(), nullable=False),
        sa.Column("ppe_required", sa.Text(), nullable=True),
        sa.Column("steps", sa.Text(), nullable=False),
        sa.Column("estimated_time_minutes", sa.Integer(), nullable=True),
        sa.Column("authorized_employees", sa.Text(), nullable=True),
        sa.Column("affected_employees", sa.Text(), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 12. safety_alerts
    op.create_table(
        "safety_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("reference_id", sa.String(36), nullable=True),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "acknowledged_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # ------------------------------------------------------------------ #
    #  SEED DATA — only if the default company exists                     #
    # ------------------------------------------------------------------ #
    conn = op.get_bind()
    company_exists = conn.execute(
        sa.text("SELECT 1 FROM companies WHERE id = :cid"),
        {"cid": DEFAULT_COMPANY_ID},
    ).fetchone()

    if not company_exists:
        return  # Skip seed data — company not present (e.g. fresh production DB)

    now = datetime.now(timezone.utc)
    one_year = now + timedelta(days=365)

    # -- Seed safety_programs ------------------------------------------------
    programs_table = sa.table(
        "safety_programs",
        sa.column("id", sa.String),
        sa.column("company_id", sa.String),
        sa.column("program_name", sa.String),
        sa.column("osha_standard", sa.String),
        sa.column("osha_standard_code", sa.String),
        sa.column("description", sa.Text),
        sa.column("content", sa.Text),
        sa.column("version", sa.Integer),
        sa.column("status", sa.String),
        sa.column("next_review_due_at", sa.DateTime),
        sa.column("applicable_job_roles", sa.Text),
        sa.column("created_at", sa.DateTime),
    )

    programs_data = [
        {
            "program_name": "Hazard Communication Program",
            "osha_standard": "29 CFR 1910.1200 — Hazard Communication",
            "osha_standard_code": "1910.1200",
            "description": "Written program for chemical hazard communication including SDS management, container labeling, and employee training requirements.",
            "applicable_job_roles": json.dumps(["All Employees"]),
        },
        {
            "program_name": "Lockout/Tagout Program",
            "osha_standard": "29 CFR 1910.147 — Control of Hazardous Energy",
            "osha_standard_code": "1910.147",
            "description": "Energy control procedures for servicing and maintenance of machines and equipment.",
            "applicable_job_roles": json.dumps(["Maintenance", "Production"]),
        },
        {
            "program_name": "Powered Industrial Truck Safety Program",
            "osha_standard": "29 CFR 1910.178 — Powered Industrial Trucks",
            "osha_standard_code": "1910.178",
            "description": "Forklift and powered industrial truck operation, training, and inspection requirements.",
            "applicable_job_roles": json.dumps(["Forklift Operators", "Warehouse"]),
        },
        {
            "program_name": "Respiratory Protection Program",
            "osha_standard": "29 CFR 1910.134 — Respiratory Protection",
            "osha_standard_code": "1910.134",
            "description": "Respiratory protection selection, fit testing, medical evaluation, and use requirements.",
            "applicable_job_roles": json.dumps(["Maintenance", "Production"]),
        },
        {
            "program_name": "Emergency Action Plan",
            "osha_standard": "29 CFR 1910.38 — Emergency Action Plans",
            "osha_standard_code": "1910.38",
            "description": "Emergency procedures including evacuation routes, alarm systems, and employee responsibilities.",
            "applicable_job_roles": json.dumps(["All Employees"]),
        },
        {
            "program_name": "Incident Investigation and Reporting Program",
            "osha_standard": None,
            "osha_standard_code": None,
            "description": "Procedures for reporting workplace injuries, illnesses, near-misses, and conducting root cause investigations.",
            "applicable_job_roles": json.dumps(["All Employees"]),
        },
        {
            "program_name": "Personal Protective Equipment Program",
            "osha_standard": "29 CFR 1910.132 — General Requirements for PPE",
            "osha_standard_code": "1910.132",
            "description": "PPE hazard assessment, selection, training, and use requirements.",
            "applicable_job_roles": json.dumps(["All Employees"]),
        },
        {
            "program_name": "Housekeeping Program",
            "osha_standard": None,
            "osha_standard_code": None,
            "description": "Facility cleanliness, organization, and housekeeping standards to prevent workplace hazards.",
            "applicable_job_roles": json.dumps(["All Employees"]),
        },
    ]

    op.bulk_insert(
        programs_table,
        [
            {
                "id": str(uuid.uuid4()),
                "company_id": DEFAULT_COMPANY_ID,
                "content": "PLACEHOLDER — This written program must be customized for your facility.",
                "version": 1,
                "status": "active",
                "next_review_due_at": one_year,
                "created_at": now,
                **prog,
            }
            for prog in programs_data
        ],
    )

    # -- Seed safety_training_requirements -----------------------------------
    requirements_table = sa.table(
        "safety_training_requirements",
        sa.column("id", sa.String),
        sa.column("company_id", sa.String),
        sa.column("training_topic", sa.String),
        sa.column("osha_standard_code", sa.String),
        sa.column("applicable_roles", sa.Text),
        sa.column("initial_training_required", sa.Boolean),
        sa.column("refresher_frequency_months", sa.Integer),
        sa.column("new_hire_deadline_days", sa.Integer),
        sa.column("created_at", sa.DateTime),
    )

    training_reqs = [
        {
            "training_topic": "Hazard Communication / Right to Know",
            "osha_standard_code": "1910.1200",
            "applicable_roles": json.dumps(["All Employees"]),
            "initial_training_required": True,
            "refresher_frequency_months": 12,
            "new_hire_deadline_days": 30,
        },
        {
            "training_topic": "Emergency Action Plan",
            "osha_standard_code": "1910.38",
            "applicable_roles": json.dumps(["All Employees"]),
            "initial_training_required": True,
            "refresher_frequency_months": None,
            "new_hire_deadline_days": 30,
        },
        {
            "training_topic": "Incident Reporting Procedures",
            "osha_standard_code": None,
            "applicable_roles": json.dumps(["All Employees"]),
            "initial_training_required": True,
            "refresher_frequency_months": None,
            "new_hire_deadline_days": 30,
        },
        {
            "training_topic": "Powered Industrial Truck Operation",
            "osha_standard_code": "1910.178",
            "applicable_roles": json.dumps(["Forklift Operators"]),
            "initial_training_required": True,
            "refresher_frequency_months": 36,
            "new_hire_deadline_days": None,
        },
        {
            "training_topic": "Forklift Pre-Shift Inspection",
            "osha_standard_code": "1910.178",
            "applicable_roles": json.dumps(["Forklift Operators"]),
            "initial_training_required": True,
            "refresher_frequency_months": None,
            "new_hire_deadline_days": None,
        },
        {
            "training_topic": "Lockout/Tagout Procedures",
            "osha_standard_code": "1910.147",
            "applicable_roles": json.dumps(["Maintenance"]),
            "initial_training_required": True,
            "refresher_frequency_months": 12,
            "new_hire_deadline_days": None,
        },
        {
            "training_topic": "Respiratory Protection",
            "osha_standard_code": "1910.134",
            "applicable_roles": json.dumps(["Maintenance"]),
            "initial_training_required": True,
            "refresher_frequency_months": 12,
            "new_hire_deadline_days": None,
        },
        {
            "training_topic": "Silica/Concrete Dust Awareness",
            "osha_standard_code": None,
            "applicable_roles": json.dumps(["Production"]),
            "initial_training_required": True,
            "refresher_frequency_months": 12,
            "new_hire_deadline_days": None,
        },
        {
            "training_topic": "PPE Selection and Use",
            "osha_standard_code": "1910.132",
            "applicable_roles": json.dumps(["Production"]),
            "initial_training_required": True,
            "refresher_frequency_months": 12,
            "new_hire_deadline_days": None,
        },
    ]

    op.bulk_insert(
        requirements_table,
        [
            {
                "id": str(uuid.uuid4()),
                "company_id": DEFAULT_COMPANY_ID,
                "created_at": now,
                **req,
            }
            for req in training_reqs
        ],
    )

    # -- Seed safety_inspection_templates + safety_inspection_items -----------
    templates_table = sa.table(
        "safety_inspection_templates",
        sa.column("id", sa.String),
        sa.column("company_id", sa.String),
        sa.column("template_name", sa.String),
        sa.column("inspection_type", sa.String),
        sa.column("equipment_type", sa.String),
        sa.column("frequency_days", sa.Integer),
        sa.column("active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
    )

    items_table = sa.table(
        "safety_inspection_items",
        sa.column("id", sa.String),
        sa.column("template_id", sa.String),
        sa.column("company_id", sa.String),
        sa.column("item_order", sa.Integer),
        sa.column("item_text", sa.Text),
        sa.column("response_type", sa.String),
        sa.column("required", sa.Boolean),
        sa.column("failure_action", sa.Text),
        sa.column("osha_reference", sa.String),
        sa.column("created_at", sa.DateTime),
    )

    # --- Template 1: Forklift Pre-Shift Inspection ---
    t1_id = str(uuid.uuid4())
    op.bulk_insert(
        templates_table,
        [
            {
                "id": t1_id,
                "company_id": DEFAULT_COMPANY_ID,
                "template_name": "Forklift Pre-Shift Inspection",
                "inspection_type": "pre_shift",
                "equipment_type": "forklift",
                "frequency_days": 1,
                "active": True,
                "created_at": now,
            },
        ],
    )

    t1_items = [
        {"item_order": 1, "item_text": "Horn — functional", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": "29 CFR 1910.178"},
        {"item_order": 2, "item_text": "Lights — all operational", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 3, "item_text": "Forks — no cracks, bends, or damage", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 4, "item_text": "Hydraulics — no leaks visible", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 5, "item_text": "Tires — adequate inflation, no damage", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 6, "item_text": "Seatbelt — functional and present", "response_type": "pass_fail", "required": True, "failure_action": None, "osha_reference": None},
        {"item_order": 7, "item_text": "Overhead guard — in place and undamaged", "response_type": "pass_fail", "required": True, "failure_action": None, "osha_reference": None},
        {"item_order": 8, "item_text": "Fluid levels — oil, hydraulic, coolant", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 9, "item_text": "Battery — charged if electric, fuel if propane", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 10, "item_text": "Data plate — present and legible", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 11, "item_text": "Any damage from previous shift?", "response_type": "yes_no", "required": False, "failure_action": "Describe damage and report to supervisor immediately", "osha_reference": None},
    ]

    op.bulk_insert(
        items_table,
        [
            {
                "id": str(uuid.uuid4()),
                "template_id": t1_id,
                "company_id": DEFAULT_COMPANY_ID,
                "created_at": now,
                **item,
            }
            for item in t1_items
        ],
    )

    # --- Template 2: Fire Extinguisher Monthly Inspection ---
    t2_id = str(uuid.uuid4())
    op.bulk_insert(
        templates_table,
        [
            {
                "id": t2_id,
                "company_id": DEFAULT_COMPANY_ID,
                "template_name": "Fire Extinguisher Monthly Inspection",
                "inspection_type": "monthly",
                "equipment_type": "fire_extinguisher",
                "frequency_days": 30,
                "active": True,
                "created_at": now,
            },
        ],
    )

    t2_items = [
        {"item_order": 1, "item_text": "Location — in designated location and accessible", "response_type": "pass_fail", "required": True, "failure_action": None, "osha_reference": None},
        {"item_order": 2, "item_text": "Pressure gauge — in green zone", "response_type": "pass_fail", "required": True, "failure_action": None, "osha_reference": None},
        {"item_order": 3, "item_text": "Pin and tamper seal — intact", "response_type": "pass_fail", "required": True, "failure_action": None, "osha_reference": None},
        {"item_order": 4, "item_text": "Physical condition — no damage, dents, or corrosion", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 5, "item_text": "Inspection tag — last annual inspection within 12 months", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
    ]

    op.bulk_insert(
        items_table,
        [
            {
                "id": str(uuid.uuid4()),
                "template_id": t2_id,
                "company_id": DEFAULT_COMPANY_ID,
                "created_at": now,
                **item,
            }
            for item in t2_items
        ],
    )

    # --- Template 3: Eyewash Station Weekly Test ---
    t3_id = str(uuid.uuid4())
    op.bulk_insert(
        templates_table,
        [
            {
                "id": t3_id,
                "company_id": DEFAULT_COMPANY_ID,
                "template_name": "Eyewash Station Weekly Test",
                "inspection_type": "weekly",
                "equipment_type": "eyewash",
                "frequency_days": 7,
                "active": True,
                "created_at": now,
            },
        ],
    )

    t3_items = [
        {"item_order": 1, "item_text": "Activate station — water flows freely from both heads", "response_type": "pass_fail", "required": True, "failure_action": None, "osha_reference": None},
        {"item_order": 2, "item_text": "Water temperature — tepid, not hot or cold", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 3, "item_text": "Area around station — clear and unobstructed", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 4, "item_text": "Flow duration — tested for minimum 15 seconds", "response_type": "pass_fail", "required": True, "failure_action": None, "osha_reference": "29 CFR 1910.151"},
    ]

    op.bulk_insert(
        items_table,
        [
            {
                "id": str(uuid.uuid4()),
                "template_id": t3_id,
                "company_id": DEFAULT_COMPANY_ID,
                "created_at": now,
                **item,
            }
            for item in t3_items
        ],
    )

    # --- Template 4: PPE Station Monthly Inspection ---
    t4_id = str(uuid.uuid4())
    op.bulk_insert(
        templates_table,
        [
            {
                "id": t4_id,
                "company_id": DEFAULT_COMPANY_ID,
                "template_name": "PPE Station Monthly Inspection",
                "inspection_type": "monthly",
                "equipment_type": "ppe_station",
                "frequency_days": 30,
                "active": True,
                "created_at": now,
            },
        ],
    )

    t4_items = [
        {"item_order": 1, "item_text": "Safety glasses — adequate supply, clean, no scratches", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 2, "item_text": "Gloves — appropriate types available, no damage", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 3, "item_text": "Hearing protection — adequate supply", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 4, "item_text": "Hard hats — present, no cracks", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 5, "item_text": "Respiratory protection — appropriate respirators available if required", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
    ]

    op.bulk_insert(
        items_table,
        [
            {
                "id": str(uuid.uuid4()),
                "template_id": t4_id,
                "company_id": DEFAULT_COMPANY_ID,
                "created_at": now,
                **item,
            }
            for item in t4_items
        ],
    )

    # --- Template 5: General Facility Monthly Safety Walkthrough ---
    t5_id = str(uuid.uuid4())
    op.bulk_insert(
        templates_table,
        [
            {
                "id": t5_id,
                "company_id": DEFAULT_COMPANY_ID,
                "template_name": "General Facility Monthly Safety Walkthrough",
                "inspection_type": "monthly",
                "equipment_type": "general_facility",
                "frequency_days": 30,
                "active": True,
                "created_at": now,
            },
        ],
    )

    t5_items = [
        {"item_order": 1, "item_text": "Emergency exits — unobstructed and marked", "response_type": "pass_fail", "required": True, "failure_action": None, "osha_reference": None},
        {"item_order": 2, "item_text": "Exit signs — illuminated", "response_type": "pass_fail", "required": True, "failure_action": None, "osha_reference": None},
        {"item_order": 3, "item_text": "Aisle ways — clear of obstructions", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 4, "item_text": "Housekeeping — general cleanliness acceptable", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 5, "item_text": "Electrical panels — unobstructed 36 inch clearance", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": "29 CFR 1910.303"},
        {"item_order": 6, "item_text": "Hazardous materials — properly stored and labeled", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 7, "item_text": "First aid kit — stocked and accessible", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 8, "item_text": "Safety signage — required signs posted", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
        {"item_order": 9, "item_text": "Spill kit — available and stocked", "response_type": "pass_fail", "required": False, "failure_action": None, "osha_reference": None},
    ]

    op.bulk_insert(
        items_table,
        [
            {
                "id": str(uuid.uuid4()),
                "template_id": t5_id,
                "company_id": DEFAULT_COMPANY_ID,
                "created_at": now,
                **item,
            }
            for item in t5_items
        ],
    )


def downgrade() -> None:
    op.drop_table("safety_alerts")
    op.drop_table("safety_loto_procedures")
    op.drop_table("safety_incidents")
    op.drop_table("safety_chemicals")
    op.drop_table("safety_inspection_results")
    op.drop_table("safety_inspections")
    op.drop_table("safety_inspection_items")
    op.drop_table("safety_inspection_templates")
    op.drop_table("employee_training_records")
    op.drop_table("safety_training_events")
    op.drop_table("safety_training_requirements")
    op.drop_table("safety_programs")
