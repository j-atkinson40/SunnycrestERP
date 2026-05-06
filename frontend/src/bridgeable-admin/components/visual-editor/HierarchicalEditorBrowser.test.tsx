/**
 * HierarchicalEditorBrowser tests — May 2026 reorganization.
 *
 * Verifies the shared two-level browser pattern (categories +
 * templates) used by Focus Editor + Workflows.
 */
import { describe, expect, it, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import {
  HierarchicalEditorBrowser,
  type HierarchicalCategory,
  type HierarchicalTemplate,
} from "./HierarchicalEditorBrowser"


function makeCategories(): HierarchicalCategory[] {
  return [
    { id: "decision", label: "Decision Focus", description: "Bounded decisions" },
    { id: "generation", label: "Generation Focus", description: "Authoring" },
    { id: "execution", label: "Execution Focus" },
  ]
}


function makeTemplates(): HierarchicalTemplate[] {
  return [
    { id: "triage-decision", label: "Triage", categoryId: "decision" },
    {
      id: "funeral-scheduling",
      label: "Funeral Scheduling",
      categoryId: "decision",
      description: "Dispatcher kanban core",
    },
    {
      id: "arrangement-scribe",
      label: "Arrangement Scribe",
      categoryId: "generation",
    },
    // execution category has no templates — empty state
  ]
}


describe("HierarchicalEditorBrowser", () => {
  it("renders all categories with their child templates", () => {
    render(
      <HierarchicalEditorBrowser
        categories={makeCategories()}
        templates={makeTemplates()}
        selectedCategoryId={null}
        selectedTemplateId={null}
        search=""
        onSearchChange={() => {}}
        onSelectCategory={() => {}}
        onSelectTemplate={() => {}}
      />,
    )
    expect(screen.getByTestId("hierarchical-category-decision")).toBeTruthy()
    expect(screen.getByTestId("hierarchical-category-generation")).toBeTruthy()
    expect(screen.getByTestId("hierarchical-category-execution")).toBeTruthy()
    expect(screen.getByTestId("hierarchical-template-row-triage-decision")).toBeTruthy()
    expect(
      screen.getByTestId("hierarchical-template-row-funeral-scheduling"),
    ).toBeTruthy()
    expect(
      screen.getByTestId("hierarchical-template-row-arrangement-scribe"),
    ).toBeTruthy()
  })

  it("shows empty state for categories with no templates", () => {
    render(
      <HierarchicalEditorBrowser
        categories={makeCategories()}
        templates={makeTemplates()}
        selectedCategoryId={null}
        selectedTemplateId={null}
        search=""
        onSearchChange={() => {}}
        onSelectCategory={() => {}}
        onSelectTemplate={() => {}}
      />,
    )
    const executionTemplates = screen.getByTestId(
      "hierarchical-templates-execution",
    )
    expect(executionTemplates.textContent).toContain("No templates yet")
  })

  it("calls onSelectCategory when a category row is clicked", () => {
    const onSelectCategory = vi.fn()
    render(
      <HierarchicalEditorBrowser
        categories={makeCategories()}
        templates={makeTemplates()}
        selectedCategoryId={null}
        selectedTemplateId={null}
        search=""
        onSearchChange={() => {}}
        onSelectCategory={onSelectCategory}
        onSelectTemplate={() => {}}
      />,
    )
    fireEvent.click(screen.getByTestId("hierarchical-category-row-decision"))
    expect(onSelectCategory).toHaveBeenCalledWith("decision")
  })

  it("calls onSelectTemplate when a template row is clicked", () => {
    const onSelectTemplate = vi.fn()
    render(
      <HierarchicalEditorBrowser
        categories={makeCategories()}
        templates={makeTemplates()}
        selectedCategoryId={null}
        selectedTemplateId={null}
        search=""
        onSearchChange={() => {}}
        onSelectCategory={() => {}}
        onSelectTemplate={onSelectTemplate}
      />,
    )
    fireEvent.click(
      screen.getByTestId("hierarchical-template-row-funeral-scheduling"),
    )
    expect(onSelectTemplate).toHaveBeenCalledWith("funeral-scheduling")
  })

  it("filters categories + templates by search across labels and descriptions", () => {
    render(
      <HierarchicalEditorBrowser
        categories={makeCategories()}
        templates={makeTemplates()}
        selectedCategoryId={null}
        selectedTemplateId={null}
        search="dispatcher"
        onSearchChange={() => {}}
        onSelectCategory={() => {}}
        onSelectTemplate={() => {}}
      />,
    )
    // funeral-scheduling description contains "dispatcher" → its
    // parent (decision) shows; siblings without match are hidden.
    expect(screen.getByTestId("hierarchical-category-decision")).toBeTruthy()
    expect(
      screen.getByTestId("hierarchical-template-row-funeral-scheduling"),
    ).toBeTruthy()
    expect(screen.queryByTestId("hierarchical-category-generation")).toBeNull()
  })

  it("matches category-self when search hits a category label", () => {
    render(
      <HierarchicalEditorBrowser
        categories={makeCategories()}
        templates={makeTemplates()}
        selectedCategoryId={null}
        selectedTemplateId={null}
        search="generation"
        onSearchChange={() => {}}
        onSelectCategory={() => {}}
        onSelectTemplate={() => {}}
      />,
    )
    expect(screen.getByTestId("hierarchical-category-generation")).toBeTruthy()
    // generation has 1 template (arrangement-scribe), shown when
    // category itself matched.
    expect(
      screen.getByTestId("hierarchical-template-row-arrangement-scribe"),
    ).toBeTruthy()
  })

  it("renders selection state via data-selected attribute", () => {
    render(
      <HierarchicalEditorBrowser
        categories={makeCategories()}
        templates={makeTemplates()}
        selectedCategoryId="decision"
        selectedTemplateId="funeral-scheduling"
        search=""
        onSearchChange={() => {}}
        onSelectCategory={() => {}}
        onSelectTemplate={() => {}}
      />,
    )
    const tmplRow = screen.getByTestId(
      "hierarchical-template-row-funeral-scheduling",
    )
    expect(tmplRow.getAttribute("data-selected")).toBe("true")
    // Category-only selection is false because a template is also
    // selected (avoids ambiguous double-active highlight).
    const categoryRow = screen.getByTestId(
      "hierarchical-category-row-decision",
    )
    expect(categoryRow.getAttribute("data-selected")).toBe("false")
  })

  it("shows 'no categories match' when search has no hits anywhere", () => {
    render(
      <HierarchicalEditorBrowser
        categories={makeCategories()}
        templates={makeTemplates()}
        selectedCategoryId={null}
        selectedTemplateId={null}
        search="nonexistent-string-xyzqq"
        onSearchChange={() => {}}
        onSelectCategory={() => {}}
        onSelectTemplate={() => {}}
      />,
    )
    expect(screen.getByText(/No categories match/i)).toBeTruthy()
  })
})
