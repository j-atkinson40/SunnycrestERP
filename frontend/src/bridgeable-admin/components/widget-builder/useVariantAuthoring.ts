/**
 * useVariantAuthoring — WB-8 variant CRUD state + mutators.
 *
 * Wraps a draft CompositionBlob + the page-level setDraft mutator and
 * provides:
 *   • currentVariantId — the operator's actively-previewed variant
 *     (controlled via the top-bar VariantSwitcher). `undefined` means
 *     "all atoms" preview.
 *   • setCurrentVariantId — switcher dispatch.
 *   • CRUD helpers — declareVariant, removeVariant, renameVariant,
 *     setTargetSurface, setCanonicalDimensions, setDefaultVariantId,
 *     reorderVariant.
 *   • Per-atom helpers — toggleAtomVariantVisibility,
 *     setAtomVariantVisibility.
 *
 * Composes with WB-4a's auto-save substrate via the existing setDraft
 * mutator pipeline — every change flows through the draft setter
 * unchanged. No new persistence path.
 */
import { useCallback, useState } from "react"

import type {
  CompositionBlob,
  TargetSurface,
  VariantDefinition,
  VariantId,
} from "@/lib/widget-builder/types/composition-blob"


export type DraftSetter = (next: CompositionBlob) => void


const CANONICAL_VARIANT_NAME: Record<VariantId, string> = {
  glance: "Glance",
  brief: "Brief",
  detail: "Detail",
  deep: "Deep",
}


/** WB-8 canonical variant_id vocabulary (per Lock 2a.1). */
export const CANONICAL_VARIANT_IDS: ReadonlyArray<VariantId> = [
  "glance",
  "brief",
  "detail",
  "deep",
]


export interface UseVariantAuthoringResult {
  currentVariantId: VariantId | undefined
  setCurrentVariantId: (id: VariantId | undefined) => void
  declareVariant: (
    variantId: VariantId,
    options?: { target_surface?: TargetSurface; variant_name?: string },
  ) => void
  removeVariant: (variantId: string) => void
  renameVariant: (variantId: string, next: string) => void
  setTargetSurface: (variantId: string, next: TargetSurface) => void
  setCanonicalDimensions: (
    variantId: string,
    dims: { width: number; height: number } | null,
  ) => void
  setDefaultVariantId: (variantId: string | null) => void
  reorderVariant: (variantId: string, toIndex: number) => void
  toggleAtomVariantVisibility: (atomId: string, variantId: VariantId) => void
  setAtomVariantVisibility: (
    atomId: string,
    variantIds: VariantId[] | undefined,
  ) => void
}


function _replaceVariants(
  blob: CompositionBlob,
  variants: VariantDefinition[],
): CompositionBlob {
  return { ...blob, variants }
}


