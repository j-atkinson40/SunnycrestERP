/**
 * DeliveryCard — single kanban card for the Dispatch Monitor.
 *
 * Phase 3.1 + 3.2 rebuild (2026-04-23, per James' operational
 * feedback on Phase 3). What changed from Phase 3:
 *   - Service-type color tints REMOVED. Dispatchers prioritize
 *     equipment context over service type as a visual cue.
 *   - Hole-dug is three-state non-nullable (unknown | yes | no).
 *     Cycles unknown → yes → no → unknown. Migration r50 backfilled
 *     all NULLs to 'unknown' + made the column NOT NULL.
 *   - Hole-dug + ancillary collapsed into a single status-indicator
 *     row. Same visual weight; both are the "what state is this in?"
 *     signal bank at the bottom of the card.
 *   - Primary text hierarchy (James' dispatcher mental model):
 *       1. Funeral home name (headline — identifies the job)
 *       2. Cemetery · City
 *       3. Service time · location · ETA  (e.g. "11:00 Church · ETA 12:00")
 *       4. Vault type · equipment hint
 *   - Secondary info compacted into an icon+tooltip row at the
 *     bottom: family name (User), driver note (StickyNote), chat
 *     activity (MessageCircle), cemetery section (MapPin) — each
 *     hidden when its data is empty. Hover / focus / tap-and-hold
 *     reveals the tooltip with the actual text.
 *   - Card target ~100-120px tall (down from ~180px in Phase 3).
 *   - Service-time + ETA ordering FIX (per user correction):
 *     service time first (anchor — that's when the service starts),
 *     ETA second (when driver arrives at cemetery after service
 *     ends). Matches "church at 11, graveside by 12" mental model.
 *
 * Card is a drag source via @dnd-kit useDraggable. Parent DndContext
 * (MonitorPage) handles drop. Clicking the card body (non-drag)
 * opens the QuickEditDialog via parent prop.
 *
 * Data throughout — shape matches `DeliveryDTO` from
 * `services/dispatch-service.ts`; type_config fields rendered
 * null-safe.
 */

import { useState } from "react"

import { useDraggable, useDroppable } from "@dnd-kit/core"
import { CSS } from "@dnd-kit/utilities"
import { useFocusDndActiveId } from "@/components/focus/FocusDndProvider"

import type {
  DeliveryDTO,
  HoleDugStatus,
} from "@/services/dispatch-service"
import { cn } from "@/lib/utils"

// R-2.1 — sub-section wrapped components imported from the
// registrations barrel. Each emits a data-component-name boundary
// div so SelectionOverlay can resolve clicks to the sub-section.
// Path 1 wrapping pattern parallels R-1.6.12 widget wrapping +
// R-2.0 entity-card wrapping.
import {
  DeliveryCardHeader,
  DeliveryCardBody,
  DeliveryCardActions,
} from "@/lib/visual-editor/registry/registrations/entity-card-sections"


export interface DeliveryCardProps {
  delivery: DeliveryDTO
  /** True when the card's schedule is finalized. Drives border style. */
  scheduleFinalized: boolean
  /** Count of ancillary deliveries attached to this parent delivery.
   *  0 hides the badge. */
  ancillaryCount?: number
  /** Click on card body → open quick-edit. */
  onOpenEdit?: (delivery: DeliveryDTO) => void
  /** Click on ancillary badge → toggle expansion. */
  onToggleAncillary?: (deliveryId: string) => void
  /** Click on hole-dug badge cycles unknown → yes → no → unknown. */
  onCycleHoleDug?: (delivery: DeliveryDTO, nextStatus: HoleDugStatus) => void
  /** Whether ancillary expanded (inline reveal below the card). */
  ancillaryExpanded?: boolean
  /** ARIA label override for the draggable wrapper. */
  ariaLabel?: string
  /** Visual density (Phase 4.2.1).
   *
   *  - "default" (Funeral Schedule Monitor widget): wider padding +
   *    generous status-row spacing. Tuned for the desktop Monitor
   *    widget's lane width (standalone kanban at full page width).
   *  - "compact" (Scheduling Focus Decide surface): tighter padding
   *    + smaller status-row icons. Keeps primary text hierarchy
   *    (FH / cemetery / time / product) fully readable while fitting
   *    more cards in the constrained Focus viewport (220px-wide
   *    driver columns vs. Monitor's 280px). All lines stay
   *    text-body-sm; the density knob only adjusts padding +
   *    icon-row scale, never hides content.
   *
   *  Prop-driven density (single component, reused across surfaces)
   *  over per-surface forks — matches the Session 3 primitive pattern
   *  (`<Button size="sm">` vs no prop) and keeps drag logic, type_config
   *  rendering, hole-dug + ancillary semantics identical across
   *  Monitor + Decide. */
  density?: "default" | "compact"
}


