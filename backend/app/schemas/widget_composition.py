"""Widget composition blob Pydantic schemas (WB-1).

Canonical Pydantic v2 schemas for the composed widget JSONB blob shape
locked in investigation Area 7 (Q-30) at
`docs/investigations/2026-05-21-widget-builder.md`. Mirrored
verbatim on the frontend at
`frontend/src/lib/widget-builder/types/composition-blob.ts` — field
names, enum values, optional/required discipline match exactly.

Per Q-30 + Q-4/Q-7/Q-10 locks:

  • CompositionBlob: top-level wrapper with schema_version (Literal[1]
    for Phase 1), root_atom_id (entry point into atom_tree),
    atom_tree (flat dict of atom_id → AtomNode for O(1) lookup +
    recursion via children refs), variants (per Q-10 single-
    composition-multi-variant model), bindings_catalog (per Q-7
    structured BindingRef objects).
  • AtomNode: 8 atom_types per Q-4 (text_label, value_display, icon,
    status_badge, divider, button, image, conditional_container).
    Children only on conditional_container per Phase 1 Q-5 nesting
    cap (2-level max). visible_in_variants for Q-10 variant
    visibility filter. binding_refs maps named props to binding_ids
    in bindings_catalog (indirection layer keeps bindings de-duped
    across atoms sharing a value).
  • BindingRef: discriminated by binding_type — 'literal' carries
    literal_value; 'field_path' carries saved_view_id + field_path +
    iteration_mode. Per Q-7 'expression' binding deferred to WB-7.
  • VariantDefinition: variant_id + variant_name + target_surface +
    optional canonical_dimensions.

The structural-validity rules (root_atom_id exists, atom_id
uniqueness, dangling-children check, nesting cap, binding-ref
integrity, variant-ref integrity) are enforced by the service-layer
validator at `app/services/widget_definitions/validators.py`. Pydantic
catches type errors + per-field bounds; semantic cross-references
require the catalog-aware validator.

Per-atom-type config schemas (TextLabelConfig, ValueDisplayConfig,
…) capture the bounded Phase 1 shape per investigation Area 1
locks. Config is stored on `AtomNode.config` as a free dict
(`Dict[str, Any]`) so the JSONB blob stays forward-compatible with
catalog extension (WB-2 atom registry adds atom_types without a
schema migration); the explicit per-type classes document the
Phase 1 shapes + serve as the lookup table the WB-2 atom-inspector
controls bind against.
"""

from __future__ import annotations

from typing import Any, Annotated, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, model_validator


# ── Atom-type vocabulary ───────────────────────────────────────────────

AtomType = Literal[
    "text_label",
    "value_display",
    "icon",
    "status_badge",
    "divider",
    "button",
    "image",
    "conditional_container",
    # WB-3 — repeater_atom for iteration-shaped widgets. Renders its
    # `children` once per row of an iterating BindingRef (iteration_mode
    # === 'per_row'). The Phase 1 nesting cap stays at 2 levels of
    # atoms-that-wrap-children: a repeater_atom may contain
    # conditional_container, but it MAY NOT contain another
    # repeater_atom (the cross-container validator rejects nested
    # repeaters). See WB-3 build log.
    "repeater_atom",
]

# Phase 1 set of atom_types that may carry children (Q-5 two-level
# nesting cap; conditional_container + repeater_atom are the two
# container atoms in Phase 1 post-WB-3).
CONTAINER_ATOM_TYPES = frozenset({"conditional_container", "repeater_atom"})


# ── Variant + surface vocabulary ─────────────────────────────────────

VariantId = Literal["glance", "brief", "detail", "deep"]

TargetSurface = Literal[
    "focus_canvas",
    "page_canvas",
    "palette_preview",
]


# ── Binding refs (Q-7) ───────────────────────────────────────────────

BindingType = Literal["literal", "field_path"]
"""Phase 1 binding vocabulary. 'expression' deferred to WB-7."""

IterationMode = Literal["per_row", "single_summary", "single_record"]


