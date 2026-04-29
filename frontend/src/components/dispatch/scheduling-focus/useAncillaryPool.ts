/**
 * useAncillaryPool — Phase W-4a Cleanup Session B.2.
 *
 * Surface-aware data hook that powers AncillaryPoolPin in BOTH
 * surface contexts:
 *
 *   • **focus_canvas** (FH Focus subtree, interactive):
 *     SchedulingFocusDataProvider context provides
 *     `poolAncillaries`, `poolLoading`, `reloadPool`,
 *     `removeFromPoolOptimistic`. Hook returns these + sets
 *     `isInteractive=true` so the dispatcher renders Detail with
 *     drag chrome enabled.
 *
 *   • **pulse_grid / spaces_pin / dashboard_grid** (read-only,
 *     no provider):
 *     Hook fetches `/widget-data/ancillary-pool` directly. Returns
 *     items + total_count + operating_mode + mode_note +
 *     `isInteractive=false`. Dispatcher renders Brief or Glance
 *     without drag chrome.
 *
 * **Why both hooks always called**: React rules-of-hooks forbid
 * conditional hook invocation. The hook calls
 * `useSchedulingFocusOptional()` AND `useState`/`useEffect` for the
 * fetch path on every render. The fetch only fires when the context
 * is null (the effect bails out if context !== null), so the cost
 * in the interactive path is essentially zero.
 *
 * **Pool definition** (matches backend
 * `/api/v1/widget-data/ancillary-pool`):
 *
 *   scheduling_type == "ancillary"
 *   AND attached_to_delivery_id IS NULL
 *   AND primary_assignee_id IS NULL
 *   AND ancillary_is_floating IS TRUE
 *   AND status != "cancelled"
 *
 * Mode-aware: production / hybrid → real pool, purchase → empty
 * items + `mode_note="no_pool_in_purchase_mode"`, vault disabled →
 * `is_vault_enabled=False` + empty items.
 *
 * **Workspace-shape preservation per §13.3.2.1**: Brief variant uses
 * mode_note + primary_navigation_target to render advisory + CTA in
 * non-pool states (purchase mode, vault disabled), preserving the
 * widget's structural shape across surface transitions.
 */

import { useCallback, useEffect, useState } from "react"

import { useSchedulingFocusOptional } from "@/contexts/scheduling-focus-context"
import apiClient from "@/lib/api-client"
import type { DeliveryDTO } from "@/services/dispatch-service"


// ── Endpoint response shape (mirrors backend ancillary_pool_service) ──


/** Slim pool item shape returned by `/widget-data/ancillary-pool`.
 *  Same field subset as DeliveryDTO that the Brief variant renders
 *  against (id + delivery_type + type_config for label/subhead). */
export interface AncillaryPoolItem {
  id: string
  delivery_type: string
  type_config: Record<string, unknown> | null
  ancillary_soft_target_date: string | null
  created_at: string | null
}


/** Full response shape from `/widget-data/ancillary-pool`. */
export interface AncillaryPoolWidgetData {
  operating_mode: "production" | "purchase" | "hybrid" | null
  is_vault_enabled: boolean
  items: AncillaryPoolItem[]
  total_count: number
  mode_note: "no_pool_in_purchase_mode" | null
  primary_navigation_target: "/dispatch" | null
}


// ── Hook return shape ───────────────────────────────────────────────


/** Surface-aware return contract. `isInteractive` discriminates the
 *  Detail vs Brief rendering path; both surfaces consume `items` +
 *  `loading` uniformly. */
export interface UseAncillaryPoolResult {
  /** Pool items. From context when interactive, from endpoint when
   *  read-only. The Detail variant gets the rich `DeliveryDTO` shape
   *  (drag-source fields populated); Brief variant gets the slim
   *  `AncillaryPoolItem` shape (id + label fields only).
   *
   *  We expose a unified shape via the `items` field — DeliveryDTO is
   *  a SUPERSET of AncillaryPoolItem, so the Detail path's items
   *  satisfy AncillaryPoolItem. The Brief variant only reads the
   *  AncillaryPoolItem subset of fields. Type-wise: items is typed
   *  as AncillaryPoolItem[]; the Detail variant separately consumes
   *  DeliveryDTO[] via `interactiveItems` when interactive. */
  items: AncillaryPoolItem[]
  /** Subset that's specifically the FH Focus interactive shape.
   *  Returns null when read-only (pulse_grid, spaces_pin). The
   *  Detail variant is the only consumer; Brief + Glance use
   *  `items`. */
  interactiveItems: DeliveryDTO[] | null
  /** True while the pool fetch (or context's reloadPool) is in
   *  flight. */
  loading: boolean
  /** True when context provides drag chrome + reload + optimistic
   *  helpers; false when fetched read-only. */
  isInteractive: boolean
  /** Total pool count. Matches `items.length` when items represents
   *  the full pool; could differ post-pagination (not used today). */
  totalCount: number
  /** Operating mode discriminator. Only meaningful in read-only mode
   *  (the context provider doesn't currently expose it). Brief
   *  variant uses this to render purchase-mode advisory. */
  operatingMode: "production" | "purchase" | "hybrid" | null
  /** Mode-related advisory key. `"no_pool_in_purchase_mode"` →
   *  Brief renders advisory + CTA; null → render real pool. */
  modeNote: "no_pool_in_purchase_mode" | null
  /** Whether vault product line is enabled. Read-only mode only. */
  isVaultEnabled: boolean
  /** Default navigate target for "Open in scheduling Focus" CTA. */
  primaryNavigationTarget: "/dispatch" | null
  /** Reload trigger. Context provides authoritative `reloadPool`;
   *  read-only mode wires a refetch. */
  reload: () => void
  /** Optimistic remove helper. Context wires the real impl; read-
   *  only mode is a no-op (no in-flight drag mutations to render). */
  removeFromPoolOptimistic: (deliveryId: string) => void
}


