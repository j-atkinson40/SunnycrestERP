/**
 * Maps of Content — LinkedTable.
 *
 * The Notion-like linked table shared by the MoC page surface and the
 * home dashboard. Purely presentational: each row arrives with its glyph
 * (`icon`), a right-column `kindLabel`, an already-computed `href`
 * (mocDeepLink → adminPath, by the caller) and an `available` flag — so
 * this component has no router/adminPath/builder coupling and is
 * unit-testable in isolation. The MoC page maps builder→glyph; the home
 * maps page→glyph; the rendering is identical (investigation §C/§E).
 *
 * Orphan-tolerant render (DESIGN_LANGUAGE §18): a row whose target is
 * unavailable renders muted + "no longer available", never a dead link.
 */

import { Link } from "react-router-dom"
import { FileText, type LucideIcon } from "lucide-react"

import { Icon } from "@/components/ui/icon"
import { EmptyState } from "@/components/ui/empty-state"
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table"

export interface LinkedTableRow {
  row_id: string
  label: string
  /** Already adminPath-wrapped; null = not linkable (orphan / unavailable). */
  href: string | null
  available: boolean
  /** Row glyph; defaults to FileText. */
  icon?: LucideIcon
  /** Right-column kind tag (e.g. "Workflow", "Map"). */
  kindLabel?: string
}

export interface LinkedTableSection {
  section_id: string
  title: string
  description?: string | null
  rows: LinkedTableRow[]
}

export interface LinkedTableProps {
  sections: LinkedTableSection[]
  emptyTitle?: string
  emptyDescription?: string
  "data-testid"?: string
}

function hasAnyRow(sections: LinkedTableSection[]): boolean {
  return sections.some((s) => s.rows.length > 0)
}

export function LinkedTable({
  sections,
  emptyTitle = "Nothing here yet",
  emptyDescription,
  "data-testid": testId,
}: LinkedTableProps) {
  if (!hasAnyRow(sections)) {
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
    <div className="space-y-6" data-testid={testId}>
      {sections.map((section) => (
        <section key={section.section_id} className="space-y-2">
          <div>
            <h3 className="text-body-sm font-medium text-content-base">
              {section.title}
            </h3>
            {section.description ? (
              <p className="text-caption text-content-muted">
                {section.description}
              </p>
            ) : null}
          </div>
          <Table>
            <TableBody>
              {section.rows.map((row) => (
                <LinkedRow key={row.row_id} row={row} />
              ))}
            </TableBody>
          </Table>
        </section>
      ))}
    </div>
  )
}

function LinkedRow({ row }: { row: LinkedTableRow }) {
  const glyph = row.icon ?? FileText
  const linkable = row.available && row.href !== null

  return (
    <TableRow
      data-testid={`moc-row-${row.row_id}`}
      data-available={row.available}
    >
      <TableCell className="w-10">
        <Icon
          icon={glyph}
          size={16}
          className={linkable ? "text-content-muted" : "text-content-subtle"}
        />
      </TableCell>
      <TableCell>
        {linkable ? (
          <Link
            to={row.href as string}
            className="text-content-base hover:text-accent focus-ring-accent rounded-sm"
          >
            {row.label}
          </Link>
        ) : (
          <span className="flex items-center gap-2 text-content-subtle">
            {row.label}
            <span className="text-caption">· no longer available</span>
          </span>
        )}
      </TableCell>
      {row.kindLabel ? (
        <TableCell className="text-right text-caption text-content-subtle">
          {row.kindLabel}
        </TableCell>
      ) : null}
    </TableRow>
  )
}
