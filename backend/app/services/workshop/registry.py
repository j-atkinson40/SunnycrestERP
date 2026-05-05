"""Workshop template-type registry — Phase 1D pattern-establisher.

Per BRIDGEABLE_MASTER §3.26.14 Workshop primitive canon + §3.26.11.12.9
Workshop integration mechanics: this module is the canonical Workshop
template-type registry (templates-as-data discipline).

**Pattern-establisher discipline**: Phase 1D registers
``burial_vault_personalization_studio`` as the first template-type.
Subsequent registrations (Step 2 ``urn_vault_personalization_studio``;
future Wall Designer / Drawing Takeoff / Audit Prep generator etc. per
§3.26.11.12 strategic vision) call ``register_template_type`` from
their own seed paths with no changes to this module.

**Storage model**: in-code module-level singleton mirroring
``vault.hub_registry`` + ``command_bar.registry`` + ``triage.platform_defaults``
precedents. Lazy-seeded on first access.

**Anti-pattern guards**:

- §2.4.4 Anti-pattern 8 (vertical-specific code creep) — registry
  carries ``applicable_verticals`` filter as data; vertical-specific
  behavior dispatched at consumer level via filter, not via
  vertical-specific registry forks.
- §3.26.11.12.16 Anti-pattern 4 (primitive count expansion against
  fifth Focus type rejected) — registry holds Generation Focus
  template-type entries; does NOT introduce new Focus type. Each
  template_type discriminator entry corresponds to a Generation
  Focus instance variant per §3.26.11.12.20 single-entity-with-
  discriminator meta-pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────────────
# Canonical authoring_context vocabulary per §3.26.11.12.19.3 Q3.
# Mirrors ``app.models.generation_focus_instance.CANONICAL_AUTHORING_CONTEXTS``
# but kept canonical at this module so registry consumers don't need to
# import the model layer.
# ─────────────────────────────────────────────────────────────────────


CANONICAL_AUTHORING_CONTEXTS: tuple[str, ...] = (
    "funeral_home_with_family",
    "manufacturer_without_family",
    "manufacturer_from_fh_share",
)


@dataclass
class TemplateTypeDescriptor:
    """One Workshop template-type registry entry.

    Each registered descriptor corresponds to a Generation Focus
    template per §3.26.11.12.20 single-entity-with-discriminator
    meta-pattern. The ``template_type`` value matches
    ``GenerationFocusInstance.template_type`` discriminator + the
    ``Document.document_type`` discriminator at canonical Document
    substrate consumption per §3.26.11.12.5.

    **Fields**:

    - ``template_type`` — discriminator value canonical at substrate +
      service layer; e.g. ``burial_vault_personalization_studio``.
    - ``display_name`` — operator-facing name shown in Workshop chrome.
    - ``description`` — operator-facing description.
    - ``applicable_verticals`` — list of Company.vertical values where
      this template-type surfaces. ``["*"]`` = cross-vertical.
    - ``applicable_authoring_contexts`` — subset of canonical 3
      authoring contexts where this template-type permits instance
      creation. Empty = all 3 permitted.
    - ``empty_canvas_state_factory_key`` — opaque key resolved by the
      consumer (``personalization_studio.instance_service._empty_canvas_state``)
      to construct a fresh canvas state. Decouples registry from
      service layer; enables registry-only tests.
    - ``tune_mode_dimensions`` — list of Tune mode dimensions exposed
      for per-tenant configuration. Each dimension key resolves to a
      tenant_config field. Empty = template-type permits no Tune mode
      customization (Tune mode UI hides per §14.14.1 chrome canon).
    - ``sort_order`` — display order in Workshop chrome.

    Anti-pattern guard: ``applicable_verticals`` is data, not code —
    Anti-pattern 8 (vertical-specific code creep) is structurally
    avoided at registry substrate.
    """

    template_type: str
    display_name: str
    description: str
    applicable_verticals: list[str] = field(default_factory=lambda: ["*"])
    applicable_authoring_contexts: list[str] = field(default_factory=list)
    empty_canvas_state_factory_key: str = ""
    tune_mode_dimensions: list[str] = field(default_factory=list)
    sort_order: int = 100


# ─────────────────────────────────────────────────────────────────────
# Module-level singleton + idempotent seed
# ─────────────────────────────────────────────────────────────────────


_registry: dict[str, TemplateTypeDescriptor] = {}
_seeded: bool = False


def register_template_type(descriptor: TemplateTypeDescriptor) -> None:
    """Register or replace a template-type by ``template_type`` key.

    Replacement is intentional — extensions and test code can override
    core registrations by registering with the same key (mirrors
    vault.hub_registry pattern).
    """
    if descriptor.applicable_authoring_contexts:
        for ctx in descriptor.applicable_authoring_contexts:
            if ctx not in CANONICAL_AUTHORING_CONTEXTS:
                raise ValueError(
                    f"applicable_authoring_contexts contains {ctx!r} which is "
                    f"not in canonical {CANONICAL_AUTHORING_CONTEXTS}. "
                    f"Anti-pattern guard at registry substrate per "
                    f"§3.26.11.12.19.3 Q3."
                )
    _registry[descriptor.template_type] = descriptor


def list_template_types(
    *,
    vertical: str | None = None,
) -> list[TemplateTypeDescriptor]:
    """Return registered template-types ordered by ``sort_order`` then
    ``template_type`` for stable ties.

    When ``vertical`` is provided, filters to descriptors whose
    ``applicable_verticals`` includes the value or contains ``"*"``.
    """
    _ensure_seeded()
    descriptors = sorted(
        _registry.values(),
        key=lambda d: (d.sort_order, d.template_type),
    )
    if vertical is None:
        return descriptors
    return [
        d
        for d in descriptors
        if "*" in d.applicable_verticals or vertical in d.applicable_verticals
    ]


def get_template_type(template_type: str) -> TemplateTypeDescriptor | None:
    _ensure_seeded()
    return _registry.get(template_type)


def reset_registry() -> None:
    """Test-only — clear the registry and mark it unseeded."""
    global _seeded
    _registry.clear()
    _seeded = False


def _ensure_seeded() -> None:
    global _seeded
    if _seeded:
        return
    _seed_default_template_types()
    _seeded = True


# ─────────────────────────────────────────────────────────────────────
# Phase 1D pattern-establisher seed
# ─────────────────────────────────────────────────────────────────────


# Tune mode dimension keys shared across canonical Personalization
# Studio category templates (Burial Vault + Urn Vault). Per
# §3.26.11.12.19.6 scope freeze, urn vault inherits canonical 4-options
# vocabulary at category scope; Tune mode dimensions parallel.
TUNE_DIMENSION_DISPLAY_LABELS = "display_labels"
TUNE_DIMENSION_EMBLEM_CATALOG = "emblem_catalog"
TUNE_DIMENSION_FONT_CATALOG = "font_catalog"
TUNE_DIMENSION_LEGACY_PRINT_CATALOG = "legacy_print_catalog"


CANONICAL_TUNE_DIMENSIONS_BURIAL_VAULT: tuple[str, ...] = (
    TUNE_DIMENSION_DISPLAY_LABELS,
    TUNE_DIMENSION_EMBLEM_CATALOG,
    TUNE_DIMENSION_FONT_CATALOG,
    TUNE_DIMENSION_LEGACY_PRINT_CATALOG,
)


# Step 2 substrate-consumption-follower: urn vault inherits same Tune
# mode dimensions per §3.26.11.12.19.6 scope freeze (Personalization
# Studio category-scope canonical 4-options vocabulary applies to all
# canonical templates).
CANONICAL_TUNE_DIMENSIONS_URN_VAULT: tuple[str, ...] = (
    TUNE_DIMENSION_DISPLAY_LABELS,
    TUNE_DIMENSION_EMBLEM_CATALOG,
    TUNE_DIMENSION_FONT_CATALOG,
    TUNE_DIMENSION_LEGACY_PRINT_CATALOG,
)


def _seed_default_template_types() -> None:
    """Phase 1D pattern-establisher seed plus Step 2 substrate-consumption-
    follower extension.

    Phase 1D registers ``burial_vault_personalization_studio``;
    Step 2 Phase 2C registers ``urn_vault_personalization_studio`` via
    the same ``register_template_type`` API. Future Generation Focus
    templates extend identically.
    """
    register_template_type(
        TemplateTypeDescriptor(
            template_type="burial_vault_personalization_studio",
            display_name="Burial Vault Personalization Studio",
            description=(
                "Generation Focus template for personalizing burial vault "
                "covers within the canonical 4-options vocabulary "
                "(legacy_print | physical_nameplate | physical_emblem | "
                "vinyl per §3.26.11.12.19.2). Funeral home directors author "
                "with families present; manufacturers author from FH-shared "
                "canvas or from sales orders without family co-authoring."
            ),
            # FH primary; manufacturer surfaces via cross-tenant share
            # OR direct sales-order authoring per Q3 canonical pairing.
            applicable_verticals=["funeral_home", "manufacturing"],
            applicable_authoring_contexts=list(CANONICAL_AUTHORING_CONTEXTS),
            empty_canvas_state_factory_key="burial_vault_personalization_studio",
            tune_mode_dimensions=list(CANONICAL_TUNE_DIMENSIONS_BURIAL_VAULT),
            sort_order=10,
        )
    )

    # Step 2 substrate-consumption-follower per Phase 2C build prompt.
    # Inherits Phase 1D registration shape via discriminator
    # differentiation. Per §3.26.11.12.19.6 scope freeze, urn vault
    # inherits canonical 4-options vocabulary at category scope; Tune
    # mode dimensions parallel Phase 1D.
    register_template_type(
        TemplateTypeDescriptor(
            template_type="urn_vault_personalization_studio",
            display_name="Urn Vault Personalization Studio",
            description=(
                "Generation Focus template for personalizing cremation "
                "urn vault covers within the canonical 4-options "
                "vocabulary (legacy_print | physical_nameplate | "
                "physical_emblem | vinyl per §3.26.11.12.19.2). Step 2 "
                "substrate-consumption-follower at Personalization Studio "
                "category — inherits Phase 1A-1G patterns from Burial "
                "Vault Personalization Studio via discriminator "
                "differentiation. Authoring contexts mirror Step 1: FH "
                "directors with families; manufacturers from FH-shared "
                "canvas or sales orders."
            ),
            applicable_verticals=["funeral_home", "manufacturing"],
            applicable_authoring_contexts=list(CANONICAL_AUTHORING_CONTEXTS),
            empty_canvas_state_factory_key="urn_vault_personalization_studio",
            tune_mode_dimensions=list(CANONICAL_TUNE_DIMENSIONS_URN_VAULT),
            sort_order=20,
        )
    )
