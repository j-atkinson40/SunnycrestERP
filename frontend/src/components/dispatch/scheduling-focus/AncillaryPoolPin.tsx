/**
 * AncillaryPoolPin — Phase B Session 4.3b.3 Canvas widget.
 *
 * Renders pool ancillaries (date-less, unassigned, floating) as a
 * scrollable list of compact draggable rows. Each row is a drag
 * source with `useDraggable({ id: "ancillary:<id>" })` so the
 * elevated DndContext (FocusDndProvider) can route drops:
 *
 *   onto driver lane     → assign_ancillary_standalone
 *   onto Unassigned lane → return_ancillary_to_pool (no-op for pool)
 *   onto parent card     → attach_ancillary
 *
 * Routing logic lives in SchedulingKanbanCore's useDndMonitor
 * listener (commit 4); this component is purely the drag SOURCE.
 *
 * Mount point
 * ───────────
 * Registered with the canvas widget registry under
 * `"funeral-scheduling.ancillary-pool"` via
 * `dispatch/scheduling-focus/register.ts`. The funeral-scheduling
 * Focus's tenantDefault layout (commit 4) seeds the widget at the
 * right-rail anchor, ~260px wide, ~70vh tall. User can drag-
 * reposition via WidgetChrome (existing canvas widget UX).
 *
 * Tier degradation
 * ────────────────
 * Canvas tier  → renders inline as a free-form widget (this surface)
 * Stack tier   → renders as a Smart Stack tile (StackRail's
 *                getWidgetRenderer dispatch)
 * Icon tier    → renders inside BottomSheet's tile grid + tap-to-
 *                expand
 * All three tiers handled by the canonical canvas widget framework
 * (Phase A Sessions 3.7-3.8 + the Phase 4.3b.3 typed-widget
 * registry).
 *
 * Empty state
 * ───────────
 * When pool is empty, render a quiet "No pool items" message — the
 * dispatcher's normal target state (every ancillary either paired
 * or standalone). Loading state during refresh: subdued opacity on
 * the existing list rather than a spinner (per PLATFORM_QUALITY_BAR
 * §1 — no perceptible lag, no spinner where in-flight data isn't
 * blocking).
 *
 * Why not reuse AncillaryCard for the row chrome
 * ──────────────────────────────────────────────
 * AncillaryCard targets driver-lane rendering with `bg-surface-
 * elevated` + `shadow-level-1` + same chrome as DeliveryCard. Pool
 * pin items are denser — visually subordinate to the lane cards
 * since pool is the "waiting" state. Compact list rows (single line
 * with truncation) maximize how many items fit at once. Same
 * type_config.product_summary fallback chain as AncillaryCard for
 * label resolution; sharing that helper would be a future
 * cleanup. For 4.3b.3 the helper inlines.
 */

import { useDraggable, useDroppable } from "@dnd-kit/core"
import { CSS } from "@dnd-kit/utilities"
import { InboxIcon } from "lucide-react"

import { useFocusDndActiveId } from "@/components/focus/FocusDndProvider"
import {
  useSchedulingFocus,
  useSchedulingFocusOptional,
} from "@/contexts/scheduling-focus-context"
import { cn } from "@/lib/utils"
import type { DeliveryDTO } from "@/services/dispatch-service"
import type { VariantId } from "@/components/widgets/types"


/** Drop target id for the AncillaryPoolPin. SchedulingKanbanCore's
 *  drag handler routes ancillary drops on this id to
 *  `returnAncillaryToPool`. Exported so tests + handler can share
 *  the canonical string without drift. */
export const ANCILLARY_POOL_DROPPABLE_ID = "ancillary-pool"


