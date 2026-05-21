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


def test_per_atom_config_schemas_covers_all_nine_phase_1_atoms():
    """The PER_ATOM_CONFIG_SCHEMAS lookup MUST cover every Phase 1
    atom_type. WB-2 atom inspector reads this dict; missing entries
    silently degrade UX.

    WB-3 expands the set to include `repeater_atom` — the iteration
    primitive for list-shaped widgets.
    """
    expected = {
        "text_label",
        "value_display",
        "icon",
        "status_badge",
        "divider",
        "button",
        "image",
        "conditional_container",
        "repeater_atom",
    }
    assert set(PER_ATOM_CONFIG_SCHEMAS.keys()) == expected


# ── WB-3 repeater_atom schema + validator coverage ────────────────────


def _repeater_blob_dict(*, with_repeater_child: bool = False) -> dict:
    """Helper — builds a minimal blob with a repeater_atom at root
    containing a single text_label per row. When `with_repeater_child=True`
    the row template ALSO contains a nested repeater_atom (validator
    should reject)."""
    atom_tree: dict = {
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
            "config": {},
        },
    }
    if with_repeater_child:
        atom_tree["row_label"] = {
            "atom_id": "row_label",
            "atom_type": "repeater_atom",
            "config": {
                "binding_id": "rows",
                "children": [],
                "direction": "column",
                "spacing": "normal",
            },
            "children": [],
            "binding_refs": {"rows": "rows"},
        }
        atom_tree["root"]["children"] = ["row_label"]
        atom_tree["root"]["config"]["children"] = ["row_label"]
    return {
        "schema_version": 1,
        "root_atom_id": "root",
        "atom_tree": atom_tree,
        "variants": [
            {
                "variant_id": "brief",
                "variant_name": "Brief",
                "target_surface": "focus_canvas",
            }
        ],
        "bindings_catalog": {
            "rows": {
                "binding_id": "rows",
                "binding_type": "field_path",
                "saved_view_id": "sv1",
                "field_path": "rows",
                "iteration_mode": "per_row",
            }
        },
    }


def test_repeater_atom_valid_blob_parses():
    """Valid repeater_atom blob parses + validates structurally + semantically."""
    from app.services.widget_definitions.validators import (
        validate_composition_blob,
    )

    blob_dict = _repeater_blob_dict()
    parsed = validate_composition_blob(blob_dict)
    assert parsed.root_atom_id == "root"
    assert parsed.atom_tree["root"].atom_type == "repeater_atom"


def test_repeater_atom_nested_repeater_rejected():
    """A repeater_atom whose subtree contains another repeater_atom
    must be rejected at validation time (Phase 1 cross-container
    nesting cap)."""
    from app.services.widget_definitions.validators import (
        CompositionBlobValidationError,
        validate_composition_blob,
    )

    blob_dict = _repeater_blob_dict(with_repeater_child=True)
    with pytest.raises(CompositionBlobValidationError) as excinfo:
        validate_composition_blob(blob_dict)
    assert any("repeater_atom may not contain" in e for e in excinfo.value.errors)


def test_repeater_atom_non_per_row_binding_rejected():
    """A repeater_atom binding_id pointing at a non-iteration binding
    must be rejected."""
    from app.services.widget_definitions.validators import (
        CompositionBlobValidationError,
        validate_composition_blob,
    )

    blob_dict = _repeater_blob_dict()
    blob_dict["bindings_catalog"]["rows"]["iteration_mode"] = "single_summary"
    with pytest.raises(CompositionBlobValidationError) as excinfo:
        validate_composition_blob(blob_dict)
    assert any("iteration_mode='per_row'" in e for e in excinfo.value.errors)


def test_repeater_atom_unknown_binding_id_rejected():
    """A repeater_atom binding_id pointing at a non-existent binding
    must be rejected."""
    from app.services.widget_definitions.validators import (
        CompositionBlobValidationError,
        validate_composition_blob,
    )

    blob_dict = _repeater_blob_dict()
    blob_dict["atom_tree"]["root"]["config"]["binding_id"] = "no-such-binding"
    with pytest.raises(CompositionBlobValidationError) as excinfo:
        validate_composition_blob(blob_dict)
    assert any("references unknown binding_id" in e for e in excinfo.value.errors)


def test_repeater_atom_config_children_mismatch_rejected():
    """When config.children and AtomNode.children disagree the
    validator rejects so the two views of the same data can't drift."""
    from app.services.widget_definitions.validators import (
        CompositionBlobValidationError,
        validate_composition_blob,
    )

    blob_dict = _repeater_blob_dict()
    blob_dict["atom_tree"]["root"]["config"]["children"] = ["different"]
    with pytest.raises(CompositionBlobValidationError) as excinfo:
        validate_composition_blob(blob_dict)
    assert any("config.children" in e for e in excinfo.value.errors)


