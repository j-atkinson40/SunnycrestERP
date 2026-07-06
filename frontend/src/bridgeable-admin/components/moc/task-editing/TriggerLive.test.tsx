/**
 * T-2.1c — the Live toggle + the evidence-backed go-live confirm.
 *
 * Coverage per the dispatch:
 * - the badge reflects is_live (Live vs Dry-run visibly distinct);
 * - the toggle calls patchTrigger; going-LIVE opens the confirm, going BACK to
 *   dry-run does NOT (the safe direction is friction-free);
 * - the confirm shows the LATEST dry-run preview effect (the engine's own
 *   "would do X" records); the no-preview fallback shows when none exists
 *   (never a fabricated effect);
 * - a MIRROR-task trigger's toggle is DISABLED with the §6 reason — not a
 *   live-looking control that silently stays dry; its badge NEVER shows Live
 *   even if is_live is set (the effective state is dry-run).
 */
import { describe, expect, it, vi, beforeEach } from "vitest"
import { render, screen, waitFor, fireEvent } from "@testing-library/react"

import { TriggerChips, MIRROR_LIVE_REASON } from "./TriggerChips"
import { TaskEditorPanel } from "./TaskEditorPanel"
import type { MoCTask, MoCTrigger } from "@/bridgeable-admin/services/moc-service"
import * as mocService from "@/bridgeable-admin/services/moc-service"

vi.mock("@/bridgeable-admin/services/moc-service", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/bridgeable-admin/services/moc-service")>()
  return {
    ...actual,
    listWorkflowTemplateOptions: vi.fn(),
    listFocusTemplateOptions: vi.fn(),
    listTriggerEvents: vi.fn(),
    patchTrigger: vi.fn(),
    getLatestScheduleRun: vi.fn(),
  }
})

const SCHEDULE_DRY: MoCTrigger = {
  id: "tr-dry", kind: "schedule", config: { spec_kind: "cron", cron: "*/15 * * * *" },
  display_order: 0, is_live: false, summary: "Every 15 minutes",
}
const SCHEDULE_LIVE: MoCTrigger = { ...SCHEDULE_DRY, id: "tr-live", is_live: true }

function task(over: Partial<MoCTask> = {}): MoCTask {
  return {
    id: "t-1", name: "Witness Task", frequency: null, task_type: null,
    description: null, display_order: 0,
    workflow: {
      exists: true, available: true, label: "Witness WF", routing: {},
      artifact_id: "wf-1", is_mirror: false,
    },
    focuses: [], triggers: [SCHEDULE_DRY],
    ...over,
  }
}

function renderPanel(t: MoCTask) {
  return render(
    <TaskEditorPanel
      isOpen onClose={() => {}} vertical="manufacturing"
      task={t} onSaved={() => {}} onError={() => {}}
    />,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(mocService.listWorkflowTemplateOptions).mockResolvedValue([])
  vi.mocked(mocService.listFocusTemplateOptions).mockResolvedValue([])
  vi.mocked(mocService.listTriggerEvents).mockResolvedValue([])
  vi.mocked(mocService.getLatestScheduleRun).mockResolvedValue(null)
})