// Same fallback chain AncillaryCard uses (Flag 5 from 4.3.3 spec).
// Inlined here for now; a shared helper is a future cleanup.
function resolvePoolItemLabel(d: DeliveryDTO): string {
  const tc = d.type_config ?? {}
  const product = (tc.product_summary as string | undefined) ?? ""
  if (product.trim()) return product
  const vault = (tc.vault_type as string | undefined) ?? ""
  if (vault.trim()) return vault
  const TYPE_LABELS: Record<string, string> = {
    funeral_home_dropoff: "Drop-off",
    funeral_home_pickup: "Pickup",
    supply_delivery: "Supply",
  }
  return TYPE_LABELS[d.delivery_type] ?? d.delivery_type
}


function resolvePoolItemSubhead(d: DeliveryDTO): string {
  const tc = d.type_config ?? {}
  const fh = (tc.funeral_home_name as string | undefined) ?? ""
  const family = (tc.family_name as string | undefined) ?? ""
  // Family OR funeral home — whichever is set. Family is the more
  // specific identifier when present (e.g. "Lombardi" pin item).
  if (family.trim()) return family
  return fh.trim()
}


interface PoolItemProps {
  delivery: DeliveryDTO
}


function PoolItem({ delivery }: PoolItemProps) {
  // Drag source. Same `distance: 8` activation constraint cascades
  // through the elevated DndContext provided by FocusDndProvider —
  // PointerSensor lives at the provider level. Drag id carries the
  // `ancillary:` prefix so SchedulingKanbanCore's drag handler
  // routes correctly (vs `delivery:` for kanban + standalone
  // cards, `widget:` for canvas widgets).
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: `ancillary:${delivery.id}`,
      data: { ancillaryId: delivery.id, source: "pool" },
    })

  const dragStyle = transform
    ? { transform: CSS.Translate.toString(transform) }
    : undefined

  const label = resolvePoolItemLabel(delivery)
  const subhead = resolvePoolItemSubhead(delivery)

  return (
    <div
      ref={setNodeRef}
      style={dragStyle}
      data-slot="ancillary-pool-item"
      data-ancillary-id={delivery.id}
      data-dragging={isDragging ? "true" : "false"}
      {...attributes}
      {...listeners}
      className={cn(
        // Compact row chrome — visually subordinate to lane cards.
        //
        // Aesthetic Arc Session 1 Commit D — divider softened
        // (border-b/60 → /30) so individual rows feel like distinct
        // items on a unified tablet surface rather than rule-line-
        // separated cells. Same intent as the post-Session-1 header
        // divider: whispers separation rather than announcing it.
        //
        // Phase 4.3b.3.2 — whole-item drag (no grip handle). Per the
        // platform standard, every draggable surface uses the
        // PointerSensor activation constraint (distance: 8) to
        // separate click from drag. Explicit drag handles clutter UI
        // and confuse the interaction model. This row is a peer of
        // DeliveryCard's drag-from-anywhere pattern (Phase A
        // Session 3.5 for canvas widgets, Phase 4.2.4 for delivery
        // cards). See PRODUCT_PRINCIPLES.md "Drag interactions" for
        // the canonical statement.
        "relative px-3 py-2",
        "border-b border-border-subtle/30 last:border-b-0",
        "transition-colors duration-quick ease-settle",
        "hover:bg-accent-subtle/40 cursor-grab active:cursor-grabbing",
        "focus-ring-accent outline-none",
        // Drag lift per PQB §2 (subtle scale + opacity dim per the
        // canonical drag-source contract).
        isDragging && "opacity-95 scale-[1.02] bg-accent-subtle/60",
      )}
      role="button"
      tabIndex={0}
      aria-label={`${label} — drag to assign or attach`}
    >
      {/* Aesthetic Arc Session 1.6 — title text wraps to up to 2 lines
          (line-clamp-2 + break-words) instead of single-line truncate.
          Per PLATFORM_PRODUCT_PRINCIPLES "Widget Compactness" (width
          subsection): ellipsis truncation is a failure mode; default
          to natural wrap when widget height is content-driven. The
          pin is height: "auto" + maxHeight: 480, so adding a second
          line for a long title is fine — pin grows by ~16px.
          line-clamp-2 caps at 2 lines as graceful overflow for
          unusually-long titles (avoids 5-line walls of text);
          break-words handles unbroken character runs.
          `title` attribute retained for native browser tooltip on
          hover — discoverable for the rare case where line-2 still
          truncates. */}
      <p
        className={cn(
          "text-body-sm font-medium leading-tight",
          "text-content-strong font-sans",
          "line-clamp-2 break-words",
        )}
        title={label}
      >
        {label}
      </p>
      {subhead && (
        <p
          className={cn(
            "mt-0.5 text-caption leading-tight",
            "text-content-muted font-sans",
            "line-clamp-2 break-words",
          )}
          title={subhead}
        >
          {subhead}
        </p>
      )}
    </div>
  )
}