class BindingRef(BaseModel):
    """Structured atom-prop binding per Q-7 lock.

    `binding_type='literal'` → carries `literal_value` (any JSON value).
    `binding_type='field_path'` → carries `saved_view_id` (the data
    source the widget binds to) + `field_path` (dotted access into a
    row, e.g. `delivery.driver_name`) + `iteration_mode` (per Q-12).

    Conditionally-required fields (literal_value / saved_view_id /
    field_path) are validated at the service layer; Pydantic only
    enforces the field-type contract.
    """

    model_config = ConfigDict(extra="forbid")

    binding_id: str
    binding_type: BindingType
    literal_value: Optional[Any] = None
    saved_view_id: Optional[str] = None
    field_path: Optional[str] = None
    iteration_mode: Optional[IterationMode] = None


# ── Atom node ────────────────────────────────────────────────────────


class AtomNode(BaseModel):
    """A single atom within a composed widget's atom tree.

    `atom_id` is the stable identifier (UUID-shaped string in
    practice but treated as opaque by the schema). `atom_type` selects
    the 8-atom Phase 1 catalog. `config` carries atom-type-specific
    props per the per-atom Config classes below — kept open as
    `Dict[str, Any]` so atom-catalog growth (WB-7 expansion) doesn't
    require schema migration.

    `children` is None for leaf atoms; a list of child atom_ids for
    container atoms (only `conditional_container` in Phase 1). The
    service-layer validator enforces "children only on container
    atoms" + the 2-level nesting cap per Q-5.

    `visible_in_variants` per Q-10: when present, the atom renders
    only in the listed variants. When None, atom renders in every
    variant the widget supports (default visibility).

    `binding_refs` maps logical prop names (e.g., 'text', 'icon')
    to `binding_id` values in `bindings_catalog`. Indirection keeps
    the same value referenceable from multiple atoms without
    duplication + makes binding rewrite (saved-view-shape-change
    mitigation per Q-RISK-2) a single-table edit.
    """

    model_config = ConfigDict(extra="forbid")

    atom_id: str
    atom_type: AtomType
    config: Dict[str, Any] = Field(default_factory=dict)
    children: Optional[List[str]] = None
    visible_in_variants: Optional[List[VariantId]] = None
    binding_refs: Optional[Dict[str, str]] = None


# ── Variants ─────────────────────────────────────────────────────────


class VariantDefinition(BaseModel):
    """A variant the widget supports.

    `target_surface` identifies which canvas/surface this variant is
    authored for — drives the WB-3 preview canvas dimensions and
    feeds the surface-availability validation (Q-23 + Q-25).

    `canonical_dimensions` is an optional `{width, height}` map
    declaring the target render box (used by WB-3 preview canvas).
    """

    model_config = ConfigDict(extra="forbid")

    variant_id: str
    variant_name: str
    target_surface: TargetSurface
    canonical_dimensions: Optional[Dict[str, int]] = None


# ── Top-level composition blob ───────────────────────────────────────