describe("Live badge (TriggerChips)", () => {
  it("shows a visibly distinct Live vs Dry-run badge from is_live", () => {
    render(<TriggerChips triggers={[SCHEDULE_DRY, SCHEDULE_LIVE]} />)
    const dry = screen.getByTestId("trigger-live-badge-tr-dry")
    const live = screen.getByTestId("trigger-live-badge-tr-live")
    expect(dry.getAttribute("data-live")).toBe("false")
    expect(dry.textContent).toContain("Dry-run")
    expect(live.getAttribute("data-live")).toBe("true")
    expect(live.textContent).toContain("Live")
    // Visibly distinct: the Live badge carries the solid accent fill.
    expect(live.innerHTML).toContain("bg-accent")
    expect(dry.innerHTML).not.toContain("bg-accent ")
  })

  it("EVENT chips carry the live badge too (T-2.2c); manual chips do not", () => {
    render(<TriggerChips triggers={[
      { id: "ev", kind: "event", config: {}, display_order: 0, summary: "order.created", is_live: false },
      { id: "man", kind: "manual", config: {}, display_order: 1, summary: "Manual" },
    ]} />)
    const evBadge = screen.getByTestId("trigger-live-badge-ev")
    expect(evBadge.getAttribute("data-live")).toBe("false")
    expect(evBadge.textContent).toContain("Dry-run")
    expect(screen.queryByTestId("trigger-live-badge-man")).toBeNull()
  })

  it("a MIRROR task's EVENT-trigger toggle is disabled with the §6 reason", () => {
    const onToggle = vi.fn()
    render(<TriggerChips
      triggers={[{ id: "ev", kind: "event", config: {}, display_order: 0, summary: "order.created", is_live: false }]}
      liveCapable={false} onToggleLive={onToggle}
    />)
    const toggle = screen.getByTestId("trigger-live-toggle-ev")
    expect(toggle.hasAttribute("disabled")).toBe(true)
    expect(toggle.getAttribute("title")).toBe(MIRROR_LIVE_REASON)
    fireEvent.click(toggle)
    expect(onToggle).not.toHaveBeenCalled()
  })

  it("a MIRROR task's badge NEVER shows Live — even if is_live is set (§6 effective state)", () => {
    render(<TriggerChips triggers={[SCHEDULE_LIVE]} liveCapable={false} />)
    const badge = screen.getByTestId("trigger-live-badge-tr-live")
    expect(badge.getAttribute("data-live")).toBe("false")
    expect(badge.textContent).toContain("Dry-run")
    expect(badge.getAttribute("title")).toBe(MIRROR_LIVE_REASON)
  })

  it("a MIRROR task's toggle is DISABLED with the §6 reason (not a lying control)", () => {
    const onToggle = vi.fn()
    render(<TriggerChips triggers={[SCHEDULE_DRY]} liveCapable={false} onToggleLive={onToggle} />)
    const toggle = screen.getByTestId("trigger-live-toggle-tr-dry")
    expect(toggle.hasAttribute("disabled")).toBe(true)
    expect(toggle.getAttribute("title")).toBe(MIRROR_LIVE_REASON)
    fireEvent.click(toggle)
    expect(onToggle).not.toHaveBeenCalled()
  })
})

