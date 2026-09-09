/**
 * PeekContext — follow-up 4 of the UI/UX arc (arc finale).
 *
 * Single peek panel at a time. Opening a new peek closes the
 * current one. Hover triggers debounce 200ms before opening (to
 * avoid mouse-movement spam); click triggers open immediately.
 *
 * Session-scoped cache:
 *   Map<"{entity_type}:{entity_id}", { data, fetchedAt }>
 *   TTL = 5 min. Repeat hovers/clicks on the same entity reuse the
 *   cache — single backend call per entity per 5-min window.
 *
 * Cancellation:
 *   AbortController per in-flight fetch. Closing a peek before
 *   data lands cancels the request. Opening a new peek before the
 *   previous resolves cancels the previous.
 *
 * Mounted in App.tsx inside the authenticated tenant branch.
 * Platform-admin / login routes do NOT mount the provider; peek
 * triggers in those areas would need to use a null-safe variant
 * (none ship in this follow-up).
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { fetchPeek } from "@/services/peek-service";
import type {
  PeekEntityType,
  PeekResponse,
  PeekTriggerType,
} from "@/types/peek";


/** Session 3 (peek bridge) — a peek has two kinds of target.
 *
 *  "entity" is the original: an id that resolves to a tenant-owned
 *  row, fetched from `GET /peek/{type}/{id}`.
 *
 *  "widget" is the note surface's standing target: a widget id
 *  resolved against the widget renderer registry on the CLIENT.
 *  It makes NO /peek call — the widget self-fetches via
 *  `useWidgetData`, exactly as it does on every other surface.
 *  That is why the p50<100ms peek budget is untouched: there is no
 *  request to be slow. `_peek_saved_view` declined to execute a
 *  view on the peek path for this reason and that ruling stands. */
export type PeekTargetKind = "entity" | "widget";

export interface PeekEntityTarget {
  targetKind: "entity";
  entityType: PeekEntityType;
  entityId: string;
}

export interface PeekWidgetTarget {
  targetKind: "widget";
  widgetId: string;
  /** Header text. Comes from the standing entry's `label`
   *  (`note/registry.py` `_e(entry_id, label, target_key)`) because
   *  there is no peek response to read `display_label` from. */
  label: string;
}

export type CurrentPeek = (PeekEntityTarget | PeekWidgetTarget) & {
  triggerType: PeekTriggerType;
  anchorElement: HTMLElement | null;
  // Each open assigns a fresh nonce so panels can ignore stale
  // close-then-reopen races.
  openId: string;
};


export type PeekStatus = "idle" | "loading" | "loaded" | "error";


export interface PeekContextValue {
  current: CurrentPeek | null;
  data: PeekResponse | null;
  status: PeekStatus;
  error: string | null;
  /**
   * Open a peek. Hover triggers debounce 200ms before fetch+open;
   * click triggers fire immediately. If a peek is already open for
   * the same entity in the same trigger mode, this is a no-op.
   */
  openPeek: (args: {
    entityType: PeekEntityType;
    entityId: string;
    triggerType: PeekTriggerType;
    anchorElement?: HTMLElement | null;
  }) => void;
  /** Session 3 — open a peek whose content is a WIDGET, resolved
   *  client-side from the widget renderer registry. Makes no network
   *  request. Same 200ms hover debounce as `openPeek`. */
  openWidgetPeek: (args: {
    widgetId: string;
    label: string;
    triggerType: PeekTriggerType;
    anchorElement?: HTMLElement | null;
  }) => void;
  closePeek: () => void;
  /** Promote a hover-mode peek to click-mode (pinned). Called when
   *  the user moves the mouse INTO the floating panel. */
  promoteToClick: () => void;
}


const PeekContext = createContext<PeekContextValue | null>(null);


// ── Cache constants ────────────────────────────────────────────────

const CACHE_TTL_MS = 5 * 60 * 1000;
const HOVER_DEBOUNCE_MS = 200;


function cacheKey(entityType: string, entityId: string): string {
  return `${entityType}:${entityId}`;
}


