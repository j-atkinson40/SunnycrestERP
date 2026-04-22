/**
 * FocusContext — Phase A Session 1 (Focus primitive scaffolding).
 *
 * The third platform primitive per PLATFORM_ARCHITECTURE.md §5: a
 * bounded-decision surface. Spaces (Monitor) are persistent contexts;
 * Command Bar (Act) is ephemeral single-action; Focus (Decide) is a
 * full-screen, decision-bounded overlay where a specific decision
 * happens with everything needed laid out.
 *
 * Session 1 ships the state machinery + URL sync. Later sessions
 * build on top:
 *   Session 2–3: anchored core mode dispatch + free-form canvas
 *   Session 4:   15-second return-pill countdown + database
 *                persistence via `focus_sessions` table
 *   Session 5–6: pin system (saved + context-aware + system-suggested)
 *   Session 7:   Focus Chat (scoped Q&A surface)
 *
 * State shape + URL discipline
 * ────────────────────────────
 * The URL is the source of truth after initial mount. `open(id)`
 * pushes `?focus=<id>` via useSearchParams; `close()` removes the
 * param. A useEffect watches the param and reconciles context state.
 * Browser back/forward naturally dismisses/reopens the Focus because
 * navigation rewrites the URL, which re-triggers the reconcile.
 *
 * Command Bar interaction
 * ───────────────────────
 * Per architectural decision: Command Bar is hidden while a Focus is
 * open. Bounded-decision discipline. Information lookup needs inside
 * a Focus are answered by Focus Chat (Session 7), not by escaping to
 * the Command Bar. CommandBarProvider consumes `useFocus()` to gate
 * its render + keyboard shortcuts — see core/CommandBarProvider.tsx.
 *
 * Return pill
 * ───────────
 * When a Focus closes, we stash the previously-open state in
 * `lastClosedFocus` so `ReturnPill` can render "Return to <id>".
 * Session 1 has no countdown — pill persists until the user clicks
 * the X or opens another Focus. Session 4 layers the 15s countdown +
 * re-arm-on-state-change semantics per PA §5.4 on top.
 *
 * Mounted in App.tsx inside BrowserRouter + above CommandBarProvider
 * so the command bar can consume Focus state.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useSearchParams } from "react-router-dom";

import type { LayoutState } from "./focus-registry";


/** Active Focus session state. `params` reserved for later sessions
 *  (entity scope, preset overrides, etc.). `layoutState` holds the
 *  session-ephemeral layout tier (Session 2 scaffolding); Session 4
 *  adds the per-user + tenant-default tiers via `focus_sessions` +
 *  `focus_layout_defaults` tables. */
export interface FocusState {
  id: string;
  openedAt: Date;
  params: Record<string, unknown>;
  /** Session-ephemeral layout — resets on Focus close. Null until
   *  the consumer calls `updateSessionLayout(...)`. Session 4 seeds
   *  this from `config.defaultLayout?.userOverride ?? tenantDefault`
   *  on open. */
  layoutState: LayoutState | null;
}


export interface FocusOpenOptions {
  /** Optional scope parameters passed to the Focus core. Reserved
   *  for later sessions — Session 1 stores but does not consume. */
  params?: Record<string, unknown>;
}


export interface FocusContextValue {
  /** Currently-open Focus, or null when no Focus is active. */
  currentFocus: FocusState | null;
  /** Derived: true when currentFocus !== null. Cheap to consume. */
  isOpen: boolean;
  /** Last closed Focus — fuels the ReturnPill. Cleared when a new
   *  Focus opens OR when the user dismisses the pill. */
  lastClosedFocus: FocusState | null;
  /** Open a Focus programmatically. If another Focus is open it is
   *  replaced (only one Focus active at a time). URL is updated
   *  to `?focus=<id>`. */
  open: (id: string, options?: FocusOpenOptions) => void;
  /** Close the currently-open Focus. URL param is removed. The
   *  just-closed state moves into `lastClosedFocus`. */
  close: () => void;
  /** Dismiss the return pill without re-entering the Focus. Clears
   *  `lastClosedFocus`. */
  dismissReturnPill: () => void;
  /** Patch the current Focus's session-ephemeral layout state. No-op
   *  if no Focus is open. Session 2 persists only in memory; Session
   *  4 wires `focus_sessions` for per-user persistence. */
  updateSessionLayout: (patch: Partial<LayoutState>) => void;
}


