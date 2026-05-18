/**
 * InheritedCoreInspectorPanel — sub-arc C-2.2c.
 *
 * Read-only side panel surfaced when an operator clicks the inherited
 * core placement on the Tier 2 canvas. Shows the Tier 1 core's
 * properties — slug, version, registered component, chrome blob
 * fields, default geometry. Provides an "Edit core in Tier 1"
 * affordance that navigates to the Tier 1 editor with the core
 * preselected. When the Tier 2 template is dirty, the affordance
 * raises a confirm-before-leave dialog with three paths:
 *
 *   ─ Save & continue → save Tier 2 draft, then navigate
 *   ─ Discard & continue → discard Tier 2 draft, then navigate
 *   ─ Cancel → return to inspecting; no navigation
 *
 * Implementation choice (surfaced in build report):
 *
 *   The panel renders as an absolutely-positioned slide-in over the
 *   inspector area (340px from the right edge). Rationale:
 *
 *     - Preserves the canvas underneath so the operator can see
 *       WHAT they're inspecting alongside its properties.
 *     - Doesn't unmount the inspector below — Tier 2 unsaved state
 *       in useFocusTemplateDraft stays intact regardless of how the
 *       operator dismisses the side panel.
 *     - Aligns with Sketch's right-panel "show me the source" style
 *       (the canonical reference the C-1 inspector substrate borrowed
 *       its rhythm from).
 *
 * The panel mounts a second PropertyPanel via the C-2.2c data-testid
 * passthrough; the inspector below keeps its `property-panel` id so
 * tests can distinguish the two.
 */
import * as React from "react"
import { X, ExternalLink } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  PropertyPanel,
  PropertyRow,
  PropertySection,
} from "@/bridgeable-admin/components/visual-authoring"
import type { CoreRecord } from "@/bridgeable-admin/services/focus-cores-service"

export interface InheritedCoreInspectorPanelProps {
  /** Inherited core data, or null while loading. */
  core: CoreRecord | null
  /** Whether the host Tier 2 template has unsaved edits. */
  isDirty: boolean
  /** Save the host template draft (used by Save-and-continue path). */
  saveDraft: () => Promise<void>
  /** Discard the host template draft (Discard-and-continue path). */
  discardDraft: () => void
  /**
   * Called when the operator confirms navigation to the Tier 1
   * editor. The host wires this to `useNavigate` with the right
   * query string (?tier=1&core=<inherited_core_id>).
   */
  onNavigateToTier1Core: (coreId: string) => void
  /** Close the side panel; preserve all state. */
  onClose: () => void
}

type ConfirmChoice = null | "save" | "discard"

