/**
 * WorkflowNodePalette — Workflow-Builder consumer of the WidgetPalette
 * primitive (2026-05-29). The right rail's none-state action palette
 * (Apple Shortcuts model): a searchable, 6-family-grouped library of the
 * 32 addable node types. Clicking an item adds that node via the page's
 * `handleAddNode` (reused verbatim — same add as the retired center-top
 * "Add:" chip-row).
 *
 * Mirrors FocusBuilderPalette's wrapper shape: registry → group-by-family
 * → PaletteCategory[] → render WidgetPalette. Two differences from the
 * Focus path: (1) CLICK-to-add (onItemClick), not drag; (2) per-type
 * Lucide ICON COMPONENTS (TYPE_ICON) via the additive `iconComponent`
 * field, not the 4-entry string-icon map. Search is wrapper-local
 * ephemeral state, filtered BEFORE the categories reach the primitive
 * (the shared primitive stays search-agnostic). Groups are always
 * expanded; collapsible is filed forward.
 */
import * as React from "react"
import { Search } from "lucide-react"

import { getByType } from "@/lib/visual-editor/registry"
import {
  nodeTypesByFamily,
  type FamilyTypeEntry,
} from "@/lib/visual-editor/workflow-node-palette"
import { resolveTypeIcon } from "./node-families"

import {
  WidgetPalette,
  type PaletteCategory,
} from "../../builder-primitives/WidgetPalette"

/** Item testid prefix so tests target rail-palette items unambiguously. */
export const NODE_PALETTE_ITEM_PREFIX = "node-palette-item-"

export interface WorkflowNodePaletteProps {
  /** Add a node of the given type (the page's handleAddNode, verbatim). */
  onAdd: (nodeType: string) => void
}

export function WorkflowNodePalette({ onAdd }: WorkflowNodePaletteProps) {
  const [query, setQuery] = React.useState("")

  // All 32 registered workflow-node types (name + plain-language label).
  const allTypes = React.useMemo<FamilyTypeEntry[]>(
    () =>
      getByType("workflow-node").map((e) => ({
        name: e.metadata.name,
        displayName: e.metadata.displayName ?? e.metadata.name,
      })),
    [],
  )

  // Group by family (NODE_FAMILY_ORDER), then filter by the search query.
  // Match on the type's plain-language label, its raw name, AND the family
  // label (typing "flow" surfaces the whole Flow-control group).
  const categories = React.useMemo<PaletteCategory[]>(() => {
    const groups = nodeTypesByFamily(allTypes)
    const q = query.trim().toLowerCase()
    return groups
      .map((g) => {
        const familyMatches = g.label.toLowerCase().includes(q)
        const items = g.types
          .filter(
            (t) =>
              q === "" ||
              familyMatches ||
              t.displayName.toLowerCase().includes(q) ||
              t.name.toLowerCase().includes(q),
          )
          .map((t) => ({
            id: t.name,
            label: t.displayName,
            iconComponent: resolveTypeIcon(t.name),
            testId: `${NODE_PALETTE_ITEM_PREFIX}${t.name}`,
          }))
        return { id: g.family, label: g.label, items }
      })
      .filter((c) => c.items.length > 0)
  }, [allTypes, query])

  return (
    <div className="flex flex-col gap-2" data-testid="workflow-node-palette">
      <div>
        <h2 className="text-caption font-semibold text-content-strong">
          Add a node
        </h2>
        <p className="text-micro text-content-muted">
          Click a node type to add it to the canvas.
        </p>
      </div>

      {/* Search — wrapper-local; filters before the primitive renders. */}
      <div className="relative">
        <Search
          size={13}
          className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-content-muted"
          aria-hidden
        />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search node types…"
          data-testid="workflow-node-palette-search"
          className="w-full rounded-md border border-border-base bg-surface-raised py-1 pl-7 pr-2 text-caption text-content-base placeholder:text-content-subtle focus:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--accent)]"
        />
      </div>

      {categories.length === 0 ? (
        <p
          className="px-1 py-2 text-caption text-content-muted"
          data-testid="workflow-node-palette-no-matches"
        >
          No node types match “{query}”.
        </p>
      ) : (
        <WidgetPalette categories={categories} onItemClick={onAdd} />
      )}
    </div>
  )
}

export default WorkflowNodePalette
