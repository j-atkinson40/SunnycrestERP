/**
 * Phase R-0 — EditModeProvider + useEditMode hook.
 *
 * Context plumbing for the runtime-aware editor. R-0 ships ZERO UI;
 * this module establishes the contract that R-1+ tenant-component
 * consumers and editor-side panels build on. The provider does NOT
 * yet wrap any tenant components — that's R-1's job.
 *
 * Contract (props provided by EditModeProvider):
 *   - tenantSlug:        which tenant the runtime editor is rendering
 *   - impersonatedUserId: which user the impersonation token represents
 *   - isEditing:         current edit-mode state (toggled by setEditing)
 *   - pageContext:       derived from URL or set explicitly
 *   - selectedComponentName / selectComponent: the per-element
 *     selection model (R-2 surface; R-0 ships the contract only)
 *   - draftOverrides:    Map of staged overrides keyed by overrideKey
 *     (`${overrideType}:${componentName}` for component overrides;
 *     other types use their own conventions)
 *   - stageOverride:     buffer an unsaved change in memory
 *   - clearStaged:       drop staged overrides for one componentName
 *   - commitDraft:       write all staged overrides through the
 *     dual-token client to the appropriate platform service
 *   - discardDraft:      reset staged state without touching backend
 *   - setEditing:        toggle edit-mode (page-level, per area 10)
 *
 * useEditMode() OUTSIDE a provider returns a stub with isEditing=false
 * and no-op setters. This matches the existing widget `_editMode`
 * convention (every widget reads `(props._editMode as boolean) || false`)
 * — components can call useEditMode unconditionally without crashing.
 *
 * commitDraft routing is the contract every runtime-aware editor
 * write follows. The provider holds a router map from override-type
 * to platform endpoint:
 *
 *   override.type === "token"            → /api/platform/admin/visual-editor/themes
 *   override.type === "component_prop"   → /api/platform/admin/visual-editor/components
 *   override.type === "component_class"  → /api/platform/admin/visual-editor/classes
 *   override.type === "dashboard_layout" → /api/platform/admin/visual-editor/dashboard-layouts
 *
 * The router is closure-injectable for tests; the default routes
 * through `useRuntimeHostClient`. R-0 ships the routing contract +
 * default no-op implementations; R-1+ wires the actual service
 * endpoints.
 */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react"

import {
  useRuntimeHostClient,
  type DualTokenHelpers,
} from "./dual-token-client"


/** The override types runtime-aware editors author. R-0 establishes
 *  the contract; R-1+ phases wire each type through commitDraft to
 *  its platform endpoint. */
export type RuntimeOverrideType =
  | "token"
  | "component_prop"
  | "component_class"
  | "dashboard_layout"


export interface RuntimeOverride {
  type: RuntimeOverrideType
  /** Component-scoped target identifier:
   *   - For "token": the token name (e.g. "accent").
   *   - For "component_prop": `${component_kind}:${component_name}`.
   *   - For "component_class": the class name (e.g. "widget").
   *   - For "dashboard_layout": the page_context (e.g. "dashboard"). */
  target: string
  /** The prop / token / config key being overridden inside the target.
   *  - For "token": "value" (the override IS the value at that key).
   *  - For "component_prop": the prop name being changed.
   *  - For "component_class": the class-prop name being changed.
   *  - For "dashboard_layout": "layout_config" (a layout is replaced
   *    as a whole, not field-merged). */
  prop: string
  /** The new value (raw — service layer validates types). */
  value: unknown
}


/** A unique key for a staged override. Used as the Map key in
 *  `draftOverrides`. Multiple overrides on the same target+prop
 *  collapse — staging the same key twice replaces. */
export function overrideKey(o: Pick<RuntimeOverride, "type" | "target" | "prop">): string {
  return `${o.type}::${o.target}::${o.prop}`
}


export interface EditModeState {
  /** Tenant slug being rendered. Editor can navigate but cannot
   *  switch tenant without re-issuing impersonation. Required when
   *  inside a real provider; null in the stub. */
  tenantSlug: string | null
  /** User the impersonation token represents. */
  impersonatedUserId: string | null
  /** Page-level edit-mode toggle (per area 10 recommendation).
   *  Per-element selection within an edited page is separate. */
  isEditing: boolean
  /** The route-derived page_context string (e.g. "dashboard",
   *  "ops_board"). null when not yet resolved. */
  pageContext: string | null
  /** The component name currently selected for editing within the
   *  active page. null when no selection. */
  selectedComponentName: string | null
  /** Staged overrides pending commit. Map keys come from
   *  `overrideKey(...)`; values are full RuntimeOverride records. */
  draftOverrides: ReadonlyMap<string, RuntimeOverride>
  /** Whether commitDraft has fired but not yet completed. */
  isCommitting: boolean
  /** Last commit error, if any. */
  commitError: string | null
}