class CompositionBlob(BaseModel):
    """The top-level shape stored on `widget_definitions.composition_blob`.

    `schema_version=1` for Phase 1; future schema migrations bump this
    + ship a Pydantic-side upcaster from older versions.

    `atom_tree` is a FLAT dict (atom_id → AtomNode) — recursion happens
    via `AtomNode.children` (list of atom_ids). The tree's root is
    `root_atom_id`. Flat-dict-with-id-refs (vs. nested) keeps lookups
    O(1) and makes serialization / diff stable.

    `variants` enumerates the variants the composition supports. Each
    atom's `visible_in_variants` references variant_ids in this list.

    `bindings_catalog` is the table of BindingRef rows; atom
    `binding_refs` values are foreign keys into this table.

    `default_variant_id` (WB-8 Lock 6a) is the variant_id consumers
    render when no explicit variantId is passed (e.g., Focus Builder
    palette preview, Spaces pin render). When None, consumers fall
    through to `variants[0]?.variant_id` then to undefined ("all
    atoms"). Backend validator (write-time) enforces referential
    integrity: when set, the value MUST equal a variant_id in
    `variants[]`.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    root_atom_id: str
    atom_tree: Dict[str, AtomNode]
    variants: List[VariantDefinition] = Field(default_factory=list)
    bindings_catalog: Dict[str, BindingRef] = Field(default_factory=dict)
    default_variant_id: Optional[str] = None

    @model_validator(mode="after")
    def _validate_default_variant_id_ref(self) -> "CompositionBlob":
        """Lock 6a: when default_variant_id is set, it must reference an
        existing variant_id declared in `variants[]`. Empty variants
        list with non-null default_variant_id is rejected.
        """
        if self.default_variant_id is None:
            return self
        variant_ids = {v.variant_id for v in self.variants}
        if self.default_variant_id not in variant_ids:
            raise ValueError(
                f"default_variant_id {self.default_variant_id!r} "
                f"does not reference any declared variant_id in "
                f"variants[]"
            )
        return self


# ── Per-atom-type Phase 1 config schemas ─────────────────────────────
#
# These are DOCUMENTATION + write-time validation aids; they are NOT
# embedded in `AtomNode.config` directly (config stays Dict[str, Any]
# for forward compatibility). The WB-2 atom inspector reads these
# shapes via Python introspection to drive the right-rail controls.


_NumberFormat = Literal["number", "currency", "percent", "date", "duration"]


# Shared semantic vocabularies (WB-4b extension — runtime parity).
_TypographyVariant = Literal[
    "body",
    "body-sm",
    "caption",
    "label",
    "heading-1",
    "heading-2",
    "heading-3",
    "mono",
    "serif",
]

_SemanticColor = Literal[
    "default",
    "muted",
    "subtle",
    "accent",
    "success",
    "warning",
    "danger",
]

_SemanticAlign = Literal["start", "center", "end"]
_AlignmentFour = Literal["start", "center", "end", "stretch"]


class TextLabelConfig(BaseModel):
    """`text_label` atom — static or templated text.

    Per Q-7 lock, the actual text value comes via a BindingRef in
    `binding_refs['text']`. This config carries presentation knobs
    only (no value).
    """

    model_config = ConfigDict(extra="forbid")

    # WB-4b — runtime fields (semantic vocab).
    text: Optional[str] = None  # required at Publish if no binding
    variant: Optional[_TypographyVariant] = "body"
    alignment: Optional[_SemanticAlign] = "start"
    color: Optional[_SemanticColor] = "default"
    max_lines: Optional[int] = None
    # Legacy WB-1 fields retained for back-compat.
    typography_token: Optional[str] = None
    align: Optional[Literal["left", "center", "right"]] = None


class ValueDisplayConfig(BaseModel):
    """`value_display` atom — single bound value with format spec.

    Per Q-8 lock: per-atom formatter prop. `format` selects the
    format family; `format_config` carries family-specific options
    (e.g., `{"currency": "USD"}` for currency).
    """

    model_config = ConfigDict(extra="forbid")

    format: _NumberFormat = "number"
    format_config: Dict[str, Any] = Field(default_factory=dict)
    # WB-4b — runtime fields.
    variant: Optional[_TypographyVariant] = "body"
    alignment: Optional[_SemanticAlign] = "start"
    color: Optional[_SemanticColor] = "default"
    placeholder: Optional[str] = None
    binding_id: Optional[str] = None  # WB-6 binding picker placeholder
    # Legacy WB-1 fields retained for back-compat.
    typography_token: Optional[str] = None
    align: Optional[Literal["left", "center", "right"]] = None


class IconConfig(BaseModel):
    """`icon` atom — Lucide-keyed icon.

    WB-4b — runtime reads `icon_name` (required), `size_token`,
    `stroke_width`, `color` (semantic). `color_token` retained for
    back-compat.
    """

    model_config = ConfigDict(extra="forbid")

    icon_name: str
    size_token: Optional[Literal["xs", "sm", "md", "lg", "xl"]] = "md"
    stroke_width: Optional[float] = 2.0
    color: Optional[_SemanticColor] = "default"
    # Legacy WB-1 field retained for back-compat.
    color_token: Optional[str] = None


class StatusBadgeConfig(BaseModel):
    """`status_badge` atom — composite text + icon + status family.

    Per Q-9: status_badge is the canonical exception to the
    container-level-chrome-only rule (has its own surface treatment).
    `status_map` maps observed status values to canonical status
    families (success / warning / error / info / neutral).
    """

    model_config = ConfigDict(extra="forbid")

    # WB-4b — runtime fields.
    label: Optional[str] = None  # required at Publish if no binding
    variant: Optional[
        Literal["neutral", "success", "warning", "danger", "info"]
    ] = "neutral"
    icon_name: Optional[str] = None
    status_map: Dict[str, str] = Field(default_factory=dict)
    show_icon: bool = True
    typography_token: Optional[str] = "caption"


class DividerConfig(BaseModel):
    """`divider` atom — 1px hairline + optional spacing.

    WB-4b — runtime reads `orientation`, `spacing` (semantic enum),
    `color`. `spacing_token` retained for back-compat.
    """

    model_config = ConfigDict(extra="forbid")

    orientation: Literal["horizontal", "vertical"] = "horizontal"
    spacing: Optional[Literal["compact", "normal", "loose"]] = "normal"
    color: Optional[Literal["subtle", "normal"]] = "subtle"
    # Legacy WB-1 field retained for back-compat.
    spacing_token: Optional[str] = None


# ── WB-7 ActionRef substrate (Area 2 Lock 2a discriminated union) ───
#
# Per WB-7 investigation Area 2 Lock 2a: ActionRef is an inline
# discriminated union per `action_kind`. Each verb's config carries
# only the fields that verb needs. The catalog-keyed alternative
# (Option B) was rejected — actions don't exhibit the same reuse
# cardinality as bindings.
#
# Per Area 6 Lock 6a: parameter bindings carry 8 sources. The 8th
# (current_row) is added in WB-7 to support row-iterated contexts.
# Mirrors `frontend/src/lib/runtime-host/buttons/types.ts` for the
# overlapping 7 sources + WB-7's current_row addition.

_ParameterBindingSource = Literal[
    "literal",
    "static",
    "route_param",
    "query_param",
    "focus_context",
    "tenant_context",
    "operator_context",
    "current_row",
]


class ParameterBindingRef(BaseModel):
    """A single ActionRef parameter binding (8 sources per WB-7 Area 6).

    `current_row` is the 8th binding source — only available inside a
    repeater_atom context. Resolver returns null outside that context;
    backend validator surfaces a contextual error at publish.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    source: _ParameterBindingSource
    # literal — direct value.
    value: Optional[Any] = None
    # static — alias for literal (kept distinct for picker UX vocabulary).
    static_value: Optional[Any] = None
    # route_param / query_param — URL param name.
    param_name: Optional[str] = None
    # focus_context / tenant_context / operator_context — field selector.
    field_name: Optional[str] = None
    # current_row — row field path (dotted access into the row dict).
    row_field: Optional[str] = None