/** Next value in the hole-dug three-state cycle: unknown → yes → no →
 *  unknown. Phase 3.1 dropped the null state per operational feedback
 *  (nobody asked for a fourth option). Exported for tests. */
export function nextHoleDugStatus(curr: HoleDugStatus): HoleDugStatus {
  if (curr === "unknown") return "yes"
  if (curr === "yes") return "no"
  // curr === "no"
  return "unknown"
}


/** Short inline label for the service-time line — the SERVICE
 *  LOCATION (where the service takes place, derived from
 *  `type_config.service_type`). Not to be confused with equipment
 *  (that's `type_config.equipment_type`, a separate field).
 *
 *  - Graveside: service happens at the cemetery — no meeting point
 *    to label differently.
 *  - Church / Funeral Home: service starts at a different location;
 *    driver needs to know where.
 *  - Ancillary / direct_ship: not kanban deliveries; no service-time
 *    line rendered (handled by the `timeLine` being empty in the
 *    card render). */
function serviceTimeLocationLabel(t: string | null | undefined): string | null {
  switch (t) {
    case "graveside":     return "Graveside"
    case "church":        return "Church"
    case "funeral_home":  return "Funeral Home"
    default: return null  // ancillary / direct_ship use no time line
  }
}


/**
 * Format `delivery.driver_start_time` (backend "HH:MM:SS") for the
 * card's eyebrow display. Returns null when input is null/empty so
 * callers can `if (startTime)` to gate the rendering.
 *
 * Output: "Start 6:30am" / "Start 5:00am" — 12-hour with am/pm
 * suffix. Plex Mono on the digits via the inline span (caller-side)
 * for tabular alignment with the line 3 service-time digits.
 *
 * Phase 4.3.3 — only displayed when explicitly set on the delivery.
 * NULL → use tenant default → not displayed (the dispatcher's
 * default expectation is the tenant default, no need to repeat it
 * on every card).
 */
function formatStartTime(raw: string | null | undefined): string | null {
  if (!raw) return null
  const m = /^(\d{1,2}):(\d{2})(?::\d{2})?$/.exec(raw)
  if (!m) return null
  const hh = Number(m[1])
  const mm = m[2]
  if (Number.isNaN(hh) || hh < 0 || hh > 23) return null
  const period = hh < 12 ? "am" : "pm"
  const h12 = hh === 0 ? 12 : hh > 12 ? hh - 12 : hh
  return mm === "00" ? `Start ${h12}${period}` : `Start ${h12}:${mm}${period}`
}


/** R-2.0 — exported as `DeliveryCardRaw`; the wrapped version (carrying
 *  `data-component-name="delivery-card"` for runtime-editor click-to-
 *  edit) is the default export from
 *  `@/lib/visual-editor/registry/registrations/entity-cards`. The raw
 *  reference stays exported so the registration shim can wrap it; new
 *  call sites should import the wrapped `DeliveryCard` from the
 *  registrations barrel. */
