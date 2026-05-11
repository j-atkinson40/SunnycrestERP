/**
 * R-8.y.d — Plugin Registry browser.
 *
 * Surfaces all 24 canonical plugin categories from
 * PLUGIN_CONTRACTS.md grouped by maturity (canonical → partial →
 * implicit). Per-category detail renders the 8-section canonical
 * contract content + a live introspection panel when the registry
 * is enumerable.
 *
 * Built-time snapshot is imported from
 * `frontend/src/lib/plugin-registry/plugin-contracts-snapshot.json`.
 * Live state via the admin endpoint at
 * `/api/platform/admin/plugin-registry/categories/{key}/registrations`.
 *
 * Pattern: documentation-as-canonical-data — PLUGIN_CONTRACTS.md
 * is the source of truth; codegen produces the JSON snapshot the
 * frontend reads at build time; CI ensures snapshot drift fails the
 * build. Future migrations promote categories from non-introspectable
 * to introspectable without touching the UI.
 */

import { useEffect, useMemo, useState } from "react"
import type { JSX } from "react"

import snapshotJson from "@/lib/plugin-registry/plugin-contracts-snapshot.json"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"

import { MarkdownContent } from "@/bridgeable-admin/components/MarkdownContent"
import {
  getCategoryRegistrations,
  PluginRegistryError,
  type CategoryRegistrationsResponse,
} from "@/bridgeable-admin/lib/plugin-registry-client"


// ─── Snapshot typing ─────────────────────────────────────────────────


interface CategoryContract {
  section_number: number
  title: string
  maturity_badge: string
  maturity_group: "canonical" | "partial" | "implicit"
  anchor: string
  purpose: string
  summary: string
  input_contract: string
  output_contract: string
  guarantees: string
  failure_modes: string
  configuration_shape: string
  registration_mechanism: string
  current_implementations: string
  cross_references: string
  current_divergences: string
  optional_subsections: Record<string, string>
  tier_hint: string
}


interface Snapshot {
  schema_version: number
  document_version: string
  total_count: number
  canonical_count: number
  partial_count: number
  implicit_count: number
  categories: CategoryContract[]
}


const SNAPSHOT = snapshotJson as Snapshot


type MaturityFilter = "all" | "canonical" | "partial" | "implicit"


// ─── Page ────────────────────────────────────────────────────────────


