/**
 * FocusContext — Phase A Session 1 + persistence in Session 4.
 *
 * The third platform primitive per PLATFORM_ARCHITECTURE.md §5: a
 * bounded-decision surface. Spaces (Monitor) are persistent contexts;
 * Command Bar (Act) is ephemeral single-action; Focus (Decide) is a
 * full-screen, decision-bounded overlay where a specific decision
 * happens with everything needed laid out.
 *
 * Session 1 shipped state machinery + URL sync. Session 4 adds
 * server-side persistence via focus_sessions + focus_layout_defaults
 * tables with 3-tier resolution (active user session → recent closed
 * within 24h → tenant default → registry default).
 *
 * State shape + URL discipline
 * ────────────────────────────
 * The URL is the source of truth after initial mount. `open(id)`
 * pushes `?focus=<id>` via useSearchParams; `close()` removes the
 * param. A useEffect watches the param and reconciles context state.
 * Browser back/forward naturally dismisses/reopens the Focus because
 * navigation rewrites the URL, which re-triggers the reconcile.
 *
 * Persistence — optimistic loading (Session 4)
 * ────────────────────────────────────────────
 * On Focus open: (1) immediately render from registry defaultLayout
 * (<100ms perceived latency per Quality Bar §1), (2) in parallel fire
 * POST /focus/{focus_type}/open which creates-or-resumes the server
 * session and returns the resolved layout via the 3-tier cascade,
 * (3) when the fetch resolves, swap to persisted state (keeps the
 * widgets where the user left them). If the fetch fails, log + keep
 * the optimistic default — persistence never blocks UX.
 *
 * Layout writes are debounced 500ms so rapid drag/resize doesn't
 * spam the server.
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
 * Session 4 layers the 15s countdown + re-arm-on-state-change
 * semantics on top — see `useReturnPillCountdown`.
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

import {
  closeFocusSession,
  openFocusSession,
  updateFocusLayout,
} from "@/services/focus-service";

import { getFocusConfig, type LayoutState, type WidgetId } from "./focus-registry";


/** Debounce window for layout-write flushes. 500ms matches saved-view
 *  update debounces elsewhere in the arc. Balances server load with
 *  responsiveness if the user stops moving briefly mid-drag. */
const LAYOUT_WRITE_DEBOUNCE_MS = 500;


/** Active Focus session state. `params` reserved for later sessions
 *  (entity scope, preset overrides, etc.). `layoutState` holds the
 *  currently-rendered layout; Session 4 seeds it optimistically from
 *  the registry default and then swaps to the server-resolved layout
 *  when the POST /open fetch resolves. */
export interface FocusState {
  id: string;
  openedAt: Date;
  params: Record<string, unknown>;
  /** Currently-rendered layout. Seeded optimistically from registry
   *  default on open; replaced with server-resolved layout when the
   *  POST /open fetch settles (3-tier cascade: active → recent →
   *  default → null-then-fallback-to-registry). */
  layoutState: LayoutState | null;
  /** Server session id once POST /open resolves. Null until then.
   *  Layout writes are gated on this — we don't fire PATCH until
   *  we know the session ID. */
  sessionId: string | null;
  /** True while POST /open is in flight. Frontend doesn't use this
   *  for loading spinners (optimistic load renders immediately) but
   *  it's available for diagnostics + tests. */
  isSyncing: boolean;
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
   *  4 wires `focus_sessions` for per-user persistence.
   *
   *  Widget merge semantics: keys in `patch.widgets` override keys in
   *  existing widgets; keys NOT in the patch are preserved. Use
   *  `removeWidget` below to delete a widget (cannot express deletion
   *  via the patch API because missing keys mean "unchanged"). */
  updateSessionLayout: (patch: Partial<LayoutState>) => void;
  /** Remove a widget from the current Focus's layout state. No-op if
   *  no Focus is open or the widget id is absent. Widget-dismiss (X
   *  chrome) calls this. */
  removeWidget: (widgetId: WidgetId) => void;
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

