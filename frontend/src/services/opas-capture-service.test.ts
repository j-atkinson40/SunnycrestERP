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
  default: { post: vi.fn(), get: vi.fn(), put: vi.fn(), patch: vi.fn() },
}))

import apiClient from "@/lib/api-client"
import {
  addLine,
  choosePick,
  fetchCapturePreferences,
  readCapture,
  setCaptureText,
  setCapturePickModifier,
  startCapture,
} from "./opas-capture-service"

const post = vi.mocked(apiClient.post)
const get = vi.mocked(apiClient.get)
const put = vi.mocked(apiClient.put)
const patch = vi.mocked(apiClient.patch)

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
    // ⚠️ A THIRD ARGUMENT SINCE 2026-10-27 — the axios CONFIG, carrying the focused
    // field as a query param when a row has been clicked. It is `{}` here because
    // nothing is focused, and `{}` rather than omitted because the call always passes
    // a config object.
    //
    // ⚠️ AND THE FIELD IS A QUERY PARAM, NOT A BODY FIELD, which this assertion also
    // pins: the body is still exactly `{ text, seq }`. `asking` is a question about
    // which question to compose in the RESPONSE, not something the session records,
    // and putting it in the body would make it look stored.
    expect(put).toHaveBeenCalledWith("/capture/sessions/abc/text", {
      text: "tent only",
      seq: 7,
    }, {})
    expect(post).not.toHaveBeenCalled()
  })

  it("setCaptureText SENDS EMPTY TEXT rather than skipping the call", async () => {
    // ⚠️ THE CLEARED BAR. An early return on empty text would leave the pane showing
    // values for words that are no longer on screen — the exact defect whole-text
    // re-extraction exists to fix, reintroduced one layer up.
    await setCaptureText("abc", "", 2)
    expect(put).toHaveBeenCalledWith(
      "/capture/sessions/abc/text", { text: "", seq: 2 }, {},
    )
  })

  it("readCapture GETs /capture/sessions/{id}", async () => {
    await readCapture("abc")
    // ⚠️ NO `params` WHEN NOTHING IS FOCUSED, and that is deliberate rather than
    // incidental. The server validates `asking` against the fields it is asking
    // about, so an empty string would be a value it must reject rather than a
    // question it was never asked.
    expect(get).toHaveBeenCalledWith("/capture/sessions/abc", {})
  })

  it("readCapture SENDS the clicked field, so Opas asks that question again", async () => {
    /** ⚠️ THE HALF THAT WAS MISSING FROM MY FIRST VERSION. The click changed a
     *  client-side focus and the question — composed on the server — did not follow.
     *  The field has to go back. */
    await readCapture("abc", "cemetery")
    expect(get).toHaveBeenCalledWith("/capture/sessions/abc", {
      params: { asking: "cemetery" },
    })
  })

  it("setCaptureText carries the clicked field too, so typing does not lose it", async () => {
    /** ⚠️ A DIRECTOR WHO CLICKS A ROW AND THEN TYPES gets a `setCaptureText` response;
     *  without the field that response composes the server's NEXT question and the
     *  outline jumps away mid-answer. */
    await setCaptureText("abc", "st marys", 3, "cemetery")
    expect(put).toHaveBeenCalledWith(
      "/capture/sessions/abc/text",
      { text: "st marys", seq: 3 },
      { params: { asking: "cemetery" } },
    )
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


describe("the pick-modifier preference — James's bug of 2026-10-29", () => {
  /**
   * ⚠️ THIS BLOCK IS THE ROOT CAUSE'S ONLY COVERAGE, AND A BREAK TEST IS HOW I FOUND
   * THAT OUT. `opas-idle-done.test.tsx` mocks the WHOLE service, so the swallow below
   * is never executed there — I broke it (put the silent default back) and all 14 host
   * tests stayed green. The same reasoning this file's own header gives for existing.
   */
  it("returns the stored value on a successful read", async () => {
    get.mockResolvedValueOnce({
      data: {
        pick_modifier: "control",
        pick_modifier_glyph: "⌃",
        pick_modifier_event_flag: "ctrlKey",
      },
    } as never)
    const got = await fetchCapturePreferences()
    expect(got).toEqual({
      pick_modifier: "control",
      pick_modifier_glyph: "⌃",
      pick_modifier_event_flag: "ctrlKey",
    })
    expect(get).toHaveBeenCalledWith("/capture/preferences")
  })

  it("⚠️ RETURNS null ON A REFUSED READ, NOT A PLAUSIBLE DEFAULT — this is the bug", async () => {
    /**
     * The chain James walked: `OpasHost` mounts outside `<Routes>`, so it asked before
     * any token existed; the endpoint answered **403** (measured live — a bogus path
     * answers 404, the control); and this function CAUGHT that and returned
     * `pick_modifier: "option"`. A refusal became indistinguishable from a user who had
     * never chosen, so the caller had nothing to retry on and the guess stood for the
     * whole session.
     *
     * ⚠️ `null` IS THE WHOLE FIX AT THIS LAYER. It does not throw — a failed preference
     * read must not stop the bar working — but the caller can now TELL.
     */
    get.mockRejectedValueOnce(Object.assign(new Error("Forbidden"), {
      response: { status: 403 },
    }))
    expect(await fetchCapturePreferences()).toBeNull()
  })

  it("and null for a network failure too, not only a 403", async () => {
    get.mockRejectedValueOnce(new Error("Network Error"))
    expect(await fetchCapturePreferences()).toBeNull()
  })

  it("the WRITE does not swallow, because the office asked for it", async () => {
    /**
     * ⚠️ THE ASYMMETRY IS DELIBERATE AND IS THE OTHER HALF OF THE RULING. A read that
     * fails can degrade to the default for display; a WRITE the office typed
     * ("set my shortcut to control") must report whether it happened, or Opas would
     * answer "Pills pick with ⌃ now." and change nothing.
     */
    patch.mockRejectedValueOnce(new Error("nope"))
    await expect(setCapturePickModifier("control")).rejects.toThrow()

    patch.mockResolvedValueOnce({
      data: {
        pick_modifier: "control",
        pick_modifier_glyph: "⌃",
        pick_modifier_event_flag: "ctrlKey",
      },
    } as never)
    const saved = await setCapturePickModifier("control")
    expect(saved.pick_modifier).toBe("control")
    expect(patch).toHaveBeenCalledWith("/capture/preferences", {
      pick_modifier: "control",
    })
  })
})
