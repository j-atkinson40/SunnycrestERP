/**
 * Tier1CoresEditor — Tier 1 Focus Core authoring surface (sub-arc C-2.1).
 *
 * Composes:
 *   - LEFT (320px): hierarchical browser — flat list of active cores,
 *     "+ New core" CTA. Click a row → load core into editor.
 *   - CENTER: card-like preview pane rendering the core's resolved
 *     chrome against a warm-gradient backdrop (mirrors the C-1 demo's
 *     preview composition so authoring quality is consistent across
 *     internal demo + production surface).
 *   - RIGHT (340px): PropertyPanel with a single chrome PropertySection.
 *     Composes C-1 primitives — ChromePresetPicker + three
 *     ScrubbableButton sliders (elevation / corner_radius / backdrop_blur)
 *     + three TokenSwatchPicker swatch rows (background / border /
 *     padding). Identical composition to C-1's ChromePrimitivesDemoPage,
 *     wired to a real focus_cores service instead of component-local
 *     state.
 *
 * Auto-save: useFocusCoreDraft debounces save at 300ms after last
 * scrub/preset/swatch change. Dirty indicator surfaces in the parent
 * top bar via the dirty-pulse callback.
 *
 * NO inheritance surfacing (Tier 1 is cascade root; C-2.2's Tier 2
 * editor adds inherits-from-Tier-1 affordances).
 */
import * as React from "react"

import { Button } from "@/components/ui/button"
import { Loader2, Plus, ArrowLeftRight } from "lucide-react"
import {
  ChromePresetPicker,
  PropertyPanel,
  PropertyRow,
  PropertySection,
  ScrubbableButton,
  TokenSwatchPicker,
  type PresetSlug,
} from "@/bridgeable-admin/components/visual-authoring"
import {
  focusCoresService,
  type CoreRecord,
} from "@/bridgeable-admin/services/focus-cores-service"
import { useFocusCoreDraft } from "@/bridgeable-admin/hooks/useFocusCoreDraft"
import { adminApi } from "@/bridgeable-admin/lib/admin-api"
import { useStudioRail } from "@/bridgeable-admin/components/studio/StudioRailContext"
import { resolveEffectiveTokens } from "@/lib/visual-editor/themes/resolve-effective-tokens"
import { BASE_TOKENS } from "@/lib/visual-editor/themes/base-tokens"
import { CreateTierOneCoreModal } from "./CreateTierOneCoreModal"

interface ChromeView {
  preset: PresetSlug | null
  elevation: number | null
  corner_radius: number | null
  backdrop_blur: number | null
  background_token: string | null
  border_token: string | null
  padding_token: string | null
}

/** Frontend mirror of backend chrome PRESETS (sub-arc C-1 canon). */
const PRESETS: Record<PresetSlug, Partial<ChromeView>> = {
  card: {
    background_token: "surface-elevated",
    elevation: 37,
    corner_radius: 37,
    padding_token: "space-6",
  },
  modal: {
    background_token: "surface-raised",
    elevation: 62,
    corner_radius: 62,
    padding_token: "space-6",
  },
  dropdown: {
    background_token: "surface-raised",
    elevation: 62,
    corner_radius: 37,
    padding_token: "space-2",
    border_token: "border-subtle",
  },
  toast: {
    background_token: "surface-raised",
    elevation: 87,
    corner_radius: 37,
    padding_token: "space-4",
  },
  floating: {
    background_token: "surface-raised",
    elevation: 87,
    corner_radius: 62,
    padding_token: "space-4",
    border_token: "border-accent",
  },
  frosted: {
    background_token: "surface-frosted",
    elevation: 50,
    corner_radius: 62,
    padding_token: "space-6",
    backdrop_blur: 60,
    border_token: "border-subtle",
  },
  custom: {},
}

function expandPreset(chrome: ChromeView): ChromeView {
  const preset = chrome.preset
  if (!preset || preset === "custom") return chrome
  const defaults = PRESETS[preset]
  const merged: ChromeView = { ...chrome }
  for (const key of Object.keys(defaults) as (keyof ChromeView)[]) {
    if (chrome[key] === null || chrome[key] === undefined) {
      ;(merged as unknown as Record<string, unknown>)[key] = defaults[
        key
      ] as unknown
    }
  }
  return merged
}

