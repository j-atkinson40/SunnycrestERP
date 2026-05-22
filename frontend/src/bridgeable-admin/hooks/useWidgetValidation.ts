/**
 * useWidgetValidation — WB-4b client-side composition-blob validator.
 *
 * Mirrors the backend strict validator at
 * `backend/app/services/widget_definitions/validators.py::
 *  validate_composition_blob_strict` for the per-atom required-field
 * tightening. Surfaces a per-atom error map so the canvas can render
 * outlines + the inspector can render field-level feedback + the
 * Publish button can disable when errors are present.
 *
 * Phase 1 strategy: client-side validation is a fast pre-check for
 * the operator (immediate red outline, Publish disabled). The
 * authoritative validator stays the backend strict validator —
 * Publish goes through the API and the server's strict pass runs
 * again as defense-in-depth.
 *
 * Lightweight + dependency-free (no zod / yup). The atom-tree is
 * small (≤ ~30 atoms per Phase 1) so re-validating on every keystroke
 * is cheap.
 */
import { useMemo } from "react"

import type {
  AtomNode,
  AtomType,
  CompositionBlob,
} from "@/lib/widget-builder/types/composition-blob"
import { variantTargetCompatibleWithSupportedSurfaces } from "@/lib/widget-builder/types/surface-mapping"


export interface ValidationResult {
  /** atom_id → list of error messages (empty list = clean). */
  errorsByAtom: Record<string, string[]>
  /** Flattened list with (atom_id, msg) pairs in atom_tree iteration order. */
  errorList: { atom_id: string; atom_type: AtomType; message: string }[]
  hasErrors: boolean
  /** WB-8 — per-variant warnings (non-blocking at draft). Key: variant_id.
   *  Surfaced as warning chips in the Variant CRUD inspector section. */
  variantWarnings: Record<string, string[]>
  /** WB-8 — variant-level errors (blocking at Publish). default_variant_id
   *  unknown reference + Lock 3a.2/3a.3 per-surface variant requirements. */
  variantErrors: string[]
}


// WB-7 — mirror of backend ActionRef structural validation. Same
// checks as `backend/app/services/widget_definitions/validators.py`
// per-action_kind required fields + mutate kind narrowing. The
// current_row context check is done at the catalog-walk level
// (checkActionsContext below) since it needs the repeater-descendant
// set.
function checkActionRef(action: unknown): string[] {
  if (!action || typeof action !== "object") return []
  const a = action as Record<string, unknown>
  const kind = a.action_kind
  const errs: string[] = []
  if (kind === "navigate") {
    if (!a.href || typeof a.href !== "string") {
      errs.push("Navigate action requires a non-empty href.")
    }
  } else if (kind === "open_focus") {
    if (!a.focus_template_slug || typeof a.focus_template_slug !== "string") {
      errs.push("Open Focus action requires a focus_template_slug.")
    }
  } else if (kind === "open_peek") {
    if (!a.peek_view_type) {
      errs.push("Open Peek action requires a peek_view_type.")
    }
  } else if (kind === "trigger_workflow") {
    if (!a.workflow_slug || typeof a.workflow_slug !== "string") {
      errs.push("Trigger workflow action requires a workflow_slug.")
    }
  } else if (kind === "mutate") {
    if (a.mutate_kind !== "anomaly_acknowledge") {
      errs.push(
        "Mutate action: Phase 1 mutate_kind must be 'anomaly_acknowledge'.",
      )
    }
    if (!a.target_id_binding || typeof a.target_id_binding !== "object") {
      errs.push("Mutate action requires a target_id_binding.")
    }
  } else if (kind !== undefined) {
    errs.push(`Unknown action verb: ${String(kind)}`)
  }
  return errs
}


