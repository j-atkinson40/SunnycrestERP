"""Pydantic schema tests for the WB-1 composition blob.

Canonical example exercise + per-atom-type Phase 1 config validation
+ structural error enumeration. Cross-side parity with the
TypeScript codec at
`frontend/src/lib/widget-builder/composition-blob-codec.ts` is tested
via the parity fixture (same JSON bytes parse on both sides).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.widget_composition import (
    PER_ATOM_CONFIG_SCHEMAS,
    AtomNode,
    BindingRef,
    ButtonConfig,
    CompositionBlob,
    ConditionalContainerConfig,
    DividerConfig,
    IconConfig,
    ImageConfig,
    StatusBadgeConfig,
    TextLabelConfig,
    ValueDisplayConfig,
    VariantDefinition,
)


# ── Canonical example ───────────────────────────────────────────────


def _canonical_example_dict() -> dict:
    """A canonical Phase 1 composition exercising all 8 atom_types,
    a 2-level conditional container, two variants, and a small
    bindings_catalog.
    """
    return {
        "schema_version": 1,
        "root_atom_id": "root",
        "atom_tree": {
            "root": {
                "atom_id": "root",
                "atom_type": "conditional_container",
                "config": {"direction": "column", "gap_token": "sm"},
                "children": [
                    "title",
                    "icon",
                    "value",
                    "status",
                    "divider",
                    "btn",
                    "img",
                ],
                "binding_refs": {"condition": "b-cond"},
            },
            "title": {
                "atom_id": "title",
                "atom_type": "text_label",
                "config": {"typography_token": "h3", "align": "left"},
                "visible_in_variants": ["brief", "detail", "deep"],
                "binding_refs": {"text": "b-driver-name"},
            },
            "icon": {
                "atom_id": "icon",
                "atom_type": "icon",
                "config": {"icon_name": "Truck", "size_token": "md"},
            },
            "value": {
                "atom_id": "value",
                "atom_type": "value_display",
                "config": {"format": "currency", "format_config": {"currency": "USD"}},
                "binding_refs": {"value": "b-revenue"},
            },
            "status": {
                "atom_id": "status",
                "atom_type": "status_badge",
                "config": {
                    "status_map": {"open": "warning", "closed": "success"},
                    "show_icon": True,
                },
            },
            "divider": {
                "atom_id": "divider",
                "atom_type": "divider",
                "config": {"orientation": "horizontal"},
            },
            "btn": {
                "atom_id": "btn",
                "atom_type": "button",
                "config": {
                    "action_kind": "navigate",
                    "action_config": {"url": "/deliveries"},
                    "variant": "secondary",
                },
            },
            "img": {
                "atom_id": "img",
                "atom_type": "image",
                "config": {"source_kind": "url", "fit": "cover"},
            },
        },
        "variants": [
            {
                "variant_id": "brief",
                "variant_name": "Brief",
                "target_surface": "focus_canvas",
                "canonical_dimensions": {"width": 320, "height": 200},
            },
            {
                "variant_id": "detail",
                "variant_name": "Detail",
                "target_surface": "page_canvas",
            },
        ],
        "bindings_catalog": {
            "b-cond": {
                "binding_id": "b-cond",
                "binding_type": "literal",
                "literal_value": True,
            },
            "b-driver-name": {
                "binding_id": "b-driver-name",
                "binding_type": "field_path",
                "saved_view_id": "view-deliveries",
                "field_path": "delivery.driver_name",
                "iteration_mode": "per_row",
            },
            "b-revenue": {
                "binding_id": "b-revenue",
                "binding_type": "field_path",
                "saved_view_id": "view-deliveries",
                "field_path": "delivery.invoice_total",
                "iteration_mode": "per_row",
            },
        },
    }


def test_canonical_example_parses_cleanly():
    blob = CompositionBlob.model_validate(_canonical_example_dict())
    assert blob.schema_version == 1
    assert blob.root_atom_id == "root"
    assert len(blob.atom_tree) == 8
    # All 8 atom_types from the Phase 1 catalog present.
    types_present = {n.atom_type for n in blob.atom_tree.values()}
    expected = {
        "conditional_container",
        "text_label",
        "icon",
        "value_display",
        "status_badge",
        "divider",
        "button",
        "image",
    }
    assert types_present == expected
    assert len(blob.variants) == 2
    assert len(blob.bindings_catalog) == 3


# ── Pydantic-side structural errors ─────────────────────────────────


def test_schema_version_must_be_one():
    raw = _canonical_example_dict()
    raw["schema_version"] = 2
    with pytest.raises(ValidationError) as exc_info:
        CompositionBlob.model_validate(raw)
    assert any(
        "schema_version" in str(e.get("loc", ""))
        or "Literal" in str(e.get("msg", ""))
        for e in exc_info.value.errors()
    )


def test_atom_type_outside_phase_1_catalog_rejected():
    raw = _canonical_example_dict()
    raw["atom_tree"]["title"]["atom_type"] = "spark_line"
    with pytest.raises(ValidationError):
        CompositionBlob.model_validate(raw)


def test_target_surface_outside_phase_1_rejected():
    raw = _canonical_example_dict()
    raw["variants"][0]["target_surface"] = "unicorn_surface"
    with pytest.raises(ValidationError):
        CompositionBlob.model_validate(raw)


def test_binding_type_outside_phase_1_rejected():
    raw = _canonical_example_dict()
    raw["bindings_catalog"]["b-cond"]["binding_type"] = "expression"
    with pytest.raises(ValidationError):
        CompositionBlob.model_validate(raw)


def test_iteration_mode_outside_phase_1_rejected():
    raw = _canonical_example_dict()
    raw["bindings_catalog"]["b-driver-name"]["iteration_mode"] = "stream"
    with pytest.raises(ValidationError):
        CompositionBlob.model_validate(raw)


def test_extra_fields_forbidden_on_atom():
    bad = {
        "atom_id": "x",
        "atom_type": "text_label",
        "config": {},
        "unexpected_field": "boo",
    }
    with pytest.raises(ValidationError):
        AtomNode.model_validate(bad)


def test_extra_fields_forbidden_on_blob():
    raw = _canonical_example_dict()
    raw["unexpected_top_level_field"] = True
    with pytest.raises(ValidationError):
        CompositionBlob.model_validate(raw)


def test_extra_fields_forbidden_on_variant():
    bad = {
        "variant_id": "x",
        "variant_name": "X",
        "target_surface": "focus_canvas",
        "rogue": 1,
    }
    with pytest.raises(ValidationError):
        VariantDefinition.model_validate(bad)


def test_extra_fields_forbidden_on_binding_ref():
    bad = {
        "binding_id": "x",
        "binding_type": "literal",
        "rogue": 1,
    }
    with pytest.raises(ValidationError):
        BindingRef.model_validate(bad)


# ── Per-atom-type config schemas ─────────────────────────────────────


def test_text_label_config_required_minimum():
    """All Phase 1 config classes accept an empty dict — defaults
    cover every field. This exercises the "no required fields"
    contract that lets WB-3 author atoms with zero-config first."""
    TextLabelConfig.model_validate({})


def test_value_display_config_format_must_be_known():
    with pytest.raises(ValidationError):
        ValueDisplayConfig.model_validate({"format": "gibberish"})


def test_icon_config_requires_icon_name():
    with pytest.raises(ValidationError):
        IconConfig.model_validate({})  # icon_name is required


def test_icon_config_accepts_canonical():
    IconConfig.model_validate({"icon_name": "Truck"})


def test_status_badge_config_defaults():
    cfg = StatusBadgeConfig.model_validate({})
    assert cfg.show_icon is True
    assert cfg.status_map == {}


def test_divider_config_orientation_enum():
    with pytest.raises(ValidationError):
        DividerConfig.model_validate({"orientation": "diagonal"})


def test_button_config_action_kind_bounded():
    with pytest.raises(ValidationError):
        ButtonConfig.model_validate({"action_kind": "destroy"})


def test_image_config_source_kind_enum():
    with pytest.raises(ValidationError):
        ImageConfig.model_validate({"source_kind": "ftp"})


def test_conditional_container_config_direction_enum():
    with pytest.raises(ValidationError):
        ConditionalContainerConfig.model_validate({"direction": "diagonal"})


def test_per_atom_config_schemas_covers_all_eight_phase_1_atoms():
    """The PER_ATOM_CONFIG_SCHEMAS lookup MUST cover every Phase 1
    atom_type. WB-2 atom inspector reads this dict; missing entries
    silently degrade UX."""
    expected = {
        "text_label",
        "value_display",
        "icon",
        "status_badge",
        "divider",
        "button",
        "image",
        "conditional_container",
    }
    assert set(PER_ATOM_CONFIG_SCHEMAS.keys()) == expected
