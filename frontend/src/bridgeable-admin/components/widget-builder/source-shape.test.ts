/**
 * WB-4a source-shape regression gates (per entry 31).
 *
 * Six+ gates that catch architectural regression by inspecting the
 * source text of the WB-4a substrate. Faster + more reliable than
 * full behavior tests for catching "someone reverted to the wrong
 * pattern" footguns.
 */
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { dirname, resolve } from "node:path"

import { describe, it, expect } from "vitest"


const HERE = dirname(fileURLToPath(import.meta.url))


function read(relPath: string): string {
  return readFileSync(resolve(HERE, relPath), "utf8")
}


describe("WB-4a source-shape regression gates", () => {
  it("Gate 1: useWidgetAutoSave debounces at 200 ms (Step 8 spec)", () => {
    const src = read("../../hooks/useWidgetAutoSave.ts")
    expect(src).toMatch(/AUTO_SAVE_DEBOUNCE_MS\s*=\s*200/)
  })

  it("Gate 2: useWidgetAutoSave uses AbortController for in-flight cancellation", () => {
    const src = read("../../hooks/useWidgetAutoSave.ts")
    expect(src).toMatch(/AbortController/)
    expect(src).toMatch(/inFlightAbortRef/)
  })

  it("Gate 3: dispatch.ts reads published_composition_blob FIRST", () => {
    const src = read("../../../lib/widget-builder/runtime/dispatch.ts")
    // The hasPublished check must precede hasDraft.
    const publishedIdx = src.indexOf("hasPublished")
    const draftIdx = src.indexOf("hasDraft")
    expect(publishedIdx).toBeGreaterThan(-1)
    expect(draftIdx).toBeGreaterThan(-1)
    expect(publishedIdx).toBeLessThan(draftIdx)
  })

  it("Gate 4: WidgetBuilderPage calls refreshComposedWidgets after Publish", () => {
    const src = read("./WidgetBuilderPage.tsx")
    expect(src).toMatch(/refreshComposedWidgets/)
    // The actual call site (not the import) must follow handlePublish.
    const publishIdx = src.indexOf("handlePublish")
    const callIdx = src.indexOf("refreshComposedWidgets()", publishIdx)
    expect(publishIdx).toBeGreaterThan(-1)
    expect(callIdx).toBeGreaterThan(publishIdx)
  })

  it("Gate 5: AtomPalette ships all 9 atoms in the 2 canonical sections", () => {
    const src = read("./AtomPalette.tsx")
    // Atom types — 9 total.
    const atoms = [
      "text_label",
      "value_display",
      "icon",
      "status_badge",
      "divider",
      "image",
      "button",
      "conditional_container",
      "repeater_atom",
    ]
    for (const a of atoms) {
      expect(src).toMatch(new RegExp(`"${a}"`))
    }
    // Two sections.
    expect(src).toMatch(/Content & Visual/)
    expect(src).toMatch(/Container & Interactive/)
  })

  it("Gate 6: WidgetBuilderPage uses PointerSensor + KeyboardSensor (Q-40)", () => {
    const src = read("./WidgetBuilderPage.tsx")
    expect(src).toMatch(/PointerSensor/)
    expect(src).toMatch(/KeyboardSensor/)
    // 3px activation distance per Q-9 canon.
    expect(src).toMatch(/distance:\s*3/)
  })

  it("Gate 7: WidgetCanvas is NOT FF-2 substrate (build-new flex-stack)", () => {
    const src = read("./WidgetCanvas.tsx")
    // Must NOT import FF-2 substrate.
    expect(src).not.toMatch(/PlacedWidgetCore/)
    expect(src).not.toMatch(/WidgetFreeFormLayer/)
    expect(src).not.toMatch(/FreeFormPlacedWidget/)
    // Must use ComposedWidget for WYSIWYG.
    expect(src).toMatch(/ComposedWidget/)
  })

  it("Gate 8: r106 migration backfills existing composed widgets", () => {
    const src = read(
      "../../../../../backend/alembic/versions/r106_widget_definitions_published_blob.py",
    )
    expect(src).toMatch(
      /UPDATE widget_definitions[\s\S]*?SET published_composition_blob = composition_blob/,
    )
    expect(src).toMatch(/WHERE composition_blob IS NOT NULL/)
  })

  // ── WB-4b gates ──────────────────────────────────────────────────

  it("WB-4b Gate 9: 9 per-atom inspectors are defined", () => {
    const src = read("./inspectors/AtomInspectorDispatch.tsx")
    const inspectors = [
      "TextLabelInspector",
      "ValueDisplayInspector",
      "IconInspector",
      "StatusBadgeInspector",
      "DividerInspector",
      "ButtonInspector",
      "ImageInspector",
      "ConditionalContainerInspector",
      "RepeaterAtomInspector",
    ]
    for (const i of inspectors) {
      expect(src).toMatch(new RegExp(`function ${i}`))
    }
    // Dispatch component is exported.
    expect(src).toMatch(/export function AtomInspectorDispatch/)
    // No-selection path renders the CanvasRootInspector.
    expect(src).toMatch(/function CanvasRootInspector/)
  })

  it("WB-4b Gate 10: useWidgetValidation hook exists + returns errorsByAtom", () => {
    const src = read("../../hooks/useWidgetValidation.ts")
    expect(src).toMatch(/export function useWidgetValidation/)
    expect(src).toMatch(/errorsByAtom/)
    expect(src).toMatch(/hasErrors/)
  })

  it("WB-4b Gate 11: WidgetListPage exists at expected route mount", () => {
    const src = read("./WidgetListPage.tsx")
    expect(src).toMatch(/export default function WidgetListPage/)
    expect(src).toMatch(/\+ New Widget/)
    // Tier filter component present.
    expect(src).toMatch(/widget-list-tier-filter/)
  })

  it("WB-4b Gate 12: Pydantic ConditionalContainerConfig has alignment", () => {
    const src = read(
      "../../../../../backend/app/schemas/widget_composition.py",
    )
    // alignment field declared on ConditionalContainerConfig (or its
    // shared vocab indirection). Schema-extension lock.
    expect(src).toMatch(/alignment: Optional\[_AlignmentFour\]/)
  })

  it("WB-4b Gate 13: TypeScript ConditionalContainerConfig has alignment", () => {
    const src = read("../../../lib/widget-builder/types/composition-blob.ts")
    expect(src).toMatch(/alignment\?: AlignmentFour/)
  })

  it("WB-4b Gate 14: AtomErrorIndicator + ErrorSummary present", () => {
    const ind = read("./AtomErrorIndicator.tsx")
    expect(ind).toMatch(/export function AtomErrorIndicator/)
    expect(ind).toMatch(/outline-status-error/)
    const sum = read("./ErrorSummary.tsx")
    expect(sum).toMatch(/export function ErrorSummary/)
    expect(sum).toMatch(/onLocate/)
  })

  it("WB-4b Gate 15: Publish button respects validation error state", () => {
    const src = read("./WidgetBuilderPage.tsx")
    expect(src).toMatch(/disabled={publishing \|\| validation\.hasErrors}/)
    expect(src).toMatch(/data-validation-blocked/)
  })

  it("WB-4b Gate 16: backend strict validator enforces required fields", () => {
    const src = read(
      "../../../../../backend/app/services/widget_definitions/validators.py",
    )
    expect(src).toMatch(/validate_composition_blob_strict/)
    // The required-field rule for text_label lives across multi-line
    // f-strings — gate via the atom_type token + the canonical
    // "either `config.text` or a binding" phrase.
    expect(src).toMatch(/text_label/)
    expect(src).toMatch(/either `config\.text` or a binding/)
    expect(src).toMatch(/requires non-empty `config\.alt`/)
  })

  it("WB-4b Gate 17: publish.py invokes the strict validator", () => {
    const src = read(
      "../../../../../backend/app/services/widget_definitions/publish.py",
    )
    expect(src).toMatch(/validate_composition_blob_strict/)
  })
})