export interface AncillaryPoolPinProps {
  /** Stable widget id from WidgetState (provided by the canvas
   *  framework's getWidgetRenderer dispatch). Currently unused —
   *  there's only one pool pin per Focus today — but matches the
   *  WidgetRendererProps contract for future per-widget telemetry /
   *  state-keying. */
  widgetId?: string
  /** Widget Library Phase W-1 — variant discriminator per Section
   *  12.2. AncillaryPoolPin declares Glance + Brief + Detail in the
   *  catalog. The full `VariantId` union is accepted for compatibility
   *  with the registry's `WidgetRendererProps` shape (which is generic
   *  across all widgets). This component renders Glance and Detail
   *  branches today; Brief + Deep fall through to Detail per Decision
   *  10 (graceful back-compat during migration window). */
  variant_id?: VariantId
  /** Phase W-2 — surface discriminator. When `surface === "spaces_pin"`,
   *  the component renders a compact summon affordance regardless of
   *  variant_id (sidebar pins always use Glance per §12.2). When
   *  surface is unset OR focus_canvas/focus_stack, variant_id chooses
   *  the rendering path. */
  surface?: "focus_canvas" | "focus_stack" | "spaces_pin"
}


/**
 * Glance variant rendering — Section 12.10 reference.
 *
 * Compact 180×60 summon affordance for the Spaces sidebar (and
 * potentially pulse_grid) per the catalog's Glance variant config.
 *
 * Composition (DESIGN_LANGUAGE.md §12.2 + §11 Pattern 1 reference):
 *   • Single-row chrome: eyebrow label + count chip + caret cue.
 *   • No list, no per-item draggability — the Glance variant's
 *     interactivity is the summon click only (Section 12.6a Widget
 *     Interactivity Discipline: state changes widget-appropriate,
 *     decisions belong in Focus). The whole tablet acts as the
 *     button.
 *   • Same Pattern 1 frosted-glass + rounded-none + composite shadow
 *     surface treatment as the Detail variant — visual continuity
 *     across surfaces (sidebar vs. focus canvas) is intentional.
 *
 * Click handler is provided by the parent surface (PinnedSection in
 * Commit 3); the variant itself is render-only here. Per Section
 * 12.6a, click summons Focus with the Detail variant — Glance's job
 * is to surface a count and offer a way to expand into a decision
 * surface.
 *
 * Empty state: still rendered (count chip omitted) — the absence of
 * pool items IS the information at a glance. "Pool clear" subtext
 * confirms; no zero-state hidden because that would silently degrade
 * the affordance.
 */
