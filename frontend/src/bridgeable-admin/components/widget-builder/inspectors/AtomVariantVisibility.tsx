/**
 * AtomVariantVisibility — WB-8 per-atom visible_in_variants chip-toggle.
 *
 * Per Lock 2a.5: multi-select chip group. Empty selection = "visible
 * in ALL variants the widget supports" sentinel state (matches schema
 * default-visibility semantics at composition-blob.ts:82).
 *
 * Mounts inside the per-atom inspector when an atom is selected (NOT
 * the root). Lists only the variants the widget actually declares.
 */
import { cn } from "@/lib/utils"
import type {
  CompositionBlob,
  VariantId,
} from "@/lib/widget-builder/types/composition-blob"

import { InspectorField, InspectorSection } from "./inspector-primitives"
import type { UseVariantAuthoringResult } from "../useVariantAuthoring"


const VARIANT_LABELS: Record<VariantId, string> = {
  glance: "Glance",
  brief: "Brief",
  detail: "Detail",
  deep: "Deep",
}


export interface AtomVariantVisibilityProps {
  blob: CompositionBlob
  atomId: string
  variantAuthoring: UseVariantAuthoringResult
}


export function AtomVariantVisibility({
  blob,
  atomId,
  variantAuthoring,
}: AtomVariantVisibilityProps) {
  const atom = blob.atom_tree[atomId]
  if (!atom) return null
  const declared = blob.variants
  if (declared.length === 0) {
    return (
      <InspectorSection title="Visible in variants">
        <div
          data-testid="atom-variant-visibility-empty"
          className="rounded-md border border-dashed border-border-subtle px-2 py-1 text-caption text-content-muted"
        >
          Declare variants in the widget Variants section first.
        </div>
      </InspectorSection>
    )
  }

  const selected = new Set<string>(atom.visible_in_variants ?? [])
  const allVariants = selected.size === 0

  return (
    <InspectorSection title="Visible in variants">
      <InspectorField label="Variants">
        <div
          data-testid="atom-variant-visibility"
          data-mode={allVariants ? "all" : "explicit"}
          className="flex flex-wrap gap-1"
        >
          {declared.map((v) => {
            const isSelected = selected.has(v.variant_id)
            return (
              <button
                key={v.variant_id}
                type="button"
                data-testid={`atom-variant-visibility-chip-${v.variant_id}`}
                data-selected={isSelected ? "true" : "false"}
                aria-pressed={isSelected}
                onClick={() =>
                  variantAuthoring.toggleAtomVariantVisibility(
                    atomId,
                    v.variant_id as VariantId,
                  )
                }
                className={cn(
                  "rounded-full px-2 py-0.5 text-caption transition-colors",
                  isSelected
                    ? "bg-accent text-accent-foreground"
                    : allVariants
                      ? "bg-surface-raised text-content-muted opacity-70"
                      : "bg-surface-raised text-content-muted hover:bg-accent-subtle",
                )}
              >
                {VARIANT_LABELS[v.variant_id as VariantId] ?? v.variant_id}
              </button>
            )
          })}
        </div>
      </InspectorField>
      {allVariants ? (
        <div
          data-testid="atom-variant-visibility-all-variants-hint"
          className="text-caption text-content-subtle"
        >
          Visible in every variant (no selection = all).
        </div>
      ) : null}
    </InspectorSection>
  )
}
