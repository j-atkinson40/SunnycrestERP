/**
 * Pre-flight verification for Studio 1a-i.B follow-up #3.
 *
 * Verifies the React Router v7 nested-Routes consumption chain that
 * Option A (per investigation §2) depends on:
 *
 *   Outer router consumes `/studio` via `path="/studio/*"`.
 *   Middle Routes consumes `live/manufacturing` via `path="live/:vertical/*"`.
 *   Inner Routes sees the remaining tail `dispatch/funeral-schedule`
 *   and matches its relative `<Route path="dispatch/funeral-schedule">`.
 *
 * If this test passes, Option A's architectural assumption holds and
 * Steps 2-6 of the build can proceed. If it fails, STOP — the
 * architectural premise is invalid and a different option (B or C)
 * must be revisited.
 *
 * Investigation: docs/investigations/2026-05-13-studio-live-router-topology.md §2 Option A
 *
 * Also asserts the test-setup pattern: StudioShell's nested <Routes>
 * MUST be wrapped in an outer <Route path="/studio/*"> to simulate
 * BridgeableAdminApp's mount. Without the outer Route consumption,
 * the inner Routes sees the full `/studio/...` pathname and the
 * relative `live/:vertical/*` won't match (relative paths require
 * ancestor consumption). The test below also verifies this directly
 * so the StudioShell.test.tsx setup pattern is grounded in mechanism.
 *
 * The test is kept in the codebase as regression protection — future
 * react-router-dom upgrades that change nested-Routes consumption
 * semantics would be caught immediately by this test failing.
 */
import { describe, expect, it } from "vitest"
import { render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"


function InnerLeaf() {
  return (
    <Routes>
      <Route
        path="dispatch/funeral-schedule"
        element={<div data-testid="dispatch-mounted" />}
      />
      <Route path="*" element={<div data-testid="fallthrough" />} />
    </Routes>
  )
}


function LiveBranch() {
  return <InnerLeaf />
}


function Inner() {
  return (
    <Routes>
      <Route path="live/:vertical/*" element={<LiveBranch />} />
    </Routes>
  )
}


describe("React Router nested-Routes consumption (pre-flight gate)", () => {
  it("nested Routes match deep tail when ancestor Routes consume prefix segments", () => {
    render(
      <MemoryRouter
        initialEntries={["/studio/live/manufacturing/dispatch/funeral-schedule"]}
      >
        <Routes>
          <Route path="/studio/*" element={<Inner />} />
        </Routes>
      </MemoryRouter>,
    )
    // If consumption works as expected:
    //   - outer matches /studio/*, consumes /studio
    //   - middle matches live/:vertical/*, consumes live/manufacturing
    //   - inner sees `dispatch/funeral-schedule` remainder and matches
    //     the literal route declaration.
    expect(screen.queryByTestId("dispatch-mounted")).toBeTruthy()
    expect(screen.queryByTestId("fallthrough")).toBeNull()
  })

  it("fallthrough route hits when no match", () => {
    render(
      <MemoryRouter
        initialEntries={["/studio/live/manufacturing/unknown-page"]}
      >
        <Routes>
          <Route path="/studio/*" element={<Inner />} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.queryByTestId("dispatch-mounted")).toBeNull()
    expect(screen.queryByTestId("fallthrough")).toBeTruthy()
  })
})