function AncillaryPoolGlanceTablet({
  poolCount,
  poolLoading,
}: {
  poolCount: number
  poolLoading: boolean
}) {
  return (
    <div
      data-slot="ancillary-pool-pin"
      data-variant="glance"
      data-surface="spaces_pin"
      // Aesthetic Arc Session 4.8 — same Pattern 1 transform as the
      // Detail variant. Tablet floats over the sidebar substrate via
      // 2px upward offset + composite atmospheric shadow.
      style={{ transform: "var(--widget-tablet-transform)" }}
      className={cn(
        // Pattern 1 frosted-glass surface (DL §11) — identical
        // composition to the Detail variant for cross-surface
        // visual continuity. The Glance variant differs in CONTENT
        // density (single row vs. scrollable list), not in surface
        // treatment.
        "relative flex items-center overflow-hidden",
        "bg-surface-elevated/85 supports-[backdrop-filter]:backdrop-blur-sm",
        "rounded-none",
        "shadow-[var(--shadow-widget-tablet)]",
        // Glance-specific dimensions per WIDGET_DEFINITIONS catalog
        // (canvas_size 180×60, density: minimal). h-15 = 60px.
        "h-15 w-full",
        // Section 12.6a — Glance summons. The tablet itself is the
        // click affordance; cursor + hover signal interactivity.
        "cursor-pointer",
        "hover:bg-surface-elevated/95",
        "transition-colors duration-quick ease-settle",
        "focus-ring-accent outline-none",
        poolLoading && "opacity-80",
      )}
      // role+tabIndex per Section 12.6a interactivity discipline:
      // Glance is a summon affordance, not a passive readout. The
      // parent PinnedSection wires the click handler; here we just
      // declare the role + keyboard accessibility.
      role="button"
      tabIndex={0}
      aria-label={
        poolCount > 0
          ? `Ancillary pool — ${poolCount} ${
              poolCount === 1 ? "item" : "items"
            } waiting. Open Focus to pair.`
          : "Ancillary pool — clear. Open Focus."
      }
    >
      {/* Bezel column — same 28px structural left edge as Detail
          variant, two short vertical grip lines per macOS column-
          resize-handle vocabulary. Aria-hidden because the tablet
          itself carries the role=button semantics. */}
      <div
        aria-hidden
        data-slot="ancillary-pool-pin-bezel-grip"
        className={cn(
          "flex h-full w-7 shrink-0 items-center justify-center",
          "border-r border-border-subtle/30",
          "gap-0.5",
        )}
      >
        <span className="block h-3 w-0.5 rounded-full bg-content-muted/30" />
        <span className="block h-3 w-0.5 rounded-full bg-content-muted/30" />
      </div>
      {/* Content row — eyebrow + count chip + caret cue. Single
          horizontal layout, no header divider, no list. Section 12.10
          Glance reference: minimum information density, summon
          affordance via tablet click.
          Note: per DL §11 Pattern 1 widget chrome reduction for
          Glance variant, the eyebrow + heading composition collapses
          to one line — eyebrow standalone reads as identifying
          label without needing a state phrase below. */}
      <div className="flex min-w-0 flex-1 items-center justify-between gap-2 px-3">
        <div className="min-w-0 flex-1">
          <p
            className={cn(
              "text-micro uppercase tracking-wider",
              "text-content-muted font-mono",
              "truncate",
            )}
            data-slot="ancillary-pool-pin-eyebrow"
          >
            Ancillary pool
          </p>
          <p
            className={cn(
              "mt-0.5 text-caption leading-tight",
              "text-content-muted font-sans",
              "truncate",
            )}
            data-slot="ancillary-pool-pin-glance-subtext"
          >
            {poolCount === 0
              ? "Pool clear"
              : `${poolCount} ${
                  poolCount === 1 ? "item" : "items"
                } waiting`}
          </p>
        </div>
        {poolCount > 0 && (
          <span
            data-slot="ancillary-pool-pin-count"
            className={cn(
              "inline-flex items-center justify-center",
              "min-w-[20px] h-5 px-1.5 rounded-full",
              "bg-accent text-content-on-accent text-caption font-medium",
              "font-mono tabular-nums shrink-0",
            )}
          >
            {poolCount}
          </span>
        )}
      </div>
    </div>
  )
}


/**
 * Glance dispatcher — connects the Spaces sidebar mount to the
 * stateless Glance tablet. Reads pool data via the OPTIONAL hook so
 * mounting outside a Focus provider degrades gracefully (count=0).
 *
 * Phase W-2 contract: this is a pure data-piping component. The
 * tablet itself (AncillaryPoolGlanceTablet) is render-only and
 * presentation-only; click handling is the parent's responsibility
 * (PinnedSection in Commit 3 wires the summon).
 */
