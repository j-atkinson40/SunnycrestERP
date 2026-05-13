/**
 * Arc 3a — Inspector Focus compositions tab.
 *
 * 3-level mode-stack with selection-driven Level 3 content
 * (Q-FOCUS-2 canon): list → composition-edit → detail. Tab owns its
 * own state per Phase 2b B-ARC2B-1 (tab-level mode-stack canon —
 * each new tab owns its own stack; consistency through convention,
 * not shared abstraction).
 *
 * ── Architectural patterns locked (Arc 3a) ──
 *
 * - **Read-mostly canvas embed with bidirectional deep-link**
 *   (Q-FOCUS-1). InteractivePlacementCanvas at 380px renders with
 *   `interactionsEnabled={false}`. Click-to-select preserved
 *   (canvas Q-CROSS-2 refinement); drag / resize / row-reorder /
 *   marquee disabled. The "Open in full editor →" deep-link builds
 *   a URL carrying `composition_id` + `return_to` URL param;
 *   standalone reads `return_to` and renders a "Back to runtime
 *   editor" affordance preserving inspector state on return.
 *   NO modal-overlay from inspector. NO in-inspector drag-drop.
 *
 * - **Selection-driven detail level pattern** (Q-FOCUS-2). Level 3
 *   branches on `SelectionUnion.kind`: row → row-config,
 *   placement → placement-config, multi → bulk-operations.
 *   Compounds forward to Arc 4 page chrome + future multi-entity
 *   surfaces.
 *
 * - **Per-tab scope pill canon refined** (Q-FOCUS-3). Scope depth
 *   is substrate-determined. Workflows = two-scope (workflow_
 *   templates table); Documents = three-scope; Focus compositions
 *   = three-scope (focus_compositions table; PLUGIN_CONTRACTS §2).
 *
 * - **One-tab-per-concern canon** (Q-FOCUS-5). Operating since
 *   Phase 2b; explicit at Arc 3a. Each inspector tab handles one
 *   substrate concern. Composition is here; per-template
 *   configurable props remain Props tab domain (focus-template
 *   ComponentKind already surfaces in Props tab kinds list).
 *
 * - **Form-local + 1.5s autosave canon** (Phase 2b B-ARC2B-2).
 *   Workflows tab canonicalized 1.5s; Focus compositions tab
 *   aligns to the same cadence (minor unification — standalone
 *   editor's 2s autosave is a divergence flagged for future
 *   harmonization; not in scope here). Atomic-per-composition
 *   service contract via `focusCompositionsService.update` PATCH
 *   replacing whole rows + canvas_config.
 *
 * - **Hybrid filter fallback to category chip** (Q-FOCUS-4 —
 *   c-expensive cost branch). `focus-template → page_context`
 *   mapping does not exist today; per settled spec, ship fallback
 *   matching Arc 3b precedent: all-templates default with focus
 *   type category chip filter.
 *
 * - **Parity-not-exceedance** (Q-UX-3 canon). Inspector matches
 *   standalone at 380px. Full canvas drag-drop authoring stays
 *   in standalone; inspector provides read-mostly preview + add
 *   row + delete row + reorder via buttons + dropdown picker +
 *   selection-driven detail editing. Future standalone improvements
 *   propagate via component reuse (InteractivePlacementCanvas
 *   shared module).
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type JSX,
} from "react"
import { Link } from "react-router-dom"
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight as ArrowRightIcon,
  ArrowUp,
  ChevronDown,
  ExternalLink,
  Loader2,
  Plus,
  Trash2,
} from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import {
  InteractivePlacementCanvas,
  type Selection,
} from "@/bridgeable-admin/components/visual-editor/composition-canvas/InteractivePlacementCanvas"
import { ColumnCountPopover } from "@/bridgeable-admin/components/visual-editor/composition-canvas/ColumnCountPopover"
import { focusCompositionsService } from "@/bridgeable-admin/services/focus-compositions-service"
import {
  getByName,
  getCanvasPlaceableComponents,
  type ComponentKind,
  type RegistryEntry,
} from "@/lib/visual-editor/registry"
import type {
  CompositionRecord,
  CompositionRow,
  Placement,
} from "@/lib/visual-editor/compositions/types"
// Arc 4d — chip-variant SourceBadge for per-composition scope tier
// display. Replaces inline `<Badge variant="outline">{source}</Badge>`
// (3-way pattern drift closure: ThemeTab inline + FocusCompositions
// inline + canonical → single canonical primitive).
import {
  SourceBadge,
  type SourceValue,
} from "@/lib/visual-editor/source-badge"


/**
 * Arc 4d — map focus_compositions resolver source string
 * (`tenant_override` | `vertical_default` | `platform_default`) to
 * canonical SourceValue.
 */
function compositionSourceToSource(source: string): SourceValue {
  switch (source) {
    case "tenant_override":
      return "tenant"
    case "vertical_default":
      return "vertical"
    case "platform_default":
      return "platform"
    default:
      return "default"
  }
}


export const FOCUS_COMPOSITIONS_AUTOSAVE_DEBOUNCE_MS = 1500


/** Mode-stack levels for the Focus compositions tab.
 *  Generic stack pattern matches Phase 2b WorkflowsTab + Arc 3b
 *  DocumentsTab verbatim. Tab owns its own state. */
export type ModeStackLevel =
  | { kind: "list" }
  | { kind: "composition-edit"; compositionFocusType: string }
  | {
      kind: "detail"
      compositionFocusType: string
      selection: SelectionUnion
    }


/** Discriminated selection union for Level 3 detail dispatch
 *  (Q-FOCUS-2). Compounds forward to Arc 4 + future multi-entity
 *  surfaces. */
export type SelectionUnion =
  | { kind: "row"; rowId: string }
  | { kind: "placement"; placementId: string }
  | { kind: "multi"; placementIds: readonly string[] }


/** Scope filter for the templates list. Three-scope per
 *  PLUGIN_CONTRACTS §2 + composition_service.py cascade. */
type Scope = "platform_default" | "vertical_default" | "tenant_override"


export interface FocusCompositionsTabProps {
  /** Impersonated tenant's vertical — drives scope-pill `vertical_default`
   *  resolution. Wired by RuntimeEditorShell from the impersonation
   *  context. */
  vertical: string | null
  /** Impersonated tenant id — drives scope-pill `tenant_override`
   *  resolution. */
  tenantId?: string | null
}


type SavingState = "idle" | "saving" | "saved" | "error"


function defaultCanvasConfig(): CompositionRecord["canvas_config"] {
  return {
    gap_size: 12,
    background_treatment: "surface-base",
  }
}


function newRowId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID()
  }
  return `row-${Math.random().toString(36).slice(2, 10)}-${Date.now()}`
}


function nextPlacementId(rows: readonly CompositionRow[]): string {
  const existing = new Set(
    rows.flatMap((r) => r.placements.map((p) => p.placement_id)),
  )
  let i = rows.flatMap((r) => r.placements).length + 1
  while (existing.has(`p${i}`)) i += 1
  return `p${i}`
}


function findAvailableStartingColumn(
  row: CompositionRow,
  width: number,
): number {
  // Greedy left-to-right; returns 0 if no slot fits (caller handles).
  const occupied = new Set<number>()
  for (const p of row.placements) {
    for (let i = 0; i < p.column_span; i += 1) {
      occupied.add(p.starting_column + i)
    }
  }
  for (let start = 0; start + width <= row.column_count; start += 1) {
    let fits = true
    for (let i = 0; i < width; i += 1) {
      if (occupied.has(start + i)) {
        fits = false
        break
      }
    }
    if (fits) return start
  }
  return 0
}


function buildEditorUrl(
  compositionFocusType: string | null,
  compositionId: string | null,
  returnTo: string,
): string {
  // Studio 1a-i.A1 (May 2026): when the runtime editor is mounted
  // inside Studio (at /studio/live/...) — currently a placeholder in
  // A1 — construct a Studio deep link. Outside Studio (standalone
  // /runtime-editor/...) keep the existing /visual-editor/* URL so
  // the standalone editor mount remains addressable. The redirect
  // layer catches the legacy URL either way.
  const inStudio =
    typeof window !== "undefined" &&
    window.location.pathname
      .replace(/^\/bridgeable-admin/, "")
      .startsWith("/studio/")
  const base = inStudio
    ? adminPath("/studio/focuses")
    : adminPath("/visual-editor/focuses")
  const params = new URLSearchParams()
  if (compositionFocusType) {
    params.set(inStudio ? "category" : "focus_type", compositionFocusType)
  }
  if (compositionId) params.set("composition_id", compositionId)
  params.set("return_to", returnTo)
  return `${base}?${params.toString()}`
}


