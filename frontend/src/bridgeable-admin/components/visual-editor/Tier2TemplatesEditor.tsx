/**
 * Tier2TemplatesEditor — Tier 2 Focus Template authoring surface.
 *
 * Sub-arc C-2.2a shipped the read-only canvas seam (3-column layout +
 * substrate/typography/chrome cascade preview). Sub-arc C-2.2b
 * (THIS arc) wires the editable three-section inspector:
 *
 *   ┌─ Browser ──┬─ Preview canvas ─────────────┬─ Inspector ─────┐
 *   │ Tier 2     │ Substrate gradient backdrop  │ Chrome          │
 *   │ templates  │  card (chrome composition,   │ Substrate       │
 *   │ list       │   typography defaults)       │ Typography      │
 *   └────────────┴──────────────────────────────┴─────────────────┘
 *
 * Inspector composition (top→bottom): Chrome → Substrate →
 * Typography. Each section reads/writes via useFocusTemplateDraft
 * (300ms debounced auto-save mirrors useFocusCoreDraft). As the
 * operator scrubs any value, the canvas updates live — both the
 * inspector and the canvas read from the same hook state. Per locked
 * decision #1 the section order is canonical.
 *
 * C-2.2c will ship the create-from-Core modal and the polished
 * inherited-core lineage panel. C-2.3 lifts the minimal lineage hint
 * captions on each section into proper inheritance chrome.
 */
import * as React from "react"

import { Button } from "@/components/ui/button"
import { Loader2, ArrowLeftRight } from "lucide-react"
import {
  focusCoresService,
  type CoreRecord,
} from "@/bridgeable-admin/services/focus-cores-service"
import {
  focusTemplatesService,
  type TemplateRecord,
  type ResolveSources,
} from "@/bridgeable-admin/services/focus-templates-service"
import type { PropertyRowInheritance } from "@/bridgeable-admin/components/visual-authoring/PropertyPanel"
import { CreateTierTwoTemplateModal } from "./CreateTierTwoTemplateModal"
import { InheritedCoreInspectorPanel } from "./InheritedCoreInspectorPanel"
import { adminApi } from "@/bridgeable-admin/lib/admin-api"
import { useStudioRail } from "@/bridgeable-admin/components/studio/StudioRailContext"
import { resolveEffectiveTokens } from "@/lib/visual-editor/themes/resolve-effective-tokens"
import { BASE_TOKENS } from "@/lib/visual-editor/themes/base-tokens"
import {
  expandPreset,
  mergeChromeWithOverrides,
  resolveChromeStyle,
} from "@/bridgeable-admin/lib/visual-editor/chrome-resolver"
import {
  expandSubstratePreset,
  resolveSubstrateStyle,
  substrateViewFromBlob,
  type SubstratePreset,
} from "@/bridgeable-admin/lib/visual-editor/substrate-resolver"
import {
  expandTypographyPreset,
  resolveTypographyBodyStyle,
  resolveTypographyHeadingStyle,
  typographyViewFromBlob,
  type TypographyPreset,
} from "@/bridgeable-admin/lib/visual-editor/typography-resolver"
import {
  ChromePresetPicker,
  PropertyPanel,
  PropertyRow,
  PropertySection,
  ScrubbableButton,
  SubstratePresetPicker,
  TokenSwatchPicker,
  TypographyPresetPicker,
  type PresetSlug,
  type SubstratePresetSlug,
  type TypographyPresetSlug,
} from "@/bridgeable-admin/components/visual-authoring"
import { useFocusTemplateDraft } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

interface ResolvedThemeResponse {
  tokens?: Record<string, string>
  resolved?: Record<string, string>
}

export interface InheritedCoreLineage {
  display_name: string
  core_slug: string
  version: number
}

