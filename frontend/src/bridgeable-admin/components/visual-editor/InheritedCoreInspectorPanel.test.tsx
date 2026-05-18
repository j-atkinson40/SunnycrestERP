/**
 * InheritedCoreInspectorPanel tests — sub-arc C-2.2c.
 *
 * Covers:
 *   - mount/unmount of the side panel
 *   - read-only display of core properties
 *   - "Edit core in Tier 1" navigates immediately when clean
 *   - "Edit core in Tier 1" raises confirm dialog when dirty
 *   - Save & continue saves draft then navigates
 *   - Discard & continue discards then navigates
 *   - Cancel keeps panel open + no navigation
 *   - Close button + footer-close dismiss panel
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import { InheritedCoreInspectorPanel } from "./InheritedCoreInspectorPanel"
import type { CoreRecord } from "@/bridgeable-admin/services/focus-cores-service"

const CORE: CoreRecord = {
  id: "core-abc-123",
  core_slug: "scheduling-kanban-core",
  display_name: "Scheduling Kanban Core",
  description: null,
  registered_component_kind: "focus-template",
  registered_component_name: "SchedulingKanbanCore",
  default_starting_column: 0,
  default_column_span: 12,
  default_row_index: 0,
  min_column_span: 6,
  max_column_span: 12,
  canvas_config: {},
  chrome: { preset: "card", elevation: 37 },
  version: 3,
  is_active: true,
  created_at: "",
  updated_at: "",
}

const onNavigateToTier1Core = vi.fn()
const onClose = vi.fn()
const saveDraft = vi.fn()
const discardDraft = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  saveDraft.mockResolvedValue(undefined)
})

afterEach(() => {
  vi.clearAllMocks()
})

describe("InheritedCoreInspectorPanel", () => {
  it("renders the core's display name, slug, and version", () => {
    render(
      <InheritedCoreInspectorPanel
        core={CORE}
        isDirty={false}
        saveDraft={saveDraft}
        discardDraft={discardDraft}
        onNavigateToTier1Core={onNavigateToTier1Core}
        onClose={onClose}
      />,
    )
    expect(
      screen.getByTestId("inherited-core-inspector-panel"),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("inherited-core-display-name").textContent,
    ).toBe("Scheduling Kanban Core")
    expect(
      screen.getByTestId("inherited-core-slug").textContent,
    ).toBe("scheduling-kanban-core · v3")
  })

  it("renders read-only chrome blob fields", () => {
    render(
      <InheritedCoreInspectorPanel
        core={CORE}
        isDirty={false}
        saveDraft={saveDraft}
        discardDraft={discardDraft}
        onNavigateToTier1Core={onNavigateToTier1Core}
        onClose={onClose}
      />,
    )
    expect(
      screen.getByTestId("inherited-core-chrome-preset"),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("inherited-core-chrome-preset").textContent,
    ).toBe("card")
    expect(
      screen.getByTestId("inherited-core-chrome-elevation").textContent,
    ).toBe("37")
  })

  it("renders the registered component kind + name", () => {
    render(
      <InheritedCoreInspectorPanel
        core={CORE}
        isDirty={false}
        saveDraft={saveDraft}
        discardDraft={discardDraft}
        onNavigateToTier1Core={onNavigateToTier1Core}
        onClose={onClose}
      />,
    )
    expect(
      screen.getByTestId("inherited-core-component-kind").textContent,
    ).toBe("focus-template")
    expect(
      screen.getByTestId("inherited-core-component-name").textContent,
    ).toBe("SchedulingKanbanCore")
  })

  it("renders loading state when core is null", () => {
    render(
      <InheritedCoreInspectorPanel
        core={null}
        isDirty={false}
        saveDraft={saveDraft}
        discardDraft={discardDraft}
        onNavigateToTier1Core={onNavigateToTier1Core}
        onClose={onClose}
      />,
    )
    expect(screen.getByTestId("inherited-core-loading")).toBeInTheDocument()
  })

  it("Close button invokes onClose", () => {
    render(
      <InheritedCoreInspectorPanel
        core={CORE}
        isDirty={false}
        saveDraft={saveDraft}
        discardDraft={discardDraft}
        onNavigateToTier1Core={onNavigateToTier1Core}
        onClose={onClose}
      />,
    )
    fireEvent.click(screen.getByTestId("inherited-core-close"))
    expect(onClose).toHaveBeenCalled()
  })

  it("Edit-core navigates directly when isDirty=false", () => {
    render(
      <InheritedCoreInspectorPanel
        core={CORE}
        isDirty={false}
        saveDraft={saveDraft}
        discardDraft={discardDraft}
        onNavigateToTier1Core={onNavigateToTier1Core}
        onClose={onClose}
      />,
    )
    fireEvent.click(screen.getByTestId("inherited-core-edit-button"))
    expect(onNavigateToTier1Core).toHaveBeenCalledWith("core-abc-123")
    // No confirm dialog renders.
    expect(
      screen.queryByTestId("inherited-core-confirm-dialog"),
    ).not.toBeInTheDocument()
  })

  it("Edit-core raises confirm dialog when isDirty=true", () => {
    render(
      <InheritedCoreInspectorPanel
        core={CORE}
        isDirty={true}
        saveDraft={saveDraft}
        discardDraft={discardDraft}
        onNavigateToTier1Core={onNavigateToTier1Core}
        onClose={onClose}
      />,
    )
    fireEvent.click(screen.getByTestId("inherited-core-edit-button"))
    expect(
      screen.getByTestId("inherited-core-confirm-dialog"),
    ).toBeInTheDocument()
    // No navigation triggered yet.
    expect(onNavigateToTier1Core).not.toHaveBeenCalled()
  })

  it("Save & continue saves the draft then navigates", async () => {
    render(
      <InheritedCoreInspectorPanel
        core={CORE}
        isDirty={true}
        saveDraft={saveDraft}
        discardDraft={discardDraft}
        onNavigateToTier1Core={onNavigateToTier1Core}
        onClose={onClose}
      />,
    )
    fireEvent.click(screen.getByTestId("inherited-core-edit-button"))
    fireEvent.click(screen.getByTestId("inherited-core-confirm-save"))
    await waitFor(() => {
      expect(saveDraft).toHaveBeenCalled()
      expect(onNavigateToTier1Core).toHaveBeenCalledWith("core-abc-123")
    })
    expect(discardDraft).not.toHaveBeenCalled()
  })

  it("Discard & continue discards then navigates", () => {
    render(
      <InheritedCoreInspectorPanel
        core={CORE}
        isDirty={true}
        saveDraft={saveDraft}
        discardDraft={discardDraft}
        onNavigateToTier1Core={onNavigateToTier1Core}
        onClose={onClose}
      />,
    )
    fireEvent.click(screen.getByTestId("inherited-core-edit-button"))
    fireEvent.click(screen.getByTestId("inherited-core-confirm-discard"))
    expect(discardDraft).toHaveBeenCalled()
    expect(onNavigateToTier1Core).toHaveBeenCalledWith("core-abc-123")
    expect(saveDraft).not.toHaveBeenCalled()
  })

  it("Cancel closes the confirm dialog without saving / discarding / navigating", () => {
    render(
      <InheritedCoreInspectorPanel
        core={CORE}
        isDirty={true}
        saveDraft={saveDraft}
        discardDraft={discardDraft}
        onNavigateToTier1Core={onNavigateToTier1Core}
        onClose={onClose}
      />,
    )
    fireEvent.click(screen.getByTestId("inherited-core-edit-button"))
    expect(
      screen.getByTestId("inherited-core-confirm-dialog"),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByTestId("inherited-core-confirm-cancel"))
    expect(
      screen.queryByTestId("inherited-core-confirm-dialog"),
    ).not.toBeInTheDocument()
    expect(saveDraft).not.toHaveBeenCalled()
    expect(discardDraft).not.toHaveBeenCalled()
    expect(onNavigateToTier1Core).not.toHaveBeenCalled()
    // Close was not called either — the dialog dismissed itself but
    // the side panel stays mounted.
    expect(onClose).not.toHaveBeenCalled()
  })

  it("shows empty-chrome notice when core ships with empty chrome blob", () => {
    render(
      <InheritedCoreInspectorPanel
        core={{ ...CORE, chrome: {} }}
        isDirty={false}
        saveDraft={saveDraft}
        discardDraft={discardDraft}
        onNavigateToTier1Core={onNavigateToTier1Core}
        onClose={onClose}
      />,
    )
    expect(
      screen.getByTestId("inherited-core-chrome-empty"),
    ).toBeInTheDocument()
  })
})
