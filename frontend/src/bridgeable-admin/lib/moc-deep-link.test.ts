import { describe, expect, it } from "vitest"

import { isWiredBuilder, mocDeepLink } from "./moc-deep-link"

describe("mocDeepLink", () => {
  it("workflows → vertical-scoped editor with workflow_type + scope", () => {
    expect(
      mocDeepLink({
        builder: "workflows",
        artifact_id: "wf-id",
        routing: {
          workflow_type: "quote_to_pour",
          scope: "vertical_default",
          vertical: "manufacturing",
        },
      }),
    ).toBe(
      "/studio/manufacturing/workflows?workflow_type=quote_to_pour&scope=vertical_default",
    )
  })

  it("workflows → platform scope when vertical is null", () => {
    expect(
      mocDeepLink({
        builder: "workflows",
        artifact_id: "wf-id",
        routing: { workflow_type: "month_end_close", scope: "platform_default" },
      }),
    ).toBe(
      "/studio/workflows?workflow_type=month_end_close&scope=platform_default",
    )
  })

  it("focuses → tier=2 + template=<artifact_id> (the focus_template id)", () => {
    expect(
      mocDeepLink({
        builder: "focuses",
        artifact_id: "focus-template-uuid",
        routing: { template_slug: "job-coordination", vertical: null },
      }),
    ).toBe("/studio/focuses?tier=2&template=focus-template-uuid")
  })

  it("documents → template_id=<artifact_id>", () => {
    expect(
      mocDeepLink({
        builder: "documents",
        artifact_id: "doc-template-uuid",
        routing: { template_key: "quote.standard", vertical: "manufacturing" },
      }),
    ).toBe("/studio/manufacturing/documents?template_id=doc-template-uuid")
  })

  it("widgets → /studio/widget-builder/<widget_id> (slug route, not artifact_id)", () => {
    expect(
      mocDeepLink({
        builder: "widgets",
        artifact_id: "widget-defs-row-id",
        routing: { widget_id: "untitled-widget-136" },
      }),
    ).toBe("/studio/widget-builder/untitled-widget-136")
  })

  // ── Orphan / insufficient-routing → null (caller renders unavailable) ──

  it("workflows with empty routing → null (orphan: no workflow_type)", () => {
    expect(
      mocDeepLink({ builder: "workflows", artifact_id: "gone", routing: {} }),
    ).toBeNull()
  })

  it("widgets with empty routing → null (orphan: no widget_id)", () => {
    expect(
      mocDeepLink({ builder: "widgets", artifact_id: "gone", routing: {} }),
    ).toBeNull()
  })

  it("unknown builder → null", () => {
    expect(
      mocDeepLink({ builder: "spreadsheets", artifact_id: "x", routing: {} }),
    ).toBeNull()
  })

  it("isWiredBuilder gates the four", () => {
    expect(["workflows", "focuses", "widgets", "documents"].every(isWiredBuilder)).toBe(
      true,
    )
    expect(isWiredBuilder("themes")).toBe(false)
    expect(isWiredBuilder("classes")).toBe(false)
  })
})