function elevationToBoxShadow(v: number | null): string {
  if (v === null || v <= 25) return "none"
  if (v <= 50) return "0 2px 6px rgba(48, 32, 16, 0.10)"
  if (v <= 75) return "0 8px 24px rgba(48, 32, 16, 0.14)"
  return "0 16px 48px rgba(48, 32, 16, 0.20)"
}
function cornerToPx(v: number | null): number {
  if (v === null || v <= 25) return 0
  if (v <= 50) return 8
  if (v <= 75) return 14
  return 24
}
function blurToPx(v: number | null): number {
  if (v === null || v <= 25) return 0
  if (v <= 50) return 8
  if (v <= 75) return 14
  return 24
}
const PADDING_PX: Record<string, number> = {
  "space-2": 8,
  "space-4": 16,
  "space-6": 24,
  "space-8": 32,
}

interface ResolvedThemeResponse {
  tokens?: Record<string, string>
  resolved?: Record<string, string>
}

function chromeViewFromDraft(draft: Record<string, unknown>): ChromeView {
  return {
    preset: (draft.preset as PresetSlug | null | undefined) ?? null,
    elevation: (draft.elevation as number | null | undefined) ?? null,
    corner_radius: (draft.corner_radius as number | null | undefined) ?? null,
    backdrop_blur: (draft.backdrop_blur as number | null | undefined) ?? null,
    background_token:
      (draft.background_token as string | null | undefined) ?? null,
    border_token: (draft.border_token as string | null | undefined) ?? null,
    padding_token: (draft.padding_token as string | null | undefined) ?? null,
  }
}

export interface Tier1CoresEditorProps {
  /** Currently selected core id, or null = empty/landing state. */
  selectedCoreId: string | null
  /** Setter for the selected core id (URL-synchronizable). */
  onSelectCore: (id: string | null) => void
  /** Notifies parent when dirty state changes (for top-bar pulse). */
  onDirtyChange?: (dirty: boolean) => void
  /** Notifies parent when last-saved timestamp updates. */
  onLastSavedChange?: (when: Date | null) => void
}

