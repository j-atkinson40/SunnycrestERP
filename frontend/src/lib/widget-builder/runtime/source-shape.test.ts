/**
 * WB-2 source-shape regression gates per DECISIONS.md entry 31.
 *
 * Catches future reverts / refactors that silently remove load-bearing
 * structural elements of the WB-2 runtime. Each gate reads a file's
 * source bytes + asserts a regex match. These complement the
 * integration tests by guarding the SHAPE of the code (not just its
 * runtime behavior).
 *
 * Pattern mirrors FocusBuilderPage's FF-4 source-shape gate at
 * `frontend/src/bridgeable-admin/components/focus-builder/FocusBuilderPage.test.tsx`
 * line 1976.
 */

import { describe, it, expect } from "vitest"


async function readSource(relPath: string): Promise<string> {
  const { readFileSync } = await import("fs")
  const { resolve } = await import("path")
  return readFileSync(resolve(__dirname, relPath), "utf-8")
}


describe("WB-2 source-shape gates", () => {
  it("ComposedWidget.tsx exists and exports default ComposedWidget", async () => {
    const src = await readSource("./ComposedWidget.tsx")
    expect(src).toMatch(/export function ComposedWidget\b/)
    expect(src).toMatch(/export default ComposedWidget/)
    // Load-bearing: the inner-div data attribute that bypasses the
    // display:contents hit-test cascade per hover-fix d9ffd90.
    expect(src).toMatch(/data-composed-widget-root/)
    // Load-bearing: parseCompositionBlob invocation.
    expect(src).toMatch(/parseCompositionBlob\(/)
  })

  it("AtomRenderer.tsx exists, exports AtomRenderer + default", async () => {
    const src = await readSource("./AtomRenderer.tsx")
    expect(src).toMatch(/export function AtomRenderer\b/)
    expect(src).toMatch(/export default AtomRenderer/)
    // Load-bearing: ConditionalContainerWrapped via registerComponent
    // is the only Phase 1 atom that gets a registerComponent wrap
    // (Area 6 dual-wrapping lock).
    expect(src).toMatch(/registerComponent\(/)
    expect(src).toMatch(/wb-conditional-container-atom/)
    // Load-bearing: variant visibility filter.
    expect(src).toMatch(/isAtomVisibleInVariant/)
    // Load-bearing: exhaustive switch over atom_type.
    expect(src).toMatch(/case "text_label":/)
    expect(src).toMatch(/case "value_display":/)
    expect(src).toMatch(/case "icon":/)
    expect(src).toMatch(/case "status_badge":/)
    expect(src).toMatch(/case "divider":/)
    expect(src).toMatch(/case "button":/)
    expect(src).toMatch(/case "image":/)
    expect(src).toMatch(/case "conditional_container":/)
  })

  it("atoms/index.tsx exists with 8 Phase 1 atom renderers", async () => {
    const src = await readSource("./atoms/index.tsx")
    expect(src).toMatch(/export function TextLabelRenderer\b/)
    expect(src).toMatch(/export function ValueDisplayRenderer\b/)
    expect(src).toMatch(/export function IconRenderer\b/)
    expect(src).toMatch(/export function StatusBadgeRenderer\b/)
    expect(src).toMatch(/export function DividerRenderer\b/)
    expect(src).toMatch(/export function ButtonRenderer\b/)
    expect(src).toMatch(/export function ImageRenderer\b/)
    expect(src).toMatch(/export function ConditionalContainerRenderer\b/)
    // Load-bearing data-atom-* attribute emission contract.
    expect(src).toMatch(/data-atom-type/)
    expect(src).toMatch(/data-atom-id/)
  })

  it("resolveBinding.ts exists with the expected exported function", async () => {
    const src = await readSource("./resolveBinding.ts")
    expect(src).toMatch(/export function resolveBinding\b/)
    // Load-bearing Phase 1 branches.
    expect(src).toMatch(/binding_type === "literal"/)
    expect(src).toMatch(/binding_type === "field_path"/)
    expect(src).toMatch(/\[bound:/)
  })

  it("register.tsx registers ComposedWidget under 'composed' key", async () => {
    const src = await readSource("./register.tsx")
    // Load-bearing: the 'composed' key is the canonical dispatch
    // entry-point for composition-blob-populated widgets.
    expect(src).toMatch(/registerWidgetRenderer\(\s*"composed"/)
    // Load-bearing: adapter bridges WidgetRendererProps to ComposedWidget.
    expect(src).toMatch(/ComposedWidget/)
  })

  it("dispatch.ts checks composition_blob presence and branches", async () => {
    const src = await readSource("./dispatch.ts")
    expect(src).toMatch(/export function dispatchWidgetDefinition\b/)
    // Load-bearing dispatch logic: presence check + dual-path routing.
    expect(src).toMatch(/composition_blob/)
    expect(src).toMatch(/getWidgetRenderer\(/)
    // Hand-coded dispatch path must NOT be removed.
    expect(src).toMatch(/getWidgetRenderer\(definition\.widget_id\)/)
  })
})


// ── WB-3 source-shape regression gates (entry 31 pattern) ─────────────

describe("WB-3 source-shape gates", () => {
  it("atoms/index.tsx ships the 9-atom Phase 1 catalog (8 existing + RepeaterAtomRenderer)", async () => {
    const src = await readSource("./atoms/index.tsx")
    expect(src).toMatch(/export function TextLabelRenderer\b/)
    expect(src).toMatch(/export function ValueDisplayRenderer\b/)
    expect(src).toMatch(/export function IconRenderer\b/)
    expect(src).toMatch(/export function StatusBadgeRenderer\b/)
    expect(src).toMatch(/export function DividerRenderer\b/)
    expect(src).toMatch(/export function ButtonRenderer\b/)
    expect(src).toMatch(/export function ImageRenderer\b/)
    expect(src).toMatch(/export function ConditionalContainerRenderer\b/)
    // WB-3 addition.
    expect(src).toMatch(/export function RepeaterAtomRenderer\b/)
    // Load-bearing data-attribute contract preserved.
    expect(src).toMatch(/data-atom-type/)
    expect(src).toMatch(/data-atom-id/)
    // Theme-token integration discipline — no hardcoded #hex colors in
    // the production atom UI (per DESIGN_LANGUAGE).
    expect(src).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
  })

  it("AtomRenderer.tsx carries repeater_atom dispatch + nesting-cap guard", async () => {
    const src = await readSource("./AtomRenderer.tsx")
    expect(src).toMatch(/case "repeater_atom":/)
    expect(src).toMatch(/RepeaterAtomWrapped/)
    expect(src).toMatch(/wb-repeater-atom/)
    // Defense-in-depth nesting cap throw.
    expect(src).toMatch(/may not contain another repeater_atom/)
  })

  it("registerComposedWidgets adapter present + idempotency-guarded", async () => {
    const src = await readSource("./registerComposedWidgets.ts")
    expect(src).toMatch(/registerComposedWidgetsFromApi/)
    expect(src).toMatch(/composed-definitions/)
    expect(src).toMatch(/registerComposedWidgetMeta/)
    // Idempotency guard.
    expect(src).toMatch(/_fetchAttempted/)
    // Graceful degradation on fetch failure.
    expect(src).toMatch(/console\.warn/)
  })

  it("canonical WidgetDefinition interface carries composition_blob field", async () => {
    const { readFileSync } = await import("fs")
    const { resolve } = await import("path")
    const src = readFileSync(
      resolve(__dirname, "../../../components/widgets/types.ts"),
      "utf-8",
    )
    expect(src).toMatch(/composition_blob\?:/)
    expect(src).toMatch(/composition_version\?:/)
    expect(src).toMatch(/tier_scope\?:/)
  })

  it("RepeaterAtomConfig TypeScript schema present in composition-blob.ts", async () => {
    const { readFileSync } = await import("fs")
    const { resolve } = await import("path")
    const src = readFileSync(
      resolve(__dirname, "../types/composition-blob.ts"),
      "utf-8",
    )
    expect(src).toMatch(/interface RepeaterAtomConfig/)
    expect(src).toMatch(/repeater_atom/)
  })

  it("codec enforces repeater_atom nesting cap structurally", async () => {
    const { readFileSync } = await import("fs")
    const { resolve } = await import("path")
    const src = readFileSync(
      resolve(__dirname, "../composition-blob-codec.ts"),
      "utf-8",
    )
    expect(src).toMatch(/repeater_atom may not contain another repeater_atom/)
  })
})
