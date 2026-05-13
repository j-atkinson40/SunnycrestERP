/**
 * Phase R-1 — Inspector Theme tab.
 *
 * Curated ~20-token subset for V1: accent family + surface families
 * (light + dark are mode-shared at the token-name level — the
 * impersonated theme's mode determines which row of `defaults` is
 * the rendered value), text content families, status families, and
 * the radius tokens. Full catalog accessible via "Show all tokens".
 *
 * Edits stage to EditModeProvider's `draftOverrides` keyed by
 * `token:{tokenName}:value`. Live preview applies the staged tokens
 * to the document root via `applyThemeToElement` — same mechanism
 * the standalone theme editor uses, scoped to root rather than a
 * preview wrapper.
 */
import { useEffect, useMemo, useState } from "react"

import {
  themesService,
  type ResolvedTheme,
  type ThemeMode,
} from "@/bridgeable-admin/services/themes-service"
import {
  TOKEN_CATALOG,
  type TokenEntry,
} from "@/lib/visual-editor/themes/token-catalog"
import {
  applyThemeToElement,
  catalogDefaultsForMode,
  stackFromResolved,
  composeEffective,
  type TokenOverrideMap,
} from "@/lib/visual-editor/themes/theme-resolver"
// Arc 4d — canonical SourceBadge (letter variant) + ScopeDiffPopover.
// Replaces inline `badgeLetter` + bare `<span>` ad-hoc badge per
// 3-way pattern drift closure.
import {
  SourceBadge,
  ScopeDiffPopover,
  type SourceValue,
  type ResolutionSourceEntry,
} from "@/lib/visual-editor/source-badge"

import { useEditMode } from "../edit-mode-context"


// V1 curated subset — names match `--<name>` CSS custom properties.
const CURATED_TOKEN_NAMES: ReadonlyArray<string> = [
  // Accent family
  "accent",
  "accent-hover",
  "accent-subtle",
  "accent-muted",
  // Surface family
  "surface-base",
  "surface-elevated",
  "surface-raised",
  "surface-sunken",
  // Content family
  "content-strong",
  "content-base",
  "content-muted",
  "content-subtle",
  "content-on-accent",
  // Status family
  "status-error",
  "status-warning",
  "status-success",
  "status-info",
  // Radius
  "radius-base",
  "radius-full",
]


