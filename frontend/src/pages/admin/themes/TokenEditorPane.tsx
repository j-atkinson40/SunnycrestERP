/**
 * TokenEditorPane — center pane of the theme editor.
 *
 * Renders the catalog grouped by category. Each row shows:
 *   - The token's display name + description
 *   - An inheritance indicator (catalog-default / platform-default
 *     / vertical-default / tenant-override / draft)
 *   - The right editor primitive for the value type (OKLCH picker,
 *     numeric slider, enum dropdown, shadow display)
 *   - A reset-to-inherited button (when the value is overridden
 *     at the current scope or higher)
 *   - An expandable "components consuming this token" section
 *     pulling from the registry's introspection API.
 */

import { useMemo, useState } from "react"
import { Search, RotateCcw, ChevronDown, ChevronRight } from "lucide-react"

import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  TOKEN_CATALOG,
  getCategoryLabel,
  getCategoryOrder,
  type TokenCategory,
  type TokenEntry,
} from "@/admin/themes/token-catalog"
import {
  resolveTokenSource,
  type ThemeStack,
  type TokenSource,
} from "@/admin/themes/theme-resolver"
import { TokenControl } from "@/admin/themes/controls/TokenControl"
import {
  getComponentsConsumingToken,
  getTokensConsumedBy,
  type ComponentKind,
} from "@/admin/registry"
import type { ThemeMode } from "@/services/themes-service"


export interface TokenEditorPaneProps {
  mode: ThemeMode
  /** Effective resolution stack — used both for current values
   * and for source-of-record indicators. */
  stack: ThemeStack
  /** Effective tokens (catalog defaults + stack), used as the
   * "current value" each control opens with. */
  effectiveTokens: Record<string, string>
  /** Set/clear an override at the current editing scope. Pass
   * `value === undefined` to clear (reset to inherited). */
  onTokenChange: (tokenName: string, value: string | undefined) => void
  /** Filter the rendered tokens to ONLY those consumed by this
   * component (registry key `"{type}:{name}"`). null = all tokens. */
  filterToComponentKey: string | null
  /** Hide tokens that are inherited from a parent scope (i.e.,
   * not currently overridden in `stack.draft` + the editing
   * scope). */
  showOnlyOverridden: boolean
  onShowOnlyOverriddenChange: (next: boolean) => void
  search: string
  onSearchChange: (next: string) => void
  /** Which scope's overrides are accumulating into `stack.draft`.
   * Affects the "Source" badge — a draft token shows
   * "Drafted at {scope}". */
  editingScope: "platform_default" | "vertical_default" | "tenant_override"
}


function sourceBadge(source: TokenSource, editingScope: string): {
  label: string
  variant: "default" | "secondary" | "outline" | "info" | "success"
} {
  switch (source) {
    case "draft":
      return {
        label: `draft@${editingScope.replace("_default", "").replace("_override", "")}`,
        variant: "info",
      }
    case "tenant-override":
      return { label: "tenant override", variant: "secondary" }
    case "vertical-default":
      return { label: "vertical default", variant: "secondary" }
    case "platform-default":
      return { label: "platform default", variant: "secondary" }
    case "catalog-default":
      return { label: "catalog default", variant: "outline" }
  }
}


