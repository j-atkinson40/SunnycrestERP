/**
 * PreviewCanvas — right pane of the theme editor.
 *
 * Renders all 17 registered components inside a sandboxed CSS
 * scope. The wrapper element carries the draft theme's effective
 * tokens as inline `--token-name` CSS variables, so every
 * stand-in inside inherits them — but the editor's OWN UI (left
 * + center panes, top bar) stays unaffected because it lives
 * outside this wrapper.
 *
 * Components are grouped by `ComponentKind` with a labeled header.
 * Clicking a component highlights it + invokes `onComponentSelect`
 * so the center pane can filter to only the tokens that component
 * consumes (`getTokensConsumedBy`).
 *
 * The `mode` prop sets `data-mode` on the wrapper so Tailwind's
 * `[data-mode="dark"]` cascade resolves correctly inside the
 * preview without touching the editor's own mode.
 */

import { useMemo } from "react"
import { Sun, Moon } from "lucide-react"

import {
  getAllRegistered,
  type RegistryEntry,
  type ComponentKind,
} from "@/admin/registry"
import {
  GROUP_ICONS,
  PREVIEW_RENDERERS,
  PreviewFallback,
} from "@/admin/themes/preview-data"
import {
  applyThemeToElement,
  type TokenOverrideMap,
} from "@/admin/themes/theme-resolver"
import type { ThemeMode } from "@/services/themes-service"


export interface PreviewCanvasProps {
  effectiveTokens: TokenOverrideMap
  previewMode: ThemeMode
  onPreviewModeChange: (mode: ThemeMode) => void
  selectedRegistryKey: string | null
  onComponentSelect: (registryKey: string | null) => void
  filterVertical?: string | null
}


function groupOrder(): ComponentKind[] {
  return [
    "widget",
    "focus",
    "focus-template",
    "document-block",
    "workflow-node",
  ]
}


function registryKey(entry: RegistryEntry): string {
  return `${entry.metadata.type}:${entry.metadata.name}`
}


export function PreviewCanvas({
  effectiveTokens,
  previewMode,
  onPreviewModeChange,
  selectedRegistryKey,
  onComponentSelect,
  filterVertical,
}: PreviewCanvasProps) {
  // Convert the effective tokens map into an inline-style object
  // suitable for the wrapper element. React doesn't accept custom
  // CSS properties via the `style` prop's typed shape directly —
  // we cast to `Record<string, string>` and let it through.
  const inlineStyle = useMemo(() => {
    const style: Record<string, string> = {}
    for (const [name, value] of Object.entries(effectiveTokens)) {
      style[`--${name}`] = String(value)
    }
    return style
  }, [effectiveTokens])

  const allEntries = useMemo(() => {
    const all = getAllRegistered()
    if (!filterVertical || filterVertical === "all") return all
    return all.filter((e) => {
      const verticals = e.metadata.verticals
      return (
        verticals.includes("all") ||
        verticals.includes(
          filterVertical as Parameters<typeof verticals.includes>[0],
        )
      )
    })
  }, [filterVertical])

  const grouped = useMemo(() => {
    const map = new Map<ComponentKind, RegistryEntry[]>()
    for (const e of allEntries) {
      const list = map.get(e.metadata.type) ?? []
      list.push(e)
      map.set(e.metadata.type, list)
    }
    return map
  }, [allEntries])

  return (
    <div
      className="flex h-full flex-col"
      data-testid="preview-canvas-root"
    >
      {/* ── Preview-mode toggle ─────────────────────────────── */}
      <div
        className="flex items-center justify-between border-b border-border-subtle bg-surface-elevated px-4 py-2"
      >
        <div className="text-body-sm text-content-muted">
          Live preview · all 17 registered components
        </div>
        <div
          className="flex items-center gap-1 rounded-md border border-border-subtle bg-surface-raised p-0.5"
          role="tablist"
          aria-label="Preview mode"
        >
          <button
            type="button"
            role="tab"
            aria-selected={previewMode === "light"}
            data-testid="preview-mode-light"
            onClick={() => onPreviewModeChange("light")}
            className={`flex items-center gap-1 rounded-sm px-2 py-1 text-caption ${
              previewMode === "light"
                ? "bg-accent-subtle text-content-strong"
                : "text-content-muted hover:bg-accent-subtle/40"
            }`}
          >
            <Sun size={12} /> Light
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={previewMode === "dark"}
            data-testid="preview-mode-dark"
            onClick={() => onPreviewModeChange("dark")}
            className={`flex items-center gap-1 rounded-sm px-2 py-1 text-caption ${
              previewMode === "dark"
                ? "bg-accent-subtle text-content-strong"
                : "text-content-muted hover:bg-accent-subtle/40"
            }`}
          >
            <Moon size={12} /> Dark
          </button>
        </div>
      </div>

      {/* ── Sandboxed render root ───────────────────────────── */}
      <div
        data-testid="preview-canvas-sandbox"
        data-mode={previewMode}
        style={{
          ...inlineStyle,
          background: "var(--surface-base)",
          color: "var(--content-base)",
          flex: 1,
          overflowY: "auto",
          padding: "1.5rem",
        }}
      >
        {groupOrder().map((kind) => {
          const entries = grouped.get(kind)
          if (!entries || entries.length === 0) return null
          return (
            <section
              key={kind}
              data-testid={`preview-group-${kind}`}
              style={{ marginBottom: "1.5rem" }}
            >
              <header
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  fontFamily: "var(--font-plex-sans)",
                  fontSize: "var(--text-micro)",
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                  color: "var(--content-muted)",
                  marginBottom: "0.5rem",
                  paddingBottom: "0.25rem",
                  borderBottom: "1px solid var(--border-subtle)",
                }}
              >
                <span style={{ color: "var(--accent)" }}>
                  {GROUP_ICONS[kind]}
                </span>
                {kind} ({entries.length})
              </header>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns:
                    "repeat(auto-fit, minmax(260px, 1fr))",
                  gap: "1rem",
                }}
              >
                {entries.map((entry) => {
                  const key = registryKey(entry)
                  const renderer = PREVIEW_RENDERERS[key]
                  const isSelected = selectedRegistryKey === key
                  return (
                    <button
                      key={key}
                      type="button"
                      data-testid={`preview-component-${entry.metadata.type}-${entry.metadata.name}`}
                      data-selected={isSelected ? "true" : "false"}
                      onClick={() =>
                        onComponentSelect(isSelected ? null : key)
                      }
                      style={{
                        textAlign: "left",
                        background: "transparent",
                        border: "none",
                        padding: 0,
                        margin: 0,
                        cursor: "pointer",
                        outline: isSelected
                          ? `2px solid var(--accent)`
                          : "none",
                        outlineOffset: "2px",
                        borderRadius: "var(--radius-base, 6px)",
                      }}
                    >
                      <div
                        style={{
                          fontFamily: "var(--font-plex-mono)",
                          fontSize: "var(--text-micro)",
                          color: "var(--content-subtle)",
                          marginBottom: "0.25rem",
                          padding: "0 0.25rem",
                        }}
                      >
                        {entry.metadata.type} · {entry.metadata.name}
                      </div>
                      {renderer ? (
                        renderer()
                      ) : (
                        <PreviewFallback
                          registryKey={key}
                          displayName={entry.metadata.displayName}
                        />
                      )}
                    </button>
                  )
                })}
              </div>
            </section>
          )
        })}
      </div>
    </div>
  )
}


// `applyThemeToElement` is re-exported for consumers wanting to
// test global application instead of the sandboxed flow.
export { applyThemeToElement }