export function ThemeTab({
  vertical,
  tenantId,
  themeMode,
}: {
  vertical: string | null
  tenantId: string | null
  themeMode: ThemeMode
}) {
  const editMode = useEditMode()
  const [resolved, setResolved] = useState<ResolvedTheme | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [showAllTokens, setShowAllTokens] = useState(false)

  useEffect(() => {
    let cancelled = false
    setIsLoading(true)
    themesService
      .resolve({
        mode: themeMode,
        vertical: vertical ?? undefined,
        tenant_id: tenantId ?? undefined,
      })
      .then((res) => {
        if (!cancelled) setResolved(res)
      })
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.warn("[runtime-editor] resolve theme failed", err)
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [themeMode, vertical, tenantId])

  // Build the 4-layer stack (catalog default → platform → vertical →
  // tenant) plus draft on top. mergeStack composes everything except
  // draft; we layer draft last for the preview.
  const draftOverrides = useMemo<TokenOverrideMap>(() => {
    const m: TokenOverrideMap = {}
    for (const o of editMode.draftOverrides.values()) {
      if (o.type === "token" && typeof o.value === "string") {
        m[o.target] = o.value
      }
    }
    return m
  }, [editMode.draftOverrides])

  const effective = useMemo<TokenOverrideMap>(() => {
    if (resolved) {
      const stack = stackFromResolved(resolved, draftOverrides)
      return composeEffective(themeMode, stack)
    }
    return { ...catalogDefaultsForMode(themeMode), ...draftOverrides }
  }, [resolved, draftOverrides, themeMode])

  // Live preview: apply effective tokens to documentElement so the
  // entire impersonated route reflects the staged theme. R-1 V1 lives
  // with this — R-2 may scope to a wrapper if double-rendering edge
  // cases appear in practice.
  useEffect(() => {
    if (typeof document === "undefined") return
    if (!editMode.isEditing) return
    applyThemeToElement(effective, document.documentElement)
    // No cleanup — leaving theme applied is what the runtime preview
    // needs. Toggling edit-mode off doesn't revert (operators expect
    // their staged preview to persist while reviewing other tabs).
  }, [effective, editMode.isEditing])

  const visibleTokens: TokenEntry[] = useMemo(() => {
    if (showAllTokens) return TOKEN_CATALOG
    const set = new Set(CURATED_TOKEN_NAMES)
    return TOKEN_CATALOG.filter((t) => set.has(t.name))
  }, [showAllTokens])

  function sourceFor(tokenName: string): "draft" | "tenant-override" | "vertical-default" | "platform-default" | "registration-default" {
    if (tokenName in draftOverrides) return "draft"
    if (!resolved) return "registration-default"
    for (const src of resolved.sources) {
      if (src.applied_keys.includes(tokenName)) {
        if (src.scope === "tenant_override") return "tenant-override"
        if (src.scope === "vertical_default") return "vertical-default"
        if (src.scope === "platform_default") return "platform-default"
      }
    }
    return "registration-default"
  }

  /**
   * Arc 4d — map `sourceFor` legacy union to canonical SourceValue.
   * Replaces inline `badgeLetter` switch with single canonical mapping.
   */
  function toCanonicalSource(
    s: ReturnType<typeof sourceFor>,
  ): SourceValue {
    switch (s) {
      case "draft":
        return "draft"
      case "tenant-override":
        return "tenant"
      case "vertical-default":
        return "vertical"
      case "platform-default":
        return "platform"
      case "registration-default":
        return "default"
    }
  }

  /**
   * Arc 4d — build resolution chain for ScopeDiffPopover. Walks
   * `resolved.sources` filtering to entries that applied THIS token.
   * Returns winning entry FIRST (resolver-order matches backend
   * source array ordering).
   */
  function chainFor(tokenName: string): ResolutionSourceEntry[] {
    if (!resolved) return []
    const chain: ResolutionSourceEntry[] = []
    for (const src of resolved.sources) {
      if (src.applied_keys.includes(tokenName)) {
        chain.push({
          scope:
            src.scope === "tenant_override"
              ? "tenant_override"
              : src.scope === "vertical_default"
              ? "vertical_default"
              : "platform_default",
          // Per-source token-value isn't exposed by themes resolver
          // today (only `applied_keys` + winning `tokens` map). The
          // ScopeDiffPopover renders "undefined" gracefully; full
          // per-tier values would require a themes resolver
          // extension parallel to Arc 4d's Documents extension —
          // tracked but out of Arc 4d scope.
          value: undefined,
          version: src.version,
          vertical: src.vertical,
          tenant_id: src.tenant_id,
        })
      }
    }
    return chain
  }

  return (
    <div className="px-1 py-2" data-testid="runtime-inspector-theme-tab">
      <div className="px-3 pb-2 text-caption text-content-muted">
        Editing theme tokens at <code className="text-content-strong">vertical_default</code>
        {vertical ? ` (${vertical})` : ""} — mode <code>{themeMode}</code>.
      </div>
      {isLoading && (
        <div className="px-3 py-1 text-caption text-content-muted">
          Loading…
        </div>
      )}
      {visibleTokens.map((token) => {
        const value = effective[token.name] ?? token.defaults[themeMode]
        const source = sourceFor(token.name)
        const draftKey = `token::${token.name}::value`
        const isOverridden = editMode.draftOverrides.has(draftKey)
        return (
          <div
            key={token.name}
            className="flex items-center gap-2 border-b border-border-subtle px-2 py-1.5"
            data-testid={`runtime-inspector-token-${token.name}`}
          >
            {/* Arc 4d — canonical SourceBadge (letter) + hover-reveal
                ScopeDiffPopover. Both consume canonical source vocabulary;
                the chain is built from `resolved.sources`. */}
            <ScopeDiffPopover
              sources={chainFor(token.name)}
              currentValue={value}
              fieldLabel={token.displayName}
              data-testid={`runtime-inspector-theme-scope-diff-${token.name}`}
            >
              <SourceBadge
                source={toCanonicalSource(source)}
                variant="letter"
              />
            </ScopeDiffPopover>
            <div className="flex-1 min-w-0">
              <div className="text-caption text-content-strong truncate">
                {token.displayName}
              </div>
              <div className="text-[10px] text-content-subtle truncate">
                --{token.name}
              </div>
            </div>
            <input
              className="w-32 rounded-sm border border-border-subtle bg-surface-raised px-1.5 py-0.5 text-[11px] font-plex-mono text-content-strong"
              value={String(value ?? "")}
              onChange={(e) =>
                editMode.stageOverride({
                  type: "token",
                  target: token.name,
                  prop: "value",
                  value: e.target.value,
                })
              }
              disabled={token.editable === false}
              data-testid={`runtime-inspector-token-input-${token.name}`}
            />
            {isOverridden && (
              <button
                type="button"
                onClick={() => editMode.clearStaged("token", token.name)}
                className="text-[10px] text-content-muted hover:text-accent"
                title="Reset to inherited"
                data-testid={`runtime-inspector-token-reset-${token.name}`}
              >
                ↺
              </button>
            )}
          </div>
        )
      })}
      <div className="px-3 py-2">
        <button
          type="button"
          onClick={() => setShowAllTokens((p) => !p)}
          className="text-caption text-accent hover:underline"
          data-testid="runtime-inspector-theme-show-all"
        >
          {showAllTokens
            ? "Show curated tokens only"
            : `Show all tokens (${TOKEN_CATALOG.length})`}
        </button>
      </div>
    </div>
  )
}