export function PeekProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<CurrentPeek | null>(null);
  const [data, setData] = useState<PeekResponse | null>(null);
  const [status, setStatus] = useState<PeekStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  // Session-scoped cache. Cleared on provider unmount.
  const cacheRef = useRef<Map<string, { data: PeekResponse; fetchedAt: number }>>(
    new Map(),
  );
  const abortRef = useRef<AbortController | null>(null);
  // Pending hover-debounce timer.
  const hoverTimerRef = useRef<number | null>(null);
  // Generation counter to drop stale resolves.
  const genRef = useRef(0);

  // ── Internal helpers ────────────────────────────────────────────

  const cancelInFlight = useCallback(() => {
    if (abortRef.current !== null) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    if (hoverTimerRef.current !== null) {
      window.clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
  }, []);

  const closePeek = useCallback(() => {
    cancelInFlight();
    setCurrent(null);
    setData(null);
    setStatus("idle");
    setError(null);
  }, [cancelInFlight]);

  const fetchAndShow = useCallback(
    async (
      entityType: PeekEntityType,
      entityId: string,
      currentGen: number,
    ) => {
      const key = cacheKey(entityType, entityId);
      // Cache hit → skip network entirely.
      const cached = cacheRef.current.get(key);
      if (cached && Date.now() - cached.fetchedAt < CACHE_TTL_MS) {
        if (currentGen !== genRef.current) return;
        setData(cached.data);
        setStatus("loaded");
        setError(null);
        return;
      }

      const controller = new AbortController();
      abortRef.current = controller;
      setStatus("loading");
      setError(null);
      try {
        const resp = await fetchPeek(entityType, entityId, {
          signal: controller.signal,
        });
        if (currentGen !== genRef.current) return;
        if (controller.signal.aborted) return;
        cacheRef.current.set(key, { data: resp, fetchedAt: Date.now() });
        setData(resp);
        setStatus("loaded");
      } catch (err) {
        if (currentGen !== genRef.current) return;
        if (controller.signal.aborted) return;
        const msg =
          (err as { response?: { data?: { detail?: string } } })?.response
            ?.data?.detail ??
          (err instanceof Error ? err.message : "Couldn't load peek.");
        setError(String(msg));
        setStatus("error");
      }
    },
    [],
  );

  const openPeek = useCallback<PeekContextValue["openPeek"]>(
    ({ entityType, entityId, triggerType, anchorElement }) => {
      // No-op if same entity + same trigger mode is already open.
      if (
        current
        && current.targetKind === "entity"
        && current.entityType === entityType
        && current.entityId === entityId
        && current.triggerType === triggerType
      ) {
        return;
      }

      cancelInFlight();
      const myGen = ++genRef.current;
      const openId = `peek_${myGen}`;
      const next: CurrentPeek = {
        targetKind: "entity",
        entityType,
        entityId,
        triggerType,
        anchorElement: anchorElement ?? null,
        openId,
      };

      // Hover triggers: debounce 200ms before open. Cancellable by
      // a closePeek before the timer fires (e.g. mouse leaves the
      // anchor before the debounce window expires).
      if (triggerType === "hover") {
        hoverTimerRef.current = window.setTimeout(() => {
          hoverTimerRef.current = null;
          // Bail if a different open happened in the meantime.
          if (myGen !== genRef.current) return;
          setCurrent(next);
          setData(null);
          void fetchAndShow(entityType, entityId, myGen);
        }, HOVER_DEBOUNCE_MS);
        return;
      }

      // Click triggers: open immediately.
      setCurrent(next);
      setData(null);
      void fetchAndShow(entityType, entityId, myGen);
    },
    [current, cancelInFlight, fetchAndShow],
  );

  /** Session 3 — widget-target open. Deliberately does NOT call
   *  `fetchAndShow`: there is no /peek request for a widget target.
   *  Status is set straight to "loaded" and `data` cleared, so the
   *  host renders the widget branch rather than a skeleton. */
  const openWidgetPeek = useCallback<PeekContextValue["openWidgetPeek"]>(
    ({ widgetId, label, triggerType, anchorElement }) => {
      if (
        current
        && current.targetKind === "widget"
        && current.widgetId === widgetId
        && current.triggerType === triggerType
      ) {
        return;
      }

      cancelInFlight();
      const myGen = ++genRef.current;
      const next: CurrentPeek = {
        targetKind: "widget",
        widgetId,
        label,
        triggerType,
        anchorElement: anchorElement ?? null,
        openId: `peek_${myGen}`,
      };

      const show = () => {
        setCurrent(next);
        setData(null);
        setStatus("loaded");
        setError(null);
      };

      if (triggerType === "hover") {
        hoverTimerRef.current = window.setTimeout(() => {
          hoverTimerRef.current = null;
          if (myGen !== genRef.current) return;
          show();
        }, HOVER_DEBOUNCE_MS);
        return;
      }

      show();
    },
    [current, cancelInFlight],
  );

  const promoteToClick = useCallback(() => {
    setCurrent((prev) =>
      prev && prev.triggerType === "hover"
        ? { ...prev, triggerType: "click" }
        : prev,
    );
  }, []);

  // Clean up any pending state on unmount.
  useEffect(
    () => () => {
      cancelInFlight();
    },
    [cancelInFlight],
  );

  const value: PeekContextValue = {
    current,
    data,
    status,
    error,
    openPeek,
    openWidgetPeek,
    closePeek,
    promoteToClick,
  };

  return (
    <PeekContext.Provider value={value}>{children}</PeekContext.Provider>
  );
}


/**
 * Hook for components that need to open / close peeks. Throws when
 * no provider is mounted — surfaces missing-provider bugs at the
 * call site rather than failing silently.
 */
export function usePeek(): PeekContextValue {
  const ctx = useContext(PeekContext);
  if (!ctx) {
    throw new Error("usePeek must be used within PeekProvider");
  }
  return ctx;
}


/**
 * Null-safe variant for surfaces that may render outside a
 * PeekProvider tree (login pages, platform admin, embedded
 * widgets in non-tenant contexts). Returns null when absent;
 * caller suppresses peek triggers gracefully.
 */
export function usePeekOptional(): PeekContextValue | null {
  return useContext(PeekContext);
}


// Test seam — exported for vitest only. Not used in production code.
export const _PEEK_TEST_HOOKS = {
  CACHE_TTL_MS,
  HOVER_DEBOUNCE_MS,
  cacheKey,
};