class _ActionRefBase(BaseModel):
    """Shared base across all 5 ActionRef variants."""

    model_config = ConfigDict(extra="forbid")

    confirm_before: Optional[bool] = None
    confirm_copy: Optional[str] = None


class NavigateActionRef(_ActionRefBase):
    """`navigate` verb — react-router push to a route template."""

    action_kind: Literal["navigate"]
    href: str
    href_binding: Optional[ParameterBindingRef] = None
    params: List[ParameterBindingRef] = Field(default_factory=list)


class OpenFocusActionRef(_ActionRefBase):
    """`open_focus` verb — open a registered Focus by slug."""

    action_kind: Literal["open_focus"]
    focus_template_slug: str
    initial_context: List[ParameterBindingRef] = Field(default_factory=list)


_PeekEntityType = Literal[
    "fh_case",
    "invoice",
    "sales_order",
    "task",
    "contact",
    "saved_view",
]


class OpenPeekActionRef(_ActionRefBase):
    """`open_peek` verb — open a peek panel for an entity."""

    action_kind: Literal["open_peek"]
    peek_view_type: _PeekEntityType
    initial_context: List[ParameterBindingRef] = Field(default_factory=list)


class TriggerWorkflowActionRef(_ActionRefBase):
    """`trigger_workflow` verb — start a workflow run.

    Per Lock 5b: confirm_before defaults true at the picker UI layer.
    Backend accepts explicit value; null is treated as default.
    """

    action_kind: Literal["trigger_workflow"]
    workflow_slug: str
    workflow_input: List[ParameterBindingRef] = Field(default_factory=list)


