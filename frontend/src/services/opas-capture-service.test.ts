/**
 * The capture service's URLs and verbs.
 *
 * ⚠️ THIS FILE EXISTS BECAUSE `capture-pane.test.tsx` MOCKS THE WHOLE SERVICE, so every
 * path string in it is untested there. A wrong path is the failure that mock cannot see:
 * the pane would be perfect, the tests green, and nothing would reach the server. Found by
 * asking what the pane tests could NOT be wrong about.
 *
 * ⚠️ `apiClient` PREFIXES `/api/v1` PER REQUEST (`api-client.ts:63`:
 * `config.baseURL = ${resolveApiBaseUrl()}/api/v1`), so the paths here are relative to
 * that and must NOT repeat it. Asserting the exact relative path is what pins the
 * agreement with the registered routes — `/api/v1/capture/sessions` and the three below,
 * exercised live against uvicorn on dev.
 */
import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("@/lib/api-client", () => ({
  default: { post: vi.fn(), get: vi.fn(), put: vi.fn() },
}))

import apiClient from "@/lib/api-client"
import {
  addLine,
  choosePick,
  readCapture,
  setCaptureText,
  startCapture,
} from "./opas-capture-service"

const post = vi.mocked(apiClient.post)
const get = vi.mocked(apiClient.get)
const put = vi.mocked(apiClient.put)

beforeEach(() => {
  vi.clearAllMocks()
  post.mockResolvedValue({ data: { session_id: "s1" } } as never)
  get.mockResolvedValue({ data: { session_id: "s1" } } as never)
  put.mockResolvedValue({ data: { session_id: "s1" } } as never)
})

describe("the four paths match the registered routes", () => {
  it("start POSTs /capture/sessions", async () => {
    await startCapture("start an order")
    expect(post).toHaveBeenCalledWith("/capture/sessions", {
      opening_line: "start an order",
    })
  })

  it("start sends null rather than omitting the key when there is no opening line", async () => {
    // ⚠️ `null`, NOT `undefined`. Axios drops undefined keys, and the endpoint's
    // Pydantic model declares `opening_line: str | None` — an absent key and an explicit
    // null both validate, but sending null keeps the request shape stable in a log.
    await startCapture()
    expect(post).toHaveBeenCalledWith("/capture/sessions", { opening_line: null })
  })

  it("addLine POSTs /capture/sessions/{id}/lines", async () => {
    await addLine("abc", "tent only")
    expect(post).toHaveBeenCalledWith("/capture/sessions/abc/lines", {
      line: "tent only",
    })
  })

  it("choosePick POSTs /capture/sessions/{id}/choose with a ONE-BASED index", async () => {
    await choosePick("abc", "vault", 2)
    expect(post).toHaveBeenCalledWith("/capture/sessions/abc/choose", {
      field_id: "vault",
      index: 2,
    })
  })

  it("setCaptureText PUTs /capture/sessions/{id}/text with the text and the seq", async () => {
    // ⚠️ `PUT`, NOT `POST`, AND THIS IS THE ASSERTION THAT PINS IT. The two verbs mean
    // different things on this session — set versus add — and nothing else in the
    // request distinguishes them. A `post` here would reach the LINES endpoint's
    // neighbour, 405, and only at runtime.
    await setCaptureText("abc", "tent only", 7)
    expect(put).toHaveBeenCalledWith("/capture/sessions/abc/text", {
      text: "tent only",
      seq: 7,
    })
    expect(post).not.toHaveBeenCalled()
  })

  it("setCaptureText SENDS EMPTY TEXT rather than skipping the call", async () => {
    // ⚠️ THE CLEARED BAR. An early return on empty text would leave the pane showing
    // values for words that are no longer on screen — the exact defect whole-text
    // re-extraction exists to fix, reintroduced one layer up.
    await setCaptureText("abc", "", 2)
    expect(put).toHaveBeenCalledWith("/capture/sessions/abc/text", { text: "", seq: 2 })
  })

  it("readCapture GETs /capture/sessions/{id}", async () => {
    await readCapture("abc")
    expect(get).toHaveBeenCalledWith("/capture/sessions/abc")
  })

  it("no path repeats the /api/v1 prefix the client already adds", async () => {
    // ⚠️ THE DUPLICATION BUG, PINNED. `apiClient` sets `baseURL = …/api/v1` per request,
    // so a path written as "/api/v1/capture/…" would request "/api/v1/api/v1/capture/…"
    // and 404 — and every pane test would still pass, because they mock this module.
    await startCapture()
    await addLine("a", "x")
    await setCaptureText("a", "x", 1)
    await choosePick("a", "f", 1)
    await readCapture("a")
    const paths = [
      ...post.mock.calls.map((c) => c[0]),
      ...get.mock.calls.map((c) => c[0]),
      ...put.mock.calls.map((c) => c[0]),
    ]
    expect(paths.length).toBe(5)
    for (const p of paths) {
      expect(p).not.toContain("/api/")
      expect(p.startsWith("/capture/sessions")).toBe(true)
    }
  })
})
