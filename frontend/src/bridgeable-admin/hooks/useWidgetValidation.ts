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


export interface ValidationResult {
  /** atom_id → list of error messages (empty list = clean). */
  errorsByAtom: Record<string, string[]>
  /** Flattened list with (atom_id, msg) pairs in atom_tree iteration order. */
  errorList: { atom_id: string; atom_type: AtomType; message: string }[]
  hasErrors: boolean
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


export function validateCompositionBlob(
  blob: CompositionBlob | null,
): ValidationResult {
  if (!blob) {
    return { errorsByAtom: {}, errorList: [], hasErrors: false }
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
  return {
    errorsByAtom,
    errorList,
    hasErrors: errorList.length > 0,
  }
}


export function useWidgetValidation(
  blob: CompositionBlob | null,
): ValidationResult {
  return useMemo(() => validateCompositionBlob(blob), [blob])
}
