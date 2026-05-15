/**
 * Tier2TemplatesEditor — Tier 2 Focus Template authoring surface
 * (sub-arc C-2.2a — READ-ONLY).
 *
 * C-2.2a ships the canvas seam: a 3-column structure that lists
 * existing Tier 2 templates, renders the resolved Focus-frame
 * composition (substrate background + typography defaults + chrome
 * cascaded from the inherited core + overrides) in a preview canvas,
 * and stubs out the inspector pane with a named placeholder pointing
 * to C-2.2b's three-section inspector + draft hook.
 *
 *   ┌─ Browser ──┬─ Preview canvas ─────────────┬─ Inspector ─────┐
 *   │ Tier 2     │ Substrate gradient backdrop  │ Three-section   │
 *   │ templates  │  card (chrome composition,   │ inspector lands │
 *   │ list       │   typography defaults)       │ in C-2.2b       │
 *   └────────────┴──────────────────────────────┴─────────────────┘
 *
 * C-2.2a is intentionally read-only. The inspector placeholder
 * mirrors the discipline from C-2.1's Tier-2 placeholder: a
 * deliberate "this exists, coming next" surface, not a 404. C-2.2b
 * wires useFocusTemplateDraft + chrome/substrate/typography inspector
 * sections; C-2.2c ships the create-from-Core modal + the inherited-
 * core inspector panel that surfaces inheritance lineage.
 */
import * as React from "react"

import { Button } from "@/components/ui/button"
import { Loader2 } from "lucide-react"
import { focusCoresService } from "@/bridgeable-admin/services/focus-cores-service"
import {
  focusTemplatesService,
  type TemplateRecord,
} from "@/bridgeable-admin/services/focus-templates-service"
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
} from "@/bridgeable-admin/lib/visual-editor/substrate-resolver"
import {
  expandTypographyPreset,
  resolveTypographyBodyStyle,
  resolveTypographyHeadingStyle,
  typographyViewFromBlob,
} from "@/bridgeable-admin/lib/visual-editor/typography-resolver"

interface ResolvedThemeResponse {
  tokens?: Record<string, string>
  resolved?: Record<string, string>
}

export interface Tier2TemplatesEditorProps {
  /** Currently selected template id, or null = empty/landing state. */
  selectedTemplateId: string | null
  /** Setter for the selected template id (URL-synchronizable). */
  onSelectTemplate: (id: string | null) => void
  /** Surfaces dirty state up to the parent top bar (always false in C-2.2a). */
  onDirtyChange?: (dirty: boolean) => void
  /** Surfaces last-saved timestamp up to the parent (null in C-2.2a). */
  onLastSavedChange?: (when: Date | null) => void
}

