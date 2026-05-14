/**
 * ChromePrimitivesDemoPage — visual-authoring demo (sub-arc C-1).
 *
 * Internal / dev surface — NOT a production editor. Demonstrates
 * the four sub-arc C-1 primitives composing a single-card chrome
 * inspector against a live theme fetch.
 *
 * Layout:
 *   - LEFT (~60%): card preview rendered against a warm-gradient
 *     backdrop so the frosted preset's backdrop_blur reads as
 *     glass-on-warm-gradient.
 *   - RIGHT (~40% or 320px): PropertyPanel with three collapsible
 *     sections — Preset (ChromePresetPicker), Sliders (3×
 *     ScrubbableButton: Elevation, Corner Radius, Backdrop Blur),
 *     Tokens (3× TokenSwatchPicker: Background, Border, Padding).
 *
 * State: component-local via useState. Initial chrome:
 * `{ preset: "card" }`. Operator interaction updates state →
 * card preview re-renders. No API persistence.
 *
 * Theme tokens: fetched from `/api/platform/admin/visual-editor/
 * themes/resolve?mode=light` once on mount. Fallback to hardcoded
 * `tokens.css` light-mode defaults on error so the demo always
 * renders.
 *
 * Slider-to-CSS mapping (mirror of locked decisions; ALSO
 * mirrored in C-2's production editor when it lands):
 *   - elevation: 0-100 → one of shadow-level-0..3
 *   - corner_radius: 0-100 → 0/8/14/24px
 *   - backdrop_blur: 0-100 → 0/8/14/24px CSS blur()
 *   - padding token: space-2 → 8px, space-4 → 16px, space-6 → 24px,
 *     space-8 → 32px
 */
import * as React from "react"

import { adminApi } from "@/bridgeable-admin/lib/admin-api"
import {
  ChromePresetPicker,
  PropertyPanel,
  PropertyRow,
  PropertySection,
  ScrubbableButton,
  TokenSwatchPicker,
  type PresetSlug,
} from "@/bridgeable-admin/components/visual-authoring"

/** Chrome v2 vocabulary (mirror of backend schemas.ChromeBlob). */
interface ChromeBlob {
  preset: PresetSlug | null
  elevation: number | null
  corner_radius: number | null
  backdrop_blur: number | null
  background_token: string | null
  border_token: string | null
  padding_token: string | null
}

/** Frontend mirror of backend PRESETS for the preview rendering. */
const PRESETS: Record<PresetSlug, Partial<ChromeBlob>> = {
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
    border_token: "border-brass",
  },
  frosted: {
    background_token: "surface-elevated",
    elevation: 50,
    corner_radius: 62,
    padding_token: "space-6",
    backdrop_blur: 60,
    border_token: "border-subtle",
  },
  custom: {},
}

/** Resolve a chrome blob with preset expansion (frontend mirror). */
function expandPreset(chrome: ChromeBlob): ChromeBlob {
  const preset = chrome.preset
  if (!preset || preset === "custom") return chrome
  const defaults = PRESETS[preset]
  const merged: ChromeBlob = { ...chrome }
  for (const key of Object.keys(defaults) as (keyof ChromeBlob)[]) {
    if (chrome[key] === null || chrome[key] === undefined) {
      ;(merged as unknown as Record<string, unknown>)[key] = defaults[
        key
      ] as unknown
    }
  }
  return merged
}

/** Slider 0-100 → shadow CSS. */
function elevationToBoxShadow(value: number | null): string {
  if (value === null || value <= 25) return "none"
  if (value <= 50) return "0 2px 6px rgba(48, 32, 16, 0.10)"
  if (value <= 75) return "0 8px 24px rgba(48, 32, 16, 0.14)"
  return "0 16px 48px rgba(48, 32, 16, 0.20)"
}

/** Slider 0-100 → border-radius px. */
function cornerRadiusToPx(value: number | null): number {
  if (value === null || value <= 25) return 0
  if (value <= 50) return 8
  if (value <= 75) return 14
  return 24
}

/** Slider 0-100 → backdrop-filter blur px. */
function backdropBlurToPx(value: number | null): number {
  if (value === null || value <= 25) return 0
  if (value <= 50) return 8
  if (value <= 75) return 14
  return 24
}

/** Padding token → px. */
const PADDING_PX: Record<string, number> = {
  "space-2": 8,
  "space-4": 16,
  "space-6": 24,
  "space-8": 32,
}

