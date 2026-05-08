/**
 * R-2.1 — AncillaryCardHeader sub-component.
 *
 * Product/type label headline. Extracted from AncillaryCard.tsx
 * (lines 167-177 pre-R-2.1). Renders INSIDE the parent's QuickEdit
 * click-button (same DOM nesting note as DeliveryCardHeader).
 *
 * Wrapped via `registerComponent` at
 * `lib/visual-editor/registry/registrations/entity-card-sections.ts`.
 */
import { cn } from "@/lib/utils"


export interface AncillaryCardHeaderProps {
  /** Resolved label (product_summary → vault_type → delivery_type). */
  label: string
}


/** R-2.1 — exported as `AncillaryCardHeaderRaw`. */
export function AncillaryCardHeaderRaw({ label }: AncillaryCardHeaderProps) {
  return (
    <div
      className={cn(
        "truncate text-body-sm font-medium leading-tight text-content-strong",
        "font-sans",
      )}
      data-slot="dispatch-ancillary-card-product"
      title={label}
    >
      {label}
    </div>
  )
}