export interface EditModeActions {
  setEditing(next: boolean): void
  setPageContext(next: string | null): void
  selectComponent(name: string | null): void
  /** Stage one override. Multiple stages with the same overrideKey
   *  replace; differing prop on same target accumulate. */
  stageOverride(o: RuntimeOverride): void
  /** Drop all staged overrides for the given (type, target). Used by
   *  the "reset" affordance in the inspector panel. */
  clearStaged(type: RuntimeOverrideType, target: string): void
  /** Commit all staged overrides through the dual-token client to
   *  their platform endpoints. Resolves with the commit's per-type
   *  outcome dictionary; rejects if any subset failed. */
  commitDraft(): Promise<RuntimeCommitOutcome>
  /** Reset all staged overrides without contacting backend. */
  discardDraft(): void
}


export interface RuntimeCommitOutcome {
  succeeded: number
  failed: number
  /** Per-override-key outcome marker for the editor to surface
   *  granular results (`{token::accent::value: 'ok'}`). */
  results: Record<string, "ok" | "error">
  errors: Array<{ key: string; reason: string }>
}


export type EditModeContextValue = EditModeState & EditModeActions


// ─── Override commit router (R-0 stub) ──────────────────────────


/** Per-type writer. Receives the dual-token helpers and the staged
 *  override; performs the appropriate platform-token write. R-0
 *  ships the contract; R-1+ phases register actual writers per type.
 *  Until then the stub writers no-op locally — the test consumer
 *  asserts the routing contract reaches the right writer. */
export type OverrideWriter = (
  helpers: DualTokenHelpers,
  override: RuntimeOverride,
) => Promise<void>


export type OverrideWriterRegistry = Partial<Record<RuntimeOverrideType, OverrideWriter>>


/** R-0 default registry: each writer no-ops. R-1+ replaces each
 *  type's writer with the real platform-token write. The provider
 *  accepts an override registry prop so tests can substitute a
 *  doubles-only registry without going through localStorage / network. */
const DEFAULT_WRITERS: Required<OverrideWriterRegistry> = {
  async token() {
    /* R-0 stub: theme writer wires to platform_themes_service in R-1. */
  },
  async component_prop() {
    /* R-0 stub: per-component override writer wires in R-1. */
  },
  async component_class() {
    /* R-0 stub: class override writer wires in R-1. */
  },
  async dashboard_layout() {
    /* R-0 stub: dashboard layout writer is wired in this phase via
     * the Widget Editor's "Dashboard Layouts" tab — but the tab
     * speaks the platform endpoint directly through its own service.
     * The runtime-editor commit path lights up in R-1 when the tab
     * folds into the runtime editor proper. */
  },
}


// ─── Stub for callers outside a provider ────────────────────────


function makeStub(): EditModeContextValue {
  return {
    tenantSlug: null,
    impersonatedUserId: null,
    isEditing: false,
    pageContext: null,
    selectedComponentName: null,
    draftOverrides: new Map<string, RuntimeOverride>(),
    isCommitting: false,
    commitError: null,
    setEditing: () => {
      /* stub — useEditMode outside provider must not crash */
    },
    setPageContext: () => {
      /* stub */
    },
    selectComponent: () => {
      /* stub */
    },
    stageOverride: () => {
      /* stub */
    },
    clearStaged: () => {
      /* stub */
    },
    commitDraft: () =>
      Promise.resolve({
        succeeded: 0,
        failed: 0,
        results: {},
        errors: [],
      }),
    discardDraft: () => {
      /* stub */
    },
  }
}


const _STUB = makeStub()


// ─── Context + provider ─────────────────────────────────────────


const EditModeContext = createContext<EditModeContextValue | null>(null)


export interface EditModeProviderProps {
  /** Tenant slug being rendered. */
  tenantSlug: string
  /** User the impersonation token represents. */
  impersonatedUserId: string
  /** Initial edit-mode state. Default: 'view'. */
  initialMode?: "view" | "edit"
  /** Initial page_context. Components can call setPageContext later. */
  initialPageContext?: string | null
  /** Override the per-type writer registry (test-injectable). */
  writers?: OverrideWriterRegistry
  children: ReactNode
}


