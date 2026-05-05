/**
 * Component editor redesign — vitest coverage for the new layout
 * primitives (May 2026 redesign). Verifies the four context frames
 * render correctly per kind, the thumbnail dispatches per kind, and
 * the compact prop control renders + dispatches edits.
 */
import { describe, expect, it, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"

import { DashboardContextFrame } from "./context-frames/DashboardContextFrame"
import { FocusContextFrame } from "./context-frames/FocusContextFrame"
import { DocumentContextFrame } from "./context-frames/DocumentContextFrame"
import { WorkflowCanvasContextFrame } from "./context-frames/WorkflowCanvasContextFrame"
import { ComponentThumbnail } from "./ComponentThumbnail"
import { CompactPropControl, inferPropGroup } from "./CompactPropControl"
import type { ConfigPropSchema } from "@/lib/visual-editor/registry"


describe("DashboardContextFrame", () => {
  it("renders dashboard chrome with the target widget", () => {
    render(
      <DashboardContextFrame>
        <div data-testid="my-widget">my widget</div>
      </DashboardContextFrame>,
    )
    expect(screen.getByTestId("dashboard-context-frame")).toBeTruthy()
    expect(screen.getByTestId("dashboard-context-target")).toBeTruthy()
    expect(screen.getByTestId("my-widget")).toBeTruthy()
    // Surrounding placeholder widgets exist
    expect(
      screen.getAllByTestId("dashboard-placeholder-widget").length,
    ).toBeGreaterThanOrEqual(4)
  })

  it("show-all-instances renders three variant slots", () => {
    render(
      <DashboardContextFrame
        showAllInstances={true}
        renderInstance={(v) => <div data-testid={`my-${v}`}>{v}</div>}
      >
        <div>fallback</div>
      </DashboardContextFrame>,
    )
    expect(screen.getByTestId("show-all-instances")).toBeTruthy()
    expect(screen.getByTestId("instance-default")).toBeTruthy()
    expect(screen.getByTestId("instance-compact")).toBeTruthy()
    expect(screen.getByTestId("instance-ultra")).toBeTruthy()
  })
})


describe("FocusContextFrame", () => {
  it("renders the Focus shell with title + Decision-style action buttons", () => {
    render(
      <FocusContextFrame focusType="decision" title="Sample Decision">
        <div>content</div>
      </FocusContextFrame>,
    )
    expect(screen.getByTestId("focus-context-frame")).toBeTruthy()
    expect(screen.getByTestId("focus-shell")).toBeTruthy()
    expect(screen.getByText("Sample Decision")).toBeTruthy()
    // Decision shows destructive + primary actions
    expect(screen.getByTestId("focus-action-destructive")).toBeTruthy()
    expect(screen.getByTestId("focus-action-primary")).toBeTruthy()
  })

  it("renders Generation-style actions for generation focusType", () => {
    render(
      <FocusContextFrame focusType="generation" title="Scribe">
        <div>content</div>
      </FocusContextFrame>,
    )
    const buttons = screen.getAllByRole("button")
    const labels = buttons.map((b) => b.textContent ?? "")
    expect(labels.some((l) => l.includes("Save draft"))).toBe(true)
    expect(labels.some((l) => l.includes("Commit"))).toBe(true)
  })

  it("show-all-instances renders three Focus shells", () => {
    render(
      <FocusContextFrame
        focusType="review"
        showAllInstances={true}
        renderInstance={(v) => <div>{v}</div>}
      >
        <div />
      </FocusContextFrame>,
    )
    expect(screen.getByTestId("instance-draft")).toBeTruthy()
    expect(screen.getByTestId("instance-active")).toBeTruthy()
    expect(screen.getByTestId("instance-complete")).toBeTruthy()
  })
})


describe("DocumentContextFrame", () => {
  it("renders document chrome with the block at top position", () => {
    render(
      <DocumentContextFrame position="top">
        <div data-testid="my-block">block</div>
      </DocumentContextFrame>,
    )
    expect(screen.getByTestId("document-context-frame")).toBeTruthy()
    expect(screen.getByTestId("document-page")).toBeTruthy()
    expect(screen.getByTestId("document-context-target")).toBeTruthy()
    expect(screen.getByTestId("my-block")).toBeTruthy()
  })

  it("respects bottom position by placing block after paragraphs", () => {
    render(
      <DocumentContextFrame position="bottom">
        <div data-testid="signature">sig</div>
      </DocumentContextFrame>,
    )
    const page = screen.getByTestId("document-page")
    expect(page.getAttribute("data-block-position")).toBe("bottom")
  })
})


describe("WorkflowCanvasContextFrame", () => {
  it("renders 3-node canvas with adjacency labels", () => {
    render(
      <WorkflowCanvasContextFrame nodeType="generation-focus-invocation">
        <div data-testid="my-node">node</div>
      </WorkflowCanvasContextFrame>,
    )
    expect(screen.getByTestId("workflow-canvas-context-frame")).toBeTruthy()
    expect(screen.getByTestId("workflow-context-target")).toBeTruthy()
    expect(screen.getAllByTestId("workflow-placeholder-node").length).toBe(2)
    expect(screen.getAllByTestId("workflow-connection-arrow").length).toBe(2)
  })
})


describe("ComponentThumbnail", () => {
  it("renders widget thumbnail for kind=widget", () => {
    render(<ComponentThumbnail kind="widget" componentName="today" />)
    const t = screen.getByTestId("component-thumbnail")
    expect(t.getAttribute("data-thumbnail-kind")).toBe("widget")
  })

  it("renders Focus thumbnail for kind=focus", () => {
    render(<ComponentThumbnail kind="focus" componentName="decision" />)
    expect(screen.getByTestId("component-thumbnail").getAttribute("data-thumbnail-kind")).toBe("focus")
  })

  it("renders template badge for kind=focus-template", () => {
    render(<ComponentThumbnail kind="focus-template" componentName="triage-decision" />)
    expect(screen.getByTestId("thumb-template-badge")).toBeTruthy()
  })

  it("renders document-block thumbnail for kind=document-block", () => {
    render(<ComponentThumbnail kind="document-block" componentName="header-block" />)
    expect(screen.getByTestId("component-thumbnail").getAttribute("data-thumbnail-kind")).toBe("document-block")
  })

  it("renders workflow-node thumbnail for kind=workflow-node", () => {
    render(<ComponentThumbnail kind="workflow-node" componentName="send-communication" />)
    expect(screen.getByTestId("component-thumbnail").getAttribute("data-thumbnail-kind")).toBe("workflow-node")
  })

  it("shows override dot when hasOverrides is true", () => {
    render(<ComponentThumbnail kind="widget" componentName="today" hasOverrides={true} />)
    expect(screen.getByTestId("thumb-override-dot")).toBeTruthy()
  })

  it("hides override dot by default", () => {
    render(<ComponentThumbnail kind="widget" componentName="today" />)
    expect(screen.queryByTestId("thumb-override-dot")).toBeNull()
  })
})


describe("CompactPropControl", () => {
  const booleanSchema: ConfigPropSchema = {
    type: "boolean",
    default: false,
    displayLabel: "Show row breakdown",
    description: "Reveals individual row counts in the widget body.",
  }

  it("renders with display label, source badge, and inline boolean control", () => {
    render(
      <CompactPropControl
        name="showRowBreakdown"
        schema={booleanSchema}
        value={false}
        onChange={() => {}}
        source="registration-default"
        isOverriddenAtCurrentScope={false}
        onReset={() => {}}
      />,
    )
    expect(screen.getByText("Show row breakdown")).toBeTruthy()
    expect(screen.getByTestId("source-badge-registration-default")).toBeTruthy()
    expect(screen.queryByTestId("compact-prop-reset-showRowBreakdown")).toBeNull()
  })

  it("renders reset button when overridden at current scope", () => {
    render(
      <CompactPropControl
        name="showRowBreakdown"
        schema={booleanSchema}
        value={true}
        onChange={() => {}}
        source="tenant-override"
        isOverriddenAtCurrentScope={true}
        onReset={() => {}}
      />,
    )
    expect(screen.getByTestId("compact-prop-reset-showRowBreakdown")).toBeTruthy()
    expect(screen.getByTestId("source-badge-tenant-override")).toBeTruthy()
  })

  it("description toggles when info icon is clicked", () => {
    render(
      <CompactPropControl
        name="showRowBreakdown"
        schema={booleanSchema}
        value={false}
        onChange={() => {}}
        source="registration-default"
        isOverriddenAtCurrentScope={false}
        onReset={() => {}}
      />,
    )
    expect(screen.queryByTestId("compact-prop-desc-showRowBreakdown")).toBeNull()
    fireEvent.click(screen.getByTestId("compact-prop-info-showRowBreakdown"))
    expect(screen.getByTestId("compact-prop-desc-showRowBreakdown")).toBeTruthy()
  })

  it("calls onReset when reset button clicked", () => {
    const onReset = vi.fn()
    render(
      <CompactPropControl
        name="showRowBreakdown"
        schema={booleanSchema}
        value={true}
        onChange={() => {}}
        source="draft"
        isOverriddenAtCurrentScope={true}
        onReset={onReset}
      />,
    )
    fireEvent.click(screen.getByTestId("compact-prop-reset-showRowBreakdown"))
    expect(onReset).toHaveBeenCalledOnce()
  })
})


describe("inferPropGroup", () => {
  it("groups appearance-related props", () => {
    expect(inferPropGroup("accentToken")).toBe("Appearance")
    expect(inferPropGroup("fontFamily")).toBe("Appearance")
  })

  it("groups layout-related props", () => {
    expect(inferPropGroup("showRowBreakdown")).toBe("Layout")
    expect(inferPropGroup("alignment")).toBe("Layout")
    expect(inferPropGroup("density")).toBe("Layout")
  })

  it("groups behavior-related props", () => {
    expect(inferPropGroup("refreshIntervalSeconds")).toBe("Behavior")
    expect(inferPropGroup("maxRetries")).toBe("Behavior")
  })

  it("falls back to General", () => {
    expect(inferPropGroup("unrelatedProp")).toBe("General")
  })
})