function AncillaryPoolGlanceVariant() {
  const optCtx = useSchedulingFocusOptional()
  return (
    <AncillaryPoolGlanceTablet
      poolCount={optCtx?.poolAncillaries.length ?? 0}
      poolLoading={optCtx?.poolLoading ?? false}
    />
  )
}


/**
 * Detail variant — pre-W-2 rich list rendering. Hard-asserts the
 * Focus provider via useSchedulingFocus(). The call sites that mount
 * Detail (Canvas, StackRail, BottomSheet, StackExpandedOverlay) all
 * sit inside the funeral-scheduling Focus, so the provider contract
 * holds.
 */
function AncillaryPoolDetailVariant() {
  const { poolAncillaries, poolLoading } = useSchedulingFocus()

  // Phase 4.3b.4 — pin becomes a drop target for return-to-pool.
  // Drag flows that drop here:
  //   - Standalone ancillary in a driver lane → returnAncillaryToPool
  //   - Attached ancillary from drawer expansion → returnAncillaryToPool
  //   - Pool item from this same pin → no-op (already in pool)
  // SchedulingKanbanCore's onDragEnd handler routes by `over.id ===
  // ANCILLARY_POOL_DROPPABLE_ID`. Visual feedback below mirrors the
  // delivery-as-parent droppable pattern: accent dashed outline +
  // accent-subtle wash, gated on active drag being an ancillary
  // (delivery: + widget: drags don't trigger pin feedback).
  const { setNodeRef: setDropRef, isOver } = useDroppable({
    id: ANCILLARY_POOL_DROPPABLE_ID,
  })
  const activeDragId = useFocusDndActiveId()
  const isAncillaryDragActive = activeDragId?.startsWith("ancillary:") ?? false
  // The pin is its own source of items, so a pool→pool drop should
  // NOT light up — feedback only when the dragged ancillary is NOT
  // currently in the pool list (standalone or attached).
  const draggedIsFromPool =
    activeDragId !== null &&
    poolAncillaries.some(
      (d) => d.id === activeDragId.replace(/^ancillary:/, ""),
    )
  const showPoolDropFeedback =
    isOver && isAncillaryDragActive && !draggedIsFromPool

  return (
    <div
      ref={setDropRef}
      data-slot="ancillary-pool-pin"
      data-pool-drop-target={showPoolDropFeedback ? "true" : "false"}
      // Aesthetic Arc Session 4.8 — Pattern 1 widget tablet
      // transform. translateY(-2px) creates genuine physical lift
      // offset combined with the layered atmospheric shadow tokens.
      // Together: pin reads as floating object hovering above
      // operations, not as an elevated card. Pre-Session-4.8 the
      // pin's lift came from shadow alone (single-shadow
      // --widget-ambient-shadow); Session 4.8 introduces the
      // transform via --widget-tablet-transform token. See DL §3
      // widget elevation tier + §11 Pattern 1 for the full
      // composition rationale. The transform applies to this outer
      // div (not the WidgetChrome wrapper which positions via its
      // own translate3d for canvas placement); no conflict with
      // drag mechanics since the pin itself doesn't drag — only
      // its CONTENTS (PoolItem rows) drag via dnd-kit. The
      // 2px upward offset is a static visual cue, not interaction.
      style={{ transform: "var(--widget-tablet-transform)" }}
      className={cn(
        // Aesthetic Arc Session 4.5 — Pattern 1 tablet treatment.
        // Reference component for Pattern 1 (Tablet) per DL §11.
        //
        // Composition (DL §11 Pattern 1):
        //   • Frosted-glass surface — bg-surface-elevated/85 +
        //     backdrop-blur-sm. Dimmed Focus backdrop bleeds
        //     through with a subtle blur. The pin reads as a
        //     frosted-glass tablet floating over content, not an
        //     opaque overlay pasted on the substrate.
        //   • Drawn edges — shadow-level-1 carries the token-
        //     defined edge treatment (top-edge highlight in dark
        //     mode + soft halo + tight grounding shadow per DL §6).
        //     Cross-surface consistency: same elevation token as
        //     DeliveryCard. The shadow IS the edge; no perimeter
        //     border per DL §6 "Card perimeter: no border."
        //   • Square-shouldered radii — rounded-md (8px). Section 0
        //     Architectural Proportions TP2 — not pillowy-large.
        //   • Bezel with grip indicator — Session 4.5 RESTRUCTURED.
        //     Pre-Session-4.5: 32×2 horizontal pill at top-center
        //     (Session 4 deviation from Pattern 1 doc which says
        //     "left side"). Post-Session-4.5: 28px dedicated LEFT-
        //     EDGE column with two short vertical grip lines (the
        //     macOS column-resize-handle vocabulary). Rendered as
        //     a flex sibling of the content area, not absolute-
        //     positioned, so the bezel is a structural element of
        //     the tablet — not decoration on top.
        //
        // Aesthetic Arc Session 4.5 — root flex direction switched
        // `flex-col` → `flex` (default row). Bezel column becomes
        // first child; main content (header + list) wrapped in a
        // flex-1 flex-col sibling.
        //
        // overflow-hidden clips the bezel column's right border so
        // it doesn't poke past the rounded corners.
        //
        // Aesthetic Arc Session 4.7 — corner radius rounded-md (8px)
        // → rounded-[2px]. Pattern 1 + Section 0 "sharp at
        // architectural scale": tablets are architectural materialized
        // objects, not pillowy chips. 2px corners read as carved
        // precision tablet, not soft toy.
        //
        // Aesthetic Arc Session 4.7 — widget elevation tier. Pre-4.7
        // the pin used `shadow-level-1` (same base as cards' atmospheric
        // layer). Post-4.7 the pin composes
        // `var(--widget-ambient-shadow)` IN ADDITION TO shadow-level-1
        // — wider blur + larger y-offset + stronger alpha. The pin
        // visibly floats further from the work surface than cards do,
        // matching PLATFORM_INTERACTION_MODEL: widgets are summoned
        // tablets ON TOP of operations, not equivalent to the work
        // surface. See DL §11 Pattern 1 elevation hierarchy.
        //
        // PLATFORM_INTERACTION_MODEL: tablets are the materialization
        // unit — they float, they're individually present, they don't
        // enclose other content. Pattern 1 reference component.
        "relative flex overflow-hidden",
        "bg-surface-elevated/85 supports-[backdrop-filter]:backdrop-blur-sm",
        // Aesthetic Arc Session 4.8 — corner radius rounded-[2px]
        // → rounded-none (0px). DOM audit confirmed pin's 2px corner
        // is technically applied, but the frosted-glass surface
        // treatment (bg /85 + backdrop-blur) inherently softens the
        // visible perimeter — semi-transparent + blurred fill blends
        // the edge into the substrate regardless of border-radius
        // value. 0px maximizes available sharpness within the
        // frosted-glass canonical Pattern 1 surface treatment.
        // DateBoxes (solid fill, no frosted-glass) keep 2px because
        // their fill carries the edge sharpness; the pin's frosted
        // treatment trades some edge sharpness for the "floating
        // tablet hovering above operations" register Pattern 1 wants.
        "rounded-none",
        // Multi-layer shadow via the composite `--shadow-widget-tablet`
        // token (defined in tokens.css). Composes shadow-level-1
        // (existing material edges + dark-mode top highlight) + the
        // widget-ambient-shadow (higher-tier lift). Single token
        // resolves cleanly through Tailwind's arbitrary-value
        // bracket syntax. See DL §3 widget elevation tier rationale +
        // §11 Pattern 1 elevation hierarchy.
        "shadow-[var(--shadow-widget-tablet)]",
        // Subtle dim during refresh — keeps the existing list visible
        // but signals data is in flight.
        poolLoading && "opacity-80",
        // Phase 4.3b.4 — drop-target visual feedback. Accent dashed
        // outline + accent-subtle wash matching DeliveryCard's parent-
        // drop pattern (Phase 4.3b.3) for consistency across all
        // ancillary drop surfaces (lane = solid accent ring;
        // parent card = dashed accent ring; pin = dashed accent
        // ring). Same DESIGN_LANGUAGE §6 accent family across the
        // platform's ancillary-drag affordances.
        showPoolDropFeedback && [
          "ring-2 ring-accent ring-dashed ring-offset-2 ring-offset-surface-base",
          "bg-accent-subtle/40",
        ],
        "transition-shadow duration-quick ease-settle",
      )}
    >
      {/* Aesthetic Arc Session 4.5 — Pattern 1 bezel column.
          28px dedicated left-edge structural column with two short
          vertical grip lines (macOS column-resize-handle vocabulary,
          per DL §11 Pattern 1 doc-spec). Two parallel vertical lines:
          each 12px tall × 2px wide, 2px apart, vertically centered
          in the bezel column. Subtle muted color at 30% alpha.

          aria-hidden because purely visual affordance — the tablet
          itself isn't draggable (its CONTENTS are individually
          draggable as ancillary items). The grip signals "this is
          a tablet you can grab and arrange," consistent with the
          Tony Stark / Jarvis interaction model.

          1px right border (border-border-subtle/30) separates the
          bezel column from the content area. shrink-0 prevents the
          flex layout from compressing the bezel under content
          pressure (the bezel is structural, not negotiable). */}
      <div
        aria-hidden
        data-slot="ancillary-pool-pin-bezel-grip"
        className={cn(
          "flex w-7 shrink-0 items-center justify-center",
          "border-r border-border-subtle/30",
          "gap-0.5",
        )}
      >
        <span className="block h-3 w-0.5 rounded-full bg-content-muted/30" />
        <span className="block h-3 w-0.5 rounded-full bg-content-muted/30" />
      </div>
      {/* Content column — wraps header + list. flex-1 fills the
          remaining horizontal space; min-w-0 allows children to
          truncate/wrap correctly inside the flex-1 container.
          flex-col preserves the existing vertical stacking of
          header above list. */}
      <div className="flex min-w-0 flex-1 flex-col">
      {/* Header — eyebrow + count badge. Matches DESIGN_LANGUAGE §4
          eyebrow treatment: text-micro uppercase tracking-wider
          text-content-muted. Count chip styling parallels the chat
          unread chip from _shared.tsx IconTooltip badge.

          Aesthetic Arc Session 4 — Pattern 1 mono label: eyebrow
          migrates from font-sans → font-mono (Geist Mono). Tablets
          carry their navigation/identification label in the precision
          register, not the narrative register. The "Ancillary pool"
          label is identifying THIS tablet's content — same role as a
          window-title bar — so it reads as data, not prose. Heading
          ("Waiting for pairing") stays font-sans (state-phrase prose).

          Aesthetic Arc Session 1 Commit D — header divider softened
          to /40 alpha. Whispers "two regions" rather than announcing
          (British register).

          Session 4.5 — header padding restored to py-2 (was pt-2.5
          pb-2 to clear the old top bezel; new bezel is on the LEFT
          column so no top clearance needed). */}
      <div
        data-slot="ancillary-pool-pin-header"
        className={cn(
          "flex items-baseline justify-between gap-2",
          "border-b border-border-subtle/40 px-3 py-2",
        )}
      >
        <div>
          <p
            className={cn(
              "text-micro uppercase tracking-wider",
              "text-content-muted font-mono",
            )}
          >
            Ancillary pool
          </p>
          <h3
            className={cn(
              "mt-0.5 text-body-sm font-medium leading-tight",
              "text-content-strong font-sans",
            )}
          >
            Waiting for pairing
          </h3>
        </div>
        {poolAncillaries.length > 0 && (
          <span
            data-slot="ancillary-pool-pin-count"
            className={cn(
              "inline-flex items-center justify-center",
              "min-w-[20px] h-5 px-1.5 rounded-full",
              "bg-accent text-content-on-accent text-caption font-medium",
              "font-mono tabular-nums",
            )}
            aria-label={`${poolAncillaries.length} pool ${
              poolAncillaries.length === 1 ? "item" : "items"
            }`}
          >
            {poolAncillaries.length}
          </span>
        )}
      </div>

      {/* List body — Aesthetic Arc Session 1.5 simplifies to natural
          content flow. Pre-Session-1.5 had `flex-1 overflow-y-auto`
          for scroll-within-pin when fixed-height; Session 1.5 makes
          the WidgetChrome wrapper content-driven (max-height: 480 +
          overflow-y: auto), so scroll happens at the chrome level
          when content exceeds the cap. List body just natural-flows.
          Empty-state inner block also drops `h-full` since there's
          no parent height to fill. */}
      <div data-slot="ancillary-pool-pin-list">
        {poolAncillaries.length === 0 && !poolLoading && (
          <div
            data-slot="ancillary-pool-pin-empty"
            className={cn(
              "flex flex-col items-center justify-center gap-2",
              "px-4 py-6 text-center",
            )}
          >
            <InboxIcon
              className="h-6 w-6 text-content-subtle"
              aria-hidden
            />
            <p
              className={cn(
                "text-caption text-content-muted font-sans",
                "leading-tight",
              )}
            >
              {showPoolDropFeedback ? "Drop to return to pool" : "No pool items"}
            </p>
            <p
              className={cn(
                "text-micro text-content-subtle font-sans",
                "leading-tight",
              )}
            >
              {showPoolDropFeedback
                ? "Releases driver + date assignment."
                : "Pair complete — every ancillary is assigned."}
            </p>
          </div>
        )}
        {poolAncillaries.map((d) => (
          <PoolItem key={d.id} delivery={d} />
        ))}
      </div>
      </div>{/* /content column (Session 4.5) */}
    </div>
  )
}


