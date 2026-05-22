/**
 * VariantSwitcher — WB-8 top-bar variant preview switcher (Lock 2a.7).
 *
 * Segmented control with 5 segments: "All atoms" (variantId=undefined,
 * the catalog-preview / unscoped render path) plus the 4 canonical
 * variants (Glance / Brief / Detail / Deep). Only declared variants
 * are clickable; undeclared variants render greyed-out.
 *
 * Live preview discipline (Lock 5a): switcher dispatches into the
 * page-level state. AtomRenderer's variant filter applies; data layer
 * is passive (WB-5 fetch state unaffected — variantId is NOT a fetch
 * key).
 */
import { cn } from "@/lib/utils"
import type {
  CompositionBlob,
  VariantId,
} from "@/lib/widget-builder/types/composition-blob"

import { CANONICAL_VARIANT_IDS } from "./useVariantAuthoring"


export interface VariantSwitcherProps {
  blob: CompositionBlob | null
  currentVariantId: VariantId | undefined
  onChange: (next: VariantId | undefined) => void
}


const VARIANT_LABELS: Record<VariantId, string> = {
  glance: "Glance",
  brief: "Brief",
  detail: "Detail",
  deep: "Deep",
}


export function VariantSwitcher({
  blob,
  currentVariantId,
  onChange,
}: VariantSwitcherProps) {
  const declaredIds = new Set<string>(
    (blob?.variants ?? []).map((v) => v.variant_id),
  )
  const hasAnyDeclared = declaredIds.size > 0

  return (
    <div
      data-testid="widget-builder-variant-switcher"
      role="tablist"
      aria-label="Preview variant"
      className="inline-flex items-center gap-0 rounded-md border border-border-subtle bg-surface-raised p-0.5"
    >
      <button
        type="button"
        role="tab"
        aria-selected={currentVariantId === undefined}
        data-testid="widget-builder-variant-switcher-all"
        data-active={currentVariantId === undefined ? "true" : "false"}
        onClick={() => onChange(undefined)}
        className={cn(
          "rounded-sm px-2 py-1 text-caption transition-colors",
          currentVariantId === undefined
            ? "bg-accent-subtle text-accent"
            : "text-content-muted hover:text-content-base",
        )}
      >
        All atoms
      </button>
      {CANONICAL_VARIANT_IDS.map((vid) => {
        const declared = declaredIds.has(vid)
        const active = currentVariantId === vid
        return (
          <button
            key={vid}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={!declared}
            data-testid={`widget-builder-variant-switcher-${vid}`}
            data-active={active ? "true" : "false"}
            data-declared={declared ? "true" : "false"}
            onClick={() => declared && onChange(vid)}
            className={cn(
              "rounded-sm px-2 py-1 text-caption transition-colors",
              active
                ? "bg-accent-subtle text-accent"
                : declared
                  ? "text-content-muted hover:text-content-base"
                  : "cursor-not-allowed text-content-subtle opacity-60",
            )}
          >
            {VARIANT_LABELS[vid]}
          </button>
        )
      })}
      {!hasAnyDeclared ? (
        <span
          data-testid="widget-builder-variant-switcher-empty"
          className="px-2 text-caption text-content-subtle"
        >
          No variants declared
        </span>
      ) : null}
    </div>
  )
}
