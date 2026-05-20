/**
 * computeDragMoveCommit unit tests (sub-arc FF-3).
 *
 * Pure-function coverage for the drag-end commit translation. Per
 * Q-40, the integration test side of FF-3 exercises @dnd-kit's
 * KeyboardSensor path; this file owns the math.
 */
import { describe, expect, it } from "vitest"

import { computeDragMoveCommit } from "./computeDragMoveCommit"

describe("computeDragMoveCommit", () => {
  it("delta within bounds → position = current + delta", () => {
    expect(
      computeDragMoveCommit({
        currentX: 100,
        currentY: 100,
        dx: 50,
        dy: -30,
        canvasWidth: 1200,
        canvasHeight: 800,
        widgetWidth: 240,
        widgetHeight: 120,
      }),
    ).toEqual({ x: 150, y: 70 })
  })

  it("zero delta → current unchanged", () => {
    expect(
      computeDragMoveCommit({
        currentX: 200,
        currentY: 300,
        dx: 0,
        dy: 0,
        canvasWidth: 1200,
        canvasHeight: 800,
        widgetWidth: 240,
        widgetHeight: 120,
      }),
    ).toEqual({ x: 200, y: 300 })
  })

  it("top-left overshoot → clamps to (0, 0) per Q-14", () => {
    expect(
      computeDragMoveCommit({
        currentX: 20,
        currentY: 10,
        dx: -100,
        dy: -200,
        canvasWidth: 1200,
        canvasHeight: 800,
        widgetWidth: 240,
        widgetHeight: 120,
      }),
    ).toEqual({ x: 0, y: 0 })
  })

  it("bottom-right overshoot → clamps to (canvas - widget) per Q-14", () => {
    expect(
      computeDragMoveCommit({
        currentX: 900,
        currentY: 600,
        dx: 500,
        dy: 500,
        canvasWidth: 1200,
        canvasHeight: 800,
        widgetWidth: 240,
        widgetHeight: 120,
      }),
    ).toEqual({ x: 960, y: 680 })
  })

  it("top-edge nudge holds at 0 (cannot drag above canvas)", () => {
    expect(
      computeDragMoveCommit({
        currentX: 0,
        currentY: 0,
        dx: -10,
        dy: -10,
        canvasWidth: 1200,
        canvasHeight: 800,
        widgetWidth: 240,
        widgetHeight: 120,
      }),
    ).toEqual({ x: 0, y: 0 })
  })

  it("bottom-edge nudge holds at canvas - widget", () => {
    expect(
      computeDragMoveCommit({
        currentX: 960,
        currentY: 680,
        dx: 10,
        dy: 10,
        canvasWidth: 1200,
        canvasHeight: 800,
        widgetWidth: 240,
        widgetHeight: 120,
      }),
    ).toEqual({ x: 960, y: 680 })
  })

  it("widget larger than canvas (defensive): collapses to 0/0", () => {
    expect(
      computeDragMoveCommit({
        currentX: 100,
        currentY: 100,
        dx: 0,
        dy: 0,
        canvasWidth: 200,
        canvasHeight: 100,
        widgetWidth: 320,
        widgetHeight: 180,
      }),
    ).toEqual({ x: 0, y: 0 })
  })

  it("zero canvas dimensions (defensive): collapses to 0/0", () => {
    expect(
      computeDragMoveCommit({
        currentX: 50,
        currentY: 50,
        dx: 10,
        dy: 10,
        canvasWidth: 0,
        canvasHeight: 0,
        widgetWidth: 240,
        widgetHeight: 120,
      }),
    ).toEqual({ x: 0, y: 0 })
  })

  it("negative delta with mid-canvas position → moves toward origin", () => {
    expect(
      computeDragMoveCommit({
        currentX: 500,
        currentY: 400,
        dx: -50,
        dy: -25,
        canvasWidth: 1200,
        canvasHeight: 800,
        widgetWidth: 240,
        widgetHeight: 120,
      }),
    ).toEqual({ x: 450, y: 375 })
  })
})
