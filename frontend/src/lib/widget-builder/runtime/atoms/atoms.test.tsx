/**
 * Atom renderer tests — WB-2 contract + WB-3 production UI.
 *
 * Phase 1 contract preserved across WB-2 → WB-3:
 *   - data-atom-type + data-atom-id emission
 *   - semantic HTML element type (span / button / hr / div / img)
 *   - graceful handling of missing config
 *
 * WB-3 production UI additions:
 *   - Typography variant + color + alignment mapping
 *   - Real lucide icon rendering (resolved via ICON_MAP)
 *   - Status badge variant-aware chrome
 *   - Real button variant + size styling
 *   - Image fallback to placeholder when no src
 *   - Repeater iteration semantics (children-per-row)
 */

import { describe, it, expect } from "vitest"
import { render } from "@testing-library/react"

import type {
  AtomNode,
  ButtonConfig,
  ConditionalContainerConfig,
  DividerConfig,
  IconConfig,
  ImageConfig,
  RepeaterAtomConfig,
  StatusBadgeConfig,
  TextLabelConfig,
  ValueDisplayConfig,
} from "../../types/composition-blob"
import {
  ButtonRenderer,
  ConditionalContainerRenderer,
  DividerRenderer,
  IconRenderer,
  ImageRenderer,
  RepeaterAtomRenderer,
  StatusBadgeRenderer,
  TextLabelRenderer,
  ValueDisplayRenderer,
} from "./index"


function mkAtom<T extends AtomNode["atom_type"]>(
  atom_type: T,
  atom_id: string,
  config: Record<string, unknown> = {},
): AtomNode {
  return {
    atom_id,
    atom_type,
    config,
  }
}


describe("TextLabelRenderer (WB-3)", () => {
  it("renders data attributes + fallback text", () => {
    const atom = mkAtom("text_label", "a1")
    const { container } = render(
      <TextLabelRenderer
        atom={atom}
        config={{} as TextLabelConfig}
        resolvedBindings={{}}
      />,
    )
    const el = container.querySelector("[data-atom-id='a1']")
    expect(el).not.toBeNull()
    expect(el?.tagName).toBe("SPAN")
    expect(el?.getAttribute("data-atom-type")).toBe("text_label")
    expect(el?.textContent).toBe("Text label")
  })

  it("prefers resolved binding over static config", () => {
    const atom = mkAtom("text_label", "a1")
    const { container } = render(
      <TextLabelRenderer
        atom={atom}
        config={{} as TextLabelConfig}
        resolvedBindings={{ text: "Hello world" }}
      />,
    )
    expect(container.textContent).toBe("Hello world")
  })

  it("applies typography + color + alignment classes", () => {
    const atom = mkAtom("text_label", "a1", {
      variant: "heading-2",
      color: "accent",
      alignment: "center",
    })
    const { container } = render(
      <TextLabelRenderer
        atom={atom}
        config={atom.config as unknown as TextLabelConfig}
        resolvedBindings={{ text: "title" }}
      />,
    )
    const el = container.querySelector("[data-atom-id='a1']") as HTMLElement
    expect(el.className).toMatch(/text-h2/)
    expect(el.className).toMatch(/text-center/)
    expect(el.className).toMatch(/accent/)
  })

  it("clamps to max_lines via webkit line-clamp style", () => {
    const atom = mkAtom("text_label", "a1", { max_lines: 2 })
    const { container } = render(
      <TextLabelRenderer
        atom={atom}
        config={atom.config as unknown as TextLabelConfig}
        resolvedBindings={{ text: "long text" }}
      />,
    )
    const el = container.querySelector("[data-atom-id='a1']") as HTMLElement
    expect(el.style.webkitLineClamp).toBe("2")
  })
})


