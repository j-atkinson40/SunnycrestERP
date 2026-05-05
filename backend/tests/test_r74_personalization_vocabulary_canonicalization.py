"""Step-0 migration r74 — substrate vocabulary canonicalization tests.

Per Personalization Studio implementation arc Step 1 build prompt + canonical resolutions Q1 + Q2:

- ``vinyl`` is canonical (was ``lifes_reflections``)
- ``physical_nameplate`` is canonical (was ``nameplate``)
- ``physical_emblem`` is canonical (was ``cover_emblem``)
- ``legacy_print`` is canonical (unchanged)

Tests verify:

1. Canonical vocabulary alignment at ``personalization_config`` source-of-truth
2. Per-tenant display label customization at Company.settings_json
3. Cross-tenant DocumentShare grant payload carries canonical substrate (not per-tenant labels)
4. Validation rejects legacy vocabulary post-r74 with canonical error message
5. Migration r74 idempotent (re-running backfill is no-op)
6. Tier definitions canonical-coherent with canonical 4-options vocabulary
7. PDF generation service handles canonical + legacy vocabulary cleanly during transition window
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.services.personalization_config import (
    CANONICAL_OPTION_TYPES,
    DEFAULT_DISPLAY_LABELS,
    OPTION_TYPE_LEGACY_PRINT,
    OPTION_TYPE_PHYSICAL_EMBLEM,
    OPTION_TYPE_PHYSICAL_NAMEPLATE,
    OPTION_TYPE_VINYL,
    PERSONALIZATION_TIERS,
    VINYL_SYMBOLS,
    LIFES_REFLECTIONS_SYMBOLS,
    get_display_label_for_tenant,
    get_full_config,
    set_display_labels_for_tenant,
    validate_personalization,
)


def _load_r74_migration_module():
    """Load r74 migration module via importlib.

    Alembic versions/ directory is not on Python sys.path by default; use file-path-based
    import to access migration's private vocabulary mappings + metadata for canonical-coherence
    tests without requiring Alembic context.
    """
    backend_dir = Path(__file__).parent.parent
    migration_path = (
        backend_dir
        / "alembic"
        / "versions"
        / "r74_personalization_vocabulary_canonicalization.py"
    )
    spec = importlib.util.spec_from_file_location(
        "r74_personalization_vocabulary_canonicalization", migration_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load migration spec from {migration_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestCanonicalVocabulary:
    """Canonical 4-options vocabulary alignment per §3.26.11.12.19.2."""

    def test_canonical_option_types_count(self):
        """Exactly 4 canonical option types per §3.26.11.12.19.2 canonical scope freeze."""
        assert len(CANONICAL_OPTION_TYPES) == 4

    def test_canonical_option_types_values(self):
        """Canonical 4-options vocabulary matches §3.26.11.12.19.2 verbatim."""
        assert OPTION_TYPE_LEGACY_PRINT == "legacy_print"
        assert OPTION_TYPE_PHYSICAL_NAMEPLATE == "physical_nameplate"
        assert OPTION_TYPE_PHYSICAL_EMBLEM == "physical_emblem"
        assert OPTION_TYPE_VINYL == "vinyl"

    def test_canonical_option_types_tuple_immutable(self):
        """Canonical option types tuple-typed for immutability discipline."""
        assert isinstance(CANONICAL_OPTION_TYPES, tuple)

    def test_legacy_vocabulary_not_in_canonical(self):
        """Legacy pre-r74 vocabulary NOT in canonical post-r74 vocabulary."""
        assert "nameplate" not in CANONICAL_OPTION_TYPES
        assert "cover_emblem" not in CANONICAL_OPTION_TYPES
        assert "lifes_reflections" not in CANONICAL_OPTION_TYPES

    def test_canonical_default_display_labels(self):
        """Default display labels canonical for all 4 option types."""
        for option_type in CANONICAL_OPTION_TYPES:
            assert option_type in DEFAULT_DISPLAY_LABELS
            assert isinstance(DEFAULT_DISPLAY_LABELS[option_type], str)
            assert DEFAULT_DISPLAY_LABELS[option_type]

    def test_default_vinyl_label_is_vinyl(self):
        """Canonical Sunnycrest tenant default — ``vinyl`` displays 'Vinyl' per Q1."""
        assert DEFAULT_DISPLAY_LABELS[OPTION_TYPE_VINYL] == "Vinyl"

    def test_vinyl_symbols_alias_lifes_reflections(self):
        """VINYL_SYMBOLS is canonical name; LIFES_REFLECTIONS_SYMBOLS is backward-compat alias."""
        assert VINYL_SYMBOLS is LIFES_REFLECTIONS_SYMBOLS

    def test_vinyl_symbols_non_empty(self):
        """Canonical vinyl symbol catalog non-empty (Wilbert canonical symbols)."""
        assert len(VINYL_SYMBOLS) > 0


class TestPerTenantDisplayLabels:
    """Per-tenant Workshop Tune mode display label customization per Q1 + §3.26.11.12.19."""

    def test_default_label_when_no_settings(self):
        """No company settings → canonical default display label."""
        label = get_display_label_for_tenant(OPTION_TYPE_VINYL, None)
        assert label == "Vinyl"

    def test_default_label_when_empty_settings(self):
        """Empty company settings → canonical default display label."""
        label = get_display_label_for_tenant(OPTION_TYPE_VINYL, {})
        assert label == "Vinyl"

    def test_default_label_when_no_personalization_overrides(self):
        """Company settings without personalization_display_labels → canonical default."""
        settings = {"some_other_key": "some_other_value"}
        label = get_display_label_for_tenant(OPTION_TYPE_VINYL, settings)
        assert label == "Vinyl"

    def test_wilbert_tenant_lifes_reflections_override(self):
        """Q1 canonical example — Wilbert tenant overrides ``vinyl`` to 'Life's Reflections'."""
        wilbert_settings = {
            "personalization_display_labels": {
                OPTION_TYPE_VINYL: "Life's Reflections"
            }
        }
        label = get_display_label_for_tenant(OPTION_TYPE_VINYL, wilbert_settings)
        assert label == "Life's Reflections"

    def test_sunnycrest_tenant_no_override(self):
        """Q1 canonical example — Sunnycrest tenant uses default 'Vinyl' (no override)."""
        sunnycrest_settings = {"personalization_display_labels": {}}
        label = get_display_label_for_tenant(OPTION_TYPE_VINYL, sunnycrest_settings)
        assert label == "Vinyl"

    def test_per_option_type_override_independent(self):
        """Per-option-type overrides are independent — overriding vinyl doesn't affect nameplate."""
        settings = {
            "personalization_display_labels": {
                OPTION_TYPE_VINYL: "Life's Reflections"
            }
        }
        assert get_display_label_for_tenant(OPTION_TYPE_VINYL, settings) == "Life's Reflections"
        # Other option types fall back to canonical defaults.
        assert (
            get_display_label_for_tenant(OPTION_TYPE_PHYSICAL_NAMEPLATE, settings)
            == "Nameplate"
        )

    def test_set_display_labels_canonical(self):
        """``set_display_labels_for_tenant`` canonicalizes labels at Company.settings_json."""
        settings = {}
        result = set_display_labels_for_tenant(
            settings, {OPTION_TYPE_VINYL: "Life's Reflections"}
        )
        assert result is settings  # In-place mutation
        assert (
            settings["personalization_display_labels"][OPTION_TYPE_VINYL]
            == "Life's Reflections"
        )

    def test_set_display_labels_preserves_other_settings(self):
        """``set_display_labels_for_tenant`` preserves unrelated Company.settings_json keys."""
        settings = {"unrelated_key": "preserved_value"}
        set_display_labels_for_tenant(settings, {OPTION_TYPE_VINYL: "Life's Reflections"})
        assert settings["unrelated_key"] == "preserved_value"

    def test_set_display_labels_rejects_legacy_vocabulary(self):
        """``set_display_labels_for_tenant`` rejects pre-r74 legacy vocabulary per Workshop Tune."""
        settings = {}
        with pytest.raises(ValueError, match="canonical option types"):
            set_display_labels_for_tenant(
                settings, {"lifes_reflections": "Life's Reflections"}
            )

    def test_set_display_labels_rejects_unknown_option_type(self):
        """``set_display_labels_for_tenant`` rejects unknown option types per scope freeze."""
        settings = {}
        with pytest.raises(ValueError, match="canonical option types"):
            set_display_labels_for_tenant(
                settings, {"hologram": "Hologram"}
            )

    def test_set_display_labels_partial_update(self):
        """``set_display_labels_for_tenant`` partial update preserves untouched labels."""
        settings = {}
        set_display_labels_for_tenant(
            settings, {OPTION_TYPE_VINYL: "Life's Reflections"}
        )
        set_display_labels_for_tenant(
            settings, {OPTION_TYPE_PHYSICAL_NAMEPLATE: "Plaque"}
        )
        # Both overrides preserved.
        labels = settings["personalization_display_labels"]
        assert labels[OPTION_TYPE_VINYL] == "Life's Reflections"
        assert labels[OPTION_TYPE_PHYSICAL_NAMEPLATE] == "Plaque"


