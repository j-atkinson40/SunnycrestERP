/**
 * R-2.1 — DeliveryCardHeader sub-component.
 *
 * Identity block of the DeliveryCard: optional driver-start-time
 * eyebrow + funeral-home headline + cemetery line. Extracted from
 * DeliveryCard.tsx (lines 471-529 pre-R-2.1) so that the canonical
 * runtime-editor sub-section registration pattern can wrap it at a
 * single import site.
 *
 * Wrapped via `registerComponent` at
 * `lib/visual-editor/registry/registrations/entity-card-sections.ts`
 * — the wrapper emits a `data-component-name="delivery-card.header"`
 * boundary div with `display: contents` so layout is unaffected and
 * SelectionOverlay's capture-phase walker can resolve clicks to this
 * sub-section.
 *
 * **DOM nesting note**: this sub-component renders INSIDE the parent
 * card's QuickEdit click-button (DeliveryCard.tsx wraps header + body
 * inside `<button data-slot="dispatch-card-body">`). SelectionOverlay's
 * preventDefault on edit-mode clicks blocks the button's onClick from
 * firing while a sub-section click resolves; production view-mode
 * semantics unchanged. Documented in /tmp/r2_1_subsection_scope.md
 * Section 6.
 *
 * **Import discipline**: per ESLint rule
 * `bridgeable/entity-card-wrapped-import`, every consumer site should
 * import the wrapped `DeliveryCardHeader` from
 * `@/lib/visual-editor/registry/registrations/entity-card-sections`.
 * Importing `DeliveryCardHeaderRaw` directly bypasses the runtime
 * registration and breaks click-to-edit.
 */
import { cn } from "@/lib/utils"


export interface DeliveryCardHeaderProps {
  /** Pre-formatted "Start 6:30am" eyebrow string. Null = not displayed. */
  startTime: string | null
  /** Funeral home name — the engraved-stone identity headline. */
  fh: string
  /** Cemetery name. Empty string = line not rendered. */
  cemetery: string
  /** Cemetery city — appended to cemetery line when present. */
  city: string
}


/** R-2.1 — exported as `DeliveryCardHeaderRaw`; the wrapped version
 *  (carrying `data-component-name="delivery-card.header"`) is the
 *  default export from
 *  `@/lib/visual-editor/registry/registrations/entity-card-sections`. */
export function DeliveryCardHeaderRaw({
  startTime,
  fh,
  cemetery,
  city,
}: DeliveryCardHeaderProps) {
  return (
    <>
      {/* Phase 4.3.3 eyebrow — driver start time when set. Tiny
          uppercase muted label sits above the FH headline so the
          primary text hierarchy is unchanged. NULL value =
          implicit tenant default = not displayed. */}
      {startTime && (
        <div
          data-slot="dispatch-card-start-time"
          className={cn(
            "text-micro uppercase tracking-wider text-content-muted",
            "font-mono leading-tight",
          )}
          aria-label={`Driver start time ${startTime.replace(/^Start /, "")}`}
        >
          {startTime}
        </div>
      )}

      {/* Line 1 — funeral home (the headline; identifies the job).
          Aesthetic Arc Session 4 — Pattern 2 card material treatment
          + DL §4 typeface roles: proper nouns (people, businesses,
          places) carry the engraving register via font-display
          (Fraunces). FH name is THE identifying word on the card. */}
      <div
        className={cn(
          "truncate text-body-sm font-medium leading-tight text-content-strong",
          "font-display",
        )}
        data-slot="dispatch-card-fh"
        title={fh}
      >
        {fh}
      </div>

      {/* Line 2 — cemetery · city */}
      {cemetery && (
        <div
          className="mt-0.5 truncate text-body-sm text-content-base"
          data-slot="dispatch-card-cemetery"
        >
          {cemetery}
          {city && (
            <span className="text-content-muted">
              {" · "}
              {city}
            </span>
          )}
        </div>
      )}
    </>
  )
}