export function DeliveryCardRaw({
  delivery,
  scheduleFinalized,
  ancillaryCount = 0,
  onOpenEdit,
  onToggleAncillary,
  onCycleHoleDug,
  ancillaryExpanded = false,
  ariaLabel,
  density = "default",
}: DeliveryCardProps) {
  const isCompact = density === "compact"
  const [isHovered, setIsHovered] = useState(false)
  const tc = delivery.type_config ?? {}
  const family = (tc.family_name as string | undefined) ?? ""
  const cemetery = (tc.cemetery_name as string | undefined) ?? ""
  const city = (tc.cemetery_city as string | undefined) ?? ""
  const section = (tc.cemetery_section as string | undefined) ?? ""
  const fh = (tc.funeral_home_name as string | undefined) ?? "—"
  const time = (tc.service_time as string | undefined) ?? null
  const eta = (tc.eta as string | undefined) ?? null
  const vaultType = (tc.vault_type as string | undefined) ?? null
  const equipmentType = (tc.equipment_type as string | undefined) ?? null
  const serviceType = (tc.service_type as string | undefined) ?? null
  const driverNote = (tc.driver_note as string | undefined) ?? ""
  const chatCount =
    typeof tc.chat_activity_count === "number" ? tc.chat_activity_count : 0
  // Phase 4.3.3 — explicit per-delivery driver start time. NULL =
  // use tenant default (DeliverySettings.default_driver_start_time);
  // not displayed when null. Format from backend is "HH:MM:SS";
  // we render "HH:MM" or 12-hour-AM/PM-ish label depending on
  // density. Eyebrow above the FH headline so it doesn't compete
  // with service-time anchor on line 3.
  const startTime = formatStartTime(delivery.driver_start_time)

  const {
    attributes,
    listeners,
    setNodeRef: setDragRef,
    transform,
    isDragging,
  } = useDraggable({
    id: `delivery:${delivery.id}`,
    data: { deliveryId: delivery.id },
  })

  // Phase 4.3b.3 — primary kanban deliveries with an assignee can
  // be the parent in an attach drop (a pool ancillary dragged onto
  // them becomes a paired ancillary). Standalone ancillaries +
  // unassigned primaries are NOT valid attach targets.
  //
  // useDroppable always runs (hooks must be unconditional); the
  // `disabled` flag gates the actual drop registration. dnd-kit
  // skips disabled droppables in collision detection.
  const canBeAttachParent =
    delivery.scheduling_type === "kanban" &&
    delivery.primary_assignee_id !== null
  const { setNodeRef: setDropRef, isOver } = useDroppable({
    id: `delivery-as-parent:${delivery.id}`,
    disabled: !canBeAttachParent,
    data: { parentDeliveryId: delivery.id },
  })

  // Combine the two refs onto the same DOM node — same element is
  // BOTH the drag source AND the drop target. dnd-kit canonical
  // pattern when one element serves both roles.
  const setNodeRef = (node: HTMLElement | null) => {
    setDragRef(node)
    setDropRef(node)
  }

  // Visual-feedback gate. The card lights up as a drop target ONLY
  // when an `ancillary:`-prefix drag is active (pool item OR
  // detached attached item being dragged). Other drag types
  // (delivery: kanban cards, widget: canvas widgets) don't trigger
  // attach feedback even if the over event fires, because attach
  // semantics don't apply to them.
  const activeDragId = useFocusDndActiveId()
  const isAncillaryDragActive = activeDragId?.startsWith("ancillary:") ?? false
  const showAttachFeedback =
    isOver && canBeAttachParent && isAncillaryDragActive

  const dragStyle = transform
    ? { transform: CSS.Translate.toString(transform) }
    : undefined

  // Aesthetic Arc Session 4.5 — Pattern 3 first channel: left-edge
  // flag wired to hole-dug semantic. 2px-wide signal-color bar at
  // the card's left edge — the card's primary status read at a
  // glance, before the dispatcher's eye reaches the bottom-rail
  // HoleDugBadge for the explicit icon.
  //
  // Mapping (DESIGN_LANGUAGE §11 Pattern 3 — two-channel rule):
  //   unknown → border-l-accent           (terracotta — needs attention)
  //   yes     → border-l-accent-confirmed (sage-green — confirmed,
  //                                        architectural-stamp register;
  //                                        distinct from --status-success
  //                                        which drives Alert/StatusPill)
  //   no      → border-l-transparent      (no flag — explicit "no hole" is
  //                                        not an attention state, the
  //                                        bottom badge carries the read)
  //
  // Pre-Session-4.5: 3px wide, status-success for confirmed.
  // Session 4.5: 2px canonical (per Pattern 3 doc); accent-confirmed
  // (per §3 token block + Pattern 3 doc-spec).
  //
  // The two-channel composition: flag (color signal + press-shadow
  // peripheral attention) + bottom badge (jewel-set icon, deliberate
  // interaction). Same data, two reads at different attention scales.
  const flagColorClass =
    delivery.hole_dug_status === "unknown"
      ? "border-l-accent"
      : delivery.hole_dug_status === "yes"
        ? "border-l-accent-confirmed"
        : "border-l-transparent"

  // Aesthetic Arc Session 4.5 + 4.6 — Pattern 2 + Pattern 3 composite
  // box-shadow. Cards read as physical material objects rather than
  // outlined panels:
  //   • inset 0 1px 0 var(--card-edge-highlight)  → top-edge catch-light
  //   • inset 0 -1px 0 var(--card-edge-shadow)    → bottom-edge shadow
  //   • var(--card-ambient-shadow)                 → lift from substrate
  //   • inset 1px 0 0 var(--flag-press-shadow)    → right-of-flag pressed
  //                                                  (only when flag exists)
  //   • var(--shadow-level-1)                      → existing material edges
  //
  // The four material tokens are MODE-AWARE (Session 4.6 calibration
  // after Session 4.5 single-value-across-modes failed visual
  // verification). Light mode: white-45% top highlight, black-20%
  // bottom edge, 8px/20px/-4px black-18% ambient. Dark mode:
  // transparent top highlight (defers to shadow-level-1's existing
  // 3px 90% warm top), black-50% bottom edge, 8px/24px/-4px black-45%
  // ambient. See DL §3 "Card material treatment tokens" + §11
  // Pattern 2 for the per-token mode-aware values + rationale.
  //
  // Hover variant lifts level-1 → level-2 (more atmosphere). Edge +
  // ambient + flag-press components carry through unchanged across
  // hover state.
  // Pre-Session-4.5: only shadow-level-1, read as flat panel.
  // Session 4.5: single-value tokens, still flat in light mode.
  // Session 4.6: mode-aware values, both modes pass visual fidelity.
  const hasFlag = delivery.hole_dug_status !== "no"
  const cardMaterialShadow = [
    hasFlag && "inset 1px 0 0 var(--flag-press-shadow)",
    "inset 0 1px 0 var(--card-edge-highlight)",
    "inset 0 -1px 0 var(--card-edge-shadow)",
    "var(--card-ambient-shadow)",
    "var(--shadow-level-1)",
  ].filter(Boolean).join(", ")
  const cardMaterialShadowHover = [
    hasFlag && "inset 1px 0 0 var(--flag-press-shadow)",
    "inset 0 1px 0 var(--card-edge-highlight)",
    "inset 0 -1px 0 var(--card-edge-shadow)",
    "var(--card-ambient-shadow)",
    "var(--shadow-level-2)",
  ].filter(Boolean).join(", ")

  // Compose the compact service-time line. Examples (user spec):
  //   "11:00 Graveside"
  //   "11:00 Church · ETA 12:00"
  //   "11:00 Funeral Home · ETA 12:00"
  // Service time FIRST (anchor — when service starts). ETA SECOND
  // (when driver arrives at cemetery AFTER service ends).
  const timeLocLabel = serviceTimeLocationLabel(serviceType)
  const timeLineParts: string[] = []
  if (time) timeLineParts.push(time)
  if (timeLocLabel) timeLineParts.push(timeLocLabel)
  const timeLine = timeLineParts.join(" ")
  const showEta = Boolean(eta) && serviceType !== "graveside"

  return (
    <div
      ref={setNodeRef}
      data-slot="dispatch-delivery-card"
      data-delivery-id={delivery.id}
      data-service-type={serviceType ?? ""}
      data-hole-dug={delivery.hole_dug_status}
      data-schedule-state={scheduleFinalized ? "finalized" : "draft"}
      data-dragging={isDragging ? "true" : "false"}
      data-attach-target={showAttachFeedback ? "true" : "false"}
      // Composite shadow applied inline because Tailwind arbitrary-
      // value classes for 4-5-shadow composites become unreadable.
      // Hover state tracked via React; transition is GPU-composite-
      // only (declared in className).
      style={{
        ...dragStyle,
        // Hover OR drag both lift to the level-2 composite (more
        // atmospheric halo). Idle stays at level-1 composite.
        boxShadow:
          isHovered || isDragging ? cardMaterialShadowHover : cardMaterialShadow,
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      aria-label={ariaLabel ?? `Delivery for the ${family || "unknown"} family`}
      {...attributes}
      {...listeners}
      className={cn(
        // Card chrome per DESIGN_LANGUAGE §6 canonical "Card (level 1)"
        // — elevated surface + rounded-md + shadow-level-1. **No
        // perimeter border**: DL §6 "Card perimeter: no border" —
        // edges emerge from surface lift + shadow halo + (in dark
        // mode) top-edge highlight. A drawn outline would re-intro
        // the "shape on a surface" read instead of "material object."
        //
        // Phase 3.3 removal of the dashed/solid draft-vs-finalized
        // border: per-card state signal moved entirely to the
        // day-header badge ("Draft" pill). Whole-day state is
        // singular; per-card repetition was noise.
        "relative rounded-[2px] bg-surface-elevated",
        // Aesthetic Arc Session 4.7 — Pattern 3 left-edge flag.
        // 3px solid colored border (refined Session 4.7 from Session
        // 4.5's 2px after visual verification: 2px on a 178-280px
        // wide card was perceptually invisible at production density;
        // 3px reads as a clear signal band). Color-mapped to
        // hole-dug status above. With rounded-[2px] corners (Session
        // 4.7 sharpening from rounded-md 8px), the flag reads as an
        // architectural-edge accent rather than a tagged-edge accent.
        // border-l-transparent (no flag) preserves the original
        // chrome silhouette when no signal is active.
        "border-l-[3px]",
        flagColorClass,
        // Material chrome via composite box-shadow (Pattern 2).
        // Replaces prior `shadow-level-1` alone — see cardMaterial-
        // Shadow above for the four-layer composition. Inline
        // style+hover via JS state because Tailwind multi-line
        // arbitrary-value box-shadow (4-shadow composite + token
        // refs) becomes unreadable as a single utility class.
        // Transition only the shadow property (GPU composite,
        // no layout cost).
        "transition-shadow duration-settle ease-settle",
        // Drag lift: subtle scale 1.02 + opacity dim per
        // PLATFORM_QUALITY_BAR.md §2 ("subtle scale on grab —
        // 1.02 to 1.04 typical lift"). Shadow intensification
        // (level-1 → level-2) is handled by the inline boxShadow
        // composite above (isDragging gates the level-2 variant).
        isDragging && "opacity-95 scale-[1.02]",
        // Phase 4.3b.3 — attach-target visual feedback. When an
        // ancillary: drag is active AND the cursor is over a card
        // that can serve as a parent (kanban + assigned), the card
        // gets a accent dashed outline + accent-subtle wash. Matches
        // the lane-droppable accent-ring convention from Scheduling
        // Lane (§4.2 onwards). data-attach-target is the testable
        // signal for the visual feedback gate.
        showAttachFeedback && [
          "ring-2 ring-accent ring-offset-2 ring-offset-surface-base",
          "ring-dashed",
          // Shadow intensification during attach hover handled by the
          // inline composite (level-2 variant gated on isHovered too —
          // attach feedback already implies hover position).
          "bg-accent-subtle/40",
        ],
        "cursor-grab active:cursor-grabbing",
        "focus-ring-accent outline-none",
      )}
      role="button"
      tabIndex={0}
    >
      {/* Body — clickable for edit AND draggable.
          Phase 4.2.4 — the prior `onPointerDown={e.stopPropagation()}`
          prevented drag from activating when pointerdown landed on
          the body (only the icon row was draggable). Removed so the
          wrapper's drag listeners receive the pointerdown and the
          PointerSensor's `activationConstraint: { distance: 8 }`
          distinguishes click (release within 8px) from drag (movement
          >8px). Click semantic: short press = open QuickEdit; press-
          and-drag = reassign. onClick still stopPropagation to keep
          the card wrapper from double-handling (e.g. if we later
          add a wrapper-level onClick). @dnd-kit suppresses the
          `click` event when a drag has activated, so the onOpenEdit
          callback never fires after a completed drag.

          R-2.1 — header + body sub-components render INSIDE this
          click-button (per /tmp/r2_1_subsection_scope.md Section 6
          option 1: minimum disruption + leverages SelectionOverlay's
          capture-phase preventDefault for view-vs-edit mode dispatch). */}
      <button
        type="button"
        data-slot="dispatch-card-body"
        data-density={density}
        onClick={(e) => {
          e.stopPropagation()
          onOpenEdit?.(delivery)
        }}
        className={cn(
          "block w-full text-left",
          // Phase 4.2.1 — density-driven padding.
          isCompact ? "px-2.5 py-1.5" : "px-3 py-2",
          // Aesthetic Arc Session 4.8 — rounded-[2px] consistency with outer card.
          "focus-ring-accent outline-none rounded-[2px]",
        )}
        aria-label={`Edit ${family || "unnamed"} family delivery`}
      >
        {/* R-2.1 — header sub-section (eyebrow + FH + cemetery). */}
        <DeliveryCardHeader
          startTime={startTime}
          fh={fh}
          cemetery={cemetery}
          city={city}
        />

        {/* R-2.1 — body sub-section (timeline + product). */}
        <DeliveryCardBody
          timeLine={timeLine}
          eta={eta}
          showEta={showEta}
          vaultType={vaultType}
          equipmentType={equipmentType}
        />
      </button>

      {/* R-2.1 — actions sub-section (icon row + ancillary badge +
          hole-dug + optional R-4 button row). Renders below + outside
          the click-button per the canonical structure. */}
      <DeliveryCardActions
        delivery={delivery}
        isCompact={isCompact}
        family={family}
        section={section}
        driverNote={driverNote}
        chatCount={chatCount}
        ancillaryCount={ancillaryCount}
        ancillaryExpanded={ancillaryExpanded}
        onToggleAncillary={onToggleAncillary}
        onCycleHoleDug={onCycleHoleDug}
        nextHoleDugStatus={nextHoleDugStatus(delivery.hole_dug_status)}
      />
    </div>
  )
}


// R-2.1 — IconTooltip + HoleDugBadge extracted to their own files +
// registered as entity-card-section sub-components. The previous
// inline implementations lived between the parent component and
// the icon-row JSX; now they're imported from the registrations
// barrel via `DeliveryCardActions` and `DeliveryCardHoleDugBadge`.
// See:
//   - DeliveryCardHoleDugBadge.tsx (sub-section: delivery-card.hole-dug-badge)
//   - DeliveryCardActions.tsx (sub-section: delivery-card.actions)
//   - _shared.tsx (IconTooltip primitive shared with AncillaryCard)