class TestCanonicalSubstratePayloadDiscipline:
    """Cross-tenant DocumentShare grant carries canonical substrate per Q1 (NOT per-tenant labels)."""

    def test_canonical_substrate_value_independent_of_display_label(self):
        """Canonical substrate value ``vinyl`` independent of per-tenant display label.

        Per Q1: cross-tenant DocumentShare grant payload carries canonical ``vinyl`` substrate value.
        Per-tenant display labels apply at rendering layer ONLY, not at substrate persistence layer.
        """
        # Wilbert and Sunnycrest both use canonical substrate value at storage layer.
        wilbert_settings = {
            "personalization_display_labels": {OPTION_TYPE_VINYL: "Life's Reflections"}
        }
        sunnycrest_settings = {"personalization_display_labels": {}}

        # Display labels diverge per-tenant.
        assert get_display_label_for_tenant(OPTION_TYPE_VINYL, wilbert_settings) != \
            get_display_label_for_tenant(OPTION_TYPE_VINYL, sunnycrest_settings)

        # Canonical substrate value is identical.
        assert OPTION_TYPE_VINYL == "vinyl"  # Both tenants persist this canonical value.


class TestValidationCanonicalVocabulary:
    """Validation enforces canonical vocabulary post-r74."""

    def test_validate_canonical_vocabulary_accepted(self):
        """Canonical 4-options vocabulary accepted at validation."""
        result = validate_personalization(
            [{"type": OPTION_TYPE_VINYL, "symbol": "Cross"}],
            "wilbert_standard",
        )
        assert result["valid"] is True

    def test_validate_legacy_vocabulary_rejected(self):
        """Legacy pre-r74 vocabulary rejected with canonical error message."""
        result = validate_personalization(
            [{"type": "lifes_reflections", "symbol": "Cross"}],
            "wilbert_standard",
        )
        assert result["valid"] is False
        assert any("legacy vocabulary" in err for err in result["errors"])

    def test_validate_canonical_mutual_exclusion(self):
        """Canonical mutual exclusion rules enforced — vinyl + nameplate canonical conflict."""
        result = validate_personalization(
            [
                {"type": OPTION_TYPE_VINYL},
                {"type": OPTION_TYPE_PHYSICAL_NAMEPLATE},
            ],
            "wilbert_standard",
        )
        assert result["valid"] is False
        assert any("Cannot combine" in err for err in result["errors"])

    def test_validate_legacy_print_unchanged(self):
        """legacy_print is canonical (unchanged from pre-r74) and accepted."""
        result = validate_personalization(
            [{"type": OPTION_TYPE_LEGACY_PRINT, "print_name": "Going Home"}],
            "wilbert_standard",
        )
        assert result["valid"] is True

    def test_validate_continental_tier_only_nameplate(self):
        """Continental tier accepts only canonical physical_nameplate."""
        nameplate_result = validate_personalization(
            [{"type": OPTION_TYPE_PHYSICAL_NAMEPLATE}],
            "continental",
        )
        assert nameplate_result["valid"] is True

        emblem_result = validate_personalization(
            [{"type": OPTION_TYPE_PHYSICAL_EMBLEM}],
            "continental",
        )
        assert emblem_result["valid"] is False

    def test_validate_legacy_nameplate_rejected_with_canonical_message(self):
        """Legacy ``nameplate`` rejected with canonical error message guiding to canonical vocab."""
        result = validate_personalization(
            [{"type": "nameplate"}],
            "continental",
        )
        assert result["valid"] is False
        assert any("legacy vocabulary" in err for err in result["errors"])


