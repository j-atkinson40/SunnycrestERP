/**
 * R-5.1 — PageEditor: center pane of the `/settings/edge-panel`
 * settings page. Edits the active page's per-row placement layer
 * (PlacementList per row) plus page-level affordances (rename for
 * personal pages, reset for tenant pages, delete for personal pages).
 *
 * Operates on the active page identified by page_id. The page may
 * be a tenant-default page (override semantics: hide/append/reorder
 * placements; cannot rename or delete) OR a user-authored personal
 * page (override semantics: full control over rows/placements;
 * deletable).
 */
import { useMemo, useState } from "react"
import { Plus, RotateCcw, Trash2 } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type {
  CompositionRow,
  Placement,
} from "@/lib/visual-editor/compositions/types"
import type { EdgePanelPage } from "@/lib/edge-panel/types"

import { ButtonPicker } from "./ButtonPicker"
import { PageReset, PersonalPageDelete } from "./ResetDialogs"
import { PlacementList } from "./PlacementList"


/** Per-page override slice — mirrors the JSON shape this page edits.
 *  Tenant-page-specific (hidden_placement_ids, additional_placements,
 *  placement_order, canvas_config). Distinct from a full
 *  EdgePanelUserOverride.page_overrides[id] entry by intent — the
 *  parent page rebuilds the override from these slices. */
export interface PageOverrideSlice {
  hidden_placement_ids?: string[]
  additional_placements?: Placement[]
  placement_order?: string[]
}


export interface PageEditorProps {
  /** Tenant page (read-only). null if active page is personal. */
  tenantPage: EdgePanelPage | null
  /** Personal page (editable). null if active page is tenant. */
  personalPage: EdgePanelPage | null
  /** Per-page override slice for THIS tenant page (only applicable
   *  when tenantPage is set). */
  pageOverride: PageOverrideSlice | null
  /** Apply a partial change to the per-page override slice for
   *  THIS tenant page. */
  onUpdateOverride: (updates: Partial<PageOverrideSlice>) => void
  /** Mutate a personal page's rows. */
  onUpdatePersonalRows: (rows: CompositionRow[]) => void
  /** Rename a personal page. */
  onRenamePersonalPage: (newName: string) => void
  onResetPage: () => void
  onDeletePersonalPage: () => void
  tenantVertical: string
}


/** Generate a UUID-shape placement_id (browser crypto). */
function newPlacementId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID()
  }
  return `pl-${Math.random().toString(36).slice(2)}-${Date.now()}`
}

function newRowId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID()
  }
  return `row-${Math.random().toString(36).slice(2)}-${Date.now()}`
}


