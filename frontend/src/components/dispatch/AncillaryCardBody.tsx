/**
 * R-2.1 — AncillaryCardBody sub-component.
 *
 * Destination funeral home + city line. Extracted from
 * AncillaryCard.tsx (lines 181-192 pre-R-2.1). Renders INSIDE the
 * parent's QuickEdit click-button.
 *
 * Wrapped via `registerComponent` at
 * `lib/visual-editor/registry/registrations/entity-card-sections.ts`.
 */


export interface AncillaryCardBodyProps {
  /** Funeral home name. */
  fh: string
  /** City. Empty = no suffix. */
  city: string
}


/** R-2.1 — exported as `AncillaryCardBodyRaw`. */
export function AncillaryCardBodyRaw({ fh, city }: AncillaryCardBodyProps) {
  return (
    <div
      className="mt-0.5 truncate text-caption text-content-muted"
      data-slot="dispatch-ancillary-card-destination"
    >
      {fh}
      {city && (
        <span>
          {" · "}
          {city}
        </span>
      )}
    </div>
  )
}