_MutateKind = Literal["anomaly_acknowledge"]


class MutateActionRef(_ActionRefBase):
    """`mutate` verb — bounded state flip per §12.6a.

    Phase 1 mutate_kind narrowed to `anomaly_acknowledge` only. Future
    state-flip kinds (mark_read, status_flip) enumerate as the kind
    Literal grows. Generic field-patch substrate is NOT shipped.
    """

    action_kind: Literal["mutate"]
    mutate_kind: _MutateKind
    target_id_binding: ParameterBindingRef


# Discriminated union per WB-7 Area 2 Lock 2a. Pydantic 2 uses
# `Annotated[Union[...], Discriminator(...)]` for tagged unions.
ActionRef = Annotated[
    Union[
        NavigateActionRef,
        OpenFocusActionRef,
        OpenPeekActionRef,
        TriggerWorkflowActionRef,
        MutateActionRef,
    ],
    Discriminator("action_kind"),
]


class ButtonConfig(BaseModel):
    """`button` atom — label + action.

    Per Q-17/Q-18 lock + WB-7 Area 2 Lock 2a: click-target vocabulary
    is bounded (navigate / open_focus / open_peek / mutate /
    trigger_workflow). The `action` field carries an `ActionRef`
    discriminated union per verb. `action_kind` + `action_config`
    remain on the shape for back-compat reads of pre-WB-7 blobs but
    operators author via the new `action` field; the inspector
    populates both fields in sync for now.

    `action_ref` field is RETIRED in WB-7 (Area 11 Surprise 4 — the
    forward-compat string slot was never populated in production).
    Typed `Optional[None]` so any legacy persisted value is parseable
    but never carries data.
    """

    model_config = ConfigDict(extra="forbid")

    # WB-4b — runtime fields.
    label: Optional[str] = None  # required at Publish if no binding
    variant: Optional[
        Literal["primary", "secondary", "ghost", "destructive"]
    ] = "secondary"
    size: Optional[Literal["sm", "md", "lg"]] = "md"
    icon_name: Optional[str] = None
    action_kind: Literal[
        "navigate",
        "open_focus",
        "open_peek",
        "mutate",
        "trigger_workflow",
    ] = "navigate"
    action_config: Dict[str, Any] = Field(default_factory=dict)
    # WB-7 — new discriminated-union ActionRef. When present, the
    # runtime dispatcher consumes this field; action_kind / action_config
    # exist for backward-compat reads of pre-WB-7 blobs.
    action: Optional[ActionRef] = None
    # WB-7 — RETIRED. `action_ref?: str` was a WB-3/4b forward-compat
    # slot that was never populated in production. Typed as
    # `Optional[None]` so any legacy persisted value parses but never
    # carries data. Operators wire via the `action` field instead.
    action_ref: Optional[None] = None
    # Forward-compat — runtime accepts a `variantVocab` alias key.
    variantVocab: Optional[
        Literal["primary", "secondary", "ghost", "destructive"]
    ] = None


class ImageConfig(BaseModel):
    """`image` atom — URL or Vault asset ref.

    WB-4b — runtime reads `source_kind`, `src`, `alt` (required at
    Publish), `aspect_ratio_token`, `object_fit`, `fallback_icon_name`.
    `fit` + `aspect_ratio` retained for back-compat.
    """

    model_config = ConfigDict(extra="forbid")

    source_kind: Literal["url", "vault_asset"] = "url"
    src: Optional[str] = None
    alt: Optional[str] = None  # required at Publish
    aspect_ratio_token: Optional[
        Literal["square", "video", "portrait", "auto"]
    ] = "auto"
    object_fit: Optional[Literal["cover", "contain"]] = "cover"
    fallback_icon_name: Optional[str] = "image"
    # Legacy WB-1 fields retained for back-compat.
    fit: Optional[Literal["cover", "contain", "fill"]] = None
    aspect_ratio: Optional[str] = None


