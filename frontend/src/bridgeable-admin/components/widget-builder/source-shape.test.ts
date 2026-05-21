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
})
