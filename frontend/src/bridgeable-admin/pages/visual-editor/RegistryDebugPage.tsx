/**
 * Admin Registry Debug Page (Phase 1).
 *
 * Inspector for the Component Registry. NOT the eventual visual
 * editor — this is a developer tool for verifying that the
 * registry is populated correctly and for monitoring coverage
 * as more components get tagged over time.
 *
 * Built on existing Bridgeable design tokens + UI primitives so
 * the page reads coherent inside the admin shell. No new
 * design language; nothing fancy.
 *
 * Layout:
 *   • Header — total count + per-type tile + per-vertical tile
 *   • Filter row — type + vertical + search
 *   • Component table — clickable rows
 *   • Detail drawer — full metadata for selected component
 *   • Token reverse-lookup panel — every consumed token with
 *     a list of components reading it
 */

import { useMemo, useState } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  getAllRegistered,
  getCountByType,
  getCoverageByVertical,
  getKnownTokens,
  getComponentsConsumingToken,
} from "@/lib/visual-editor/registry"
import type {
  ComponentKind,
  RegistryEntry,
  VerticalScope,
} from "@/lib/visual-editor/registry"


const COMPONENT_KINDS: ComponentKind[] = [
  "widget",
  "focus",
  "focus-template",
  "document-block",
  "pulse-widget",
  "workflow-node",
  "layout",
  "composite",
]

const VERTICALS: VerticalScope[] = [
  "all",
  "manufacturing",
  "funeral_home",
  "cemetery",
  "crematory",
]


function formatRelative(ms: number): string {
  const delta = Date.now() - ms
  if (delta < 1000) return "just now"
  if (delta < 60_000) return `${Math.floor(delta / 1000)}s ago`
  if (delta < 3_600_000) return `${Math.floor(delta / 60_000)}m ago`
  return `${Math.floor(delta / 3_600_000)}h ago`
}


