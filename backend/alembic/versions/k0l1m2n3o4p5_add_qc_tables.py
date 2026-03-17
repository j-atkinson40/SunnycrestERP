"""add qc_inspection_templates, qc_inspection_steps, qc_inspections,
qc_step_results, qc_media, qc_defect_types, qc_dispositions,
qc_rework_records tables and seed data

Revision ID: k0l1m2n3o4p5
Revises: j9k0l1m2n3o4
Create Date: 2026-03-17

"""
import uuid

from alembic import op
import sqlalchemy as sa

revision = "k0l1m2n3o4p5"
down_revision = "j9k0l1m2n3o4"
branch_labels = None
depends_on = None

DEFAULT_COMPANY_ID = "65ef982b-5bee-4fc8-a8bb-19096b58ff3d"


def upgrade() -> None:
    # -- qc_defect_types (created first because qc_step_results references it)
    op.create_table(
        "qc_defect_types",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("defect_name", sa.String(200), nullable=False),
        sa.Column("product_category", sa.String(50), nullable=False),
        sa.Column(
            "default_severity",
            sa.String(20),
            nullable=False,
            server_default="minor",
        ),
        sa.Column(
            "default_disposition",
            sa.String(30),
            nullable=False,
            server_default="hold_pending_review",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # -- qc_inspection_templates
    op.create_table(
        "qc_inspection_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("product_category", sa.String(50), nullable=False),
        sa.Column("template_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "wilbert_warranty_compliant",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_active",
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

    # -- qc_inspection_steps
    op.create_table(
        "qc_inspection_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("qc_inspection_templates.id"),
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
        sa.Column("step_name", sa.String(200), nullable=False),
        sa.Column(
            "step_order", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "inspection_type",
            sa.String(30),
            nullable=False,
            server_default="visual",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("pass_criteria", sa.Text(), nullable=True),
        sa.Column(
            "photo_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # -- qc_inspections
    op.create_table(
        "qc_inspections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "inventory_item_id",
            sa.String(36),
            sa.ForeignKey("inventory_items.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("qc_inspection_templates.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("product_category", sa.String(50), nullable=False),
        sa.Column("product_type", sa.String(100), nullable=True),
        sa.Column(
            "inspector_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("overall_notes", sa.Text(), nullable=True),
        sa.Column(
            "certificate_number", sa.String(20), unique=True, nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- qc_step_results
    op.create_table(
        "qc_step_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "inspection_id",
            sa.String(36),
            sa.ForeignKey("qc_inspections.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "step_id",
            sa.String(36),
            sa.ForeignKey("qc_inspection_steps.id"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "result",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "defect_type_id",
            sa.String(36),
            sa.ForeignKey("qc_defect_types.id"),
            nullable=True,
        ),
        sa.Column("defect_severity", sa.String(20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # -- qc_media
    op.create_table(
        "qc_media",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "step_result_id",
            sa.String(36),
            sa.ForeignKey("qc_step_results.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "inspection_id",
            sa.String(36),
            sa.ForeignKey("qc_inspections.id"),
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
        sa.Column("file_url", sa.String(500), nullable=False),
        sa.Column("caption", sa.String(500), nullable=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # -- qc_dispositions
    op.create_table(
        "qc_dispositions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "inspection_id",
            sa.String(36),
            sa.ForeignKey("qc_inspections.id"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column(
            "company_id",
            sa.String(36),
            sa.ForeignKey("companies.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "decided_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("disposition", sa.String(30), nullable=False),
        sa.Column("disposition_notes", sa.Text(), nullable=True),
        sa.Column("rework_instructions", sa.Text(), nullable=True),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # -- qc_rework_records
    op.create_table(
        "qc_rework_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "inspection_id",
            sa.String(36),
            sa.ForeignKey("qc_inspections.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "original_inspection_id",
            sa.String(36),
            sa.ForeignKey("qc_inspections.id"),
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
        sa.Column("rework_description", sa.Text(), nullable=False),
        sa.Column(
            "rework_completed_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "rework_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "re_inspection_id",
            sa.String(36),
            sa.ForeignKey("qc_inspections.id"),
            nullable=True,
        ),
    )

    # -- Add qc_status column to inventory_items
    op.add_column(
        "inventory_items",
        sa.Column("qc_status", sa.String(30), nullable=True),
    )

    # -- Seed data (only if the default company exists in this environment) ---
    conn = op.get_bind()
    company_exists = conn.execute(
        sa.text("SELECT 1 FROM companies WHERE id = :cid"),
        {"cid": DEFAULT_COMPANY_ID},
    ).fetchone()

    if not company_exists:
        return  # Skip seed data — company not present (e.g. fresh production DB)

    defect_types_table = sa.table(
        "qc_defect_types",
        sa.column("id", sa.String),
        sa.column("company_id", sa.String),
        sa.column("defect_name", sa.String),
        sa.column("product_category", sa.String),
        sa.column("default_severity", sa.String),
        sa.column("default_disposition", sa.String),
        sa.column("description", sa.Text),
        sa.column("is_active", sa.Boolean),
    )

    burial_vault_defects = [
        ("Surface crack", "major", "hold_pending_review"),
        ("Hairline crack", "minor", "conditional_pass"),
        ("Surface void/honeycombing", "major", "rework"),
        ("Improper seal seat", "major", "rework"),
        ("Personalization error", "major", "rework"),
        ("Cosmetic blemish", "minor", "conditional_pass"),
        ("Color inconsistency", "minor", "conditional_pass"),
        ("Failed pressure test", "critical", "scrap"),
        ("Structural crack through wall", "critical", "scrap"),
        ("Improper lid fit", "major", "rework"),
        ("Damaged corner", "major", "hold_pending_review"),
    ]

    redi_rock_defects = [
        ("Dimensional out of tolerance", "major", "hold_pending_review"),
        ("Surface spalling", "minor", "conditional_pass"),
        ("Structural crack", "critical", "scrap"),
        ("Broken connection point", "critical", "scrap"),
        ("Surface void", "minor", "rework"),
    ]

    rows = []
    for name, severity, disposition in burial_vault_defects:
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "company_id": DEFAULT_COMPANY_ID,
                "defect_name": name,
                "product_category": "burial_vault",
                "default_severity": severity,
                "default_disposition": disposition,
                "description": None,
                "is_active": True,
            }
        )
    for name, severity, disposition in redi_rock_defects:
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "company_id": DEFAULT_COMPANY_ID,
                "defect_name": name,
                "product_category": "redi_rock",
                "default_severity": severity,
                "default_disposition": disposition,
                "description": None,
                "is_active": True,
            }
        )

    op.bulk_insert(defect_types_table, rows)

    # -- Seed inspection templates -------------------------------------------
    templates_table = sa.table(
        "qc_inspection_templates",
        sa.column("id", sa.String),
        sa.column("company_id", sa.String),
        sa.column("product_category", sa.String),
        sa.column("template_name", sa.String),
        sa.column("description", sa.Text),
        sa.column("wilbert_warranty_compliant", sa.Boolean),
        sa.column("is_active", sa.Boolean),
    )

    steps_table = sa.table(
        "qc_inspection_steps",
        sa.column("id", sa.String),
        sa.column("template_id", sa.String),
        sa.column("company_id", sa.String),
        sa.column("step_name", sa.String),
        sa.column("step_order", sa.Integer),
        sa.column("inspection_type", sa.String),
        sa.column("description", sa.Text),
        sa.column("pass_criteria", sa.Text),
        sa.column("photo_required", sa.Boolean),
        sa.column("required", sa.Boolean),
    )

    # Burial Vault template
    bv_template_id = str(uuid.uuid4())
    op.bulk_insert(
        templates_table,
        [
            {
                "id": bv_template_id,
                "company_id": DEFAULT_COMPANY_ID,
                "product_category": "burial_vault",
                "template_name": "Burial Vault Standard Inspection",
                "description": "Full QC inspection for burial vaults including Wilbert warranty compliance checks",
                "wilbert_warranty_compliant": True,
                "is_active": True,
            },
        ],
    )

    bv_steps = [
        {
            "step_name": "Visual Surface Inspection",
            "step_order": 1,
            "inspection_type": "visual",
            "description": "Inspect all exterior surfaces for cracks, voids, blemishes, and color consistency",
            "pass_criteria": "No visible cracks, voids larger than 3mm, or color inconsistencies",
            "photo_required": True,
            "required": True,
        },
        {
            "step_name": "Dimensional Check",
            "step_order": 2,
            "inspection_type": "dimensional",
            "description": "Verify length, width, height, and wall thickness against specifications",
            "pass_criteria": "All dimensions within +/- 1/4 inch tolerance",
            "photo_required": False,
            "required": True,
        },
        {
            "step_name": "Lid Fit Check",
            "step_order": 3,
            "inspection_type": "visual",
            "description": "Place lid on vault body and verify proper fit and alignment",
            "pass_criteria": "Lid seats flush with no gaps exceeding 1/8 inch",
            "photo_required": True,
            "required": True,
        },
        {
            "step_name": "Seal Seat Inspection",
            "step_order": 4,
            "inspection_type": "visual",
            "description": "Inspect seal seat surface for smoothness and proper profile",
            "pass_criteria": "Seal seat smooth, free of voids, and within profile tolerance",
            "photo_required": True,
            "required": True,
        },
        {
            "step_name": "Pressure Test",
            "step_order": 5,
            "inspection_type": "pressure_test",
            "description": "Perform hydrostatic pressure test per Wilbert warranty requirements",
            "pass_criteria": "No water ingress after 15 minutes at specified pressure",
            "photo_required": False,
            "required": True,
        },
        {
            "step_name": "Personalization Verification",
            "step_order": 6,
            "inspection_type": "visual",
            "description": "Verify all personalization markings match order specifications",
            "pass_criteria": "All text, emblems, and decorations match order exactly",
            "photo_required": True,
            "required": False,
        },
        {
            "step_name": "Final Photo Documentation",
            "step_order": 7,
            "inspection_type": "photo_required",
            "description": "Capture final photos of completed vault from all angles",
            "pass_criteria": "Clear photos of all four sides, top, and interior",
            "photo_required": True,
            "required": True,
        },
    ]

    op.bulk_insert(
        steps_table,
        [
            {
                "id": str(uuid.uuid4()),
                "template_id": bv_template_id,
                "company_id": DEFAULT_COMPANY_ID,
                **step,
            }
            for step in bv_steps
        ],
    )

    # Redi-Rock template
    rr_template_id = str(uuid.uuid4())
    op.bulk_insert(
        templates_table,
        [
            {
                "id": rr_template_id,
                "company_id": DEFAULT_COMPANY_ID,
                "product_category": "redi_rock",
                "template_name": "Redi-Rock Block Inspection",
                "description": "Standard QC inspection for Redi-Rock retaining wall blocks",
                "wilbert_warranty_compliant": False,
                "is_active": True,
            },
        ],
    )

    rr_steps = [
        {
            "step_name": "Visual Surface Inspection",
            "step_order": 1,
            "inspection_type": "visual",
            "description": "Inspect all surfaces for spalling, cracks, and voids",
            "pass_criteria": "No structural cracks; surface voids less than 5mm",
            "photo_required": True,
            "required": True,
        },
        {
            "step_name": "Dimensional Verification",
            "step_order": 2,
            "inspection_type": "dimensional",
            "description": "Measure block dimensions and verify within tolerance",
            "pass_criteria": "All dimensions within +/- 3mm of specification",
            "photo_required": False,
            "required": True,
        },
        {
            "step_name": "Connection Point Check",
            "step_order": 3,
            "inspection_type": "visual",
            "description": "Verify all knobs and connection points are intact and properly formed",
            "pass_criteria": "All connection points intact with no chips or breaks",
            "photo_required": True,
            "required": True,
        },
        {
            "step_name": "Weight Verification",
            "step_order": 4,
            "inspection_type": "dimensional",
            "description": "Weigh block to verify concrete density within specification",
            "pass_criteria": "Weight within 5% of target weight for block type",
            "photo_required": False,
            "required": True,
        },
    ]

    op.bulk_insert(
        steps_table,
        [
            {
                "id": str(uuid.uuid4()),
                "template_id": rr_template_id,
                "company_id": DEFAULT_COMPANY_ID,
                **step,
            }
            for step in rr_steps
        ],
    )


def downgrade() -> None:
    op.drop_column("inventory_items", "qc_status")
    op.drop_table("qc_rework_records")
    op.drop_table("qc_dispositions")
    op.drop_table("qc_media")
    op.drop_table("qc_step_results")
    op.drop_table("qc_inspections")
    op.drop_table("qc_inspection_steps")
    op.drop_table("qc_inspection_templates")
    op.drop_table("qc_defect_types")