describe("Go-live flow (TaskEditorPanel)", () => {
  it("toggling TO live opens the confirm — and does NOT patch until confirmed", async () => {
    renderPanel(task())
    fireEvent.click(await screen.findByTestId("trigger-live-toggle-tr-dry"))
    expect(await screen.findByTestId("go-live-confirm")).toBeTruthy()
    expect(mocService.patchTrigger).not.toHaveBeenCalled()
  })

  it("the confirm shows the LATEST dry-run preview effect (the engine's would-do)", async () => {
    vi.mocked(mocService.getLatestScheduleRun).mockResolvedValue({
      run_id: "r1", task_name: "Witness Task", moc_task_trigger_id: "tr-dry",
      company_id: "c1", status: "completed", is_dry_run: true,
      intended_fire: "2026-07-01T22:00:00+00:00", started_at: "2026-07-01T22:05:00+00:00",
      would_do: ["would execute action:record_marker"],
    })
    renderPanel(task())
    fireEvent.click(await screen.findByTestId("trigger-live-toggle-tr-dry"))
    const preview = await screen.findByTestId("go-live-preview")
    expect(preview.textContent).toContain("action:record_marker")
    expect(mocService.getLatestScheduleRun).toHaveBeenCalledWith("tr-dry")
    expect(screen.queryByTestId("go-live-no-preview")).toBeNull()
  })

  it("a NEVER-previewed trigger's confirm shows the no-preview fallback (no fabricated effect)", async () => {
    vi.mocked(mocService.getLatestScheduleRun).mockResolvedValue(null)
    renderPanel(task())
    fireEvent.click(await screen.findByTestId("trigger-live-toggle-tr-dry"))
    const fallback = await screen.findByTestId("go-live-no-preview")
    expect(fallback.textContent).toContain("hasn’t previewed yet")
    expect(screen.queryByTestId("go-live-preview")).toBeNull()
  })

  it("confirming PATCHes is_live=true; cancel does not", async () => {
    vi.mocked(mocService.patchTrigger).mockResolvedValue({ ...SCHEDULE_DRY, is_live: true })
    renderPanel(task())
    fireEvent.click(await screen.findByTestId("trigger-live-toggle-tr-dry"))
    fireEvent.click(await screen.findByTestId("go-live-confirm-button"))
    await waitFor(() =>
      expect(mocService.patchTrigger).toHaveBeenCalledWith("tr-dry", { is_live: true }),
    )
    // and the badge flips to Live from the response
    await waitFor(() =>
      expect(screen.getByTestId("trigger-live-toggle-tr-dry").getAttribute("data-live")).toBe("true"),
    )
  })

  it("cancel closes the confirm without patching", async () => {
    renderPanel(task())
    fireEvent.click(await screen.findByTestId("trigger-live-toggle-tr-dry"))
    fireEvent.click(await screen.findByTestId("go-live-cancel"))
    await waitFor(() => expect(screen.queryByTestId("go-live-confirm")).toBeNull())
    expect(mocService.patchTrigger).not.toHaveBeenCalled()
  })

  it("toggling BACK to dry-run patches IMMEDIATELY — no confirm (the safe direction)", async () => {
    vi.mocked(mocService.patchTrigger).mockResolvedValue({ ...SCHEDULE_LIVE, is_live: false })
    renderPanel(task({ triggers: [SCHEDULE_LIVE] }))
    fireEvent.click(await screen.findByTestId("trigger-live-toggle-tr-live"))
    await waitFor(() =>
      expect(mocService.patchTrigger).toHaveBeenCalledWith("tr-live", { is_live: false }),
    )
    expect(screen.queryByTestId("go-live-confirm")).toBeNull()
  })

  it("an EVENT trigger's confirm words the consequence by event, with provenance (T-2.2c)", async () => {
    vi.mocked(mocService.getLatestScheduleRun).mockResolvedValue({
      run_id: "r2", task_name: "Witness Task", moc_task_trigger_id: "tr-ev",
      company_id: "c1", status: "completed", is_dry_run: true,
      intended_fire: null, started_at: "2026-07-06T12:00:00+00:00",
      would_do: ["would execute action:record_marker"],
    })
    const EVENT_TRIG: MoCTrigger = {
      id: "tr-ev", kind: "event", config: { event: "order.created", conditions: [] },
      display_order: 0, is_live: false, summary: "order.created: funeral",
    }
    renderPanel(task({ triggers: [EVENT_TRIG] }))
    fireEvent.click(await screen.findByTestId("trigger-live-toggle-tr-ev"))
    const consequence = await screen.findByTestId("go-live-consequence")
    expect(consequence.textContent).toContain("whenever")
    expect(consequence.textContent).toContain("order.created: funeral")
    expect(consequence.textContent).not.toContain("on schedule")
    // the evidence still comes from the unified fires log (trigger-scoped)
    const preview = await screen.findByTestId("go-live-preview")
    expect(preview.textContent).toContain("action:record_marker")
  })

  it("a never-matched EVENT trigger's confirm shows the event-worded fallback", async () => {
    vi.mocked(mocService.getLatestScheduleRun).mockResolvedValue(null)
    const EVENT_TRIG: MoCTrigger = {
      id: "tr-ev2", kind: "event", config: { event: "order.created", conditions: [] },
      display_order: 0, is_live: false, summary: "order.created",
    }
    renderPanel(task({ triggers: [EVENT_TRIG] }))
    fireEvent.click(await screen.findByTestId("trigger-live-toggle-tr-ev2"))
    const fallback = await screen.findByTestId("go-live-no-preview")
    expect(fallback.textContent).toContain("hasn’t matched-and-previewed yet")
    expect(fallback.textContent).toContain("when the event occurs")
  })

  it("a mirror task's panel toggle is disabled (wired from workflow.is_mirror)", async () => {
    renderPanel(task({
      workflow: {
        exists: true, available: true, label: "Mirror WF", routing: {},
        artifact_id: "wf-m", is_mirror: true,
      },
    }))
    const toggle = await screen.findByTestId("trigger-live-toggle-tr-dry")
    expect(toggle.hasAttribute("disabled")).toBe(true)
    fireEvent.click(toggle)
    expect(screen.queryByTestId("go-live-confirm")).toBeNull()
  })
})
