/**
 * CanvasContextMenu tests — sub-arc FF-5.
 *
 * Portal-rendered context menu. Tests assert visibility based on
 * isOpen, click → onAction + onClose composition, and the two
 * dismiss paths (Escape + click-outside).
 */
import { describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { CanvasContextMenu } from "./CanvasContextMenu"

describe("CanvasContextMenu", () => {
  it("renders nothing when isOpen is false", () => {
    render(
      <CanvasContextMenu
        isOpen={false}
        position={{ x: 100, y: 100 }}
        onClose={() => {}}
        onAction={() => {}}
      />,
    )
    expect(screen.queryByTestId("canvas-context-menu")).not.toBeInTheDocument()
  })

  it("renders all four options when isOpen is true", () => {
    render(
      <CanvasContextMenu
        isOpen
        position={{ x: 100, y: 100 }}
        onClose={() => {}}
        onAction={() => {}}
      />,
    )
    expect(screen.getByTestId("canvas-context-menu")).toBeInTheDocument()
    expect(screen.getByTestId("context-menu-action-front")).toBeInTheDocument()
    expect(
      screen.getByTestId("context-menu-action-forward"),
    ).toBeInTheDocument()
    expect(
      screen.getByTestId("context-menu-action-backward"),
    ).toBeInTheDocument()
    expect(screen.getByTestId("context-menu-action-back")).toBeInTheDocument()
  })

  it("each option fires onAction with correct action AND calls onClose", () => {
    const onAction = vi.fn()
    const onClose = vi.fn()
    render(
      <CanvasContextMenu
        isOpen
        position={{ x: 0, y: 0 }}
        onClose={onClose}
        onAction={onAction}
      />,
    )
    fireEvent.click(screen.getByTestId("context-menu-action-front"))
    expect(onAction).toHaveBeenLastCalledWith("front")
    expect(onClose).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByTestId("context-menu-action-forward"))
    expect(onAction).toHaveBeenLastCalledWith("forward")
    expect(onClose).toHaveBeenCalledTimes(2)

    fireEvent.click(screen.getByTestId("context-menu-action-backward"))
    expect(onAction).toHaveBeenLastCalledWith("backward")
    expect(onClose).toHaveBeenCalledTimes(3)

    fireEvent.click(screen.getByTestId("context-menu-action-back"))
    expect(onAction).toHaveBeenLastCalledWith("back")
    expect(onClose).toHaveBeenCalledTimes(4)
  })

  it("Escape key calls onClose", () => {
    const onClose = vi.fn()
    render(
      <CanvasContextMenu
        isOpen
        position={{ x: 0, y: 0 }}
        onClose={onClose}
        onAction={() => {}}
      />,
    )
    fireEvent.keyDown(document, { key: "Escape" })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("click outside menu calls onClose", () => {
    const onClose = vi.fn()
    render(
      <div data-testid="outside-anchor">
        <CanvasContextMenu
          isOpen
          position={{ x: 0, y: 0 }}
          onClose={onClose}
          onAction={() => {}}
        />
      </div>,
    )
    fireEvent.mouseDown(screen.getByTestId("outside-anchor"))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("click inside menu does not call onClose via the outside-handler", () => {
    // (Option click DOES call onClose, but via its own click handler;
    // the outside-mousedown handler must NOT additionally fire onClose
    // when the mousedown lands inside the menu.)
    const onClose = vi.fn()
    render(
      <CanvasContextMenu
        isOpen
        position={{ x: 0, y: 0 }}
        onClose={onClose}
        onAction={() => {}}
      />,
    )
    const menu = screen.getByTestId("canvas-context-menu")
    fireEvent.mouseDown(menu)
    expect(onClose).not.toHaveBeenCalled()
  })

  it("position prop translates to inline style top/left", () => {
    render(
      <CanvasContextMenu
        isOpen
        position={{ x: 250, y: 410 }}
        onClose={() => {}}
        onAction={() => {}}
      />,
    )
    const menu = screen.getByTestId("canvas-context-menu")
    const styleAttr = menu.getAttribute("style") ?? ""
    expect(styleAttr).toMatch(/top:\s*410px/i)
    expect(styleAttr).toMatch(/left:\s*250px/i)
    expect(styleAttr).toMatch(/position:\s*fixed/i)
  })

  it("does not attach document listeners when isOpen is false", () => {
    const onClose = vi.fn()
    render(
      <CanvasContextMenu
        isOpen={false}
        position={{ x: 0, y: 0 }}
        onClose={onClose}
        onAction={() => {}}
      />,
    )
    // No menu → Escape should NOT fire onClose.
    fireEvent.keyDown(document, { key: "Escape" })
    expect(onClose).not.toHaveBeenCalled()
  })
})