class RepeaterAtomConfig(BaseModel):
    """`repeater_atom` atom — iteration over a per_row BindingRef (WB-3).

    Architectural primitive for iteration-shaped widgets (lists,
    repeating cards, log lines). At render time:

      • Resolves the BindingRef referenced by `binding_id` against the
        atom's `binding_refs['rows']` slot.
      • For each row of the resolved data, renders the atom_ids in
        `config.children` once with a per-row dataContext.
      • Phase 1 placeholder data: WB-3 surfaces 1 mock row so the
        layout space is visible in the authoring shell. WB-6 wires
        real saved-view row projection.

    Phase 1 nesting cap (cross-container): a repeater_atom MAY contain
    conditional_container as a child. A repeater_atom may NOT contain
    another repeater_atom. The service-layer validator rejects nested
    repeaters; the Pydantic schema only types the shape.

    The repeater's child atom_ids live in the top-level atom_tree (same
    flat-dict-with-id-refs model as conditional_container). `config.children`
    lists the ordered atom_ids rendered per row.
    """

    model_config = ConfigDict(extra="forbid")

    binding_id: str
    """BindingRef binding_id in the parent CompositionBlob's
    `bindings_catalog` referencing a `field_path` binding with
    `iteration_mode='per_row'`. Validator enforces both invariants."""

    children: List[str] = Field(default_factory=list)
    """Ordered atom_ids rendered once per row. Must match
    AtomNode.children for the same atom (the canonical tree-walk
    field). Validator enforces equivalence."""

    direction: Literal["row", "column"] = "column"
    spacing: Literal["compact", "normal", "loose"] = "normal"
    empty_state: Optional[str] = None
    max_rows: Optional[int] = None


class ConditionalContainerConfig(BaseModel):
    """`conditional_container` atom — children render only when
    `condition` evaluates true.

    Per Q-7 expression-deferral, Phase 1 conditions are restricted
    to a simple shape: a BindingRef in `binding_refs['condition']`
    that resolves to a truthy value. WB-7 may extend the condition
    vocabulary to support derived expressions.
    """

    model_config = ConfigDict(extra="forbid")

    direction: Literal["row", "column"] = "column"
    gap_token: Optional[str] = "sm"
    # WB-4b — runtime reads `spacing` (semantic) + `alignment`.
    # `alignment` is the canonical Surprise-1 schema-extension (per
    # the WB-4b investigation Q-resolution). Stretch is included to
    # match canvas-flex parity even though the WB-4b runtime renderer
    # accepts only start/center/end today.
    spacing: Optional[Literal["compact", "normal", "loose"]] = "normal"
    alignment: Optional[_AlignmentFour] = "start"
    condition_binding_id: Optional[str] = None  # WB-7 placeholder


# Lookup table for the WB-2 atom inspector. Maps atom_type → Config
# class. Keeps the per-atom-type config schemas centrally documented;
# WB-2 introspects this dict to build the right-rail controls.
PER_ATOM_CONFIG_SCHEMAS: Dict[str, type[BaseModel]] = {
    "text_label": TextLabelConfig,
    "value_display": ValueDisplayConfig,
    "icon": IconConfig,
    "status_badge": StatusBadgeConfig,
    "divider": DividerConfig,
    "button": ButtonConfig,
    "image": ImageConfig,
    "conditional_container": ConditionalContainerConfig,
    "repeater_atom": RepeaterAtomConfig,
}


__all__ = [
    "ActionRef",
    "AtomNode",
    "AtomType",
    "BindingRef",
    "BindingType",
    "ButtonConfig",
    "CONTAINER_ATOM_TYPES",
    "CompositionBlob",
    "ConditionalContainerConfig",
    "DividerConfig",
    "IconConfig",
    "ImageConfig",
    "IterationMode",
    "MutateActionRef",
    "NavigateActionRef",
    "OpenFocusActionRef",
    "OpenPeekActionRef",
    "PER_ATOM_CONFIG_SCHEMAS",
    "ParameterBindingRef",
    "RepeaterAtomConfig",
    "StatusBadgeConfig",
    "TargetSurface",
    "TextLabelConfig",
    "TriggerWorkflowActionRef",
    "ValueDisplayConfig",
    "VariantDefinition",
    "VariantId",
]
