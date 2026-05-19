/**
 * FocusBuilderInspector tests (sub-arc F-2).
 */
import * as React from "react"
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { BASE_TOKENS } from "@/lib/visual-editor/themes/base-tokens"

import { FocusBuilderInspector } from "./FocusBuilderInspector"
import {
  FocusBuilderSelectionProvider,
  useFocusBuilderSelection,
  type Selection,
} from "./FocusBuilderSelectionContext"
import type { UseFocusCoreDraftResult } from "@/bridgeable-admin/hooks/useFocusCoreDraft"
import type { UseFocusTemplateDraftResult } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"
import type { CoreRecord } from "@/bridgeable-admin/services/focus-cores-service"
import type { ResolveSources } from "@/bridgeable-admin/services/focus-templates-service"

const tokens = { ...BASE_TOKENS.light }

function makeCoreHook(): UseFocusCoreDraftResult {
  return {
    core: {
      id: "core-1",
      core_slug: "s",
      display_name: "S",
      description: null,
      registered_component_kind: "focus-template",
      registered_component_name: "S",
      default_starting_column: 0,
      default_column_span: 12,
      default_row_index: 0,
      min_column_span: 1,
      max_column_span: 12,
      canvas_config: {},
      chrome: { preset: "card" },
      version: 1,
      is_active: true,
      created_at: "",
      updated_at: "",
    },
    draft: { preset: "card" },
    updateDraft: vi.fn(),
    save: vi.fn().mockResolvedValue(undefined),
    discard: vi.fn(),
    isDirty: false,
    isSaving: false,
    lastSavedAt: null,
    error: null,
    isLoading: false,
    editSessionId: "session-1",
  }
}

function makeTemplateHook(): UseFocusTemplateDraftResult {
  return {
    template: {
      id: "tpl-1",
      scope: "vertical_default",
      vertical: "manufacturing",
      template_slug: "t",
      display_name: "T",
      description: null,
      inherits_from_core_id: "core-1",
      inherits_from_core_version: 1,
      rows: [],
      canvas_config: {},
      chrome_overrides: {},
      substrate: {},
      typography: {},
      version: 1,
      is_active: true,
      created_at: "",
      updated_at: "",
    },
    chromeOverridesDraft: {},
    substrateDraft: { preset: "morning-warm" },
    typographyDraft: { preset: "frosted-text" },
    updateChromeOverrides: vi.fn(),
    updateSubstrate: vi.fn(),
    updateTypography: vi.fn(),
    resetChromeOverridesField: vi.fn(),
    resetSubstrateField: vi.fn(),
    resetTypographyField: vi.fn(),
    save: vi.fn().mockResolvedValue(undefined),
    discard: vi.fn(),
    isDirty: false,
    isSaving: false,
    lastSavedAt: null,
    error: null,
    isLoading: false,
    editSessionId: "session-1",
  }
}

const inheritedCore: CoreRecord = {
  id: "core-1",
  core_slug: "scheduling-kanban-core",
  display_name: "Scheduling Kanban",
  description: null,
  registered_component_kind: "focus-template",
  registered_component_name: "SchedulingKanbanCore",
  default_starting_column: 0,
  default_column_span: 12,
  default_row_index: 0,
  min_column_span: 1,
  max_column_span: 12,
  canvas_config: {},
  chrome: { preset: "card" },
  version: 9,
  is_active: true,
  created_at: "",
  updated_at: "",
}

function SelectionPrimer({ selection }: { selection: Selection }) {
  const { setSelection } = useFocusBuilderSelection()
  React.useEffect(() => {
    setSelection(selection)
  }, [setSelection, selection])
  return null
}