describe("ValueDisplayRenderer (WB-3)", () => {
  it("renders placeholder when no binding present", () => {
    const atom = mkAtom("value_display", "a2", {
      format: "currency",
      format_config: {},
    })
    const { container } = render(
      <ValueDisplayRenderer
        atom={atom}
        config={atom.config as unknown as ValueDisplayConfig}
        resolvedBindings={{}}
      />,
    )
    expect(container.textContent).toBe("[currency]")
  })

  it("formats currency with Intl", () => {
    const atom = mkAtom("value_display", "a2", {
      format: "currency",
      format_config: { currency_code: "USD" },
    })
    const { container } = render(
      <ValueDisplayRenderer
        atom={atom}
        config={atom.config as unknown as ValueDisplayConfig}
        resolvedBindings={{ value: 1234.5 }}
      />,
    )
    expect(container.textContent).toMatch(/\$1,234\.50/)
  })

  it("formats numbers with Intl", () => {
    const atom = mkAtom("value_display", "a2", {
      format: "number",
      format_config: {},
    })
    const { container } = render(
      <ValueDisplayRenderer
        atom={atom}
        config={atom.config as unknown as ValueDisplayConfig}
        resolvedBindings={{ value: 1234567 }}
      />,
    )
    expect(container.textContent).toMatch(/1,234,567/)
  })

  it("uses explicit placeholder when provided", () => {
    const atom = mkAtom("value_display", "a2", {
      format: "text",
      format_config: {},
      placeholder: "—",
    })
    const { container } = render(
      <ValueDisplayRenderer
        atom={atom}
        config={atom.config as unknown as ValueDisplayConfig}
        resolvedBindings={{}}
      />,
    )
    expect(container.textContent).toBe("—")
  })
})


describe("IconRenderer (WB-3)", () => {
  it("renders an SVG lucide icon with size attribute", () => {
    const atom = mkAtom("icon", "a3", {
      icon_name: "alert-circle",
      size_token: "md",
    })
    const { container } = render(
      <IconRenderer
        atom={atom}
        config={atom.config as unknown as IconConfig}
        resolvedBindings={{}}
      />,
    )
    const wrap = container.querySelector("[data-atom-id='a3']")
    expect(wrap).not.toBeNull()
    expect(wrap?.getAttribute("data-atom-type")).toBe("icon")
    const svg = wrap?.querySelector("svg")
    expect(svg).not.toBeNull()
    expect(svg?.getAttribute("width")).toBe("20")
    expect(svg?.getAttribute("data-icon-name")).toBe("alert-circle")
  })

  it("falls back to default Layers icon when icon_name unknown", () => {
    const atom = mkAtom("icon", "a3", { icon_name: "no-such-icon" })
    const { container } = render(
      <IconRenderer
        atom={atom}
        config={atom.config as unknown as IconConfig}
        resolvedBindings={{}}
      />,
    )
    expect(container.querySelector("svg")).not.toBeNull()
  })

  it("throws when config.icon_name is missing", () => {
    const atom = mkAtom("icon", "a3", {})
    expect(() =>
      render(
        <IconRenderer
          atom={atom}
          config={atom.config as unknown as IconConfig}
          resolvedBindings={{}}
        />,
      ),
    ).toThrow(/missing required config.icon_name/)
  })
})


describe("StatusBadgeRenderer (WB-3)", () => {
  it("renders badge with default neutral variant", () => {
    const atom = mkAtom("status_badge", "a4", {
      status_map: {},
      show_icon: false,
    })
    const { container } = render(
      <StatusBadgeRenderer
        atom={atom}
        config={atom.config as unknown as StatusBadgeConfig}
        resolvedBindings={{ label: "Open" }}
      />,
    )
    const el = container.querySelector("[data-atom-id='a4']")
    expect(el?.getAttribute("data-variant")).toBe("neutral")
    expect(el?.textContent).toBe("Open")
  })

  it("maps bound status via status_map to variant", () => {
    const atom = mkAtom("status_badge", "a4", {
      status_map: { active: "success", overdue: "danger" },
      show_icon: false,
    })
    const { container } = render(
      <StatusBadgeRenderer
        atom={atom}
        config={atom.config as unknown as StatusBadgeConfig}
        resolvedBindings={{ status: "active" }}
      />,
    )
    const el = container.querySelector("[data-atom-id='a4']")
    expect(el?.getAttribute("data-variant")).toBe("success")
    expect(el?.textContent).toBe("active")
  })
})


