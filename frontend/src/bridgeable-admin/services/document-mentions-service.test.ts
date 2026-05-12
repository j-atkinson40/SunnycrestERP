/**
 * Document mentions service — token shape helpers + vocabulary constants.
 *
 * Arc 4b.2a substrate test coverage. The `resolveMention` axios wrapper
 * itself is a thin pass-through and is covered at the backend layer
 * (test_documents_arc_4b2a_mention_substrate.py); here we verify the
 * pure helpers + canonical vocabulary catalogs that Arc 4b.2b consumer
 * code will rely on.
 */
import { describe, expect, it } from "vitest"

import {
  buildRefToken,
  MENTION_ENTITY_LABELS,
  MENTION_ENTITY_LABELS_PLURAL,
  MENTION_ENTITY_TYPES,
  parseRefTokens,
  REF_TOKEN_REGEX,
} from "./document-mentions-service"


describe("MENTION_ENTITY_TYPES catalog", () => {
  it("ships canonical 4-entity picker subset", () => {
    // Q-COUPLING-1 — picker subset at v1 ships with 4 entity types.
    // Expansion has documented trigger criteria; do not extend without
    // running Arc 4b.2 investigation.
    expect(MENTION_ENTITY_TYPES).toEqual(["case", "order", "contact", "product"])
  })

  it("matches singular labels for each entity type", () => {
    for (const t of MENTION_ENTITY_TYPES) {
      expect(MENTION_ENTITY_LABELS[t]).toBeTruthy()
    }
  })

  it("matches plural labels for each entity type", () => {
    for (const t of MENTION_ENTITY_TYPES) {
      expect(MENTION_ENTITY_LABELS_PLURAL[t]).toBeTruthy()
    }
  })

  it("plural and singular differ for every entity type", () => {
    for (const t of MENTION_ENTITY_TYPES) {
      expect(MENTION_ENTITY_LABELS[t]).not.toEqual(
        MENTION_ENTITY_LABELS_PLURAL[t],
      )
    }
  })
})


describe("buildRefToken", () => {
  it("emits canonical Jinja function-call form", () => {
    expect(buildRefToken("case", "abc-123")).toBe(
      '{{ ref("case", "abc-123") }}',
    )
  })

  it("accepts substrate vocabulary identifiers", () => {
    expect(buildRefToken("fh_case", "uid-1")).toBe(
      '{{ ref("fh_case", "uid-1") }}',
    )
  })

  it("strips quote characters defensively", () => {
    const tok = buildRefToken('case"injection', 'uid"-1')
    // Only 4 quote characters remain (the canonical token quotes)
    const quoteCount = (tok.match(/"/g) || []).length
    expect(quoteCount).toBe(4)
  })
})


describe("parseRefTokens", () => {
  it("extracts tokens in document order", () => {
    const body = `
      Some text {{ ref("case", "abc") }} more text
      {{ ref("order", "xyz") }} end.
    `
    expect(parseRefTokens(body)).toEqual([
      { entity_type: "case", entity_id: "abc" },
      { entity_type: "order", entity_id: "xyz" },
    ])
  })

  it("preserves duplicates", () => {
    const body = '{{ ref("case", "x") }} and {{ ref("case", "x") }}'
    expect(parseRefTokens(body)).toHaveLength(2)
  })

  it("returns empty array for empty body", () => {
    expect(parseRefTokens("")).toEqual([])
  })

  it("handles substrate vocabulary", () => {
    expect(parseRefTokens('{{ ref("fh_case", "id1") }}')).toEqual([
      { entity_type: "fh_case", entity_id: "id1" },
    ])
  })

  it("round-trips build + parse", () => {
    const tok = buildRefToken("contact", "contact-uid")
    const body = `prefix ${tok} suffix`
    expect(parseRefTokens(body)).toEqual([
      { entity_type: "contact", entity_id: "contact-uid" },
    ])
  })

  it("resets regex state across calls", () => {
    // Defensive — global regex constants can persist lastIndex
    // between invocations and produce non-deterministic results.
    const body = '{{ ref("case", "x") }}'
    expect(parseRefTokens(body)).toHaveLength(1)
    expect(parseRefTokens(body)).toHaveLength(1) // second call same result
  })
})


describe("REF_TOKEN_REGEX", () => {
  it("matches canonical token shape", () => {
    REF_TOKEN_REGEX.lastIndex = 0
    const m = REF_TOKEN_REGEX.exec('{{ ref("case", "abc-123") }}')
    expect(m).not.toBeNull()
    expect(m?.[1]).toBe("case")
    expect(m?.[2]).toBe("abc-123")
  })

  it("does not match malformed tokens", () => {
    REF_TOKEN_REGEX.lastIndex = 0
    expect(REF_TOKEN_REGEX.exec("{{ ref(case, abc) }}")).toBeNull()
  })
})
