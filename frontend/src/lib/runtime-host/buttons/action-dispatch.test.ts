/**
 * R-4.0 — action-handler dispatch vitest coverage.
 *
 * Five handlers + the public dispatchAction entry point. Backend
 * calls (apiClient.post) are mocked at module scope per
 * vi.mock("@/lib/api-client"). React-hook-bound deps come in via
 * the `deps` parameter so handlers stay testable from vitest.
 */
import { describe, it, expect, vi, beforeEach } from "vitest"

vi.mock("@/lib/api-client", () => ({
  __esModule: true,
  default: {
    post: vi.fn(),
  },
}))

import apiClient from "@/lib/api-client"
import {
  DISPATCH_HANDLERS,
  dispatchAction,
  __internals,
} from "./action-dispatch"


type MockApi = { post: ReturnType<typeof vi.fn> }
const api = apiClient as unknown as MockApi


function makeDeps() {
  return {
    navigate: vi.fn(),
    openFocus: vi.fn(),
  }
}


beforeEach(() => {
  api.post.mockReset()
})


describe("R-4.0 dispatch handlers", () => {
  describe("navigate", () => {
    it("calls deps.navigate with the configured route", async () => {
      const deps = makeDeps()
      const result = await DISPATCH_HANDLERS.navigate(
        { route: "/home" },
        {},
        deps,
      )
      expect(deps.navigate).toHaveBeenCalledWith("/home")
      expect(result.status).toBe("success")
    })

    it("substitutes {name} placeholders from resolved params", async () => {
      const deps = makeDeps()
      await DISPATCH_HANDLERS.navigate(
        { route: "/cases/{case_id}" },
        { case_id: "case-42" },
        deps,
      )
      expect(deps.navigate).toHaveBeenCalledWith("/cases/case-42")
    })

    it("returns error when route missing", async () => {
      const deps = makeDeps()
      const result = await DISPATCH_HANDLERS.navigate({}, {}, deps)
      expect(result.status).toBe("error")
      expect(deps.navigate).not.toHaveBeenCalled()
    })
  })

  describe("open_focus", () => {
    it("calls deps.openFocus with focusId + resolved params", async () => {
      const deps = makeDeps()
      const result = await DISPATCH_HANDLERS.open_focus(
        { focusId: "funeral-scheduling" },
        { date: "2026-05-08" },
        deps,
      )
      expect(deps.openFocus).toHaveBeenCalledWith(
        "funeral-scheduling",
        { params: { date: "2026-05-08" } },
      )
      expect(result.status).toBe("success")
    })

    it("returns error when focusId missing", async () => {
      const deps = makeDeps()
      const result = await DISPATCH_HANDLERS.open_focus({}, {}, deps)
      expect(result.status).toBe("error")
      expect(deps.openFocus).not.toHaveBeenCalled()
    })

    it("filters null-valued resolved params from openFocus payload", async () => {
      const deps = makeDeps()
      await DISPATCH_HANDLERS.open_focus(
        { focusId: "x" },
        { a: "1", b: null },
        deps,
      )
      expect(deps.openFocus).toHaveBeenCalledWith("x", {
        params: { a: "1" },
      })
    })
  })

  describe("trigger_workflow", () => {
    it("POSTs to the workflow start endpoint with trigger_context", async () => {
      api.post.mockResolvedValueOnce({ data: { id: "run-7" } })
      const result = await DISPATCH_HANDLERS.trigger_workflow(
        { workflowId: "wf_x" },
        { tenant_id: "t-1", triggered_by: "u-1" },
        makeDeps(),
      )
      expect(api.post).toHaveBeenCalledWith(
        "/workflows/wf_x/start",
        {
          trigger_context: {
            source: "r4_button",
            tenant_id: "t-1",
            triggered_by: "u-1",
          },
        },
      )
      expect(result.status).toBe("success")
      expect(result.data?.run_id).toBe("run-7")
    })

    it("returns error on POST failure", async () => {
      api.post.mockRejectedValueOnce(new Error("network down"))
      const result = await DISPATCH_HANDLERS.trigger_workflow(
        { workflowId: "wf_x" },
        {},
        makeDeps(),
      )
      expect(result.status).toBe("error")
      expect(result.errorMessage).toContain("network down")
    })

    it("returns error when workflowId missing", async () => {
      const result = await DISPATCH_HANDLERS.trigger_workflow(
        {},
        {},
        makeDeps(),
      )
      expect(result.status).toBe("error")
      expect(api.post).not.toHaveBeenCalled()
    })
  })

  describe("create_vault_item", () => {
    it("POSTs to /vault/items with item_type + resolved fields", async () => {
      api.post.mockResolvedValueOnce({ data: { id: "vi-1" } })
      const result = await DISPATCH_HANDLERS.create_vault_item(
        { itemType: "task" },
        { title: "my task", assignee_id: "u-1" },
        makeDeps(),
      )
      expect(api.post).toHaveBeenCalledWith("/vault/items", {
        item_type: "task",
        title: "my task",
        assignee_id: "u-1",
      })
      expect(result.status).toBe("success")
      expect(result.data?.item_id).toBe("vi-1")
    })

    it("filters null-valued fields from the body", async () => {
      api.post.mockResolvedValueOnce({ data: { id: "vi-2" } })
      await DISPATCH_HANDLERS.create_vault_item(
        { itemType: "x" },
        { a: "1", b: null },
        makeDeps(),
      )
      expect(api.post).toHaveBeenCalledWith("/vault/items", {
        item_type: "x",
        a: "1",
      })
    })

    it("returns error when itemType missing", async () => {
      const result = await DISPATCH_HANDLERS.create_vault_item(
        {},
        {},
        makeDeps(),
      )
      expect(result.status).toBe("error")
    })
  })

  describe("run_playwright_workflow", () => {
    it("POSTs to the script execution endpoint", async () => {
      api.post.mockResolvedValueOnce({ data: { log_id: "log-1" } })
      const result = await DISPATCH_HANDLERS.run_playwright_workflow(
        { scriptName: "ss_certificate_submit" },
        { cert_id: "c-1" },
        makeDeps(),
      )
      expect(api.post).toHaveBeenCalledWith(
        "/playwright-scripts/ss_certificate_submit/run",
        { inputs: { cert_id: "c-1" } },
      )
      expect(result.status).toBe("success")
      expect(result.data?.log_id).toBe("log-1")
    })

    it("returns error when scriptName missing", async () => {
      const result = await DISPATCH_HANDLERS.run_playwright_workflow(
        {},
        {},
        makeDeps(),
      )
      expect(result.status).toBe("error")
    })
  })

  describe("dispatchAction (entry point)", () => {
    it("routes to the right handler", async () => {
      const deps = makeDeps()
      const result = await dispatchAction(
        "navigate",
        { route: "/home" },
        {},
        deps,
      )
      expect(result.status).toBe("success")
      expect(deps.navigate).toHaveBeenCalledWith("/home")
    })

    it("returns error for unknown action types", async () => {
      const result = await dispatchAction(
        "totally_not_real" as never,
        {},
        {},
        makeDeps(),
      )
      expect(result.status).toBe("error")
      expect(result.errorMessage).toContain("Unknown action type")
    })

    it("catches handler-thrown errors", async () => {
      api.post.mockImplementationOnce(() => {
        throw new Error("sync boom")
      })
      const result = await dispatchAction(
        "trigger_workflow",
        { workflowId: "wf" },
        {},
        makeDeps(),
      )
      expect(result.status).toBe("error")
      expect(result.errorMessage).toBe("sync boom")
    })
  })

  describe("internals", () => {
    it("paramsToQueryString drops null values", () => {
      expect(
        __internals.paramsToQueryString({ a: "1", b: null, c: 2 }),
      ).toBe("?a=1&c=2")
    })
    it("paramsToQueryString empty produces empty string", () => {
      expect(__internals.paramsToQueryString({})).toBe("")
    })
  })
})