/** Browse the focus-template registry for templates that declare
 *  `extensions.compositionFocusType`. Returns the unique set of
 *  composition_focus_type values + their display labels (sourced from
 *  the registering template). Templates without compositionFocusType
 *  (e.g., generation-only focuses) don't surface here per Q-FOCUS-5
 *  (composition-only tab; per-template props live in Props tab). */
interface CompositionTemplateOption {
  composition_focus_type: string
  display_label: string
  focus_type_category: string // "decision" | "coordination" | etc.
}


function listCompositionTemplates(): CompositionTemplateOption[] {
  const entries: CompositionTemplateOption[] = []
  const seen = new Set<string>()
  const kinds: ComponentKind[] = ["focus-template"]
  for (const kind of kinds) {
    // Iterate via getByName for known names by scanning the registry
    // surface. The registry exposes getAllRegistered via barrel; here
    // we use a defensive approach — scan known focus-template names.
    // The actual list is small (3 today: triage-decision, arrangement-
    // scribe, funeral-scheduling).
    for (const candidate of FOCUS_TEMPLATE_CANDIDATES) {
      const entry: RegistryEntry | null = getByName(kind, candidate) ?? null
      if (!entry) continue
      const ext = entry.metadata.extensions as
        | { compositionFocusType?: string; focusType?: string }
        | undefined
      const cft = ext?.compositionFocusType
      if (!cft || seen.has(cft)) continue
      seen.add(cft)
      entries.push({
        composition_focus_type: cft,
        display_label: entry.metadata.displayName ?? entry.metadata.name,
        focus_type_category: ext?.focusType ?? "decision",
      })
    }
  }
  return entries
}


// Known focus-template names. Add new ones here as they register.
// Drives the list shown in the tab; per Q-FOCUS-4 c-expensive
// cost branch, we ship category chip filter rather than a route-
// derived hybrid filter (would require focus-template → page_context
// substrate evolution).
const FOCUS_TEMPLATE_CANDIDATES = [
  "triage-decision",
  "arrangement-scribe",
  "funeral-scheduling",
] as const


const FOCUS_TYPE_CATEGORIES = [
  "decision",
  "coordination",
  "execution",
  "review",
  "generation",
] as const
type FocusTypeCategory = (typeof FOCUS_TYPE_CATEGORIES)[number]


export function FocusCompositionsTab({
  vertical,
  tenantId,
}: FocusCompositionsTabProps): JSX.Element {
  // ── Mode-stack state (B-ARC2B-1: tab-level, not inspector-level) ──
  const [modeStack, setModeStack] = useState<ModeStackLevel[]>([
    { kind: "list" },
  ])
  const currentLevel = modeStack[modeStack.length - 1]

  const push = useCallback((level: ModeStackLevel) => {
    setModeStack((prev) => [...prev, level])
  }, [])

  const pop = useCallback(() => {
    setModeStack((prev) => (prev.length > 1 ? prev.slice(0, -1) : prev))
  }, [])

  if (currentLevel.kind === "list") {
    return (
      <ListView
        vertical={vertical}
        tenantId={tenantId ?? null}
        onSelectComposition={(compositionFocusType) =>
          push({ kind: "composition-edit", compositionFocusType })
        }
      />
    )
  }

  if (currentLevel.kind === "composition-edit") {
    return (
      <CompositionEditView
        compositionFocusType={currentLevel.compositionFocusType}
        vertical={vertical}
        tenantId={tenantId ?? null}
        onBack={pop}
        onSelectDetail={(selection) =>
          push({
            kind: "detail",
            compositionFocusType: currentLevel.compositionFocusType,
            selection,
          })
        }
      />
    )
  }

  // detail
  return (
    <DetailView
      compositionFocusType={currentLevel.compositionFocusType}
      selection={currentLevel.selection}
      vertical={vertical}
      tenantId={tenantId ?? null}
      onBack={pop}
    />
  )
}


// ─────────────────────────────────────────────────────────────────
// Level 1 — Composition template list
// ─────────────────────────────────────────────────────────────────