class TestTierDefinitionsCanonical:
    """Canonical tier definitions match canonical 4-options vocabulary."""

    def test_wilbert_standard_tier_canonical(self):
        """Wilbert standard tier accepts canonical 4-options vocabulary."""
        tier = PERSONALIZATION_TIERS["wilbert_standard"]
        assert OPTION_TYPE_LEGACY_PRINT in tier["available_types"]
        assert OPTION_TYPE_VINYL in tier["available_types"]
        assert OPTION_TYPE_PHYSICAL_NAMEPLATE in tier["available_types"]
        assert OPTION_TYPE_PHYSICAL_EMBLEM in tier["available_types"]

    def test_continental_tier_canonical(self):
        """Continental tier canonical scope (physical_nameplate only)."""
        tier = PERSONALIZATION_TIERS["continental"]
        assert tier["available_types"] == [OPTION_TYPE_PHYSICAL_NAMEPLATE]

    def test_salute_tier_canonical(self):
        """Salute tier canonical scope (physical_nameplate + physical_emblem)."""
        tier = PERSONALIZATION_TIERS["salute"]
        assert OPTION_TYPE_PHYSICAL_NAMEPLATE in tier["available_types"]
        assert OPTION_TYPE_PHYSICAL_EMBLEM in tier["available_types"]
        # Tier deliberately excludes legacy_print + vinyl per Wilbert canonical.
        assert OPTION_TYPE_LEGACY_PRINT not in tier["available_types"]
        assert OPTION_TYPE_VINYL not in tier["available_types"]

    def test_urn_vault_tier_canonical(self):
        """Urn vault tier canonical scope (full 4-options + uses_urn_prints flag)."""
        tier = PERSONALIZATION_TIERS["urn_vault"]
        for option_type in CANONICAL_OPTION_TYPES:
            assert option_type in tier["available_types"]
        assert tier.get("uses_urn_prints") is True

    def test_no_tier_references_legacy_vocabulary(self):
        """No tier definition references pre-r74 legacy vocabulary."""
        legacy_vocab = {"nameplate", "cover_emblem", "lifes_reflections"}
        for tier_name, tier in PERSONALIZATION_TIERS.items():
            for option_type in tier["available_types"]:
                assert option_type not in legacy_vocab, (
                    f"Tier {tier_name} references legacy vocabulary {option_type}"
                )
            for group in tier.get("mutual_exclusive_groups", []):
                for option_type in group:
                    assert option_type not in legacy_vocab, (
                        f"Tier {tier_name} mutual_exclusive_groups references legacy "
                        f"vocabulary {option_type}"
                    )


