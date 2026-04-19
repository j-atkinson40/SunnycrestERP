"""Intelligence Phase 2c-0b — multimodal (vision) support.

Schema additions:
  intelligence_prompt_versions.supports_vision       Boolean, default False
  intelligence_prompt_versions.vision_content_type   String(32), nullable
                                                    ("image" | "document" | null)

Data changes:
  - Seeds `vision` route in intelligence_model_routes if absent
    (Sonnet 4.6 primary + fallback; vision pricing = text pricing for Sonnet 4.6)
  - Promotes the two prompts that Phase 2c-0a flagged via the __content_type__
    marker:
      accounting.extract_check_image  → supports_vision=true, vision_content_type="image"
      pricing.extract_pdf_text        → supports_vision=true, vision_content_type="document"
    and strips __content_type__ from their variable_schema (keeping the rest).

Revision ID: r18_intelligence_vision_support
Revises: r17_intelligence_linkage_extensions
"""

from alembic import op
import sqlalchemy as sa


revision = "r18_intelligence_vision_support"
down_revision = "r17_intelligence_linkage_extensions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Column additions ─────────────────────────────────────────────
    op.add_column(
        "intelligence_prompt_versions",
        sa.Column(
            "supports_vision",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "intelligence_prompt_versions",
        sa.Column("vision_content_type", sa.String(32), nullable=True),
    )

    # ── 2. Seed vision model route (if not already present) ─────────────
    # Sonnet 4.6 as both primary and fallback — no cheaper vision fallback.
    # Pricing matches text Sonnet 4.6: $3/M input, $15/M output.
    bind = op.get_bind()
    exists = bind.execute(
        sa.text("SELECT id FROM intelligence_model_routes WHERE route_key = 'vision'")
    ).first()
    if exists is None:
        import uuid as _uuid

        bind.execute(
            sa.text(
                """
                INSERT INTO intelligence_model_routes (
                    id, route_key, primary_model, fallback_model, provider,
                    input_cost_per_million, output_cost_per_million,
                    max_tokens_default, temperature_default,
                    is_active, notes, created_at, updated_at
                ) VALUES (
                    :id, 'vision', 'claude-sonnet-4-6', 'claude-sonnet-4-6', 'anthropic',
                    3.00, 15.00,
                    8192, 0.3,
                    true,
                    'Vision-capable route for image and document content blocks (Phase 2c-0b)',
                    NOW(), NOW()
                )
                """
            ),
            {"id": str(_uuid.uuid4())},
        )

    # ── 3. Promote the two Phase 2c-0a vision prompts ───────────────────
    # accounting.extract_check_image → image
    # pricing.extract_pdf_text       → document
    import json as _json

    for prompt_key, content_type in (
        ("accounting.extract_check_image", "image"),
        ("pricing.extract_pdf_text", "document"),
    ):
        # Locate the active v1 for the platform-global prompt
        row = bind.execute(
            sa.text(
                """
                SELECT v.id, v.variable_schema
                FROM intelligence_prompt_versions v
                JOIN intelligence_prompts p ON p.id = v.prompt_id
                WHERE p.prompt_key = :key
                  AND p.company_id IS NULL
                  AND v.status = 'active'
                """
            ),
            {"key": prompt_key},
        ).first()
        if row is None:
            # Prompt not yet seeded — skip (seed_intelligence_phase2c.py must run first)
            continue

        version_id, current_schema = row
        # Strip the __content_type__ marker while preserving the rest
        new_schema = {
            k: v for k, v in (current_schema or {}).items() if k != "__content_type__"
        }
        bind.execute(
            sa.text(
                """
                UPDATE intelligence_prompt_versions
                SET supports_vision = true,
                    vision_content_type = :ctype,
                    variable_schema = CAST(:vs AS json)
                WHERE id = :vid
                """
            ),
            {
                "vid": version_id,
                "ctype": content_type,
                "vs": _json.dumps(new_schema),
            },
        )


def downgrade() -> None:
    # Data rollback: restore __content_type__ markers for future re-promotion
    bind = op.get_bind()
    import json as _json

    for prompt_key, content_type in (
        ("accounting.extract_check_image", "image"),
        ("pricing.extract_pdf_text", "document"),
    ):
        row = bind.execute(
            sa.text(
                """
                SELECT v.id, v.variable_schema
                FROM intelligence_prompt_versions v
                JOIN intelligence_prompts p ON p.id = v.prompt_id
                WHERE p.prompt_key = :key
                  AND p.company_id IS NULL
                  AND v.status = 'active'
                """
            ),
            {"key": prompt_key},
        ).first()
        if row is None:
            continue
        version_id, current_schema = row
        restored = dict(current_schema or {})
        restored["__content_type__"] = {
            "type": "string",
            "required": True,
            "description": f"{content_type} — multimodal, rendered by 2c-0b",
        }
        bind.execute(
            sa.text(
                """
                UPDATE intelligence_prompt_versions
                SET supports_vision = false,
                    vision_content_type = NULL,
                    variable_schema = CAST(:vs AS json)
                WHERE id = :vid
                """
            ),
            {"vid": version_id, "vs": _json.dumps(restored)},
        )

    # Delete the vision route
    bind.execute(
        sa.text("DELETE FROM intelligence_model_routes WHERE route_key = 'vision'")
    )

    op.drop_column("intelligence_prompt_versions", "vision_content_type")
    op.drop_column("intelligence_prompt_versions", "supports_vision")
