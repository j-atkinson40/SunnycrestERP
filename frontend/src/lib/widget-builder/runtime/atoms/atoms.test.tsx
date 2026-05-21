/**
 * WB-2 Phase 1 atom renderer placeholder tests.
 *
 * Locks the data-attribute contract (data-atom-type, data-atom-id)
 * + fallback rendering behavior so WB-3 (real UI) can replace
 * internals without breaking AtomRenderer's dispatch.
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


describe("TextLabelRenderer", () => {
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
})


describe("ValueDisplayRenderer", () => {
  it("renders format marker when no binding present", () => {
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
    const el = container.querySelector("[data-atom-id='a2']")
    expect(el?.getAttribute("data-atom-type")).toBe("value_display")
  })

  it("renders bound value when present", () => {
    const atom = mkAtom("value_display", "a2", {
      format: "number",
      format_config: {},
    })
    const { container } = render(
      <ValueDisplayRenderer
        atom={atom}
        config={atom.config as unknown as ValueDisplayConfig}
        resolvedBindings={{ value: 42 }}
      />,
    )
    expect(container.textContent).toBe("42")
  })
})


describe("IconRenderer", () => {
  it("renders icon marker with name", () => {
    const atom = mkAtom("icon", "a3", { icon_name: "alert-circle" })
    const { container } = render(
      <IconRenderer
        atom={atom}
        config={atom.config as unknown as IconConfig}
        resolvedBindings={{}}
      />,
    )
    expect(container.textContent).toBe("[icon:alert-circle]")
    expect(
      container
        .querySelector("[data-atom-id='a3']")
        ?.getAttribute("data-atom-type"),
    ).toBe("icon")
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


describe("StatusBadgeRenderer", () => {
  it("renders default badge marker without binding", () => {
    const atom = mkAtom("status_badge", "a4", {
      status_map: {},
      show_icon: false,
    })
    const { container } = render(
      <StatusBadgeRenderer
        atom={atom}
        config={atom.config as unknown as StatusBadgeConfig}
        resolvedBindings={{}}
      />,
    )
    expect(container.textContent).toBe("[badge]")
    expect(
      container
        .querySelector("[data-atom-id='a4']")
        ?.getAttribute("data-atom-type"),
    ).toBe("status_badge")
  })

  it("includes status string when bound", () => {
    const atom = mkAtom("status_badge", "a4", {
      status_map: {},
      show_icon: false,
    })
    const { container } = render(
      <StatusBadgeRenderer
        atom={atom}
        config={atom.config as unknown as StatusBadgeConfig}
        resolvedBindings={{ status: "active" }}
      />,
    )
    expect(container.textContent).toBe("[badge:active]")
  })
})


describe("DividerRenderer", () => {
  it("renders hr with orientation data attribute", () => {
    const atom = mkAtom("divider", "a5", { orientation: "vertical" })
    const { container } = render(
      <DividerRenderer
        atom={atom}
        config={atom.config as unknown as DividerConfig}
        resolvedBindings={{}}
      />,
    )
    const hr = container.querySelector("hr")
    expect(hr).not.toBeNull()
    expect(hr?.getAttribute("data-atom-id")).toBe("a5")
    expect(hr?.getAttribute("data-atom-type")).toBe("divider")
    expect(hr?.getAttribute("data-orientation")).toBe("vertical")
  })

  it("defaults orientation to horizontal", () => {
    const atom = mkAtom("divider", "a5")
    const { container } = render(
      <DividerRenderer
        atom={atom}
        config={{} as DividerConfig}
        resolvedBindings={{}}
      />,
    )
    expect(container.querySelector("hr")?.getAttribute("data-orientation")).toBe(
      "horizontal",
    )
  })
})


describe("ButtonRenderer", () => {
  it("renders a button element with action-kind attribute", () => {
    const atom = mkAtom("button", "a6", {
      action_kind: "navigate",
      action_config: { route: "/x" },
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
    expect(btn?.textContent).toBe("[button]")
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

  it("uses bound label when present", () => {
    const atom = mkAtom("button", "a6", {
      action_kind: "navigate",
      action_config: {},
    })
    const { container } = render(
      <ButtonRenderer
        atom={atom}
        config={atom.config as unknown as ButtonConfig}
        resolvedBindings={{ label: "Open case" }}
      />,
    )
    expect(container.querySelector("button")?.textContent).toBe("Open case")
  })
})


describe("ImageRenderer", () => {
  it("renders placeholder span with source-kind attr", () => {
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
    expect(el?.textContent).toBe("[image]")
    expect(el?.getAttribute("data-source-kind")).toBe("vault_asset")
  })

  it("defaults source-kind to 'url'", () => {
    const atom = mkAtom("image", "a7")
    const { container } = render(
      <ImageRenderer
        atom={atom}
        config={{} as ImageConfig}
        resolvedBindings={{}}
      />,
    )
    expect(
      container
        .querySelector("[data-atom-id='a7']")
        ?.getAttribute("data-source-kind"),
    ).toBe("url")
  })
})


describe("ConditionalContainerRenderer", () => {
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

  it("renders empty when no children provided", () => {
    const atom = mkAtom("conditional_container", "a8")
    const { container } = render(
      <ConditionalContainerRenderer
        atom={atom}
        config={{} as ConditionalContainerConfig}
        resolvedBindings={{}}
      />,
    )
    const root = container.querySelector("[data-atom-id='a8']")
    expect(root).not.toBeNull()
    expect(root?.children.length).toBe(0)
  })
})
