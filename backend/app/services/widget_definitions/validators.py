"""Widget definition write-time validators (WB-1).

Additive branch per the FF-1 pattern: existing hand-coded widget
definitions (composition_blob IS NULL) flow through the legacy code
path unchanged. Composed widgets (composition_blob IS NOT NULL)
trigger this validator.

Two entry points:

  • `validate_composition_blob(raw)` — structural validation against
    the Pydantic schema + semantic cross-references (root atom
    existence, atom_id uniqueness, dangling children refs, Phase 1
    nesting cap per Q-5, binding-ref integrity, variant-ref
    integrity, per-atom-type config validation).
  • `validate_widget_definition_write(payload)` — orchestrates the
    additive branch: composition_blob NULL → no-op (legacy path
    unchanged); composition_blob populated → calls
    `validate_composition_blob` + enforces composition_version == 1
    + enforces tier_scope ∈ {'platform', 'vertical'}.

WB-3 (the auto-save hook) calls `validate_widget_definition_write`
before any write. WB-1 ships the validator only; no API routes are
modified to invoke it (write paths land in WB-4/WB-5).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from pydantic import ValidationError

from app.schemas.widget_composition import (
    CONTAINER_ATOM_TYPES,
    PER_ATOM_CONFIG_SCHEMAS,
    CompositionBlob,
)


# Phase 1 nesting cap per Q-5: root → group → atom. Containers
# (conditional_container) may have children, but those children may
# NOT themselves be containers.
_MAX_NESTING_DEPTH = 2

_VALID_TIER_SCOPES = frozenset({"platform", "vertical"})


class CompositionBlobValidationError(ValueError):
    """Raised when a composition_blob fails structural or semantic
    validation. Carries the list of error messages so the API layer
    can surface operator-actionable errors in one response.
    """

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__("; ".join(errors) if errors else "validation failed")


def validate_composition_blob(raw: Any) -> CompositionBlob:
    """Validate + parse a composition_blob into a CompositionBlob.

    Raises `CompositionBlobValidationError` on any failure (Pydantic
    structural errors AND semantic cross-reference errors are
    surfaced together via the errors list).
    """
    errors: list[str] = []

    # Pydantic structural validation first.
    try:
        blob = CompositionBlob.model_validate(raw)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", ()))
            msg = err.get("msg", "validation error")
            errors.append(f"{loc}: {msg}" if loc else msg)
        raise CompositionBlobValidationError(errors)

    # composition_version Phase 1 lock — schema_version is enforced by
    # the Literal[1] in the Pydantic schema; this is a defensive
    # double-check for callers that bypass schema construction.
    if blob.schema_version != 1:
        errors.append(
            f"schema_version: expected 1 for WB Phase 1, "
            f"got {blob.schema_version!r}"
        )

    atom_ids = list(blob.atom_tree.keys())
    atom_id_set = set(atom_ids)

    # atom_tree key uniqueness is guaranteed by the dict structure;
    # explicit duplicate check protects against pre-Pydantic raw-JSON
    # callers that bypass model construction (none in WB-1, but the
    # error message helps future arc work that hand-builds blobs).
    if len(atom_ids) != len(atom_id_set):
        # Find the duplicates for an actionable error.
        seen: set[str] = set()
        dupes: set[str] = set()
        for aid in atom_ids:
            if aid in seen:
                dupes.add(aid)
            seen.add(aid)
        errors.append(
            f"atom_tree: duplicate atom_ids: {sorted(dupes)}"
        )

    # Internal helper invariant: every AtomNode.atom_id should match
    # its key in atom_tree. (Pydantic doesn't enforce this; the
    # service layer does.)
    for key, node in blob.atom_tree.items():
        if node.atom_id != key:
            errors.append(
                f"atom_tree[{key!r}]: atom_id mismatch "
                f"(node.atom_id={node.atom_id!r})"
            )

    # root_atom_id must exist in atom_tree.
    if blob.root_atom_id not in atom_id_set:
        errors.append(
            f"root_atom_id: {blob.root_atom_id!r} not present in "
            f"atom_tree"
        )

    # Children refs must point at existing atom_ids; nesting cap
    # enforced via recursive depth check.
    _validate_children_refs(blob, atom_id_set, errors)

    # Variant references: every visible_in_variants entry must point
    # at a declared variant_id.
    variant_ids = {v.variant_id for v in blob.variants}
    for atom_id, node in blob.atom_tree.items():
        if node.visible_in_variants is None:
            continue
        for vid in node.visible_in_variants:
            if vid not in variant_ids:
                errors.append(
                    f"atom_tree[{atom_id!r}].visible_in_variants: "
                    f"references unknown variant_id {vid!r}"
                )

    # Variant_id uniqueness within `variants` list.
    if len(variant_ids) != len(blob.variants):
        seen_v: set[str] = set()
        dup_v: set[str] = set()
        for v in blob.variants:
            if v.variant_id in seen_v:
                dup_v.add(v.variant_id)
            seen_v.add(v.variant_id)
        errors.append(f"variants: duplicate variant_id: {sorted(dup_v)}")

    # Binding-ref integrity: every binding_refs value must be a
    # binding_id in bindings_catalog; bindings_catalog keys must
    # match the BindingRef.binding_id.
    binding_id_set = set(blob.bindings_catalog.keys())
    for binding_key, binding_ref in blob.bindings_catalog.items():
        if binding_ref.binding_id != binding_key:
            errors.append(
                f"bindings_catalog[{binding_key!r}]: binding_id "
                f"mismatch ({binding_ref.binding_id!r})"
            )
    for atom_id, node in blob.atom_tree.items():
        if node.binding_refs is None:
            continue
        for prop_name, binding_id in node.binding_refs.items():
            if binding_id not in binding_id_set:
                errors.append(
                    f"atom_tree[{atom_id!r}].binding_refs[{prop_name!r}]: "
                    f"references unknown binding_id {binding_id!r}"
                )

    # Per-atom-type config validation: when the atom_type has a
    # registered Phase 1 config schema, validate the config dict
    # against it. Forward-compat: atom_types added in WB-2/7 without
    # a schema entry pass through (config stays Dict[str, Any]).
    for atom_id, node in blob.atom_tree.items():
        config_schema = PER_ATOM_CONFIG_SCHEMAS.get(node.atom_type)
        if config_schema is None:
            continue
        try:
            config_schema.model_validate(node.config)
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(p) for p in err.get("loc", ()))
                msg = err.get("msg", "validation error")
                errors.append(
                    f"atom_tree[{atom_id!r}].config.{loc}: {msg}"
                    if loc
                    else f"atom_tree[{atom_id!r}].config: {msg}"
                )

    if errors:
        raise CompositionBlobValidationError(errors)

    return blob


def _validate_children_refs(
    blob: CompositionBlob,
    atom_id_set: set[str],
    errors: list[str],
) -> None:
    """Walk the tree from root + verify:
      • Every child_id reference points at an existing atom_id.
      • Children only on container atoms.
      • Phase 1 nesting cap (no container nested inside a container).
      • No cycles (a child appears at most once in the traversal).
    """
    # Pre-check: every atom with children must be a container atom.
    for atom_id, node in blob.atom_tree.items():
        if node.children is not None and node.atom_type not in CONTAINER_ATOM_TYPES:
            errors.append(
                f"atom_tree[{atom_id!r}]: atom_type "
                f"{node.atom_type!r} cannot carry children "
                f"(only container atoms can: "
                f"{sorted(CONTAINER_ATOM_TYPES)})"
            )

    # Pre-check: every child_id reference must exist in atom_tree.
    for atom_id, node in blob.atom_tree.items():
        if node.children is None:
            continue
        for child_id in node.children:
            if child_id not in atom_id_set:
                errors.append(
                    f"atom_tree[{atom_id!r}].children: references "
                    f"unknown atom_id {child_id!r}"
                )

    # Walk from root + enforce nesting cap + cycle-detection. If the
    # root_atom_id is missing the pre-check above already reported
    # it; bail out of the walk to avoid KeyError noise.
    if blob.root_atom_id not in atom_id_set:
        return

    visited: set[str] = set()

    def _walk(atom_id: str, depth: int) -> None:
        if atom_id in visited:
            errors.append(
                f"atom_tree: cycle detected — atom_id {atom_id!r} "
                f"appears more than once in the tree"
            )
            return
        visited.add(atom_id)
        node = blob.atom_tree.get(atom_id)
        if node is None:
            return
        if depth > _MAX_NESTING_DEPTH:
            errors.append(
                f"atom_tree[{atom_id!r}]: nesting depth {depth} "
                f"exceeds Phase 1 cap of {_MAX_NESTING_DEPTH}"
            )
            return
        if node.children is None:
            return
        for child_id in node.children:
            if child_id not in atom_id_set:
                continue  # already reported above
            _walk(child_id, depth + 1)

    _walk(blob.root_atom_id, depth=1)


def validate_widget_definition_write(
    payload: Dict[str, Any],
    *,
    legacy_validator: Optional[callable] = None,
) -> None:
    """Top-level validator entry point — orchestrates the additive
    branch.

    `payload` is the proposed widget_definitions row shape (the keys
    that may carry composition_blob, composition_version, tier_scope,
    and other WB-1 fields).

    `legacy_validator` is an optional callback for the
    hand-coded-widget path. WB-1 doesn't ship a legacy validator
    (existing widgets are seeded by `seed_widget_definitions`, not
    via this entry point); the parameter exists so WB-3+ can opt in.

    Behavior:
      • composition_blob IS NULL + composition_version IS NULL →
        legacy path. Calls `legacy_validator(payload)` if provided;
        otherwise no-op (preserves the pre-WB-1 write contract).
      • composition_blob populated → calls
        `validate_composition_blob` + enforces
        composition_version == 1 + tier_scope ∈ valid set.

    Raises `CompositionBlobValidationError` on failure.
    """
    composition_blob = payload.get("composition_blob")
    composition_version = payload.get("composition_version")

    # CHECK constraint at the DB level catches "one populated, one
    # NULL" but errors raised at write time are uglier than schema
    # errors raised here. Defense-in-depth.
    if (composition_blob is None) != (composition_version is None):
        raise CompositionBlobValidationError(
            [
                "composition_blob and composition_version must be "
                "jointly present or jointly absent",
            ]
        )

    # Legacy path — composition not populated.
    if composition_blob is None:
        if legacy_validator is not None:
            legacy_validator(payload)
        return

    # Composed path — validate.
    errors: list[str] = []

    # Composition version Phase 1 stamp.
    if composition_version != 1:
        errors.append(
            f"composition_version: expected 1 for WB Phase 1, "
            f"got {composition_version!r}"
        )

    # Tier scope vocabulary.
    tier_scope = payload.get("tier_scope")
    if tier_scope is not None and tier_scope not in _VALID_TIER_SCOPES:
        errors.append(
            f"tier_scope: expected one of "
            f"{sorted(_VALID_TIER_SCOPES)}, got {tier_scope!r}"
        )

    # Composition-blob structural + semantic validation.
    try:
        validate_composition_blob(composition_blob)
    except CompositionBlobValidationError as exc:
        errors.extend(exc.errors)

    if errors:
        raise CompositionBlobValidationError(errors)


def composition_atom_types(blob: CompositionBlob) -> Iterable[str]:
    """Iterate over the atom_types present in a composition blob.

    Helper for downstream consumers (atom-catalog telemetry, WB-2
    inspector building) that need to know which atom_types a blob
    references.
    """
    for node in blob.atom_tree.values():
        yield node.atom_type
