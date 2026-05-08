/**
 * R-2.1 — DeliveryCardBody sub-component.
 *
 * "What about this delivery matters" block — service time +
 * location + ETA on line 3, then product/equipment bundle on line 4.
 * Extracted from DeliveryCard.tsx (lines 531-565 pre-R-2.1).
 *
 * Like DeliveryCardHeader, this renders INSIDE the parent's QuickEdit
 * click-button. See DeliveryCardHeader.tsx for the DOM nesting note.
 *
 * Wrapped via `registerComponent` at
 * `lib/visual-editor/registry/registrations/entity-card-sections.ts`.
 */
export interface DeliveryCardBodyProps {
  /** Composed time line ("11:00 Graveside" / "11:00 Church"). Empty
   *  string = no service time line rendered (ancillary/direct_ship). */
  timeLine: string
  /** ETA string. Only rendered when `showEta` is true. */
  eta: string | null
  /** Whether to render the ETA suffix. Driven by parent's serviceType
   *  check (graveside doesn't get ETA). */
  showEta: boolean
  /** Vault product name (e.g. "Monticello"). Null = product line skipped. */
  vaultType: string | null
  /** Equipment bundle name. Null = equipment line skipped. */
  equipmentType: string | null
}


/** R-2.1 — exported as `DeliveryCardBodyRaw`. */
export function DeliveryCardBodyRaw({
  timeLine,
  eta,
  showEta,
  vaultType,
  equipmentType,
}: DeliveryCardBodyProps) {
  return (
    <>
      {/* Line 3 — service time · location · ETA (compact, mono for
          numeric anchor). */}
      {timeLine && (
        <div
          className="mt-0.5 truncate text-body-sm text-content-base"
          data-slot="dispatch-card-timeline"
        >
          <span className="font-mono tabular-nums">{timeLine}</span>
          {showEta && eta && (
            <span className="text-content-muted">
              {" · ETA "}
              <span className="font-mono tabular-nums">{eta}</span>
            </span>
          )}
        </div>
      )}

      {/* Line 4 — Product · Equipment bundle (caption, muted). */}
      {(vaultType || equipmentType) && (
        <div
          className="mt-0.5 truncate text-caption text-content-muted"
          data-slot="dispatch-card-product"
        >
          {vaultType && <span>{vaultType}</span>}
          {vaultType && equipmentType && <span>{" · "}</span>}
          {equipmentType && <span>{equipmentType}</span>}
        </div>
      )}
    </>
  )
}