function ListView({
  vertical,
  tenantId,
  onSelectComposition,
}: {
  vertical: string | null
  tenantId: string | null
  onSelectComposition: (compositionFocusType: string) => void
}) {
  // Per-tab scope pill (Q-FOCUS-3 + B-ARC2-5: each tab owns its
  // scope state; three-scope per PLUGIN_CONTRACTS §2).
  const [scope, setScope] = useState<Scope>("vertical_default")
  const [scopePillOpen, setScopePillOpen] = useState(false)

  // Q-FOCUS-4: category chip filter (c-expensive fallback). "all" =
  // show every template; per-category filter chips narrow by focus
  // type (decision/coordination/execution/review/generation).
  const [categoryFilter, setCategoryFilter] = useState<
    "all" | FocusTypeCategory
  >("all")

  const allTemplates = useMemo(() => listCompositionTemplates(), [])
  const visibleTemplates = useMemo(() => {
    if (categoryFilter === "all") return allTemplates
    return allTemplates.filter(
      (t) => t.focus_type_category === categoryFilter,
    )
  }, [allTemplates, categoryFilter])

  // Resolve compositions for visible templates against the active
  // scope. Per-template fetch — small N (3 today) keeps this simple;
  // future N>10 could batch, but YAGNI.
  const [resolveResults, setResolveResults] = useState<
    Record<string, { source: string | null; compositionId: string | null }>
  >({})
  const [isResolving, setIsResolving] = useState(false)

  useEffect(() => {
    let cancelled = false
    setIsResolving(true)
    Promise.all(
      visibleTemplates.map(async (t) => {
        try {
          const resolved = await focusCompositionsService.resolve({
            focus_type: t.composition_focus_type,
            vertical: scope === "vertical_default" ? vertical : null,
            tenant_id: scope === "tenant_override" ? tenantId : null,
          })
          return [
            t.composition_focus_type,
            {
              source: resolved.source,
              compositionId: resolved.source_id,
            },
          ] as const
        } catch (err) {
          // eslint-disable-next-line no-console
          console.warn("[runtime-editor] focus composition resolve failed", err)
          return [
            t.composition_focus_type,
            { source: null, compositionId: null },
          ] as const
        }
      }),
    ).then((pairs) => {
      if (cancelled) return
      const next: Record<
        string,
        { source: string | null; compositionId: string | null }
      > = {}
      for (const [key, val] of pairs) next[key] = val
      setResolveResults(next)
      setIsResolving(false)
    })
    return () => {
      cancelled = true
    }
  }, [visibleTemplates, scope, vertical, tenantId])

  const returnToUrl =
    typeof window !== "undefined"
      ? window.location.pathname + window.location.search
      : "/"

  return (
    <div
      className="flex flex-col gap-2 px-3 py-3"
      data-testid="runtime-inspector-focus-list"
    >
      {/* Header: title + scope pill */}
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-body-sm font-medium text-content-strong">
          Focus compositions
        </h2>
        <ScopePill
          scope={scope}
          onChange={setScope}
          open={scopePillOpen}
          onOpenChange={setScopePillOpen}
          hasTenant={!!tenantId}
          hasVertical={!!vertical}
        />
      </div>

      {/* Category chip filter (Q-FOCUS-4 c-expensive fallback). */}
      <div
        className="flex flex-wrap gap-1"
        data-testid="runtime-inspector-focus-category-chips"
      >
        <CategoryChip
          label="All"
          value="all"
          active={categoryFilter === "all"}
          onClick={() => setCategoryFilter("all")}
        />
        {FOCUS_TYPE_CATEGORIES.map((cat) => (
          <CategoryChip
            key={cat}
            label={cat.charAt(0).toUpperCase() + cat.slice(1)}
            value={cat}
            active={categoryFilter === cat}
            onClick={() => setCategoryFilter(cat)}
          />
        ))}
      </div>

      {/* Template list */}
      {isResolving && (
        <div className="flex items-center gap-2 text-caption text-content-muted">
          <Loader2 size={14} className="animate-spin" /> Resolving compositions…
        </div>
      )}
      {!isResolving && visibleTemplates.length === 0 && (
        <div
          className="rounded-sm border border-border-subtle bg-surface-sunken px-3 py-3 text-caption text-content-muted"
          data-testid="runtime-inspector-focus-empty"
        >
          {categoryFilter === "all"
            ? "No focus-template registrations carry compositionFocusType. The composition tab surfaces templates that declare a composition_focus_type extension key."
            : `No ${categoryFilter} focus templates registered. Try a different category, or "All" to see every template.`}
        </div>
      )}
      <ul className="flex flex-col gap-1">
        {visibleTemplates.map((t) => {
          const result = resolveResults[t.composition_focus_type]
          const compositionId = result?.compositionId ?? null
          const source = result?.source ?? null
          const editorUrl = buildEditorUrl(
            t.composition_focus_type,
            compositionId,
            returnToUrl,
          )
          return (
            <li
              key={t.composition_focus_type}
              data-testid={`runtime-inspector-focus-row-${t.composition_focus_type}`}
              className="flex items-center justify-between gap-2 rounded-sm border border-border-subtle bg-surface-elevated px-2 py-2 hover:border-accent/40"
            >
              <button
                type="button"
                onClick={() =>
                  onSelectComposition(t.composition_focus_type)
                }
                className="flex-1 text-left"
                data-testid={`runtime-inspector-focus-row-edit-${t.composition_focus_type}`}
              >
                <div className="text-body-sm font-medium text-content-strong">
                  {t.display_label}
                </div>
                <div className="flex items-center gap-1 text-caption text-content-muted">
                  <code className="font-plex-mono text-micro">
                    {t.composition_focus_type}
                  </code>
                  <Badge variant="outline" className="text-micro">
                    {t.focus_type_category}
                  </Badge>
                  {/* Arc 4d — canonical chip-variant SourceBadge.
                      Replaces inline `<Badge>{source}</Badge>`. */}
                  {source && (
                    <SourceBadge
                      source={compositionSourceToSource(source)}
                      variant="chip"
                      data-testid={`runtime-inspector-focus-row-${t.composition_focus_type}-scope`}
                    />
                  )}
                </div>
              </button>
              <Link
                to={editorUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-sm p-1 text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong"
                aria-label="Open in full editor"
                data-testid={`runtime-inspector-focus-deeplink-${t.composition_focus_type}`}
              >
                <ExternalLink size={14} />
              </Link>
            </li>
          )
        })}
      </ul>
    </div>
  )
}


function CategoryChip({
  label,
  value,
  active,
  onClick,
}: {
  label: string
  value: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-2 py-0.5 text-micro transition-colors ${
        active
          ? "border-accent bg-accent-subtle text-content-strong"
          : "border-border-subtle bg-surface-elevated text-content-muted hover:border-border-base"
      }`}
      data-testid={`runtime-inspector-focus-chip-${value}`}
      data-active={active ? "true" : "false"}
    >
      {label}
    </button>
  )
}


function ScopePill({
  scope,
  onChange,
  open,
  onOpenChange,
  hasTenant,
  hasVertical,
}: {
  scope: Scope
  onChange: (next: Scope) => void
  open: boolean
  onOpenChange: (next: boolean) => void
  hasTenant: boolean
  hasVertical: boolean
}) {
  const label =
    scope === "platform_default"
      ? "Platform"
      : scope === "vertical_default"
        ? "Vertical"
        : "Tenant"
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => onOpenChange(!open)}
        className="flex items-center gap-1 rounded-sm border border-border-subtle bg-surface-elevated px-2 py-0.5 text-micro text-content-muted hover:border-border-base"
        data-testid="runtime-inspector-focus-scope-pill"
        data-scope={scope}
      >
        {label}
        <ChevronDown size={10} />
      </button>
      {open && (
        <div
          className="absolute right-0 top-full mt-1 flex w-40 flex-col rounded-sm border border-border-subtle bg-surface-raised shadow-level-2"
          data-testid="runtime-inspector-focus-scope-menu"
        >
          {(["platform_default", "vertical_default", "tenant_override"] as const).map(
            (s) => {
              const disabled =
                (s === "vertical_default" && !hasVertical) ||
                (s === "tenant_override" && !hasTenant)
              return (
                <button
                  key={s}
                  type="button"
                  disabled={disabled}
                  onClick={() => {
                    if (disabled) return
                    onChange(s)
                    onOpenChange(false)
                  }}
                  className={`px-2 py-1 text-left text-caption hover:bg-accent-subtle/40 disabled:opacity-50 ${
                    scope === s ? "text-content-strong font-medium" : "text-content-muted"
                  }`}
                  data-testid={`runtime-inspector-focus-scope-${s}`}
                >
                  {s === "platform_default" && "Platform default"}
                  {s === "vertical_default" && "Vertical default"}
                  {s === "tenant_override" && "Tenant override"}
                </button>
              )
            },
          )}
        </div>
      )}
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────
// Level 2 — Composition edit (read-mostly canvas + affordances)
// ─────────────────────────────────────────────────────────────────


/** Form-local draft + 1.5s autosave hook for a composition.
 *  Atomic-per-composition: PATCH replaces whole rows + canvas_config.
 *  Mirrors WorkflowsTab's useWorkflowDraft shape; Phase 2b
 *  form-local-autosave canon. */
function useCompositionDraft(params: {
  compositionFocusType: string
  scope: Scope
  vertical: string | null
  tenantId: string | null
}) {
  const { compositionFocusType, scope, vertical, tenantId } = params
  const [activeRow, setActiveRow] = useState<CompositionRecord | null>(null)
  const [draftRows, setDraftRows] = useState<CompositionRow[]>([])
  const [draftCanvasConfig, setDraftCanvasConfig] = useState<
    CompositionRecord["canvas_config"]
  >(defaultCanvasConfig())
  const [lastSavedRows, setLastSavedRows] = useState<CompositionRow[]>([])
  const [lastSavedCanvasConfig, setLastSavedCanvasConfig] = useState<
    CompositionRecord["canvas_config"]
  >(defaultCanvasConfig())
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [savingState, setSavingState] = useState<SavingState>("idle")
  const autosaveTimerRef = useRef<number | null>(null)

  // Load via resolve → list (first row matching scope/focus_type).
  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setLoadError(null)
    focusCompositionsService
      .resolve({
        focus_type: compositionFocusType,
        vertical: scope === "vertical_default" ? vertical : null,
        tenant_id: scope === "tenant_override" ? tenantId : null,
      })
      .then(async (resolved) => {
        if (cancelled) return
        // If resolve returned a source (matching scope), fetch full
        // record for editing. Otherwise empty draft.
        if (resolved.source_id) {
          try {
            const full = await focusCompositionsService.get(resolved.source_id)
            if (cancelled) return
            // Only adopt the resolved record if it's at the SAME scope
            // the operator selected — resolve may have walked the chain
            // and returned a parent-scope record.
            if (full.scope === scope) {
              setActiveRow(full)
              setDraftRows(full.rows)
              setDraftCanvasConfig(full.canvas_config)
              setLastSavedRows(full.rows)
              setLastSavedCanvasConfig(full.canvas_config)
            } else {
              // Adopt as starting draft but no active row at this scope
              // yet — saving creates a new record.
              setActiveRow(null)
              setDraftRows(full.rows)
              setDraftCanvasConfig(full.canvas_config)
              setLastSavedRows([])
              setLastSavedCanvasConfig(defaultCanvasConfig())
            }
          } catch (err) {
            // eslint-disable-next-line no-console
            console.warn("[runtime-editor] composition get failed", err)
            setActiveRow(null)
            setDraftRows(resolved.rows)
            setDraftCanvasConfig(resolved.canvas_config)
            setLastSavedRows([])
            setLastSavedCanvasConfig(defaultCanvasConfig())
          }
        } else {
          setActiveRow(null)
          setDraftRows([])
          setDraftCanvasConfig(defaultCanvasConfig())
          setLastSavedRows([])
          setLastSavedCanvasConfig(defaultCanvasConfig())
        }
      })
      .catch((err) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.warn("[runtime-editor] composition resolve failed", err)
        setLoadError(
          err instanceof Error ? err.message : "Failed to load composition",
        )
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [compositionFocusType, scope, vertical, tenantId])

  const isDirty = useMemo(() => {
    return (
      JSON.stringify([lastSavedRows, lastSavedCanvasConfig]) !==
      JSON.stringify([draftRows, draftCanvasConfig])
    )
  }, [draftRows, draftCanvasConfig, lastSavedRows, lastSavedCanvasConfig])

  const performSave = useCallback(async () => {
    setSavingState("saving")
    try {
      if (activeRow) {
        const updated = await focusCompositionsService.update(activeRow.id, {
          rows: draftRows,
          canvas_config: draftCanvasConfig,
        })
        setActiveRow(updated)
        setLastSavedRows(updated.rows)
        setLastSavedCanvasConfig(updated.canvas_config)
      } else {
        const created = await focusCompositionsService.create({
          scope,
          focus_type: compositionFocusType,
          vertical: scope === "vertical_default" ? vertical : null,
          tenant_id: scope === "tenant_override" ? tenantId : null,
          rows: draftRows,
          canvas_config: draftCanvasConfig,
        })
        setActiveRow(created)
        setLastSavedRows(created.rows)
        setLastSavedCanvasConfig(created.canvas_config)
      }
      setSavingState("saved")
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[runtime-editor] composition save failed", err)
      setSavingState("error")
      toast.error("Failed to save composition", {
        action: {
          label: "Retry",
          onClick: () => {
            void performSave()
          },
        },
      })
    }
  }, [
    activeRow,
    draftRows,
    draftCanvasConfig,
    scope,
    compositionFocusType,
    vertical,
    tenantId,
  ])

  // Autosave debounce — 1.5s after last mutation (Phase 2b canon).
  useEffect(() => {
    if (!isDirty) return
    if (autosaveTimerRef.current !== null) {
      window.clearTimeout(autosaveTimerRef.current)
    }
    autosaveTimerRef.current = window.setTimeout(() => {
      void performSave()
    }, FOCUS_COMPOSITIONS_AUTOSAVE_DEBOUNCE_MS)
    return () => {
      if (autosaveTimerRef.current !== null) {
        window.clearTimeout(autosaveTimerRef.current)
        autosaveTimerRef.current = null
      }
    }
  }, [draftRows, draftCanvasConfig, isDirty, performSave])

  const flushPendingSave = useCallback(async () => {
    if (autosaveTimerRef.current !== null) {
      window.clearTimeout(autosaveTimerRef.current)
      autosaveTimerRef.current = null
    }
    if (isDirty) {
      await performSave()
    }
  }, [isDirty, performSave])

  const discardDraft = useCallback(() => {
    setDraftRows(lastSavedRows)
    setDraftCanvasConfig(lastSavedCanvasConfig)
    setSavingState("idle")
  }, [lastSavedRows, lastSavedCanvasConfig])

  return {
    activeRow,
    draftRows,
    setDraftRows,
    draftCanvasConfig,
    setDraftCanvasConfig,
    isLoading,
    loadError,
    isDirty,
    savingState,
    flushPendingSave,
    discardDraft,
  }
}


type GuardAction = "save" | "discard" | null


function CompositionEditView({
  compositionFocusType,
  vertical,
  tenantId,
  onBack,
  onSelectDetail,
}: {
  compositionFocusType: string
  vertical: string | null
  tenantId: string | null
  onBack: () => void
  onSelectDetail: (selection: SelectionUnion) => void
}) {
  // Scope is fixed at vertical_default for the editing surface (Q-FOCUS-3
  // canon — operator picks scope at list level; editing happens in that
  // scope). Reading the scope from list-view state would require lifting;
  // for parity with Workflows we keep edit-view scope fixed at the
  // tenant-impersonation default (vertical_default).
  const scope: Scope = "vertical_default"
  const draft = useCompositionDraft({
    compositionFocusType,
    scope,
    vertical,
    tenantId,
  })

  const [selection, setSelection] = useState<Selection>({ kind: "none" })
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [guardOpen, setGuardOpen] = useState(false)
  const [guardAction, setGuardAction] = useState<GuardAction>(null)

  const palette = useMemo(() => getCanvasPlaceableComponents(), [])

  const handleSelectPlacement = useCallback(
    (placementId: string, opts: { shift: boolean }) => {
      setSelection((prev) => {
        if (opts.shift && prev.kind === "placement" && prev.placementIds) {
          const next = new Set(prev.placementIds)
          next.add(placementId)
          return { kind: "placements-multi", placementIds: next }
        }
        if (opts.shift && prev.kind === "placements-multi" && prev.placementIds) {
          const next = new Set(prev.placementIds)
          next.add(placementId)
          return { kind: "placements-multi", placementIds: next }
        }
        return {
          kind: "placement",
          placementIds: new Set([placementId]),
        }
      })
    },
    [],
  )

  const handleSelectRow = useCallback((rowId: string) => {
    setSelection({ kind: "row", rowId })
  }, [])

  const handleDeselectAll = useCallback(() => {
    setSelection({ kind: "none" })
  }, [])

  const handleOpenDetailFromSelection = useCallback(() => {
    if (selection.kind === "row" && selection.rowId) {
      onSelectDetail({ kind: "row", rowId: selection.rowId })
      return
    }
    if (selection.kind === "placement" && selection.placementIds) {
      const ids = Array.from(selection.placementIds)
      if (ids.length === 1) {
        onSelectDetail({ kind: "placement", placementId: ids[0] })
        return
      }
      if (ids.length > 1) {
        onSelectDetail({ kind: "multi", placementIds: ids })
        return
      }
    }
    if (selection.kind === "placements-multi" && selection.placementIds) {
      onSelectDetail({
        kind: "multi",
        placementIds: Array.from(selection.placementIds),
      })
    }
  }, [selection, onSelectDetail])

  const handleAddRow = useCallback(() => {
    draft.setDraftRows((cur) => [
      ...cur,
      {
        row_id: newRowId(),
        column_count: 12,
        row_height: "auto",
        column_widths: null,
        nested_rows: null,
        placements: [],
      },
    ])
  }, [draft])

  const handleDeleteRow = useCallback(
    (rowId: string) => {
      draft.setDraftRows((cur) => cur.filter((r) => r.row_id !== rowId))
      setSelection({ kind: "none" })
    },
    [draft],
  )

  const handleAddRowAbove = useCallback(
    (rowIndex: number) => {
      draft.setDraftRows((cur) => {
        const next = [...cur]
        next.splice(rowIndex, 0, {
          row_id: newRowId(),
          column_count: 12,
          row_height: "auto",
          column_widths: null,
          nested_rows: null,
          placements: [],
        })
        return next
      })
    },
    [draft],
  )

  const handleAddRowBelow = useCallback(
    (rowIndex: number) => {
      draft.setDraftRows((cur) => {
        const next = [...cur]
        next.splice(rowIndex + 1, 0, {
          row_id: newRowId(),
          column_count: 12,
          row_height: "auto",
          column_widths: null,
          nested_rows: null,
          placements: [],
        })
        return next
      })
    },
    [draft],
  )

  const handleChangeRowColumnCount = useCallback(
    (rowId: string, newColumnCount: number) => {
      draft.setDraftRows((cur) =>
        cur.map((r) =>
          r.row_id === rowId ? { ...r, column_count: newColumnCount } : r,
        ),
      )
    },
    [draft],
  )

  const handleReorderRow = useCallback(
    (rowId: string, direction: "up" | "down") => {
      draft.setDraftRows((cur) => {
        const idx = cur.findIndex((r) => r.row_id === rowId)
        if (idx < 0) return cur
        const swap = direction === "up" ? idx - 1 : idx + 1
        if (swap < 0 || swap >= cur.length) return cur
        const next = [...cur]
        ;[next[idx], next[swap]] = [next[swap], next[idx]]
        return next
      })
    },
    [draft],
  )

  const handleAddPlacement = useCallback(
    (componentName: string, componentKind: ComponentKind) => {
      // Add to selected row OR last row OR new row.
      draft.setDraftRows((cur) => {
        let targetRowIndex =
          selection.kind === "row"
            ? cur.findIndex((r) => r.row_id === selection.rowId)
            : -1
        if (targetRowIndex < 0) targetRowIndex = cur.length - 1
        let rows = cur
        if (targetRowIndex < 0) {
          // No rows; create one
          rows = [
            {
              row_id: newRowId(),
              column_count: 12,
              row_height: "auto",
              column_widths: null,
              nested_rows: null,
              placements: [],
            },
          ]
          targetRowIndex = 0
        }
        const targetRow = rows[targetRowIndex]
        const placementId = nextPlacementId(rows)
        const width = Math.min(4, targetRow.column_count)
        const startingColumn = findAvailableStartingColumn(targetRow, width)
        const newPlacement: Placement = {
          placement_id: placementId,
          component_kind: componentKind,
          component_name: componentName,
          starting_column: startingColumn,
          column_span: width,
          prop_overrides: {},
          display_config: {},
          nested_rows: null,
        }
        return rows.map((r, i) =>
          i === targetRowIndex
            ? { ...r, placements: [...r.placements, newPlacement] }
            : r,
        )
      })
      setPaletteOpen(false)
    },
    [draft, selection],
  )

  const handleDeletePlacement = useCallback(
    (placementId: string) => {
      draft.setDraftRows((cur) =>
        cur.map((r) => ({
          ...r,
          placements: r.placements.filter(
            (p) => p.placement_id !== placementId,
          ),
        })),
      )
      setSelection({ kind: "none" })
    },
    [draft],
  )

  // Arc 4c — placement reorder within row (Alt+ArrowLeft/Right
  // canonical per Q-ARC4C-3 + per-placement Move buttons).
  // Moves the selected placement N column-spans within its row.
  // Multi-select group: shifts every selected placement together;
  // clamps each at row bounds.
  const handleMovePlacements = useCallback(
    (placementIds: string[], delta: number) => {
      if (placementIds.length === 0 || delta === 0) return
      const ids = new Set(placementIds)
      draft.setDraftRows((cur) =>
        cur.map((r) => {
          const movingHere = r.placements.filter((p) =>
            ids.has(p.placement_id),
          )
          if (movingHere.length === 0) return r
          return {
            ...r,
            placements: r.placements.map((p) => {
              if (!ids.has(p.placement_id)) return p
              const proposed = p.starting_column + delta
              const clamped = Math.max(
                0,
                Math.min(r.column_count - p.column_span, proposed),
              )
              return { ...p, starting_column: clamped }
            }),
          }
        }),
      )
    },
    [draft],
  )

  // Arc 4c — Alt+ArrowUp/Down row reorder via keyboard (parallel to
  // Move-up/Move-down buttons). When a row is selected, moves the row
  // up/down in the rows array. When a placement is selected, finds
  // its row and moves THAT row (operator-intent canon: "the thing I'm
  // editing should move").
  const handleReorderRowViaKey = useCallback(
    (direction: "up" | "down") => {
      const rowId =
        selection.kind === "row" && selection.rowId
          ? selection.rowId
          : (() => {
              if (
                (selection.kind === "placement" ||
                  selection.kind === "placements-multi") &&
                selection.placementIds
              ) {
                const firstId = Array.from(selection.placementIds)[0]
                for (const r of draft.draftRows) {
                  if (
                    r.placements.some((p) => p.placement_id === firstId)
                  ) {
                    return r.row_id
                  }
                }
              }
              return null
            })()
      if (!rowId) return
      draft.setDraftRows((cur) => {
        const idx = cur.findIndex((r) => r.row_id === rowId)
        if (idx < 0) return cur
        const swap = direction === "up" ? idx - 1 : idx + 1
        if (swap < 0 || swap >= cur.length) return cur
        const next = [...cur]
        ;[next[idx], next[swap]] = [next[swap], next[idx]]
        return next
      })
    },
    [draft, selection],
  )

  // Arc 4c — column-axis nudge for selected placements per Q-ARC4C-3.
  // Bare ArrowLeft/Right = ±1 column-span; Shift+Arrow = ±5 (matching
  // Figma + Arc 3a standalone canon). Multi-select moves group.
  const handleKeyboardNudge = useCallback(
    (delta: number) => {
      if (selection.kind !== "placement" && selection.kind !== "placements-multi")
        return
      const ids = Array.from(selection.placementIds ?? [])
      handleMovePlacements(ids, delta)
    },
    [selection, handleMovePlacements],
  )

  // Arc 4c — inspector-scoped keyboard listener. Handles:
  //   Arrow alone       : ±1 column-span nudge for selected placements
  //   Shift+Arrow       : ±5 column-span nudge (larger step)
  //   Alt+ArrowUp/Down  : row reorder per Q-ARC4C-3 canonical canon
  //   Alt+ArrowLeft/Right: in-row placement reorder (±1)
  //   Backspace/Delete  : per Q-ARC4C-4: NO modal for placement delete
  //   Escape            : clear selection
  //
  // Skip when focus is on input/textarea/contentEditable — matches
  // Arc 4b.1b Documents canon + standalone canvas keyboard canon.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      if (target) {
        const tag = target.tagName
        if (
          tag === "INPUT" ||
          tag === "TEXTAREA" ||
          tag === "SELECT" ||
          target.isContentEditable
        ) {
          return
        }
      }
      // Cmd/Ctrl-modified Arrow stays browser-reserved per Q-ARC4C-3
      // (Cmd/Ctrl+Arrow is canonical browser navigation; do not
      // hijack).
      if (e.metaKey || e.ctrlKey) return

      // Alt+Arrow first (modifier-distinguished from bare/shift):
      if (e.altKey && !e.shiftKey) {
        if (e.key === "ArrowUp") {
          e.preventDefault()
          handleReorderRowViaKey("up")
          return
        }
        if (e.key === "ArrowDown") {
          e.preventDefault()
          handleReorderRowViaKey("down")
          return
        }
        if (e.key === "ArrowLeft") {
          if (
            selection.kind === "placement" ||
            selection.kind === "placements-multi"
          ) {
            e.preventDefault()
            handleMovePlacements(
              Array.from(selection.placementIds ?? []),
              -1,
            )
          }
          return
        }
        if (e.key === "ArrowRight") {
          if (
            selection.kind === "placement" ||
            selection.kind === "placements-multi"
          ) {
            e.preventDefault()
            handleMovePlacements(
              Array.from(selection.placementIds ?? []),
              1,
            )
          }
          return
        }
        return
      }

      // Bare/Shift+Arrow — column-axis nudge for selected placements
      // (Q-ARC4C-3 grid-coordinate-native canon).
      if (e.key === "ArrowLeft" && !e.altKey) {
        if (
          selection.kind === "placement" ||
          selection.kind === "placements-multi"
        ) {
          e.preventDefault()
          handleKeyboardNudge(e.shiftKey ? -5 : -1)
        }
        return
      }
      if (e.key === "ArrowRight" && !e.altKey) {
        if (
          selection.kind === "placement" ||
          selection.kind === "placements-multi"
        ) {
          e.preventDefault()
          handleKeyboardNudge(e.shiftKey ? 5 : 1)
        }
        return
      }

      // Delete/Backspace — no modal per Q-ARC4C-4 canon. Cmd+Z is the
      // safety net via the standalone editor; inspector relies on
      // tab-level autosave + draft state for reversibility.
      if (
        (e.key === "Backspace" || e.key === "Delete") &&
        !e.altKey
      ) {
        if (
          selection.kind === "placement" ||
          selection.kind === "placements-multi"
        ) {
          const ids = Array.from(selection.placementIds ?? [])
          if (ids.length > 0) {
            e.preventDefault()
            // Bulk-delete still no modal per canonical canon.
            ids.forEach((id) => handleDeletePlacement(id))
          }
        }
        return
      }

      if (e.key === "Escape") {
        setSelection({ kind: "none" })
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [
    selection,
    handleKeyboardNudge,
    handleMovePlacements,
    handleReorderRowViaKey,
    handleDeletePlacement,
  ])

  // Read-mostly canvas: drag/resize/marquee disabled but click-to-select
  // preserved. Canvas Q-CROSS-2 refinement.
  const noopCommitMove = useCallback(() => {}, [])
  const noopCommitResize = useCallback(() => {}, [])
  const noopCommitRowReorder = useCallback(() => {}, [])

  const hasPendingWrite =
    draft.savingState === "saving" || draft.isDirty

  const handleBack = useCallback(() => {
    if (hasPendingWrite) {
      setGuardOpen(true)
      return
    }
    onBack()
  }, [hasPendingWrite, onBack])

  const handleGuardSave = useCallback(async () => {
    setGuardAction("save")
    await draft.flushPendingSave()
    setGuardAction(null)
    setGuardOpen(false)
    onBack()
  }, [draft, onBack])

  const handleGuardDiscard = useCallback(() => {
    setGuardAction("discard")
    draft.discardDraft()
    setGuardAction(null)
    setGuardOpen(false)
    onBack()
  }, [draft, onBack])

  // Build deep-link URL preserving current inspector state.
  const returnToUrl =
    typeof window !== "undefined"
      ? window.location.pathname + window.location.search
      : "/"
  const editorUrl = buildEditorUrl(
    compositionFocusType,
    draft.activeRow?.id ?? null,
    returnToUrl,
  )

  // Determine if a placement OR row is currently selected (for detail
  // CTA + delete affordance).
  const selectedRowId =
    selection.kind === "row" && selection.rowId ? selection.rowId : null
  const selectedPlacementIds: string[] =
    selection.kind === "placement" || selection.kind === "placements-multi"
      ? Array.from(selection.placementIds ?? [])
      : []
  const selectedRow = selectedRowId
    ? draft.draftRows.find((r) => r.row_id === selectedRowId)
    : null

  if (draft.isLoading) {
    return (
      <div
        className="flex flex-col gap-2 px-3 py-3"
        data-testid="runtime-inspector-focus-edit-loading"
      >
        <BackHeader label="Focus compositions" onBack={onBack} />
        <div className="flex items-center gap-2 text-caption text-content-muted">
          <Loader2 size={14} className="animate-spin" /> Loading composition…
        </div>
      </div>
    )
  }

  if (draft.loadError) {
    return (
      <div
        className="flex flex-col gap-2 px-3 py-3"
        data-testid="runtime-inspector-focus-edit-error"
      >
        <BackHeader label="Focus compositions" onBack={onBack} />
        <div className="rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error">
          {draft.loadError}
        </div>
      </div>
    )
  }

  return (
    <div
      className="flex flex-col gap-2 px-3 py-3"
      data-testid="runtime-inspector-focus-edit"
      data-composition-focus-type={compositionFocusType}
    >
      {/* Back header + saving indicator */}
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={handleBack}
          className="flex items-center gap-1 text-caption text-content-muted hover:text-content-strong"
          data-testid="runtime-inspector-focus-edit-back"
        >
          <ArrowLeft size={12} />
          <span>Focus compositions</span>
        </button>
        <SavingIndicator state={draft.savingState} isDirty={draft.isDirty} />
      </div>

      {/* Title */}
      <h2
        className="text-body-sm font-medium text-content-strong"
        data-testid="runtime-inspector-focus-edit-title"
      >
        {compositionFocusType}
      </h2>

      {/* Open in full editor — prominent affordance */}
      <Link
        to={editorUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-1 self-start rounded-sm border border-border-subtle bg-surface-elevated px-2 py-1 text-caption text-content-muted hover:border-accent/40 hover:text-content-strong"
        data-testid="runtime-inspector-focus-deeplink-open"
      >
        <ExternalLink size={12} /> Open in full editor
      </Link>

      {/* Action bar — Add row + Add placement (dropdown picker) */}
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          onClick={handleAddRow}
          data-testid="runtime-inspector-focus-add-row"
        >
          <Plus size={12} /> Add row
        </Button>
        <div className="relative">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setPaletteOpen((o) => !o)}
            disabled={palette.length === 0 || draft.draftRows.length === 0}
            data-testid="runtime-inspector-focus-add-placement"
          >
            <Plus size={12} /> Add placement
            <ChevronDown size={10} />
          </Button>
          {paletteOpen && (
            <div
              className="absolute left-0 top-full z-30 mt-1 flex max-h-64 w-56 flex-col overflow-y-auto rounded-sm border border-border-subtle bg-surface-raised shadow-level-2"
              data-testid="runtime-inspector-focus-palette"
            >
              {palette.map((entry) => (
                <button
                  key={`${entry.metadata.type}-${entry.metadata.name}`}
                  type="button"
                  onClick={() =>
                    handleAddPlacement(
                      entry.metadata.name,
                      entry.metadata.type as ComponentKind,
                    )
                  }
                  className="px-2 py-1 text-left text-caption text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong"
                  data-testid={`runtime-inspector-focus-palette-${entry.metadata.name}`}
                >
                  <span className="block font-medium text-content-strong">
                    {entry.metadata.displayName ?? entry.metadata.name}
                  </span>
                  <code className="font-plex-mono text-micro">
                    {entry.metadata.type}:{entry.metadata.name}
                  </code>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Read-mostly canvas */}
      {draft.draftRows.length === 0 ? (
        <div
          className="rounded-sm border border-dashed border-border-subtle bg-surface-sunken px-3 py-6 text-center text-caption text-content-muted"
          data-testid="runtime-inspector-focus-canvas-empty"
        >
          No rows yet. Click "Add row" to start composing.
        </div>
      ) : (
        <div
          className="rounded-sm border border-border-subtle"
          data-testid="runtime-inspector-focus-canvas-wrap"
        >
          <InteractivePlacementCanvas
            rows={draft.draftRows}
            gapSize={draft.draftCanvasConfig.gap_size ?? 12}
            backgroundTreatment={
              draft.draftCanvasConfig.background_treatment
            }
            selection={selection}
            showGrid={false}
            interactionsEnabled={false}
            // Arc 4c — alignment guides STANDALONE-ONLY per Q-FOCUS-1
            // canon (inspector canvas read-mostly; no drag → no guides).
            showAlignmentGuides={false}
            onSelectPlacement={handleSelectPlacement}
            onSelectRow={handleSelectRow}
            onDeselectAll={handleDeselectAll}
            onCommitPlacementMove={noopCommitMove}
            onCommitPlacementResize={noopCommitResize}
            onCommitRowReorder={noopCommitRowReorder}
            onAddRowAbove={handleAddRowAbove}
            onAddRowBelow={handleAddRowBelow}
            onDeleteRow={handleDeleteRow}
            onChangeRowColumnCount={handleChangeRowColumnCount}
          />
        </div>
      )}

      {/* Per-row reorder buttons (drag disabled in read-mostly mode;
          buttons preserve row reorder affordance per parity-not-
          exceedance canon). */}
      {draft.draftRows.length > 1 && (
        <div
          className="flex flex-col gap-1"
          data-testid="runtime-inspector-focus-row-reorder"
        >
          <div className="text-caption text-content-muted">Reorder rows</div>
          {draft.draftRows.map((row, idx) => (
            <div
              key={row.row_id}
              className="flex items-center justify-between rounded-sm border border-border-subtle bg-surface-elevated px-2 py-1"
              data-testid={`runtime-inspector-focus-row-reorder-${row.row_id}`}
            >
              <span className="text-caption text-content-muted">
                Row {idx + 1}
                <Badge variant="outline" className="ml-1 text-micro">
                  {row.placements.length} placement
                  {row.placements.length === 1 ? "" : "s"}
                </Badge>
              </span>
              <div className="flex items-center gap-1">
                {/* Arc 4c — ColumnCountPopover wired inline per Q-ARC4C-6
                    Option (c). Second-consumer canon validation
                    (canonical outcome a — substrate holds verbatim). */}
                <ColumnCountPopover
                  row={row}
                  onChange={(n) =>
                    handleChangeRowColumnCount(row.row_id, n)
                  }
                  triggerTestId={`runtime-inspector-focus-row-cols-${row.row_id}`}
                  triggerClassName="rounded-sm border border-border-subtle bg-surface-raised px-1.5 py-0.5 font-plex-mono text-micro text-content-strong hover:bg-accent-subtle/40"
                />
                <button
                  type="button"
                  onClick={() => handleReorderRow(row.row_id, "up")}
                  disabled={idx === 0}
                  className="rounded-sm p-1 text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong disabled:opacity-40"
                  aria-label={`Move row ${idx + 1} up`}
                  data-testid={`runtime-inspector-focus-row-up-${row.row_id}`}
                >
                  <ArrowUp size={12} />
                </button>
                <button
                  type="button"
                  onClick={() => handleReorderRow(row.row_id, "down")}
                  disabled={idx === draft.draftRows.length - 1}
                  className="rounded-sm p-1 text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong disabled:opacity-40"
                  aria-label={`Move row ${idx + 1} down`}
                  data-testid={`runtime-inspector-focus-row-down-${row.row_id}`}
                >
                  <ArrowDown size={12} />
                </button>
                <button
                  type="button"
                  onClick={() => handleDeleteRow(row.row_id)}
                  className="rounded-sm p-1 text-content-muted hover:bg-status-error-muted hover:text-status-error"
                  aria-label={`Delete row ${idx + 1}`}
                  data-testid={`runtime-inspector-focus-row-delete-${row.row_id}`}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Selection footer — open detail */}
      {(selectedRow ||
        selectedPlacementIds.length > 0) && (
        <div
          className="flex items-center justify-between rounded-sm border border-accent/40 bg-accent-subtle/20 px-2 py-1"
          data-testid="runtime-inspector-focus-selection-footer"
        >
          <span className="text-caption text-content-muted">
            {selectedRow
              ? "Row selected"
              : selectedPlacementIds.length === 1
                ? "Placement selected"
                : `${selectedPlacementIds.length} placements selected`}
          </span>
          <div className="flex gap-1">
            {/* Arc 4c — placement reorder within row via Move-left /
                Move-right buttons (parallel to Alt+ArrowLeft/Right
                keyboard shortcut). Visible only when at least one
                placement is selected. */}
            {selectedPlacementIds.length > 0 && (
              <>
                <button
                  type="button"
                  onClick={() =>
                    handleMovePlacements(selectedPlacementIds, -1)
                  }
                  className="rounded-sm p-1 text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong"
                  aria-label="Move placement left"
                  data-testid="runtime-inspector-focus-placement-move-left"
                >
                  <ArrowLeft size={12} />
                </button>
                <button
                  type="button"
                  onClick={() =>
                    handleMovePlacements(selectedPlacementIds, 1)
                  }
                  className="rounded-sm p-1 text-content-muted hover:bg-accent-subtle/40 hover:text-content-strong"
                  aria-label="Move placement right"
                  data-testid="runtime-inspector-focus-placement-move-right"
                >
                  <ArrowRightIcon size={12} />
                </button>
              </>
            )}
            {selectedPlacementIds.length === 1 && (
              <button
                type="button"
                onClick={() =>
                  handleDeletePlacement(selectedPlacementIds[0])
                }
                className="rounded-sm p-1 text-content-muted hover:bg-status-error-muted hover:text-status-error"
                aria-label="Delete placement"
                data-testid="runtime-inspector-focus-placement-delete"
              >
                <Trash2 size={12} />
              </button>
            )}
            {selectedPlacementIds.length > 1 && (
              <button
                type="button"
                onClick={() => {
                  // Arc 4c Q-ARC4C-4 canonical canon — bulk delete NO modal.
                  selectedPlacementIds.forEach((id) =>
                    handleDeletePlacement(id),
                  )
                }}
                className="rounded-sm p-1 text-content-muted hover:bg-status-error-muted hover:text-status-error"
                aria-label="Delete selected placements"
                data-testid="runtime-inspector-focus-placement-bulk-delete"
              >
                <Trash2 size={12} />
              </button>
            )}
            <Button
              size="sm"
              variant="outline"
              onClick={handleOpenDetailFromSelection}
              data-testid="runtime-inspector-focus-open-detail"
            >
              Open details
            </Button>
          </div>
        </div>
      )}

      <UnsavedChangesDialog
        open={guardOpen}
        actionPending={guardAction}
        onSave={handleGuardSave}
        onDiscard={handleGuardDiscard}
        onCancel={() => setGuardOpen(false)}
      />
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────
// Level 3 — Selection-driven detail
// ─────────────────────────────────────────────────────────────────


function DetailView({
  compositionFocusType,
  selection,
  vertical,
  tenantId,
  onBack,
}: {
  compositionFocusType: string
  selection: SelectionUnion
  vertical: string | null
  tenantId: string | null
  onBack: () => void
}) {
  // Resolve composition + locate the selection target. Detail
  // mutations flow back into Level 2's form-local draft via callback
  // would be the cleanest pattern, but Level 3 is a separate mode-
  // stack level — we re-load the composition and act on it directly.
  // This is the parity-not-exceedance trade: simpler than threading
  // draft state across levels. Detail is read-mostly + delete only
  // for the inspector v1; full per-placement edit (prop_overrides
  // JSON editor) is available in the standalone editor via the
  // deep-link from Level 2.
  const scope: Scope = "vertical_default"

  const [composition, setComposition] = useState<CompositionRecord | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    setLoadError(null)
    focusCompositionsService
      .resolve({
        focus_type: compositionFocusType,
        vertical: scope === "vertical_default" ? vertical : null,
        tenant_id: tenantId,
      })
      .then(async (resolved) => {
        if (cancelled) return
        if (!resolved.source_id) {
          setComposition(null)
          setIsLoading(false)
          return
        }
        try {
          const full = await focusCompositionsService.get(resolved.source_id)
          if (!cancelled) setComposition(full)
        } catch (err) {
          if (!cancelled) {
            // eslint-disable-next-line no-console
            console.warn("[runtime-editor] composition detail get failed", err)
            setLoadError(
              err instanceof Error ? err.message : "Failed to load composition",
            )
          }
        }
      })
      .catch((err) => {
        if (cancelled) return
        // eslint-disable-next-line no-console
        console.warn(
          "[runtime-editor] composition detail resolve failed",
          err,
        )
        setLoadError(
          err instanceof Error ? err.message : "Failed to load composition",
        )
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [compositionFocusType, vertical, tenantId])

  const returnToUrl =
    typeof window !== "undefined"
      ? window.location.pathname + window.location.search
      : "/"
  const editorUrl = buildEditorUrl(
    compositionFocusType,
    composition?.id ?? null,
    returnToUrl,
  )

  if (isLoading) {
    return (
      <div
        className="flex flex-col gap-2 px-3 py-3"
        data-testid="runtime-inspector-focus-detail-loading"
      >
        <BackHeader label="Composition" onBack={onBack} />
        <div className="flex items-center gap-2 text-caption text-content-muted">
          <Loader2 size={14} className="animate-spin" /> Loading…
        </div>
      </div>
    )
  }

  if (loadError) {
    return (
      <div
        className="flex flex-col gap-2 px-3 py-3"
        data-testid="runtime-inspector-focus-detail-error"
      >
        <BackHeader label="Composition" onBack={onBack} />
        <div className="rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error">
          {loadError}
        </div>
      </div>
    )
  }

  if (!composition) {
    return (
      <div
        className="flex flex-col gap-2 px-3 py-3"
        data-testid="runtime-inspector-focus-detail-empty"
      >
        <BackHeader label="Composition" onBack={onBack} />
        <div className="rounded-sm border border-border-subtle bg-surface-sunken px-2 py-2 text-caption text-content-muted">
          No composition exists at this scope.
        </div>
      </div>
    )
  }

  // Selection-driven detail dispatch (Q-FOCUS-2 canon).
  if (selection.kind === "row") {
    return (
      <RowDetailContent
        composition={composition}
        rowId={selection.rowId}
        editorUrl={editorUrl}
        onBack={onBack}
      />
    )
  }

  if (selection.kind === "placement") {
    return (
      <PlacementDetailContent
        composition={composition}
        placementId={selection.placementId}
        editorUrl={editorUrl}
        onBack={onBack}
      />
    )
  }

  // selection.kind === "multi"
  return (
    <BulkDetailContent
      composition={composition}
      placementIds={selection.placementIds}
      editorUrl={editorUrl}
      onBack={onBack}
    />
  )
}


function RowDetailContent({
  composition,
  rowId,
  editorUrl,
  onBack,
}: {
  composition: CompositionRecord
  rowId: string
  editorUrl: string
  onBack: () => void
}) {
  const row = composition.rows.find((r) => r.row_id === rowId)
  return (
    <div
      className="flex flex-col gap-2 px-3 py-3"
      data-testid="runtime-inspector-focus-detail-row"
      data-row-id={rowId}
    >
      <BackHeader label="Composition" onBack={onBack} />
      <h3 className="text-body-sm font-medium text-content-strong">
        Row config
      </h3>
      {!row ? (
        <div className="rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error">
          Row not found in current composition.
        </div>
      ) : (
        <>
          <DetailField label="Row ID">
            <code className="font-plex-mono text-micro">{rowId}</code>
          </DetailField>
          <DetailField label="Column count">
            <Badge variant="outline">{row.column_count}</Badge>
          </DetailField>
          <DetailField label="Row height">
            <Badge variant="outline">
              {row.row_height === "auto" ? "auto" : `${row.row_height}px`}
            </Badge>
          </DetailField>
          <DetailField label="Placements">
            <Badge variant="outline">{row.placements.length}</Badge>
          </DetailField>
        </>
      )}
      <DetailLink editorUrl={editorUrl} />
    </div>
  )
}


function PlacementDetailContent({
  composition,
  placementId,
  editorUrl,
  onBack,
}: {
  composition: CompositionRecord
  placementId: string
  editorUrl: string
  onBack: () => void
}) {
  let foundRowId: string | null = null
  let foundPlacement: Placement | null = null
  for (const r of composition.rows) {
    const p = r.placements.find((pl) => pl.placement_id === placementId)
    if (p) {
      foundPlacement = p
      foundRowId = r.row_id
      break
    }
  }
  const entry = foundPlacement
    ? getByName(foundPlacement.component_kind, foundPlacement.component_name)
    : null
  return (
    <div
      className="flex flex-col gap-2 px-3 py-3"
      data-testid="runtime-inspector-focus-detail-placement"
      data-placement-id={placementId}
    >
      <BackHeader label="Composition" onBack={onBack} />
      <h3 className="text-body-sm font-medium text-content-strong">
        Placement config
      </h3>
      {!foundPlacement ? (
        <div className="rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error">
          Placement not found in current composition.
        </div>
      ) : (
        <>
          <DetailField label="Component">
            <span className="font-medium text-content-strong">
              {entry?.metadata.displayName ?? foundPlacement.component_name}
            </span>
          </DetailField>
          <DetailField label="Kind">
            <code className="font-plex-mono text-micro">
              {foundPlacement.component_kind}
            </code>
          </DetailField>
          <DetailField label="Row">
            <code className="font-plex-mono text-micro">{foundRowId}</code>
          </DetailField>
          <DetailField label="Starting column">
            <Badge variant="outline">{foundPlacement.starting_column}</Badge>
          </DetailField>
          <DetailField label="Column span">
            <Badge variant="outline">{foundPlacement.column_span}</Badge>
          </DetailField>
          <DetailField label="Prop overrides">
            <Badge variant="outline">
              {Object.keys(foundPlacement.prop_overrides).length} key
              {Object.keys(foundPlacement.prop_overrides).length === 1 ? "" : "s"}
            </Badge>
          </DetailField>
        </>
      )}
      <DetailLink editorUrl={editorUrl} note="Edit prop overrides in full editor" />
    </div>
  )
}


function BulkDetailContent({
  composition: _composition,
  placementIds,
  editorUrl,
  onBack,
}: {
  composition: CompositionRecord
  placementIds: readonly string[]
  editorUrl: string
  onBack: () => void
}) {
  void _composition
  return (
    <div
      className="flex flex-col gap-2 px-3 py-3"
      data-testid="runtime-inspector-focus-detail-bulk"
    >
      <BackHeader label="Composition" onBack={onBack} />
      <h3 className="text-body-sm font-medium text-content-strong">
        Bulk operations
      </h3>
      <DetailField label="Selected placements">
        <Badge variant="outline">{placementIds.length}</Badge>
      </DetailField>
      <div className="rounded-sm border border-border-subtle bg-surface-sunken px-2 py-2 text-caption text-content-muted">
        Bulk operations land in a future arc when concrete operator
        signal warrants. v1 supports per-selection viewing.
      </div>
      <DetailLink editorUrl={editorUrl} note="Manage in full editor" />
    </div>
  )
}


function DetailField({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-sm border border-border-subtle bg-surface-elevated px-2 py-1">
      <span className="text-caption text-content-muted">{label}</span>
      <div className="text-caption text-content-strong">{children}</div>
    </div>
  )
}


function DetailLink({
  editorUrl,
  note,
}: {
  editorUrl: string
  note?: string
}) {
  return (
    <Link
      to={editorUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-1 self-start rounded-sm border border-border-subtle bg-surface-elevated px-2 py-1 text-caption text-content-muted hover:border-accent/40 hover:text-content-strong"
      data-testid="runtime-inspector-focus-detail-deeplink"
    >
      <ExternalLink size={12} /> {note ?? "Open in full editor"}
    </Link>
  )
}


// ─────────────────────────────────────────────────────────────────
// Shared sub-components
// ─────────────────────────────────────────────────────────────────


function BackHeader({
  label,
  onBack,
}: {
  label: string
  onBack: () => void
}) {
  return (
    <button
      type="button"
      onClick={onBack}
      className="flex items-center gap-1 text-caption text-content-muted hover:text-content-strong"
      data-testid="runtime-inspector-focus-back-header"
    >
      <ArrowLeft size={12} />
      <span>{label}</span>
    </button>
  )
}


function SavingIndicator({
  state,
  isDirty,
}: {
  state: SavingState
  isDirty: boolean
}) {
  if (state === "saving") {
    return (
      <span
        className="flex items-center gap-1 text-caption text-content-muted"
        data-testid="runtime-inspector-focus-saving-indicator"
        data-state="saving"
      >
        <Loader2 size={10} className="animate-spin" />
        Saving…
      </span>
    )
  }
  if (state === "error") {
    return (
      <span
        className="text-caption text-status-error"
        data-testid="runtime-inspector-focus-saving-indicator"
        data-state="error"
      >
        Save failed
      </span>
    )
  }
  if (isDirty) {
    return (
      <span
        className="text-caption text-content-muted"
        data-testid="runtime-inspector-focus-saving-indicator"
        data-state="unsaved"
      >
        Unsaved
      </span>
    )
  }
  if (state === "saved") {
    return (
      <span
        className="text-caption text-content-muted"
        data-testid="runtime-inspector-focus-saving-indicator"
        data-state="saved"
      >
        Saved
      </span>
    )
  }
  return null
}


function UnsavedChangesDialog({
  open,
  actionPending,
  onSave,
  onDiscard,
  onCancel,
}: {
  open: boolean
  actionPending: GuardAction
  onSave: () => void
  onDiscard: () => void
  onCancel: () => void
}) {
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onCancel()
      }}
    >
      <DialogContent
        showCloseButton={false}
        data-testid="runtime-inspector-focus-unsaved-dialog"
      >
        <DialogHeader>
          <DialogTitle>Unsaved changes</DialogTitle>
          <DialogDescription>
            You have unsaved composition changes. Save now or discard?
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={onCancel}
            disabled={actionPending !== null}
            data-testid="runtime-inspector-focus-unsaved-cancel"
          >
            Cancel
          </Button>
          <Button
            variant="outline"
            onClick={onDiscard}
            disabled={actionPending !== null}
            data-testid="runtime-inspector-focus-unsaved-discard"
          >
            Discard
          </Button>
          <Button
            onClick={() => {
              void onSave()
            }}
            disabled={actionPending !== null}
            data-testid="runtime-inspector-focus-unsaved-save"
          >
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
