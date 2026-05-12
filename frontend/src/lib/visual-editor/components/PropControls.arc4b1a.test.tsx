/**
 * Arc 4b.1a — PropControlDispatcher vocabulary extension tests.
 *
 * Covers the 4 new control components + dispatcher branches added
 * additively to PropControls.tsx. Existing 8 ConfigPropType branches
 * are covered by `component-config.test.ts` (smoke) + per-component
 * vitest below their consumers.
 */
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import {
  ConditionalRuleControl,
  CONDITIONAL_RULE_OPERATORS,
  ListOfPartiesControl,
  PropControlDispatcher,
  TableOfColumnsControl,
  TableOfRowsControl,
  type ColumnDef,
  type ConditionalRule,
  type PartyDef,
  type TotalsRowDef,
} from "./PropControls"


// ─── TableOfColumnsControl ──────────────────────────────────────


describe("TableOfColumnsControl", () => {
  it("renders empty state when value is empty", () => {
    const onChange = vi.fn()
    render(<TableOfColumnsControl value={[]} onChange={onChange} />)
    expect(
      screen.getByTestId("prop-table-of-columns-empty"),
    ).toBeInTheDocument()
  })

  it("renders one row per column with header + field + format inputs", () => {
    const onChange = vi.fn()
    const cols: ColumnDef[] = [
      { header: "Qty", field: "quantity", format: "number" },
      { header: "Total", field: "line_total" },
    ]
    render(<TableOfColumnsControl value={cols} onChange={onChange} />)
    expect(screen.getByTestId("prop-table-of-columns-row-0")).toBeInTheDocument()
    expect(screen.getByTestId("prop-table-of-columns-row-1")).toBeInTheDocument()
    expect(
      (screen.getByTestId("prop-table-of-columns-row-0-header") as HTMLInputElement).value,
    ).toBe("Qty")
    expect(
      (screen.getByTestId("prop-table-of-columns-row-0-field") as HTMLInputElement).value,
    ).toBe("quantity")
    expect(
      (screen.getByTestId("prop-table-of-columns-row-0-format") as HTMLInputElement).value,
    ).toBe("number")
  })

  it("Add column appends an empty column", () => {
    const onChange = vi.fn()
    render(<TableOfColumnsControl value={[]} onChange={onChange} />)
    fireEvent.click(screen.getByTestId("prop-table-of-columns-add"))
    expect(onChange).toHaveBeenCalledWith([{ header: "", field: "" }])
  })

  it("Remove column drops the row", () => {
    const onChange = vi.fn()
    const cols: ColumnDef[] = [
      { header: "A", field: "a" },
      { header: "B", field: "b" },
    ]
    render(<TableOfColumnsControl value={cols} onChange={onChange} />)
    fireEvent.click(screen.getByTestId("prop-table-of-columns-row-0-remove"))
    expect(onChange).toHaveBeenCalledWith([{ header: "B", field: "b" }])
  })

  it("Reorder swaps adjacent rows; bounds disable up/down at edges", () => {
    const onChange = vi.fn()
    const cols: ColumnDef[] = [
      { header: "A", field: "a" },
      { header: "B", field: "b" },
      { header: "C", field: "c" },
    ]
    render(<TableOfColumnsControl value={cols} onChange={onChange} />)
    expect(screen.getByTestId("prop-table-of-columns-row-0-up")).toBeDisabled()
    expect(screen.getByTestId("prop-table-of-columns-row-2-down")).toBeDisabled()
    fireEvent.click(screen.getByTestId("prop-table-of-columns-row-1-down"))
    expect(onChange).toHaveBeenCalledWith([
      { header: "A", field: "a" },
      { header: "C", field: "c" },
      { header: "B", field: "b" },
    ])
  })

  it("Edit field updates the row immutably", () => {
    const onChange = vi.fn()
    const cols: ColumnDef[] = [{ header: "A", field: "a" }]
    render(<TableOfColumnsControl value={cols} onChange={onChange} />)
    fireEvent.change(
      screen.getByTestId("prop-table-of-columns-row-0-header"),
      { target: { value: "A2" } },
    )
    expect(onChange).toHaveBeenCalledWith([{ header: "A2", field: "a" }])
  })

  it("clears format key when format input cleared", () => {
    const onChange = vi.fn()
    const cols: ColumnDef[] = [
      { header: "A", field: "a", format: "currency" },
    ]
    render(<TableOfColumnsControl value={cols} onChange={onChange} />)
    fireEvent.change(
      screen.getByTestId("prop-table-of-columns-row-0-format"),
      { target: { value: "" } },
    )
    expect(onChange).toHaveBeenCalledWith([
      { header: "A", field: "a", format: undefined },
    ])
  })

  it("disabled prop disables all inputs and add", () => {
    render(
      <TableOfColumnsControl
        value={[{ header: "A", field: "a" }]}
        onChange={() => undefined}
        disabled
      />,
    )
    expect(screen.getByTestId("prop-table-of-columns-add")).toBeDisabled()
    expect(
      screen.getByTestId("prop-table-of-columns-row-0-header"),
    ).toBeDisabled()
  })
})


