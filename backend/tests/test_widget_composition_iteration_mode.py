"""WB-6 iteration_mode validator extension tests.

Tests the 5 bidirectional iteration_mode + binding-shape compatibility
checks added in `validators.validate_composition_blob_strict`.

  1. repeater_atom MUST use iteration_mode='per_row'
     (already enforced by structural validator — restated for context)
  2. iteration_mode='per_row' MUST be consumed by a repeater_atom
  3. value_display / text_label / icon / status_badge / button / image
     MUST use single_record OR single_summary (not per_row)
  4. binding_type='literal' MUST NOT carry iteration_mode
  5. Every field_path BindingRef MUST set iteration_mode +
     saved_view_id + non-empty field_path

Strict validator runs at Publish (per WB-4b Step 2). Draft state stays
permissive. These tests exercise the strict validator only.
"""

from __future__ import annotations

import pytest

from app.services.widget_definitions.validators import (
    CompositionBlobValidationError,
    validate_composition_blob,
    validate_composition_blob_strict,
)


# ── Helpers ─────────────────────────────────────────────────────────────


def _value_display_blob(
    *,
    binding_type: str = "field_path",
    iteration_mode: str | None = "single_record",
    saved_view_id: str | None = "sv1",
    field_path: str | None = "amount",
    literal_value=None,
) -> dict:
    """Minimal blob: root container with one value_display atom bound
    via `binding_refs.value` to a single binding."""
    return {
        "schema_version": 1,
        "root_atom_id": "root",
        "atom_tree": {
            "root": {
                "atom_id": "root",
                "atom_type": "conditional_container",
                "config": {"direction": "column"},
                "children": ["v1"],
            },
            "v1": {
                "atom_id": "v1",
                "atom_type": "value_display",
                "config": {"format": "currency", "format_config": {"currency_code": "USD"}},
                "binding_refs": {"value": "b1"},
            },
        },
        "variants": [
            {"variant_id": "brief", "variant_name": "Brief", "target_surface": "focus_canvas"}
        ],
        "bindings_catalog": {
            "b1": {
                "binding_id": "b1",
                "binding_type": binding_type,
                "saved_view_id": saved_view_id,
                "field_path": field_path,
                "iteration_mode": iteration_mode,
                "literal_value": literal_value,
            }
        },
    }


def _repeater_blob(
    *,
    iteration_mode: str | None = "per_row",
    saved_view_id: str | None = "sv1",
    field_path: str | None = "items",
) -> dict:
    return {
        "schema_version": 1,
        "root_atom_id": "root",
        "atom_tree": {
            "root": {
                "atom_id": "root",
                "atom_type": "repeater_atom",
                "config": {
                    "binding_id": "rows",
                    "children": ["row_label"],
                    "direction": "column",
                    "spacing": "normal",
                },
                "children": ["row_label"],
                "binding_refs": {"rows": "rows"},
            },
            "row_label": {
                "atom_id": "row_label",
                "atom_type": "text_label",
                "config": {"text": "Row"},
            },
        },
        "variants": [
            {"variant_id": "brief", "variant_name": "Brief", "target_surface": "focus_canvas"}
        ],
        "bindings_catalog": {
            "rows": {
                "binding_id": "rows",
                "binding_type": "field_path",
                "saved_view_id": saved_view_id,
                "field_path": field_path,
                "iteration_mode": iteration_mode,
            }
        },
    }


# ── Check 1: repeater_atom requires per_row (structural; restated) ─────


def test_check_1_repeater_with_per_row_passes():
    blob = _repeater_blob(iteration_mode="per_row")
    validate_composition_blob_strict(blob)  # no raise


def test_check_1_repeater_with_single_record_rejected():
    blob = _repeater_blob(iteration_mode="single_record")
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob_strict(blob)
    assert any("iteration_mode='per_row'" in e for e in exc.value.errors)


# ── Check 2: per_row bindings must be consumed by a repeater_atom ──────


def test_check_2_orphan_per_row_binding_rejected():
    """A per_row binding NOT consumed by any repeater_atom is rejected."""
    blob = _value_display_blob(iteration_mode="per_row")
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob_strict(blob)
    # Either (or both) of the WB-6 messages fires; both indicate the
    # same misuse. We assert SOMETHING fires.
    msgs = exc.value.errors
    assert any(
        "per_row binding must be consumed by a repeater_atom" in e
        or "must use iteration_mode='single_record' or 'single_summary'" in e
        for e in msgs
    )


