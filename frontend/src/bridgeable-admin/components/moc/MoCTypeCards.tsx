/**
 * Maps of Content — per-type linked cards (MoC manufacturing polish, Phase A).
 *
 * Replaces the flat LinkedTable list on the MoC PAGE surface with the Notion
 * model's structure: a row of titled cards, ONE per builder TYPE present in
 * the map (Workflows / Focuses / Widgets / Documents today — but rendered
 * DATA-DRIVEN from the grouped input, so a 5th type or a 2nd artifact-in-a-type
 * appears with no code change). Each card header signals "link out" (underlined
 * + up-right arrow, per the Notion convention); each entry is a hyperlink into
 * that artifact's own builder (href already mocDeepLink→adminPath'd by the
 * caller). Orphan-tolerant per DESIGN_LANGUAGE §18 — an unavailable entry
 * renders muted, never a dead link.
 *
 * Purely presentational (no router/service coupling beyond <Link>) — the MoC
 * page groups rows by builder and hands cards in. The home keeps LinkedTable.
 */

import { Link } from "react-router-dom"
import { ArrowUpRight, FileText, type LucideIcon } from "lucide-react"

import { Icon } from "@/components/ui/icon"
import { EmptyState } from "@/components/ui/empty-state"

export interface MoCTypeCardEntry {
  row_id: string
  label: string
  /** Already adminPath-wrapped; null = not linkable (orphan / unavailable). */
  href: string | null
  available: boolean
  unavailableReason?: "orphan" | "not-built"
}

export interface MoCTypeCard {
  /** The builder key (workflows / focuses / widgets / documents / future). */
  builder: string
  /** The card title — the plural type name (e.g. "Workflows"). */
  title: string
  icon?: LucideIcon
  entries: MoCTypeCardEntry[]
}

export interface MoCTypeCardsProps {
  cards: MoCTypeCard[]
  emptyTitle?: string
  emptyDescription?: string
  "data-testid"?: string
}

export function MoCTypeCards({
  cards,
  emptyTitle = "Nothing here yet",
  emptyDescription,
  "data-testid": testId,
}: MoCTypeCardsProps) {
  const visibleCards = cards.filter((c) => c.entries.length > 0)
  if (visibleCards.length === 0) {
    return (
      <EmptyState
        variant="quiet"
        title={emptyTitle}
        description={emptyDescription}
        data-testid={testId ? `${testId}-empty` : undefined}
      />
    )
  }

  return (
    // All type-cards on ONE row at EQUAL width: N equal columns where N = the
    // number of cards present (data-driven — a 5th type stays equal-width 1/5,
    // never wraps). gap-4 = the dashboard 16px grid gap. minmax(0,1fr) lets
    // columns shrink rather than overflow on narrower-but-still-wide viewports.
    <div
      className="grid gap-4"
      style={{
        gridTemplateColumns: `repeat(${visibleCards.length}, minmax(0, 1fr))`,
      }}
      data-testid={testId}
    >
      {visibleCards.map((card) => (
        <TypeCard key={card.builder} card={card} />
      ))}
    </div>
  )
}

function TypeCard({ card }: { card: MoCTypeCard }) {
  const TypeIcon = card.icon ?? FileText
  return (
    <section
      className="rounded-lg border border-border-subtle bg-surface-elevated p-4 shadow-level-1"
      data-testid={`moc-type-card-${card.builder}`}
    >
      {/* Header signals "link out" — underlined type name + up-right arrow. */}
      <div className="mb-3 flex items-center gap-2 border-b border-border-subtle pb-2">
        <Icon icon={TypeIcon} size={16} className="text-content-muted" />
        <h3 className="text-body-sm font-medium text-content-base underline decoration-border-strong underline-offset-4">
          {card.title}
        </h3>
        <Icon icon={ArrowUpRight} size={14} className="text-content-subtle" />
      </div>
      <ul className="space-y-1">
        {card.entries.map((entry) => (
          // testid + data-available co-located (the orphan-tolerance contract
          // the MoC e2e asserts): `moc-row-<id>` with data-available true|false.
          <li
            key={entry.row_id}
            data-testid={`moc-row-${entry.row_id}`}
            data-available={entry.available}
          >
            <TypeCardEntry entry={entry} />
          </li>
        ))}
      </ul>
    </section>
  )
}

function TypeCardEntry({ entry }: { entry: MoCTypeCardEntry }) {
  const linkable = entry.available && entry.href !== null
  if (linkable) {
    return (
      <Link
        to={entry.href as string}
        className="focus-ring-accent flex items-center gap-1.5 rounded-sm py-0.5 text-body-sm text-content-base hover:text-accent"
        data-available="true"
      >
        {entry.label}
        <ArrowUpRight size={12} className="opacity-0 transition-opacity group-hover:opacity-60" />
      </Link>
    )
  }
  return (
    <span
      className="flex items-center gap-2 py-0.5 text-body-sm text-content-subtle"
      data-available="false"
    >
      {entry.label}
      <span className="text-caption">
        {entry.unavailableReason === "not-built"
          ? "· no map yet"
          : "· no longer available"}
      </span>
    </span>
  )
}