export function TokenEditorPane({
  mode: _mode,
  stack,
  effectiveTokens,
  onTokenChange,
  filterToComponentKey,
  showOnlyOverridden,
  onShowOnlyOverriddenChange,
  search,
  onSearchChange,
  editingScope,
}: TokenEditorPaneProps) {
  const [collapsed, setCollapsed] = useState<Set<TokenCategory>>(new Set())
  const [consumersOpenFor, setConsumersOpenFor] = useState<string | null>(null)

  // If filtering by component, fetch the consumed-token names once.
  const filterTokenNames: Set<string> | null = useMemo(() => {
    if (!filterToComponentKey) return null
    const colonIdx = filterToComponentKey.indexOf(":")
    if (colonIdx === -1) return null
    const type = filterToComponentKey.slice(0, colonIdx) as ComponentKind
    const name = filterToComponentKey.slice(colonIdx + 1)
    if (!type || !name) return null
    return new Set(getTokensConsumedBy(type, name))
  }, [filterToComponentKey])

  const filteredCatalog: TokenEntry[] = useMemo(() => {
    const lowerSearch = search.trim().toLowerCase()
    return TOKEN_CATALOG.filter((t) => {
      if (filterTokenNames && !filterTokenNames.has(t.name)) return false
      if (showOnlyOverridden) {
        const source = resolveTokenSource(t.name, stack)
        if (source === "catalog-default" || source === "platform-default") {
          return false
        }
      }
      if (lowerSearch) {
        const haystack =
          `${t.name} ${t.displayName} ${t.description ?? ""} ${t.category} ${t.subcategory ?? ""}`.toLowerCase()
        if (!haystack.includes(lowerSearch)) return false
      }
      return true
    })
  }, [filterTokenNames, showOnlyOverridden, stack, search])

  const grouped: Record<TokenCategory, TokenEntry[]> = useMemo(() => {
    const out = {} as Record<TokenCategory, TokenEntry[]>
    for (const t of filteredCatalog) {
      out[t.category] = out[t.category] ?? []
      out[t.category].push(t)
    }
    return out
  }, [filteredCatalog])

  function toggleCategory(c: TokenCategory) {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(c)) next.delete(c)
      else next.add(c)
      return next
    })
  }

  const totalShown = filteredCatalog.length

  return (
    <div
      className="flex h-full flex-col"
      data-testid="token-editor-pane"
    >
      {/* ── Filter bar ─────────────────────────────────────── */}
      <div className="flex flex-col gap-2 border-b border-border-subtle bg-surface-elevated px-4 py-3">
        <div className="flex items-center gap-2">
          <Search size={14} className="text-content-muted" />
          <Input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search tokens (name, description)…"
            data-testid="token-search-input"
            className="flex-1"
          />
        </div>
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 text-caption text-content-muted">
            <input
              type="checkbox"
              checked={showOnlyOverridden}
              onChange={(e) => onShowOnlyOverriddenChange(e.target.checked)}
              data-testid="token-show-overridden-toggle"
            />
            Show only overridden tokens
          </label>
          <span
            className="text-caption font-plex-mono text-content-muted"
            data-testid="token-shown-count"
          >
            {totalShown} of {TOKEN_CATALOG.length}
          </span>
        </div>
        {filterToComponentKey && (
          <div
            className="flex items-center justify-between rounded-md bg-accent-subtle px-2 py-1 text-caption text-content-strong"
            data-testid="token-component-filter-banner"
          >
            <span>
              Showing only tokens consumed by{" "}
              <code className="font-plex-mono">{filterToComponentKey}</code>
            </span>
            <button
              type="button"
              onClick={() => onTokenChange("__clear-filter__", undefined)}
              className="text-content-muted hover:text-content-strong"
            >
              Clear
            </button>
          </div>
        )}
      </div>

      {/* ── Token rows ─────────────────────────────────────── */}
      <div
        className="flex-1 overflow-y-auto px-4 py-3"
        data-testid="token-list"
      >
        {totalShown === 0 ? (
          <p className="text-body-sm text-content-muted">
            No tokens match the current filters.
          </p>
        ) : (
          getCategoryOrder().map((category) => {
            const entries = grouped[category]
            if (!entries || entries.length === 0) return null
            const isCollapsed = collapsed.has(category)
            return (
              <section
                key={category}
                data-testid={`token-category-${category}`}
                className="mb-4"
              >
                <button
                  type="button"
                  onClick={() => toggleCategory(category)}
                  className="flex w-full items-center justify-between border-b border-border-subtle pb-1 text-left"
                  data-testid={`token-category-toggle-${category}`}
                >
                  <span className="flex items-center gap-1 text-micro uppercase tracking-wider text-content-muted">
                    {isCollapsed ? (
                      <ChevronRight size={12} />
                    ) : (
                      <ChevronDown size={12} />
                    )}
                    {getCategoryLabel(category)}
                    <Badge variant="outline" className="ml-1">
                      {entries.length}
                    </Badge>
                  </span>
                </button>
                {!isCollapsed && (
                  <div className="mt-2 flex flex-col gap-3">
                    {entries.map((token) => {
                      const value = effectiveTokens[token.name] ?? ""
                      const source = resolveTokenSource(token.name, stack)
                      const sb = sourceBadge(source, editingScope)
                      const isOverriddenAtEditingScope =
                        source === "draft" ||
                        (editingScope === "platform_default" &&
                          source === "platform-default") ||
                        (editingScope === "vertical_default" &&
                          source === "vertical-default") ||
                        (editingScope === "tenant_override" &&
                          source === "tenant-override")
                      const consumers = getComponentsConsumingToken(token.name)
                      const isConsumersOpen = consumersOpenFor === token.name
                      return (
                        <div
                          key={token.name}
                          data-testid={`token-row-${token.name}`}
                          className="rounded-md border border-border-subtle bg-surface-elevated p-3"
                        >
                          <div className="flex items-baseline justify-between gap-2">
                            <div>
                              <div className="text-body-sm font-medium text-content-strong">
                                {token.displayName}
                              </div>
                              <code
                                className="font-plex-mono text-caption text-content-muted"
                                data-testid={`token-row-${token.name}-name`}
                              >
                                --{token.name}
                              </code>
                            </div>
                            <div className="flex items-center gap-2">
                              <Badge
                                variant={sb.variant}
                                data-testid={`token-row-${token.name}-source`}
                              >
                                {sb.label}
                              </Badge>
                              {isOverriddenAtEditingScope && (
                                <button
                                  type="button"
                                  onClick={() =>
                                    onTokenChange(token.name, undefined)
                                  }
                                  className="flex items-center gap-1 rounded-sm border border-border-base bg-surface-raised px-2 py-1 text-caption text-content-muted hover:bg-accent-subtle"
                                  data-testid={`token-row-${token.name}-reset`}
                                  aria-label={`Reset ${token.displayName} to inherited`}
                                >
                                  <RotateCcw size={11} />
                                  Reset
                                </button>
                              )}
                            </div>
                          </div>
                          {token.description && (
                            <p className="mt-1 text-caption text-content-muted">
                              {token.description}
                            </p>
                          )}
                          <div className="mt-2">
                            <TokenControl
                              token={token}
                              value={value}
                              onChange={(next) =>
                                onTokenChange(token.name, next)
                              }
                            />
                          </div>
                          {consumers.length > 0 && (
                            <div className="mt-2">
                              <button
                                type="button"
                                onClick={() =>
                                  setConsumersOpenFor((cur) =>
                                    cur === token.name ? null : token.name,
                                  )
                                }
                                className="flex items-center gap-1 text-caption text-content-muted hover:text-content-strong"
                                data-testid={`token-row-${token.name}-consumers-toggle`}
                              >
                                {isConsumersOpen ? (
                                  <ChevronDown size={12} />
                                ) : (
                                  <ChevronRight size={12} />
                                )}
                                {consumers.length}{" "}
                                {consumers.length === 1
                                  ? "component consumes"
                                  : "components consume"}{" "}
                                this token
                              </button>
                              {isConsumersOpen && (
                                <ul
                                  className="ml-4 mt-1 flex flex-col gap-0.5"
                                  data-testid={`token-row-${token.name}-consumers`}
                                >
                                  {consumers.map((c) => (
                                    <li
                                      key={`${c.metadata.type}:${c.metadata.name}`}
                                      className="text-caption text-content-base"
                                    >
                                      <Badge
                                        variant="outline"
                                        className="mr-1.5"
                                      >
                                        {c.metadata.type}
                                      </Badge>
                                      <span className="text-content-strong">
                                        {c.metadata.displayName}
                                      </span>{" "}
                                      <code className="font-plex-mono text-content-muted">
                                        {c.metadata.name}
                                      </code>
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </section>
            )
          })
        )}
      </div>
    </div>
  )
}
