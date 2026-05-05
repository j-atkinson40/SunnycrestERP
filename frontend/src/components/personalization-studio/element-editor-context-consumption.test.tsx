/**
 * ElementEditorSurface canonical-context-consumption tests — Phase 1G
 * chrome-canvas runtime wiring at canonical FontEditor + EmblemEditor.
 *
 * Coverage:
 *   - FontEditor canonical-context-consumes canonical Hopkins per-tenant
 *     font_catalog (canonical "sans" canonical-excluded)
 *   - FontEditor canonical-fallback to canonical CANONICAL_FONT_CATALOG
 *     when canonical provider absent (canonical Phase 1B canonical-
 *     pattern-establisher discipline preserved)
 *   - EmblemEditor canonical-context-consumes canonical Hopkins per-
 *     tenant emblem_catalog (canonical patriotic_flag canonical-included
 *     canonical Hopkins-specific subset)
 *   - EmblemEditor canonical-fallback to canonical CANONICAL_EMBLEM_CATALOG
 *     when canonical provider absent
 */

import { useEffect } from "react"
import { render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { ElementEditorSurface } from "./ElementEditorSurface"
import {
  PersonalizationCanvasStateProvider,
  usePersonalizationCanvasState,
} from "./canvas-state-context"
import { PersonalizationStudioTenantConfigProvider } from "./tenant-config-context"
import {
  emptyCanvasState,
  type CanvasState,
} from "@/types/personalization-studio"
import type { TenantPersonalizationConfig } from "@/types/workshop"


// Canonical Hopkins config: canonical font subset + canonical
// patriotic_flag emblem inclusion (canonical Phase 1G demo seed
// canonical-Hopkins-specific subset).
function _hopkinsConfig(): TenantPersonalizationConfig {
  return {
    template_type: "burial_vault_personalization_studio",
    display_labels: {
      legacy_print: "Legacy Print",
      physical_nameplate: "Nameplate",
      physical_emblem: "Cover Emblem",
      vinyl: "Vinyl",
    },
    emblem_catalog: [
      "rose",
      "cross",
      "praying_hands",
      "dove",
      "wreath",
      "patriotic_flag",
    ],
    font_catalog: ["serif", "italic", "uppercase"],
    legacy_print_catalog: [],
    defaults: {
      display_labels: {
        legacy_print: "Legacy Print",
        physical_nameplate: "Nameplate",
        physical_emblem: "Cover Emblem",
        vinyl: "Vinyl",
      },
      emblem_catalog: [
        "rose", "cross", "praying_hands", "dove",
        "wreath", "star_of_david", "masonic", "patriotic_flag",
      ],
      font_catalog: ["serif", "sans", "italic", "uppercase"],
      legacy_print_catalog: [],
    },
    vinyl_symbols: [],
  }
}


function _initialCanvasStateWithFontElement(): CanvasState {
  const base = emptyCanvasState("burial_vault_personalization_studio")
  return {
    ...base,
    canvas_layout: {
      elements: [
        {
          id: "elem-font-1",
          element_type: "name_text",
          x: 100,
          y: 100,
          config: { name_display: "TEST", font: "serif" },
        },
      ],
    },
  }
}


function _initialCanvasStateWithEmblemElement(): CanvasState {
  const base = emptyCanvasState("burial_vault_personalization_studio")
  return {
    ...base,
    canvas_layout: {
      elements: [
        {
          id: "elem-emblem-1",
          element_type: "emblem",
          x: 100,
          y: 100,
          config: { emblem_key: "rose" },
        },
      ],
    },
  }
}


// Canonical helper: surfaces canonical setEditing canonical-pre-mount
// for canonical ElementEditorSurface canonical-render. useEffect
// canonical-fires once at canonical mount per canonical canonical-
// canonical-mount-only discipline.
function _OpenEditor({
  elementId,
  editorType,
}: {
  elementId: string
  editorType: "font" | "emblem" | "date" | "nameplate_text"
}) {
  const { setEditing } = usePersonalizationCanvasState()
  useEffect(() => {
    setEditing({ elementId, editorType })
    // Canonical setEditing canonical-stable canonical-reference at
    // canonical context value canonical-memo; canonical effect
    // canonical-fires once at canonical mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return null
}


describe("FontEditor canonical-context-consumption", () => {
  it("canonical-Hopkins-config canonical-flows canonical font_catalog into canonical FontEditor", async () => {
    render(
      <PersonalizationStudioTenantConfigProvider
        templateType="burial_vault_personalization_studio"
        initialConfig={_hopkinsConfig()}
      >
        <PersonalizationCanvasStateProvider
          initialCanvasState={_initialCanvasStateWithFontElement()}
        >
          <_OpenEditor elementId="elem-font-1" editorType="font" />
          <ElementEditorSurface />
        </PersonalizationCanvasStateProvider>
      </PersonalizationStudioTenantConfigProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId("font-editor-select")).toBeInTheDocument()
    })

    const select = screen.getByTestId(
      "font-editor-select",
    ) as HTMLSelectElement
    const options = Array.from(select.options).map((o) => o.value)
    // Canonical Hopkins-specific canonical-subset: serif + italic +
    // uppercase canonical-included; canonical "sans" canonical-excluded.
    expect(options).toEqual(["serif", "italic", "uppercase"])
    expect(options).not.toContain("sans")
  })

  it("canonical-fallback to canonical CANONICAL_FONT_CATALOG when canonical provider absent", async () => {
    render(
      <PersonalizationCanvasStateProvider
        initialCanvasState={_initialCanvasStateWithFontElement()}
      >
        <_OpenEditor elementId="elem-font-1" editorType="font" />
        <ElementEditorSurface />
      </PersonalizationCanvasStateProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId("font-editor-select")).toBeInTheDocument()
    })

    const select = screen.getByTestId(
      "font-editor-select",
    ) as HTMLSelectElement
    const options = Array.from(select.options).map((o) => o.value)
    // Canonical Phase 1B canonical-pattern-establisher canonical-default
    // catalog canonical-fallback (canonical sans canonical-included).
    expect(options).toContain("serif")
    expect(options).toContain("sans")
    expect(options).toContain("italic")
    expect(options).toContain("uppercase")
  })
})


