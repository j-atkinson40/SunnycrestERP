/**
 * VariantsInspectorSection — WB-8 widget-root inspector CRUD surface.
 *
 * Replaces the WB-4b read-only list. Per Lock 2a sub-decisions:
 *   • declare-toggle for each canonical variant (picker-constrained
 *     to glance / brief / detail / deep per Lock 2a.1).
 *   • Inline rename (variant_name).
 *   • Delete with confirmation; default-variant deletion blocked
 *     (operator must promote another variant first).
 *   • Reorder via up/down buttons (drag-handle equivalent for the
 *     WB-4a flex-stack pattern — keeps tests JSDOM-compatible).
 *   • Target_surface picker (3-value enum per Lock 2a.2).
 *   • Canonical_dimensions width/height inputs with surface-default
 *     fallback display.
 *   • Default-variant radio per row.
 *   • Per-variant warning chip when target_surface is incompatible
 *     with widget supported_surfaces (Lock 3a Option B at draft).
 */
import { ChevronDown, ChevronUp, Trash2 } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type {
  CompositionBlob,
  TargetSurface,
  VariantId,
} from "@/lib/widget-builder/types/composition-blob"
import { surfaceDefaultDimensions } from "@/lib/widget-builder/types/surface-mapping"

import {
  InspectorField,
  InspectorSection,
  SelectField,
  TextFieldUncontrolled,
} from "./inspector-primitives"
import {
  CANONICAL_VARIANT_IDS,
  type UseVariantAuthoringResult,
} from "../useVariantAuthoring"


const TARGET_SURFACE_OPTIONS = [
  { value: "focus_canvas", label: "Focus canvas" },
  { value: "page_canvas", label: "Page canvas" },
  { value: "palette_preview", label: "Palette preview" },
] as const


const VARIANT_LABELS: Record<VariantId, string> = {
  glance: "Glance",
  brief: "Brief",
  detail: "Detail",
  deep: "Deep",
}


export interface VariantsInspectorSectionProps {
  blob: CompositionBlob
  variantAuthoring: UseVariantAuthoringResult
  variantWarnings?: Record<string, string[]>
  variantErrors?: string[]
}


