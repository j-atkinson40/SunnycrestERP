/**
 * Builder Craft 1b — state-primitive tests (§18.1 + §18.3).
 *
 * Covers: EmptyState quiet variant (canon anatomy + one-action ceiling +
 * panel-default byte-compat), Skeleton craft variant (+ default unchanged),
 * ErrorState triad (+ details disclosure), Kbd treatment, ShortcutOverlay
 * (groups + kbd + Esc via dialog) and the `?` key hook's input suppression.
 */
import { describe, it, expect, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import { useState } from "react"
import { Workflow } from "lucide-react"

import { EmptyState } from "./empty-state"
import { Skeleton } from "./skeleton"
import { ErrorState } from "./error-state"
import { Kbd } from "./kbd"
import {
  ShortcutOverlay,
  useShortcutOverlayKey,
  type ShortcutGroup,
} from "./shortcut-overlay"

describe("EmptyState quiet variant (§18.1)", () => {
  it("renders the canon anatomy: 24px/1.5-stroke/content-subtle icon, no border box", () => {
    render(
      <EmptyState
        variant="quiet"
        icon={Workflow}
        title="Workflow templates"
        description="Pick a type on the left to start."
        data-testid="es"
      />,
    )
    const root = screen.getByTestId("es")
    expect(root.getAttribute("data-variant")).toBe("quiet")
    expect(root.className).not.toContain("border-dashed")
    const svg = root.querySelector("svg")!
    expect(svg.getAttribute("width")).toBe("24")
    expect(svg.getAttribute("stroke-width")).toBe("1.5")
    expect(svg.classList.contains("text-content-subtle")).toBe(true)
  })

  it("enforces the one-action ceiling: action wins, secondaryAction dropped", () => {
    render(
      <EmptyState
        variant="quiet"
        title="t"
        action={<button>Primary</button>}
        secondaryAction={<button>Secondary</button>}
      />,
    )
    expect(screen.getByRole("button", { name: "Primary" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Secondary" })).toBeNull()
  })

  it("default (panel) variant is unchanged — dashed border box intact", () => {
    render(<EmptyState title="t" data-testid="es" />)
    expect(screen.getByTestId("es").className).toContain("border-dashed")
  })
})

describe("Skeleton craft variant (§18.1)", () => {
  it("craft = surface-elevated + radius-sm + token-timed pulse", () => {
    const { container } = render(<Skeleton variant="craft" />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain("bg-surface-elevated")
    expect(el.className).toContain("rounded-sm")
    expect(el.className).toContain("animation-duration:var(--duration-considered)")
    expect(el.className).toContain("animation-timing-function:var(--ease-gentle)")
  })

  it("default is byte-identical to the Phase 7 look", () => {
    const { container } = render(<Skeleton />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toBe("rounded bg-surface-sunken motion-safe:animate-pulse")
  })
})

describe("ErrorState triad (§18.1)", () => {
  it("renders what happened / what survived / Retry; raw detail collapsed", () => {
    const onRetry = vi.fn()
    render(
      <ErrorState
        what="Couldn't load the workflows"
        survived="Your draft is intact."
        onRetry={onRetry}
        details="Request failed with status code 500"
      />,
    )
    expect(screen.getByTestId("error-state-what")).toHaveTextContent(
      "Couldn't load the workflows",
    )
    expect(screen.getByTestId("error-state-survived")).toHaveTextContent(
      "Your draft is intact.",
    )
    // The raw string is NOT visible until the disclosure opens.
    expect(screen.queryByTestId("error-state-details")).toBeNull()
    fireEvent.click(screen.getByTestId("error-state-details-toggle"))
    expect(screen.getByTestId("error-state-details")).toHaveTextContent(
      "Request failed with status code 500",
    )
    fireEvent.click(screen.getByTestId("error-state-retry"))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})

describe("Kbd (§18.3)", () => {
  it("renders the key-cap treatment", () => {
    render(<Kbd data-testid="k">⌘ ↵</Kbd>)
    const el = screen.getByTestId("k")
    expect(el.tagName.toLowerCase()).toBe("kbd")
    expect(el.className).toContain("bg-surface-sunken")
    expect(el.className).toContain("text-micro")
    expect(el.className).toContain("font-mono")
  })
})

const GROUPS: ShortcutGroup[] = [
  {
    title: "Canvas",
    shortcuts: [{ keys: "⇧ click", label: "Multi-select nodes" }],
  },
  {
    title: "Assistant",
    shortcuts: [{ keys: "⌘ ↵", label: "Generate workflow" }],
  },
]

describe("ShortcutOverlay (§18.3)", () => {
  it("renders groups by task with kbd caps when open", () => {
    render(
      <ShortcutOverlay
        groups={GROUPS}
        open
        onOpenChange={() => {}}
        surface="Workflow editor"
      />,
    )
    const overlay = screen.getByTestId("shortcut-overlay")
    expect(overlay).toHaveTextContent("Workflow editor shortcuts")
    expect(overlay).toHaveTextContent("Canvas")
    expect(overlay).toHaveTextContent("Multi-select nodes")
    expect(overlay).toHaveTextContent("Generate workflow")
    expect(overlay.querySelectorAll('[data-slot="kbd"]').length).toBeGreaterThanOrEqual(2)
  })

  it("? toggles via the hook; suppressed while an input is focused", () => {
    function Harness() {
      const [open, setOpen] = useState(false)
      useShortcutOverlayKey(setOpen)
      return (
        <div>
          <input data-testid="inp" />
          <ShortcutOverlay groups={GROUPS} open={open} onOpenChange={setOpen} />
        </div>
      )
    }
    render(<Harness />)
    expect(screen.queryByTestId("shortcut-overlay")).toBeNull()
    // ? with an input focused → suppressed.
    const inp = screen.getByTestId("inp")
    inp.focus()
    fireEvent.keyDown(inp, { key: "?" })
    expect(screen.queryByTestId("shortcut-overlay")).toBeNull()
    // ? on the body → opens.
    inp.blur()
    fireEvent.keyDown(document.body, { key: "?" })
    expect(screen.getByTestId("shortcut-overlay")).toBeInTheDocument()
    // ? again → closes (toggle).
    fireEvent.keyDown(document.body, { key: "?" })
    expect(screen.queryByTestId("shortcut-overlay")).toBeNull()
  })
})