/** Hardcoded fallback (tokens.css light-mode defaults — abbreviated). */
const FALLBACK_TOKENS: Record<string, string> = {
  "surface-base": "#fbfaf6",
  "surface-elevated": "#ffffff",
  "surface-raised": "#fdfcf8",
  "surface-sunken": "#f1efe9",
  "border-subtle": "#e8e3d8",
  "border-base": "#cfc8b8",
  "border-strong": "#a89e88",
  "border-brass": "#9C5640",
}

interface ResolvedThemeResponse {
  tokens?: Record<string, string>
  resolved?: Record<string, string>
}

export default function ChromePrimitivesDemoPage() {
  const [chrome, setChrome] = React.useState<ChromeBlob>({
    preset: "card",
    elevation: null,
    corner_radius: null,
    backdrop_blur: null,
    background_token: null,
    border_token: null,
    padding_token: null,
  })

  const [themeTokens, setThemeTokens] = React.useState<Record<string, string>>(
    FALLBACK_TOKENS,
  )

  React.useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await adminApi.get<ResolvedThemeResponse>(
          "/api/platform/admin/visual-editor/themes/resolve",
          { params: { mode: "light" } },
        )
        if (cancelled) return
        // The endpoint shape carries the resolved token map under
        // `tokens` or `resolved` depending on phase. Try both, fall
        // back gracefully.
        const map = res.data.tokens ?? res.data.resolved ?? {}
        // Normalize: tokens may be keyed with or without leading `--`.
        const normalized: Record<string, string> = { ...FALLBACK_TOKENS }
        for (const [k, v] of Object.entries(map)) {
          const key = k.startsWith("--") ? k.slice(2) : k
          normalized[key] = v
        }
        setThemeTokens(normalized)
      } catch {
        // Fallback only — demo is internal/dev; do not block render
        // on theme fetch failure.
        if (!cancelled) setThemeTokens(FALLBACK_TOKENS)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  // Resolved chrome (preset expanded). Display uses this view.
  const resolved = React.useMemo(() => expandPreset(chrome), [chrome])

  const cardStyle: React.CSSProperties = {
    background:
      themeTokens[resolved.background_token ?? "surface-elevated"] ??
      "var(--surface-elevated, #ffffff)",
    borderRadius: cornerRadiusToPx(resolved.corner_radius ?? null),
    boxShadow: elevationToBoxShadow(resolved.elevation ?? null),
    padding: PADDING_PX[resolved.padding_token ?? "space-6"] ?? 24,
    border: resolved.border_token
      ? `1px solid ${
          themeTokens[resolved.border_token] ?? "var(--border-subtle)"
        }`
      : "1px solid transparent",
    backdropFilter:
      resolved.backdrop_blur && resolved.backdrop_blur > 25
        ? `blur(${backdropBlurToPx(resolved.backdrop_blur ?? null)}px)`
        : undefined,
    WebkitBackdropFilter:
      resolved.backdrop_blur && resolved.backdrop_blur > 25
        ? `blur(${backdropBlurToPx(resolved.backdrop_blur ?? null)}px)`
        : undefined,
    transition: "all 200ms ease-out",
  }

  function setField<K extends keyof ChromeBlob>(field: K, value: ChromeBlob[K]) {
    setChrome((prev) => ({ ...prev, [field]: value }))
  }

  return (
    <div
      data-testid="chrome-primitives-demo-page"
      className="flex h-full min-h-[calc(100vh-4rem)] w-full flex-col"
    >
      {/* Header */}
      <header className="border-b border-[color:var(--border-subtle)] bg-[color:var(--surface-base)] px-6 py-4">
        <h1
          className="text-[15px] font-medium text-[color:var(--content-strong)]"
          style={{ fontFamily: "var(--font-plex-sans)" }}
        >
          Chrome primitives demo
        </h1>
        <p
          className="text-[12px] text-[color:var(--content-muted)]"
          style={{ fontFamily: "var(--font-plex-sans)" }}
        >
          Sub-arc C-1. Internal / dev surface — not a production
          editor. C-2 builds the Tier 1+2 production editor consuming
          the same primitives.
        </p>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Preview pane */}
        <div
          data-testid="chrome-preview"
          className="relative flex-1 overflow-hidden"
          style={{
            background:
              // Warm gradient so backdrop_blur reads as glass.
              "linear-gradient(135deg, #f9d9a6 0%, #e9b27e 30%, #c97d52 60%, #9C5640 100%)",
          }}
        >
          {/* Subtle texture lines so the blur has something to act on. */}
          <div
            aria-hidden
            className="absolute inset-0 opacity-30"
            style={{
              backgroundImage:
                "repeating-linear-gradient(45deg, rgba(255,255,255,0.18) 0 1px, transparent 1px 22px)",
            }}
          />
          <div className="relative flex h-full items-center justify-center p-12">
            <div
              data-testid="chrome-preview-card"
              style={{
                ...cardStyle,
                width: "min(440px, 80%)",
                minHeight: 200,
              }}
              className="flex flex-col gap-2 text-[color:var(--content-strong)]"
            >
              <span
                className="text-[10px] tracking-[0.08em] uppercase text-[color:var(--content-muted)]"
                style={{ fontFamily: "var(--font-plex-sans)" }}
              >
                Preview
              </span>
              <h2
                className="text-[20px] font-medium"
                style={{ fontFamily: "var(--font-plex-serif)" }}
              >
                The Range Rover digital design thread
              </h2>
              <p
                className="text-[13px] leading-relaxed text-[color:var(--content-base)]"
                style={{ fontFamily: "var(--font-plex-sans)" }}
              >
                Restrained, materially honest, architecturally
                proportioned, warmly confident, time-resistant. Adjust
                the inspector on the right to see the chrome
                resolve against a warm gradient.
              </p>
              <span
                className="mt-2 text-[11px] tabular-nums text-[color:var(--content-muted)]"
                style={{ fontFamily: "var(--font-plex-mono)" }}
              >
                preset: {resolved.preset ?? "—"} · elev:{" "}
                {resolved.elevation ?? "—"} · radius:{" "}
                {resolved.corner_radius ?? "—"} · blur:{" "}
                {resolved.backdrop_blur ?? "—"}
              </span>
            </div>
          </div>
        </div>

        {/* Inspector pane */}
        <div className="w-[340px] shrink-0">
          <PropertyPanel>
            <PropertySection title="Preset">
              <PropertyRow>
                <ChromePresetPicker
                  value={chrome.preset}
                  onChange={(p) => setField("preset", p as PresetSlug | null)}
                />
              </PropertyRow>
            </PropertySection>

            <PropertySection title="Sliders">
              <PropertyRow>
                <ScrubbableButton
                  value={chrome.elevation ?? resolved.elevation ?? 0}
                  min={0}
                  max={100}
                  label="Elevation"
                  onChange={(v) => setField("elevation", v)}
                />
              </PropertyRow>
              <PropertyRow>
                <ScrubbableButton
                  value={chrome.corner_radius ?? resolved.corner_radius ?? 0}
                  min={0}
                  max={100}
                  label="Corner radius"
                  onChange={(v) => setField("corner_radius", v)}
                />
              </PropertyRow>
              <PropertyRow>
                <ScrubbableButton
                  value={chrome.backdrop_blur ?? resolved.backdrop_blur ?? 0}
                  min={0}
                  max={100}
                  label="Backdrop blur"
                  onChange={(v) => setField("backdrop_blur", v)}
                />
              </PropertyRow>
            </PropertySection>

            <PropertySection title="Tokens">
              <PropertyRow>
                <TokenSwatchPicker
                  value={chrome.background_token ?? resolved.background_token ?? null}
                  tokenFamily="surface"
                  themeTokens={themeTokens}
                  onChange={(t) => setField("background_token", t)}
                  label="Background"
                />
              </PropertyRow>
              <PropertyRow>
                <TokenSwatchPicker
                  value={chrome.border_token ?? resolved.border_token ?? null}
                  tokenFamily="border"
                  themeTokens={themeTokens}
                  onChange={(t) => setField("border_token", t)}
                  label="Border"
                />
              </PropertyRow>
              <PropertyRow>
                <TokenSwatchPicker
                  value={chrome.padding_token ?? resolved.padding_token ?? null}
                  tokenFamily="padding"
                  themeTokens={themeTokens}
                  onChange={(t) => setField("padding_token", t)}
                  label="Padding"
                />
              </PropertyRow>
            </PropertySection>
          </PropertyPanel>
        </div>
      </div>
    </div>
  )
}
