"""Semantic validator tests for the WB-1 composition blob.

Exercises the cross-reference rules layered on top of the
Pydantic-schema structural pass: root_atom_id existence, atom_id
uniqueness, dangling children refs, Phase 1 nesting cap, binding-ref
integrity, variant-ref integrity, container-only-children invariant.

Also verifies the additive branch contract of
`validate_widget_definition_write`: composition_blob NULL → no-op
(legacy path unchanged); composition_blob populated → full
validation.
"""

from __future__ import annotations

import pytest

from app.services.widget_definitions.validators import (
    CompositionBlobValidationError,
    validate_composition_blob,
    validate_widget_definition_write,
)


def _minimal_valid_blob() -> dict:
    """A minimal blob: a single text_label root atom, one variant,
    no bindings."""
    return {
        "schema_version": 1,
        "root_atom_id": "a1",
        "atom_tree": {
            "a1": {
                "atom_id": "a1",
                "atom_type": "text_label",
                "config": {},
            },
        },
        "variants": [
            {
                "variant_id": "brief",
                "variant_name": "Brief",
                "target_surface": "focus_canvas",
            },
        ],
        "bindings_catalog": {},
    }


def test_minimal_valid_blob_passes():
    blob = validate_composition_blob(_minimal_valid_blob())
    assert blob.root_atom_id == "a1"


# ── Structural cross-reference rules ────────────────────────────────


def test_root_atom_id_must_exist_in_tree():
    raw = _minimal_valid_blob()
    raw["root_atom_id"] = "does-not-exist"
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob(raw)
    assert any("root_atom_id" in e for e in exc.value.errors)


def test_dangling_child_ref_rejected():
    raw = _minimal_valid_blob()
    raw["atom_tree"]["a1"] = {
        "atom_id": "a1",
        "atom_type": "conditional_container",
        "config": {"direction": "column"},
        "children": ["ghost"],
    }
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob(raw)
    assert any("unknown atom_id 'ghost'" in e for e in exc.value.errors)


def test_non_container_atom_cannot_have_children():
    raw = _minimal_valid_blob()
    raw["atom_tree"]["a1"] = {
        "atom_id": "a1",
        "atom_type": "text_label",
        "config": {},
        "children": ["a2"],
    }
    raw["atom_tree"]["a2"] = {
        "atom_id": "a2",
        "atom_type": "text_label",
        "config": {},
    }
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob(raw)
    assert any("cannot carry children" in e for e in exc.value.errors)


def test_phase_1_nesting_cap_two_levels():
    """A conditional_container holding a conditional_container as a
    child exceeds the 2-level nesting cap."""
    raw = {
        "schema_version": 1,
        "root_atom_id": "root",
        "atom_tree": {
            "root": {
                "atom_id": "root",
                "atom_type": "conditional_container",
                "config": {"direction": "column"},
                "children": ["nested"],
            },
            "nested": {
                "atom_id": "nested",
                "atom_type": "conditional_container",
                "config": {"direction": "row"},
                "children": ["leaf"],
            },
            "leaf": {
                "atom_id": "leaf",
                "atom_type": "text_label",
                "config": {},
            },
        },
        "variants": [],
        "bindings_catalog": {},
    }
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob(raw)
    assert any(
        "nesting depth" in e or "cannot carry children" in e
        for e in exc.value.errors
    )


def test_atom_id_mismatch_rejected():
    raw = _minimal_valid_blob()
    raw["atom_tree"]["a1"]["atom_id"] = "different"
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob(raw)
    assert any("atom_id mismatch" in e for e in exc.value.errors)


def test_unknown_variant_id_in_visible_in_variants():
    raw = _minimal_valid_blob()
    raw["atom_tree"]["a1"]["visible_in_variants"] = ["mystery"]
    with pytest.raises(Exception):  # Pydantic or service-layer
        validate_composition_blob(raw)


def test_unknown_binding_id_in_binding_refs():
    raw = _minimal_valid_blob()
    raw["atom_tree"]["a1"]["binding_refs"] = {"text": "no-such-binding"}
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob(raw)
    assert any(
        "unknown binding_id 'no-such-binding'" in e
        for e in exc.value.errors
    )


def test_binding_catalog_key_must_match_binding_id():
    raw = _minimal_valid_blob()
    raw["bindings_catalog"]["b1"] = {
        "binding_id": "MISMATCH",
        "binding_type": "literal",
        "literal_value": "x",
    }
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob(raw)
    assert any("binding_id mismatch" in e for e in exc.value.errors)


def test_invalid_per_atom_config_rejected():
    raw = _minimal_valid_blob()
    # icon requires icon_name; omitting it should fail per-atom-config check.
    raw["atom_tree"]["a1"] = {
        "atom_id": "a1",
        "atom_type": "icon",
        "config": {},  # missing required icon_name
    }
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob(raw)
    assert any(
        "icon_name" in e or "config" in e for e in exc.value.errors
    )


def test_validator_collects_multiple_errors_into_one_raise():
    """The validator surfaces ALL errors in a single raise, not one
    at a time. This matches the operator-actionable contract — one
    save attempt → full error list."""
    raw = _minimal_valid_blob()
    raw["root_atom_id"] = "ghost"
    raw["atom_tree"]["a1"]["binding_refs"] = {"text": "missing"}
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob(raw)
    # At minimum: missing-root + missing-binding errors both present.
    assert len(exc.value.errors) >= 2


# ── Top-level validate_widget_definition_write entry point ──────────


def test_legacy_path_no_op_when_blob_and_version_null():
    """Legacy hand-coded widget shape: both NULL. No validation
    fires (preserves pre-WB-1 write contract)."""
    payload = {
        "composition_blob": None,
        "composition_version": None,
    }
    # Must not raise.
    validate_widget_definition_write(payload)


def test_legacy_path_invokes_optional_callback():
    payload = {"composition_blob": None, "composition_version": None}
    called = {"n": 0}

    def legacy(payload):
        called["n"] += 1

    validate_widget_definition_write(payload, legacy_validator=legacy)
    assert called["n"] == 1


def test_one_populated_one_null_rejected():
    payload = {
        "composition_blob": _minimal_valid_blob(),
        "composition_version": None,
    }
    with pytest.raises(CompositionBlobValidationError):
        validate_widget_definition_write(payload)


def test_composition_version_must_be_one():
    payload = {
        "composition_blob": _minimal_valid_blob(),
        "composition_version": 2,
    }
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_widget_definition_write(payload)
    assert any("composition_version" in e for e in exc.value.errors)


def test_tier_scope_enum_enforced():
    payload = {
        "composition_blob": _minimal_valid_blob(),
        "composition_version": 1,
        "tier_scope": "tenant",
    }
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_widget_definition_write(payload)
    assert any("tier_scope" in e for e in exc.value.errors)


def test_composed_path_valid_blob_passes():
    payload = {
        "composition_blob": _minimal_valid_blob(),
        "composition_version": 1,
        "tier_scope": "platform",
    }
    validate_widget_definition_write(payload)


def test_composed_path_valid_blob_vertical_tier_passes():
    payload = {
        "composition_blob": _minimal_valid_blob(),
        "composition_version": 1,
        "tier_scope": "vertical",
    }
    validate_widget_definition_write(payload)
