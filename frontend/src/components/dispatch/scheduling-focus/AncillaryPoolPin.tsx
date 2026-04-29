/**
 * AncillaryPoolPin — Phase B Session 4.3b.3 Canvas widget +
 * Phase W-4a Cleanup Session B.2 surface-aware refactor.
 *
 * Surface-aware variant dispatcher:
 *   • surface === "spaces_pin" OR variant_id === "glance"
 *       → Glance variant (compact summon affordance, sidebar)
 *   • surface === "pulse_grid" OR variant_id === "brief"
 *       → Brief variant (read-only count + top 3 items + Open in
 *         scheduling Focus CTA — workspace-shape preservation per
 *         §13.3.2.1)
 *   • default (focus_canvas, focus_stack, dashboard_grid Detail)
 *       → Detail variant (interactive, requires
 *         SchedulingFocusDataProvider)
 *
 * **Pre-Session-B.2 architecture**: Detail variant called strict
 * `useSchedulingFocus()` which threw outside the FH Focus subtree.
 * The widget had `pulse_grid` in its `supported_surfaces` declaration
 * but couldn't actually render in pulse_grid — the registry-key
 * mismatch (`funeral-scheduling.ancillary-pool` vs canonical
 * `scheduling.ancillary-pool`) MASKED this deeper issue. Phase W-4a
 * Step 5's MissingWidgetEmptyState empty-slot filter surfaced the
 * gap; Session B.2 closes it.
 *
 * **Post-Session-B.2 architecture**:
 *   1. Backend `/widget-data/ancillary-pool` endpoint provides read-
 *      only mode-aware pool data (production / purchase / hybrid /
 *      vault-disabled).
 *   2. `useAncillaryPool` hook reads from SchedulingFocusContext
 *      when present (FH Focus subtree, full DeliveryDTO with drag-
 *      source fields), falls back to the surface-fetched endpoint
 *      otherwise (pulse_grid + spaces_pin + dashboard_grid).
 *   3. Detail variant calls drag-related hooks directly (assumes
 *      interactive context). Brief variant calls NO drag hooks —
 *      bounded interactions only per §12.6a.
 *   4. PoolItem split into PoolItemContent (pure presentation) +
 *      PoolItemDraggable (Detail's drag source) + PoolItemStatic
 *      (Brief's read-only row with click-to-navigate).
 *
 * Empty state: when pool is empty, render a quiet "No pool items"
 * message — the dispatcher's normal target state. In Brief on
 * pulse_grid surface with `mode_note=no_pool_in_purchase_mode`,
 * advisory + CTA preserve the workspace shape per §13.3.2.1.
 */

import { useDraggable, useDroppable } from "@dnd-kit/core"
import { CSS } from "@dnd-kit/utilities"
import { ArrowRight, InboxIcon } from "lucide-react"
import { Link } from "react-router-dom"

import { useFocusDndActiveId } from "@/components/focus/FocusDndProvider"
import { useSchedulingFocusOptional } from "@/contexts/scheduling-focus-context"
import { cn } from "@/lib/utils"
import type { DeliveryDTO } from "@/services/dispatch-service"
import type { VariantId } from "@/components/widgets/types"

import {
  useAncillaryPool,
  type AncillaryPoolItem,
} from "./useAncillaryPool"


/** Drop target id for the AncillaryPoolPin. SchedulingKanbanCore's
 *  drag handler routes ancillary drops on this id to
 *  `returnAncillaryToPool`. Exported so tests + handler can share
 *  the canonical string without drift. */
export const ANCILLARY_POOL_DROPPABLE_ID = "ancillary-pool"


// ── Label/subhead helpers (shared across all PoolItem variants) ────