export function Tier1CoresEditor({
  selectedCoreId,
  onSelectCore,
  onDirtyChange,
  onLastSavedChange,
}: Tier1CoresEditorProps) {
  const [cores, setCores] = React.useState<CoreRecord[]>([])
  const [listLoading, setListLoading] = React.useState(true)
  const [listError, setListError] = React.useState<string | null>(null)
  const [createOpen, setCreateOpen] = React.useState(false)
  const [themeTokens, setThemeTokens] = React.useState<Record<string, string>>({
    ...BASE_TOKENS.light,
  })

  const { railExpanded, inStudioContext } = useStudioRail()
  const hideLeftBrowser = railExpanded && inStudioContext

  const {
    core,
    draft,
    updateDraft,
    isDirty,
    isSaving,
    lastSavedAt,
    error,
    isLoading,
  } = useFocusCoreDraft(selectedCoreId)

  // Surface dirty state + last-saved upward.
  React.useEffect(() => {
    onDirtyChange?.(isDirty)
  }, [isDirty, onDirtyChange])
  React.useEffect(() => {
    onLastSavedChange?.(lastSavedAt)
  }, [lastSavedAt, onLastSavedChange])

  // Theme tokens (one-shot fetch).
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
      const records = await focusCoresService.list()
      // Defensive: studio-editor-adaptation's generic adminApi mock
      // returns `{items, rows}` for any URL it doesn't recognize. The
      // Tier 1 cores endpoint is a list-typed payload; tolerate the
      // mismatch gracefully by coercing to an empty array.
      setCores(Array.isArray(records) ? records : [])
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Failed to load cores")
    } finally {
      setListLoading(false)
    }
  }, [])

  React.useEffect(() => {
    void refreshList()
  }, [refreshList])

  const view = React.useMemo(
    () => expandPreset(chromeViewFromDraft(draft)),
    [draft],
  )

  const cardStyle: React.CSSProperties = {
    background:
      themeTokens[view.background_token ?? "surface-elevated"] ??
      "var(--surface-elevated)",
    borderRadius: cornerToPx(view.corner_radius ?? null),
    boxShadow: elevationToBoxShadow(view.elevation ?? null),
    padding: PADDING_PX[view.padding_token ?? "space-6"] ?? 24,
    border: view.border_token
      ? `1px solid ${themeTokens[view.border_token] ?? "var(--border-subtle)"}`
      : "1px solid transparent",
    backdropFilter:
      view.backdrop_blur && view.backdrop_blur > 25
        ? `blur(${blurToPx(view.backdrop_blur ?? null)}px)`
        : undefined,
    WebkitBackdropFilter:
      view.backdrop_blur && view.backdrop_blur > 25
        ? `blur(${blurToPx(view.backdrop_blur ?? null)}px)`
        : undefined,
    transition: "all 200ms ease-out",
  }

  return (
    <div className="flex h-full flex-1 overflow-hidden">
      {/* Left rail — cores browser. Hidden when mounted inside the
          Studio shell with the rail expanded; standalone-mount keeps
          the browser visible. focus-editor-browser testid carries
          the studio-rail-adaptation contract from the prior page. */}
      {!hideLeftBrowser && (
      <aside
        data-testid="focus-editor-browser"
        data-tier1-cores-browser="true"
        className="flex w-[320px] shrink-0 flex-col border-r border-[color:var(--border-subtle)] bg-[color:var(--surface-sunken)]"
      >
        <header className="flex items-center justify-between border-b border-[color:var(--border-subtle)] px-3 py-2">
          <span
            className="text-[11px] font-medium uppercase tracking-wide text-[color:var(--content-muted)]"
            style={{ fontFamily: "var(--font-plex-sans)" }}
          >
            Focus Cores
          </span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setCreateOpen(true)}
            data-testid="new-core-button"
            className="h-7 gap-1 px-2 text-[12px]"
          >
            <Plus className="h-3 w-3" />
            New core
          </Button>
        </header>

        <div className="flex-1 overflow-y-auto">
          {listLoading && (
            <div
              data-testid="cores-loading"
              className="flex items-center justify-center p-4 text-[12px] text-[color:var(--content-muted)]"
            >
              <Loader2 className="mr-2 h-3 w-3 animate-spin" /> Loading cores…
            </div>
          )}
          {listError && (
            <div
              role="alert"
              data-testid="cores-error"
              className="m-3 rounded-md border border-[color:var(--status-error)] bg-[color:var(--status-error-muted)] px-3 py-2 text-[12px] text-[color:var(--status-error)]"
            >
              {listError}
            </div>
          )}
          {!listLoading && !listError && cores.length === 0 && (
            <div
              data-testid="cores-empty"
              className="m-3 rounded-md border border-dashed border-[color:var(--border-subtle)] p-4 text-center text-[12px] text-[color:var(--content-muted)]"
            >
              No cores yet. Click <span className="font-medium">New core</span> to create one.
            </div>
          )}
          <ul className="flex flex-col" data-testid="cores-list">
            {cores
              .filter((c) => c.is_active)
              .sort((a, b) => a.display_name.localeCompare(b.display_name))
              .map((c) => {
                const selected = c.id === selectedCoreId
                return (
                  <li key={c.id}>
                    <button
                      type="button"
                      data-testid={`core-row-${c.core_slug}`}
                      data-selected={selected ? "true" : "false"}
                      onClick={() => onSelectCore(c.id)}
                      className={`flex w-full flex-col items-start gap-0.5 border-b border-[color:var(--border-subtle)] px-3 py-2 text-left transition-colors ${
                        selected
                          ? "bg-[color:var(--accent-subtle)] border-l-2 border-l-[color:var(--accent)]"
                          : "hover:bg-[color:var(--accent-subtle)]/50"
                      }`}
                      style={{ fontFamily: "var(--font-plex-sans)" }}
                    >
                      <span className="text-[13px] font-medium text-[color:var(--content-strong)]">
                        {c.display_name}
                      </span>
                      <span className="text-[11px] text-[color:var(--content-muted)] font-mono">
                        {c.registered_component_name} · v{c.version}
                      </span>
                    </button>
                  </li>
                )
              })}
          </ul>
        </div>
      </aside>
      )}

      {/* Center — preview pane */}
      <section
        data-testid="tier1-preview"
        className="relative flex flex-1 overflow-hidden"
        style={{
          background:
            "linear-gradient(135deg, #f9d9a6 0%, #e9b27e 30%, #c97d52 60%, #9C5640 100%)",
        }}
      >
        <div
          aria-hidden
          className="absolute inset-0 opacity-30"
          style={{
            backgroundImage:
              "repeating-linear-gradient(45deg, rgba(255,255,255,0.18) 0 1px, transparent 1px 22px)",
          }}
        />
        <div className="relative flex h-full flex-1 items-center justify-center p-12">
          {!selectedCoreId ? (
            <div
              data-testid="tier1-no-selection"
              className="rounded-lg bg-[color:var(--surface-elevated)]/90 p-6 text-center text-[13px] text-[color:var(--content-muted)] shadow-[var(--shadow-level-1)]"
            >
              {cores.length === 0
                ? "Create a Focus Core to start authoring its chrome."
                : "Select a Focus Core on the left to edit its chrome."}
            </div>
          ) : isLoading ? (
            <div className="text-[13px] text-[color:var(--content-on-accent)]">
              <Loader2 className="inline-block h-4 w-4 animate-spin" /> Loading…
            </div>
          ) : error ? (
            <div
              role="alert"
              data-testid="tier1-load-error"
              className="rounded-md border border-[color:var(--status-error)] bg-[color:var(--status-error-muted)] px-3 py-2 text-[12px] text-[color:var(--status-error)]"
            >
              {error}
            </div>
          ) : (
            <div
              data-testid="tier1-preview-card"
              style={{ ...cardStyle, width: "min(440px, 80%)", minHeight: 200 }}
              className="flex flex-col gap-2 text-[color:var(--content-strong)]"
            >
              <span
                className="text-[10px] uppercase tracking-[0.08em] text-[color:var(--content-muted)]"
                style={{ fontFamily: "var(--font-plex-sans)" }}
              >
                {core?.core_slug ?? "—"}
              </span>
              <h2
                className="text-[20px] font-medium"
                style={{ fontFamily: "var(--font-plex-serif)" }}
              >
                {core?.display_name ?? "Focus Core"}
              </h2>
              <p
                className="text-[13px] leading-relaxed text-[color:var(--content-base)]"
                style={{ fontFamily: "var(--font-plex-sans)" }}
              >
                {core?.description ??
                  "Adjust the chrome inspector on the right. Saves apply automatically after a short pause."}
              </p>
              <span
                className="mt-2 text-[11px] tabular-nums text-[color:var(--content-muted)]"
                style={{ fontFamily: "var(--font-plex-mono)" }}
              >
                preset: {view.preset ?? "—"} · elev: {view.elevation ?? "—"} ·
                radius: {view.corner_radius ?? "—"} · blur:{" "}
                {view.backdrop_blur ?? "—"}
                {isSaving ? " · saving…" : ""}
              </span>
            </div>
          )}
        </div>
      </section>

      {/* Right — chrome inspector */}
      <aside
        data-testid="tier1-inspector"
        className="w-[340px] shrink-0 overflow-y-auto"
      >
        {!selectedCoreId ? (
          <div
            className="flex h-full items-center justify-center p-6 text-center text-[12px] text-[color:var(--content-muted)]"
            style={{ fontFamily: "var(--font-plex-sans)" }}
          >
            <span>
              <ArrowLeftRight className="mx-auto mb-2 h-4 w-4" />
              Select a core to edit its chrome.
            </span>
          </div>
        ) : (
          <PropertyPanel>
            <PropertySection title="Chrome" defaultExpanded>
              <PropertyRow>
                <ChromePresetPicker
                  value={view.preset}
                  onChange={(p) => updateDraft({ preset: p as PresetSlug | null })}
                />
              </PropertyRow>
              <PropertyRow>
                <ScrubbableButton
                  value={view.elevation ?? 0}
                  min={0}
                  max={100}
                  label="Elevation"
                  onChange={(v) => updateDraft({ elevation: v })}
                />
              </PropertyRow>
              <PropertyRow>
                <ScrubbableButton
                  value={view.corner_radius ?? 0}
                  min={0}
                  max={100}
                  label="Corner radius"
                  onChange={(v) => updateDraft({ corner_radius: v })}
                />
              </PropertyRow>
              <PropertyRow>
                <ScrubbableButton
                  value={view.backdrop_blur ?? 0}
                  min={0}
                  max={100}
                  label="Backdrop blur"
                  onChange={(v) => updateDraft({ backdrop_blur: v })}
                />
              </PropertyRow>
              <PropertyRow>
                <TokenSwatchPicker
                  value={view.background_token ?? null}
                  tokenFamily="surface"
                  themeTokens={themeTokens}
                  onChange={(t) => updateDraft({ background_token: t })}
                  label="Background"
                />
              </PropertyRow>
              <PropertyRow>
                <TokenSwatchPicker
                  value={view.border_token ?? null}
                  tokenFamily="border"
                  themeTokens={themeTokens}
                  onChange={(t) => updateDraft({ border_token: t })}
                  label="Border"
                />
              </PropertyRow>
              <PropertyRow>
                <TokenSwatchPicker
                  value={view.padding_token ?? null}
                  tokenFamily="padding"
                  themeTokens={themeTokens}
                  onChange={(t) => updateDraft({ padding_token: t })}
                  label="Padding"
                />
              </PropertyRow>
            </PropertySection>
          </PropertyPanel>
        )}
      </aside>

      <CreateTierOneCoreModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(rec) => {
          setCreateOpen(false)
          void refreshList()
          onSelectCore(rec.id)
        }}
      />
    </div>
  )
}

export default Tier1CoresEditor
