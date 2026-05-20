/**
 * FocusEditorPage — Studio's Focus authoring surface.
 *
 * Sub-arc C-2.1 (May 2026): rewritten around the Tier 1 + Tier 2
 * inheritance model. The previous shape (single-tier composition
 * authoring against the legacy `focus_compositions` table) predated
 * the substrate phase (sub-arcs A → B-5) and is replaced.
 *
 *   ┌─ Top bar ────────────────────────────────────────────────┐
 *   │ [Tier 1 cores | Tier 2 templates ]   • <core name>   ⏱  │
 *   └──────────────────────────────────────────────────────────┘
 *   ┌─ Browser ──┬─ Preview ────────────────┬─ Inspector ──────┐
 *   │ Tier 1 ─→  │ Card-like preview        │ Chrome           │
 *   │   cores    │ surface applying         │   PropertyPanel  │
 *   │ Tier 2 ─→  │ resolved chrome          │   composed from  │
 *   │   placeholder (C-2.2)                                    │
 *   └────────────┴──────────────────────────┴──────────────────┘
 *
 * Tier 1 = Focus Cores (this sub-arc): chrome-only authoring against
 * platform-default cores. Composes the C-1 visual-authoring
 * primitives (ScrubbableButton, TokenSwatchPicker, ChromePresetPicker,
 * PropertyPanel) into a chrome inspector that auto-saves a 300ms
 * debounce after the last scrub or swatch change.
 *
 * Tier 2 = Focus Templates: named placeholder in C-2.1. C-2.2 will
 * ship the templates editor + the three-section inspector
 * (chrome / substrate / typography) + canvas tier-prop adaptation +
 * inheritance surfacing.
 *
 * URL contract: ?tier=1|2 deep-links the active tier. ?core=<id>
 * pre-selects a Tier 1 core. ?return_to=<url> preserves the
 * Arc-3a runtime-editor back-link contract.
 */
import * as React from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { ArrowLeft, Circle } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Tier1CoresEditor } from "@/bridgeable-admin/components/visual-editor/Tier1CoresEditor"
import {
  Tier2TemplatesEditor,
  type InheritedCoreLineage,
} from "@/bridgeable-admin/components/visual-editor/Tier2TemplatesEditor"
import { CoexistenceDeprecationBanner } from "@/bridgeable-admin/components/focus-builder/CoexistenceDeprecationBanner"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"

type Tier = "1" | "2"

function relativeTime(when: Date | null): string {
  if (!when) return ""
  const secs = Math.max(0, Math.round((Date.now() - when.getTime()) / 1000))
  if (secs < 5) return "just now"
  if (secs < 60) return `${secs}s ago`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  return `${hrs}h ago`
}

