/**
 * FocusBuilderRightRailPlaceholder — empty inspector state for F-1.
 *
 * F-2 replaces this with a real selection-driven inspector
 * (SelectionDrivenInspector + RightRailWithSections primitives).
 */
export function FocusBuilderRightRailPlaceholder() {
  return (
    <div
      className="grid h-full place-items-center px-4 py-4 text-center text-[12px] text-content-muted"
      data-testid="focus-builder-right-rail-empty"
    >
      <div>
        <div className="mb-1 text-[11px] uppercase tracking-wider">
          Inspector
        </div>
        <div>Editing arrives in F-2.</div>
      </div>
    </div>
  )
}

export default FocusBuilderRightRailPlaceholder
