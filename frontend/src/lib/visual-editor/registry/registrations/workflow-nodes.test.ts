/**
 * workflow-nodes.test — Phase B sub-arc B-2 (node-type registry expansion).
 *
 * Backfill validation for the 32 workflow-node registrations. Mirrors the
 * Phase-3 Component Configuration backfill-validation precedent. The
 * strongest assert is bidirectional registry <-> vocabulary coverage:
 * every canonical VALID_NODE_TYPES value has a registration AND every
 * registration name is in VALID_NODE_TYPES — so vocabulary drift on
 * either side fails loudly here.
 *
 * Registry is populated via the auto-register side-effect import.
 */

import { describe, it, expect, beforeAll } from "vitest"

import "@/lib/visual-editor/registry/auto-register"
import { getByType } from "@/lib/visual-editor/registry"
import { VALID_NODE_TYPES } from "@/lib/visual-editor/workflows/canvas-validator"

describe("workflow-nodes registry — B-2 backfill validation", () => {
  let entries: ReturnType<typeof getByType>
  let registeredNames: Set<string>

  beforeAll(() => {
    entries = getByType("workflow-node")
    registeredNames = new Set(entries.map((e) => e.metadata.name))
  })

  it("registers exactly 32 workflow-node types (31 + notify_via_contact_preference, 3a.1; the retired generation-focus-invocation twin from P2 stays out)", () => {
    expect(entries.length).toBe(32)
  })

  it("registry count matches the canonical VALID_NODE_TYPES vocabulary", () => {
    expect(entries.length).toBe(VALID_NODE_TYPES.length)
  })

  // ── Bidirectional coverage ──────────────────────────────────────────

  it("every canonical VALID_NODE_TYPES value has a registration", () => {
    const missing = VALID_NODE_TYPES.filter((t) => !registeredNames.has(t))
    expect(missing).toEqual([])
  })

  it("every registration name is a canonical VALID_NODE_TYPES value (no orphans)", () => {
    const vocab = new Set<string>(VALID_NODE_TYPES)
    const orphans = [...registeredNames].filter((n) => !vocab.has(n))
    expect(orphans).toEqual([])
  })

  // Per-name coverage — one assert per canonical type (32 asserts).
  it.each(VALID_NODE_TYPES.map((t) => [t]))(
    "has a registration for %s",
    (nodeType) => {
      expect(registeredNames.has(nodeType)).toBe(true)
    },
  )

  // ── Per-registration shape ──────────────────────────────────────────

  it("every registration has >=3 configurableProps keys", () => {
    const offenders = entries
      .map((e) => ({
        name: e.metadata.name,
        count: Object.keys(e.metadata.configurableProps ?? {}).length,
      }))
      .filter((x) => x.count < 3)
    // No operator-adjudicated lifecycle exception was needed: start carries
    // 3 genuine visual-config props (nodeShape/labelPosition/accentToken)
    // and end carries 4 (terminalStatus + the 3 visual). If a future entry
    // legitimately needs <3, this assert + the adjudication record update
    // together.
    expect(offenders).toEqual([])
  })

  it("every registration declares non-empty consumedTokens", () => {
    const offenders = entries
      .filter((e) => (e.metadata.consumedTokens?.length ?? 0) === 0)
      .map((e) => e.metadata.name)
    expect(offenders).toEqual([])
  })

  it("every registration carries schemaVersion + componentVersion >= 1", () => {
    for (const e of entries) {
      expect(e.metadata.schemaVersion).toBeGreaterThanOrEqual(1)
      expect(e.metadata.componentVersion).toBeGreaterThanOrEqual(1)
    }
  })

  it("every registration maps to a runtime workflowStepType via extensions", () => {
    const offenders = entries
      .filter((e) => {
        const ext = e.metadata.extensions as
          | { workflowStepType?: unknown }
          | undefined
        return typeof ext?.workflowStepType !== "string"
      })
      .map((e) => e.metadata.name)
    expect(offenders).toEqual([])
  })

  it("uses category 'workflow-nodes' on all entries (Path A flat — no grouping)", () => {
    const offenders = entries
      .filter((e) => e.metadata.category !== "workflow-nodes")
      .map((e) => e.metadata.name)
    expect(offenders).toEqual([])
  })

  it("preserves the surviving Phase-1 entry (send-communication) at componentVersion 2", () => {
    // The other Phase-1 entry, generation-focus-invocation, was retired in
    // focus-invocation reconciliation P2 (redundant twin of invoke_generation_focus).
    const comm = entries.find((e) => e.metadata.name === "send-communication")
    expect(comm?.metadata.componentVersion).toBe(2)
    expect(
      entries.find((e) => e.metadata.name === "generation-focus-invocation"),
    ).toBeUndefined()
  })

  it("lifecycle markers carry genuine visual-config props (start=3, end>=3)", () => {
    const start = entries.find((e) => e.metadata.name === "start")
    const end = entries.find((e) => e.metadata.name === "end")
    expect(Object.keys(start?.metadata.configurableProps ?? {})).toEqual(
      expect.arrayContaining(["nodeShape", "labelPosition", "accentToken"]),
    )
    expect(
      Object.keys(end?.metadata.configurableProps ?? {}).length,
    ).toBeGreaterThanOrEqual(3)
  })
})