// ── Implementation ──────────────────────────────────────────────────


export function useAncillaryPool(): UseAncillaryPoolResult {
  // Always call both hooks — context-aware AND read-only-fetch — so
  // React rules-of-hooks are satisfied on every render. The fetch
  // effect bails out when context is non-null, so the interactive
  // path pays no network cost.
  const ctx = useSchedulingFocusOptional()

  const [fetchedData, setFetchedData] = useState<AncillaryPoolWidgetData | null>(null)
  const [fetchLoading, setFetchLoading] = useState<boolean>(true)
  const [refreshTick, setRefreshTick] = useState<number>(0)

  useEffect(() => {
    // Skip fetch when context provides authoritative data.
    if (ctx !== null) {
      setFetchLoading(false)
      return
    }
    let cancelled = false
    setFetchLoading(true)
    apiClient
      .get<AncillaryPoolWidgetData>("/widget-data/ancillary-pool")
      .then((r) => {
        if (cancelled) return
        setFetchedData(r.data)
      })
      .catch((e) => {
        if (cancelled) return
        // Surface-fetched widgets degrade gracefully on fetch error.
        // Pulse silent-filter discipline (§13.4.3) — surface error
        // via console.warn for telemetry, render empty state.
        // eslint-disable-next-line no-console
        console.warn("[useAncillaryPool] fetch failed:", e)
        setFetchedData({
          operating_mode: null,
          is_vault_enabled: false,
          items: [],
          total_count: 0,
          mode_note: null,
          primary_navigation_target: null,
        })
      })
      .finally(() => {
        if (!cancelled) setFetchLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [ctx, refreshTick])

  const reloadFetch = useCallback(() => {
    setRefreshTick((n) => n + 1)
  }, [])

  // Interactive path — context is the single source of truth.
  if (ctx !== null) {
    return {
      // Context's poolAncillaries are full DeliveryDTOs which satisfy
      // the AncillaryPoolItem subset.
      items: ctx.poolAncillaries.map(
        (d): AncillaryPoolItem => ({
          id: d.id,
          delivery_type: d.delivery_type,
          type_config: (d.type_config ?? null) as
            | Record<string, unknown>
            | null,
          ancillary_soft_target_date: null,  // not exposed via context
          created_at: null,                  // not exposed via context
        }),
      ),
      interactiveItems: ctx.poolAncillaries,
      loading: ctx.poolLoading,
      isInteractive: true,
      totalCount: ctx.poolAncillaries.length,
      // Context-provider mounts only inside FH Focus where vault is
      // operational by definition; surface mode discriminators as
      // null + production-equivalent defaults for type-safety.
      operatingMode: null,
      modeNote: null,
      isVaultEnabled: true,
      primaryNavigationTarget: "/dispatch",
      reload: ctx.reloadPool,
      removeFromPoolOptimistic: ctx.removeFromPoolOptimistic,
    }
  }

  // Read-only path — endpoint provides authoritative data.
  return {
    items: fetchedData?.items ?? [],
    interactiveItems: null,
    loading: fetchLoading,
    isInteractive: false,
    totalCount: fetchedData?.total_count ?? 0,
    operatingMode: fetchedData?.operating_mode ?? null,
    modeNote: fetchedData?.mode_note ?? null,
    isVaultEnabled: fetchedData?.is_vault_enabled ?? false,
    primaryNavigationTarget: fetchedData?.primary_navigation_target ?? null,
    reload: reloadFetch,
    removeFromPoolOptimistic: () => {
      // Read-only mode — no optimistic mutations. The widget can't
      // initiate drags, so this is a structural no-op rather than
      // a missing capability.
    },
  }
}