describe("DividerRenderer (WB-3)", () => {
  it("renders hr horizontal by default", () => {
    const atom = mkAtom("divider", "a5")
    const { container } = render(
      <DividerRenderer
        atom={atom}
        config={{} as DividerConfig}
        resolvedBindings={{}}
      />,
    )
    const hr = container.querySelector("hr")
    expect(hr).not.toBeNull()
    expect(hr?.getAttribute("data-atom-id")).toBe("a5")
    expect(hr?.getAttribute("data-orientation")).toBe("horizontal")
  })

  it("renders vertical divider as a div separator", () => {
    const atom = mkAtom("divider", "a5", { orientation: "vertical" })
    const { container } = render(
      <DividerRenderer
        atom={atom}
        config={atom.config as unknown as DividerConfig}
        resolvedBindings={{}}
      />,
    )
    const el = container.querySelector("[data-atom-id='a5']")
    expect(el?.tagName).toBe("DIV")
    expect(el?.getAttribute("role")).toBe("separator")
    expect(el?.getAttribute("aria-orientation")).toBe("vertical")
  })
})


describe("ButtonRenderer (WB-3)", () => {
  it("renders a button element with action-kind + variant attributes", () => {
    const atom = mkAtom("button", "a6", {
      action_kind: "navigate",
      action_config: { route: "/x" },
      variant: "primary",
      size: "md",
    })
    const { container } = render(
      <ButtonRenderer
        atom={atom}
        config={atom.config as unknown as ButtonConfig}
        resolvedBindings={{}}
      />,
    )
    const btn = container.querySelector("button")
    expect(btn).not.toBeNull()
    expect(btn?.getAttribute("type")).toBe("button")
    expect(btn?.getAttribute("data-atom-id")).toBe("a6")
    expect(btn?.getAttribute("data-action-kind")).toBe("navigate")
    expect(btn?.getAttribute("data-variant")).toBe("primary")
    expect(btn?.textContent).toBe("Button")
  })

  it("onClick is a no-op (does not throw)", () => {
    const atom = mkAtom("button", "a6", {
      action_kind: "open_focus",
      action_config: {},
    })
    const { container } = render(
      <ButtonRenderer
        atom={atom}
        config={atom.config as unknown as ButtonConfig}
        resolvedBindings={{}}
      />,
    )
    const btn = container.querySelector("button")!
    expect(() => btn.click()).not.toThrow()
  })

  it("uses static label from config", () => {
    const atom = mkAtom("button", "a6", {
      action_kind: "navigate",
      action_config: {},
      label: "Open case",
    })
    const { container } = render(
      <ButtonRenderer
        atom={atom}
        config={atom.config as unknown as ButtonConfig}
        resolvedBindings={{}}
      />,
    )
    expect(container.querySelector("button")?.textContent).toBe("Open case")
  })

  it("uses bound label over static config", () => {
    const atom = mkAtom("button", "a6", {
      action_kind: "navigate",
      action_config: {},
      label: "static",
    })
    const { container } = render(
      <ButtonRenderer
        atom={atom}
        config={atom.config as unknown as ButtonConfig}
        resolvedBindings={{ label: "bound" }}
      />,
    )
    expect(container.querySelector("button")?.textContent).toBe("bound")
  })

  it("renders a leading icon when icon_name supplied", () => {
    const atom = mkAtom("button", "a6", {
      action_kind: "navigate",
      action_config: {},
      icon_name: "plus",
      label: "Add",
    })
    const { container } = render(
      <ButtonRenderer
        atom={atom}
        config={atom.config as unknown as ButtonConfig}
        resolvedBindings={{}}
      />,
    )
    expect(container.querySelector("button svg")).not.toBeNull()
  })
})


