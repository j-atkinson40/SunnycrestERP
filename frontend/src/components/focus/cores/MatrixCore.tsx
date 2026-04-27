/**
 * MatrixCore — stub renderer for Focus `matrix` mode.
 *
 * Phase A Session 2 stub. Renders a 4×4 placeholder table with row
 * and column headers — visually distinct from the other core stubs.
 * The mode is what Inventory Rebalancing Focus (cross-location) will
 * use in post-September phases.
 *
 * Real matrix mechanics (cell editing, row/column selection,
 * aggregations) land when the first real matrix-mode Focus ships.
 */

import { CoreHeader, EscToDismissHint, type CoreProps } from "./_shared"


const COLUMNS = ["Plant A", "Plant B", "Plant C", "Plant D"]
const ROWS = ["Monticello", "Continental", "Triune", "Cameo"]


export function MatrixCore({ config }: CoreProps) {
  return (
    <div className="flex h-full flex-col gap-4">
      <CoreHeader modeLabel="matrix" title={config.displayName} />

      <div className="flex-1 overflow-auto rounded-md border border-border-subtle bg-surface-sunken/40 p-4">
        <table className="w-full border-collapse font-sans text-body-sm">
          <thead>
            <tr>
              <th
                scope="col"
                className="border-b border-border-subtle px-3 py-2 text-left text-micro uppercase tracking-wider text-content-muted"
              />
              {COLUMNS.map((col) => (
                <th
                  key={col}
                  scope="col"
                  className="border-b border-border-subtle px-3 py-2 text-left text-micro uppercase tracking-wider text-content-muted"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row}>
                <th
                  scope="row"
                  className="border-b border-border-subtle px-3 py-2 text-left font-medium text-content-strong"
                >
                  {row}
                </th>
                {COLUMNS.map((col) => (
                  <td
                    key={col}
                    className="border-b border-border-subtle px-3 py-2 text-content-muted"
                  >
                    —
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <EscToDismissHint />
    </div>
  )
}
