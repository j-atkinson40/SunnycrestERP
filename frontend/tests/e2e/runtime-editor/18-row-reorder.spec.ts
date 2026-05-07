/**
 * R-3.1 Spec 18 — composition row reorder.
 *
 * Validates: API-driven multi-row composition + reorder via PATCH +
 * verify rows[] array shape + order + per-row column_count preserved.
 *
 * Smoke-shaped: drag-handle reorder gesture is exercised at the unit
 * level via use-canvas-interactions tests (pointerToInsertIndex). This
 * spec proves the backend service + API + renderer round-trip
 * preserves row order across reorder operations.
 */
import { test, expect } from "@playwright/test"
import {
  loginAsPlatformAdmin,
  STAGING_BACKEND,
} from "./_shared"


test.describe("R-3.1 spec 18 — row reorder", () => {
  test("rows array order is preserved through PATCH; per-row column_count survives reorder", async ({
    page,
  }) => {
    const adminToken = await loginAsPlatformAdmin(page)

    // Create a 3-row composition with distinct column_counts so we
    // can verify reorder preserves per-row identity.
    const r1Id = crypto.randomUUID()
    const r2Id = crypto.randomUUID()
    const r3Id = crypto.randomUUID()
    const create = await page.request.post(
      `${STAGING_BACKEND}/api/platform/admin/visual-editor/compositions/`,
      {
        headers: { Authorization: `Bearer ${adminToken}` },
        data: {
          scope: "vertical_default",
          focus_type: "scheduling",
          vertical: "manufacturing",
          rows: [
            {
              row_id: r1Id,
              column_count: 1,
              row_height: 192,
              column_widths: null,
              nested_rows: null,
              placements: [],
            },
            {
              row_id: r2Id,
              column_count: 4,
              row_height: 240,
              column_widths: null,
              nested_rows: null,
              placements: [],
            },
            {
              row_id: r3Id,
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

    expect(created.rows.length).toBe(3)
    expect(created.rows[0].row_id).toBe(r1Id)
    expect(created.rows[0].column_count).toBe(1)
    expect(created.rows[1].column_count).toBe(4)
    expect(created.rows[2].column_count).toBe(12)

    // Reorder: move row 0 to the bottom (index 2). Editor's
    // handleReorderRow does this same operation. Resulting order:
    // [r2, r3, r1].
    const reordered = await page.request.patch(
      `${STAGING_BACKEND}/api/platform/admin/visual-editor/compositions/${created.id}`,
      {
        headers: { Authorization: `Bearer ${adminToken}` },
        data: {
          rows: [created.rows[1], created.rows[2], created.rows[0]],
          canvas_config: created.canvas_config,
        },
      },
    )
    expect(reordered.ok()).toBe(true)
    const reorderedData = await reordered.json()

    expect(reorderedData.rows.length).toBe(3)
    expect(reorderedData.rows[0].row_id).toBe(r2Id)
    expect(reorderedData.rows[0].column_count).toBe(4)
    expect(reorderedData.rows[1].row_id).toBe(r3Id)
    expect(reorderedData.rows[1].column_count).toBe(12)
    expect(reorderedData.rows[2].row_id).toBe(r1Id)
    expect(reorderedData.rows[2].column_count).toBe(1)

    // Verify resolution returns the new order too (write-side
    // versioning correctly deactivated the prior row + the new active
    // row reflects the reordered shape).
    const resolved = await page.request.get(
      `${STAGING_BACKEND}/api/platform/admin/visual-editor/compositions/resolve?focus_type=scheduling&vertical=manufacturing`,
      { headers: { Authorization: `Bearer ${adminToken}` } },
    )
    expect(resolved.ok()).toBe(true)
    const resolvedData = await resolved.json()
    expect(resolvedData.rows.length).toBe(3)
    expect(resolvedData.rows[0].row_id).toBe(r2Id)
    expect(resolvedData.rows[2].row_id).toBe(r1Id)
  })
})