export function EditModeProvider({
  tenantSlug,
  impersonatedUserId,
  initialMode = "view",
  initialPageContext = null,
  writers,
  children,
}: EditModeProviderProps) {
  const helpers = useRuntimeHostClient()
  const [isEditing, setIsEditing] = useState(initialMode === "edit")
  const [pageContext, setPageContextState] = useState<string | null>(
    initialPageContext,
  )
  const [selectedComponentName, setSelectedComponentName] = useState<
    string | null
  >(null)
  const [draftOverrides, setDraftOverrides] = useState<
    Map<string, RuntimeOverride>
  >(() => new Map())
  const [isCommitting, setIsCommitting] = useState(false)
  const [commitError, setCommitError] = useState<string | null>(null)

  const writerRegistry = useMemo<Required<OverrideWriterRegistry>>(
    () => ({
      ...DEFAULT_WRITERS,
      ...(writers ?? {}),
    }),
    [writers],
  )

  const setEditing = useCallback((next: boolean) => {
    setIsEditing(next)
    if (!next) {
      // Leaving edit mode clears the per-element selection so the next
      // edit-mode entry starts clean.
      setSelectedComponentName(null)
    }
  }, [])

  const setPageContext = useCallback((next: string | null) => {
    setPageContextState(next)
  }, [])

  const selectComponent = useCallback((name: string | null) => {
    setSelectedComponentName(name)
  }, [])

  const stageOverride = useCallback((o: RuntimeOverride) => {
    setDraftOverrides((prev) => {
      const next = new Map(prev)
      next.set(overrideKey(o), o)
      return next
    })
  }, [])

  const clearStaged = useCallback(
    (type: RuntimeOverrideType, target: string) => {
      setDraftOverrides((prev) => {
        const next = new Map(prev)
        for (const k of Array.from(next.keys())) {
          if (k.startsWith(`${type}::${target}::`)) {
            next.delete(k)
          }
        }
        return next
      })
    },
    [],
  )

  const discardDraft = useCallback(() => {
    setDraftOverrides(new Map())
    setCommitError(null)
  }, [])

  const commitDraft = useCallback(async () => {
    setIsCommitting(true)
    setCommitError(null)
    const results: Record<string, "ok" | "error"> = {}
    const errors: Array<{ key: string; reason: string }> = []
    let succeeded = 0
    let failed = 0

    for (const [key, override] of draftOverrides.entries()) {
      const writer = writerRegistry[override.type]
      try {
        await writer(helpers, override)
        results[key] = "ok"
        succeeded += 1
      } catch (err) {
        const reason =
          err instanceof Error ? err.message : "unknown error"
        results[key] = "error"
        errors.push({ key, reason })
        failed += 1
      }
    }

    if (failed > 0) {
      setCommitError(
        `${failed} override${failed === 1 ? "" : "s"} failed to commit`,
      )
    } else {
      // All succeeded — clear staged.
      setDraftOverrides(new Map())
    }
    setIsCommitting(false)

    return { succeeded, failed, results, errors }
  }, [draftOverrides, helpers, writerRegistry])

  const value = useMemo<EditModeContextValue>(
    () => ({
      tenantSlug,
      impersonatedUserId,
      isEditing,
      pageContext,
      selectedComponentName,
      draftOverrides,
      isCommitting,
      commitError,
      setEditing,
      setPageContext,
      selectComponent,
      stageOverride,
      clearStaged,
      commitDraft,
      discardDraft,
    }),
    [
      tenantSlug,
      impersonatedUserId,
      isEditing,
      pageContext,
      selectedComponentName,
      draftOverrides,
      isCommitting,
      commitError,
      setEditing,
      setPageContext,
      selectComponent,
      stageOverride,
      clearStaged,
      commitDraft,
      discardDraft,
    ],
  )

  return (
    <EditModeContext.Provider value={value}>
      {children}
    </EditModeContext.Provider>
  )
}


/** Returns the active EditModeContextValue, or a no-op stub when
 *  called outside a provider. The stub matches the existing widget
 *  `_editMode` convention — components opt into edit-awareness
 *  without crashing in non-editor contexts. */
export function useEditMode(): EditModeContextValue {
  const ctx = useContext(EditModeContext)
  return ctx ?? _STUB
}


// Internals exposed for unit tests; not part of the public API.
export const __edit_mode_internals = {
  DEFAULT_WRITERS,
  makeStub,
  overrideKey,
}