export function Tier2TemplatesEditor({
  selectedTemplateId,
  onSelectTemplate,
  onDirtyChange,
  onLastSavedChange,
}: Tier2TemplatesEditorProps) {
  const [templates, setTemplates] = React.useState<TemplateRecord[]>([])
  const [listLoading, setListLoading] = React.useState(true)
  const [listError, setListError] = React.useState<string | null>(null)
  const [themeTokens, setThemeTokens] = React.useState<Record<string, string>>({
    ...BASE_TOKENS.light,
  })
  const [template, setTemplate] = React.useState<TemplateRecord | null>(null)
  const [templateLoading, setTemplateLoading] = React.useState(false)
  const [templateError, setTemplateError] = React.useState<string | null>(null)
  const [coreChrome, setCoreChrome] = React.useState<
    Record<string, unknown> | null
  >(null)

  const { railExpanded, inStudioContext } = useStudioRail()
  const hideLeftBrowser = railExpanded && inStudioContext

  // C-2.2a is read-only — never report dirty / last-saved. Call the
  // callbacks once on mount to clear any stale state from the parent.
  React.useEffect(() => {
    onDirtyChange?.(false)
    onLastSavedChange?.(null)
  }, [onDirtyChange, onLastSavedChange])

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

  // Fetch selected template + its inherited core's chrome.
  React.useEffect(() => {
    if (!selectedTemplateId) {
      setTemplate(null)
      setCoreChrome(null)
      setTemplateError(null)
      return
    }
    let cancelled = false
    setTemplateLoading(true)
    setTemplateError(null)
    async function load() {
      try {
        const t = await focusTemplatesService.get(selectedTemplateId as string)
        if (cancelled) return
        setTemplate(t)
        // Fetch the inherited core in parallel (best-effort — failure
        // doesn't block the preview; we just render the override blob
        // without a base to merge onto).
        try {
          const core = await focusCoresService.get(t.inherits_from_core_id)
          if (cancelled) return
          setCoreChrome(core.chrome ?? null)
        } catch {
          if (!cancelled) setCoreChrome(null)
        }
      } catch (err) {
        if (!cancelled) {
          setTemplateError(
            err instanceof Error ? err.message : "Failed to load template",
          )
        }
      } finally {
        if (!cancelled) setTemplateLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [selectedTemplateId])

  // Compose the chrome / substrate / typography views for preview.
  const chromeView = React.useMemo(
    () =>
      expandPreset(
        mergeChromeWithOverrides(coreChrome, template?.chrome_overrides),
      ),
    [coreChrome, template?.chrome_overrides],
  )
  const substrateView = React.useMemo(
    () => expandSubstratePreset(substrateViewFromBlob(template?.substrate)),
    [template?.substrate],
  )
  const typographyView = React.useMemo(
    () => expandTypographyPreset(typographyViewFromBlob(template?.typography)),
    [template?.typography],
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

  // Canvas-wide typography exposed as CSS custom properties so any
  // inner text content (current preview card, future inherited-core
  // placement) inherits the template's typographic intent without
  // each surface re-resolving the view. Per the C-2.2a.1 locked
  // decision #2 (canvas-wide typography as CSS variables).
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

  return (
    <div className="flex h-full flex-1 overflow-hidden">
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
              disabled
              data-testid="new-template-button"
              title="Create flow ships in sub-arc C-2.2c"
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
          C-2.2a.1 testid; `tier2-preview` is retained for the C-2.2a
          tests that pre-date the rename and asserts on the same node. */}
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
              <p
                className="text-[13px] leading-relaxed"
                style={bodyStyle}
              >
                {template?.description ??
                  "Tier 2 template preview. The three-section inspector (chrome / substrate / typography) lands in sub-arc C-2.2b."}
              </p>
              <span
                className="mt-2 text-[11px] tabular-nums text-[color:var(--content-muted)]"
                style={{ fontFamily: "var(--font-plex-mono)" }}
              >
                inherits: {template?.inherits_from_core_id?.slice(0, 8) ?? "—"}{" "}
                · v{template?.inherits_from_core_version ?? "—"}
                {" · "}
                chrome: {chromeView.preset ?? "—"}
                {" · "}
                substrate: {substrateView.preset ?? "—"}
                {" · "}
                typography: {typographyView.preset ?? "—"}
              </span>
            </div>
          )}
        </div>
      </section>

      {/* RIGHT — inspector placeholder (named, intentional). */}
      <aside
        data-testid="tier2-inspector"
        className="w-[340px] shrink-0 overflow-y-auto border-l border-[color:var(--border-subtle)] bg-[color:var(--surface-sunken)]"
      >
        <div
          data-testid="tier2-inspector-placeholder"
          className="m-3 flex flex-col items-start gap-2 rounded-lg border border-dashed border-[color:var(--accent-muted)] bg-[color:var(--surface-elevated)] p-4 shadow-[var(--shadow-level-1)]"
          style={{ fontFamily: "var(--font-plex-sans)" }}
        >
          <span className="text-[11px] uppercase tracking-wide text-[color:var(--accent)]">
            Coming in sub-arc C-2.2b
          </span>
          <h3
            className="text-[14px] font-medium text-[color:var(--content-strong)]"
            style={{ fontFamily: "var(--font-plex-serif)" }}
          >
            Three-section inspector
          </h3>
          <p className="text-[12px] leading-relaxed text-[color:var(--content-muted)]">
            C-2.2b wires the chrome / substrate / typography editor
            against the live template draft. C-2.2c adds the inherited-
            core lineage panel and the create-from-Core flow.
          </p>
          <ul className="ml-4 list-disc text-[12px] text-[color:var(--content-muted)]">
            <li>Chrome overrides (override the inherited core)</li>
            <li>Substrate (B-4 page-background atmospheric tier)</li>
            <li>Typography (B-5 heading / body weight + color)</li>
          </ul>
        </div>
      </aside>
    </div>
  )
}

export default Tier2TemplatesEditor