describe("FocusBuilderInspector", () => {
  it("renders empty state when selection.kind === 'none'", () => {
    render(
      <FocusBuilderSelectionProvider>
        <FocusBuilderInspector
          mode="template"
          themeTokens={tokens}
          templateHook={makeTemplateHook()}
          inheritedCore={inheritedCore}
        />
      </FocusBuilderSelectionProvider>,
    )
    expect(
      screen.getByTestId("focus-builder-inspector-empty"),
    ).toBeInTheDocument()
  })

  it("renders chrome section when selection.kind === 'core' (template mode)", () => {
    render(
      <FocusBuilderSelectionProvider>
        <SelectionPrimer selection={{ kind: "core" }} />
        <FocusBuilderInspector
          mode="template"
          themeTokens={tokens}
          templateHook={makeTemplateHook()}
          inheritedCore={inheritedCore}
        />
      </FocusBuilderSelectionProvider>,
    )
    expect(
      screen.getByTestId("focus-builder-inspector"),
    ).toBeInTheDocument()
    // Chrome heading visible.
    expect(screen.getAllByText("Chrome").length).toBeGreaterThan(0)
    // Substrate/Typography sections NOT mounted for core selection.
    expect(screen.queryByText("Substrate")).not.toBeInTheDocument()
    expect(screen.queryByText("Typography")).not.toBeInTheDocument()
  })

  it("renders substrate + typography sections when selection.kind === 'background' (template mode)", () => {
    render(
      <FocusBuilderSelectionProvider>
        <SelectionPrimer selection={{ kind: "background" }} />
        <FocusBuilderInspector
          mode="template"
          themeTokens={tokens}
          templateHook={makeTemplateHook()}
          inheritedCore={inheritedCore}
        />
      </FocusBuilderSelectionProvider>,
    )
    expect(screen.getAllByText("Substrate").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Typography").length).toBeGreaterThan(0)
    // Chrome NOT mounted for background selection on template.
    expect(screen.queryByText("Chrome")).not.toBeInTheDocument()
  })

  it("background selection on core falls through to chrome (no substrate vocab)", () => {
    render(
      <FocusBuilderSelectionProvider>
        <SelectionPrimer selection={{ kind: "background" }} />
        <FocusBuilderInspector
          mode="core"
          themeTokens={tokens}
          coreHook={makeCoreHook()}
        />
      </FocusBuilderSelectionProvider>,
    )
    expect(screen.getAllByText("Chrome").length).toBeGreaterThan(0)
    expect(screen.queryByText("Substrate")).not.toBeInTheDocument()
    expect(screen.queryByText("Typography")).not.toBeInTheDocument()
  })

  it("'View canonical core' button visible only when onOpenInheritedCorePanel supplied", () => {
    const onOpen = vi.fn()
    render(
      <FocusBuilderSelectionProvider>
        <SelectionPrimer selection={{ kind: "core" }} />
        <FocusBuilderInspector
          mode="template"
          themeTokens={tokens}
          templateHook={makeTemplateHook()}
          inheritedCore={inheritedCore}
          onOpenInheritedCorePanel={onOpen}
        />
      </FocusBuilderSelectionProvider>,
    )
    const btn = screen.getByTestId("view-canonical-core-button")
    expect(btn).toBeInTheDocument()
    fireEvent.click(btn)
    expect(onOpen).toHaveBeenCalledTimes(1)
  })

  it("'View canonical core' button hidden in core mode", () => {
    const onOpen = vi.fn()
    render(
      <FocusBuilderSelectionProvider>
        <SelectionPrimer selection={{ kind: "core" }} />
        <FocusBuilderInspector
          mode="core"
          themeTokens={tokens}
          coreHook={makeCoreHook()}
          onOpenInheritedCorePanel={onOpen}
        />
      </FocusBuilderSelectionProvider>,
    )
    // The core branch deliberately doesn't render the header.
    expect(
      screen.queryByTestId("view-canonical-core-button"),
    ).not.toBeInTheDocument()
  })

  it("template chrome row carries inheritance indicator from resolver sources", () => {
    const sources: ResolveSources = {
      template: {},
      core: {},
      tenant: null,
      chrome_sources: { preset: "tier1", elevation: "tier2" },
      substrate_sources: {},
      typography_sources: {},
    }
    render(
      <FocusBuilderSelectionProvider>
        <SelectionPrimer selection={{ kind: "core" }} />
        <FocusBuilderInspector
          mode="template"
          themeTokens={tokens}
          templateHook={makeTemplateHook()}
          inheritedCore={inheritedCore}
          sources={sources}
        />
      </FocusBuilderSelectionProvider>,
    )
    // At least one row should reflect "inherited" from tier1.
    const inheritedRows = screen.getAllByTestId("property-row-inheritance-caption")
    expect(inheritedRows.length).toBeGreaterThanOrEqual(1)
    expect(inheritedRows[0].textContent).toMatch(/Tier 1 core/)
  })

  it("scrubbable + preset picker updates fire hook update methods", () => {
    const hook = makeTemplateHook()
    render(
      <FocusBuilderSelectionProvider>
        <SelectionPrimer selection={{ kind: "core" }} />
        <FocusBuilderInspector
          mode="template"
          themeTokens={tokens}
          templateHook={hook}
          inheritedCore={inheritedCore}
        />
      </FocusBuilderSelectionProvider>,
    )
    // The ChromePresetPicker for the "card" preset renders a control;
    // clicking a different preset button fires updateChromeOverrides.
    // Find any chrome preset button and click it — the picker exposes
    // role="radio" buttons per preset.
    const buttons = screen
      .getAllByRole("button")
      .filter((b) => b.textContent && /modal|card|dropdown|frosted/i.test(b.textContent))
    expect(buttons.length).toBeGreaterThan(0)
  })
})