function _extractActionBindings(action: unknown): Array<{
  source?: unknown
  name?: unknown
}> {
  if (!action || typeof action !== "object") return []
  const a = action as Record<string, unknown>
  const out: Array<{ source?: unknown; name?: unknown }> = []
  for (const key of ["params", "initial_context", "workflow_input"]) {
    const lst = a[key]
    if (Array.isArray(lst)) {
      for (const item of lst) {
        if (item && typeof item === "object") {
          out.push(item as Record<string, unknown>)
        }
      }
    }
  }
  for (const key of ["href_binding", "target_id_binding"]) {
    const item = a[key]
    if (item && typeof item === "object") {
      out.push(item as Record<string, unknown>)
    }
  }
  return out
}


function checkAtom(node: AtomNode): string[] {
  const cfg = (node.config ?? {}) as Record<string, unknown>
  const bindings = node.binding_refs ?? {}
  const errs: string[] = []

  switch (node.atom_type) {
    case "text_label": {
      const hasBinding = "text" in bindings
      const text = typeof cfg.text === "string" ? cfg.text.trim() : ""
      if (!hasBinding && !text) {
        errs.push("Text label requires content (text or a binding).")
      }
      break
    }
    case "value_display": {
      const hasBinding = "value" in bindings
      const hasStatic =
        typeof cfg.binding_id === "string" && cfg.binding_id.length > 0
      if (!hasBinding && !hasStatic) {
        errs.push("Value display requires a binding (activates in WB-6).")
      }
      break
    }
    case "icon": {
      const name = typeof cfg.icon_name === "string" ? cfg.icon_name.trim() : ""
      if (!name) errs.push("Icon requires an icon_name.")
      break
    }
    case "status_badge": {
      const hasBinding = "label" in bindings || "status" in bindings
      const label = typeof cfg.label === "string" ? cfg.label.trim() : ""
      if (!hasBinding && !label) {
        errs.push("Status badge requires a label (text or binding).")
      }
      break
    }
    case "button": {
      const hasBinding = "label" in bindings
      const label = typeof cfg.label === "string" ? cfg.label.trim() : ""
      if (!hasBinding && !label) {
        errs.push("Button requires a label.")
      }
      // WB-7 — ActionRef structural validation.
      const action = cfg.action
      if (action !== undefined && action !== null) {
        for (const e of checkActionRef(action)) errs.push(e)
      }
      break
    }
    case "image": {
      const alt = typeof cfg.alt === "string" ? cfg.alt.trim() : ""
      if (!alt) {
        errs.push("Image requires alt text (accessibility).")
      }
      break
    }
    case "repeater_atom": {
      // Phase 1: binding_id is required at Publish per the existing
      // repeater_atom structural validator. We surface it as a soft
      // notice client-side since the binding picker is a WB-6
      // placeholder today.
      const id = typeof cfg.binding_id === "string" ? cfg.binding_id : ""
      if (!id) {
        errs.push("Repeater requires a row binding (activates in WB-6).")
      }
      break
    }
    default:
      break
  }
  return errs
}


// WB-6 — bidirectional iteration_mode + binding-shape compatibility
// checks. Mirrors backend validator at validators.py per Phase 1
// WB-4b canon (frontend mirror is fast pre-check; backend strict
// validator runs at Publish as defense-in-depth).
const _NON_REPEATER_LEAF_ATOM_TYPES = new Set([
  "value_display",
  "text_label",
  "icon",
  "status_badge",
  "button",
  "image",
])


