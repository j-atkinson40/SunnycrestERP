/**
 * Phase R-1 — Inspector right-rail panel.
 *
 * 380px wide, full-height minus header. Slides in/out on selection.
 * Default tab: Props (the most-frequently-edited surface for widget
 * authoring). Theme | Class | Props in canonical reading order.
 *
 * Footer carries Commit / Discard buttons + per-failed-key inline
 * errors with Retry buttons (Part 7 — partial-commit UX). Header
 * shows the selected widget's identity (kind:name) + close affordance.
 *
 * Render gated on `isEditing && selectedComponentName !== null`.
 * Outside that, the rail is unmounted so the impersonated tenant
 * route renders at full width.
 */
import { useMemo, useState } from "react"
import { X } from "lucide-react"

import {
  getByName,
  getSubSectionsFor,
  type ComponentKind,
  type RegistryEntry,
} from "@/lib/visual-editor/registry"
import type { ThemeMode } from "@/bridgeable-admin/services/themes-service"

import { useEditMode } from "../edit-mode-context"
import { ClassTab } from "./ClassTab"
import { DocumentsTab } from "./DocumentsTab"
import { PropsTab } from "./PropsTab"
import { ThemeTab } from "./ThemeTab"
import { WorkflowsTab } from "./WorkflowsTab"


// Arc 2 Phase 2a — added "workflows" as 4th tab in the inner strip.
// Workflows tab follows direct-service-call pattern (NOT staged-
// override writer) — saves go through workflowTemplatesService
// directly.
//
// Arc 3b — added "documents" as 5th tab. Per-block immediate writes
// (Q-DOCS-2 canon); tab is selection-independent at the tab body
// level (operator can browse document templates regardless of which
// component is selected).
type TabKey = "props" | "class" | "theme" | "workflows" | "documents"


export interface InspectorPanelProps {
  /** Vertical scope used by the Theme tab's resolve call. Wired by
   *  RuntimeEditorShell from the impersonation context. */
  vertical: string | null
  /** Tenant id used by the Theme tab's resolve call. */
  tenantId: string | null
  /** Mode used by the Theme tab. R-1 ships light only via the toggle
   *  default; future phases pipe the theme-mode picker through. */
  themeMode: ThemeMode
}


