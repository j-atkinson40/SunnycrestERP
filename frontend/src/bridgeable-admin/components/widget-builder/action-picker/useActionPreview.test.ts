/**
 * useActionPreview — pure-function preview text tests.
 *
 * Asserts the preview text is computed without dispatching to R-4
 * (non-dispatching gate per Lock 4b).
 */
import { describe, expect, it, vi } from "vitest"

import type { ActionRef } from "@/lib/widget-builder/types/composition-blob"
import { computeActionPreviewText } from "./useActionPreview"

vi.mock("@/lib/runtime-host/buttons/action-dispatch", () => ({
  // If the preview function ever imports dispatchAction this mock
  // shows up — failing the non-dispatching gate.
  dispatchAction: vi.fn(() => {
    throw new Error("computeActionPreviewText must not invoke dispatcher")
  }),
}))


describe("computeActionPreviewText (non-dispatching)", () => {
  it("describes navigate", () => {
    const a: ActionRef = {
      action_kind: "navigate",
      href: "/cases/{id}",
      params: [],
      confirm_before: false,
    }
    expect(computeActionPreviewText(a)).toMatch(/Navigate to \/cases\/\{id\}/)
  })
  it("describes empty navigate", () => {
    const a: ActionRef = {
      action_kind: "navigate",
      href: "",
      params: [],
      confirm_before: false,
    }
    expect(computeActionPreviewText(a)).toMatch(/target route not set/)
  })
  it("describes open_focus", () => {
    const a: ActionRef = {
      action_kind: "open_focus",
      focus_template_slug: "funeral-scheduling",
      initial_context: [],
      confirm_before: false,
    }
    expect(computeActionPreviewText(a)).toMatch(/Open Focus "funeral-scheduling"/)
  })
  it("describes open_peek", () => {
    const a: ActionRef = {
      action_kind: "open_peek",
      peek_view_type: "invoice",
      initial_context: [],
      confirm_before: false,
    }
    expect(computeActionPreviewText(a)).toMatch(/Open invoice peek/)
  })
  it("describes trigger_workflow", () => {
    const a: ActionRef = {
      action_kind: "trigger_workflow",
      workflow_slug: "wf_x",
      workflow_input: [],
      confirm_before: true,
    }
    expect(computeActionPreviewText(a)).toMatch(/Trigger workflow "wf_x"/)
  })
  it("describes mutate with row binding", () => {
    const a: ActionRef = {
      action_kind: "mutate",
      mutate_kind: "anomaly_acknowledge",
      target_id_binding: {
        name: "id",
        source: "current_row",
        row_field: "id",
      },
      confirm_before: true,
    }
    expect(computeActionPreviewText(a)).toMatch(/anomaly_acknowledge bound to row\.id/)
  })
  it("describes literal binding in preview", () => {
    const a: ActionRef = {
      action_kind: "mutate",
      mutate_kind: "anomaly_acknowledge",
      target_id_binding: {
        name: "id",
        source: "literal",
        value: "x",
      },
      confirm_before: true,
    }
    expect(computeActionPreviewText(a)).toMatch(/literal "x"/)
  })
  it("null action prompts pick-a-verb", () => {
    expect(computeActionPreviewText(null)).toMatch(/Pick an action verb/)
  })
})
