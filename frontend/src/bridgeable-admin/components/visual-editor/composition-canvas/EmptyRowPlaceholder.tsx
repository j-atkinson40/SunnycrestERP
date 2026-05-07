/**
 * EmptyRowPlaceholder — rendered inside an empty row (no placements)
 * to give the operator a clear hint that this row is a drop target /
 * needs content.
 */


interface Props {
  rowId: string
  columnCount: number
}


export function EmptyRowPlaceholder({ rowId, columnCount }: Props) {
  return (
    <div
      data-testid={`empty-row-placeholder-${rowId}`}
      style={{
        gridColumn: `1 / span ${columnCount}`,
      }}
      className="flex items-center justify-center rounded-md border border-dashed border-border-base bg-surface-base/40 py-6 text-caption text-content-subtle"
    >
      Drag a component from the palette into this row.
    </div>
  )
}
