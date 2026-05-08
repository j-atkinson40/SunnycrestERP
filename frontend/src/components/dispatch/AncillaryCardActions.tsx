/**
 * R-2.1 — AncillaryCardActions sub-component.
 *
 * Optional icon row (only renders when a note exists today).
 * Extracted from AncillaryCard.tsx (lines 195-213 pre-R-2.1).
 * Renders below + outside the parent's QuickEdit click-button.
 *
 * Marked `optional: true` in the registration — the parent's render
 * decides at runtime whether to mount this section based on data
 * presence (note exists). Empty render returns null so the icon
 * row collapses entirely.
 *
 * R-2.1 also accepts an optional `buttonSlugs` array for R-4 button
 * composition (parallel to DeliveryCardActions). When non-empty,
 * the section renders even without a note.
 *
 * Wrapped via `registerComponent` at
 * `lib/visual-editor/registry/registrations/entity-card-sections.ts`.
 */
import { StickyNoteIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { RegisteredButton } from "@/lib/runtime-host/buttons/RegisteredButton"

import { IconTooltip } from "./_shared"


export interface AncillaryCardActionsProps {
  /** Driver note. Empty string = no note icon (and section may not render). */
  note: string
  /** R-2.1 — optional list of registered button slugs. */
  buttonSlugs?: string[]
}


/** R-2.1 — exported as `AncillaryCardActionsRaw`. */
export function AncillaryCardActionsRaw({
  note,
  buttonSlugs,
}: AncillaryCardActionsProps) {
  const hasButtons = buttonSlugs && buttonSlugs.length > 0
  // Section is optional — collapse entirely if no content to show.
  if (!note && !hasButtons) return null

  return (
    <div
      data-slot="dispatch-ancillary-card-icon-row"
      className={cn(
        "flex items-center justify-end gap-0.5",
        "border-t border-border-subtle/60 px-2.5 py-1",
      )}
    >
      {hasButtons && (
        <div
          className="flex items-center gap-1 mr-auto"
          data-slot="dispatch-ancillary-card-button-row"
        >
          {buttonSlugs!.map((slug) => (
            <RegisteredButton key={slug} componentName={slug} />
          ))}
        </div>
      )}
      {note && (
        <IconTooltip
          icon={StickyNoteIcon}
          label={note}
          dataSlot="dispatch-ancillary-icon-note"
          highlight
        />
      )}
    </div>
  )
}