export function InheritedCoreInspectorPanel({
  core,
  isDirty,
  saveDraft,
  discardDraft,
  onNavigateToTier1Core,
  onClose,
}: InheritedCoreInspectorPanelProps) {
  const [confirmOpen, setConfirmOpen] = React.useState(false)
  const [confirmBusy, setConfirmBusy] = React.useState<ConfirmChoice>(null)

  const handleEditCore = React.useCallback(() => {
    if (!core) return
    if (isDirty) {
      setConfirmOpen(true)
      return
    }
    onNavigateToTier1Core(core.id)
  }, [core, isDirty, onNavigateToTier1Core])

  const handleSaveAndContinue = React.useCallback(async () => {
    if (!core) return
    setConfirmBusy("save")
    try {
      await saveDraft()
      setConfirmOpen(false)
      onNavigateToTier1Core(core.id)
    } finally {
      setConfirmBusy(null)
    }
  }, [core, saveDraft, onNavigateToTier1Core])

  const handleDiscardAndContinue = React.useCallback(() => {
    if (!core) return
    setConfirmBusy("discard")
    discardDraft()
    setConfirmOpen(false)
    setConfirmBusy(null)
    onNavigateToTier1Core(core.id)
  }, [core, discardDraft, onNavigateToTier1Core])

  const handleConfirmCancel = React.useCallback(() => {
    setConfirmOpen(false)
    setConfirmBusy(null)
  }, [])

  return (
    <aside
      data-testid="inherited-core-inspector-panel"
      role="complementary"
      aria-label="Inherited core inspector"
      className="absolute inset-y-0 right-0 z-30 flex w-[340px] shrink-0 flex-col border-l-2 border-l-[color:var(--accent)] bg-[color:var(--surface-sunken)] shadow-[var(--shadow-level-2)]"
    >
      <header
        className="flex items-start justify-between gap-2 border-b border-[color:var(--border-subtle)] px-4 py-3"
        style={{ fontFamily: "var(--font-plex-sans)" }}
      >
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[color:var(--accent)]">
            Inherited Tier 1 core
          </span>
          <span
            data-testid="inherited-core-display-name"
            className="text-[14px] font-medium text-[color:var(--content-strong)]"
          >
            {core?.display_name ?? "Loading…"}
          </span>
          {core && (
            <span
              data-testid="inherited-core-slug"
              className="text-[11px] text-[color:var(--content-muted)]"
              style={{ fontFamily: "var(--font-plex-mono)" }}
            >
              {core.core_slug} · v{core.version}
            </span>
          )}
        </div>
        <button
          type="button"
          aria-label="Close inherited core inspector"
          data-testid="inherited-core-close"
          onClick={onClose}
          className="rounded p-1 text-[color:var(--content-muted)] hover:bg-[color:var(--accent-subtle)] hover:text-[color:var(--content-base)]"
        >
          <X className="h-4 w-4" />
        </button>
      </header>

      <div className="flex-1 overflow-y-auto">
        {core ? (
          <PropertyPanel data-testid="inherited-core-properties-panel">
            <PropertySection title="Registered component" defaultExpanded>
              <PropertyRow label="Kind">
                <span
                  data-testid="inherited-core-component-kind"
                  className="text-[12px] text-[color:var(--content-base)] font-mono"
                >
                  {core.registered_component_kind}
                </span>
              </PropertyRow>
              <PropertyRow label="Name">
                <span
                  data-testid="inherited-core-component-name"
                  className="text-[12px] text-[color:var(--content-base)] font-mono"
                >
                  {core.registered_component_name}
                </span>
              </PropertyRow>
            </PropertySection>

            <PropertySection title="Chrome (read-only)" defaultExpanded>
              {Object.entries(core.chrome ?? {}).length === 0 ? (
                <PropertyRow>
                  <span
                    data-testid="inherited-core-chrome-empty"
                    className="text-[11px] italic text-[color:var(--content-muted)]"
                  >
                    Core ships with empty chrome — Tier 2 overrides are
                    the source of truth.
                  </span>
                </PropertyRow>
              ) : (
                Object.entries(core.chrome ?? {}).map(([k, v]) => (
                  <PropertyRow key={k} label={k}>
                    <span
                      data-testid={`inherited-core-chrome-${k}`}
                      className="text-[12px] text-[color:var(--content-base)] font-mono"
                    >
                      {String(v)}
                    </span>
                  </PropertyRow>
                ))
              )}
            </PropertySection>

            <PropertySection title="Default geometry" defaultExpanded>
              <PropertyRow label="Starting column">
                <span className="text-[12px] tabular-nums text-[color:var(--content-base)] font-mono">
                  {core.default_starting_column}
                </span>
              </PropertyRow>
              <PropertyRow label="Column span">
                <span className="text-[12px] tabular-nums text-[color:var(--content-base)] font-mono">
                  {core.default_column_span}
                </span>
              </PropertyRow>
              <PropertyRow label="Row index">
                <span className="text-[12px] tabular-nums text-[color:var(--content-base)] font-mono">
                  {core.default_row_index}
                </span>
              </PropertyRow>
              <PropertyRow label="Min span">
                <span className="text-[12px] tabular-nums text-[color:var(--content-base)] font-mono">
                  {core.min_column_span}
                </span>
              </PropertyRow>
              <PropertyRow label="Max span">
                <span className="text-[12px] tabular-nums text-[color:var(--content-base)] font-mono">
                  {core.max_column_span}
                </span>
              </PropertyRow>
            </PropertySection>
          </PropertyPanel>
        ) : (
          <div
            data-testid="inherited-core-loading"
            className="flex h-full items-center justify-center p-6 text-[12px] text-[color:var(--content-muted)]"
          >
            Loading inherited core…
          </div>
        )}
      </div>

      <footer className="flex items-center justify-between gap-2 border-t border-[color:var(--border-subtle)] p-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={onClose}
          data-testid="inherited-core-close-footer"
        >
          Close
        </Button>
        <Button
          size="sm"
          onClick={handleEditCore}
          disabled={!core}
          data-testid="inherited-core-edit-button"
          className="gap-1"
        >
          <ExternalLink className="h-3 w-3" />
          Edit core in Tier 1
        </Button>
      </footer>

      {confirmOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="inherited-core-confirm-title"
          data-testid="inherited-core-confirm-dialog"
          className="absolute inset-0 z-40 flex items-center justify-center bg-[color:var(--shadow-color-strong,rgba(48,32,16,0.40))]"
          onClick={(e) => {
            if (e.target === e.currentTarget && !confirmBusy) {
              handleConfirmCancel()
            }
          }}
        >
          <div
            className="flex w-[320px] max-w-[90%] flex-col gap-3 rounded-lg border border-[color:var(--border-subtle)] bg-[color:var(--surface-elevated)] p-4 shadow-[var(--shadow-level-2)]"
            style={{ fontFamily: "var(--font-plex-sans)" }}
          >
            <h3
              id="inherited-core-confirm-title"
              className="text-[14px] font-medium text-[color:var(--content-strong)]"
            >
              You have unsaved changes
            </h3>
            <p className="text-[12px] text-[color:var(--content-muted)]">
              Jumping to the Tier 1 editor will leave this Tier 2
              template. Choose how to handle your unsaved edits.
            </p>
            <div className="flex flex-col gap-2">
              <Button
                size="sm"
                onClick={handleSaveAndContinue}
                disabled={confirmBusy !== null}
                data-testid="inherited-core-confirm-save"
              >
                {confirmBusy === "save"
                  ? "Saving…"
                  : "Save & continue"}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={handleDiscardAndContinue}
                disabled={confirmBusy !== null}
                data-testid="inherited-core-confirm-discard"
              >
                Discard & continue
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={handleConfirmCancel}
                disabled={confirmBusy !== null}
                data-testid="inherited-core-confirm-cancel"
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
    </aside>
  )
}

export default InheritedCoreInspectorPanel
