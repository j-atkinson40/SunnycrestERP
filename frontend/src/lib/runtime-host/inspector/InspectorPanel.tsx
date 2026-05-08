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

import { getByName, type ComponentKind } from "@/lib/visual-editor/registry"
import type { ThemeMode } from "@/bridgeable-admin/services/themes-service"

import { useEditMode } from "../edit-mode-context"
import { ClassTab } from "./ClassTab"
import { PropsTab } from "./PropsTab"
import { ThemeTab } from "./ThemeTab"


type TabKey = "props" | "class" | "theme"


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
    ]
    for (const k of kinds) {
      const entry = getByName(k, editMode.selectedComponentName)
      if (entry) return entry
    }
    return null
  }, [editMode.selectedComponentName])

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

      {/* Tab strip */}
      <nav className="flex border-b border-border-subtle text-caption">
        {(["theme", "class", "props"] as const).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setActiveTab(key)}
            className={`flex-1 px-3 py-2 font-medium transition-colors ${
              activeTab === key
                ? "border-b-2 border-accent text-content-strong"
                : "border-b-2 border-transparent text-content-muted hover:text-content-strong"
            }`}
            data-testid={`runtime-inspector-tab-${key}`}
            data-active={activeTab === key ? "true" : "false"}
          >
            {key === "theme" ? "Theme" : key === "class" ? "Class" : "Props"}
          </button>
        ))}
      </nav>

      {/* Tab body */}
      <div className="flex-1 overflow-y-auto">
        {!selectedEntry && (
          <div className="px-3 py-4 text-caption text-content-muted">
            Selected component <code>{editMode.selectedComponentName}</code> is
            not registered. Edits unavailable.
          </div>
        )}
        {selectedEntry && activeTab === "props" && (
          <PropsTab selectedEntry={selectedEntry} vertical={vertical} />
        )}
        {selectedEntry && activeTab === "class" && (
          <ClassTab selectedEntry={selectedEntry} />
        )}
        {selectedEntry && activeTab === "theme" && (
          <ThemeTab
            vertical={vertical}
            tenantId={tenantId}
            themeMode={themeMode}
          />
        )}
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