export default function RegistryDebugPage() {
  // Snapshot the registry once per render. The registry is
  // module-load-populated; we don't expect it to change between
  // renders inside this page.
  const all = useMemo(() => getAllRegistered(), [])
  const countByType = useMemo(() => getCountByType(), [])
  const coverageByVertical = useMemo(() => getCoverageByVertical(), [])
  const knownTokens = useMemo(() => getKnownTokens(), [])

  const [typeFilter, setTypeFilter] = useState<ComponentKind | "all">("all")
  const [verticalFilter, setVerticalFilter] = useState<VerticalScope | "any">(
    "any",
  )
  const [search, setSearch] = useState("")
  const [selected, setSelected] = useState<RegistryEntry | null>(null)
  const [tokenInspect, setTokenInspect] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase()
    return all.filter((entry) => {
      if (typeFilter !== "all" && entry.metadata.type !== typeFilter)
        return false
      if (verticalFilter !== "any") {
        const vs = entry.metadata.verticals
        const matchesVertical =
          verticalFilter === "all"
            ? vs.includes("all")
            : vs.includes(verticalFilter) || vs.includes("all")
        if (!matchesVertical) return false
      }
      if (term) {
        const haystack =
          `${entry.metadata.name} ${entry.metadata.displayName} ${entry.metadata.description ?? ""} ${entry.metadata.category ?? ""}`.toLowerCase()
        if (!haystack.includes(term)) return false
      }
      return true
    })
  }, [all, typeFilter, verticalFilter, search])

  const tokenInspectEntries = tokenInspect
    ? getComponentsConsumingToken(tokenInspect)
    : []

  return (
    <div
      className="mx-auto flex max-w-7xl flex-col gap-6 p-6"
      data-testid="registry-debug-page"
    >
      {/* ── Page header ────────────────────────────────── */}
      <header className="flex flex-col gap-2">
        <h1 className="text-h2 font-plex-serif font-medium text-content-strong">
          Component Registry
        </h1>
        <p className="text-body-sm text-content-muted">
          Phase 1 of the Admin Visual Editor. Inspect tagged components +
          their declared metadata + token consumption.
        </p>
      </header>

      {/* ── Coverage summary ──────────────────────────── */}
      <section
        className="grid grid-cols-1 gap-4 md:grid-cols-3"
        data-testid="registry-coverage"
      >
        <Card>
          <CardHeader>
            <CardTitle>Total registered</CardTitle>
          </CardHeader>
          <CardContent>
            <div
              className="text-display font-plex-serif text-content-strong"
              data-testid="registry-total-count"
            >
              {all.length}
            </div>
            <p className="text-caption text-content-muted">components</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>By type</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-1">
              {COMPONENT_KINDS.filter((k) => (countByType[k] ?? 0) > 0).map(
                (kind) => (
                  <li
                    key={kind}
                    className="flex items-center justify-between text-body-sm"
                    data-testid={`registry-count-type-${kind}`}
                  >
                    <span className="text-content-base">{kind}</span>
                    <Badge variant="secondary">{countByType[kind] ?? 0}</Badge>
                  </li>
                ),
              )}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>By vertical</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-1">
              {VERTICALS.map((v) => (
                <li
                  key={v}
                  className="flex items-center justify-between text-body-sm"
                  data-testid={`registry-coverage-${v}`}
                >
                  <span className="text-content-base">{v}</span>
                  <Badge variant="secondary">
                    {coverageByVertical[v] ?? 0}
                  </Badge>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </section>

      {/* ── Filters ───────────────────────────────────── */}
      <section
        className="flex flex-wrap items-end gap-3"
        data-testid="registry-filters"
      >
        <label className="flex flex-col gap-1">
          <span className="text-caption text-content-muted">Type</span>
          <select
            data-testid="registry-filter-type"
            className="rounded-md border border-border-base bg-surface-raised px-3 py-2 text-body-sm text-content-strong"
            value={typeFilter}
            onChange={(e) =>
              setTypeFilter(e.target.value as ComponentKind | "all")
            }
          >
            <option value="all">All types</option>
            {COMPONENT_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {kind}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-caption text-content-muted">Vertical</span>
          <select
            data-testid="registry-filter-vertical"
            className="rounded-md border border-border-base bg-surface-raised px-3 py-2 text-body-sm text-content-strong"
            value={verticalFilter}
            onChange={(e) =>
              setVerticalFilter(e.target.value as VerticalScope | "any")
            }
          >
            <option value="any">Any vertical</option>
            {VERTICALS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 flex-grow min-w-[200px]">
          <span className="text-caption text-content-muted">Search</span>
          <Input
            data-testid="registry-filter-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="name / displayName / description"
          />
        </label>

        <div className="text-body-sm text-content-muted">
          Showing{" "}
          <span
            data-testid="registry-filtered-count"
            className="font-plex-mono text-content-strong"
          >
            {filtered.length}
          </span>{" "}
          of {all.length}
        </div>
      </section>

      {/* ── Component table ───────────────────────────── */}
      <section data-testid="registry-table-section">
        <Card>
          <CardHeader>
            <CardTitle>Components</CardTitle>
          </CardHeader>
          <CardContent>
            {filtered.length === 0 ? (
              <p className="text-body-sm text-content-muted">
                No components match the current filters.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table
                  className="w-full text-left text-body-sm"
                  data-testid="registry-table"
                >
                  <thead>
                    <tr className="border-b border-border-subtle text-micro uppercase tracking-wider text-content-muted">
                      <th className="px-3 py-2">Display name</th>
                      <th className="px-3 py-2">Type</th>
                      <th className="px-3 py-2">Name</th>
                      <th className="px-3 py-2">Verticals</th>
                      <th className="px-3 py-2">Tokens</th>
                      <th className="px-3 py-2">Schema v.</th>
                      <th className="px-3 py-2">Comp. v.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((entry) => (
                      <tr
                        key={`${entry.metadata.type}:${entry.metadata.name}`}
                        data-testid={`registry-row-${entry.metadata.type}-${entry.metadata.name}`}
                        className="cursor-pointer border-b border-border-subtle/50 hover:bg-accent-subtle"
                        onClick={() => setSelected(entry)}
                      >
                        <td className="px-3 py-2 text-content-strong">
                          {entry.metadata.displayName}
                        </td>
                        <td className="px-3 py-2">
                          <Badge variant="outline">
                            {entry.metadata.type}
                          </Badge>
                        </td>
                        <td className="px-3 py-2 font-plex-mono text-caption text-content-muted">
                          {entry.metadata.name}
                        </td>
                        <td className="px-3 py-2 text-content-muted">
                          {entry.metadata.verticals.join(", ")}
                        </td>
                        <td className="px-3 py-2 font-plex-mono text-caption text-content-muted">
                          {entry.metadata.consumedTokens.length}
                        </td>
                        <td className="px-3 py-2 font-plex-mono text-caption text-content-muted">
                          {entry.metadata.schemaVersion}
                        </td>
                        <td className="px-3 py-2 font-plex-mono text-caption text-content-muted">
                          {entry.metadata.componentVersion}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {/* ── Detail drawer ─────────────────────────────── */}
      {selected && (
        <ComponentDetail
          entry={selected}
          onClose={() => setSelected(null)}
          onTokenInspect={(tok) => setTokenInspect(tok)}
        />
      )}

      {/* ── Token inverse-lookup ──────────────────────── */}
      <section data-testid="registry-tokens-section">
        <Card>
          <CardHeader>
            <CardTitle>Tokens consumed across the registry</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-body-sm text-content-muted mb-3">
              Click a token to see which components read from it. The editor
              uses this to show "changing this token affects N components"
              before the user commits a token edit.
            </p>
            {knownTokens.length === 0 ? (
              <p className="text-body-sm text-content-muted">
                No tokens registered yet.
              </p>
            ) : (
              <div
                className="flex flex-wrap gap-2"
                data-testid="registry-known-tokens"
              >
                {knownTokens.map((tok) => (
                  <button
                    key={tok}
                    type="button"
                    data-testid={`registry-token-${tok}`}
                    onClick={() =>
                      setTokenInspect((cur) => (cur === tok ? null : tok))
                    }
                    className={`rounded-sm border px-2 py-1 font-plex-mono text-caption transition-colors ${
                      tokenInspect === tok
                        ? "border-accent bg-accent-subtle text-content-strong"
                        : "border-border-base bg-surface-raised text-content-base hover:bg-accent-subtle"
                    }`}
                  >
                    {tok}
                  </button>
                ))}
              </div>
            )}

            {tokenInspect && (
              <div
                className="mt-4 rounded-md border border-border-subtle bg-surface-sunken p-3"
                data-testid="registry-token-inspect"
              >
                <div className="flex items-center justify-between mb-2">
                  <p className="text-body-sm text-content-strong">
                    Components reading <code>{tokenInspect}</code>:{" "}
                    <span
                      className="font-plex-mono"
                      data-testid="registry-token-consumer-count"
                    >
                      {tokenInspectEntries.length}
                    </span>
                  </p>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setTokenInspect(null)}
                  >
                    Clear
                  </Button>
                </div>
                {tokenInspectEntries.length === 0 ? (
                  <p className="text-caption text-content-muted">
                    No components consume this token.
                  </p>
                ) : (
                  <ul className="flex flex-col gap-1">
                    {tokenInspectEntries.map((entry) => (
                      <li
                        key={`${entry.metadata.type}:${entry.metadata.name}`}
                        className="text-body-sm"
                        data-testid={`registry-token-consumer-${entry.metadata.type}-${entry.metadata.name}`}
                      >
                        <Badge variant="outline" className="mr-2">
                          {entry.metadata.type}
                        </Badge>
                        <span className="text-content-strong">
                          {entry.metadata.displayName}
                        </span>{" "}
                        <code className="font-plex-mono text-caption text-content-muted">
                          {entry.metadata.name}
                        </code>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  )
}


// ─── Detail drawer ───────────────────────────────────────────────

interface ComponentDetailProps {
  entry: RegistryEntry
  onClose: () => void
  onTokenInspect: (token: string) => void
}

function ComponentDetail({
  entry,
  onClose,
  onTokenInspect,
}: ComponentDetailProps) {
  const { metadata, registeredAt } = entry
  const tokens = useMemo(() => {
    const seen = new Set<string>(metadata.consumedTokens)
    for (const v of metadata.variants ?? []) {
      for (const t of v.additionalConsumedTokens ?? []) seen.add(t)
    }
    return Array.from(seen).sort()
  }, [metadata])

  const propEntries = Object.entries(metadata.configurableProps ?? {})

  return (
    <Card data-testid="registry-detail">
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle data-testid="registry-detail-title">
              {metadata.displayName}
            </CardTitle>
            <p
              className="text-caption text-content-muted font-plex-mono mt-1"
              data-testid="registry-detail-id"
            >
              {metadata.type} · {metadata.name}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-5">
          {metadata.description && (
            <p className="text-body text-content-base">
              {metadata.description}
            </p>
          )}

          <DetailRow label="Category" value={metadata.category ?? "—"} />
          <DetailRow
            label="Verticals"
            value={metadata.verticals.join(", ")}
          />
          <DetailRow
            label="User paradigms"
            value={metadata.userParadigms.join(", ")}
          />
          {metadata.productLines && metadata.productLines.length > 0 && (
            <DetailRow
              label="Product lines"
              value={metadata.productLines.join(", ")}
            />
          )}
          <DetailRow
            label="Schema version"
            value={String(metadata.schemaVersion)}
          />
          <DetailRow
            label="Component version"
            value={String(metadata.componentVersion)}
          />
          <DetailRow
            label="Registered"
            value={formatRelative(registeredAt)}
          />

          {/* Tokens */}
          <div data-testid="registry-detail-tokens">
            <p className="text-micro uppercase tracking-wider text-content-muted mb-2">
              Tokens consumed ({tokens.length})
            </p>
            <div className="flex flex-wrap gap-1.5">
              {tokens.map((tok) => (
                <button
                  key={tok}
                  type="button"
                  onClick={() => onTokenInspect(tok)}
                  className="rounded-sm border border-border-base bg-surface-raised px-2 py-0.5 font-plex-mono text-caption text-content-base hover:bg-accent-subtle"
                >
                  {tok}
                </button>
              ))}
            </div>
          </div>

          {/* Configurable props */}
          {propEntries.length > 0 && (
            <div data-testid="registry-detail-props">
              <p className="text-micro uppercase tracking-wider text-content-muted mb-2">
                Configurable props ({propEntries.length})
              </p>
              <ul className="flex flex-col gap-2">
                {propEntries.map(([key, schema]) => (
                  <li
                    key={key}
                    className="rounded-md border border-border-subtle bg-surface-sunken p-2"
                  >
                    <div className="flex items-center gap-2">
                      <code className="font-plex-mono text-caption text-content-strong">
                        {key}
                      </code>
                      <Badge variant="outline">{schema.type}</Badge>
                      {schema.required && (
                        <Badge variant="warning">required</Badge>
                      )}
                    </div>
                    {schema.description && (
                      <p className="text-caption text-content-muted mt-1">
                        {schema.description}
                      </p>
                    )}
                    <p className="text-caption text-content-muted mt-1">
                      Default:{" "}
                      <code className="font-plex-mono">
                        {JSON.stringify(schema.default)}
                      </code>
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Variants */}
          {metadata.variants && metadata.variants.length > 0 && (
            <div data-testid="registry-detail-variants">
              <p className="text-micro uppercase tracking-wider text-content-muted mb-2">
                Variants ({metadata.variants.length})
              </p>
              <ul className="flex flex-col gap-1">
                {metadata.variants.map((v) => (
                  <li key={v.name} className="text-body-sm">
                    <code className="font-plex-mono text-caption text-content-strong">
                      {v.name}
                    </code>
                    {v.displayLabel && (
                      <span className="text-content-muted ml-2">
                        — {v.displayLabel}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Slots */}
          {metadata.slots && metadata.slots.length > 0 && (
            <div data-testid="registry-detail-slots">
              <p className="text-micro uppercase tracking-wider text-content-muted mb-2">
                Slots ({metadata.slots.length})
              </p>
              <ul className="flex flex-col gap-2">
                {metadata.slots.map((s) => (
                  <li
                    key={s.name}
                    className="rounded-md border border-border-subtle bg-surface-sunken p-2"
                  >
                    <code className="font-plex-mono text-caption text-content-strong">
                      {s.name}
                    </code>
                    {s.description && (
                      <p className="text-caption text-content-muted mt-1">
                        {s.description}
                      </p>
                    )}
                    <p className="text-caption text-content-muted mt-1">
                      Accepts:{" "}
                      {s.acceptedTypes.length === 0
                        ? "any registered type"
                        : s.acceptedTypes.join(", ")}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Extensions */}
          {metadata.extensions && Object.keys(metadata.extensions).length > 0 && (
            <div data-testid="registry-detail-extensions">
              <p className="text-micro uppercase tracking-wider text-content-muted mb-2">
                Extensions
              </p>
              <pre className="rounded-md border border-border-subtle bg-surface-sunken p-2 font-plex-mono text-caption text-content-base overflow-x-auto">
                {JSON.stringify(metadata.extensions, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}


function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-3">
      <span className="text-micro uppercase tracking-wider text-content-muted min-w-[140px]">
        {label}
      </span>
      <span className="text-body-sm text-content-strong">{value}</span>
    </div>
  )
}
