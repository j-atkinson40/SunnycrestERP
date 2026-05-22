"""WB-7 — ActionRef discriminated union + per-verb validator tests.

Covers:
  • Pydantic discriminated union parses all 5 variants.
  • Each variant requires its kind-specific fields (Pydantic catches
    "missing required field per kind" via the discriminator).
  • Strict validator enforces per-action_kind required fields.
  • Mutate verb narrowed to mutate_kind='anomaly_acknowledge' only.
  • current_row binding source rejected outside a repeater context.
  • Existing button validation (label requirement) unchanged.
  • action_ref legacy field accepts None but not strings.

The cross-side symmetry assertion is enforced by the parallel
TypeScript codec + AtomRenderer tests + ActionPicker tests; this
file is the BACKEND half of the WB-7 symmetry pair.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.widget_composition import (
    ButtonConfig,
    MutateActionRef,
    NavigateActionRef,
    OpenFocusActionRef,
    OpenPeekActionRef,
    ParameterBindingRef,
    TriggerWorkflowActionRef,
)
from app.services.widget_definitions.validators import (
    CompositionBlobValidationError,
    validate_composition_blob_strict,
)


def _base_blob(button_config: dict) -> dict:
    """A minimal blob with a single button atom for action tests."""
    return {
        "schema_version": 1,
        "root_atom_id": "root",
        "atom_tree": {
            "root": {
                "atom_id": "root",
                "atom_type": "conditional_container",
                "config": {"direction": "column"},
                "children": ["btn"],
            },
            "btn": {
                "atom_id": "btn",
                "atom_type": "button",
                "config": button_config,
            },
        },
        "variants": [],
        "bindings_catalog": {},
    }


def _blob_with_repeater(button_config: dict, view_id: str = "v1") -> dict:
    """Blob with a button atom inside a repeater_atom subtree."""
    return {
        "schema_version": 1,
        "root_atom_id": "root",
        "atom_tree": {
            "root": {
                "atom_id": "root",
                "atom_type": "conditional_container",
                "config": {"direction": "column"},
                "children": ["rep"],
            },
            "rep": {
                "atom_id": "rep",
                "atom_type": "repeater_atom",
                "config": {"binding_id": "rows-binding", "children": ["btn"]},
                "children": ["btn"],
            },
            "btn": {
                "atom_id": "btn",
                "atom_type": "button",
                "config": button_config,
            },
        },
        "variants": [],
        "bindings_catalog": {
            "rows-binding": {
                "binding_id": "rows-binding",
                "binding_type": "field_path",
                "saved_view_id": view_id,
                "field_path": "rows",
                "iteration_mode": "per_row",
            }
        },
    }


# ── Pydantic discriminated-union parse ─────────────────────────────


class TestActionRefVariants:
    def test_navigate_variant_parses(self) -> None:
        cfg = ButtonConfig(
            label="Go",
            action={"action_kind": "navigate", "href": "/cases/{id}"},
        )
        assert isinstance(cfg.action, NavigateActionRef)
        assert cfg.action.href == "/cases/{id}"

    def test_open_focus_variant_parses(self) -> None:
        cfg = ButtonConfig(
            label="Open",
            action={
                "action_kind": "open_focus",
                "focus_template_slug": "funeral-scheduling",
            },
        )
        assert isinstance(cfg.action, OpenFocusActionRef)
        assert cfg.action.focus_template_slug == "funeral-scheduling"

    def test_open_peek_variant_parses(self) -> None:
        cfg = ButtonConfig(
            label="Peek",
            action={
                "action_kind": "open_peek",
                "peek_view_type": "invoice",
            },
        )
        assert isinstance(cfg.action, OpenPeekActionRef)
        assert cfg.action.peek_view_type == "invoice"

    def test_trigger_workflow_variant_parses(self) -> None:
        cfg = ButtonConfig(
            label="Run",
            action={
                "action_kind": "trigger_workflow",
                "workflow_slug": "wf_sys_month_end_close",
                "confirm_before": True,
            },
        )
        assert isinstance(cfg.action, TriggerWorkflowActionRef)
        assert cfg.action.workflow_slug == "wf_sys_month_end_close"
        assert cfg.action.confirm_before is True

    def test_mutate_variant_parses(self) -> None:
        cfg = ButtonConfig(
            label="Ack",
            action={
                "action_kind": "mutate",
                "mutate_kind": "anomaly_acknowledge",
                "target_id_binding": {
                    "name": "anomaly_id",
                    "source": "current_row",
                    "row_field": "id",
                },
                "confirm_before": True,
            },
        )
        assert isinstance(cfg.action, MutateActionRef)
        assert cfg.action.mutate_kind == "anomaly_acknowledge"
        assert cfg.action.target_id_binding.row_field == "id"

    def test_malformed_action_kind_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ButtonConfig(
                label="X",
                action={"action_kind": "not_a_real_verb", "href": "/x"},
            )

    def test_missing_action_kind_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ButtonConfig(label="X", action={"href": "/x"})

    def test_navigate_missing_href_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ButtonConfig(label="X", action={"action_kind": "navigate"})

    def test_open_focus_missing_slug_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ButtonConfig(label="X", action={"action_kind": "open_focus"})

    def test_open_peek_missing_view_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ButtonConfig(label="X", action={"action_kind": "open_peek"})

    def test_open_peek_unknown_entity_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ButtonConfig(
                label="X",
                action={
                    "action_kind": "open_peek",
                    "peek_view_type": "not_a_real_entity",
                },
            )

    def test_trigger_workflow_missing_slug_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ButtonConfig(label="X", action={"action_kind": "trigger_workflow"})

    def test_mutate_missing_target_binding_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ButtonConfig(
                label="X",
                action={
                    "action_kind": "mutate",
                    "mutate_kind": "anomaly_acknowledge",
                },
            )

    def test_mutate_disallowed_kind_rejected_by_pydantic(self) -> None:
        # Pydantic catches at parse via Literal narrowing.
        with pytest.raises(ValidationError):
            ButtonConfig(
                label="X",
                action={
                    "action_kind": "mutate",
                    "mutate_kind": "delete_row",
                    "target_id_binding": {
                        "name": "id",
                        "source": "current_row",
                        "row_field": "id",
                    },
                },
            )


# ── ParameterBindingRef 8 sources ──────────────────────────────────


class TestParameterBindingSources:
    @pytest.mark.parametrize(
        "source",
        [
            "literal",
            "static",
            "route_param",
            "query_param",
            "focus_context",
            "tenant_context",
            "operator_context",
            "current_row",
        ],
    )
    def test_all_8_sources_parse(self, source: str) -> None:
        ref = ParameterBindingRef(name="x", source=source)
        assert ref.source == source

    def test_unknown_source_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ParameterBindingRef(name="x", source="totally_made_up")


# ── Strict validator: per-verb required fields ────────────────────


class TestStrictValidatorPerVerb:
    def test_navigate_missing_href_flagged_at_strict(self) -> None:
        # Build a blob where Pydantic accepts the dict shape because
        # the structural validator collects errors. We bypass by
        # putting the empty action in via a raw dict not via the
        # ButtonConfig constructor — Pydantic at strict would raise
        # too, but the strict validator surfaces a friendlier message.
        blob = _base_blob(
            {
                "label": "X",
                "action": {"action_kind": "navigate", "href": ""},
            }
        )
        with pytest.raises(CompositionBlobValidationError) as exc:
            validate_composition_blob_strict(blob)
        assert any("navigate action requires href" in e for e in exc.value.errors)

    def test_open_focus_empty_slug_flagged(self) -> None:
        blob = _base_blob(
            {
                "label": "X",
                "action": {
                    "action_kind": "open_focus",
                    "focus_template_slug": "",
                },
            }
        )
        with pytest.raises(CompositionBlobValidationError) as exc:
            validate_composition_blob_strict(blob)
        assert any(
            "focus_template_slug" in e for e in exc.value.errors
        )

    def test_trigger_workflow_empty_slug_flagged(self) -> None:
        blob = _base_blob(
            {
                "label": "X",
                "action": {
                    "action_kind": "trigger_workflow",
                    "workflow_slug": "",
                },
            }
        )
        with pytest.raises(CompositionBlobValidationError) as exc:
            validate_composition_blob_strict(blob)
        assert any("workflow_slug" in e for e in exc.value.errors)


# ── Mutate verb narrowing ──────────────────────────────────────────


class TestMutateNarrowing:
    def test_mutate_anomaly_acknowledge_accepted_inside_repeater(self) -> None:
        blob = _blob_with_repeater(
            {
                "label": "Ack",
                "action": {
                    "action_kind": "mutate",
                    "mutate_kind": "anomaly_acknowledge",
                    "target_id_binding": {
                        "name": "id",
                        "source": "current_row",
                        "row_field": "id",
                    },
                },
            }
        )
        # Validator should not flag mutate or current_row.
        try:
            validate_composition_blob_strict(blob)
        except CompositionBlobValidationError as exc:
            for e in exc.errors:
                assert "current_row" not in e
                assert "mutate_kind" not in e


# ── current_row context check ──────────────────────────────────────


class TestCurrentRowContext:
    def test_current_row_inside_repeater_is_valid(self) -> None:
        blob = _blob_with_repeater(
            {
                "label": "Open",
                "action": {
                    "action_kind": "open_peek",
                    "peek_view_type": "fh_case",
                    "initial_context": [
                        {
                            "name": "entity_id",
                            "source": "current_row",
                            "row_field": "id",
                        }
                    ],
                },
            }
        )
        try:
            validate_composition_blob_strict(blob)
        except CompositionBlobValidationError as exc:
            for e in exc.errors:
                assert "current_row" not in e

    def test_current_row_outside_repeater_is_rejected(self) -> None:
        blob = _base_blob(
            {
                "label": "Open",
                "action": {
                    "action_kind": "open_peek",
                    "peek_view_type": "fh_case",
                    "initial_context": [
                        {
                            "name": "entity_id",
                            "source": "current_row",
                            "row_field": "id",
                        }
                    ],
                },
            }
        )
        with pytest.raises(CompositionBlobValidationError) as exc:
            validate_composition_blob_strict(blob)
        assert any(
            "current_row" in e and "not inside a repeater" in e
            for e in exc.value.errors
        )


# ── Existing button label validation unchanged ─────────────────────


class TestExistingButtonValidationUnchanged:
    def test_button_without_label_or_binding_still_flagged(self) -> None:
        blob = _base_blob({"action": {"action_kind": "navigate", "href": "/x"}})
        with pytest.raises(CompositionBlobValidationError) as exc:
            validate_composition_blob_strict(blob)
        assert any(
            "button" in e.lower() and "label" in e for e in exc.value.errors
        )

    def test_button_with_label_and_action_clean(self) -> None:
        blob = _base_blob(
            {
                "label": "Go",
                "action": {"action_kind": "navigate", "href": "/x"},
            }
        )
        # Should NOT raise.
        validate_composition_blob_strict(blob)


# ── action_ref legacy field ────────────────────────────────────────


class TestActionRefLegacyField:
    def test_action_ref_none_accepted(self) -> None:
        cfg = ButtonConfig(label="X", action_ref=None)
        assert cfg.action_ref is None

    def test_action_ref_string_rejected(self) -> None:
        # Retired: typed Optional[None] only.
        with pytest.raises(ValidationError):
            ButtonConfig(label="X", action_ref="some-string")