export interface Tier2TemplatesEditorProps {
  /** Currently selected template id, or null = empty/landing state. */
  selectedTemplateId: string | null
  /** Setter for the selected template id (URL-synchronizable). */
  onSelectTemplate: (id: string | null) => void
  /** Surfaces dirty state up to the parent top bar. */
  onDirtyChange?: (dirty: boolean) => void
  /** Surfaces last-saved timestamp up to the parent. */
  onLastSavedChange?: (when: Date | null) => void
  /**
   * Sub-arc C-2.2c — surfaces the loaded template's inherited Tier 1
   * core (display_name + slug + version) up to the parent so the
   * FocusEditorPage top bar can render the "Inherits from:" lineage
   * chrome. Null when no template is loaded or the inherited core
   * couldn't be resolved.
   */
  onInheritedCoreChange?: (lineage: InheritedCoreLineage | null) => void
  /**
   * Studio's currently-active vertical slug (or null = Platform
   * scope). Forwarded to CreateTierTwoTemplateModal so it can default
   * the scope + vertical fields to match the operator's Studio context.
   */
  defaultVertical?: string | null
  /**
   * Sub-arc C-2.3 — navigate to the Tier 1 editor with `coreId`
   * preselected. Lifted from this editor's local useSearchParams
   * handler up to FocusEditorPage (the canonical URL owner per the
   * C-2.3 consolidation). The previous in-editor implementation read
   * + wrote the location bar directly; the parent now owns it.
   */
  onNavigateToTier1Core?: (coreId: string) => void
  /**
   * Sub-arc C-2.3 — controlled side-panel state lifted to the parent
   * so the FocusEditorPage top-bar lineage chrome can open the panel
   * (same panel as the canvas placement click).
   */
  inheritedCorePanelOpen?: boolean
  onInheritedCorePanelOpenChange?: (open: boolean) => void
}

