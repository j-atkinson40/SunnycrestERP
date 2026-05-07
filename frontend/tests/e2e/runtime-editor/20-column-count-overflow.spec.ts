/**
 * R-3.1 Spec 20 — column count overflow rejection.
 *
 * Validates: backend rejects column_count decreases that would clip
 * placements (the editor's UI Popover disables these values, but the
 * backend is the canonical guard). Increase always permitted.
 *
 * Smoke-shaped: validateColumnCountChange picker logic is exercised at
 * unit level (use-canvas-interactions tests). This spec proves the
 * backend enforces the same invariant when an admin attempts a direct
 * PATCH that would clip.
 */
import { test, expect } from "@playwright/test"
import {
  loginAsPlatformAdmin,
  STAGING_BACKEND,
} from "./_shared"


test.describe("R-3.1 spec 20 — column count overflow rejection", () => {
  test("backend rejects column_count decrease that would clip placements", async ({
    page,
  }) => {
    const adminToken = await loginAsPlatformAdmin(page)

    // Create a row at column_count=12 with a placement spanning
    // columns 8-11 (starting_column=8, column_span=4 → ends at 12).
    const rowId = crypto.randomUUID()
    const create = await page.request.post(
      `${STAGING_BACKEND}/api/platform/admin/visual-editor/compositions/`,
      {
        headers: { Authorization: `Bearer ${adminToken}` },
        data: {
          scope: "vertical_default",
          focus_type: "review",
          vertical: "funeral_home",
          rows: [
            {
              row_id: rowId,
              column_count: 12,
              row_height: 240,
              column_widths: null,
              nested_rows: null,
              placements: [
                {
                  placement_id: "wide",
                  component_kind: "widget",
                  component_name: "today",
                  starting_column: 8,
                  column_span: 4,
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
    expect(create.ok()).toBe(true)
    const created = await create.json()

    // Attempt to reduce column_count to 8: placement at 8+4=12 > 8
    // → MUST be rejected with HTTP 400 by composition_service
    // _validate_rows().
    const reject = await page.request.patch(
      `${STAGING_BACKEND}/api/platform/admin/visual-editor/compositions/${created.id}`,
      {
        headers: { Authorization: `Bearer ${adminToken}` },
        data: {
          rows: [
            {
              ...created.rows[0],
              column_count: 8, // would clip the placement at 8+4=12
            },
          ],
          canvas_config: created.canvas_config,
        },
      },
    )
    expect(reject.status()).toBe(400)
  })

  test("backend permits column_count INCREASE (placements stay in place)", async ({
    page,
  }) => {
    const adminToken = await loginAsPlatformAdmin(page)

    const rowId = crypto.randomUUID()
    const create = await page.request.post(
      `${STAGING_BACKEND}/api/platform/admin/visual-editor/compositions/`,
      {
        headers: { Authorization: `Bearer ${adminToken}` },
        data: {
          scope: "vertical_default",
          focus_type: "review",
          vertical: "manufacturing",
          rows: [
            {
              row_id: rowId,
              column_count: 4,
              row_height: 240,
              column_widths: null,
              nested_rows: null,
              placements: [
                {
                  placement_id: "p1",
                  component_kind: "widget",
                  component_name: "today",
                  starting_column: 0,
                  column_span: 4,
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
    expect(create.ok()).toBe(true)
    const created = await create.json()

    // Increase column_count to 12: 0+4=4 <= 12 → PERMITTED.
    const increased = await page.request.patch(
      `${STAGING_BACKEND}/api/platform/admin/visual-editor/compositions/${created.id}`,
      {
        headers: { Authorization: `Bearer ${adminToken}` },
        data: {
          rows: [{ ...created.rows[0], column_count: 12 }],
          canvas_config: created.canvas_config,
        },
      },
    )
    expect(increased.ok()).toBe(true)
    const data = await increased.json()
    expect(data.rows[0].column_count).toBe(12)
    // Placement stays at the same starting_column.
    expect(data.rows[0].placements[0].starting_column).toBe(0)
    expect(data.rows[0].placements[0].column_span).toBe(4)
  })

  test("backend permits column_count DECREASE that does NOT clip", async ({
    page,
  }) => {
    const adminToken = await loginAsPlatformAdmin(page)

    const rowId = crypto.randomUUID()
    const create = await page.request.post(
      `${STAGING_BACKEND}/api/platform/admin/visual-editor/compositions/`,
      {
        headers: { Authorization: `Bearer ${adminToken}` },
        data: {
          scope: "vertical_default",
          focus_type: "review",
          vertical: "crematory",
          rows: [
            {
              row_id: rowId,
              column_count: 12,
              row_height: 240,
              column_widths: null,
              nested_rows: null,
              placements: [
                {
                  placement_id: "p1",
                  component_kind: "widget",
                  component_name: "today",
                  starting_column: 0,
                  column_span: 2,
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
    expect(create.ok()).toBe(true)
    const created = await create.json()

    // Decrease column_count to 4: placement at 0+2=2 <= 4 → permitted.
    const decreased = await page.request.patch(
      `${STAGING_BACKEND}/api/platform/admin/visual-editor/compositions/${created.id}`,
      {
        headers: { Authorization: `Bearer ${adminToken}` },
        data: {
          rows: [{ ...created.rows[0], column_count: 4 }],
          canvas_config: created.canvas_config,
        },
      },
    )
    expect(decreased.ok()).toBe(true)
    const data = await decreased.json()
    expect(data.rows[0].column_count).toBe(4)
  })
})