export function InspectorPanel({
  vertical,
  tenantId,
  themeMode,
}: InspectorPanelProps) {
  const editMode = useEditMode()
  const [activeTab, setActiveTab] = useState<TabKey>("props")

  // Look up the selected component's registry entry. The capture-phase
  // click handler stores names; we walk every kind to find the matching
  // entry (component names are unique within a kind by registry
  // contract; collision across kinds is rare but possible — we take
  // the first match).
  //
  // R-2.0.4: kinds list extended to include the 4 ComponentKind values
  // added during the May 2026 class-configuration phase (entity-card,
  // button, form-input, surface-card).
  //
  // R-2.1: kinds list extended with the 13th ComponentKind value
  // (entity-card-section). When a sub-section is selected, the union
  // shape carries `kind: "component-section"` AND we still resolve the
  // sub-section's own entry here for the per-section inner triad.
  // Add a kind here whenever ComponentKind grows.
  const selectedEntry = useMemo(() => {
    if (!editMode.selectedComponentName) return null
    const kinds: ComponentKind[] = [
      "widget",
      "focus",
      "focus-template",
      "document-block",
      "pulse-widget",
      "workflow-node",
      "layout",
      "composite",
      "entity-card",
      "button",
      "form-input",
      "surface-card",
      "entity-card-section",
    ]
    for (const k of kinds) {
      const entry = getByName(k, editMode.selectedComponentName)
      if (entry) return entry
    }
    return null
  }, [editMode.selectedComponentName])

  // R-2.1 — outer tabs.
  //
  // When the selection is a sub-section, OR when the selection is a
  // parent that has registered sub-sections, the inspector renders an
  // outer tab strip [Card][Header][Body][Actions][...] above the inner
  // triad (Theme/Class/Props). The active outer tab determines which
  // entry the inner triad operates on — clicking "Card" scopes inner
  // triad to the parent, clicking a sub-section tab scopes to that
  // section.
  //
  // Sub-sections are discovered via `getSubSectionsFor(parentKind,
  // parentName)` which consults `extensions.entityCardSection` (NOT
  // slug-string parsing — the metadata path stays canonical even if a
  // future parent slug contains dots).
  const isSubSectionSelected =
    editMode.selection.kind === "component-section"
  const parentKind: ComponentKind | null =
    editMode.selection.kind === "component-section"
      ? editMode.selection.parentKind
      : editMode.selection.kind === "component"
        ? editMode.selection.componentKind
        : null
  const parentName: string | null =
    editMode.selection.kind === "component-section"
      ? editMode.selection.parentName
      : editMode.selection.kind === "component"
        ? editMode.selection.componentName
        : null

  const parentEntry: RegistryEntry | null = useMemo(() => {
    if (!parentKind || !parentName) return null
    return getByName(parentKind, parentName) ?? null
  }, [parentKind, parentName])

  const subSections: readonly RegistryEntry[] = useMemo(() => {
    if (!parentKind || !parentName) return []
    return getSubSectionsFor(parentKind, parentName)
  }, [parentKind, parentName])

  // Outer tab activation. "card" tab = parent; sub-section names = sub.
  // Default: when a sub-section is selected, that sub-section's tab is
  // active; otherwise the "card" tab is active.
  const [outerTabOverride, setOuterTabOverride] = useState<string | null>(
    null,
  )
  // The currently-active outer tab's identifier.
  const activeOuterTab: string =
    outerTabOverride ??
    (isSubSectionSelected
      ? editMode.selection.kind === "component-section"
        ? editMode.selection.componentName
        : "card"
      : "card")

  // Resolve the entry the inner triad operates on. If active outer tab
  // is "card", that's the parent. Otherwise it's the named sub-section.
  const activeInnerEntry: RegistryEntry | null = useMemo(() => {
    if (activeOuterTab === "card") return parentEntry
    return subSections.find((s) => s.metadata.name === activeOuterTab) ??
      selectedEntry
  }, [activeOuterTab, parentEntry, subSections, selectedEntry])

  const outerTabsVisible = subSections.length > 0

  if (!editMode.isEditing) return null
  if (!editMode.selectedComponentName) return null

  const stagedCount = editMode.draftOverrides.size

  return (
    <aside
      data-runtime-editor-chrome="true"
      data-testid="runtime-inspector-panel"
      className="fixed right-0 top-0 z-[95] h-full w-[380px] border-l border-border-base bg-surface-elevated shadow-level-3 flex flex-col"
      style={{ zIndex: 95 }}
    >
      {/* Header */}
      <header className="flex items-center justify-between border-b border-border-subtle px-4 py-3">
        <div className="min-w-0 flex-1">
          <div className="text-caption text-content-muted">
            {selectedEntry?.metadata.type ?? "unknown"}
          </div>
          <div
            className="text-body-sm font-medium text-content-strong truncate"
            data-testid="runtime-inspector-component-name"
            data-component-slug={editMode.selectedComponentName ?? ""}
          >
            {selectedEntry?.metadata.displayName ??
              editMode.selectedComponentName}
          </div>
        </div>
        <button
          type="button"
          onClick={() => editMode.selectComponent(null)}
          className="ml-2 rounded-sm p-1 text-content-muted hover:bg-accent-subtle hover:text-content-strong"
          aria-label="Close inspector"
          data-testid="runtime-inspector-close"
        >
          <X size={16} />
        </button>
      </header>

      {/* R-2.1 — outer tab strip. Renders ONLY when the selected
          component (or its parent) has registered sub-sections.
          Card tab = the parent's own theme/class/props; sub-section
          tabs scope the inner triad to that sub-section's entry. */}
      {outerTabsVisible && (
        <nav
          className="flex border-b border-border-subtle text-caption overflow-x-auto"
          data-testid="runtime-inspector-outer-tabs"
        >
          <button
            type="button"
            onClick={() => setOuterTabOverride("card")}
            className={`flex-shrink-0 px-3 py-1.5 font-medium transition-colors ${
              activeOuterTab === "card"
                ? "border-b-2 border-accent text-content-strong"
                : "border-b-2 border-transparent text-content-muted hover:text-content-strong"
            }`}
            data-testid="runtime-inspector-outer-tab-card"
            data-active={activeOuterTab === "card" ? "true" : "false"}
          >
            Card
          </button>
          {subSections.map((s) => {
            const tabId = s.metadata.name
            // Strip parent prefix from displayName for the tab label
            // ("Delivery Card · Header" → "Header"). Falls back to
            // sectionRole capitalized when displayName doesn't carry
            // the canonical separator.
            const fullDisplay = s.metadata.displayName
            const sepIdx = fullDisplay.indexOf(" · ")
            const tabLabel =
              sepIdx >= 0
                ? fullDisplay.slice(sepIdx + 3)
                : fullDisplay
            return (
              <button
                key={tabId}
                type="button"
                onClick={() => setOuterTabOverride(tabId)}
                className={`flex-shrink-0 px-3 py-1.5 font-medium transition-colors ${
                  activeOuterTab === tabId
                    ? "border-b-2 border-accent text-content-strong"
                    : "border-b-2 border-transparent text-content-muted hover:text-content-strong"
                }`}
                data-testid={`runtime-inspector-outer-tab-${tabId}`}
                data-active={activeOuterTab === tabId ? "true" : "false"}
              >
                {tabLabel}
              </button>
            )
          })}
        </nav>
      )}

      {/* Inner tab strip (Theme / Class / Props / Workflows).
          Arc 2 Phase 2a appended Workflows as 4th tab. Tab content
          swap below renders the Workflows tab body even when no
          activeInnerEntry exists (workflows tab is selection-
          independent — operator can browse workflows for any surface
          regardless of which component is selected). The panel
          itself still gates on selection per the existing R-1
          contract; selection-free panel mount is Phase 2b territory
          per investigation §5 "selection model" finding. */}
      <nav className="flex border-b border-border-subtle text-caption">
        {(["theme", "class", "props", "workflows", "documents"] as const).map(
          (key) => (
            <button
              key={key}
              type="button"
              onClick={() => setActiveTab(key)}
              className={`flex-1 px-2 py-2 font-medium transition-colors ${
                activeTab === key
                  ? "border-b-2 border-accent text-content-strong"
                  : "border-b-2 border-transparent text-content-muted hover:text-content-strong"
              }`}
              data-testid={`runtime-inspector-tab-${key}`}
              data-active={activeTab === key ? "true" : "false"}
            >
              {key === "theme"
                ? "Theme"
                : key === "class"
                  ? "Class"
                  : key === "props"
                    ? "Props"
                    : key === "workflows"
                      ? "Workflows"
                      : "Documents"}
            </button>
          ),
        )}
      </nav>

      {/* Tab body — operates on activeInnerEntry (R-2.1) which derives
          from the active outer tab + selection state. Arc 2 Phase 2a:
          Workflows tab renders independently of activeInnerEntry —
          workflows browse is selection-independent. Arc 3b: Documents
          tab follows the same selection-independent pattern. The
          unregistered-component notice only shows for Theme / Class /
          Props tabs. */}
      <div className="flex-1 overflow-y-auto">
        {!activeInnerEntry &&
          activeTab !== "workflows" &&
          activeTab !== "documents" && (
            <div className="px-3 py-4 text-caption text-content-muted">
              Selected component <code>{editMode.selectedComponentName}</code>{" "}
              is not registered. Edits unavailable.
            </div>
          )}
        {activeInnerEntry && activeTab === "props" && (
          <PropsTab selectedEntry={activeInnerEntry} vertical={vertical} />
        )}
        {activeInnerEntry && activeTab === "class" && (
          <ClassTab selectedEntry={activeInnerEntry} />
        )}
        {activeInnerEntry && activeTab === "theme" && (
          <ThemeTab
            vertical={vertical}
            tenantId={tenantId}
            themeMode={themeMode}
          />
        )}
        {activeTab === "workflows" && <WorkflowsTab vertical={vertical} />}
        {activeTab === "documents" && <DocumentsTab vertical={vertical} />}
      </div>

      {/* Footer — commit/discard + partial-commit errors */}
      <footer className="border-t border-border-subtle px-3 py-2">
        {editMode.commitError && (
          <div
            className="mb-2 rounded-sm bg-status-error-muted px-2 py-1 text-caption text-status-error"
            data-testid="runtime-inspector-commit-error"
          >
            {editMode.commitError}
          </div>
        )}
        <div className="flex items-center justify-between gap-2">
          <span
            className="text-caption text-content-muted"
            data-testid="runtime-inspector-staged-count"
          >
            {stagedCount === 0
              ? "No unsaved changes"
              : `${stagedCount} unsaved change${stagedCount === 1 ? "" : "s"}`}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => editMode.discardDraft()}
              disabled={stagedCount === 0 || editMode.isCommitting}
              className="rounded-sm border border-border-base px-2 py-1 text-caption text-content-strong hover:bg-accent-subtle/40 disabled:opacity-50"
              data-testid="runtime-inspector-discard"
            >
              Discard
            </button>
            <button
              type="button"
              onClick={() => void editMode.commitDraft()}
              disabled={stagedCount === 0 || editMode.isCommitting}
              className="rounded-sm bg-accent px-2 py-1 text-caption text-content-on-accent hover:bg-accent-hover disabled:opacity-50"
              data-testid="runtime-inspector-commit"
            >
              {editMode.isCommitting ? "Committing…" : "Commit"}
            </button>
          </div>
        </div>
      </footer>
    </aside>
  )
}