export function Tier2TemplatesEditor({
  selectedTemplateId,
  onSelectTemplate,
  onDirtyChange,
  onLastSavedChange,
  onInheritedCoreChange,
  defaultVertical,
  onNavigateToTier1Core,
  inheritedCorePanelOpen: controlledPanelOpen,
  onInheritedCorePanelOpenChange,
}: Tier2TemplatesEditorProps) {
  const [templates, setTemplates] = React.useState<TemplateRecord[]>([])
  const [listLoading, setListLoading] = React.useState(true)
  const [listError, setListError] = React.useState<string | null>(null)
  const [themeTokens, setThemeTokens] = React.useState<Record<string, string>>({
    ...BASE_TOKENS.light,
  })
  const [coreChrome, setCoreChrome] = React.useState<
    Record<string, unknown> | null
  >(null)
  const [coreSlug, setCoreSlug] = React.useState<string | null>(null)
  // Full inherited core record for the InheritedCoreInspectorPanel.
  // Loaded lazily alongside coreChrome / coreSlug from the same fetch.
  const [inheritedCore, setInheritedCore] = React.useState<CoreRecord | null>(
    null,
  )
  // Sub-arc C-2.2c: modal + side-panel state.
  // Sub-arc C-2.3: panel state may be lifted to the parent (controlled
  // mode) so the FocusEditorPage lineage chrome can open it. Falls
  // back to local uncontrolled state when no controller is wired —
  // preserves the C-2.2c canvas-placement-click behavior in isolation.
  const [createModalOpen, setCreateModalOpen] = React.useState(false)
  const [uncontrolledPanelOpen, setUncontrolledPanelOpen] =
    React.useState(false)
  const inheritedCorePanelOpen =
    controlledPanelOpen ?? uncontrolledPanelOpen
  const setInheritedCorePanelOpen = React.useCallback(
    (open: boolean) => {
      if (onInheritedCorePanelOpenChange) {
        onInheritedCorePanelOpenChange(open)
      } else {
        setUncontrolledPanelOpen(open)
      }
    },
    [onInheritedCorePanelOpenChange],
  )

  const { railExpanded, inStudioContext } = useStudioRail()
  const hideLeftBrowser = railExpanded && inStudioContext

  // The C-2.2b editable hook. Replaces C-2.2a's component-local
  // template state — the canvas now reads from the draft so live
  // cascade is "free" (no separate wiring beyond hook membership).
  const {
    template,
    chromeOverridesDraft,
    substrateDraft,
    typographyDraft,
    updateChromeOverrides,
    updateSubstrate,
    updateTypography,
    resetChromeOverridesField,
    resetSubstrateField,
    resetTypographyField,
    save: saveDraft,
    discard: discardDraft,
    isDirty,
    lastSavedAt,
    isLoading: templateLoading,
    error: templateError,
  } = useFocusTemplateDraft(selectedTemplateId)

  // Sub-arc C-2.3 — resolver-driven inheritance provenance. The
  // resolver returns per-field {tier1|tier2|tier3|null} for each of
  // chrome / substrate / typography. Refetched whenever the saved
  // template version changes (i.e. after a save round-trip) so
  // operator-authored explicit values transition from "tier1
  // inherited" → "tier2 explicit" without operator action.
  const [sources, setSources] = React.useState<ResolveSources | null>(null)
  React.useEffect(() => {
    if (!template?.template_slug) {
      setSources(null)
      return
    }
    // Defensive: some test fixtures stub the templates service without
    // a `resolve` method. The inheritance chrome is a best-effort
    // overlay — fall back to null sources when the call isn't wired.
    if (typeof focusTemplatesService.resolve !== "function") {
      setSources(null)
      return
    }
    let cancelled = false
    focusTemplatesService
      .resolve({
        template_slug: template.template_slug,
        vertical: template.vertical ?? null,
      })
      .then((resp) => {
        if (cancelled) return
        setSources(resp.sources)
      })
      .catch(() => {
        if (!cancelled) setSources(null)
      })
    return () => {
      cancelled = true
    }
  }, [
    template?.template_slug,
    template?.vertical,
    template?.version,
  ])

  // Surface dirty + last-saved up to the parent (FocusEditorPage's
  // top bar renders the indicator).
  React.useEffect(() => {
    onDirtyChange?.(isDirty)
  }, [isDirty, onDirtyChange])
  React.useEffect(() => {
    onLastSavedChange?.(lastSavedAt)
  }, [lastSavedAt, onLastSavedChange])

  // Theme tokens (one-shot fetch with graceful fallback).
  React.useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await adminApi.get<ResolvedThemeResponse>(
          "/api/platform/admin/visual-editor/themes/resolve",
          { params: { mode: "light" } },
        )
        if (cancelled) return
        const overrides = res.data.tokens ?? res.data.resolved ?? {}
        setThemeTokens(resolveEffectiveTokens("light", overrides))
      } catch {
        if (!cancelled) setThemeTokens(resolveEffectiveTokens("light", {}))
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  const refreshList = React.useCallback(async () => {
    setListLoading(true)
    setListError(null)
    try {
      const records = await focusTemplatesService.list()
      setTemplates(Array.isArray(records) ? records : [])
    } catch (err) {
      setListError(
        err instanceof Error ? err.message : "Failed to load templates",
      )
    } finally {
      setListLoading(false)
    }
  }, [])

  React.useEffect(() => {
    void refreshList()
  }, [refreshList])

  // Fetch the inherited core's chrome (for cascade preview + lineage
  // hint). Best-effort — failure doesn't block the preview.
  React.useEffect(() => {
    if (!template?.inherits_from_core_id) {
      setCoreChrome(null)
      setCoreSlug(null)
      setInheritedCore(null)
      onInheritedCoreChange?.(null)
      return
    }
    let cancelled = false
    focusCoresService
      .get(template.inherits_from_core_id)
      .then((core) => {
        if (cancelled) return
        setCoreChrome(core.chrome ?? null)
        setCoreSlug(core.core_slug ?? null)
        setInheritedCore(core)
        onInheritedCoreChange?.({
          display_name: core.display_name,
          core_slug: core.core_slug,
          version:
            template.inherits_from_core_version ?? core.version ?? 1,
        })
      })
      .catch(() => {
        if (!cancelled) {
          setCoreChrome(null)
          setCoreSlug(null)
          setInheritedCore(null)
          onInheritedCoreChange?.(null)
        }
      })
    return () => {
      cancelled = true
    }
  }, [
    template?.inherits_from_core_id,
    template?.inherits_from_core_version,
    onInheritedCoreChange,
  ])

  // Compose the chrome / substrate / typography views FROM THE DRAFT
  // (not from `template.<blob>`). This is what makes the canvas live
  // cascade: every updateX flows draft → view → resolved style →
  // applied DOM in the same React render.
  const chromeView = React.useMemo(
    () => expandPreset(mergeChromeWithOverrides(coreChrome, chromeOverridesDraft)),
    [coreChrome, chromeOverridesDraft],
  )
  const substrateView = React.useMemo(
    () => expandSubstratePreset(substrateViewFromBlob(substrateDraft)),
    [substrateDraft],
  )
  const typographyView = React.useMemo(
    () => expandTypographyPreset(typographyViewFromBlob(typographyDraft)),
    [typographyDraft],
  )

  const substrateStyle = React.useMemo(
    () => resolveSubstrateStyle(substrateView, themeTokens),
    [substrateView, themeTokens],
  )
  const cardStyle = React.useMemo(
    () => resolveChromeStyle(chromeView, themeTokens),
    [chromeView, themeTokens],
  )
  const headingStyle = React.useMemo(
    () => resolveTypographyHeadingStyle(typographyView, themeTokens),
    [typographyView, themeTokens],
  )
  const bodyStyle = React.useMemo(
    () => resolveTypographyBodyStyle(typographyView, themeTokens),
    [typographyView, themeTokens],
  )

  const canvasStyle = React.useMemo<React.CSSProperties>(
    () => ({
      ...substrateStyle,
      ["--tier2-heading-weight" as string]: String(
        typographyView.heading_weight ?? 500,
      ),
      ["--tier2-body-weight" as string]: String(
        typographyView.body_weight ?? 400,
      ),
      ["--tier2-heading-color" as string]:
        (typographyView.heading_color_token &&
          themeTokens[typographyView.heading_color_token]) ||
        "var(--content-strong)",
      ["--tier2-body-color" as string]:
        (typographyView.body_color_token &&
          themeTokens[typographyView.body_color_token]) ||
        "var(--content-base)",
    }),
    [substrateStyle, typographyView, themeTokens],
  )

  // Sub-arc C-2.3 — URL handling lives at FocusEditorPage now.
  // `onNavigateToTier1Core` is invoked from the inherited-core
  // inspector's "Edit core in Tier 1" path; the parent rewrites the
  // URL + preserves return_to.
  const handleNavigateToTier1Core = React.useCallback(
    (coreId: string) => {
      onNavigateToTier1Core?.(coreId)
    },
    [onNavigateToTier1Core],
  )

  // Sub-arc C-2.3 — map the resolver's per-field tier string to a
  // PropertyRowInheritance value. Resolver vocabulary:
  //   "tier1" → inherited from the Tier 1 core (chrome only)
  //   "tier2" → explicit at the current tier (Tier 2 template)
  //   "tier3" → would be a Tier 3 composition delta; in this editor's
  //             context (Tier 2 authoring with no Tier 3 in scope) we
  //             treat it as explicit at the current resolve view.
  //   null    → no value at any tier; row is neutral (no decoration).
  const chromeInheritanceFor = React.useCallback(
    (field: string): PropertyRowInheritance => {
      const tier = sources?.chrome_sources?.[field]
      if (tier === "tier1") return { tier: "Tier 1 core" }
      if (tier === "tier2" || tier === "tier3") return "explicit"
      return null
    },
    [sources],
  )
  // Substrate / typography do not cascade from Tier 1 (cores are
  // substrate/typography-free by design — see resolver.py). The only
  // observable states are "tier2" (explicit) or null (unset). No
  // inherited-from-parent indicator applies here, but the explicit
  // signal still drives the reset ↺ affordance per locked decisions.
  const substrateInheritanceFor = React.useCallback(
    (field: string): PropertyRowInheritance => {
      const tier = sources?.substrate_sources?.[field]
      if (tier === "tier2" || tier === "tier3") return "explicit"
      return null
    },
    [sources],
  )
  const typographyInheritanceFor = React.useCallback(
    (field: string): PropertyRowInheritance => {
      const tier = sources?.typography_sources?.[field]
      if (tier === "tier2" || tier === "tier3") return "explicit"
      return null
    },
    [sources],
  )

  // Inheritance lineage strings rendered in each section's header.
  // Minimal v1 per locked decision #6 — C-2.3 ships polished UI.
  const chromeLineage = coreSlug
    ? `cascading from: ${coreSlug} (Tier 1${
        template?.inherits_from_core_version
          ? ` v${template.inherits_from_core_version}`
          : ""
      })`
    : "Tier 2 override"
  const substrateLineage = "Focus-level (Tier 2 default)"
  const typographyLineage = "Focus-level (Tier 2 default)"

  return (
    <div className="relative flex h-full flex-1 overflow-hidden">
      {/* LEFT — templates browser */}
      {!hideLeftBrowser && (
        <aside
          data-testid="focus-editor-browser"
          data-tier2-templates-browser="true"
          className="flex w-[320px] shrink-0 flex-col border-r border-[color:var(--border-subtle)] bg-[color:var(--surface-sunken)]"
        >
          <header className="flex items-center justify-between border-b border-[color:var(--border-subtle)] px-3 py-2">
            <span
              className="text-[11px] font-medium uppercase tracking-wide text-[color:var(--content-muted)]"
              style={{ fontFamily: "var(--font-plex-sans)" }}
            >
              Focus Templates
            </span>
            <Button
              size="sm"
              variant="outline"
              data-testid="new-template-button"
              onClick={() => setCreateModalOpen(true)}
              className="h-7 gap-1 px-2 text-[12px]"
            >
              + New
            </Button>
          </header>

          <div className="flex-1 overflow-y-auto">
            {listLoading && (
              <div
                data-testid="templates-loading"
                className="flex items-center justify-center p-4 text-[12px] text-[color:var(--content-muted)]"
              >
                <Loader2 className="mr-2 h-3 w-3 animate-spin" /> Loading
                templates…
              </div>
            )}
            {listError && (
              <div
                role="alert"
                data-testid="templates-error"
                className="m-3 rounded-md border border-[color:var(--status-error)] bg-[color:var(--status-error-muted)] px-3 py-2 text-[12px] text-[color:var(--status-error)]"
              >
                {listError}
              </div>
            )}
            {!listLoading && !listError && templates.length === 0 && (
              <div
                data-testid="templates-empty"
                className="m-3 rounded-md border border-dashed border-[color:var(--border-subtle)] p-4 text-center text-[12px] text-[color:var(--content-muted)]"
              >
                No Tier 2 templates yet. The create-from-Core flow ships
                in sub-arc C-2.2c.
              </div>
            )}
            <ul className="flex flex-col" data-testid="templates-list">
              {templates
                .filter((t) => t.is_active)
                .sort((a, b) => a.display_name.localeCompare(b.display_name))
                .map((t) => {
                  const selected = t.id === selectedTemplateId
                  return (
                    <li key={t.id}>
                      <button
                        type="button"
                        data-testid={`template-row-${t.template_slug}`}
                        data-selected={selected ? "true" : "false"}
                        onClick={() => onSelectTemplate(t.id)}
                        className={`flex w-full flex-col items-start gap-0.5 border-b border-[color:var(--border-subtle)] px-3 py-2 text-left transition-colors ${
                          selected
                            ? "bg-[color:var(--accent-subtle)] border-l-2 border-l-[color:var(--accent)]"
                            : "hover:bg-[color:var(--accent-subtle)]/50"
                        }`}
                        style={{ fontFamily: "var(--font-plex-sans)" }}
                      >
                        <span className="text-[13px] font-medium text-[color:var(--content-strong)]">
                          {t.display_name}
                        </span>
                        <span className="text-[11px] text-[color:var(--content-muted)] font-mono">
                          {t.scope}
                          {t.vertical ? ` · ${t.vertical}` : ""} · v{t.version}
                        </span>
                      </button>
                    </li>
                  )
                })}
            </ul>
          </div>
        </aside>
      )}

      {/* CENTER — preview canvas. `tier2-canvas` is the canonical
          C-2.2a.1 testid; `tier2-preview` is retained for transitional
          continuity. */}
      <section
        data-testid="tier2-canvas"
        data-tier2-preview="true"
        className="relative flex flex-1 overflow-hidden"
        style={canvasStyle}
      >
        <div className="relative flex h-full flex-1 items-center justify-center p-12">
          {!selectedTemplateId ? (
            <div
              data-testid="tier2-no-selection"
              className="rounded-lg bg-[color:var(--surface-elevated)]/90 p-6 text-center text-[13px] text-[color:var(--content-muted)] shadow-[var(--shadow-level-1)]"
            >
              {templates.length === 0
                ? "No templates yet — the create flow ships in sub-arc C-2.2c."
                : "Select a Tier 2 template on the left to preview its composition."}
            </div>
          ) : templateLoading ? (
            <div className="text-[13px] text-[color:var(--content-base)]">
              <Loader2 className="inline-block h-4 w-4 animate-spin" />{" "}
              Loading…
            </div>
          ) : templateError ? (
            <div
              role="alert"
              data-testid="tier2-load-error"
              className="rounded-md border border-[color:var(--status-error)] bg-[color:var(--status-error-muted)] px-3 py-2 text-[12px] text-[color:var(--status-error)]"
            >
              {templateError}
            </div>
          ) : (
            <div
              data-testid="tier2-preview-card"
              style={{ ...cardStyle, width: "min(440px, 80%)", minHeight: 200 }}
              className="flex flex-col gap-2"
            >
              <span
                className="text-[10px] uppercase tracking-[0.08em] text-[color:var(--content-muted)]"
                style={{ fontFamily: "var(--font-plex-sans)" }}
              >
                {template?.template_slug ?? "—"}
              </span>
              <h2 className="text-[20px]" style={headingStyle}>
                {template?.display_name ?? "Focus Template"}
              </h2>
              <p className="text-[13px] leading-relaxed" style={bodyStyle}>
                {template?.description ??
                  "Tier 2 template preview. Edit chrome, substrate, or typography on the right; the canvas updates live."}
              </p>
              <button
                type="button"
                data-testid="inherited-core-placement"
                onClick={() => setInheritedCorePanelOpen(true)}
                disabled={!inheritedCore}
                className="mt-2 cursor-pointer rounded-sm border border-transparent px-1 py-0.5 text-left text-[11px] tabular-nums text-[color:var(--content-muted)] transition-colors hover:border-[color:var(--accent-subtle)] hover:bg-[color:var(--accent-subtle)] disabled:cursor-default disabled:hover:border-transparent disabled:hover:bg-transparent"
                style={{ fontFamily: "var(--font-plex-mono)" }}
                title={
                  inheritedCore
                    ? "Inspect inherited Tier 1 core"
                    : "Loading inherited core…"
                }
              >
                inherits: {coreSlug ?? template?.inherits_from_core_id?.slice(0, 8) ?? "—"}{" "}
                · v{template?.inherits_from_core_version ?? "—"}
                {" · "}
                chrome: {chromeView.preset ?? "—"}
                {" · "}
                substrate: {substrateView.preset ?? "—"}
                {" · "}
                typography: {typographyView.preset ?? "—"}
              </button>
            </div>
          )}
        </div>
      </section>

      {/* RIGHT — three-section inspector. */}
      <aside
        data-testid="tier2-inspector"
        className="w-[340px] shrink-0 overflow-y-auto border-l border-[color:var(--border-subtle)] bg-[color:var(--surface-sunken)]"
      >
        {!selectedTemplateId ? (
          <div
            data-testid="tier2-inspector-empty"
            className="flex h-full items-center justify-center p-6 text-center text-[12px] text-[color:var(--content-muted)]"
            style={{ fontFamily: "var(--font-plex-sans)" }}
          >
            <span>
              <ArrowLeftRight className="mx-auto mb-2 h-4 w-4" />
              Select a template to edit its chrome / substrate / typography.
            </span>
          </div>
        ) : (
          <PropertyPanel>
            {/* CHROME — cascaded on top of inherited core's chrome. */}
            <PropertySection
              title="Chrome"
              lineageHint={chromeLineage}
              defaultExpanded
            >
              <PropertyRow
                inheritanceSource={chromeInheritanceFor("preset")}
                onReset={() => resetChromeOverridesField("preset")}
              >
                <ChromePresetPicker
                  value={(chromeView.preset ?? null) as PresetSlug | null}
                  onChange={(p) =>
                    updateChromeOverrides({
                      preset: p as PresetSlug | null,
                    })
                  }
                />
              </PropertyRow>
              <PropertyRow
                inheritanceSource={chromeInheritanceFor("elevation")}
                onReset={() => resetChromeOverridesField("elevation")}
              >
                <ScrubbableButton
                  value={chromeView.elevation ?? 0}
                  min={0}
                  max={100}
                  label="Elevation"
                  onChange={(v) => updateChromeOverrides({ elevation: v })}
                />
              </PropertyRow>
              <PropertyRow
                inheritanceSource={chromeInheritanceFor("corner_radius")}
                onReset={() => resetChromeOverridesField("corner_radius")}
              >
                <ScrubbableButton
                  value={chromeView.corner_radius ?? 0}
                  min={0}
                  max={100}
                  label="Corner radius"
                  onChange={(v) =>
                    updateChromeOverrides({ corner_radius: v })
                  }
                />
              </PropertyRow>
              <PropertyRow
                inheritanceSource={chromeInheritanceFor("backdrop_blur")}
                onReset={() => resetChromeOverridesField("backdrop_blur")}
              >
                <ScrubbableButton
                  value={chromeView.backdrop_blur ?? 0}
                  min={0}
                  max={100}
                  label="Backdrop blur"
                  onChange={(v) =>
                    updateChromeOverrides({ backdrop_blur: v })
                  }
                />
              </PropertyRow>
              <PropertyRow
                inheritanceSource={chromeInheritanceFor("background_token")}
                onReset={() => resetChromeOverridesField("background_token")}
              >
                <TokenSwatchPicker
                  value={chromeView.background_token ?? null}
                  tokenFamily="surface"
                  themeTokens={themeTokens}
                  onChange={(t) =>
                    updateChromeOverrides({ background_token: t })
                  }
                  label="Background"
                />
              </PropertyRow>
              <PropertyRow
                inheritanceSource={chromeInheritanceFor("border_token")}
                onReset={() => resetChromeOverridesField("border_token")}
              >
                <TokenSwatchPicker
                  value={chromeView.border_token ?? null}
                  tokenFamily="border"
                  themeTokens={themeTokens}
                  onChange={(t) => updateChromeOverrides({ border_token: t })}
                  label="Border"
                />
              </PropertyRow>
              <PropertyRow
                inheritanceSource={chromeInheritanceFor("padding_token")}
                onReset={() => resetChromeOverridesField("padding_token")}
              >
                <TokenSwatchPicker
                  value={chromeView.padding_token ?? null}
                  tokenFamily="padding"
                  themeTokens={themeTokens}
                  onChange={(t) => updateChromeOverrides({ padding_token: t })}
                  label="Padding"
                />
              </PropertyRow>
            </PropertySection>

            {/* SUBSTRATE — Focus-scope page-background atmospheric tier. */}
            <PropertySection
              title="Substrate"
              lineageHint={substrateLineage}
              defaultExpanded
            >
              <PropertyRow
                inheritanceSource={substrateInheritanceFor("preset")}
                onReset={() => resetSubstrateField("preset")}
              >
                <SubstratePresetPicker
                  value={
                    (substrateView.preset ??
                      null) as SubstratePresetSlug | null
                  }
                  onChange={(p) =>
                    updateSubstrate({
                      preset: p as SubstratePreset | null,
                    })
                  }
                />
              </PropertyRow>
              <PropertyRow
                inheritanceSource={substrateInheritanceFor("intensity")}
                onReset={() => resetSubstrateField("intensity")}
              >
                <ScrubbableButton
                  value={substrateView.intensity ?? 0}
                  min={0}
                  max={100}
                  label="Intensity"
                  onChange={(v) => updateSubstrate({ intensity: v })}
                />
              </PropertyRow>
              <PropertyRow
                inheritanceSource={substrateInheritanceFor("base_token")}
                onReset={() => resetSubstrateField("base_token")}
              >
                <TokenSwatchPicker
                  value={substrateView.base_token ?? null}
                  tokenFamily="surface"
                  themeTokens={themeTokens}
                  onChange={(t) => updateSubstrate({ base_token: t })}
                  label="Base"
                />
              </PropertyRow>
              <PropertyRow
                inheritanceSource={substrateInheritanceFor("accent_token_1")}
                onReset={() => resetSubstrateField("accent_token_1")}
              >
                <TokenSwatchPicker
                  value={substrateView.accent_token_1 ?? null}
                  tokenFamily="surface"
                  themeTokens={themeTokens}
                  onChange={(t) => updateSubstrate({ accent_token_1: t })}
                  label="Accent 1"
                />
              </PropertyRow>
              <PropertyRow
                inheritanceSource={substrateInheritanceFor("accent_token_2")}
                onReset={() => resetSubstrateField("accent_token_2")}
              >
                <TokenSwatchPicker
                  value={substrateView.accent_token_2 ?? null}
                  tokenFamily="surface"
                  themeTokens={themeTokens}
                  onChange={(t) => updateSubstrate({ accent_token_2: t })}
                  label="Accent 2"
                />
              </PropertyRow>
            </PropertySection>

            {/* TYPOGRAPHY — Focus-scope heading + body weight + color. */}
            <PropertySection
              title="Typography"
              lineageHint={typographyLineage}
              defaultExpanded
            >
              <PropertyRow
                inheritanceSource={typographyInheritanceFor("preset")}
                onReset={() => resetTypographyField("preset")}
              >
                <TypographyPresetPicker
                  value={
                    (typographyView.preset ??
                      null) as TypographyPresetSlug | null
                  }
                  onChange={(p) =>
                    updateTypography({
                      preset: p as TypographyPreset | null,
                    })
                  }
                />
              </PropertyRow>
              <PropertyRow
                inheritanceSource={typographyInheritanceFor("heading_weight")}
                onReset={() => resetTypographyField("heading_weight")}
              >
                <ScrubbableButton
                  value={typographyView.heading_weight ?? 400}
                  min={400}
                  max={900}
                  label="Heading weight"
                  onChange={(v) => updateTypography({ heading_weight: v })}
                />
              </PropertyRow>
              <PropertyRow
                inheritanceSource={typographyInheritanceFor("body_weight")}
                onReset={() => resetTypographyField("body_weight")}
              >
                <ScrubbableButton
                  value={typographyView.body_weight ?? 400}
                  min={400}
                  max={900}
                  label="Body weight"
                  onChange={(v) => updateTypography({ body_weight: v })}
                />
              </PropertyRow>
              <PropertyRow
                inheritanceSource={typographyInheritanceFor(
                  "heading_color_token",
                )}
                onReset={() => resetTypographyField("heading_color_token")}
              >
                <TokenSwatchPicker
                  value={typographyView.heading_color_token ?? null}
                  tokenFamily="surface"
                  themeTokens={themeTokens}
                  onChange={(t) =>
                    updateTypography({ heading_color_token: t })
                  }
                  label="Heading color"
                />
              </PropertyRow>
              <PropertyRow
                inheritanceSource={typographyInheritanceFor("body_color_token")}
                onReset={() => resetTypographyField("body_color_token")}
              >
                <TokenSwatchPicker
                  value={typographyView.body_color_token ?? null}
                  tokenFamily="surface"
                  themeTokens={themeTokens}
                  onChange={(t) => updateTypography({ body_color_token: t })}
                  label="Body color"
                />
              </PropertyRow>
            </PropertySection>
          </PropertyPanel>
        )}
      </aside>

      {/* Sub-arc C-2.2c — slide-in side panel for inspecting the
          inherited Tier 1 core. Overlays the inspector area; does
          NOT unmount the inspector below so Tier 2 unsaved state in
          useFocusTemplateDraft stays intact regardless of dismissal. */}
      {inheritedCorePanelOpen && selectedTemplateId && (
        <InheritedCoreInspectorPanel
          core={inheritedCore}
          isDirty={isDirty}
          saveDraft={saveDraft}
          discardDraft={discardDraft}
          onNavigateToTier1Core={(coreId) => {
            setInheritedCorePanelOpen(false)
            handleNavigateToTier1Core(coreId)
          }}
          onClose={() => setInheritedCorePanelOpen(false)}
        />
      )}

      {/* Sub-arc C-2.2c — create-from-Core modal. */}
      <CreateTierTwoTemplateModal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onCreated={(record) => {
          setCreateModalOpen(false)
          // Refresh the browser list so the new row appears, then
          // select it. URL update flows through onSelectTemplate.
          void refreshList()
          onSelectTemplate(record.id)
        }}
        defaultVertical={defaultVertical ?? null}
      />
    </div>
  )
}

export default Tier2TemplatesEditor