def test_check_2_per_row_inside_repeater_passes():
    """Per_row binding consumed by a repeater_atom — valid."""
    blob = _repeater_blob(iteration_mode="per_row")
    validate_composition_blob_strict(blob)  # no raise


# ── Check 3: leaf atoms must use single_record / single_summary ────────


def test_check_3_value_display_with_per_row_rejected():
    blob = _value_display_blob(iteration_mode="per_row")
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob_strict(blob)
    assert any(
        "must use iteration_mode='single_record' or 'single_summary'" in e
        for e in exc.value.errors
    )


def test_check_3_value_display_with_single_summary_passes():
    blob = _value_display_blob(iteration_mode="single_summary")
    validate_composition_blob_strict(blob)


def test_check_3_value_display_with_single_record_passes():
    blob = _value_display_blob(iteration_mode="single_record")
    validate_composition_blob_strict(blob)


# ── Check 4: literal bindings must NOT carry iteration_mode ────────────


def test_check_4_literal_with_iteration_mode_rejected():
    """Literal binding with iteration_mode set — rejected (literal +
    iteration semantics are mutually exclusive)."""
    blob = _value_display_blob(
        binding_type="literal",
        iteration_mode="single_record",
        saved_view_id=None,
        field_path=None,
        literal_value="X",
    )
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob_strict(blob)
    assert any(
        "literal bindings must not carry iteration_mode" in e
        for e in exc.value.errors
    )


def test_check_4_literal_without_iteration_mode_passes():
    """Literal binding without iteration_mode — valid (backward-compat
    preserved per Area 4 lock)."""
    blob = _value_display_blob(
        binding_type="literal",
        iteration_mode=None,
        saved_view_id=None,
        field_path=None,
        literal_value=42,
    )
    validate_composition_blob_strict(blob)


# ── Check 5: field_path requires iteration_mode + saved_view_id +
#    non-empty field_path ──────────────────────────────────────────────


def test_check_5_field_path_without_iteration_mode_rejected():
    blob = _value_display_blob(iteration_mode=None)
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob_strict(blob)
    assert any(
        "field_path binding requires iteration_mode" in e
        for e in exc.value.errors
    )


def test_check_5_field_path_without_saved_view_id_rejected():
    blob = _value_display_blob(saved_view_id=None)
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob_strict(blob)
    assert any(
        "non-empty saved_view_id" in e
        for e in exc.value.errors
    )


def test_check_5_field_path_with_empty_field_path_rejected():
    blob = _value_display_blob(field_path="")
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob_strict(blob)
    assert any(
        "non-empty field_path" in e
        for e in exc.value.errors
    )


def test_check_5_well_formed_field_path_passes():
    blob = _value_display_blob(
        iteration_mode="single_record",
        saved_view_id="sv1",
        field_path="amount",
    )
    validate_composition_blob_strict(blob)


# ── Draft state stays permissive (validate_composition_blob) ───────────


def test_draft_permissive_orphan_per_row_passes_loose_validator():
    """Loose (draft) validator does NOT enforce the WB-6 checks.

    Operator authoring mid-binding mustn't be hard-blocked. Strict
    gate runs at Publish only.
    """
    blob = _value_display_blob(iteration_mode="per_row")
    # Loose validator — fine.
    validate_composition_blob(blob)


def test_draft_permissive_literal_with_iteration_mode_passes_loose_validator():
    """Loose validator does NOT reject literal+iteration_mode either.

    Defers all binding-shape policing to the strict gate.
    """
    blob = _value_display_blob(
        binding_type="literal",
        iteration_mode="single_record",
        saved_view_id=None,
        field_path=None,
        literal_value="X",
    )
    validate_composition_blob(blob)


# ── Existing WB-4b validator substrate continues working ───────────────


def test_existing_wb4b_image_alt_check_still_fires():
    """Pre-WB-6 strict check (image requires alt) still fires alongside
    the new WB-6 checks."""
    blob = {
        "schema_version": 1,
        "root_atom_id": "root",
        "atom_tree": {
            "root": {
                "atom_id": "root",
                "atom_type": "conditional_container",
                "config": {"direction": "column"},
                "children": ["img"],
            },
            "img": {
                "atom_id": "img",
                "atom_type": "image",
                "config": {"source_kind": "url"},
            },
        },
        "variants": [],
        "bindings_catalog": {},
    }
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob_strict(blob)
    assert any("alt" in e for e in exc.value.errors)
