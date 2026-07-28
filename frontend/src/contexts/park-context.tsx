/**
 * ParkContext — S-5, the spatial working-set layer of Act.
 *
 * Park holds N concurrent LIGHT ACTS + reference tablets on a free-form
 * canvas, assembled from the command bar and worked across at once. This
 * is the CLIENT-MEMORY session store (RULED Type B #2): tablets, per-act
 * drafts, and canvas positions live in React state — nothing server-
 * persisted, no table, no reaper (the ephemerality). A hard refresh ends
 * the session; a DELIBERATE exit arms a grace-window relaunch pill.
 *
 * THE NO-DATA-BEFORE-COMMIT GUARANTEE (structural): this context has NO
 * commit path. It never calls a write endpoint. A tablet's draft lives
 * here in memory; only the tablet's own Send/Save gesture calls a commit
 * service directly. When the session evaporates, un-committed drafts
 * leave ZERO rows behind — because nothing here ever wrote them.
 *
 * PEER LAYER + SUSPEND-AND-RETURN (spec): park is a peer to the command
 * bar and Focus, not a child of either. It coexists with the bar (park
 * must NOT touch `?focus=`/`currentFocus`, or the Focus-exclusivity gate
 * would close the bar). When a Focus opens (escalation, or any Focus
 * while park is arranged), park SUSPENDS — `isSuspended` derives from
 * Focus state; the ParkHost hides tablets but the SESSION STATE IS HELD.
 * On Focus close, park RESUMES: same tablets, arrangement, drafts, no
 * countdown (suspension ≠ exit).
 *
 * ESCALATION (RULED Type B #1): `escalate` reads the act-type's declared
 * escalation target from the park act-registry (`escalationFocusFor`) —
 * park holds no hardcoded list. If the act declares a registered Focus,
 * park opens it and hands off the tablet's draft as the Focus params (the
 * S-3a crossing, now fired from park); park then suspends behind it.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"

import { useFocusOptional } from "@/contexts/focus-context"
import type { WidgetPosition } from "@/contexts/focus-registry"
import {
  escalationFocusFor,
  getParkAct,
} from "@/components/park/park-act-registry"
import { _setParkSummon } from "@/components/park/park-summon"

/** One parked act/reference tablet. `draft` is per-act, in-memory only —
 *  its shape is act-defined; the tablet owns it. */
export interface ParkTablet {
  tabletId: string
  actType: string
  widgetType: string
  position: WidgetPosition
  draft: Record<string, unknown>
}

export interface ParkSession {
  tablets: ParkTablet[]
}

export interface ParkContextValue {
  /** Tablets currently in the working set (empty when park is closed). */
  tablets: ParkTablet[]
  /** True when park has ≥1 tablet AND is not suspended behind a Focus. */
  isActive: boolean
  /** True while a Focus is open over an arranged park — tablets hidden,
   *  session held intact (suspend-and-return). */
  isSuspended: boolean
  /** Summon a new tablet for an act-type. Returns its tablet id. */
  summon: (actType: string) => string | null
  /** Remove one tablet (dismiss, not exit — no grace pill). */
  dismissTablet: (tabletId: string) => void
  /** Update a tablet's in-memory draft — a full object OR a functional
   *  updater `(prev) => next` (use the updater to merge against the LATEST
   *  draft, avoiding stale-closure clobbering from async seeds). NEVER
   *  commits. */
  updateDraft: (
    tabletId: string,
    draft:
      | Record<string, unknown>
      | ((prev: Record<string, unknown>) => Record<string, unknown>),
  ) => void
  /** Persist a tablet's canvas position (drag/resize → park session). */
  updateTabletPosition: (tabletId: string, position: WidgetPosition) => void
  /** Escalate a tablet to its declared Focus (if any), handing off its
   *  draft. No-op for light acts. Park suspends behind the opened Focus. */
  escalate: (tabletId: string) => void
  /** Whether a tablet's act-type escalates (declares a registered Focus).
   *  Tablets read this to decide whether to show an escalate affordance. */
  canEscalate: (tabletId: string) => boolean
  /** Deliberate exit — stash the session for the grace window + close. */
  exitPark: () => void
  /** The just-exited session, held for the grace window (drives the
   *  relaunch pill). Null when there's nothing to relaunch. */
  lastClosedSession: ParkSession | null
  /** Restore the last-closed session (grace-window relaunch). */
  relaunchSession: () => void
  /** Drop the last-closed session (grace window expired / dismissed). */
  clearLastClosed: () => void
}

const ParkContext = createContext<ParkContextValue | null>(null)

export function usePark(): ParkContextValue {
  const ctx = useContext(ParkContext)
  if (ctx === null) {
    throw new Error("usePark() called outside ParkProvider.")
  }
  return ctx
}

/** Null-safe variant — components that may render outside the park tree
 *  (e.g. the admin editor preview) call this. */
export function useParkOptional(): ParkContextValue | null {
  return useContext(ParkContext)
}

// Module-scoped id source — stable React keys + tablet identity. Not
// crypto.randomUUID (jsdom/vitest don't reliably expose it); a per-
// session counter suffices.
let _seq = 0
function nextTabletId(): string {
  _seq += 1
  return `pt${_seq}`
}

