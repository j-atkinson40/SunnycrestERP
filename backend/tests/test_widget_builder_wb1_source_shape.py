"""Source-shape regression gates for WB-1 substrate.

Per DECISIONS.md 2026-05-21 entry 31, every load-bearing substrate
file ships a source-shape gate — a regex check that catches
hypothetical reverts (someone removes the additive branch, dropping
the validator's composed-path; someone removes the CompositionBlob
schema; someone removes the AtomType enum from the frontend mirror).

These tests run as part of the standard pytest suite and fail loud
if the substrate's canonical shape drifts.
"""

from __future__ import annotations

import os
import re

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)


def _read(rel_path: str) -> str:
    abs_path = os.path.join(_REPO_ROOT, rel_path)
    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()


def test_widget_definitions_validator_has_composition_blob_branch():
    """The validator MUST carry the additive composition_blob branch
    (legacy NULL path + composed path orchestration). Catches a
    hypothetical revert that drops the additive substrate."""
    source = _read(
        "backend/app/services/widget_definitions/validators.py"
    )
    # The additive branch is gated on composition_blob presence.
    assert "composition_blob" in source
    assert re.search(
        r"def\s+validate_widget_definition_write", source
    ), "top-level entry point missing"
    assert re.search(
        r"def\s+validate_composition_blob", source
    ), "composition-blob validator missing"
    # Phase 1 nesting cap + tier_scope vocabulary present.
    assert "_MAX_NESTING_DEPTH" in source
    assert "_VALID_TIER_SCOPES" in source


def test_pydantic_composition_schema_declares_composition_blob_class():
    """The Pydantic schema file MUST declare CompositionBlob +
    AtomNode + BindingRef + VariantDefinition. Catches accidental
    deletion / rename."""
    source = _read("backend/app/schemas/widget_composition.py")
    assert re.search(
        r"class\s+CompositionBlob\s*\(\s*BaseModel\s*\)", source
    )
    assert re.search(r"class\s+AtomNode\s*\(\s*BaseModel\s*\)", source)
    assert re.search(r"class\s+BindingRef\s*\(\s*BaseModel\s*\)", source)
    assert re.search(
        r"class\s+VariantDefinition\s*\(\s*BaseModel\s*\)", source
    )
    # 8 atom_types in the Phase 1 catalog.
    for atom_type in (
        "text_label",
        "value_display",
        "icon",
        "status_badge",
        "divider",
        "button",
        "image",
        "conditional_container",
    ):
        assert f'"{atom_type}"' in source, (
            f"AtomType vocabulary missing {atom_type!r}"
        )


def test_frontend_composition_blob_types_mirror_backend():
    """The frontend types file MUST declare the AtomType union with
    the same 8 Phase 1 atoms as the backend Pydantic Literal. Catches
    drift between Pydantic + TypeScript mirrors."""
    source = _read(
        "frontend/src/lib/widget-builder/types/composition-blob.ts"
    )
    assert "export type AtomType" in source
    # All 8 atom_types must appear as literal-union members.
    for atom_type in (
        "text_label",
        "value_display",
        "icon",
        "status_badge",
        "divider",
        "button",
        "image",
        "conditional_container",
    ):
        assert f'"{atom_type}"' in source, (
            f"frontend AtomType missing {atom_type!r}"
        )
    # Top-level shape interfaces.
    assert "export interface CompositionBlob" in source
    assert "export interface AtomNode" in source
    assert "export interface BindingRef" in source
    assert "export interface VariantDefinition" in source


def test_frontend_codec_module_exports_round_trip_helpers():
    """The codec MUST expose parseCompositionBlob +
    serializeCompositionBlob + CompositionBlobParseError. WB-2/WB-3
    rely on this surface."""
    source = _read(
        "frontend/src/lib/widget-builder/composition-blob-codec.ts"
    )
    assert "export function parseCompositionBlob" in source
    assert "export function serializeCompositionBlob" in source
    assert "export class CompositionBlobParseError" in source


def test_widget_definition_model_carries_wb1_columns():
    """The SQLAlchemy model MUST declare composition_blob,
    composition_version, tier_scope, and the 3 last_edit_session_*
    columns introduced by r105."""
    source = _read("backend/app/models/widget_definition.py")
    for column_name in (
        "composition_blob",
        "composition_version",
        "tier_scope",
        "last_edit_session_id",
        "last_edit_session_at",
        "last_edit_session_actor_id",
    ):
        assert column_name in source, (
            f"WidgetDefinition model missing column {column_name!r}"
        )


def test_r105_migration_anchored_at_r104():
    """The r105 migration MUST chain off r104. Catches an
    accidental rename / revision-id drift."""
    source = _read(
        "backend/alembic/versions/"
        "r105_widget_definitions_composition_extension.py"
    )
    assert 'revision = "r105_widget_definitions_composition_extension"' in source
    assert (
        'down_revision = "r104_migrate_focus_templates_to_freeform"'
        in source
    )
    # The CHECK constraint name must be stable.
    assert "ck_widget_definitions_composition_blob_version_paired" in source