export default function PluginRegistryBrowser() {
  const [search, setSearch] = useState("")
  const [maturity, setMaturity] = useState<MaturityFilter>("all")
  const [selectedSection, setSelectedSection] = useState<number | null>(null)

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase()
    return SNAPSHOT.categories.filter((c) => {
      if (maturity !== "all" && c.maturity_group !== maturity) return false
      if (term) {
        const hay = `${c.title} §${c.section_number} ${c.summary} ${c.maturity_badge}`.toLowerCase()
        if (!hay.includes(term)) return false
      }
      return true
    })
  }, [search, maturity])

  const grouped = useMemo(() => {
    const canonical = filtered.filter((c) => c.maturity_group === "canonical")
    const partial = filtered.filter((c) => c.maturity_group === "partial")
    const implicit = filtered.filter((c) => c.maturity_group === "implicit")
    return { canonical, partial, implicit }
  }, [filtered])

  const selected = useMemo(() => {
    if (selectedSection === null) return null
    return SNAPSHOT.categories.find(
      (c) => c.section_number === selectedSection,
    )
  }, [selectedSection])

  return (
    <div
      className="mx-auto flex max-w-7xl flex-col gap-6 p-6"
      data-testid="plugin-registry-browser"
    >
      {/* ─── Header ─────────────────────────────────────────── */}
      <header className="flex flex-col gap-2">
        <h1 className="text-h2 font-plex-serif font-medium text-content-strong">
          Plugin Registry
        </h1>
        <p className="text-body-sm text-content-muted">
          {SNAPSHOT.total_count} canonical plugin categories from{" "}
          <code className="font-plex-mono text-content-strong">
            PLUGIN_CONTRACTS.md
          </code>{" "}
          (document v{SNAPSHOT.document_version}). Operator-facing
          architectural-surface documentation; live introspection where
          the runtime registry enumerates.
        </p>
      </header>

      {/* ─── Maturity stat cards ───────────────────────────── */}
      <section
        className="grid grid-cols-1 gap-4 md:grid-cols-4"
        data-testid="plugin-registry-stats"
      >
        <Card>
          <CardHeader>
            <CardTitle>Total</CardTitle>
          </CardHeader>
          <CardContent>
            <div
              className="text-display font-plex-serif text-content-strong"
              data-testid="plugin-registry-total-count"
            >
              {SNAPSHOT.total_count}
            </div>
            <p className="text-caption text-content-muted">categories</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Canonical</CardTitle>
          </CardHeader>
          <CardContent>
            <div
              className="text-display font-plex-serif text-content-strong"
              data-testid="plugin-registry-canonical-count"
            >
              {SNAPSHOT.canonical_count}
            </div>
            <p className="text-caption text-content-muted">
              ✓ contract matches substrate
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Partial</CardTitle>
          </CardHeader>
          <CardContent>
            <div
              className="text-display font-plex-serif text-content-strong"
              data-testid="plugin-registry-partial-count"
            >
              {SNAPSHOT.partial_count}
            </div>
            <p className="text-caption text-content-muted">
              ~ documented divergences
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Implicit</CardTitle>
          </CardHeader>
          <CardContent>
            <div
              className="text-display font-plex-serif text-content-strong"
              data-testid="plugin-registry-implicit-count"
            >
              {SNAPSHOT.implicit_count}
            </div>
            <p className="text-caption text-content-muted">
              ~ pattern, no canonical registry yet
            </p>
          </CardContent>
        </Card>
      </section>

      {/* ─── Filter row ────────────────────────────────────── */}
      <section
        className="flex flex-wrap items-end gap-3"
        data-testid="plugin-registry-filters"
      >
        <label className="flex flex-col gap-1">
          <span className="text-caption text-content-muted">Maturity</span>
          <select
            data-testid="plugin-registry-maturity-filter"
            value={maturity}
            onChange={(e) => setMaturity(e.target.value as MaturityFilter)}
            className="rounded-md border border-border-base bg-surface-raised px-3 py-2 text-body-sm text-content-strong"
          >
            <option value="all">All groups</option>
            <option value="canonical">Canonical only</option>
            <option value="partial">Partial only</option>
            <option value="implicit">Implicit only</option>
          </select>
        </label>
        <label className="flex flex-grow min-w-[240px] flex-col gap-1">
          <span className="text-caption text-content-muted">Search</span>
          <Input
            data-testid="plugin-registry-search-input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="title / section number / summary"
          />
        </label>
        <div className="text-body-sm text-content-muted">
          Showing{" "}
          <span
            data-testid="plugin-registry-filtered-count"
            className="font-plex-mono text-content-strong"
          >
            {filtered.length}
          </span>{" "}
          of {SNAPSHOT.total_count}
        </div>
      </section>

      {/* ─── Grouped category list ─────────────────────────── */}
      <section data-testid="plugin-registry-groups" className="flex flex-col gap-6">
        <MaturityGroup
          title="Canonical"
          subtitle="Contract canonical — substrate matches documented contract."
          categories={grouped.canonical}
          onSelect={setSelectedSection}
          selectedSection={selectedSection}
          testId="plugin-registry-group-canonical"
        />
        <MaturityGroup
          title="Partial"
          subtitle="Contract partial — see Current Divergences subsection."
          categories={grouped.partial}
          onSelect={setSelectedSection}
          selectedSection={selectedSection}
          testId="plugin-registry-group-partial"
        />
        <MaturityGroup
          title="Implicit"
          subtitle="Contract implicit pattern — substrate works but canonical registry promotion lags."
          categories={grouped.implicit}
          onSelect={setSelectedSection}
          selectedSection={selectedSection}
          testId="plugin-registry-group-implicit"
        />
      </section>

      {/* ─── Detail view ───────────────────────────────────── */}
      {selected && (
        <CategoryDetail
          category={selected}
          onClose={() => setSelectedSection(null)}
          onSectionJump={(n) => setSelectedSection(n)}
        />
      )}
    </div>
  )
}


// ─── Maturity group ─────────────────────────────────────────────────


interface MaturityGroupProps {
  title: string
  subtitle: string
  categories: CategoryContract[]
  onSelect: (sectionNumber: number) => void
  selectedSection: number | null
  testId: string
}


function MaturityGroup({
  title,
  subtitle,
  categories,
  onSelect,
  selectedSection,
  testId,
}: MaturityGroupProps) {
  if (categories.length === 0) return null
  return (
    <div data-testid={testId}>
      <div className="mb-2 flex items-baseline gap-3">
        <h2 className="text-h4 font-plex-serif font-medium text-content-strong">
          {title}
        </h2>
        <span className="text-caption text-content-muted">
          ({categories.length})
        </span>
      </div>
      <p className="mb-3 text-caption text-content-muted">{subtitle}</p>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {categories.map((c) => (
          <CategoryCard
            key={c.section_number}
            category={c}
            selected={selectedSection === c.section_number}
            onClick={() => onSelect(c.section_number)}
          />
        ))}
      </div>
    </div>
  )
}


// ─── Category card ──────────────────────────────────────────────────


interface CategoryCardProps {
  category: CategoryContract
  selected: boolean
  onClick: () => void
}


