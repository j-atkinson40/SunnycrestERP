/**
 * The Sunnycrest Workshop — sections + cards pins.
 *
 *  * SECTION DERIVATION — types-with-tasks materialize; empty types are
 *    simply absent (derived, never configured); untyped tasks gather under
 *    General, last; typed sections alphabetical.
 *  * COLLAPSE PERSISTENCE — localStorage-class, default expanded.
 *  * THE CARD — the prose frequency + the T-0 authority truth (the
 *    runtime-managed badge carries onto the card), the "yours" pill, the
 *    live/dry-run chip, honest ponderability (a bare task gets no button
 *    role — no dead gesture).
 */
import { beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"

import { TaskCard } from "./TaskCard"
import { TaskSections, deriveSections } from "./TaskSections"
import type { MapTask } from "@/services/moc-map-service"

function task(over: Partial<MapTask>): MapTask {
  return {
    id: over.id ?? Math.random().toString(36).slice(2),
    name: "A Task",
    display_order: 0,
    scope: "vertical_default",
    triggers: [],
    ...over,
  } as MapTask
}

beforeEach(() => localStorage.clear())

describe("deriveSections", () => {
  it("materializes types-with-tasks, alphabetical, untyped last as General", () => {
    const sections = deriveSections([
      task({ task_type: "Operations" }),
      task({ task_type: "Accounting" }),
      task({ task_type: "Accounting" }),
      task({ task_type: null }),
    ])
    expect(sections.map((s) => s.type)).toEqual([
      "Accounting", "Operations", "General",
    ])
    expect(sections[0].tasks).toHaveLength(2)
  })

  it("hides empty types by construction — no tasks, no section", () => {
    expect(deriveSections([])).toEqual([])
  })
})

describe("TaskSections", () => {
  const tasks = [
    task({ id: "t1", name: "Close the books", task_type: "Accounting" }),
    task({ id: "t2", name: "Pour schedule", task_type: null }),
  ]

  it("renders derived sections with counts; collapse persists", () => {
    const { unmount } = render(
      <TaskSections tasks={tasks} onPonder={() => {}} onOpenOffer={() => {}}
        canAdd={false} onAdd={() => {}} />,
    )
    expect(screen.getByTestId("map-section-Accounting")).toBeTruthy()
    expect(screen.getByTestId("map-section-General")).toBeTruthy()
    // default expanded
    expect(screen.getByTestId("map-section-grid-Accounting")).toBeTruthy()

    fireEvent.click(screen.getByTestId("map-section-toggle-Accounting"))
    expect(screen.queryByTestId("map-section-grid-Accounting")).toBeNull()

    // persisted across a remount (localStorage-class)
    unmount()
    render(
      <TaskSections tasks={tasks} onPonder={() => {}} onOpenOffer={() => {}}
        canAdd={false} onAdd={() => {}} />,
    )
    expect(screen.queryByTestId("map-section-grid-Accounting")).toBeNull()
    expect(screen.getByTestId("map-section-grid-General")).toBeTruthy()
  })

  it("admin add is per-section (pre-filled) + hidden for viewers", () => {
    const onAdd = vi.fn()
    render(
      <TaskSections tasks={tasks} onPonder={() => {}} onOpenOffer={() => {}}
        canAdd onAdd={onAdd} />,
    )
    fireEvent.click(screen.getByTestId("map-section-add-Accounting"))
    expect(onAdd).toHaveBeenCalledWith("Accounting")
    fireEvent.click(screen.getByTestId("map-section-add-General"))
    expect(onAdd).toHaveBeenCalledWith(null)
  })
})

describe("TaskCard", () => {
  it("carries the prose frequency, the yours pill, and the live chip", () => {
    render(
      <TaskCard
        task={task({
          id: "c1", name: "Cash Receipts", scope: "tenant_override",
          derived_frequency: "Daily · 11:30 PM",
          workflow: { exists: true, available: true, label: "Cash Receipts" },
          triggers: [{ id: "x", kind: "schedule", config: {}, display_order: 0,
                       is_live: true, is_active: true } as never],
        })}
        onPonder={() => {}} onOpenOffer={() => {}}
      />,
    )
    expect(screen.getByTestId("map-card-when-c1").textContent).toContain("Daily · 11:30 PM")
    expect(screen.getByTestId("map-card-yours-c1")).toBeTruthy()
    expect(screen.getByTestId("map-card-live-c1")).toBeTruthy()
  })

  it("the T-0 authority truth carries — runtime prose + the managed badge", () => {
    render(
      <TaskCard
        task={task({
          id: "c2", name: "Safety Program",
          schedule_authority: "runtime_scheduler",
          runtime_schedule_summary: "The 1st of each month at 6:00 AM (tenant-local)",
          derived_frequency: null,
          workflow: { exists: true, available: true, label: "Safety" },
        })}
        onPonder={() => {}} onOpenOffer={() => {}}
      />,
    )
    expect(screen.getByTestId("map-card-when-c2").textContent).toContain(
      "The 1st of each month at 6:00 AM",
    )
    expect(screen.getByTestId("map-card-managed-c2")).toBeTruthy()
  })

  it("a bare task is honestly un-ponderable — no button role, no dead click", () => {
    const onPonder = vi.fn()
    render(
      <TaskCard
        task={task({ id: "c3", name: "Bare", workflow: null })}
        onPonder={onPonder} onOpenOffer={() => {}}
      />,
    )
    const card = screen.getByTestId("map-card-c3")
    expect(card.getAttribute("role")).toBeNull()
    fireEvent.click(card)
    expect(onPonder).not.toHaveBeenCalled()
  })

  it("a ponderable card opens the ponder on click (the mouse path)", () => {
    const onPonder = vi.fn()
    render(
      <TaskCard
        task={task({
          id: "c4", name: "Statement Run",
          workflow: { exists: true, available: true, label: "SR" },
        })}
        onPonder={onPonder} onOpenOffer={() => {}}
      />,
    )
    fireEvent.click(screen.getByTestId("map-card-c4"))
    expect(onPonder).toHaveBeenCalledTimes(1)
  })
})
