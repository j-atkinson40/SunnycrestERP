/**
 * R-5.1 — applyUserOverride parity tests.
 *
 * Mirrors backend test_edge_panel_user_override coverage so the
 * frontend client-side preview produces identical output to the
 * backend resolver for the canonical override types. Drift between
 * the two is a defect — both implementations enforce the same
 * order-of-operations contract.
 */
import { describe, expect, it } from "vitest"

import type {
  CompositionRow,
  Placement,
} from "@/lib/visual-editor/compositions/types"
import type {
  EdgePanelPage,
  EdgePanelUserOverride,
  ResolvedEdgePanel,
} from "./types"
import {
  applyPlacementOverridesToRows,
  applyUserOverride,
} from "./applyOverride"


function makePlacement(id: string, name = "navigate-to-pulse"): Placement {
  return {
    placement_id: id,
    component_kind: "button",
    component_name: name,
    starting_column: 0,
    column_span: 1,
    prop_overrides: {},
    display_config: {},
    nested_rows: null,
  }
}

function makeRow(rowId: string, placements: Placement[]): CompositionRow {
  return {
    row_id: rowId,
    column_count: 1,
    row_height: "auto",
    column_widths: null,
    nested_rows: null,
    placements,
  }
}

function makePage(
  pageId: string,
  name: string,
  rows: CompositionRow[],
): EdgePanelPage {
  return {
    page_id: pageId,
    name,
    rows,
    canvas_config: {},
  }
}

function makeTenant(pages: EdgePanelPage[]): ResolvedEdgePanel {
  return {
    panel_key: "default",
    vertical: "manufacturing",
    tenant_id: "t1",
    source: "platform_default",
    source_id: "src",
    source_version: 1,
    pages,
    canvas_config: {},
  }
}


describe("applyPlacementOverridesToRows", () => {
  it("drops placements in hidden_placement_ids", () => {
    const rows = [
      makeRow("r1", [makePlacement("p1"), makePlacement("p2")]),
    ]
    const out = applyPlacementOverridesToRows(rows, {
      hidden_placement_ids: ["p1"],
    })
    expect(out).toHaveLength(1)
    expect(out[0].placements.map((p) => p.placement_id)).toEqual(["p2"])
  })

  it("silently drops orphan IDs in hidden_placement_ids", () => {
    const rows = [makeRow("r1", [makePlacement("p1")])]
    const out = applyPlacementOverridesToRows(rows, {
      hidden_placement_ids: ["nonexistent", "p1"],
    })
    expect(out[0].placements).toHaveLength(0)
  })

  it("appends additional_placements to row_index 0 by default", () => {
    const rows = [
      makeRow("r1", [makePlacement("p1")]),
      makeRow("r2", [makePlacement("p2")]),
    ]
    const out = applyPlacementOverridesToRows(rows, {
      additional_placements: [makePlacement("p3")],
    })
    expect(out[0].placements.map((p) => p.placement_id)).toEqual(["p1", "p3"])
    expect(out[1].placements.map((p) => p.placement_id)).toEqual(["p2"])
  })

  it("appends additional_placements to declared row_index", () => {
    const rows = [
      makeRow("r1", [makePlacement("p1")]),
      makeRow("r2", [makePlacement("p2")]),
    ]
    const add = { ...makePlacement("p3"), row_index: 1 }
    const out = applyPlacementOverridesToRows(rows, {
      additional_placements: [add],
    })
    expect(out[1].placements.map((p) => p.placement_id)).toEqual(["p2", "p3"])
  })

  it("clamps too-high row_index to last row", () => {
    const rows = [makeRow("r1", [makePlacement("p1")])]
    const add = { ...makePlacement("p3"), row_index: 99 }
    const out = applyPlacementOverridesToRows(rows, {
      additional_placements: [add],
    })
    expect(out[0].placements.map((p) => p.placement_id)).toEqual(["p1", "p3"])
  })

  it("synthesizes a row when adding to empty rows", () => {
    const out = applyPlacementOverridesToRows([], {
      additional_placements: [makePlacement("p1")],
    })
    expect(out).toHaveLength(1)
    expect(out[0].placements).toHaveLength(1)
    expect(out[0].column_count).toBe(12)
  })

  it("strips row_index from persisted placement shape", () => {
    const add = { ...makePlacement("p3"), row_index: 0 }
    const out = applyPlacementOverridesToRows(
      [makeRow("r1", [])],
      { additional_placements: [add] },
    )
    const persisted = out[0].placements[0] as Placement & { row_index?: number }
    expect(persisted.row_index).toBeUndefined()
  })

  it("reorders placements by placement_order", () => {
    const rows = [
      makeRow("r1", [
        makePlacement("p1"),
        makePlacement("p2"),
        makePlacement("p3"),
      ]),
    ]
    const out = applyPlacementOverridesToRows(rows, {
      placement_order: ["p3", "p1", "p2"],
    })
    expect(out[0].placements.map((p) => p.placement_id)).toEqual([
      "p3",
      "p1",
      "p2",
    ])
  })

  it("appends unmentioned placements at end after ordered ones", () => {
    const rows = [
      makeRow("r1", [
        makePlacement("p1"),
        makePlacement("p2"),
        makePlacement("p3"),
      ]),
    ]
    const out = applyPlacementOverridesToRows(rows, {
      placement_order: ["p3"],
    })
    expect(out[0].placements.map((p) => p.placement_id)).toEqual([
      "p3",
      "p1",
      "p2",
    ])
  })

  it("composes hidden + additional + order in correct sequence", () => {
    const rows = [
      makeRow("r1", [makePlacement("p1"), makePlacement("p2")]),
    ]
    const out = applyPlacementOverridesToRows(rows, {
      hidden_placement_ids: ["p1"],
      additional_placements: [makePlacement("p3")],
      placement_order: ["p3", "p2"],
    })
    expect(out[0].placements.map((p) => p.placement_id)).toEqual(["p3", "p2"])
  })
})