export default function FocusEditorPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  const tierParam = searchParams.get("tier")
  const tier: Tier = tierParam === "2" ? "2" : "1"
  const selectedCoreId = searchParams.get("core")
  const selectedTemplateId = searchParams.get("template")
  const returnTo = searchParams.get("return_to")

  const [isDirty, setIsDirty] = React.useState(false)
  const [lastSavedAt, setLastSavedAt] = React.useState<Date | null>(null)
  // Sub-arc C-2.2c — inherited core lineage chrome for Tier 2.
  const [inheritedCoreLineage, setInheritedCoreLineage] =
    React.useState<InheritedCoreLineage | null>(null)
  // Sub-arc C-2.3 — controlled side-panel state. Lifted from the
  // Tier 2 editor so the lineage chrome in the top bar (this file)
  // can open the same panel the canvas placement opens. Single
  // source of truth prevents desync between the two trigger sites.
  const [inheritedCorePanelOpen, setInheritedCorePanelOpen] =
    React.useState(false)

  // Reset lineage when switching tiers; lineage is Tier-2-only.
  React.useEffect(() => {
    if (tierParam !== "2") {
      setInheritedCoreLineage(null)
      setInheritedCorePanelOpen(false)
    }
  }, [tierParam])

  // Close the inherited-core panel when the user switches templates;
  // its scope is the currently-loaded template.
  React.useEffect(() => {
    setInheritedCorePanelOpen(false)
  }, [selectedTemplateId])

  // Browser confirm-before-leave when dirty.
  React.useEffect(() => {
    if (!isDirty) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ""
    }
    window.addEventListener("beforeunload", handler)
    return () => window.removeEventListener("beforeunload", handler)
  }, [isDirty])

  const switchTier = (next: Tier) => {
    const params = new URLSearchParams(searchParams)
    params.set("tier", next)
    // Switching tiers strips the OTHER tier's selection param —
    // selections are tier-scoped and meaningless across tier
    // boundaries.
    if (next === "2") params.delete("core")
    else params.delete("template")
    setSearchParams(params, { replace: true })
  }

  const setSelectedCore = React.useCallback(
    (id: string | null) => {
      const params = new URLSearchParams(searchParams)
      if (id) params.set("core", id)
      else params.delete("core")
      setSearchParams(params, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const setSelectedTemplate = React.useCallback(
    (id: string | null) => {
      const params = new URLSearchParams(searchParams)
      if (id) params.set("template", id)
      else params.delete("template")
      setSearchParams(params, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  // Sub-arc C-2.3 — URL-handling consolidation. The Tier 2 editor
  // previously read+wrote useSearchParams itself to navigate to a
  // Tier 1 core. The canonical owner of the URL is this page; the
  // editor now invokes this callback. Preserves any return_to so
  // the runtime-editor back-link chain stays intact.
  const navigateToTier1Core = React.useCallback(
    (coreId: string) => {
      const params = new URLSearchParams(searchParams)
      params.set("tier", "1")
      params.set("core", coreId)
      params.delete("template")
      setSearchParams(params, { replace: false })
    },
    [searchParams, setSearchParams],
  )

  // Force-refresh the "Auto-saved Xs ago" label every 5 seconds so
  // the readout doesn't go stale between actual saves.
  const [, forceRender] = React.useReducer((n: number) => n + 1, 0)
  React.useEffect(() => {
    if (!lastSavedAt) return
    const t = setInterval(forceRender, 5000)
    return () => clearInterval(t)
  }, [lastSavedAt])

  return (
    <div
      data-testid="focus-editor-page"
      data-focus-editor-root="true"
      className="flex h-full min-h-[calc(100vh-4rem)] w-full flex-col bg-[color:var(--surface-base)]"
    >
      {/* focus-editor testid carries the canonical wrapper contract
          from the prior page — Studio rail adaptation tests assert
          this id is present regardless of which tier body mounts. */}
      <div data-testid="focus-editor" className="hidden" aria-hidden />
      {/* F-5 coexistence deprecation banner — points operators at the
          new Focus Builder at /studio/builder/focuses. Dismissible
          per-session via localStorage. Forward-only — only on this
          legacy route; the new Focus Builder route renders nothing. */}
      <CoexistenceDeprecationBanner linkHref={adminPath("studio/builder/focuses")} />
      {/* Top bar */}
      <header
        data-testid="focus-editor-top-bar"
        className="flex items-center gap-3 border-b border-[color:var(--border-subtle)] bg-[color:var(--surface-base)] px-4 py-2"
        style={{ fontFamily: "var(--font-plex-sans)" }}
      >
        {returnTo && (
          <Button
            variant="ghost"
            size="sm"
            data-testid="focus-editor-return-to"
            onClick={() => navigate(decodeURIComponent(returnTo))}
            className="gap-1"
          >
            <ArrowLeft className="h-3 w-3" />
            Back
          </Button>
        )}

        {/* Tier toggle (segmented control). */}
        <div
          role="tablist"
          aria-label="Focus tier"
          data-testid="focus-tier-toggle"
          className="flex rounded-md border border-[color:var(--border-base)] bg-[color:var(--surface-raised)] p-0.5"
        >
          <TierButton
            tier="1"
            active={tier === "1"}
            label="Tier 1 cores"
            onClick={() => switchTier("1")}
          />
          <TierButton
            tier="2"
            active={tier === "2"}
            label="Tier 2 templates"
            onClick={() => switchTier("2")}
          />
        </div>

        <h1
          className="text-[14px] font-medium text-[color:var(--content-strong)]"
          data-testid="focus-editor-title"
        >
          Focuses
        </h1>

        {/* Sub-arc C-2.3 — tier indicator pill. Brass-toned chip next
            to the editor display name. Hidden when no selection is
            active so the chrome only appears when there's a target
            to attribute the tier to. */}
        {((tier === "1" && selectedCoreId) ||
          (tier === "2" && selectedTemplateId)) && (
          <span
            data-testid="tier-indicator-pill"
            data-tier={tier}
            className="rounded-sm bg-[color:var(--accent-subtle)] px-2 py-0.5 text-[10px] tracking-wide text-[color:var(--accent)]"
            style={{ fontFamily: "var(--font-plex-mono)" }}
          >
            Tier {tier}
          </span>
        )}

        <div className="flex flex-1 items-center gap-2">
          {/* Sub-arc C-2.3 — interactive lineage chrome. The Tier 2
              "Inherits from: X" indicator becomes a button that opens
              the same inherited-core inspector panel as the canvas
              placement click (locked decision #15). Dirty-state
              confirm-before-leave flow lives inside the panel itself
              (C-2.2c) — no extra guard needed here. */}
          {tier === "2" && inheritedCoreLineage && (
            <button
              type="button"
              data-testid="tier2-lineage-chrome"
              onClick={() => setInheritedCorePanelOpen(true)}
              className="cursor-pointer rounded-sm border border-transparent px-1 py-0.5 text-[11px] text-[color:var(--content-muted)] transition-colors hover:border-[color:var(--accent-subtle)] hover:bg-[color:var(--accent-subtle)] hover:text-[color:var(--content-base)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[color:var(--accent)]"
              style={{ fontFamily: "var(--font-plex-mono)" }}
              title="Inspect inherited Tier 1 core"
            >
              Inherits from: {inheritedCoreLineage.display_name} (Tier 1 v
              {inheritedCoreLineage.version})
            </button>
          )}
          {isDirty && (
            <span
              data-testid="dirty-indicator"
              className="flex items-center gap-1.5 text-[11px] text-[color:var(--accent)]"
              aria-label="Unsaved changes"
            >
              <Circle className="h-2 w-2 fill-[color:var(--accent)] text-[color:var(--accent)]" />
              Unsaved
            </span>
          )}
          {!isDirty && lastSavedAt && (
            <span
              data-testid="last-saved-indicator"
              className="text-[11px] text-[color:var(--content-muted)]"
            >
              Auto-saved {relativeTime(lastSavedAt)}
            </span>
          )}
        </div>
      </header>

      {/* Tier body */}
      {tier === "1" ? (
        <Tier1CoresEditor
          selectedCoreId={selectedCoreId}
          onSelectCore={setSelectedCore}
          onDirtyChange={setIsDirty}
          onLastSavedChange={setLastSavedAt}
        />
      ) : (
        <Tier2TemplatesEditor
          selectedTemplateId={selectedTemplateId}
          onSelectTemplate={setSelectedTemplate}
          onDirtyChange={setIsDirty}
          onLastSavedChange={setLastSavedAt}
          onInheritedCoreChange={setInheritedCoreLineage}
          onNavigateToTier1Core={navigateToTier1Core}
          inheritedCorePanelOpen={inheritedCorePanelOpen}
          onInheritedCorePanelOpenChange={setInheritedCorePanelOpen}
        />
      )}
    </div>
  )
}

interface TierButtonProps {
  tier: Tier
  active: boolean
  label: string
  onClick: () => void
}

function TierButton({ tier, active, label, onClick }: TierButtonProps) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      data-testid={`tier-toggle-${tier}`}
      data-active={active ? "true" : "false"}
      onClick={onClick}
      className={`rounded-[5px] px-3 py-1 text-[12px] font-medium transition-colors ${
        active
          ? "bg-[color:var(--accent)] text-[color:var(--content-on-accent)] shadow-sm"
          : "text-[color:var(--content-muted)] hover:text-[color:var(--content-base)]"
      }`}
    >
      {label}
    </button>
  )
}

// Tier2Placeholder was replaced by <Tier2TemplatesEditor /> in
// sub-arc C-2.2a — the READ-ONLY canvas seam now mounts directly.
// Three-section inspector lands in C-2.2b; create flow in C-2.2c.