export function PageEditor({
  tenantPage,
  personalPage,
  pageOverride,
  onUpdateOverride,
  onUpdatePersonalRows,
  onRenamePersonalPage,
  onResetPage,
  onDeletePersonalPage,
  tenantVertical,
}: PageEditorProps) {
  const [resetOpen, setResetOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [pickerRowIndex, setPickerRowIndex] = useState(0)

  const isTenant = tenantPage !== null
  const activePage = (tenantPage ?? personalPage) as EdgePanelPage | null

  const hiddenIds = useMemo(
    () => pageOverride?.hidden_placement_ids ?? [],
    [pageOverride],
  )
  const additionalPlacements = useMemo(
    () => pageOverride?.additional_placements ?? [],
    [pageOverride],
  )
  const placementOrder = useMemo(
    () => pageOverride?.placement_order ?? null,
    [pageOverride],
  )

  const hasCustomization = useMemo(() => {
    return (
      hiddenIds.length > 0 ||
      additionalPlacements.length > 0 ||
      (placementOrder !== null && placementOrder.length > 0)
    )
  }, [hiddenIds, additionalPlacements, placementOrder])

  if (!activePage) {
    return (
      <div
        data-testid="edge-panel-settings-page-editor"
        className="flex flex-col gap-3 p-4 text-content-muted"
      >
        Select a page from the left to begin customizing.
      </div>
    )
  }

  function onToggleHide(placementId: string) {
    if (!isTenant) return
    const current = hiddenIds
    const next = current.includes(placementId)
      ? current.filter((id) => id !== placementId)
      : [...current, placementId]
    onUpdateOverride({ hidden_placement_ids: next })
  }

  function onAddPlacement(rowIndex: number) {
    setPickerRowIndex(rowIndex)
    setPickerOpen(true)
  }

  function onPickerSelect(slug: string, defaults: Record<string, unknown>) {
    const placement: Placement = {
      placement_id: newPlacementId(),
      component_kind: "button",
      component_name: slug,
      starting_column: 0,
      column_span: 1,
      prop_overrides: { ...defaults },
      display_config: {},
      nested_rows: null,
      row_index: pickerRowIndex,
    }
    if (isTenant) {
      const next = [...additionalPlacements, placement]
      onUpdateOverride({ additional_placements: next })
    } else if (personalPage) {
      const rows = [...personalPage.rows]
      // Strip row_index (resolution-hint) before appending to a row.
      const { row_index: _omit, ...rest } = placement
      void _omit
      const persisted = rest as Placement
      if (rows.length === 0) {
        rows.push({
          row_id: newRowId(),
          column_count: 12,
          row_height: "auto",
          column_widths: null,
          nested_rows: null,
          placements: [persisted],
        })
      } else {
        const target = Math.min(pickerRowIndex, rows.length - 1)
        rows[target] = {
          ...rows[target],
          placements: [...rows[target].placements, persisted],
        }
      }
      onUpdatePersonalRows(rows)
    }
  }

  function onDeletePersonalPlacement(placementId: string) {
    if (isTenant) {
      // User-added placement on a tenant page lives in additional_placements.
      const next = additionalPlacements.filter(
        (p) => p.placement_id !== placementId,
      )
      onUpdateOverride({ additional_placements: next })
    } else if (personalPage) {
      const rows = personalPage.rows.map((row) => ({
        ...row,
        placements: row.placements.filter(
          (p) => p.placement_id !== placementId,
        ),
      }))
      onUpdatePersonalRows(rows)
    }
  }

  function onReorderRow(rowIndex: number, orderedIds: string[]) {
    if (isTenant) {
      // Tenant pages: store as page-level placement_order. R-5.1 spec
      // applies one ordering per row per backend semantics; for the
      // settings UI v1, keep a flat placement_order list — the
      // resolver applies it per-row by filtering to in-row ids.
      onUpdateOverride({ placement_order: orderedIds })
    } else if (personalPage) {
      const rows = [...personalPage.rows]
      const row = rows[rowIndex]
      if (!row) return
      const byId = new Map<string, Placement>()
      row.placements.forEach((p) => byId.set(p.placement_id, p))
      const next: Placement[] = []
      for (const pid of orderedIds) {
        const found = byId.get(pid)
        if (found) {
          next.push(found)
          byId.delete(pid)
        }
      }
      for (const remaining of byId.values()) next.push(remaining)
      rows[rowIndex] = { ...row, placements: next }
      onUpdatePersonalRows(rows)
    }
  }

  function onAddPersonalRow() {
    if (!personalPage) return
    const rows = [
      ...personalPage.rows,
      {
        row_id: newRowId(),
        column_count: 12,
        row_height: "auto",
        column_widths: null,
        nested_rows: null,
        placements: [],
      } as CompositionRow,
    ]
    onUpdatePersonalRows(rows)
  }

  // Filter additional_placements to a specific row index (for tenant
  // pages — additional_placements carry row_index hints).
  function additionalForRow(idx: number): Placement[] {
    return additionalPlacements.filter((p) => (p.row_index ?? 0) === idx)
  }

  return (
    <div
      data-testid="edge-panel-settings-page-editor"
      className="flex flex-col gap-4 p-4"
    >
      <header className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-1 min-w-0 flex-1">
          {isTenant ? (
            <>
              <div className="flex items-center gap-2">
                <h2 className="text-h3 font-plex-serif text-content-strong">
                  {activePage.name}
                </h2>
                <Badge variant="secondary">From admin</Badge>
                {hasCustomization && (
                  <Badge variant="info" data-testid="edge-panel-settings-page-customized">
                    Customized
                  </Badge>
                )}
              </div>
              <p className="text-body-sm text-content-muted">
                Hide tenant placements, add your own buttons, or reorder.
                Admin-authored placements you don't hide will keep tracking
                tenant updates.
              </p>
            </>
          ) : (
            <>
              <Label htmlFor="page-name-input" className="sr-only">
                Page name
              </Label>
              <Input
                id="page-name-input"
                value={activePage.name}
                onChange={(e) => onRenamePersonalPage(e.target.value)}
                className="text-h3 font-plex-serif"
                data-testid="edge-panel-settings-page-name-input"
              />
              <Badge variant="default" className="w-fit">
                Personal
              </Badge>
            </>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {isTenant && hasCustomization && (
            <Button
              variant="outline"
              size="sm"
              type="button"
              onClick={() => setResetOpen(true)}
              data-testid="edge-panel-settings-page-reset"
            >
              <RotateCcw className="h-4 w-4" /> Reset page
            </Button>
          )}
          {!isTenant && (
            <Button
              variant="outline"
              size="sm"
              type="button"
              onClick={() => setDeleteOpen(true)}
              data-testid="edge-panel-settings-page-delete-personal"
            >
              <Trash2 className="h-4 w-4" /> Delete page
            </Button>
          )}
        </div>
      </header>

      {isTenant && tenantPage.rows.length === 0 && (
        <Alert variant="info">
          <AlertDescription>
            This page has no rows yet — add a placement to create one.
          </AlertDescription>
        </Alert>
      )}

      <div className="flex flex-col gap-4">
        {(isTenant ? tenantPage!.rows : personalPage!.rows).map(
          (row, idx) => (
            <div
              key={row.row_id}
              className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-base p-3"
            >
              <div className="text-micro uppercase tracking-wider text-content-muted">
                Row {idx + 1}
              </div>
              <PlacementList
                rowIndex={idx}
                tenantPlacements={isTenant ? row.placements : []}
                additionalPlacements={
                  isTenant ? additionalForRow(idx) : row.placements
                }
                hiddenIds={isTenant ? hiddenIds : []}
                placementOrder={isTenant ? placementOrder : null}
                onToggleHide={onToggleHide}
                onDeletePersonal={onDeletePersonalPlacement}
                onAddPlacement={() => onAddPlacement(idx)}
                onReorder={(ids) => onReorderRow(idx, ids)}
              />
            </div>
          ),
        )}
        {!isTenant && (
          <Button
            variant="outline"
            size="sm"
            type="button"
            onClick={onAddPersonalRow}
            data-testid="edge-panel-settings-page-add-row"
          >
            <Plus className="h-4 w-4" /> Add row
          </Button>
        )}
        {isTenant && tenantPage.rows.length === 0 && (
          // Allow adding to row 0 even when tenant page has no rows
          // — creates a synthesized row via the resolver semantics.
          <Button
            variant="outline"
            size="sm"
            type="button"
            onClick={() => onAddPlacement(0)}
            data-testid="edge-panel-settings-page-add-first-placement"
          >
            <Plus className="h-4 w-4" /> Add a button
          </Button>
        )}
      </div>

      <ButtonPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={onPickerSelect}
        tenantVertical={tenantVertical}
      />
      <PageReset
        open={resetOpen}
        pageName={activePage.name}
        onClose={() => setResetOpen(false)}
        onConfirm={() => {
          setResetOpen(false)
          onResetPage()
        }}
      />
      <PersonalPageDelete
        open={deleteOpen}
        pageName={activePage.name}
        onClose={() => setDeleteOpen(false)}
        onConfirm={() => {
          setDeleteOpen(false)
          onDeletePersonalPage()
        }}
      />
    </div>
  )
}