/** Simple slice-1 placement: lay new tablets out left-to-right with a
 *  slight vertical stagger so the working set reads as distinct tablets
 *  rather than a stack. Wraps to a second row after 3. Smart-positioning
 *  engine deferred (§5.7). */
function seedPosition(index: number, size: { width: number; height: number }): WidgetPosition {
  const col = index % 3
  const row = Math.floor(index / 3)
  return {
    anchor: "top-left",
    offsetX: 40 + col * 372,
    offsetY: 88 + row * 300 + (col % 2) * 40,
    width: size.width,
    height: size.height,
  }
}

export function ParkProvider({ children }: { children: ReactNode }) {
  const focus = useFocusOptional()
  const [session, setSession] = useState<ParkSession | null>(null)
  const [lastClosedSession, setLastClosedSession] =
    useState<ParkSession | null>(null)

  const tablets = session?.tablets ?? []
  const focusOpen = focus?.isOpen ?? false
  // Suspend-and-return: any open Focus over an arranged park suspends it.
  const isSuspended = focusOpen && tablets.length > 0
  const isActive = tablets.length > 0 && !isSuspended

  const summon = useCallback((actType: string): string | null => {
    const act = getParkAct(actType)
    if (!act) return null
    const tabletId = nextTabletId()
    setSession((prev) => {
      const existing = prev?.tablets ?? []
      const tablet: ParkTablet = {
        tabletId,
        actType,
        widgetType: act.widgetType,
        position: seedPosition(existing.length, act.defaultSize),
        draft: {},
      }
      return { tablets: [...existing, tablet] }
    })
    return tabletId
  }, [])

  const dismissTablet = useCallback((tabletId: string) => {
    setSession((prev) => {
      if (!prev) return prev
      const tablets = prev.tablets.filter((t) => t.tabletId !== tabletId)
      return tablets.length > 0 ? { tablets } : null
    })
  }, [])

  const updateDraft = useCallback(
    (
      tabletId: string,
      draft:
        | Record<string, unknown>
        | ((prev: Record<string, unknown>) => Record<string, unknown>),
    ) => {
      // In-memory ONLY. No commit path exists here by construction.
      setSession((prev) => {
        if (!prev) return prev
        return {
          tablets: prev.tablets.map((t) =>
            t.tabletId === tabletId
              ? {
                  ...t,
                  draft: typeof draft === "function" ? draft(t.draft) : draft,
                }
              : t,
          ),
        }
      })
    },
    [],
  )

  const updateTabletPosition = useCallback(
    (tabletId: string, position: WidgetPosition) => {
      setSession((prev) => {
        if (!prev) return prev
        return {
          tablets: prev.tablets.map((t) =>
            t.tabletId === tabletId ? { ...t, position } : t,
          ),
        }
      })
    },
    [],
  )

  const canEscalate = useCallback(
    (tabletId: string) => {
      const tablet = session?.tablets.find((t) => t.tabletId === tabletId)
      if (!tablet) return false
      return escalationFocusFor(tablet.actType) !== null
    },
    [session],
  )

  const escalate = useCallback(
    (tabletId: string) => {
      const tablet = session?.tablets.find((t) => t.tabletId === tabletId)
      if (!tablet) return
      // Park READS the declaration — no hardcoded list here.
      const focusId = escalationFocusFor(tablet.actType)
      if (!focusId || !focus) return
      // Hand off the tablet's draft as the Focus params (S-3a crossing).
      // The session STAYS intact — park suspends (derived), not exits;
      // the tablet is still here on Focus close (suspend-and-return).
      focus.open(focusId, { params: { extraction: tablet.draft } })
    },
    [session, focus],
  )

  const exitPark = useCallback(() => {
    setSession((prev) => {
      if (prev && prev.tablets.length > 0) setLastClosedSession(prev)
      return null
    })
  }, [])

  const relaunchSession = useCallback(() => {
    setLastClosedSession((prev) => {
      if (prev) setSession(prev)
      return null
    })
  }, [])

  const clearLastClosed = useCallback(() => setLastClosedSession(null), [])

  // Publish summon to the command-bar bridge (intent-shaped summon lands
  // through command-bar actions, which aren't React-context aware).
  useEffect(() => {
    _setParkSummon(summon)
    return () => _setParkSummon(null)
  }, [summon])

  const value = useMemo<ParkContextValue>(
    () => ({
      tablets,
      isActive,
      isSuspended,
      summon,
      dismissTablet,
      updateDraft,
      updateTabletPosition,
      escalate,
      canEscalate,
      exitPark,
      lastClosedSession,
      relaunchSession,
      clearLastClosed,
    }),
    [
      tablets,
      isActive,
      isSuspended,
      summon,
      dismissTablet,
      updateDraft,
      updateTabletPosition,
      escalate,
      canEscalate,
      exitPark,
      lastClosedSession,
      relaunchSession,
      clearLastClosed,
    ],
  )

  return <ParkContext.Provider value={value}>{children}</ParkContext.Provider>
}