describe("applyUserOverride", () => {
  it("returns tenant pages unchanged when override is null/empty", () => {
    const tenant = makeTenant([
      makePage("pg1", "Quick Actions", [
        makeRow("r1", [makePlacement("p1")]),
      ]),
    ])
    const out = applyUserOverride(tenant, null)
    expect(out).toEqual(tenant.pages)

    const out2 = applyUserOverride(tenant, {})
    expect(out2).toHaveLength(1)
  })

  it("returns [] when tenant default is null", () => {
    expect(applyUserOverride(null, {})).toEqual([])
  })

  it("R-5.0 full-replace: rows in page_override replaces tenant page rows", () => {
    const tenant = makeTenant([
      makePage("pg1", "QA", [makeRow("r1", [makePlacement("p1")])]),
    ])
    const override: EdgePanelUserOverride = {
      page_overrides: {
        pg1: { rows: [makeRow("user-row", [makePlacement("user-p")])] },
      },
    }
    const out = applyUserOverride(tenant, override)
    expect(out[0].rows[0].row_id).toBe("user-row")
  })

  it("ignores per-placement fields when rows escape-hatch is set", () => {
    const tenant = makeTenant([
      makePage("pg1", "QA", [makeRow("r1", [makePlacement("p1")])]),
    ])
    const override: EdgePanelUserOverride = {
      page_overrides: {
        pg1: {
          rows: [makeRow("user-row", [makePlacement("user-p")])],
          hidden_placement_ids: ["p1"],
          additional_placements: [makePlacement("p99")],
        },
      },
    }
    const out = applyUserOverride(tenant, override)
    expect(out[0].rows[0].row_id).toBe("user-row")
    expect(out[0].rows[0].placements).toHaveLength(1)
    expect(out[0].rows[0].placements[0].placement_id).toBe("user-p")
  })

  it("appends additional_pages after per-page overrides applied", () => {
    const tenant = makeTenant([
      makePage("pg1", "Quick Actions", [
        makeRow("r1", [makePlacement("p1")]),
      ]),
    ])
    const personal = makePage("pg-personal", "My Drafts", [makeRow("r-p", [])])
    const out = applyUserOverride(tenant, {
      additional_pages: [personal],
    })
    expect(out.map((p) => p.page_id)).toEqual(["pg1", "pg-personal"])
  })

  it("drops personal page that collides with tenant page_id (tenant wins)", () => {
    const tenant = makeTenant([
      makePage("pg1", "Tenant Page", [makeRow("r1", [])]),
    ])
    const personal = makePage("pg1", "Personal masquerading", [makeRow("r-p", [])])
    const out = applyUserOverride(tenant, {
      additional_pages: [personal],
    })
    expect(out).toHaveLength(1)
    expect(out[0].name).toBe("Tenant Page")
  })

  it("drops pages listed in hidden_page_ids", () => {
    const tenant = makeTenant([
      makePage("pg1", "QA", [makeRow("r1", [])]),
      makePage("pg2", "Dispatch", [makeRow("r2", [])]),
    ])
    const out = applyUserOverride(tenant, {
      hidden_page_ids: ["pg2"],
    })
    expect(out).toHaveLength(1)
    expect(out[0].page_id).toBe("pg1")
  })

  it("reorders pages by page_order_override", () => {
    const tenant = makeTenant([
      makePage("pg1", "First", [makeRow("r1", [])]),
      makePage("pg2", "Second", [makeRow("r2", [])]),
      makePage("pg3", "Third", [makeRow("r3", [])]),
    ])
    const out = applyUserOverride(tenant, {
      page_order_override: ["pg3", "pg1"],
    })
    // pg3 first, pg1 second, pg2 (not mentioned) appended at end.
    expect(out.map((p) => p.page_id)).toEqual(["pg3", "pg1", "pg2"])
  })

  it("composes per-page + additional + hidden + order in correct sequence", () => {
    const tenant = makeTenant([
      makePage("pg1", "Quick Actions", [
        makeRow("r1", [makePlacement("t1"), makePlacement("t2")]),
      ]),
      makePage("pg2", "Dispatch", [makeRow("r2", [makePlacement("t3")])]),
    ])
    const personal = makePage("pg3", "Personal", [makeRow("rp", [])])
    const out = applyUserOverride(tenant, {
      page_overrides: {
        pg1: { hidden_placement_ids: ["t1"] },
      },
      additional_pages: [personal],
      hidden_page_ids: ["pg2"],
      page_order_override: ["pg3", "pg1"],
    })
    expect(out.map((p) => p.page_id)).toEqual(["pg3", "pg1"])
    expect(out[1].rows[0].placements.map((p) => p.placement_id)).toEqual(["t2"])
  })
})
