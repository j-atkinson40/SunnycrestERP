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
from app.services.widget_definitions.surface_mapping import (
    variant_target_compatible_with_supported_surfaces,
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

    # WB-3 — repeater_atom semantic gates:
    #   • config.binding_id must reference a BindingRef in bindings_catalog
    #     with binding_type='field_path' AND iteration_mode='per_row'.
    #   • config.children must equal AtomNode.children (both canonical
    #     and informational lists must agree).
    #   • repeater_atom MAY NOT contain another repeater_atom in its
    #     children subtree (cross-container nesting cap).
    for atom_id, node in blob.atom_tree.items():
        if node.atom_type != "repeater_atom":
            continue
        cfg = node.config or {}
        cfg_binding_id = cfg.get("binding_id") if isinstance(cfg, dict) else None
        if not isinstance(cfg_binding_id, str) or not cfg_binding_id:
            errors.append(
                f"atom_tree[{atom_id!r}].config.binding_id: "
                f"repeater_atom requires a non-empty binding_id"
            )
        else:
            ref = blob.bindings_catalog.get(cfg_binding_id)
            if ref is None:
                errors.append(
                    f"atom_tree[{atom_id!r}].config.binding_id: "
                    f"references unknown binding_id {cfg_binding_id!r}"
                )
            else:
                if ref.binding_type != "field_path":
                    errors.append(
                        f"atom_tree[{atom_id!r}].config.binding_id: "
                        f"repeater_atom binding must be 'field_path' "
                        f"(got {ref.binding_type!r})"
                    )
                if ref.iteration_mode != "per_row":
                    errors.append(
                        f"atom_tree[{atom_id!r}].config.binding_id: "
                        f"repeater_atom binding must have "
                        f"iteration_mode='per_row' (got "
                        f"{ref.iteration_mode!r})"
                    )
        # config.children equivalence to AtomNode.children
        cfg_children = cfg.get("children") if isinstance(cfg, dict) else None
        node_children = node.children or []
        if cfg_children is None:
            cfg_children = []
        if list(cfg_children) != list(node_children):
            errors.append(
                f"atom_tree[{atom_id!r}]: repeater_atom config.children "
                f"({cfg_children!r}) must equal AtomNode.children "
                f"({node_children!r})"
            )
        # Cross-container nesting cap — no repeater inside repeater.
        # Walk only the repeater's subtree (not the full tree) so we
        # surface the smallest actionable error.
        _seen: set[str] = set()

        def _walk_repeater_subtree(start: str) -> None:
            if start in _seen:
                return
            _seen.add(start)
            sub = blob.atom_tree.get(start)
            if sub is None:
                return
            if sub.children is None:
                return
            for child_id in sub.children:
                child = blob.atom_tree.get(child_id)
                if child is None:
                    continue
                if child.atom_type == "repeater_atom":
                    errors.append(
                        f"atom_tree[{atom_id!r}]: repeater_atom may "
                        f"not contain another repeater_atom (found "
                        f"{child_id!r}) — Phase 1 cross-container "
                        f"nesting cap"
                    )
                _walk_repeater_subtree(child_id)

        for child_id in node_children:
            # Check the direct child itself before recursing — a
            # repeater whose immediate child is also a repeater is
            # exactly the nesting case we reject.
            direct = blob.atom_tree.get(child_id)
            if direct is not None and direct.atom_type == "repeater_atom":
                errors.append(
                    f"atom_tree[{atom_id!r}]: repeater_atom may "
                    f"not contain another repeater_atom (found "
                    f"{child_id!r}) — Phase 1 cross-container "
                    f"nesting cap"
                )
            _walk_repeater_subtree(child_id)

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


def validate_composition_blob_strict(
    raw: Any,
    *,
    supported_surfaces: list[str] | tuple[str, ...] | None = None,
) -> CompositionBlob:
    """Strict validator — runs the full WB-4b Publish gate.

    Wraps `validate_composition_blob` (structural + cross-reference
    integrity) AND enforces per-atom required fields per atom_type
    (WB-4b Step 2 tightening). Required-field rules per the
    schema-runtime drift audit:

      • text_label: either `binding_refs['text']` OR non-empty
        `config.text` must be present.
      • value_display: either `binding_refs['value']` OR a
        `config.binding_id` must be present.
      • icon: `config.icon_name` non-empty (Pydantic already enforces).
      • status_badge: either `binding_refs['label']` /
        `binding_refs['status']` OR non-empty `config.label` must be
        present.
      • button: either `binding_refs['label']` OR non-empty
        `config.label` must be present.
      • image: non-empty `config.alt` REQUIRED for a11y.
      • repeater_atom: non-empty `config.binding_id` (already covered
        by the structural validator).

    Raises CompositionBlobValidationError on any failure (structural
    errors and required-field errors surface in a single errors list).
    """
    errors: list[str] = []
    try:
        blob = validate_composition_blob(raw)
    except CompositionBlobValidationError as exc:
        # Add structural errors but keep going to surface required-field
        # gaps in the same response when possible. If the blob couldn't
        # be parsed at all, re-raise — there's nothing to check further.
        errors.extend(exc.errors)
        try:
            blob = CompositionBlob.model_validate(raw)
        except Exception:
            raise CompositionBlobValidationError(errors)

    # WB-6 — bidirectional iteration_mode + binding-shape compatibility
    # checks. Added at strict (Publish) gate; draft state stays
    # permissive per Lock 5e.
    #
    # Check 1 (repeater_atom → per_row) is already enforced by the
    # structural validator (validate_composition_blob). The 5 WB-6
    # bidirectional checks here:
    #
    #   1. (redundant with structural; restated for completeness)
    #      repeater_atom binding MUST use iteration_mode='per_row'.
    #   2. iteration_mode='per_row' bindings MUST be consumed by a
    #      repeater_atom (no non-repeater atom may consume a per_row
    #      binding). Inverse of check 1.
    #   3. value_display + text_label + icon + status_badge + button +
    #      image bindings MUST use 'single_record' OR 'single_summary'
    #      (not 'per_row'). Non-repeater leaf-atom constraint.
    #   4. binding_type='literal' MUST NOT carry iteration_mode (per
    #      Area 4 Lock — literal-binding behavior unchanged; iteration
    #      semantics are field_path-only).
    #   5. Every field_path BindingRef MUST set iteration_mode (and
    #      saved_view_id + field_path) — the field_path declared shape
    #      MUST be compatible. Saved-view emit_shape resolves at
    #      runtime; structural check is "iteration_mode declared per
    #      Lock 5e".
    _NON_REPEATER_LEAF_ATOM_TYPES = frozenset({
        "value_display",
        "text_label",
        "icon",
        "status_badge",
        "button",
        "image",
    })
    _PER_ROW_BINDING_IDS: set[str] = set()
    for binding_id, ref in blob.bindings_catalog.items():
        # WB-6 check 4: literal bindings must not carry iteration_mode.
        if ref.binding_type == "literal" and ref.iteration_mode is not None:
            errors.append(
                f"bindings_catalog[{binding_id!r}]: literal bindings "
                f"must not carry iteration_mode (got "
                f"{ref.iteration_mode!r}). WB-6 reserves iteration "
                f"semantics for field_path bindings."
            )
        # WB-6 check 5: field_path bindings must declare iteration_mode
        # + saved_view_id + non-empty field_path.
        if ref.binding_type == "field_path":
            if ref.iteration_mode is None:
                errors.append(
                    f"bindings_catalog[{binding_id!r}]: field_path "
                    f"binding requires iteration_mode (one of "
                    f"per_row / single_summary / single_record)."
                )
            if not ref.saved_view_id:
                errors.append(
                    f"bindings_catalog[{binding_id!r}]: field_path "
                    f"binding requires non-empty saved_view_id."
                )
            if not ref.field_path:
                errors.append(
                    f"bindings_catalog[{binding_id!r}]: field_path "
                    f"binding requires non-empty field_path."
                )
            if ref.iteration_mode == "per_row":
                _PER_ROW_BINDING_IDS.add(binding_id)

    # Build a set of binding_ids legitimately consumed by a
    # repeater_atom (either via repeater config.binding_id OR
    # binding_refs map). Other consumers of per_row bindings are
    # rejected by check 2.
    _REPEATER_PERROW_CONSUMERS: set[str] = set()
    for atom_id, node in blob.atom_tree.items():
        if node.atom_type != "repeater_atom":
            continue
        cfg = node.config if isinstance(node.config, dict) else {}
        bid = cfg.get("binding_id") if isinstance(cfg, dict) else None
        if isinstance(bid, str) and bid:
            _REPEATER_PERROW_CONSUMERS.add(bid)
        for _, ref_id in (node.binding_refs or {}).items():
            _REPEATER_PERROW_CONSUMERS.add(ref_id)

    for atom_id, node in blob.atom_tree.items():
        if node.atom_type not in _NON_REPEATER_LEAF_ATOM_TYPES:
            continue
        for prop_name, binding_id in (node.binding_refs or {}).items():
            ref = blob.bindings_catalog.get(binding_id)
            if ref is None:
                continue  # structural validator already flagged
            if ref.binding_type != "field_path":
                continue
            mode = ref.iteration_mode
            # WB-6 check 3: non-repeater leaf atoms must use
            # single_record OR single_summary (not per_row).
            if mode == "per_row":
                errors.append(
                    f"atom_tree[{atom_id!r}].binding_refs[{prop_name!r}]: "
                    f"{node.atom_type} atoms must use iteration_mode="
                    f"'single_record' or 'single_summary' (got "
                    f"'per_row'). per_row bindings must be consumed by "
                    f"a repeater_atom."
                )
            elif mode is not None and mode not in (
                "single_record",
                "single_summary",
            ):
                errors.append(
                    f"atom_tree[{atom_id!r}].binding_refs[{prop_name!r}]: "
                    f"unknown iteration_mode {mode!r}"
                )

    # WB-6 check 2: per_row bindings must be consumed by a
    # repeater_atom — find orphaned per_row bindings.
    for binding_id in _PER_ROW_BINDING_IDS:
        if binding_id not in _REPEATER_PERROW_CONSUMERS:
            errors.append(
                f"bindings_catalog[{binding_id!r}]: per_row binding "
                f"must be consumed by a repeater_atom (none found in "
                f"this composition)."
            )

    # WB-7 — ActionRef structural validation for button atoms.
    #
    # Strict gate (Publish-time): when a button atom carries
    # `config.action` (the new discriminated-union ActionRef), enforce
    # per-action_kind required fields + current_row context invariant
    # + mutate_kind narrowing. Pydantic's discriminator catches "wrong
    # field shape per kind" at parse time; this layer surfaces the
    # cross-atom-context invariants (current_row inside a repeater) +
    # the §12.6a bounded-state-flip discipline (mutate_kind
    # restricted).
    #
    # Per Lock 5e parallel: strict-only at Publish; draft state stays
    # permissive (the picker can leave fields empty mid-edit).
    repeater_descendant_atom_ids: set[str] = set()
    for _aid, _node in blob.atom_tree.items():
        if _node.atom_type != "repeater_atom":
            continue
        # Walk the repeater's subtree (excluding itself) and mark every
        # descendant as "inside a repeater." current_row bindings are
        # valid only inside this set.
        _stack: list[str] = list(_node.children or [])
        while _stack:
            cid = _stack.pop()
            if cid in repeater_descendant_atom_ids:
                continue
            repeater_descendant_atom_ids.add(cid)
            child = blob.atom_tree.get(cid)
            if child and child.children:
                _stack.extend(child.children)

    for atom_id, node in blob.atom_tree.items():
        if node.atom_type != "button":
            continue
        cfg = node.config if isinstance(node.config, dict) else {}
        action = cfg.get("action") if isinstance(cfg, dict) else None
        if action is None:
            continue  # button without `action` is a legacy/no-op button
        if not isinstance(action, dict):
            errors.append(
                f"atom_tree[{atom_id!r}].config.action: must be an object"
            )
            continue
        kind = action.get("action_kind")
        # Per-action_kind required-field validation. Pydantic
        # discriminator catches malformed shapes at parse — this layer
        # surfaces aggregated, friendlier errors when the strict gate
        # runs against a blob where Pydantic accepted the parse but the
        # operator left a required field empty.
        if kind == "navigate":
            if not action.get("href"):
                errors.append(
                    f"atom_tree[{atom_id!r}].config.action.href: "
                    f"navigate action requires href"
                )
        elif kind == "open_focus":
            if not action.get("focus_template_slug"):
                errors.append(
                    f"atom_tree[{atom_id!r}].config.action.focus_template_slug: "
                    f"open_focus action requires focus_template_slug"
                )
        elif kind == "open_peek":
            if not action.get("peek_view_type"):
                errors.append(
                    f"atom_tree[{atom_id!r}].config.action.peek_view_type: "
                    f"open_peek action requires peek_view_type"
                )
        elif kind == "trigger_workflow":
            if not action.get("workflow_slug"):
                errors.append(
                    f"atom_tree[{atom_id!r}].config.action.workflow_slug: "
                    f"trigger_workflow action requires workflow_slug"
                )
        elif kind == "mutate":
            mutate_kind = action.get("mutate_kind")
            if mutate_kind != "anomaly_acknowledge":
                errors.append(
                    f"atom_tree[{atom_id!r}].config.action.mutate_kind: "
                    f"Phase 1 mutate_kind must be 'anomaly_acknowledge' "
                    f"(got {mutate_kind!r}). §12.6a bounded-state-flip "
                    f"discipline."
                )
            target = action.get("target_id_binding")
            if not isinstance(target, dict):
                errors.append(
                    f"atom_tree[{atom_id!r}].config.action.target_id_binding: "
                    f"mutate action requires a target_id_binding"
                )
        elif kind is not None:
            errors.append(
                f"atom_tree[{atom_id!r}].config.action.action_kind: "
                f"unknown action_kind {kind!r}"
            )

        # current_row context check — any ParameterBindingRef with
        # source='current_row' is valid only inside a repeater_atom.
        def _bindings_in_action(a: dict) -> list[dict]:
            out: list[dict] = []
            for key in (
                "params",
                "initial_context",
                "workflow_input",
            ):
                lst = a.get(key)
                if isinstance(lst, list):
                    for item in lst:
                        if isinstance(item, dict):
                            out.append(item)
            for key in ("href_binding", "target_id_binding"):
                item = a.get(key)
                if isinstance(item, dict):
                    out.append(item)
            return out

        if atom_id not in repeater_descendant_atom_ids:
            for binding in _bindings_in_action(action):
                if binding.get("source") == "current_row":
                    bname = binding.get("name") or "<unnamed>"
                    errors.append(
                        f"atom_tree[{atom_id!r}].config.action: "
                        f"binding {bname!r} uses source='current_row' "
                        f"but the button is not inside a repeater_atom"
                    )

    for atom_id, node in blob.atom_tree.items():
        cfg = node.config or {}
        if not isinstance(cfg, dict):
            continue
        binding_refs = node.binding_refs or {}

        if node.atom_type == "text_label":
            has_binding = "text" in binding_refs
            has_static = bool(cfg.get("text"))
            if not has_binding and not has_static:
                errors.append(
                    f"atom_tree[{atom_id!r}].config.text: text_label "
                    f"requires either `config.text` or a binding at "
                    f"`binding_refs.text`"
                )
        elif node.atom_type == "value_display":
            has_binding = "value" in binding_refs
            has_static = bool(cfg.get("binding_id"))
            if not has_binding and not has_static:
                errors.append(
                    f"atom_tree[{atom_id!r}].config.binding_id: "
                    f"value_display requires either `config.binding_id` "
                    f"or a binding at `binding_refs.value`"
                )
        elif node.atom_type == "status_badge":
            has_binding = (
                "label" in binding_refs or "status" in binding_refs
            )
            has_static = bool(cfg.get("label"))
            if not has_binding and not has_static:
                errors.append(
                    f"atom_tree[{atom_id!r}].config.label: status_badge "
                    f"requires either `config.label` or a binding at "
                    f"`binding_refs.label`/`binding_refs.status`"
                )
        elif node.atom_type == "button":
            has_binding = "label" in binding_refs
            has_static = bool(cfg.get("label"))
            if not has_binding and not has_static:
                errors.append(
                    f"atom_tree[{atom_id!r}].config.label: button "
                    f"requires either `config.label` or a binding at "
                    f"`binding_refs.label`"
                )
        elif node.atom_type == "image":
            if not cfg.get("alt"):
                errors.append(
                    f"atom_tree[{atom_id!r}].config.alt: image "
                    f"requires non-empty `config.alt` (accessibility)"
                )

    # WB-8 Lock 3a — cross-surface compatibility enforcement at Publish.
    # When the caller passes supported_surfaces (the widget's top-level
    # surface declaration), enforce the per-variant compatibility +
    # Lock 3a.2/3a.3 per-surface variant-requirement rules.
    if supported_surfaces is not None:
        compat_issues = validate_cross_surface_compatibility(
            blob, supported_surfaces, strict=True
        )
        errors.extend(compat_issues)

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


def validate_cross_surface_compatibility(
    blob: CompositionBlob,
    supported_surfaces: list[str] | tuple[str, ...] | None,
    *,
    strict: bool = False,
) -> list[str]:
    """WB-8 Lock 3a cross-surface compatibility check.

    For each declared variant, asserts that its target_surface maps
    (per `surface_mapping.TARGET_TO_WIDGET_SURFACES`) to at least one
    entry in the widget's top-level supported_surfaces. Lock 3a.2 +
    Lock 3a.3 add the per-surface variant-requirement rules:
      • supported_surfaces includes "spaces_pin" → variants[] MUST
        contain a variant with variant_id="glance".
      • supported_surfaces includes "focus_canvas" → variants[] MUST
        contain a variant with variant_id="brief".

    Hybrid validation per Lock 3a:
      • `strict=False` (authoring-time / draft) — returns warnings
        as a non-empty list but the caller treats them as soft
        warnings (chip in inspector; not blocking).
      • `strict=True` (Publish) — same checks; caller raises on
        non-empty result.

    Returns list of human-readable issue strings; empty list = clean.
    """
    issues: list[str] = []
    if not supported_surfaces:
        return issues
    supported = list(supported_surfaces)

    # Per-variant cross-vocabulary check.
    for v in blob.variants:
        if not variant_target_compatible_with_supported_surfaces(
            v.target_surface, supported
        ):
            issues.append(
                f"variants[{v.variant_id!r}].target_surface: "
                f"{v.target_surface!r} is incompatible with widget "
                f"supported_surfaces={supported!r}"
            )

    # Lock 3a.2 — spaces_pin requires a Glance variant declaration.
    if "spaces_pin" in supported:
        variant_ids = {v.variant_id for v in blob.variants}
        if "glance" not in variant_ids:
            issues.append(
                "[Lock 3a.2] supported_surfaces includes 'spaces_pin' "
                "but no variant with variant_id='glance' is declared"
            )

    # Lock 3a.3 — focus_canvas requires a Brief variant declaration.
    # Only check when the widget actually declares non-empty variants[]
    # (an entirely empty variants list is the WB-1 initial state and
    # doesn't trigger this rule until the operator declares ANY
    # variants — graceful migration for shipped composed widgets per
    # R10 mitigation).
    if "focus_canvas" in supported and blob.variants:
        variant_ids = {v.variant_id for v in blob.variants}
        if "brief" not in variant_ids:
            issues.append(
                "[Lock 3a.3] supported_surfaces includes 'focus_canvas' "
                "but no variant with variant_id='brief' is declared"
            )

    # Note: strict-only flag is reserved for future per-rule severity
    # split. Phase 1 treats every issue as the same severity; callers
    # determine whether to raise or warn.
    _ = strict
    return issues


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
    blob: Optional[CompositionBlob] = None
    try:
        blob = validate_composition_blob(composition_blob)
    except CompositionBlobValidationError as exc:
        errors.extend(exc.errors)

    # WB-8 Lock 3a — cross-surface compat at write time (draft path).
    # Treated as soft warnings here — collected into errors only when
    # supported_surfaces declares spaces_pin or focus_canvas with
    # Lock 3a.2/3a.3 required-variant gaps. Pure target_surface
    # mismatches are surfaced via authoring-time chip in the inspector;
    # publish.py runs the strict validator (with supported_surfaces) as
    # the blocking gate.
    if blob is not None:
        supported = payload.get("supported_surfaces")
        if supported is not None:
            for issue in validate_cross_surface_compatibility(
                blob, supported, strict=False
            ):
                # Only the Lock 3a.2/3a.3 required-variant gaps are
                # blocking at the orchestrator level — they prevent a
                # widget declaring spaces_pin without Glance from being
                # written at all. Pure target_surface mismatches are
                # soft (warn-only at draft).
                if issue.startswith("[Lock 3a."):
                    errors.append(issue)

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