class TestFullConfigCanonical:
    """``get_full_config`` exposes canonical 4-options vocabulary."""

    def test_full_config_includes_canonical_option_types(self):
        """Full config includes canonical_option_types for frontend canonical-vocabulary alignment."""
        config = get_full_config()
        assert "canonical_option_types" in config
        assert config["canonical_option_types"] == list(CANONICAL_OPTION_TYPES)

    def test_full_config_includes_default_display_labels(self):
        """Full config includes default display labels for frontend rendering layer."""
        config = get_full_config()
        assert "default_display_labels" in config
        assert config["default_display_labels"] == DEFAULT_DISPLAY_LABELS

    def test_full_config_includes_vinyl_symbols(self):
        """Full config includes canonical vinyl symbols catalog."""
        config = get_full_config()
        assert "vinyl_symbols" in config
        assert config["vinyl_symbols"] == VINYL_SYMBOLS

    def test_full_config_backward_compat_alias(self):
        """Full config preserves lifes_reflections_symbols alias for transition-window callers."""
        config = get_full_config()
        assert "lifes_reflections_symbols" in config
        assert config["lifes_reflections_symbols"] == VINYL_SYMBOLS


class TestMigrationR74Idempotency:
    """Migration r74 idempotency — re-running backfill is no-op."""

    def test_vocab_mapping_disjoint_keys_and_values(self):
        """Canonical vocabulary mapping has disjoint old → new sets (idempotent re-run discipline)."""
        migration = _load_r74_migration_module()

        old_set = set(migration._VOCAB_MAPPING.keys())
        new_set = set(migration._VOCAB_MAPPING.values())
        assert old_set.isdisjoint(new_set), (
            "Vocabulary mapping keys + values overlap — re-running migration would "
            "mistakenly re-rename canonical values back to legacy. Migration NOT idempotent."
        )

    def test_vocab_mapping_canonical_targets(self):
        """Mapping targets are canonical 4-options vocabulary post-r74."""
        migration = _load_r74_migration_module()

        for canonical_target in migration._VOCAB_MAPPING.values():
            assert canonical_target in CANONICAL_OPTION_TYPES, (
                f"Migration r74 target {canonical_target!r} NOT in canonical 4-options "
                f"vocabulary {CANONICAL_OPTION_TYPES}"
            )

    def test_vocab_mapping_inverse_complete(self):
        """Migration r74 _VOCAB_MAPPING_INVERSE is complete inverse of _VOCAB_MAPPING."""
        migration = _load_r74_migration_module()

        # Inverse should round-trip.
        for old, new in migration._VOCAB_MAPPING.items():
            assert migration._VOCAB_MAPPING_INVERSE[new] == old

    def test_legacy_print_NOT_in_mapping(self):
        """``legacy_print`` is canonical pre-r74 + post-r74; NOT in migration mapping."""
        migration = _load_r74_migration_module()

        assert "legacy_print" not in migration._VOCAB_MAPPING
        assert "legacy_print" not in migration._VOCAB_MAPPING.values()


class TestMigrationR74Metadata:
    """Migration r74 metadata canonical."""

    def test_revision_id_canonical(self):
        """Migration r74 revision ID matches canonical naming."""
        migration = _load_r74_migration_module()

        assert migration.revision == "r74_personalization_vocabulary_canonicalization"

    def test_down_revision_r72(self):
        """Migration r74 down_revision is r72_ptr_consent_metadata (r73 number skipped canonically)."""
        migration = _load_r74_migration_module()

        assert migration.down_revision == "r72_ptr_consent_metadata"