  // Debounced layout-write scheduler. Holds a timer id per-session;
  // each updateSessionLayout call cancels the previous timer and
  // schedules a fresh one. On timer fire, the latest layoutState is
  // PATCHed to the server. Cleared on session close so stale writes
  // never race a close.
  const layoutWriteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
  const pendingWriteLayoutRef = useRef<LayoutState | null>(null);
  const cancelPendingLayoutWrite = useCallback(() => {
    if (layoutWriteTimerRef.current !== null) {
      clearTimeout(layoutWriteTimerRef.current);
      layoutWriteTimerRef.current = null;
    }
    pendingWriteLayoutRef.current = null;
  }, []);

  // Sync state FROM URL. The URL is the source of truth after initial
  // mount; this effect reconciles context state whenever it changes.
  useEffect(() => {
    if (focusParam) {
      // URL says a Focus should be open.
      if (
        prevFocusRef.current === null ||
        prevFocusRef.current.id !== focusParam
      ) {
        // Optimistic load (Session 4): seed layoutState from registry
        // defaultLayout immediately so the first paint is instant.
        // The server POST /open kicks off in parallel below; when it
        // resolves, we swap to the persisted layout.
        const seededLayout =
          getFocusConfig(focusParam)?.defaultLayout?.tenantDefault ?? null;
        const newFocus: FocusState = {
          id: focusParam,
          openedAt: new Date(),
          params: pendingParamsRef.current ?? {},
          layoutState: seededLayout,
          sessionId: null,
          isSyncing: true,
        };
        pendingParamsRef.current = null;
        setCurrentFocus(newFocus);
        setLastClosedFocus(null);
        prevFocusRef.current = newFocus;

        // Fire POST /open in parallel with the optimistic render.
        const focusTypeAtRequest = focusParam;
        void openFocusSession(focusParam)
          .then((resp) => {
            // If user navigated to a different Focus (or closed)
            // before this resolved, drop the response — stale path.
            if (
              prevFocusRef.current === null ||
              prevFocusRef.current.id !== focusTypeAtRequest
            ) {
              return;
            }
            const persistedLayout =
              (resp.layout_state as LayoutState | null) ?? null;
            setCurrentFocus((prev) => {
              if (prev === null || prev.id !== focusTypeAtRequest) {
                return prev;
              }
              return {
                ...prev,
                sessionId: resp.session.id,
                isSyncing: false,
                // Use persisted layout if server returned one;
                // otherwise keep the optimistic registry default.
                layoutState:
                  persistedLayout !== null && "widgets" in persistedLayout
                    ? persistedLayout
                    : prev.layoutState,
              };
            });
            // Update prevFocusRef to match so close path picks it up.
            if (
              prevFocusRef.current !== null &&
              prevFocusRef.current.id === focusTypeAtRequest
            ) {
              prevFocusRef.current = {
                ...prevFocusRef.current,
                sessionId: resp.session.id,
                isSyncing: false,
              };
            }
          })
          .catch((err) => {
            // Persistence failure never blocks UX. Log + continue
            // with the optimistic registry default.
            // eslint-disable-next-line no-console
            console.warn(
              "[focus] openFocusSession failed — continuing with registry default",
              err,
            );
            setCurrentFocus((prev) =>
              prev === null || prev.id !== focusTypeAtRequest
                ? prev
                : { ...prev, isSyncing: false },
            );
          });
      }
    } else if (prevFocusRef.current !== null) {
      // URL says no Focus; we were previously open → transition to
      // closed. Stash the prior state so ReturnPill can render.
      const closingFocus = prevFocusRef.current;
      setLastClosedFocus(closingFocus);
      setCurrentFocus(null);
      prevFocusRef.current = null;

      // Flush any pending layout write before the close, then fire
      // POST /close. Both best-effort — UI doesn't wait on either.
      const pendingLayout = pendingWriteLayoutRef.current;
      const sessionId = closingFocus.sessionId;
      cancelPendingLayoutWrite();
      if (sessionId !== null) {
        const flushPromise =
          pendingLayout !== null
            ? updateFocusLayout(sessionId, pendingLayout).catch((err) => {
                // eslint-disable-next-line no-console
                console.warn("[focus] final layout flush failed", err);
              })
            : Promise.resolve();
        void flushPromise.then(() =>
          closeFocusSession(sessionId).catch((err) => {
            // eslint-disable-next-line no-console
            console.warn("[focus] closeFocusSession failed", err);
          }),
        );
      }
    }
    // else: no focus param AND we weren't open — nothing to do.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  /** Schedule a debounced PATCH /layout flush. Called after every
   *  in-memory layout change. The most recent layout wins — earlier
   *  pending timers are cancelled when a new one is scheduled. */
  const scheduleLayoutWrite = useCallback(
    (nextLayout: LayoutState, sessionId: string | null) => {
      pendingWriteLayoutRef.current = nextLayout;
      if (sessionId === null) {
        // No session yet (POST /open hasn't resolved). Keep the
        // latest layout in pendingWriteLayoutRef; it'll be picked
        // up on next updateSessionLayout call that has a sessionId.
        return;
      }
      if (layoutWriteTimerRef.current !== null) {
        clearTimeout(layoutWriteTimerRef.current);
      }
      layoutWriteTimerRef.current = setTimeout(() => {
        layoutWriteTimerRef.current = null;
        const toWrite = pendingWriteLayoutRef.current;
        pendingWriteLayoutRef.current = null;
        if (toWrite === null) return;
        updateFocusLayout(sessionId, toWrite).catch((err) => {
          // eslint-disable-next-line no-console
          console.warn("[focus] updateFocusLayout failed", err);
        });
      }, LAYOUT_WRITE_DEBOUNCE_MS);
    },
    [],
  );

  const updateSessionLayout = useCallback(
    (patch: Partial<LayoutState>) => {
      setCurrentFocus((prev) => {
        if (prev === null) return prev;
        const base: LayoutState = prev.layoutState ?? { widgets: {} };
        const nextLayout: LayoutState = {
          ...base,
          ...patch,
          widgets: { ...base.widgets, ...(patch.widgets ?? {}) },
        };
        // Best-effort background persistence. Don't block the UI
        // state update on the fetch.
        scheduleLayoutWrite(nextLayout, prev.sessionId);
        return { ...prev, layoutState: nextLayout };
      });
    },
    [scheduleLayoutWrite],
  );

  const removeWidget = useCallback(
    (widgetId: WidgetId) => {
      setCurrentFocus((prev) => {
        if (prev === null || prev.layoutState === null) return prev;
        if (!(widgetId in prev.layoutState.widgets)) return prev;
        const { [widgetId]: _removed, ...remaining } =
          prev.layoutState.widgets;
        void _removed;
        const nextLayout: LayoutState = {
          ...prev.layoutState,
          widgets: remaining,
        };
        scheduleLayoutWrite(nextLayout, prev.sessionId);
        return { ...prev, layoutState: nextLayout };
      });
    },
    [scheduleLayoutWrite],
  );

  // Clean up any pending write timer on unmount.
  useEffect(() => {
    return () => cancelPendingLayoutWrite();
  }, [cancelPendingLayoutWrite]);

  const value = useMemo<FocusContextValue>(
    () => ({
      currentFocus,
      isOpen: currentFocus !== null,
      lastClosedFocus,
      open,
      close,
      dismissReturnPill,
      updateSessionLayout,
      removeWidget,
    }),
    [
      currentFocus,
      lastClosedFocus,
      open,
      close,
      dismissReturnPill,
      updateSessionLayout,
      removeWidget,
    ],
  );

  return (
    <FocusContext.Provider value={value}>{children}</FocusContext.Provider>
  );
}