/**
 * Top-level dispatcher — Widget Library Phase W-2.
 *
 * Selects the variant component based on the W-1 unified-contract
 * props (variant_id + surface) per Section 12.3 Decision 5 (one
 * component per widget; internal switch). The dispatcher itself
 * calls NO hooks — each variant component owns its hook order, so
 * React's rules-of-hooks are satisfied across renders that flip
 * between variants.
 *
 * Glance branch (sidebar / pulse_grid):
 *   - Triggered by `surface === "spaces_pin"` OR `variant_id === "glance"`.
 *   - Renders the compact 180×60 summon affordance.
 *   - Tolerates non-Focus mounting (the sidebar surface is global).
 *
 * Detail branch (default — Focus canvas, stack, bottom sheet, stack
 * expanded overlay):
 *   - Triggered when neither Glance signal is present.
 *   - Renders the full scrollable list with drag-source affordance.
 *   - Hard-asserts the Focus provider via useSchedulingFocus.
 *
 * Brief variant:
 *   - Declared in the catalog (canvas_size 280×320), but Phase W-2
 *     ships only Glance + Detail rendering. Brief falls through to
 *     Detail today as graceful behavior; a dedicated Brief tablet
 *     ships when a consumer surface (pulse_grid summary, focus_stack
 *     compact) needs it. Decision 10 (back-compat during migration)
 *     covers this — widgets ship variants incrementally without
 *     breaking pre-existing consumers.
 */
export function AncillaryPoolPin(props: AncillaryPoolPinProps) {
  const isGlance =
    props.surface === "spaces_pin" || props.variant_id === "glance"
  if (isGlance) {
    return <AncillaryPoolGlanceVariant />
  }
  return <AncillaryPoolDetailVariant />
}
