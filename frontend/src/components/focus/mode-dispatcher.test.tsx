/**
 * ModeDispatcher — vitest unit tests.
 *
 * Renders the right core for each registered mode; renders the
 * unknown-focus error state for ids not in the registry.
 */

import { render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import {
  _resetRegistryForTests,
  registerFocus,
} from "@/contexts/focus-registry"

import { ModeDispatcher } from "./mode-dispatcher"


// The registry seeds test-* stubs at module load. Tests that register
// extra entries clean up after themselves so cross-test contamination
// can't leak. Re-seeding the base set happens via re-importing the
// registry module is heavyweight, so we explicitly register only what
// we add and unregister on teardown via _resetRegistryForTests in
// the coreComponent suite.


describe("ModeDispatcher — routes to the correct core by mode", () => {
  const cases: Array<{ id: string; expectedTitle: string; expectedEyebrow: string }> = [
    { id: "test-kanban", expectedTitle: "Kanban stub", expectedEyebrow: "kanban" },
    {
      id: "test-single-record",
      expectedTitle: "Single-record stub",
      expectedEyebrow: "singleRecord",
    },
    {
      id: "test-edit-canvas",
      expectedTitle: "Edit-canvas stub",
      expectedEyebrow: "editCanvas",
    },
    {
      id: "test-triage-queue",
      expectedTitle: "Triage-queue stub",
      expectedEyebrow: "triageQueue",
    },
    { id: "test-matrix", expectedTitle: "Matrix stub", expectedEyebrow: "matrix" },
  ]

  for (const { id, expectedTitle, expectedEyebrow } of cases) {
    it(`renders the core for id=${id}`, () => {
      render(<ModeDispatcher focusId={id} />)
      expect(screen.getByText(expectedTitle)).toBeInTheDocument()
      // Eyebrow includes the mode label — use getAllByText in case
      // the mode name appears elsewhere on the page.
      expect(
        screen.getByText(new RegExp(`Core mode.*${expectedEyebrow}`, "i")),
      ).toBeInTheDocument()
    })
  }
})


describe("ModeDispatcher — unknown id", () => {
  it("renders the unknown-focus error state (not a crash)", () => {
    render(<ModeDispatcher focusId="does-not-exist" />)
    expect(screen.getByText(/No Focus registered at this id/i)).toBeInTheDocument()
    expect(screen.getByText(/does-not-exist/)).toBeInTheDocument()
    expect(screen.getByText(/Unknown focus/i)).toBeInTheDocument()
  })

  it("error state includes the dismiss hint (Esc)", () => {
    render(<ModeDispatcher focusId="still-missing" />)
    expect(screen.getByText(/click outside to dismiss/i)).toBeInTheDocument()
  })
})


describe("ModeDispatcher — coreComponent override (Phase B Session 4 Phase 4.2)", () => {
  // Local-scope tests register extra ids and clean those up at the
  // end; we DON'T reset the whole registry because the base test-*
  // stubs were seeded at module load and are load-bearing for the
  // other describe blocks.
  const addedIds = new Set<string>()

  function registerTemporary(config: Parameters<typeof registerFocus>[0]) {
    addedIds.add(config.id)
    registerFocus(config)
  }

  afterEach(() => {
    // Restore the registry state by wiping and re-registering just
    // the base test-* stubs. Because the ids from other suites in
    // the file use test-<mode> that focus-registry.ts already seeds
    // at module load, the clean approach is: wipe, then re-seed from
    // the known five stubs identity.
    _resetRegistryForTests()
    // Re-register the five base stubs inline. Keep in sync with
    // focus-registry.ts's module-load seeds.
    const BASE_STUBS: Array<{
      id: string
      mode: Parameters<typeof registerFocus>[0]["mode"]
      displayName: string
    }> = [
      { id: "test-kanban", mode: "kanban", displayName: "Kanban stub" },
      {
        id: "test-single-record",
        mode: "singleRecord",
        displayName: "Single-record stub",
      },
      {
        id: "test-edit-canvas",
        mode: "editCanvas",
        displayName: "Edit-canvas stub",
      },
      {
        id: "test-triage-queue",
        mode: "triageQueue",
        displayName: "Triage-queue stub",
      },
      { id: "test-matrix", mode: "matrix", displayName: "Matrix stub" },
    ]
    for (const stub of BASE_STUBS) {
      registerFocus(stub)
    }
    addedIds.clear()
  })

  it("dispatches to coreComponent when provided, bypassing MODE_RENDERERS", () => {
    function SpecializedCore() {
      return <div data-slot="specialized-core">Specialized core content</div>
    }
    registerTemporary({
      id: "custom-kanban-workflow",
      mode: "kanban",
      displayName: "Custom Kanban",
      coreComponent: SpecializedCore,
    })
    render(<ModeDispatcher focusId="custom-kanban-workflow" />)
    // Specialized content appears.
    expect(screen.getByText("Specialized core content")).toBeInTheDocument()
    // Stub mode label ("Core mode · kanban") does NOT appear because
    // the stub renderer was bypassed.
    expect(screen.queryByText(/Core mode · kanban/i)).toBeNull()
  })

  it("falls back to MODE_RENDERERS when coreComponent is absent", () => {
    registerTemporary({
      id: "plain-kanban-workflow",
      mode: "kanban",
      displayName: "Plain Kanban",
    })
    render(<ModeDispatcher focusId="plain-kanban-workflow" />)
    // Uses the stub KanbanCore — eyebrow appears.
    expect(screen.getByText(/Core mode · kanban/i)).toBeInTheDocument()
    expect(screen.getByText("Plain Kanban")).toBeInTheDocument()
  })
})


// ── Read-only, 2026-09-10 ────────────────────────────────────────────
//
// ⚠️ THE SEAM. The hook can be correct and the notice can render in
// isolation while the dispatcher never puts them together — which is the
// substrate-built-and-unwired failure, and it shows as a Focus that is silently
// inert. Every assertion here is paired with a control at the same seam.

vi.mock("@/contexts/auth-context", () => ({
  useAuthOptional: () => mockAuth,
}))
const mockAuth = { hasPermission: (_k: string) => false, isAdmin: false }

describe("ModeDispatcher — read-only", () => {
  afterEach(() => {
    _resetRegistryForTests()
    mockAuth.hasPermission = () => false
    mockAuth.isAdmin = false
  })

  function registerGated() {
    registerFocus({
      id: "ro-focus",
      mode: "kanban",
      displayName: "Gated",
      editPermission: "delivery.edit",
    })
  }

  it("renders the read-only notice when the permission is absent", () => {
    registerGated()
    mockAuth.hasPermission = () => false
    render(<ModeDispatcher focusId="ro-focus" />)
    expect(screen.getByTestId("focus-read-only-notice")).toBeTruthy()
  })

  it("CONTROL: no notice when the permission is held", () => {
    // The pair. Without it, "the notice rendered" is satisfied by a dispatcher
    // that always renders it.
    registerGated()
    mockAuth.hasPermission = (k: string) => k === "delivery.edit"
    render(<ModeDispatcher focusId="ro-focus" />)
    expect(screen.queryByTestId("focus-read-only-notice")).toBeNull()
  })

  it("CONTROL: no notice for a Focus that declares no editPermission", () => {
    registerFocus({ id: "ungated", mode: "kanban", displayName: "Ungated" })
    mockAuth.hasPermission = () => false
    render(<ModeDispatcher focusId="ungated" />)
    expect(screen.queryByTestId("focus-read-only-notice")).toBeNull()
  })

  it("the core still renders — read-only never blanks the surface", () => {
    // ⚠️ "Cannot act" is satisfied perfectly by rendering nothing. It is the
    // wrong answer: the user is meant to SEE this and not change it.
    registerGated()
    mockAuth.hasPermission = () => false
    render(<ModeDispatcher focusId="ro-focus" />)
    expect(screen.getByText("Gated")).toBeTruthy()
  })
})
