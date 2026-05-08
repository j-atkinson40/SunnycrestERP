/**
 * R-5.2 — EdgePanelEditor PageList.
 *
 * Extracted from EdgePanelEditorPage's inline left-rail logic. Pure
 * presentational component — handlers are emit-only via props.
 *
 * data-testid attributes preserved verbatim from the R-5.0 inline
 * shape so spec 28 stays green:
 *   - edge-panel-editor-page-list (the <ul>)
 *   - edge-panel-editor-page-{idx} (per-row button)
 *   - edge-panel-editor-add-page (Add page button)
 *
 * Page reorder via ↑/↓ buttons matches R-5.1 personal-page reorder
 * convention. Drag-drop page reorder explicitly out of scope per
 * R-5.2 spec; lands in R-5.x for both surfaces simultaneously.
 */
import { ArrowDown, ArrowUp } from "lucide-react"

import { Button } from "@/components/ui/button"
import type { EdgePanelPage } from "@/lib/edge-panel/types"


export interface PageListProps {
  pages: EdgePanelPage[]
  activePageIndex: number
  defaultPageIndex: number
  onSelectPage: (idx: number) => void
  onAddPage: () => void
  onMovePageUp: (idx: number) => void
  onMovePageDown: (idx: number) => void
}


export function PageList({
  pages,
  activePageIndex,
  defaultPageIndex,
  onSelectPage,
  onAddPage,
  onMovePageUp,
  onMovePageDown,
}: PageListProps) {
  return (
    <div className="flex flex-col gap-3 rounded-md border border-border-subtle bg-surface-elevated p-3">
      <div className="flex items-center justify-between">
        <h2 className="text-body-sm font-medium text-content-strong">Pages</h2>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onAddPage}
          data-testid="edge-panel-editor-add-page"
        >
          + Add page
        </Button>
      </div>
      <ul
        className="flex flex-col gap-1"
        data-testid="edge-panel-editor-page-list"
      >
        {pages.map((page, idx) => (
          <li key={page.page_id}>
            <div
              className={`flex items-center gap-1 rounded px-1 py-0.5 ${
                idx === activePageIndex
                  ? "bg-accent-subtle"
                  : "hover:bg-surface-sunken"
              }`}
            >
              <button
                type="button"
                onClick={() => onSelectPage(idx)}
                data-testid={`edge-panel-editor-page-${idx}`}
                data-active={idx === activePageIndex ? "true" : "false"}
                className={`flex flex-1 items-center justify-between rounded px-2 py-1 text-left text-body-sm ${
                  idx === activePageIndex
                    ? "text-content-strong"
                    : "text-content-muted"
                }`}
              >
                <span className="truncate">{page.name}</span>
                {idx === defaultPageIndex && (
                  <span className="text-micro text-accent">DEFAULT</span>
                )}
              </button>
              <div className="flex shrink-0 flex-col">
                <button
                  type="button"
                  onClick={() => onMovePageUp(idx)}
                  disabled={idx === 0}
                  data-testid={`edge-panel-editor-page-${idx}-move-up`}
                  aria-label={`Move page ${page.name} up`}
                  className="rounded p-0.5 text-content-muted hover:bg-accent-subtle hover:text-content-strong disabled:opacity-30 disabled:hover:bg-transparent"
                >
                  <ArrowUp className="h-3 w-3" />
                </button>
                <button
                  type="button"
                  onClick={() => onMovePageDown(idx)}
                  disabled={idx === pages.length - 1}
                  data-testid={`edge-panel-editor-page-${idx}-move-down`}
                  aria-label={`Move page ${page.name} down`}
                  className="rounded p-0.5 text-content-muted hover:bg-accent-subtle hover:text-content-strong disabled:opacity-30 disabled:hover:bg-transparent"
                >
                  <ArrowDown className="h-3 w-3" />
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