describe("ImageRenderer (WB-3)", () => {
  it("renders placeholder div when no src", () => {
    const atom = mkAtom("image", "a7", {
      source_kind: "vault_asset",
      fit: "cover",
    })
    const { container } = render(
      <ImageRenderer
        atom={atom}
        config={atom.config as unknown as ImageConfig}
        resolvedBindings={{}}
      />,
    )
    const el = container.querySelector("[data-atom-id='a7']")
    expect(el?.tagName).toBe("DIV")
    expect(el?.getAttribute("data-source-kind")).toBe("vault_asset")
    expect(el?.getAttribute("role")).toBe("img")
    // Fallback icon visible.
    expect(el?.querySelector("svg")).not.toBeNull()
  })

  it("renders img element when src is provided via resolvedBindings", () => {
    const atom = mkAtom("image", "a7", {
      source_kind: "url",
      fit: "contain",
      alt: "team photo",
    })
    const { container } = render(
      <ImageRenderer
        atom={atom}
        config={atom.config as unknown as ImageConfig}
        resolvedBindings={{ src: "https://example.com/foo.png" }}
      />,
    )
    const img = container.querySelector("img")
    expect(img).not.toBeNull()
    expect(img?.getAttribute("src")).toBe("https://example.com/foo.png")
    expect(img?.getAttribute("alt")).toBe("team photo")
  })
})


describe("ConditionalContainerRenderer (WB-3)", () => {
  it("renders children inside a div with direction attribute", () => {
    const atom = mkAtom("conditional_container", "a8", {
      direction: "column",
    })
    const { container } = render(
      <ConditionalContainerRenderer
        atom={atom}
        config={atom.config as unknown as ConditionalContainerConfig}
        resolvedBindings={{}}
      >
        <span data-testid="child">child content</span>
      </ConditionalContainerRenderer>,
    )
    const root = container.querySelector("[data-atom-id='a8']")
    expect(root?.tagName).toBe("DIV")
    expect(root?.getAttribute("data-direction")).toBe("column")
    expect(root?.querySelector("[data-testid='child']")?.textContent).toBe(
      "child content",
    )
  })

  it("hides content when condition binding resolves falsy", () => {
    const atom = mkAtom("conditional_container", "a8")
    const { container } = render(
      <ConditionalContainerRenderer
        atom={atom}
        config={{} as ConditionalContainerConfig}
        resolvedBindings={{ condition: false }}
      >
        <span>hidden</span>
      </ConditionalContainerRenderer>,
    )
    expect(container.querySelector("[data-atom-id='a8']")).toBeNull()
  })
})


describe("RepeaterAtomRenderer (WB-3, NEW)", () => {
  it("renders provided children rows", () => {
    const atom = mkAtom("repeater_atom", "rep", {
      binding_id: "rows",
      children: ["row_label"],
      direction: "column",
      spacing: "normal",
    })
    const { container } = render(
      <RepeaterAtomRenderer
        atom={atom}
        config={atom.config as unknown as RepeaterAtomConfig}
        resolvedBindings={{}}
      >
        <span data-testid="row">row content</span>
      </RepeaterAtomRenderer>,
    )
    const el = container.querySelector("[data-atom-id='rep']")
    expect(el).not.toBeNull()
    expect(el?.getAttribute("data-direction")).toBe("column")
    expect(container.querySelector("[data-testid='row']")?.textContent).toBe(
      "row content",
    )
  })

  it("renders empty_state when no rows provided", () => {
    const atom = mkAtom("repeater_atom", "rep", {
      binding_id: "rows",
      children: [],
      empty_state: "Nothing yet",
    })
    const { container } = render(
      <RepeaterAtomRenderer
        atom={atom}
        config={atom.config as unknown as RepeaterAtomConfig}
        resolvedBindings={{}}
      />,
    )
    const el = container.querySelector("[data-atom-id='rep']")
    expect(el?.textContent).toBe("Nothing yet")
  })

  it("exposes row count via data attribute when children provided", () => {
    const atom = mkAtom("repeater_atom", "rep", {
      binding_id: "rows",
      children: ["row_label"],
    })
    const { container } = render(
      <RepeaterAtomRenderer
        atom={atom}
        config={atom.config as unknown as RepeaterAtomConfig}
        resolvedBindings={{}}
      >
        {[<span key="0">a</span>, <span key="1">b</span>]}
      </RepeaterAtomRenderer>,
    )
    expect(
      container
        .querySelector("[data-atom-id='rep']")
        ?.getAttribute("data-row-count"),
    ).toBe("2")
  })
})