describe("EmblemEditor canonical-context-consumption", () => {
  it("canonical-Hopkins-config canonical-flows canonical emblem_catalog into canonical EmblemEditor", async () => {
    render(
      <PersonalizationStudioTenantConfigProvider
        templateType="burial_vault_personalization_studio"
        initialConfig={_hopkinsConfig()}
      >
        <PersonalizationCanvasStateProvider
          initialCanvasState={_initialCanvasStateWithEmblemElement()}
        >
          <_OpenEditor elementId="elem-emblem-1" editorType="emblem" />
          <ElementEditorSurface />
        </PersonalizationCanvasStateProvider>
      </PersonalizationStudioTenantConfigProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId("emblem-editor-grid")).toBeInTheDocument()
    })

    // Canonical Hopkins-specific canonical-subset: canonical
    // patriotic_flag canonical-included.
    expect(
      screen.getByText("Patriotic flag"),
    ).toBeInTheDocument()
    expect(screen.getByText("Rose")).toBeInTheDocument()
    expect(screen.getByText("Cross")).toBeInTheDocument()
    // Canonical canonical-default-but-Hopkins-excluded canonical-
    // emblem-keys canonical-do-not-render at canonical Hopkins scope:
    // canonical star_of_david + canonical masonic canonical-excluded.
    expect(screen.queryByText("Star of David")).not.toBeInTheDocument()
    expect(screen.queryByText("Masonic")).not.toBeInTheDocument()
  })

  it("canonical-fallback to canonical CANONICAL_EMBLEM_CATALOG when canonical provider absent", async () => {
    render(
      <PersonalizationCanvasStateProvider
        initialCanvasState={_initialCanvasStateWithEmblemElement()}
      >
        <_OpenEditor elementId="elem-emblem-1" editorType="emblem" />
        <ElementEditorSurface />
      </PersonalizationCanvasStateProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId("emblem-editor-grid")).toBeInTheDocument()
    })

    // Canonical Phase 1B canonical-pattern-establisher canonical-default
    // catalog canonical-fallback (canonical 5-emblem default surface).
    expect(screen.getByText("Rose")).toBeInTheDocument()
    expect(screen.getByText("Cross")).toBeInTheDocument()
    expect(screen.getByText("Praying hands")).toBeInTheDocument()
    expect(screen.getByText("Dove")).toBeInTheDocument()
    expect(screen.getByText("Wreath")).toBeInTheDocument()
  })
})