// ─── TableOfRowsControl ─────────────────────────────────────────


describe("TableOfRowsControl", () => {
  it("renders per-row label + variable + emphasis switch", () => {
    const onChange = vi.fn()
    const rows: TotalsRowDef[] = [
      { label: "Subtotal", variable: "subtotal" },
      { label: "Total", variable: "total", emphasis: true },
    ]
    render(<TableOfRowsControl value={rows} onChange={onChange} />)
    expect(
      (screen.getByTestId("prop-table-of-rows-row-0-label") as HTMLInputElement).value,
    ).toBe("Subtotal")
    expect(
      (screen.getByTestId("prop-table-of-rows-row-1-emphasis") as HTMLInputElement).checked,
    ).toBe(true)
  })

  it("toggle emphasis on/off", () => {
    const onChange = vi.fn()
    const rows: TotalsRowDef[] = [
      { label: "Subtotal", variable: "subtotal" },
    ]
    render(<TableOfRowsControl value={rows} onChange={onChange} />)
    fireEvent.click(screen.getByTestId("prop-table-of-rows-row-0-emphasis"))
    expect(onChange).toHaveBeenCalledWith([
      { label: "Subtotal", variable: "subtotal", emphasis: true },
    ])
  })

  it("Add row appends empty row", () => {
    const onChange = vi.fn()
    render(<TableOfRowsControl value={[]} onChange={onChange} />)
    fireEvent.click(screen.getByTestId("prop-table-of-rows-add"))
    expect(onChange).toHaveBeenCalledWith([{ label: "", variable: "" }])
  })

  it("Remove row drops correctly", () => {
    const onChange = vi.fn()
    const rows: TotalsRowDef[] = [
      { label: "A", variable: "a" },
      { label: "B", variable: "b" },
    ]
    render(<TableOfRowsControl value={rows} onChange={onChange} />)
    fireEvent.click(screen.getByTestId("prop-table-of-rows-row-0-remove"))
    expect(onChange).toHaveBeenCalledWith([{ label: "B", variable: "b" }])
  })

  it("Empty state shown when no rows", () => {
    render(<TableOfRowsControl value={[]} onChange={() => undefined} />)
    expect(screen.getByTestId("prop-table-of-rows-empty")).toBeInTheDocument()
  })

  it("Reorder swaps adjacent rows", () => {
    const onChange = vi.fn()
    const rows: TotalsRowDef[] = [
      { label: "A", variable: "a" },
      { label: "B", variable: "b" },
    ]
    render(<TableOfRowsControl value={rows} onChange={onChange} />)
    fireEvent.click(screen.getByTestId("prop-table-of-rows-row-0-down"))
    expect(onChange).toHaveBeenCalledWith([
      { label: "B", variable: "b" },
      { label: "A", variable: "a" },
    ])
  })
})


// ─── ListOfPartiesControl ───────────────────────────────────────


describe("ListOfPartiesControl", () => {
  it("renders party rows with role + signature_date", () => {
    const onChange = vi.fn()
    const parties: PartyDef[] = [
      { role: "Customer" },
      { role: "Funeral Director", signature_date: "2026-05-12" },
    ]
    render(<ListOfPartiesControl value={parties} onChange={onChange} />)
    expect(
      (screen.getByTestId("prop-list-of-parties-row-0-role") as HTMLInputElement).value,
    ).toBe("Customer")
    expect(
      (screen.getByTestId("prop-list-of-parties-row-1-date") as HTMLInputElement).value,
    ).toBe("2026-05-12")
  })

  it("Add party appends empty party", () => {
    const onChange = vi.fn()
    render(<ListOfPartiesControl value={[]} onChange={onChange} />)
    fireEvent.click(screen.getByTestId("prop-list-of-parties-add"))
    expect(onChange).toHaveBeenCalledWith([{ role: "" }])
  })

  it("clears signature_date when date input cleared", () => {
    const onChange = vi.fn()
    const parties: PartyDef[] = [{ role: "X", signature_date: "2026-01-01" }]
    render(<ListOfPartiesControl value={parties} onChange={onChange} />)
    fireEvent.change(
      screen.getByTestId("prop-list-of-parties-row-0-date"),
      { target: { value: "" } },
    )
    expect(onChange).toHaveBeenCalledWith([
      { role: "X", signature_date: undefined },
    ])
  })

  it("Remove party drops the row", () => {
    const onChange = vi.fn()
    const parties: PartyDef[] = [{ role: "A" }, { role: "B" }]
    render(<ListOfPartiesControl value={parties} onChange={onChange} />)
    fireEvent.click(screen.getByTestId("prop-list-of-parties-row-0-remove"))
    expect(onChange).toHaveBeenCalledWith([{ role: "B" }])
  })
})