export function VariantsInspectorSection({
  blob,
  variantAuthoring,
  variantWarnings,
  variantErrors,
}: VariantsInspectorSectionProps) {
  const declaredIds = new Set(blob.variants.map((v) => v.variant_id))
  const undeclared = CANONICAL_VARIANT_IDS.filter(
    (vid) => !declaredIds.has(vid),
  )
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  return (
    <InspectorSection title="Variants">
      <div
        data-testid="widget-builder-variants-inspector"
        className="flex flex-col gap-2"
      >
        {variantErrors && variantErrors.length > 0 ? (
          <ul
            data-testid="widget-builder-variants-inspector-errors"
            className="rounded-md border border-status-error/30 bg-status-error-muted px-2 py-1 text-caption text-status-error"
          >
            {variantErrors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        ) : null}

        {blob.variants.length === 0 ? (
          <div
            data-testid="widget-builder-variants-inspector-empty"
            className="rounded-md border border-dashed border-border-subtle px-2 py-2 text-caption text-content-muted"
          >
            Create your first variant
          </div>
        ) : null}

        {blob.variants.map((v, idx) => {
          const isDefault = blob.default_variant_id === v.variant_id
          const warnings = variantWarnings?.[v.variant_id] ?? []
          const dims =
            v.canonical_dimensions ??
            surfaceDefaultDimensions(v.target_surface)
          const usingFallback = v.canonical_dimensions === undefined
          return (
            <div
              key={v.variant_id}
              data-testid={`widget-builder-variant-row-${v.variant_id}`}
              data-default={isDefault ? "true" : "false"}
              className={cn(
                "rounded-md border border-border-subtle bg-surface-raised p-2",
                isDefault && "border-accent/40",
              )}
            >
              <div className="mb-1 flex items-center gap-2">
                <div className="flex-1 text-body-sm font-medium text-content-base">
                  {VARIANT_LABELS[v.variant_id as VariantId] ?? v.variant_id}
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  data-testid={`widget-builder-variant-row-${v.variant_id}-up`}
                  disabled={idx === 0}
                  onClick={() =>
                    variantAuthoring.reorderVariant(v.variant_id, idx - 1)
                  }
                  aria-label="Move up"
                >
                  <ChevronUp size={14} />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  data-testid={`widget-builder-variant-row-${v.variant_id}-down`}
                  disabled={idx === blob.variants.length - 1}
                  onClick={() =>
                    variantAuthoring.reorderVariant(v.variant_id, idx + 1)
                  }
                  aria-label="Move down"
                >
                  <ChevronDown size={14} />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  data-testid={`widget-builder-variant-row-${v.variant_id}-delete`}
                  disabled={isDefault}
                  title={
                    isDefault
                      ? "Promote another variant before deleting the default"
                      : undefined
                  }
                  onClick={() => setConfirmDelete(v.variant_id)}
                  aria-label="Delete variant"
                >
                  <Trash2 size={14} />
                </Button>
              </div>

              {confirmDelete === v.variant_id ? (
                <div
                  data-testid={`widget-builder-variant-row-${v.variant_id}-confirm-delete`}
                  className="mb-2 rounded-md border border-status-warning/30 bg-status-warning-muted px-2 py-1 text-caption text-status-warning"
                >
                  Delete {VARIANT_LABELS[v.variant_id as VariantId]}?
                  <div className="mt-1 flex gap-2">
                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      data-testid={`widget-builder-variant-row-${v.variant_id}-confirm-delete-yes`}
                      onClick={() => {
                        variantAuthoring.removeVariant(v.variant_id)
                        setConfirmDelete(null)
                      }}
                    >
                      Delete
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setConfirmDelete(null)}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : null}

              <InspectorField label="Display name">
                <TextFieldUncontrolled
                  testId={`widget-builder-variant-row-${v.variant_id}-name`}
                  value={v.variant_name}
                  placeholder={VARIANT_LABELS[v.variant_id as VariantId]}
                  onCommit={(next) =>
                    variantAuthoring.renameVariant(
                      v.variant_id,
                      next || VARIANT_LABELS[v.variant_id as VariantId],
                    )
                  }
                />
              </InspectorField>

              <InspectorField label="Target surface">
                <SelectField
                  testId={`widget-builder-variant-row-${v.variant_id}-target-surface`}
                  value={v.target_surface}
                  onChange={(next) =>
                    variantAuthoring.setTargetSurface(
                      v.variant_id,
                      next as TargetSurface,
                    )
                  }
                  options={TARGET_SURFACE_OPTIONS}
                />
              </InspectorField>

              <div className="flex gap-2">
                <InspectorField label="Width">
                  <TextFieldUncontrolled
                    testId={`widget-builder-variant-row-${v.variant_id}-width`}
                    value={String(dims.width)}
                    onCommit={(next) => {
                      const n = parseInt(next, 10)
                      if (!Number.isFinite(n) || n <= 0) return
                      variantAuthoring.setCanonicalDimensions(v.variant_id, {
                        width: n,
                        height: dims.height,
                      })
                    }}
                  />
                </InspectorField>
                <InspectorField label="Height">
                  <TextFieldUncontrolled
                    testId={`widget-builder-variant-row-${v.variant_id}-height`}
                    value={String(dims.height)}
                    onCommit={(next) => {
                      const n = parseInt(next, 10)
                      if (!Number.isFinite(n) || n <= 0) return
                      variantAuthoring.setCanonicalDimensions(v.variant_id, {
                        width: dims.width,
                        height: n,
                      })
                    }}
                  />
                </InspectorField>
              </div>
              {usingFallback ? (
                <div
                  data-testid={`widget-builder-variant-row-${v.variant_id}-dims-fallback`}
                  className="text-caption text-content-subtle"
                >
                  Using surface-default dimensions
                </div>
              ) : null}

              <div className="mt-2 flex items-center gap-2">
                <input
                  type="radio"
                  data-testid={`widget-builder-variant-row-${v.variant_id}-default-radio`}
                  checked={isDefault}
                  onChange={() =>
                    variantAuthoring.setDefaultVariantId(v.variant_id)
                  }
                  id={`variant-default-${v.variant_id}`}
                />
                <label
                  htmlFor={`variant-default-${v.variant_id}`}
                  className="text-caption text-content-muted"
                >
                  Default for bridge consumers
                </label>
              </div>

              {warnings.length > 0 ? (
                <ul
                  data-testid={`widget-builder-variant-row-${v.variant_id}-warnings`}
                  className="mt-2 rounded-md border border-status-warning/30 bg-status-warning-muted px-2 py-1 text-caption text-status-warning"
                >
                  {warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          )
        })}

        {undeclared.length > 0 ? (
          <div
            data-testid="widget-builder-variants-inspector-add-row"
            className="flex flex-wrap gap-1 pt-1"
          >
            <span className="text-caption text-content-muted">Add:</span>
            {undeclared.map((vid) => (
              <Button
                key={vid}
                type="button"
                variant="secondary"
                size="sm"
                data-testid={`widget-builder-variants-inspector-add-${vid}`}
                onClick={() => variantAuthoring.declareVariant(vid)}
              >
                + {VARIANT_LABELS[vid]}
              </Button>
            ))}
          </div>
        ) : null}
      </div>
    </InspectorSection>
  )
}