def test_repeater_atom_config_pydantic_shape():
    """Pydantic schema rejects malformed RepeaterAtomConfig shapes."""
    from app.schemas.widget_composition import RepeaterAtomConfig

    # Valid baseline.
    cfg = RepeaterAtomConfig.model_validate(
        {"binding_id": "rows", "children": ["a", "b"]}
    )
    assert cfg.binding_id == "rows"
    assert cfg.spacing == "normal"

    # binding_id required.
    with pytest.raises(ValidationError):
        RepeaterAtomConfig.model_validate({"children": []})

    # spacing enum bounded.
    with pytest.raises(ValidationError):
        RepeaterAtomConfig.model_validate(
            {"binding_id": "rows", "children": [], "spacing": "extra-loose"}
        )

    # direction enum bounded.
    with pytest.raises(ValidationError):
        RepeaterAtomConfig.model_validate(
            {"binding_id": "rows", "children": [], "direction": "diagonal"}
        )


# ── WB-4b schema-extension + strict-validator tests ─────────────────


def _baseline_blob_with_atom(atom_type: str, config: dict, binding_refs=None):
    """Compose a minimal valid blob with the given leaf atom as child
    of a root conditional_container. Used by WB-4b required-field
    tightening tests."""
    atom_id = "leaf-1"
    blob = {
        "schema_version": 1,
        "root_atom_id": "root",
        "atom_tree": {
            "root": {
                "atom_id": "root",
                "atom_type": "conditional_container",
                "config": {"direction": "column"},
                "children": [atom_id],
            },
            atom_id: {
                "atom_id": atom_id,
                "atom_type": atom_type,
                "config": config,
            },
        },
        "variants": [],
        "bindings_catalog": {},
    }
    if binding_refs is not None:
        blob["atom_tree"][atom_id]["binding_refs"] = binding_refs
    return blob


# Schema-extension acceptance — new fields parse without error.


def test_wb4b_text_label_accepts_new_fields():
    from app.schemas.widget_composition import TextLabelConfig

    cfg = TextLabelConfig.model_validate(
        {
            "text": "Hello",
            "variant": "heading-2",
            "alignment": "center",
            "color": "accent",
            "max_lines": 2,
        }
    )
    assert cfg.text == "Hello"
    assert cfg.variant == "heading-2"
    assert cfg.alignment == "center"
    assert cfg.color == "accent"


def test_wb4b_text_label_legacy_fields_still_accepted():
    from app.schemas.widget_composition import TextLabelConfig

    cfg = TextLabelConfig.model_validate(
        {"typography_token": "body", "align": "left"}
    )
    assert cfg.typography_token == "body"
    assert cfg.align == "left"


def test_wb4b_value_display_accepts_new_fields():
    from app.schemas.widget_composition import ValueDisplayConfig

    cfg = ValueDisplayConfig.model_validate(
        {
            "format": "currency",
            "format_config": {"currency_code": "USD"},
            "variant": "body",
            "alignment": "end",
            "color": "default",
            "placeholder": "—",
            "binding_id": "amt",
        }
    )
    assert cfg.placeholder == "—"
    assert cfg.binding_id == "amt"


def test_wb4b_icon_accepts_stroke_width_and_semantic_color():
    from app.schemas.widget_composition import IconConfig

    cfg = IconConfig.model_validate(
        {"icon_name": "check", "stroke_width": 2.5, "color": "success"}
    )
    assert cfg.stroke_width == 2.5
    assert cfg.color == "success"


def test_wb4b_status_badge_accepts_label_variant_icon():
    from app.schemas.widget_composition import StatusBadgeConfig

    cfg = StatusBadgeConfig.model_validate(
        {"label": "Pending", "variant": "warning", "icon_name": "info"}
    )
    assert cfg.label == "Pending"
    assert cfg.variant == "warning"


def test_wb4b_divider_accepts_spacing_and_color():
    from app.schemas.widget_composition import DividerConfig

    cfg = DividerConfig.model_validate(
        {"orientation": "horizontal", "spacing": "loose", "color": "normal"}
    )
    assert cfg.spacing == "loose"
    assert cfg.color == "normal"


def test_wb4b_button_accepts_label_size_icon_destructive():
    from app.schemas.widget_composition import ButtonConfig

    cfg = ButtonConfig.model_validate(
        {
            "label": "Delete",
            "variant": "destructive",
            "size": "sm",
            "icon_name": "x",
            "action_kind": "mutate",
        }
    )
    assert cfg.label == "Delete"
    assert cfg.variant == "destructive"
    assert cfg.size == "sm"
    assert cfg.icon_name == "x"


def test_wb4b_image_accepts_src_alt_aspect_object_fit():
    from app.schemas.widget_composition import ImageConfig

    cfg = ImageConfig.model_validate(
        {
            "source_kind": "url",
            "src": "https://example.com/x.png",
            "alt": "X",
            "aspect_ratio_token": "video",
            "object_fit": "contain",
            "fallback_icon_name": "image",
        }
    )
    assert cfg.alt == "X"
    assert cfg.aspect_ratio_token == "video"