export function useVariantAuthoring(
  blob: CompositionBlob | null,
  setDraft: DraftSetter,
): UseVariantAuthoringResult {
  const [currentVariantId, setCurrentVariantId] = useState<
    VariantId | undefined
  >(undefined)

  const declareVariant = useCallback(
    (
      variantId: VariantId,
      options?: { target_surface?: TargetSurface; variant_name?: string },
    ) => {
      if (!blob) return
      // No-op if already declared.
      if (blob.variants.some((v) => v.variant_id === variantId)) return
      const next: VariantDefinition = {
        variant_id: variantId,
        variant_name:
          options?.variant_name ?? CANONICAL_VARIANT_NAME[variantId],
        target_surface: options?.target_surface ?? "focus_canvas",
      }
      setDraft(_replaceVariants(blob, [...blob.variants, next]))
    },
    [blob, setDraft],
  )

  const removeVariant = useCallback(
    (variantId: string) => {
      if (!blob) return
      // Block removal of the current default — operator must promote
      // another variant first.
      if (blob.default_variant_id === variantId) return
      const next = blob.variants.filter((v) => v.variant_id !== variantId)
      // Cascade-clean any atoms with visible_in_variants references.
      const nextAtomTree = { ...blob.atom_tree }
      for (const [aid, node] of Object.entries(nextAtomTree)) {
        if (!node.visible_in_variants) continue
        const filtered = node.visible_in_variants.filter(
          (vid) => vid !== variantId,
        )
        if (filtered.length === node.visible_in_variants.length) continue
        nextAtomTree[aid] = {
          ...node,
          visible_in_variants:
            filtered.length > 0 ? filtered : undefined,
        }
      }
      setDraft({ ...blob, variants: next, atom_tree: nextAtomTree })
    },
    [blob, setDraft],
  )

  const renameVariant = useCallback(
    (variantId: string, next: string) => {
      if (!blob) return
      const updated = blob.variants.map((v) =>
        v.variant_id === variantId ? { ...v, variant_name: next } : v,
      )
      setDraft(_replaceVariants(blob, updated))
    },
    [blob, setDraft],
  )

  const setTargetSurface = useCallback(
    (variantId: string, next: TargetSurface) => {
      if (!blob) return
      const updated = blob.variants.map((v) =>
        v.variant_id === variantId ? { ...v, target_surface: next } : v,
      )
      setDraft(_replaceVariants(blob, updated))
    },
    [blob, setDraft],
  )

  const setCanonicalDimensions = useCallback(
    (
      variantId: string,
      dims: { width: number; height: number } | null,
    ) => {
      if (!blob) return
      const updated = blob.variants.map((v) => {
        if (v.variant_id !== variantId) return v
        if (dims === null) {
          const { canonical_dimensions: _omit, ...rest } = v
          return rest
        }
        return { ...v, canonical_dimensions: dims }
      })
      setDraft(_replaceVariants(blob, updated))
    },
    [blob, setDraft],
  )

  const setDefaultVariantId = useCallback(
    (variantId: string | null) => {
      if (!blob) return
      if (variantId === null) {
        const { default_variant_id: _omit, ...rest } = blob
        setDraft({ ...rest })
        return
      }
      // Defensive: only accept references to declared variants.
      if (!blob.variants.some((v) => v.variant_id === variantId)) return
      setDraft({ ...blob, default_variant_id: variantId })
    },
    [blob, setDraft],
  )

  const reorderVariant = useCallback(
    (variantId: string, toIndex: number) => {
      if (!blob) return
      const fromIndex = blob.variants.findIndex(
        (v) => v.variant_id === variantId,
      )
      if (fromIndex < 0) return
      const clamped = Math.max(0, Math.min(toIndex, blob.variants.length - 1))
      if (clamped === fromIndex) return
      const next = blob.variants.slice()
      const [moved] = next.splice(fromIndex, 1)
      next.splice(clamped, 0, moved)
      setDraft(_replaceVariants(blob, next))
    },
    [blob, setDraft],
  )

  const toggleAtomVariantVisibility = useCallback(
    (atomId: string, variantId: VariantId) => {
      if (!blob) return
      const node = blob.atom_tree[atomId]
      if (!node) return
      const current = node.visible_in_variants ?? []
      const next = current.includes(variantId)
        ? current.filter((v) => v !== variantId)
        : [...current, variantId]
      // Empty selection → drop the field entirely (default-all sentinel
      // per Lock 2a.5 — visible in every variant the widget supports).
      const updated = {
        ...node,
        visible_in_variants: next.length > 0 ? next : undefined,
      }
      setDraft({
        ...blob,
        atom_tree: { ...blob.atom_tree, [atomId]: updated },
      })
    },
    [blob, setDraft],
  )

  const setAtomVariantVisibility = useCallback(
    (atomId: string, variantIds: VariantId[] | undefined) => {
      if (!blob) return
      const node = blob.atom_tree[atomId]
      if (!node) return
      const updated = {
        ...node,
        visible_in_variants:
          variantIds && variantIds.length > 0 ? variantIds : undefined,
      }
      setDraft({
        ...blob,
        atom_tree: { ...blob.atom_tree, [atomId]: updated },
      })
    },
    [blob, setDraft],
  )

  return {
    currentVariantId,
    setCurrentVariantId,
    declareVariant,
    removeVariant,
    renameVariant,
    setTargetSurface,
    setCanonicalDimensions,
    setDefaultVariantId,
    reorderVariant,
    toggleAtomVariantVisibility,
    setAtomVariantVisibility,
  }
}