function CategoryCard({ category, selected, onClick }: CategoryCardProps) {
  const badgeVariant: "success" | "warning" | "secondary" =
    category.maturity_group === "canonical"
      ? "success"
      : category.maturity_group === "partial"
        ? "warning"
        : "secondary"
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={`plugin-registry-category-card-${category.section_number}`}
      data-section={category.section_number}
      data-selected={selected ? "true" : "false"}
      data-maturity={category.maturity_group}
      className={
        selected
          ? "flex flex-col gap-2 rounded-md border-2 border-accent bg-accent-subtle p-4 text-left"
          : "flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-elevated p-4 text-left hover:border-accent/40"
      }
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <span className="font-plex-mono text-caption text-content-muted">
            §{category.section_number}
          </span>
          <span className="text-body font-medium text-content-strong">
            {category.title}
          </span>
        </div>
        <Badge variant={badgeVariant}>{category.maturity_group}</Badge>
      </div>
      <p className="text-body-sm text-content-muted">
        {truncate(category.summary, 200)}
      </p>
      {category.tier_hint && (
        <div className="flex items-center gap-2">
          <Badge variant="outline">tier {category.tier_hint}</Badge>
        </div>
      )}
    </button>
  )
}


// ─── Detail view ────────────────────────────────────────────────────


interface CategoryDetailProps {
  category: CategoryContract
  onClose: () => void
  onSectionJump: (sectionNumber: number) => void
}


function CategoryDetail({
  category,
  onClose,
  onSectionJump,
}: CategoryDetailProps) {
  return (
    <Card data-testid="plugin-registry-detail">
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardTitle data-testid="plugin-registry-detail-title">
              §{category.section_number} {category.title}
            </CardTitle>
            <p className="mt-1 text-caption text-content-muted">
              {category.maturity_badge}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-5">
          <DetailSection
            label="Purpose"
            content={category.purpose}
            onSectionJump={onSectionJump}
          />
          <DetailSection
            label="Input Contract"
            content={category.input_contract}
            onSectionJump={onSectionJump}
          />
          <DetailSection
            label="Output Contract"
            content={category.output_contract}
            onSectionJump={onSectionJump}
          />
          <DetailSection
            label="Guarantees"
            content={category.guarantees}
            onSectionJump={onSectionJump}
          />
          <DetailSection
            label="Failure Modes"
            content={category.failure_modes}
            onSectionJump={onSectionJump}
          />
          <DetailSection
            label="Configuration Shape"
            content={category.configuration_shape}
            onSectionJump={onSectionJump}
          />
          <DetailSection
            label="Registration Mechanism"
            content={category.registration_mechanism}
            onSectionJump={onSectionJump}
          />
          {category.current_divergences && (
            <DetailSection
              label="Current Divergences from Canonical"
              content={category.current_divergences}
              onSectionJump={onSectionJump}
            />
          )}
          <DetailSection
            label="Current Implementations"
            content={category.current_implementations}
            onSectionJump={onSectionJump}
          />
          <DetailSection
            label="Cross-References"
            content={category.cross_references}
            onSectionJump={onSectionJump}
          />

          {/* Live introspection panel */}
          <IntrospectionPanel
            categoryKey={categoryKeyFor(category)}
            sectionNumber={category.section_number}
          />
        </div>
      </CardContent>
    </Card>
  )
}


// ─── Detail section ─────────────────────────────────────────────────


interface DetailSectionProps {
  label: string
  content: string
  onSectionJump: (sectionNumber: number) => void
}


function DetailSection({ label, content, onSectionJump }: DetailSectionProps) {
  if (!content) return null
  return (
    <div>
      <p className="mb-2 text-micro uppercase tracking-wider text-content-muted">
        {label}
      </p>
      <MarkdownContent
        content={content}
        onCrossReferenceClick={onSectionJump}
      />
    </div>
  )
}


// ─── Live introspection panel ───────────────────────────────────────


interface IntrospectionPanelProps {
  categoryKey: string
  sectionNumber: number
}


