"""WB-8 — variant authoring substrate tests.

Covers:
  • default_variant_id referential integrity (Pydantic model_validator
    rejects unknown variant_id references; null is accepted).
  • Cross-surface compatibility helper (surface_mapping.py matrix +
    variant_target_compatible_with_supported_surfaces helper).
  • Authoring-time vs. Publish-time enforcement of Lock 3a rules.
  • Lock 3a.2 (spaces_pin → Glance required) + Lock 3a.3 (focus_canvas
    → Brief required when variants[] non-empty).
  • Backward-compat: composition_blobs without variants[] / without
    default_variant_id continue to parse + validate cleanly.

Cross-side symmetry with the TypeScript codec + frontend validator is
enforced by the parallel frontend tests; this file is the BACKEND
half of the WB-8 symmetry pair.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.widget_composition import CompositionBlob
from app.services.widget_definitions.surface_mapping import (
    TARGET_TO_WIDGET_SURFACES,
    check_atom_surface_compat,
    variant_target_compatible_with_supported_surfaces,
)
from app.services.widget_definitions.validators import (
    CompositionBlobValidationError,
    validate_composition_blob,
    validate_composition_blob_strict,
    validate_cross_surface_compatibility,
    validate_widget_definition_write,
)


def _minimal_blob(**overrides) -> dict:
    base = {
        "schema_version": 1,
        "root_atom_id": "root",
        "atom_tree": {
            "root": {
                "atom_id": "root",
                "atom_type": "conditional_container",
                "config": {"direction": "column"},
                "children": [],
            },
        },
        "variants": [],
        "bindings_catalog": {},
    }
    base.update(overrides)
    return base


# ── default_variant_id integrity ──────────────────────────────────────


class TestDefaultVariantIdIntegrity:
    def test_null_default_variant_id_is_accepted(self) -> None:
        blob = CompositionBlob.model_validate(_minimal_blob())
        assert blob.default_variant_id is None

    def test_absent_default_variant_id_defaults_to_none(self) -> None:
        # The field's optional/None default permits omission entirely.
        blob_dict = _minimal_blob()
        assert "default_variant_id" not in blob_dict
        blob = CompositionBlob.model_validate(blob_dict)
        assert blob.default_variant_id is None

    def test_default_variant_id_references_declared_variant(self) -> None:
        blob = CompositionBlob.model_validate(
            _minimal_blob(
                variants=[
                    {
                        "variant_id": "brief",
                        "variant_name": "Brief",
                        "target_surface": "focus_canvas",
                    },
                ],
                default_variant_id="brief",
            )
        )
        assert blob.default_variant_id == "brief"

    def test_default_variant_id_unknown_reference_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            CompositionBlob.model_validate(
                _minimal_blob(
                    variants=[
                        {
                            "variant_id": "brief",
                            "variant_name": "Brief",
                            "target_surface": "focus_canvas",
                        },
                    ],
                    default_variant_id="detail",
                )
            )
        assert "default_variant_id" in str(exc_info.value)

    def test_default_variant_id_with_empty_variants_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CompositionBlob.model_validate(
                _minimal_blob(default_variant_id="brief"),
            )


# ── Surface mapping + cross-vocabulary helpers ────────────────────────


class TestSurfaceMapping:
    def test_matrix_lists_all_three_target_surfaces(self) -> None:
        assert set(TARGET_TO_WIDGET_SURFACES.keys()) == {
            "focus_canvas",
            "page_canvas",
            "palette_preview",
        }

    def test_focus_canvas_maps_to_focus_surfaces(self) -> None:
        assert "focus_canvas" in TARGET_TO_WIDGET_SURFACES["focus_canvas"]
        assert "focus_stack" in TARGET_TO_WIDGET_SURFACES["focus_canvas"]

    def test_page_canvas_maps_to_page_surfaces(self) -> None:
        assert "pulse_grid" in TARGET_TO_WIDGET_SURFACES["page_canvas"]
        assert "dashboard_grid" in TARGET_TO_WIDGET_SURFACES["page_canvas"]

    def test_palette_preview_is_unscoped(self) -> None:
        # palette_preview should be compatible with the full
        # WidgetSurface enum.
        assert (
            "pulse_grid" in TARGET_TO_WIDGET_SURFACES["palette_preview"]
        )
        assert (
            "spaces_pin" in TARGET_TO_WIDGET_SURFACES["palette_preview"]
        )
        assert (
            "peek_inline" in TARGET_TO_WIDGET_SURFACES["palette_preview"]
        )

    def test_variant_compat_with_focus_canvas(self) -> None:
        assert variant_target_compatible_with_supported_surfaces(
            "focus_canvas", ["focus_canvas", "spaces_pin"]
        )
        # Pure spaces_pin without focus_canvas → not compatible.
        assert not variant_target_compatible_with_supported_surfaces(
            "focus_canvas", ["spaces_pin"]
        )

    def test_variant_compat_unknown_target_surface_passes(self) -> None:
        # Forward-compat: unknown target_surface → True.
        assert variant_target_compatible_with_supported_surfaces(
            "unknown_surface", ["focus_canvas"]
        )

    def test_check_atom_surface_compat_allowed_paths(self) -> None:
        assert check_atom_surface_compat(
            "text_label", "focus_canvas"
        ) == "allowed"
        assert check_atom_surface_compat(
            "button", "page_canvas"
        ) == "allowed"

    def test_check_atom_surface_compat_palette_preview_warnings(
        self,
    ) -> None:
        # Phase 1: palette_preview warns on repeater_atom + button.
        assert check_atom_surface_compat(
            "repeater_atom", "palette_preview"
        ) == "warned"
        assert check_atom_surface_compat(
            "button", "palette_preview"
        ) == "warned"
        # Other atoms are allowed at palette_preview.
        assert check_atom_surface_compat(
            "text_label", "palette_preview"
        ) == "allowed"

    def test_check_atom_surface_compat_unknown_inputs(self) -> None:
        # Forward-compat: unknown atom_kind / target_surface → allowed.
        assert check_atom_surface_compat(
            "new_atom", "focus_canvas"
        ) == "allowed"
        assert check_atom_surface_compat(
            "text_label", "new_surface"
        ) == "allowed"


# ── Cross-surface compatibility validation ────────────────────────────


class TestCrossSurfaceCompatibility:
    def test_no_issues_when_variants_compatible(self) -> None:
        blob = CompositionBlob.model_validate(
            _minimal_blob(
                variants=[
                    {
                        "variant_id": "brief",
                        "variant_name": "Brief",
                        "target_surface": "focus_canvas",
                    },
                ],
            )
        )
        issues = validate_cross_surface_compatibility(
            blob, ["focus_canvas"]
        )
        assert issues == []

    def test_pure_mismatch_issues_surfaced(self) -> None:
        # Variant targets focus_canvas; widget only supports
        # dashboard_grid → mismatch.
        blob = CompositionBlob.model_validate(
            _minimal_blob(
                variants=[
                    {
                        "variant_id": "brief",
                        "variant_name": "Brief",
                        "target_surface": "focus_canvas",
                    },
                ],
            )
        )
        issues = validate_cross_surface_compatibility(
            blob, ["dashboard_grid"]
        )
        assert any("incompatible" in i for i in issues)

    def test_lock_3a_2_spaces_pin_requires_glance(self) -> None:
        # spaces_pin in supported but no Glance variant → blocking.
        blob = CompositionBlob.model_validate(
            _minimal_blob(
                variants=[
                    {
                        "variant_id": "brief",
                        "variant_name": "Brief",
                        "target_surface": "focus_canvas",
                    },
                ],
            )
        )
        issues = validate_cross_surface_compatibility(
            blob, ["spaces_pin", "focus_canvas"]
        )
        assert any("Lock 3a.2" in i for i in issues)

    def test_lock_3a_3_focus_canvas_requires_brief(self) -> None:
        blob = CompositionBlob.model_validate(
            _minimal_blob(
                variants=[
                    {
                        "variant_id": "detail",
                        "variant_name": "Detail",
                        "target_surface": "focus_canvas",
                    },
                ],
            )
        )
        issues = validate_cross_surface_compatibility(
            blob, ["focus_canvas"]
        )
        assert any("Lock 3a.3" in i for i in issues)

    def test_lock_3a_3_does_not_fire_on_empty_variants(self) -> None:
        # Empty variants[] is the WB-1 initial state — Lock 3a.3 is
        # graceful per R10 mitigation.
        blob = CompositionBlob.model_validate(_minimal_blob())
        issues = validate_cross_surface_compatibility(
            blob, ["focus_canvas"]
        )
        assert not any("Lock 3a.3" in i for i in issues)

    def test_empty_supported_surfaces_no_issues(self) -> None:
        blob = CompositionBlob.model_validate(
            _minimal_blob(
                variants=[
                    {
                        "variant_id": "brief",
                        "variant_name": "Brief",
                        "target_surface": "focus_canvas",
                    },
                ],
            )
        )
        assert (
            validate_cross_surface_compatibility(blob, []) == []
        )
        assert (
            validate_cross_surface_compatibility(blob, None) == []
        )


# ── Publish-time enforcement (strict validator) ──────────────────────


class TestPublishTimeEnforcement:
    def _strict_blob(self) -> dict:
        # A passable strict-validation blob with a brief variant.
        return {
            "schema_version": 1,
            "root_atom_id": "root",
            "atom_tree": {
                "root": {
                    "atom_id": "root",
                    "atom_type": "conditional_container",
                    "config": {"direction": "column"},
                    "children": ["t"],
                },
                "t": {
                    "atom_id": "t",
                    "atom_type": "text_label",
                    "config": {"text": "hello"},
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

    def test_strict_passes_with_compatible_surfaces(self) -> None:
        validate_composition_blob_strict(
            self._strict_blob(),
            supported_surfaces=["focus_canvas"],
        )

    def test_strict_blocks_on_mismatch(self) -> None:
        with pytest.raises(CompositionBlobValidationError) as exc_info:
            validate_composition_blob_strict(
                self._strict_blob(),
                supported_surfaces=["dashboard_grid"],
            )
        assert any("incompatible" in e for e in exc_info.value.errors)

    def test_strict_blocks_spaces_pin_without_glance(self) -> None:
        with pytest.raises(CompositionBlobValidationError) as exc_info:
            validate_composition_blob_strict(
                self._strict_blob(),
                supported_surfaces=["spaces_pin", "focus_canvas"],
            )
        assert any("Lock 3a.2" in e for e in exc_info.value.errors)

    def test_strict_without_supported_surfaces_kwarg_skips_check(
        self,
    ) -> None:
        # Backward-compat: callers that don't pass supported_surfaces
        # still get the existing strict-required-field checks but skip
        # cross-surface compat.
        validate_composition_blob_strict(self._strict_blob())


# ── validate_widget_definition_write — orchestrator semantics ─────────


class TestOrchestratorBehavior:
    def test_lock_3a_2_blocks_draft_writes(self) -> None:
        payload = {
            "composition_blob": _minimal_blob(
                variants=[
                    {
                        "variant_id": "brief",
                        "variant_name": "Brief",
                        "target_surface": "focus_canvas",
                    },
                ],
            ),
            "composition_version": 1,
            "tier_scope": "vertical",
            "supported_surfaces": ["spaces_pin"],
        }
        with pytest.raises(CompositionBlobValidationError) as exc_info:
            validate_widget_definition_write(payload)
        assert any("Lock 3a.2" in e for e in exc_info.value.errors)

    def test_pure_target_surface_mismatch_does_not_block_draft(
        self,
    ) -> None:
        # Lock 3a Option B at draft — pure mismatches are SOFT.
        payload = {
            "composition_blob": _minimal_blob(
                variants=[
                    {
                        "variant_id": "brief",
                        "variant_name": "Brief",
                        "target_surface": "focus_canvas",
                    },
                ],
            ),
            "composition_version": 1,
            "tier_scope": "vertical",
            "supported_surfaces": ["dashboard_grid"],
        }
        # Should NOT raise — pure mismatch is authoring-time warn-only.
        validate_widget_definition_write(payload)

    def test_backward_compat_empty_variants_passes(self) -> None:
        payload = {
            "composition_blob": _minimal_blob(),
            "composition_version": 1,
            "tier_scope": "vertical",
            "supported_surfaces": ["focus_canvas"],
        }
        # Lock 3a.3 explicitly does NOT fire when variants[] is empty.
        validate_widget_definition_write(payload)

    def test_legacy_path_untouched(self) -> None:
        # composition_blob=None → legacy widget path; no checks.
        validate_widget_definition_write({})


# ── default_variant_id round-trip via validate_composition_blob ───────


class TestDefaultVariantIdRoundTrip:
    def test_round_trip_preserves_default_variant_id(self) -> None:
        blob = validate_composition_blob(
            _minimal_blob(
                variants=[
                    {
                        "variant_id": "brief",
                        "variant_name": "Brief",
                        "target_surface": "focus_canvas",
                    },
                ],
                default_variant_id="brief",
            )
        )
        assert blob.default_variant_id == "brief"

    def test_invalid_default_variant_id_surfaces_as_validation_error(
        self,
    ) -> None:
        with pytest.raises(CompositionBlobValidationError):
            validate_composition_blob(
                _minimal_blob(
                    variants=[
                        {
                            "variant_id": "brief",
                            "variant_name": "Brief",
                            "target_surface": "focus_canvas",
                        },
                    ],
                    default_variant_id="not_a_variant",
                )
            )