// Same fallback chain AncillaryCard uses (Flag 5 from 4.3.3 spec).
// Inlined here for now; a shared helper is a future cleanup.
// Accepts both AncillaryPoolItem (slim, surface-fetched) and
// DeliveryDTO (rich, context) shapes — both have the type_config +
// delivery_type fields the helpers read.
function resolvePoolItemLabel(
  d: AncillaryPoolItem | DeliveryDTO,
): string {
  const tc = (d.type_config as Record<string, unknown> | null) ?? {}
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


function resolvePoolItemSubhead(
  d: AncillaryPoolItem | DeliveryDTO,
): string {
  const tc = (d.type_config as Record<string, unknown> | null) ?? {}
  const fh = (tc.funeral_home_name as string | undefined) ?? ""
  const family = (tc.family_name as string | undefined) ?? ""
  // Family OR funeral home — whichever is set. Family is the more
  // specific identifier when present (e.g. "Lombardi" pin item).
  if (family.trim()) return family
  return fh.trim()
}


// ── PoolItem — three-component split (Session B.2) ─────────────────


interface PoolItemContentProps {
  label: string
  subhead: string
  /** Draggable variant adds the `cursor-grab` cue; static keeps
   *  default cursor (still tabbable / clickable when in Static
   *  wrapper). */
  draggable?: boolean
  /** Optional dragging state — applied by the Draggable wrapper
   *  for the lift/dim visual cue. */
  isDragging?: boolean
}


/**
 * PoolItemContent — pure presentation, no hooks.
 *
 * The visual chrome shared by both PoolItemDraggable (FH Focus
 * Detail variant) and PoolItemStatic (Pulse Brief variant). Drag
 * cursor + drag-active visual state controlled via props so the
 * static wrapper can opt out of the grab/grabbing affordance.
 */
function PoolItemContent({
  label,
  subhead,
  draggable = false,
  isDragging = false,
}: PoolItemContentProps) {
  return (
    <div
      data-slot="ancillary-pool-item-content"
      className={cn(
        // Compact row chrome — visually subordinate to lane cards.
        // Aesthetic Arc Session 1 Commit D — divider softened
        // (border-b/60 → /30) so individual rows feel like distinct
        // items on a unified tablet surface rather than rule-line-
        // separated cells.
        "relative px-3 py-2",
        "border-b border-border-subtle/30 last:border-b-0",
        "transition-colors duration-quick ease-settle",
        "hover:bg-accent-subtle/40",
        "focus-ring-accent outline-none",
        // Drag affordance: cursor + lift visual state. Brief
        // (static) variant disables to avoid implying drag on a
        // non-interactive surface per §12.6a.
        draggable && "cursor-grab active:cursor-grabbing",
        isDragging && "opacity-95 scale-[1.02] bg-accent-subtle/60",
      )}
    >
      {/* Aesthetic Arc Session 1.6 — title text wraps to up to 2 lines
          (line-clamp-2 + break-words) instead of single-line truncate.
          Per PLATFORM_PRODUCT_PRINCIPLES "Widget Compactness". */}
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


interface PoolItemDraggableProps {
  delivery: DeliveryDTO
}


/**
 * PoolItemDraggable — interactive Detail-variant row.
 *
 * Wraps PoolItemContent with @dnd-kit's `useDraggable`. Drag id
 * carries the `ancillary:` prefix so SchedulingKanbanCore's
 * cross-context drag handler routes correctly (vs `delivery:` for
 * kanban + standalone cards, `widget:` for canvas widgets).
 * `distance: 8` activation constraint cascades through the elevated
 * DndContext (FocusDndProvider) — PointerSensor lives at the
 * provider level. Whole-item drag (no grip handle) per the platform
 * standard — see PRODUCT_PRINCIPLES.md "Drag interactions".
 */
function PoolItemDraggable({ delivery }: PoolItemDraggableProps) {
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
      data-interactive="true"
      {...attributes}
      {...listeners}
      role="button"
      tabIndex={0}
      aria-label={`${label} — drag to assign or attach`}
    >
      <PoolItemContent
        label={label}
        subhead={subhead}
        draggable
        isDragging={isDragging}
      />
    </div>
  )
}


interface PoolItemStaticProps {
  item: AncillaryPoolItem
  /** Default-target route when the user clicks the item. Pulse
   *  Brief surfaces use `/dispatch` so click-through reaches the
   *  scheduling Focus where the user CAN interact. */
  navigateTo: string
}


/**
 * PoolItemStatic — read-only Pulse-grid Brief-variant row.
 *
 * No drag hooks (rules-of-hooks: this component is a separate
 * render path from Draggable, so its hook order is independent).
 * Clicks navigate to `/dispatch` so the user reaches a surface
 * where the pool item IS interactive. Per §12.6a workspace-shape
 * preservation: Brief shows the pool concept, Detail in Focus
 * provides the bounded interactions.
 */
function PoolItemStatic({ item, navigateTo }: PoolItemStaticProps) {
  const label = resolvePoolItemLabel(item)
  const subhead = resolvePoolItemSubhead(item)
  return (
    <Link
      to={navigateTo}
      data-slot="ancillary-pool-item"
      data-ancillary-id={item.id}
      data-interactive="false"
      className="block focus-ring-accent outline-none"
      aria-label={`${label} — open in scheduling Focus to interact`}
    >
      <PoolItemContent
        label={label}
        subhead={subhead}
        draggable={false}
      />
    </Link>
  )
}


// ── Component prop contract ─────────────────────────────────────────


export interface AncillaryPoolPinProps {
  /** Stable widget id from WidgetState (provided by the canvas
   *  framework's getWidgetRenderer dispatch). Currently unused —
   *  there's only one pool pin per Focus today — but matches the
   *  WidgetRendererProps contract for future per-widget telemetry /
   *  state-keying. */
  widgetId?: string
  /** Widget Library Phase W-1 — variant discriminator per Section
   *  12.2. AncillaryPoolPin declares Glance + Brief + Detail in the
   *  catalog. Post-Session-B.2: all three variants render real
   *  content (Brief was previously a fall-through to Detail per
   *  pre-Session-B.2 graceful back-compat). */
  variant_id?: VariantId
  /** Phase W-2 — surface discriminator. When `surface === "spaces_pin"`,
   *  the component renders a compact summon affordance regardless of
   *  variant_id. When `surface === "pulse_grid"`, Brief read-only
   *  rendering. Otherwise variant_id chooses the path (default Detail
   *  interactive). */
  surface?: "focus_canvas" | "focus_stack" | "spaces_pin" | "pulse_grid"
}


// ── Glance variant (unchanged from pre-Session-B.2) ────────────────


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
 *
 * Click handler is provided by the parent surface (PinnedSection in
 * Commit 3); the variant itself is render-only here. Per Section
 * 12.6a, click summons Focus with the Detail variant.
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
      style={{ transform: "var(--widget-tablet-transform)" }}
      className={cn(
        "relative flex items-center overflow-hidden",
        "bg-surface-elevated/85 supports-[backdrop-filter]:backdrop-blur-sm",
        "rounded-none",
        "shadow-[var(--shadow-widget-tablet)]",
        "h-15 w-full",
        "cursor-pointer",
        "hover:bg-surface-elevated/95",
        "transition-colors duration-quick ease-settle",
        "focus-ring-accent outline-none",
        poolLoading && "opacity-80",
      )}
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


// ── Brief variant (NEW — Session B.2) ──────────────────────────────


/**
 * Brief variant — Phase W-4a Cleanup Session B.2.
 *
 * Read-only pulse_grid rendering: count + top 3 items + "Open in
 * scheduling Focus →" CTA. NO drag chrome per §12.6a (drag-attach
 * to delivery is canvas-conditional; pulse_grid is non-canvas).
 *
 * **Workspace-shape preservation per §13.3.2.1**: the eyebrow +
 * heading + CTA structure renders identically in pool-empty,
 * pool-with-items, purchase-mode, and vault-disabled states. Only
 * the CONTENT row (item list vs advisory text) changes. Operators
 * recognize the widget by structural shape across surface
 * transitions.
 *
 * Sunnycrest canonical Pulse composition (§13.8.1 State B) seeds
 * Brief at 2×1 (cols=2, rows=1) — header + ~3 visible items, no
 * scrollable overflow.
 */
function AncillaryPoolBriefVariant() {
  const {
    items,
    totalCount,
    loading,
    operatingMode,
    modeNote,
    isVaultEnabled,
    primaryNavigationTarget,
  } = useAncillaryPool()

  // Workspace-shape preservation: surface-aware content row builder
  // chooses advisory vs item-list based on data state. Eyebrow +
  // header + CTA stay constant.
  const showItems =
    isVaultEnabled && operatingMode !== "purchase" && totalCount > 0
  const showPurchaseAdvisory = modeNote === "no_pool_in_purchase_mode"
  const showVaultDisabledAdvisory = !isVaultEnabled
  const showEmptyAdvisory =
    isVaultEnabled && operatingMode !== "purchase" && totalCount === 0

  // Top 3 items — Brief's compact list per Sunnycrest §13.8.1 State B.
  const topItems = items.slice(0, 3)
  const overflowCount = Math.max(0, totalCount - topItems.length)

  return (
    <div
      data-slot="ancillary-pool-pin"
      data-variant="brief"
      data-surface="pulse_grid"
      style={{ transform: "var(--widget-tablet-transform)" }}
      className={cn(
        // Pattern 1 frosted-glass tablet treatment matching the
        // Detail variant for cross-surface visual continuity.
        "relative flex h-full overflow-hidden",
        "bg-surface-elevated/85 supports-[backdrop-filter]:backdrop-blur-sm",
        "rounded-none",
        "shadow-[var(--shadow-widget-tablet)]",
        loading && "opacity-80",
        "transition-shadow duration-quick ease-settle",
      )}
    >
      {/* Bezel column — same structural left-edge column as Detail
          variant. Visual continuity across surfaces. */}
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
      {/* Content column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header — eyebrow + count chip. Identical structure to
            Detail variant per workspace-shape preservation. */}
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
              {showPurchaseAdvisory
                ? "Purchase mode"
                : showVaultDisabledAdvisory
                  ? "Vault not enabled"
                  : totalCount === 0
                    ? "Pool clear"
                    : "Waiting for pairing"}
            </h3>
          </div>
          {showItems && (
            <span
              data-slot="ancillary-pool-pin-count"
              className={cn(
                "inline-flex items-center justify-center",
                "min-w-[20px] h-5 px-1.5 rounded-full",
                "bg-accent text-content-on-accent text-caption font-medium",
                "font-mono tabular-nums shrink-0",
              )}
              aria-label={`${totalCount} pool ${
                totalCount === 1 ? "item" : "items"
              }`}
            >
              {totalCount}
            </span>
          )}
        </div>

        {/* Content row — items list OR advisory. Workspace-shape
            preservation: structure stable across data states. */}
        <div
          data-slot="ancillary-pool-pin-list"
          className="flex-1 overflow-y-auto"
        >
          {showItems &&
            topItems.map((item) => (
              <PoolItemStatic
                key={item.id}
                item={item}
                navigateTo={
                  primaryNavigationTarget ?? "/dispatch"
                }
              />
            ))}
          {showItems && overflowCount > 0 && (
            <p
              data-slot="ancillary-pool-pin-overflow"
              className={cn(
                "px-3 py-2 text-caption text-content-muted font-sans",
                "border-b border-border-subtle/30",
              )}
            >
              + {overflowCount} more
            </p>
          )}
          {showPurchaseAdvisory && (
            <div
              data-slot="ancillary-pool-pin-mode-advisory"
              data-mode="purchase"
              className="flex flex-col items-center justify-center gap-2 px-4 py-6 text-center"
            >
              <p className="text-caption text-content-muted font-sans leading-tight">
                Pool not active in purchase mode.
              </p>
              <p className="text-micro text-content-subtle font-sans leading-tight">
                Vault arrives via licensee transfers.
              </p>
            </div>
          )}
          {showVaultDisabledAdvisory && (
            <div
              data-slot="ancillary-pool-pin-mode-advisory"
              data-mode="vault_disabled"
              className="flex flex-col items-center justify-center gap-2 px-4 py-6 text-center"
            >
              <InboxIcon
                className="h-6 w-6 text-content-subtle"
                aria-hidden
              />
              <p className="text-caption text-content-muted font-sans leading-tight">
                Vault product line not enabled.
              </p>
            </div>
          )}
          {showEmptyAdvisory && (
            <div
              data-slot="ancillary-pool-pin-empty"
              className="flex flex-col items-center justify-center gap-2 px-4 py-6 text-center"
            >
              <InboxIcon
                className="h-6 w-6 text-content-subtle"
                aria-hidden
              />
              <p className="text-caption text-content-muted font-sans leading-tight">
                No pool items.
              </p>
              <p className="text-micro text-content-subtle font-sans leading-tight">
                Pair complete — every ancillary is assigned.
              </p>
            </div>
          )}
        </div>

        {/* CTA footer — Open in scheduling Focus link. Workspace-
            shape preservation: CTA preserved across all data states
            (pool-with-items, pool-empty, purchase-mode, vault-
            disabled). Hides only when navigationTarget is null
            (no actionable target). */}
        {primaryNavigationTarget && (
          <Link
            to={primaryNavigationTarget}
            data-slot="ancillary-pool-pin-cta"
            className={cn(
              "flex items-center justify-between gap-2 px-3 py-2",
              "border-t border-border-subtle/40",
              "text-body-sm font-medium text-accent font-sans",
              "hover:bg-accent-subtle/40",
              "transition-colors duration-quick ease-settle",
              "focus-ring-accent outline-none",
            )}
          >
            <span>Open in scheduling Focus</span>
            <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
        )}
      </div>
    </div>
  )
}


// ── Detail variant (refactored Session B.2) ────────────────────────


/**
 * Detail variant — interactive FH Focus rendering.
 *
 * Refactored Session B.2 to use `useAncillaryPool` instead of strict
 * `useSchedulingFocus()`. Hook returns interactive items + drag
 * helpers when SchedulingFocusContext is present (the FH Focus
 * canonical mount). When ctx is absent (theoretical pulse_grid +
 * variant_id="detail"), the hook falls back to the read-only fetch;
 * the dispatcher routes that case to Brief variant in canonical
 * Sunnycrest composition, so this code path renders only inside the
 * FH Focus subtree in practice.
 *
 * Drag chrome (useDroppable + useFocusDndActiveId) calls remain as
 * before — both hooks tolerate being called outside their parent
 * contexts (return inert values), so the component is render-safe
 * across surface dispatch.
 */
function AncillaryPoolDetailVariant() {
  const {
    items,
    interactiveItems,
    loading,
    isInteractive,
  } = useAncillaryPool()

  // Phase 4.3b.4 — pin becomes a drop target for return-to-pool.
  // Drag flows that drop here:
  //   - Standalone ancillary in a driver lane → returnAncillaryToPool
  //   - Attached ancillary from drawer expansion → returnAncillaryToPool
  //   - Pool item from this same pin → no-op (already in pool)
  // SchedulingKanbanCore's onDragEnd handler routes by `over.id ===
  // ANCILLARY_POOL_DROPPABLE_ID`. useDroppable safely returns inert
  // values outside DndContext, so the call is render-safe even
  // outside FH Focus subtree.
  const { setNodeRef: setDropRef, isOver } = useDroppable({
    id: ANCILLARY_POOL_DROPPABLE_ID,
  })
  const activeDragId = useFocusDndActiveId()
  const isAncillaryDragActive = activeDragId?.startsWith("ancillary:") ?? false
  // Drop-feedback only fires when interactive (FH Focus subtree).
  const draggedIsFromPool =
    activeDragId !== null &&
    interactiveItems !== null &&
    interactiveItems.some(
      (d) => d.id === activeDragId.replace(/^ancillary:/, ""),
    )
  const showPoolDropFeedback =
    isInteractive && isOver && isAncillaryDragActive && !draggedIsFromPool

  return (
    <div
      ref={setDropRef}
      data-slot="ancillary-pool-pin"
      data-variant="detail"
      data-pool-drop-target={showPoolDropFeedback ? "true" : "false"}
      data-interactive={isInteractive ? "true" : "false"}
      style={{ transform: "var(--widget-tablet-transform)" }}
      className={cn(
        "relative flex overflow-hidden",
        "bg-surface-elevated/85 supports-[backdrop-filter]:backdrop-blur-sm",
        "rounded-none",
        "shadow-[var(--shadow-widget-tablet)]",
        loading && "opacity-80",
        showPoolDropFeedback && [
          "ring-2 ring-accent ring-dashed ring-offset-2 ring-offset-surface-base",
          "bg-accent-subtle/40",
        ],
        "transition-shadow duration-quick ease-settle",
      )}
    >
      {/* Bezel column — structural left-edge column with grip lines */}
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
      {/* Content column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header — eyebrow + count badge */}
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
          {items.length > 0 && (
            <span
              data-slot="ancillary-pool-pin-count"
              className={cn(
                "inline-flex items-center justify-center",
                "min-w-[20px] h-5 px-1.5 rounded-full",
                "bg-accent text-content-on-accent text-caption font-medium",
                "font-mono tabular-nums",
              )}
              aria-label={`${items.length} pool ${
                items.length === 1 ? "item" : "items"
              }`}
            >
              {items.length}
            </span>
          )}
        </div>

        {/* List body — natural content flow per Aesthetic Arc Session
            1.5. WidgetChrome wrapper (max-height: 480 + overflow-y:
            auto) handles scroll at the chrome level. */}
        <div data-slot="ancillary-pool-pin-list">
          {items.length === 0 && !loading && (
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
          {/* Interactive: render full DeliveryDTO Draggable rows.
              Read-only fallback (theoretical): static rows via
              PoolItemStatic. Dispatcher routes pulse_grid to Brief
              variant canonically, so this fallback rarely fires. */}
          {isInteractive && interactiveItems !== null
            ? interactiveItems.map((d) => (
                <PoolItemDraggable key={d.id} delivery={d} />
              ))
            : items.map((item) => (
                <PoolItemStatic
                  key={item.id}
                  item={item}
                  navigateTo="/dispatch"
                />
              ))}
        </div>
      </div>
    </div>
  )
}


// ── Top-level dispatcher (Session B.2 surface-aware) ───────────────


/**
 * Top-level dispatcher — surface-aware variant routing.
 *
 * Per §12.6 + §12.6a + Sunnycrest canonical Pulse composition
 * (§13.8.1 State B):
 *
 *   • surface === "spaces_pin" OR variant_id === "glance"
 *       → Glance variant (compact summon affordance)
 *   • surface === "pulse_grid" OR variant_id === "brief"
 *       → Brief variant (read-only, no drag chrome)
 *   • default
 *       → Detail variant (interactive, drag-source rows)
 *
 * Each variant component owns its hook order — the dispatcher itself
 * calls NO hooks, so React's rules-of-hooks are satisfied across
 * renders that flip between variants (the variant components MOUNT
 * AND UNMOUNT instead of conditionally calling hooks within one
 * lifecycle).
 */
export function AncillaryPoolPin(props: AncillaryPoolPinProps) {
  const isGlance =
    props.surface === "spaces_pin" || props.variant_id === "glance"
  if (isGlance) {
    return <AncillaryPoolGlanceVariant />
  }

  const isBrief =
    props.surface === "pulse_grid" || props.variant_id === "brief"
  if (isBrief) {
    return <AncillaryPoolBriefVariant />
  }

  return <AncillaryPoolDetailVariant />
}