// ─── ConditionalRuleControl ─────────────────────────────────────


describe("ConditionalRuleControl", () => {
  it("renders bounded operator vocabulary", () => {
    const onChange = vi.fn()
    const rule: ConditionalRule = {
      field: "case.disposition",
      operator: "equals",
      value: "cremation",
    }
    render(<ConditionalRuleControl value={rule} onChange={onChange} />)
    const operatorSelect = screen.getByTestId(
      "prop-conditional-rule-operator",
    ) as HTMLSelectElement
    // Number of <option> elements MUST equal the canonical operator
    // vocabulary; new operators register additively via the array.
    expect(operatorSelect.options.length).toBe(
      CONDITIONAL_RULE_OPERATORS.length,
    )
    expect(operatorSelect.value).toBe("equals")
  })

  it("renders field + operator + value initially", () => {
    const rule: ConditionalRule = {
      field: "case.disposition",
      operator: "equals",
      value: "burial",
    }
    render(<ConditionalRuleControl value={rule} onChange={() => undefined} />)
    expect(
      (screen.getByTestId("prop-conditional-rule-field") as HTMLInputElement).value,
    ).toBe("case.disposition")
    expect(
      (screen.getByTestId("prop-conditional-rule-value") as HTMLInputElement).value,
    ).toBe("burial")
  })

  it("hides value input for nullary operators (exists / not_exists)", () => {
    const rule: ConditionalRule = {
      field: "case.disposition",
      operator: "exists",
    }
    render(<ConditionalRuleControl value={rule} onChange={() => undefined} />)
    expect(
      screen.queryByTestId("prop-conditional-rule-value"),
    ).not.toBeInTheDocument()
  })

  it("changing operator to nullary clears the value field", () => {
    const onChange = vi.fn()
    const rule: ConditionalRule = {
      field: "x",
      operator: "equals",
      value: "y",
    }
    render(<ConditionalRuleControl value={rule} onChange={onChange} />)
    fireEvent.change(
      screen.getByTestId("prop-conditional-rule-operator"),
      { target: { value: "exists" } },
    )
    expect(onChange).toHaveBeenCalledWith({
      field: "x",
      operator: "exists",
      value: undefined,
    })
  })

  it("changing operator from nullary back ensures value is empty-string not undefined", () => {
    const onChange = vi.fn()
    const rule: ConditionalRule = {
      field: "x",
      operator: "exists",
    }
    render(<ConditionalRuleControl value={rule} onChange={onChange} />)
    fireEvent.change(
      screen.getByTestId("prop-conditional-rule-operator"),
      { target: { value: "equals" } },
    )
    expect(onChange).toHaveBeenCalledWith({
      field: "x",
      operator: "equals",
      value: "",
    })
  })

  it("editing field calls onChange with new field", () => {
    const onChange = vi.fn()
    const rule: ConditionalRule = {
      field: "",
      operator: "equals",
      value: "",
    }
    render(<ConditionalRuleControl value={rule} onChange={onChange} />)
    fireEvent.change(screen.getByTestId("prop-conditional-rule-field"), {
      target: { value: "case.priority" },
    })
    expect(onChange).toHaveBeenCalledWith({
      field: "case.priority",
      operator: "equals",
      value: "",
    })
  })

  it("renders fieldSuggestions as datalist options", () => {
    const rule: ConditionalRule = {
      field: "",
      operator: "equals",
      value: "",
    }
    const { container } = render(
      <ConditionalRuleControl
        value={rule}
        onChange={() => undefined}
        fieldSuggestions={["case.disposition", "case.priority"]}
      />,
    )
    const dataList = container.querySelector("datalist")
    expect(dataList).not.toBeNull()
    expect(dataList?.querySelectorAll("option").length).toBe(2)
  })

  it("operator vocabulary is bounded (NOT free-form Jinja)", () => {
    // Regression guard for scope guard: conditional-rule MUST be
    // bounded grammar. If unbounded grammar is added, this test must
    // be updated AND the scope guard must be re-deliberated.
    expect(CONDITIONAL_RULE_OPERATORS).toEqual([
      "equals",
      "not_equals",
      "contains",
      "not_contains",
      "exists",
      "not_exists",
      "greater_than",
      "less_than",
    ])
  })
})