function checkBindingsCatalog(
  blob: CompositionBlob,
): { atomId: string; message: string }[] {
  const errs: { atomId: string; message: string }[] = []

  // Build the set of binding_ids consumed by repeater_atoms (via
  // config.binding_id OR binding_refs map).
  const repeaterConsumers = new Set<string>()
  for (const [, node] of Object.entries(blob.atom_tree)) {
    if (node.atom_type !== "repeater_atom") continue
    const cfg = (node.config ?? {}) as Record<string, unknown>
    const bid = typeof cfg.binding_id === "string" ? cfg.binding_id : null
    if (bid) repeaterConsumers.add(bid)
    for (const [, refId] of Object.entries(node.binding_refs ?? {})) {
      repeaterConsumers.add(refId)
    }
  }

  const perRowBindingIds = new Set<string>()

  for (const [bindingId, ref] of Object.entries(blob.bindings_catalog)) {
    // Check 4: literal bindings must not carry iteration_mode.
    if (
      ref.binding_type === "literal" &&
      ref.iteration_mode !== undefined &&
      ref.iteration_mode !== null
    ) {
      errs.push({
        atomId: "__bindings__",
        message: `Binding "${bindingId}" (literal) cannot carry iteration_mode.`,
      })
    }
    // Check 5: field_path bindings must declare iteration_mode +
    // saved_view_id + non-empty field_path.
    if (ref.binding_type === "field_path") {
      if (!ref.iteration_mode) {
        errs.push({
          atomId: "__bindings__",
          message: `Binding "${bindingId}" needs an iteration mode.`,
        })
      }
      if (!ref.saved_view_id) {
        errs.push({
          atomId: "__bindings__",
          message: `Binding "${bindingId}" needs a saved view.`,
        })
      }
      if (!ref.field_path) {
        errs.push({
          atomId: "__bindings__",
          message: `Binding "${bindingId}" needs a field path.`,
        })
      }
      if (ref.iteration_mode === "per_row") {
        perRowBindingIds.add(bindingId)
      }
    }
  }

  // Check 3 + a piece of Check 2: leaf atoms with per_row bindings.
  for (const [atomId, node] of Object.entries(blob.atom_tree)) {
    if (!_NON_REPEATER_LEAF_ATOM_TYPES.has(node.atom_type)) continue
    for (const [propName, bindingId] of Object.entries(
      node.binding_refs ?? {},
    )) {
      const ref = blob.bindings_catalog[bindingId]
      if (!ref) continue
      if (ref.binding_type !== "field_path") continue
      if (ref.iteration_mode === "per_row") {
        errs.push({
          atomId,
          message: `Binding "${propName}" uses per_row but ${node.atom_type} requires single_record or single_summary.`,
        })
      }
    }
  }

  // Check 2: per_row bindings must be consumed by a repeater_atom.
  for (const bindingId of perRowBindingIds) {
    if (!repeaterConsumers.has(bindingId)) {
      errs.push({
        atomId: "__bindings__",
        message: `Per-row binding "${bindingId}" must be consumed by a repeater atom.`,
      })
    }
  }

  return errs
}