const FocusContext = createContext<FocusContextValue | null>(null);


/**
 * Read the Focus context. Throws if called outside FocusProvider —
 * no silent no-ops, because a missing provider is a load-bearing
 * mount-order bug not a render-time feature toggle.
 */
export function useFocus(): FocusContextValue {
  const ctx = useContext(FocusContext);
  if (ctx === null) {
    throw new Error(
      "useFocus() called outside FocusProvider. Mount FocusProvider " +
        "in App.tsx above any component that needs Focus state.",
    );
  }
  return ctx;
}


export function FocusProvider({ children }: { children: ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [currentFocus, setCurrentFocus] = useState<FocusState | null>(null);
  const [lastClosedFocus, setLastClosedFocus] = useState<FocusState | null>(
    null,
  );

  // Track the most recently active Focus for the open→close transition
  // detection. Updated whenever we set currentFocus to a non-null value,
  // consumed in the URL-watcher effect.
  const prevFocusRef = useRef<FocusState | null>(null);

  // Pending params awaiting URL reconcile. open() writes here so that
  // when the URL reconcile effect picks up the new param it can attach
  // the full state (including params) instead of only the id. Cleared
  // when consumed.
  const pendingParamsRef = useRef<Record<string, unknown> | null>(null);

  const focusParam = searchParams.get("focus");

  // Sync state FROM URL. The URL is the source of truth after initial
  // mount; this effect reconciles context state whenever it changes.
  useEffect(() => {
    if (focusParam) {
      // URL says a Focus should be open.
      if (
        prevFocusRef.current === null ||
        prevFocusRef.current.id !== focusParam
      ) {
        const newFocus: FocusState = {
          id: focusParam,
          openedAt: new Date(),
          params: pendingParamsRef.current ?? {},
          layoutState: null,
        };
        pendingParamsRef.current = null;
        setCurrentFocus(newFocus);
        setLastClosedFocus(null);
        prevFocusRef.current = newFocus;
      }
    } else if (prevFocusRef.current !== null) {
      // URL says no Focus; we were previously open → transition to
      // closed. Stash the prior state so ReturnPill can render.
      setLastClosedFocus(prevFocusRef.current);
      setCurrentFocus(null);
      prevFocusRef.current = null;
    }
    // else: no focus param AND we weren't open — nothing to do.
  }, [focusParam]);

  const open = useCallback(
    (id: string, options?: FocusOpenOptions) => {
      pendingParamsRef.current = options?.params ?? {};
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.set("focus", id);
          return next;
        },
        { replace: false },
      );
    },
    [setSearchParams],
  );

  const close = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("focus");
        return next;
      },
      { replace: false },
    );
  }, [setSearchParams]);

  const dismissReturnPill = useCallback(() => {
    setLastClosedFocus(null);
  }, []);

  const updateSessionLayout = useCallback(
    (patch: Partial<LayoutState>) => {
      setCurrentFocus((prev) => {
        if (prev === null) return prev;
        const base: LayoutState = prev.layoutState ?? { widgets: {} };
        return {
          ...prev,
          layoutState: {
            ...base,
            ...patch,
            widgets: { ...base.widgets, ...(patch.widgets ?? {}) },
          },
        };
      });
    },
    [],
  );

  const value = useMemo<FocusContextValue>(
    () => ({
      currentFocus,
      isOpen: currentFocus !== null,
      lastClosedFocus,
      open,
      close,
      dismissReturnPill,
      updateSessionLayout,
    }),
    [
      currentFocus,
      lastClosedFocus,
      open,
      close,
      dismissReturnPill,
      updateSessionLayout,
    ],
  );

  return (
    <FocusContext.Provider value={value}>{children}</FocusContext.Provider>
  );
}