def test_wb4b_conditional_container_accepts_alignment():
    """Surprise-1 schema-extension: alignment field on
    ConditionalContainerConfig per the WB-4b investigation."""
    from app.schemas.widget_composition import ConditionalContainerConfig

    cfg = ConditionalContainerConfig.model_validate(
        {
            "direction": "row",
            "spacing": "compact",
            "alignment": "center",
        }
    )
    assert cfg.alignment == "center"
    assert cfg.spacing == "compact"
    # Default when omitted.
    cfg2 = ConditionalContainerConfig.model_validate({"direction": "column"})
    assert cfg2.alignment == "start"


def test_wb4b_conditional_container_alignment_enum_bounded():
    from app.schemas.widget_composition import ConditionalContainerConfig

    with pytest.raises(ValidationError):
        ConditionalContainerConfig.model_validate(
            {"direction": "column", "alignment": "diagonal"}
        )


# Strict-validator (Publish-gate) tests — required-field tightening.


def test_wb4b_strict_text_label_requires_text_or_binding():
    from app.services.widget_definitions.validators import (
        CompositionBlobValidationError,
        validate_composition_blob_strict,
    )

    blob_no_text = _baseline_blob_with_atom("text_label", {})
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob_strict(blob_no_text)
    assert any("text_label" in e and "text" in e for e in exc.value.errors)

    # Static text — OK.
    blob_static = _baseline_blob_with_atom("text_label", {"text": "Hi"})
    validate_composition_blob_strict(blob_static)


def test_wb4b_strict_button_requires_label_or_binding():
    from app.services.widget_definitions.validators import (
        CompositionBlobValidationError,
        validate_composition_blob_strict,
    )

    blob = _baseline_blob_with_atom("button", {"action_kind": "navigate"})
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob_strict(blob)
    assert any("button" in e and "label" in e for e in exc.value.errors)

    blob_ok = _baseline_blob_with_atom(
        "button", {"label": "Go", "action_kind": "navigate"}
    )
    validate_composition_blob_strict(blob_ok)


def test_wb4b_strict_status_badge_requires_label_or_binding():
    from app.services.widget_definitions.validators import (
        CompositionBlobValidationError,
        validate_composition_blob_strict,
    )

    blob = _baseline_blob_with_atom("status_badge", {})
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob_strict(blob)
    assert any("status_badge" in e for e in exc.value.errors)

    blob_ok = _baseline_blob_with_atom("status_badge", {"label": "Active"})
    validate_composition_blob_strict(blob_ok)


def test_wb4b_strict_image_requires_alt():
    from app.services.widget_definitions.validators import (
        CompositionBlobValidationError,
        validate_composition_blob_strict,
    )

    blob = _baseline_blob_with_atom(
        "image", {"source_kind": "url", "src": "x.png"}
    )
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob_strict(blob)
    assert any("image" in e and "alt" in e for e in exc.value.errors)

    blob_ok = _baseline_blob_with_atom(
        "image", {"source_kind": "url", "src": "x.png", "alt": "logo"}
    )
    validate_composition_blob_strict(blob_ok)


def test_wb4b_strict_value_display_requires_binding_or_binding_id():
    from app.services.widget_definitions.validators import (
        CompositionBlobValidationError,
        validate_composition_blob_strict,
    )

    blob = _baseline_blob_with_atom("value_display", {"format": "number"})
    with pytest.raises(CompositionBlobValidationError) as exc:
        validate_composition_blob_strict(blob)
    assert any("value_display" in e for e in exc.value.errors)

    blob_ok = _baseline_blob_with_atom(
        "value_display", {"format": "number", "binding_id": "amt"}
    )
    validate_composition_blob_strict(blob_ok)


def test_wb4b_strict_text_label_binding_satisfies_requirement():
    """A binding_refs.text entry pointing at a real binding satisfies
    the requirement even without a static config.text value."""
    from app.services.widget_definitions.validators import (
        validate_composition_blob_strict,
    )

    blob = _baseline_blob_with_atom(
        "text_label", {}, binding_refs={"text": "txt"}
    )
    blob["bindings_catalog"]["txt"] = {
        "binding_id": "txt",
        "binding_type": "literal",
        "literal_value": "Hi",
    }
    validate_composition_blob_strict(blob)


def test_wb4b_strict_accepts_valid_composition():
    """Smoke test — a fully-filled composition passes strict
    validation with no errors raised."""
    from app.services.widget_definitions.validators import (
        validate_composition_blob_strict,
    )

    blob = _baseline_blob_with_atom("text_label", {"text": "Hello"})
    result = validate_composition_blob_strict(blob)
    assert result.root_atom_id == "root"