// ─── PropControlDispatcher — extended vocabulary dispatch ───────


describe("PropControlDispatcher (Arc 4b.1a vocabulary)", () => {
  it("dispatches tableOfColumns to TableOfColumnsControl", () => {
    const onChange = vi.fn()
    render(
      <PropControlDispatcher
        schema={{ type: "tableOfColumns", default: [] }}
        value={[{ header: "A", field: "a" }] as ColumnDef[]}
        onChange={onChange}
        data-testid="dispatch-cols"
      />,
    )
    expect(screen.getByTestId("dispatch-cols")).toBeInTheDocument()
    expect(screen.getByTestId("dispatch-cols-row-0")).toBeInTheDocument()
  })

  it("dispatches tableOfRows to TableOfRowsControl", () => {
    render(
      <PropControlDispatcher
        schema={{ type: "tableOfRows", default: [] }}
        value={[{ label: "X", variable: "x" }] as TotalsRowDef[]}
        onChange={() => undefined}
        data-testid="dispatch-rows"
      />,
    )
    expect(screen.getByTestId("dispatch-rows")).toBeInTheDocument()
    expect(screen.getByTestId("dispatch-rows-row-0-label")).toBeInTheDocument()
  })

  it("dispatches listOfParties to ListOfPartiesControl", () => {
    render(
      <PropControlDispatcher
        schema={{ type: "listOfParties", default: [] }}
        value={[{ role: "Customer" }] as PartyDef[]}
        onChange={() => undefined}
        data-testid="dispatch-parties"
      />,
    )
    expect(screen.getByTestId("dispatch-parties")).toBeInTheDocument()
    expect(screen.getByTestId("dispatch-parties-row-0-role")).toBeInTheDocument()
  })

  it("dispatches conditionalRule to ConditionalRuleControl", () => {
    render(
      <PropControlDispatcher
        schema={{
          type: "conditionalRule",
          default: { field: "", operator: "equals", value: "" },
        }}
        value={{ field: "x", operator: "equals", value: "y" } as ConditionalRule}
        onChange={() => undefined}
        data-testid="dispatch-cond"
      />,
    )
    expect(screen.getByTestId("dispatch-cond")).toBeInTheDocument()
    expect(screen.getByTestId("dispatch-cond-operator")).toBeInTheDocument()
  })

  it("conditionalRule dispatcher synthesizes default when value is malformed", () => {
    // Defensive: passing arbitrary value should not crash; control
    // synthesizes its default rule.
    render(
      <PropControlDispatcher
        schema={{
          type: "conditionalRule",
          default: { field: "", operator: "equals", value: "" },
        }}
        value={null}
        onChange={() => undefined}
        data-testid="dispatch-cond-malformed"
      />,
    )
    const op = screen.getByTestId(
      "dispatch-cond-malformed-operator",
    ) as HTMLSelectElement
    expect(op.value).toBe("equals")
  })

  it("tableOfColumns dispatcher coerces non-array value to []", () => {
    render(
      <PropControlDispatcher
        schema={{ type: "tableOfColumns", default: [] }}
        value={"not-an-array" as unknown}
        onChange={() => undefined}
        data-testid="dispatch-cols-bad"
      />,
    )
    expect(
      screen.getByTestId("dispatch-cols-bad-empty"),
    ).toBeInTheDocument()
  })

  it("existing 8 ConfigPropType branches still work (regression smoke)", () => {
    // Confirms Arc 4b.1a is purely additive; existing dispatch
    // unchanged.
    render(
      <PropControlDispatcher
        schema={{ type: "boolean", default: false }}
        value={true}
        onChange={() => undefined}
        data-testid="dispatch-bool"
      />,
    )
    expect(
      (screen.getByTestId("dispatch-bool-switch") as HTMLInputElement).checked,
    ).toBe(true)
  })
})