function IntrospectionPanel({
  categoryKey,
  sectionNumber,
}: IntrospectionPanelProps) {
  const [data, setData] = useState<CategoryRegistrationsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setData(null)
    getCategoryRegistrations(categoryKey)
      .then((d) => {
        if (!cancelled) setData(d)
      })
      .catch((err: PluginRegistryError | Error) => {
        if (cancelled) return
        const msg =
          err instanceof PluginRegistryError
            ? `${err.status}: ${err.message}`
            : err.message
        setError(msg)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [categoryKey])

  if (loading) {
    return (
      <div
        className="rounded-md border border-border-subtle bg-surface-sunken p-3"
        data-testid="plugin-registry-introspection-panel"
        data-state="loading"
      >
        <p className="text-caption text-content-muted">Loading registry…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div
        className="rounded-md border border-status-warning bg-status-warning-muted p-3"
        data-testid="plugin-registry-introspection-panel"
        data-state="error"
      >
        <p className="text-body-sm text-status-warning">
          Introspection failed: {error}
        </p>
      </div>
    )
  }

  if (!data) return null

  if (!data.registry_introspectable) {
    return (
      <div
        className="rounded-md border border-border-base bg-surface-sunken p-3"
        data-testid="plugin-registry-static-only-banner"
        data-section={sectionNumber}
      >
        <p className="mb-2 text-micro uppercase tracking-wider text-content-muted">
          Live registry — static only
        </p>
        <p className="text-body-sm text-content-base">{data.reason}</p>
        {data.expected_implementations_count > 0 && (
          <p className="mt-2 text-caption text-content-muted">
            Expected implementations:{" "}
            <code className="font-plex-mono text-content-strong">
              {data.expected_implementations_count}
            </code>
            {data.tier_hint && (
              <>
                {" · "}tier{" "}
                <code className="font-plex-mono text-content-strong">
                  {data.tier_hint}
                </code>
              </>
            )}
          </p>
        )}
      </div>
    )
  }

  return (
    <div
      className="rounded-md border border-status-success bg-status-success-muted/30 p-3"
      data-testid="plugin-registry-introspection-panel"
      data-state="live"
      data-registry-size={data.registry_size}
    >
      <div className="mb-2 flex items-baseline justify-between">
        <p className="text-micro uppercase tracking-wider text-content-muted">
          Live registry state
        </p>
        <span className="font-plex-mono text-caption text-content-strong">
          {data.registry_size} {data.registry_size === 1 ? "entry" : "entries"}
        </span>
      </div>
      {data.registrations.length === 0 ? (
        <p className="text-caption text-content-muted">
          Registry is empty in this runtime.
        </p>
      ) : (
        <ul className="flex flex-col gap-1" data-testid="plugin-registry-live-list">
          {data.registrations.map((r) => (
            <li
              key={r.key}
              className="rounded-sm border border-border-subtle bg-surface-elevated p-2"
              data-testid={`plugin-registry-live-entry-${r.key}`}
            >
              <code className="font-plex-mono text-caption text-content-strong">
                {r.key}
              </code>
              {renderRegistrationMetadata(r.metadata)}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}


// ─── Helpers ────────────────────────────────────────────────────────


function truncate(s: string, n: number): string {
  if (!s) return ""
  if (s.length <= n) return s
  const cut = s.lastIndexOf(" ", n)
  if (cut < n / 2) return s.slice(0, n) + "…"
  return s.slice(0, cut) + "…"
}


function renderRegistrationMetadata(
  metadata: Record<string, unknown>,
): JSX.Element | null {
  const entries = Object.entries(metadata).filter(
    ([k]) => k !== "key" && k !== "kind" && k !== "template_type",
  )
  if (entries.length === 0) return null
  // Display the first 2-3 simple-typed entries inline. Skip
  // arrays/objects for compactness.
  const inline = entries
    .filter(([, v]) => typeof v === "string" || typeof v === "number")
    .slice(0, 2)
  if (inline.length === 0) return null
  return (
    <div className="mt-1 flex flex-wrap gap-2">
      {inline.map(([k, v]) => (
        <span key={k} className="text-caption text-content-muted">
          <code className="font-plex-mono">{k}</code>:{" "}
          <span className="text-content-base">{String(v)}</span>
        </span>
      ))}
    </div>
  )
}


// Map snapshot section number → backend category_key.
//
// Backend catalog keys are documented in
// `backend/app/services/plugin_registry/category_catalog.py` —
// each category_key matches the canonical PLUGIN_CONTRACTS.md
// section title in snake_case.
function categoryKeyFor(category: CategoryContract): string {
  const SECTION_TO_KEY: Record<number, string> = {
    1: "intake_adapters",
    2: "focus_composition_kinds",
    3: "widget_kinds",
    4: "document_blocks",
    5: "theme_tokens",
    6: "workshop_template_types",
    7: "composition_action_types",
    8: "accounting_providers",
    9: "email_providers",
    10: "playwright_scripts",
    11: "calendar_providers",
    12: "workflow_node_types",
    13: "intelligence_providers",
    14: "delivery_channels",
    15: "triage_queue_configs",
    16: "agent_kinds",
    17: "button_kinds",
    18: "intake_match_condition_operators",
    19: "notification_categories",
    20: "activity_log_event_types",
    21: "pdf_generator_callers",
    22: "page_contexts",
    23: "customer_classification_rules",
    24: "intent_classifiers",
  }
  return SECTION_TO_KEY[category.section_number] ?? "unknown"
}
