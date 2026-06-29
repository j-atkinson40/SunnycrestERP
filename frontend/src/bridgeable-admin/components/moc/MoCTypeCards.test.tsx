/**
 * MoC manufacturing polish Phase A — per-type cards.
 *
 * Covers the grouping/deep-link logic (toTypeCards) against the manufacturing
 * seed's shape (4 builders, 1 artifact each), the data-driven auto-grow (a 2nd
 * artifact in a type renders a 2nd entry — no code change), and the
 * presentational card render incl. orphan-tolerance.
 */
import { describe, expect, it } from "vitest"
import { render, screen, within } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"

import { toTypeCards } from "../../pages/moc/MoCPage"
import { MoCTypeCards } from "./MoCTypeCards"
import type {
  MoCResolvedPage,
  MoCResolvedRow,
} from "@/bridgeable-admin/services/moc-service"

function row(over: Partial<MoCResolvedRow> & { builder: string; row_id: string }): MoCResolvedRow {
  return {
    artifact_id: `${over.row_id}-artifact`,
    label: over.label ?? over.row_id,
    resolution: {
      exists: true,
      available: true,
      label: over.label ?? over.row_id,
      routing: {},
    },
    ...over,
  } as MoCResolvedRow
}

/** A page mirroring the manufacturing seed (1 each), plus optional extras. */
function mfgPage(extraRows: MoCResolvedRow[] = []): MoCResolvedPage {
  return {
    id: "page-1",
    scope: "vertical_default",
    vertical: "manufacturing",
    tenant_id: null,
    slug: "manufacturing-map",
    title: "Manufacturing",
    description: "Artifact-first navigation for the manufacturing floor.",
    sections: [
      {
        section_id: "s1",
        title: "Production",
        rows: [
          row({
            row_id: "r-wf",
            builder: "workflows",
            artifact_id: "wf-1",
            label: "Quote → Pour",
            resolution: {
              exists: true, available: true, label: "Quote → Pour",
              routing: { workflow_type: "quote_to_pour", scope: "vertical_default", vertical: "manufacturing" },
            },
          }),
          row({
            row_id: "r-foc",
            builder: "focuses",
            artifact_id: "foc-1",
            label: "Job Coordination",
            resolution: {
              exists: true, available: true, label: "Job Coordination",
              routing: { vertical: "manufacturing", template_slug: "job-coordination" },
            },
          }),
          row({
            row_id: "r-wid",
            builder: "widgets",
            artifact_id: "wid-row-1",
            label: "Accounts Receivable",
            resolution: {
              exists: true, available: true, label: "Accounts Receivable",
              routing: { widget_id: "ar_summary" },
            },
          }),
          row({
            row_id: "r-doc",
            builder: "documents",
            artifact_id: "doc-1",
            label: "Standard Quote",
            resolution: {
              exists: true, available: true, label: "Standard Quote",
              routing: { vertical: "manufacturing", template_key: "quote.standard" },
            },
          }),
          ...extraRows,
        ],
      },
    ],
  }
}

describe("toTypeCards — grouping + deep-links", () => {
  it("groups the manufacturing map into one card per builder type, canonical order", () => {
    const cards = toTypeCards(mfgPage())
    expect(cards.map((c) => c.builder)).toEqual([
      "workflows",
      "focuses",
      "widgets",
      "documents",
    ])
    expect(cards.map((c) => c.title)).toEqual([
      "Workflows",
      "Focuses",
      "Widgets",
      "Documents",
    ])
    expect(cards.every((c) => c.entries.length === 1)).toBe(true)
  })

  it("computes the correct builder deep-link + artifact id per type", () => {
    const byBuilder = Object.fromEntries(
      toTypeCards(mfgPage()).map((c) => [c.builder, c.entries[0]]),
    )
    expect(byBuilder.workflows.href).toContain("workflow_type=quote_to_pour")
    expect(byBuilder.focuses.href).toContain("tier=2")
    expect(byBuilder.focuses.href).toContain("template=foc-1")
    expect(byBuilder.widgets.href).toContain("widget-builder/ar_summary")
    expect(byBuilder.documents.href).toContain("template_id=doc-1")
    expect(Object.values(byBuilder).every((e) => e.available)).toBe(true)
  })

  it("is data-driven: a 2nd artifact in a type renders a 2nd entry (auto-grow)", () => {
    const cards = toTypeCards(
      mfgPage([
        row({
          row_id: "r-foc2",
          builder: "focuses",
          artifact_id: "foc-2",
          label: "Decision Triage",
          resolution: {
            exists: true, available: true, label: "Decision Triage",
            routing: { vertical: "manufacturing", template_slug: "decision-triage" },
          },
        }),
      ]),
    )
    const focuses = cards.find((c) => c.builder === "focuses")
    expect(focuses?.entries.map((e) => e.label)).toEqual([
      "Job Coordination",
      "Decision Triage",
    ])
  })

  it("marks an unresolved reference unavailable (orphan → null href)", () => {
    const cards = toTypeCards(
      mfgPage([
        row({
          row_id: "r-orphan",
          builder: "documents",
          artifact_id: "gone",
          label: "Removed Doc",
          resolution: { exists: false, available: false, label: "Removed Doc", routing: {} },
        }),
      ]),
    )
    const docs = cards.find((c) => c.builder === "documents")
    const orphan = docs?.entries.find((e) => e.row_id === "r-orphan")
    expect(orphan?.available).toBe(false)
    expect(orphan?.href).toBeNull()
  })
})

describe("MoCTypeCards — render", () => {
  function renderCards(page = mfgPage()) {
    return render(
      <MemoryRouter>
        <MoCTypeCards cards={toTypeCards(page)} data-testid="moc-type-cards" />
      </MemoryRouter>,
    )
  }

  it("renders a card per builder type with its artifact links", () => {
    renderCards()
    for (const builder of ["workflows", "focuses", "widgets", "documents"]) {
      expect(screen.getByTestId(`moc-type-card-${builder}`)).toBeTruthy()
    }
    const wfCard = screen.getByTestId("moc-type-card-workflows")
    const link = within(wfCard).getByRole("link", { name: /Quote → Pour/ })
    expect(link.getAttribute("href")).toContain("workflow_type=quote_to_pour")
  })

  it("renders an orphan entry muted (data-available=false), never a link", () => {
    renderCards(
      mfgPage([
        row({
          row_id: "r-orphan",
          builder: "documents",
          artifact_id: "gone",
          label: "Removed Doc",
          resolution: { exists: false, available: false, label: "Removed Doc", routing: {} },
        }),
      ]),
    )
    const orphan = screen.getByTestId("moc-row-r-orphan")
    expect(orphan.getAttribute("data-available")).toBe("false")
    expect(within(orphan).queryByRole("link")).toBeNull()
  })
})