export function validateCompositionBlob(
  blob: CompositionBlob | null,
  supportedSurfaces?: ReadonlyArray<string>,
): ValidationResult {
  if (!blob) {
    return {
      errorsByAtom: {},
      errorList: [],
      hasErrors: false,
      variantWarnings: {},
      variantErrors: [],
    }
  }
  const errorsByAtom: Record<string, string[]> = {}
  const errorList: ValidationResult["errorList"] = []
  for (const [atomId, node] of Object.entries(blob.atom_tree)) {
    // Skip the synthetic root container — it has no required fields.
    if (atomId === blob.root_atom_id) continue
    const errs = checkAtom(node)
    if (errs.length === 0) continue
    errorsByAtom[atomId] = errs
    for (const message of errs) {
      errorList.push({ atom_id: atomId, atom_type: node.atom_type, message })
    }
  }

  // WB-6 — bidirectional binding-shape checks across the catalog.
  const bindingErrs = checkBindingsCatalog(blob)
  for (const { atomId, message } of bindingErrs) {
    if (!errorsByAtom[atomId]) errorsByAtom[atomId] = []
    errorsByAtom[atomId].push(message)
    const node = blob.atom_tree[atomId]
    errorList.push({
      atom_id: atomId,
      atom_type: node?.atom_type ?? ("text_label" as AtomType),
      message,
    })
  }

  // WB-7 — current_row context check. Mirrors backend validator:
  // any ActionRef binding with source='current_row' is valid only
  // inside a repeater_atom. Walk all repeaters first to build the
  // descendant set, then check each button atom's action bindings.
  const repeaterDescendants = new Set<string>()
  for (const node of Object.values(blob.atom_tree)) {
    if (node.atom_type !== "repeater_atom") continue
    if (!node.children) continue
    const stack: string[] = [...node.children]
    while (stack.length > 0) {
      const next = stack.pop()!
      if (repeaterDescendants.has(next)) continue
      repeaterDescendants.add(next)
      const child = blob.atom_tree[next]
      if (child && child.children) stack.push(...child.children)
    }
  }
  for (const [atomId, node] of Object.entries(blob.atom_tree)) {
    if (node.atom_type !== "button") continue
    const cfg = (node.config ?? {}) as Record<string, unknown>
    const action = cfg.action
    if (!action) continue
    if (repeaterDescendants.has(atomId)) continue
    for (const b of _extractActionBindings(action)) {
      if (b.source === "current_row") {
        const message =
          `Action binding "${String(b.name ?? "")}" uses current_row but ` +
          `this button is not inside a repeater.`
        if (!errorsByAtom[atomId]) errorsByAtom[atomId] = []
        errorsByAtom[atomId].push(message)
        errorList.push({
          atom_id: atomId,
          atom_type: node.atom_type,
          message,
        })
      }
    }
  }

  // WB-8 — variant-substrate validation. Two outputs:
  //   • variantWarnings: per-variant target_surface mismatch chips
  //     (authoring-time soft warning per Lock 3a Option B).
  //   • variantErrors: default_variant_id referential integrity +
  //     Lock 3a.2 (spaces_pin → Glance required) + Lock 3a.3
  //     (focus_canvas → Brief required). All blocking at Publish.
  const variantWarnings: Record<string, string[]> = {}
  const variantErrors: string[] = []
  const declaredVariantIds = new Set(
    blob.variants.map((v) => v.variant_id),
  )
  if (blob.default_variant_id) {
    if (!declaredVariantIds.has(blob.default_variant_id)) {
      variantErrors.push(
        `Default variant "${blob.default_variant_id}" does not reference a declared variant.`,
      )
    }
  }
  if (supportedSurfaces && supportedSurfaces.length > 0) {
    for (const v of blob.variants) {
      if (
        !variantTargetCompatibleWithSupportedSurfaces(
          v.target_surface,
          supportedSurfaces,
        )
      ) {
        if (!variantWarnings[v.variant_id]) {
          variantWarnings[v.variant_id] = []
        }
        variantWarnings[v.variant_id].push(
          `Target surface "${v.target_surface}" is incompatible with this widget's supported surfaces.`,
        )
      }
    }
    // Lock 3a.2 — spaces_pin requires Glance variant.
    if (
      supportedSurfaces.includes("spaces_pin") &&
      !declaredVariantIds.has("glance")
    ) {
      variantErrors.push(
        "Widget supports spaces_pin but no Glance variant is declared.",
      )
    }
    // Lock 3a.3 — focus_canvas requires Brief variant (when variants[] non-empty).
    if (
      supportedSurfaces.includes("focus_canvas") &&
      blob.variants.length > 0 &&
      !declaredVariantIds.has("brief")
    ) {
      variantErrors.push(
        "Widget supports focus_canvas but no Brief variant is declared.",
      )
    }
  }

  return {
    errorsByAtom,
    errorList,
    hasErrors:
      errorList.length > 0 || variantErrors.length > 0,
    variantWarnings,
    variantErrors,
  }
}


export function useWidgetValidation(
  blob: CompositionBlob | null,
  supportedSurfaces?: ReadonlyArray<string>,
): ValidationResult {
  return useMemo(
    () => validateCompositionBlob(blob, supportedSurfaces),
    // The supportedSurfaces array identity is the controlling key;
    // callers should memoize the array if they mutate the underlying
    // surfaces frequently. Spreading into deps would re-render too
    // aggressively on parent rerenders.
    [blob, supportedSurfaces],
  )
}
