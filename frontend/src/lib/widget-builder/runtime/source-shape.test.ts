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


// ── WB-6 source-shape regression gates (entry 31 pattern) ─────────────

describe("WB-6 source-shape gates", () => {
  it("resolveBinding.ts substantiates field_path resolution (no Phase-1 placeholder)", async () => {
    const src = await readSource("./resolveBinding.ts")
    // Real resolution primitives present.
    expect(src).toMatch(/export function parseFieldPath\b/)
    expect(src).toMatch(/export function walkFieldPath\b/)
    // Iteration_mode branches.
    expect(src).toMatch(/iteration_mode\s*===?\s*['"]single_summary['"]|mode\s*===?\s*['"]single_summary['"]/)
    expect(src).toMatch(/iteration_mode\s*===?\s*['"]per_row['"]|mode\s*===?\s*['"]per_row['"]/)
    expect(src).toMatch(/iteration_mode\s*===?\s*['"]single_record['"]|mode\s*===?\s*['"]single_record['"]/)
    // Per-row context-spread + summary context discriminator.
    expect(src).toMatch(/__row/)
    expect(src).toMatch(/__summary/)
    // Backward-compat literal branch.
    expect(src).toMatch(/binding_type === "literal"/)
    // Numeric segment array indexing.
    expect(src).toMatch(/\\d\+|\\d/)
    // Malformed-throw discipline.
    expect(src).toMatch(/malformed field_path/)
    // WB-2 placeholder string syntax REMOVED from the field_path path.
    // (kept only for unset field_path draft-state edge case.)
    expect(src).not.toMatch(/\[bound:row\./)
  })

  it("AtomRenderer.tsx substantiates iteration (no longer 1 mock row)", async () => {
    const src = await readSource("./AtomRenderer.tsx")
    // Real row iteration via dataContext.rows.
    expect(src).toMatch(/dataContext as \{ rows\??: unknown \}/)
    expect(src).toMatch(/realRows/)
    // Per-row context-spread.
    expect(src).toMatch(/__row: true, __index: i, \.\.\.rowData/)
    // max_rows respected.
    expect(src).toMatch(/max_rows/)
  })

  it("BindingPicker substrate present", async () => {
    const { readFileSync } = await import("fs")
    const { resolve } = await import("path")
    const dir = resolve(
      __dirname,
      "../../../bridgeable-admin/components/widget-builder/binding-picker",
    )
    const bindingPicker = readFileSync(
      resolve(dir, "BindingPicker.tsx"),
      "utf-8",
    )
    expect(bindingPicker).toMatch(/export function BindingPicker\b/)
    expect(bindingPicker).toMatch(/SavedViewPicker/)
    expect(bindingPicker).toMatch(/FieldPathPicker/)
    expect(bindingPicker).toMatch(/IterationModePicker/)
    expect(bindingPicker).toMatch(/BindingPreviewTooltip/)

    const sv = readFileSync(resolve(dir, "SavedViewPicker.tsx"), "utf-8")
    expect(sv).toMatch(/export function SavedViewPicker\b/)
    // Shape-compatibility filter present.
    expect(sv).toMatch(/ARRAY_SHAPED_MODES/)

    const fp = readFileSync(resolve(dir, "FieldPathPicker.tsx"), "utf-8")
    expect(fp).toMatch(/export function FieldPathPicker\b/)
    // Free-text fallback present per Risk 1.
    expect(fp).toMatch(/freetext/i)

    const im = readFileSync(
      resolve(dir, "IterationModePicker.tsx"),
      "utf-8",
    )
    expect(im).toMatch(/export function IterationModePicker\b/)
    expect(im).toMatch(/inferIterationMode/)

    const tip = readFileSync(
      resolve(dir, "BindingPreviewTooltip.tsx"),
      "utf-8",
    )
    expect(tip).toMatch(/BindingPreviewTooltip/)

    const useP = readFileSync(resolve(dir, "useBindingPicker.ts"), "utf-8")
    expect(useP).toMatch(/export function useBindingPicker\b/)
    expect(useP).toMatch(/listSavedViews/)
    expect(useP).toMatch(/listEntityTypes/)

    const usePrev = readFileSync(
      resolve(dir, "useBindingPreview.ts"),
      "utf-8",
    )
    expect(usePrev).toMatch(/export function useBindingPreview\b/)
    expect(usePrev).toMatch(/executeSavedView/)
    expect(usePrev).toMatch(/resolveBinding/)
  })

  it("AtomInspectorDispatch consumes BindingPicker (5 inspectors wired)", async () => {
    const { readFileSync } = await import("fs")
    const { resolve } = await import("path")
    const src = readFileSync(
      resolve(
        __dirname,
        "../../../bridgeable-admin/components/widget-builder/inspectors/AtomInspectorDispatch.tsx",
      ),
      "utf-8",
    )
    expect(src).toMatch(/import \{ BindingPicker \}/)
    // Inspector binding update hook present.
    expect(src).toMatch(/export function useAtomBindingUpdater\b/)
    // ValueDisplay + Button + Image + ConditionalContainer + Repeater
    // all carry the BindingPicker (atomType="…") strings.
    expect(src).toMatch(/atomType="value_display"/)
    expect(src).toMatch(/atomType="button"/)
    expect(src).toMatch(/atomType="image"/)
    expect(src).toMatch(/atomType="conditional_container"/)
    expect(src).toMatch(/atomType="repeater_atom"/)
  })

  it("backend validators carries 5 bidirectional iteration_mode checks", async () => {
    const { readFileSync } = await import("fs")
    const { resolve } = await import("path")
    const src = readFileSync(
      resolve(
        __dirname,
        "../../../../../backend/app/services/widget_definitions/validators.py",
      ),
      "utf-8",
    )
    // Check 2 / 3 (per_row consumption + leaf-atom mode).
    // Strings are split across Python f-string concat; match smaller substrings.
    expect(src).toMatch(/per_row binding/)
    expect(src).toMatch(/single_record' or 'single_summary'/)
    // Check 4 (literal + iteration_mode rejection).
    expect(src).toMatch(/literal bindings must not carry iteration_mode/)
    // Check 5 (field_path requires iteration_mode + saved_view_id + field_path).
    // Python f-strings split across lines; match on smaller substrings.
    expect(src).toMatch(/binding requires iteration_mode/)
    expect(src).toMatch(/non-empty saved_view_id/)
    expect(src).toMatch(/non-empty field_path/)
  })

  it("useWidgetValidation mirrors backend checks", async () => {
    const { readFileSync } = await import("fs")
    const { resolve } = await import("path")
    const src = readFileSync(
      resolve(
        __dirname,
        "../../../bridgeable-admin/hooks/useWidgetValidation.ts",
      ),
      "utf-8",
    )
    expect(src).toMatch(/checkBindingsCatalog/)
    expect(src).toMatch(/cannot carry iteration_mode/)
    expect(src).toMatch(/per_row but/)
    expect(src).toMatch(/must be consumed by a repeater/)
  })
})
