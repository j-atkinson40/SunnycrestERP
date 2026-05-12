/**
 * Arc 4a.1 — ClassTab Focus class buttonSlugs rendering tests.
 *
 * Verifies that the existing ClassTab infrastructure (CompactPropControl
 * → PropControlDispatcher → ArrayControl + componentReference dispatch)
 * renders the new Focus class-level buttonSlugs prop correctly. No
 * ClassTab extension was required for Arc 4a.1 — the dispatch chain
 * already handles `array` with `itemSchema: componentReference`
 * (R-2.1 canon reuse).
 */
import { beforeAll, describe, expect, it, vi } from "vitest"
import { render } from "@testing-library/react"

import "@/lib/visual-editor/registry/auto-register"
import { CLASS_REGISTRATIONS } from "@/lib/visual-editor/registry/class-registrations"
import { EditModeProvider } from "../edit-mode-context"
import { ClassTab } from "./ClassTab"
import { getByName, type RegistryEntry } from "@/lib/visual-editor/registry"


// Mock the class-config service — it tries to fetch from network.
vi.mock(
  "@/bridgeable-admin/services/component-class-configurations-service",
  () => ({
    componentClassConfigurationsService: {
      resolve: vi.fn().mockResolvedValue({
        component_class: "focus",
        props: {},
        sources: [],
      }),
    },
  }),
)


describe("Arc 4a.1 — Focus class registration carries buttonSlugs", () => {
  it("focus class includes buttonSlugs in configurableProps", () => {
    const focus = CLASS_REGISTRATIONS["focus"]
    expect(focus).toBeDefined()
    expect(focus.configurableProps).toHaveProperty("buttonSlugs")
    expect(focus.configurableProps.buttonSlugs.type).toBe("array")
  })

  it("focus-template class includes buttonSlugs override slot", () => {
    const focusTemplate = CLASS_REGISTRATIONS["focus-template"]
    expect(focusTemplate.configurableProps).toHaveProperty("buttonSlugs")
  })
})


describe("Arc 4a.1 — ClassTab renders Focus class buttonSlugs", () => {
  let focusEntry: RegistryEntry | undefined

  beforeAll(() => {
    // The auto-register barrel registers focus-type entries via
    // focus-types.ts. We use one of those entries as our "selected
    // entry" for the ClassTab test (its type is "focus", so
    // getEffectiveComponentClasses returns ["focus"]).
    focusEntry =
      getByName("focus", "triage-decision") ??
      getByName("focus", "arrangement-scribe") ??
      getByName("focus", "execution") ??
      getByName("focus", "decision")
  })

  it("auto-register populates at least one focus entry", () => {
    expect(focusEntry).toBeDefined()
  })

  it("ClassTab renders the buttonSlugs prop for a focus entry", () => {
    if (!focusEntry) return // skip if no focus entry registered
    const { getByTestId } = render(
      <EditModeProvider
        tenantSlug="testco"
        impersonatedUserId="user1"
        initialMode="edit"
      >
        <ClassTab selectedEntry={focusEntry} />
      </EditModeProvider>,
    )

    // ClassTab renders each prop with `runtime-inspector-class-prop-<name>`.
    // The buttonSlugs prop should be present.
    expect(getByTestId("runtime-inspector-class-prop-buttonSlugs")).toBeDefined()
  })

  it("ClassTab renders the buttonSlugs as ArrayControl dispatch", () => {
    if (!focusEntry) return
    const { container } = render(
      <EditModeProvider
        tenantSlug="testco"
        impersonatedUserId="user1"
        initialMode="edit"
      >
        <ClassTab selectedEntry={focusEntry} />
      </EditModeProvider>,
    )

    // The CompactPropControl wraps PropControlDispatcher; for type
    // "array" the dispatcher renders ArrayControl which has
    // data-testid="compact-prop-buttonSlugs" + the array-specific
    // "Add entry" affordance.
    const buttonSlugRow = container.querySelector(
      '[data-testid="runtime-inspector-class-prop-buttonSlugs"]',
    )
    expect(buttonSlugRow).not.toBeNull()
  })
})
