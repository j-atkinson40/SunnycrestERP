/**
 * R-3.1 Spec 19 — cross-row placement drag persistence.
 *
 * Validates: API-driven cross-row placement movement (placement
 * removed from source row + added to target row at the new
 * starting_column) round-trips through service + renderer.
 *
 * Smoke-shaped: drag gesture state machine is exercised at unit level
 * (use-canvas-interactions hit-test + commit logic). This spec proves
 * the backend accepts cross-row placement movements via PATCH + the
 * resolution returns the placements in their target rows correctly.
 */
import { test, expect } from "@playwright/test"
import {
  loginAsPlatformAdmin,
  STAGING_BACKEND,
} from "./_shared"


test.describe("R-3.1 spec 19 — cross-row drag", () => {
  test("placement moves from source row to target row at specific starting_column", async ({
    page,
  }) => {
    const adminToken = await loginAsPlatformAdmin(page)

    // Create a 2-row composition: row 0 has 'today' at column 0,
    // row 1 is empty at column_count=12.
    const r1Id = crypto.randomUUID()
    const r2Id = crypto.randomUUID()
    const placementId = "today"
    const create = await page.request.post(
      `${STAGING_BACKEND}/api/platform/admin/visual-editor/compositions/`,
      {
        headers: { Authorization: `Bearer ${adminToken}` },
        data: {
          scope: "vertical_default",
          focus_type: "scheduling",
          vertical: "cemetery",
          rows: [
            {
              row_id: r1Id,
              column_count: 4,
              row_height: 240,
              column_widths: null,
              nested_rows: null,
              placements: [
                {
                  placement_id: placementId,
                  component_kind: "widget",
                  component_name: "today",
                  starting_column: 0,
                  column_span: 1,
                  prop_overrides: {},
                  display_config: { show_header: true, show_border: true },
                  nested_rows: null,
                },
              ],
            },
            {
              row_id: r2Id,
              column_count: 12,
              row_height: 320,
              column_widths: null,
              nested_rows: null,
              placements: [],
            },
          ],
          canvas_config: { gap_size: 12 },
        },
      },
    )
    expect(create.ok()).toBe(true)
    const created = await create.json()
    expect(created.rows[0].placements.length).toBe(1)
    expect(created.rows[1].placements.length).toBe(0)

    // Cross-row drag: move 'today' from row 0 (column_count=4) to
    // row 1 (column_count=12) at starting_column=8 with column_span=4.
    const moved = await page.request.patch(
      `${STAGING_BACKEND}/api/platform/admin/visual-editor/compositions/${created.id}`,
      {
        headers: { Authorization: `Bearer ${adminToken}` },
        data: {
          rows: [
            {
              ...created.rows[0],
              placements: [], // source row empty after move
            },
            {
              ...created.rows[1],
              placements: [
                {
                  placement_id: placementId,
                  component_kind: "widget",
                  component_name: "today",
                  starting_column: 8,
                  column_span: 4,
                  prop_overrides: {},
                  display_config: { show_header: true, show_border: true },
                  nested_rows: null,
                },
              ],
            },
          ],
          canvas_config: created.canvas_config,
        },
      },
    )
    expect(moved.ok()).toBe(true)
    const movedData = await moved.json()

    // Source row now empty
    expect(movedData.rows[0].placements.length).toBe(0)
    // Target row has the placement at the new starting_column
    expect(movedData.rows[1].placements.length).toBe(1)
    expect(movedData.rows[1].placements[0].placement_id).toBe(placementId)
    expect(movedData.rows[1].placements[0].starting_column).toBe(8)
    expect(movedData.rows[1].placements[0].column_span).toBe(4)

    // Verify resolution agrees.
    const resolved = await page.request.get(
      `${STAGING_BACKEND}/api/platform/admin/visual-editor/compositions/resolve?focus_type=scheduling&vertical=cemetery`,
      { headers: { Authorization: `Bearer ${adminToken}` } },
    )
    const resolvedData = await resolved.json()
    expect(resolvedData.rows[1].placements[0].starting_column).toBe(8)
  })

  test("cross-row move into a smaller row clamps starting_column", async ({
    page,
  }) => {
    // Conceptual contract test: backend validation rejects placements
    // whose starting_column + column_span > target row's column_count.
    // This exercises the validation guard documented at
    // composition_service._validate_rows.
    const adminToken = await loginAsPlatformAdmin(page)

    // Create a row at column_count=4 with a placement at starting_column=8
    // — should be REJECTED (8 + 1 > 4).
    const create = await page.request.post(
      `${STAGING_BACKEND}/api/platform/admin/visual-editor/compositions/`,
      {
        headers: { Authorization: `Bearer ${adminToken}` },
        data: {
          scope: "vertical_default",
          focus_type: "scheduling",
          vertical: "crematory",
          rows: [
            {
              row_id: crypto.randomUUID(),
              column_count: 4,
              row_height: "auto",
              column_widths: null,
              nested_rows: null,
              placements: [
                {
                  placement_id: "out-of-bounds",
                  component_kind: "widget",
                  component_name: "today",
                  starting_column: 8, // overflows column_count=4
                  column_span: 1,
                  prop_overrides: {},
                  display_config: {},
                  nested_rows: null,
                },
              ],
            },
          ],
          canvas_config: { gap_size: 12 },
        },
      },
    )
    // Backend MUST reject this with 400.
    expect(create.status()).toBe(400)
  })
})
