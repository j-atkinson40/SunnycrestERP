/**
 * PersonalizationStudioTuneModePanel tests — Phase 1D Tune mode chrome
 * per DESIGN_LANGUAGE §14.14.2 visual canon.
 *
 * Covers:
 * - Per-dimension sub-panel rendering (display labels + emblem catalog
 *   + font catalog + legacy print catalog)
 * - Tenant config load + save flow
 * - Display label override + reset behavior
 * - Catalog subset selection (toggle + select-all + select-none)
 * - Boundary discipline error surfacing (HTTP 422 from backend)
 * - Pattern-establisher discipline (templateType prop dispatch for
 *   Step 2 inheritance)
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { PersonalizationStudioTuneModePanel } from "./PersonalizationStudioTuneModePanel"
import type { TenantPersonalizationConfig } from "@/types/workshop"

const FIXTURE_CONFIG: TenantPersonalizationConfig = {
  template_type: "burial_vault_personalization_studio",
  display_labels: {
    legacy_print: "Legacy Print",
    physical_nameplate: "Nameplate",
    physical_emblem: "Emblem",
    vinyl: "Vinyl",
  },
  emblem_catalog: ["rose", "cross", "praying_hands", "dove"],
  font_catalog: ["serif", "sans", "italic"],
  legacy_print_catalog: ["American Flag", "Going Home", "Cross — Gold"],
  defaults: {
    display_labels: {
      legacy_print: "Legacy Print",
      physical_nameplate: "Nameplate",
      physical_emblem: "Emblem",
      vinyl: "Vinyl",
    },
    emblem_catalog: ["rose", "cross", "praying_hands", "dove", "wreath"],
    font_catalog: ["serif", "sans", "italic", "uppercase"],
    legacy_print_catalog: [
      "American Flag",
      "Going Home",
      "Cross — Gold",
      "Pieta",
    ],
  },
  vinyl_symbols: ["Cross", "Star of David", "Floral"],
}

vi.mock("@/services/workshop-service", () => {
  // Inlined fixture per vi.mock factory hoisting discipline — top-level
  // variable references not accessible inside the factory.
  const fixture: TenantPersonalizationConfig = {
    template_type: "burial_vault_personalization_studio",
    display_labels: {
      legacy_print: "Legacy Print",
      physical_nameplate: "Nameplate",
      physical_emblem: "Emblem",
      vinyl: "Vinyl",
    },
    emblem_catalog: ["rose", "cross", "praying_hands", "dove"],
    font_catalog: ["serif", "sans", "italic"],
    legacy_print_catalog: ["American Flag", "Going Home", "Cross — Gold"],
    defaults: {
      display_labels: {
        legacy_print: "Legacy Print",
        physical_nameplate: "Nameplate",
        physical_emblem: "Emblem",
        vinyl: "Vinyl",
      },
      emblem_catalog: ["rose", "cross", "praying_hands", "dove", "wreath"],
      font_catalog: ["serif", "sans", "italic", "uppercase"],
      legacy_print_catalog: [
        "American Flag",
        "Going Home",
        "Cross — Gold",
        "Pieta",
      ],
    },
    vinyl_symbols: ["Cross", "Star of David", "Floral"],
  }
  return {
    getTenantPersonalizationConfig: vi.fn().mockResolvedValue(fixture),
    updateTenantPersonalizationConfig: vi
      .fn()
      .mockImplementation(async (_templateType: string, body: unknown) => {
        const next = { ...fixture }
        const update = body as Partial<TenantPersonalizationConfig>
        if (update.display_labels) {
          next.display_labels = {
            ...next.display_labels,
            ...update.display_labels,
          }
        }
        if (update.emblem_catalog) next.emblem_catalog = update.emblem_catalog
        if (update.font_catalog) next.font_catalog = update.font_catalog
        if (update.legacy_print_catalog) {
          next.legacy_print_catalog = update.legacy_print_catalog
        }
        return next
      }),
  }
})


describe("PersonalizationStudioTuneModePanel — Phase 1D Tune mode chrome", () => {
  it("renders all 4 dimension sub-panels per §14.14.2 visual canon", async () => {
    render(
      <PersonalizationStudioTuneModePanel templateType="burial_vault_personalization_studio" />,
    )
    await waitFor(() => {
      expect(
        document.querySelector(
          "[data-slot='personalization-studio-tune-mode-panel']",
        ),
      ).toBeInTheDocument()
    })
    expect(
      document.querySelector("[data-section='display-labels']"),
    ).toBeInTheDocument()
    expect(
      document.querySelector("[data-section='emblem-catalog']"),
    ).toBeInTheDocument()
    expect(
      document.querySelector("[data-section='font-catalog']"),
    ).toBeInTheDocument()
    expect(
      document.querySelector("[data-section='legacy-print-catalog']"),
    ).toBeInTheDocument()
  })

  it("renders display label inputs for each canonical option type", async () => {
    render(
      <PersonalizationStudioTuneModePanel templateType="burial_vault_personalization_studio" />,
    )
    await waitFor(() => {
      const fields = document.querySelectorAll(
        "[data-slot='display-label-field']",
      )
      expect(fields.length).toBe(4)
    })
    const optionTypes = Array.from(
      document.querySelectorAll("[data-slot='display-label-field']"),
    ).map((el) => el.getAttribute("data-option-type"))
    expect(optionTypes.sort()).toEqual([
      "legacy_print",
      "physical_emblem",
      "physical_nameplate",
      "vinyl",
    ])
  })

  it("save button disabled when no changes", async () => {
    render(
      <PersonalizationStudioTuneModePanel templateType="burial_vault_personalization_studio" />,
    )
    await waitFor(() => {
      expect(
        document.querySelector("[data-slot='tune-mode-panel-save']"),
      ).toBeInTheDocument()
    })
    const saveBtn = document.querySelector(
      "[data-slot='tune-mode-panel-save']",
    ) as HTMLButtonElement
    expect(saveBtn.disabled).toBe(true)
  })

  it("editing display label enables save button + marks panel dirty", async () => {
    render(
      <PersonalizationStudioTuneModePanel templateType="burial_vault_personalization_studio" />,
    )
    await waitFor(() => {
      expect(
        document.querySelector("[data-section='display-labels']"),
      ).toBeInTheDocument()
    })
    const vinylField = document.querySelector(
      "[data-slot='display-label-field'][data-option-type='vinyl'] input",
    ) as HTMLInputElement
    fireEvent.change(vinylField, { target: { value: "Life's Reflections" } })

    const saveBtn = document.querySelector(
      "[data-slot='tune-mode-panel-save']",
    ) as HTMLButtonElement
    expect(saveBtn.disabled).toBe(false)
    const panel = document.querySelector(
      "[data-slot='personalization-studio-tune-mode-panel']",
    ) as HTMLElement
    expect(panel.getAttribute("data-dirty")).toBe("true")
  })

  it("display label override marks field as customized", async () => {
    render(
      <PersonalizationStudioTuneModePanel templateType="burial_vault_personalization_studio" />,
    )
    await waitFor(() => {
      expect(
        document.querySelector("[data-section='display-labels']"),
      ).toBeInTheDocument()
    })
    const vinylField = document.querySelector(
      "[data-slot='display-label-field'][data-option-type='vinyl']",
    ) as HTMLElement
    expect(vinylField.getAttribute("data-overridden")).toBe("false")

    const input = vinylField.querySelector("input") as HTMLInputElement
    fireEvent.change(input, { target: { value: "Life's Reflections" } })
    expect(vinylField.getAttribute("data-overridden")).toBe("true")
  })

  it("editing display label back to default removes override", async () => {
    render(
      <PersonalizationStudioTuneModePanel templateType="burial_vault_personalization_studio" />,
    )
    await waitFor(() => {
      expect(
        document.querySelector("[data-section='display-labels']"),
      ).toBeInTheDocument()
    })
    const vinylField = document.querySelector(
      "[data-slot='display-label-field'][data-option-type='vinyl']",
    ) as HTMLElement
    const input = vinylField.querySelector("input") as HTMLInputElement
    fireEvent.change(input, { target: { value: "Life's Reflections" } })
    expect(vinylField.getAttribute("data-overridden")).toBe("true")
    // Revert to canonical default — override should clear.
    fireEvent.change(input, { target: { value: "Vinyl" } })
    expect(vinylField.getAttribute("data-overridden")).toBe("false")
  })

  it("emblem catalog renders all canonical-default entries", async () => {
    render(
      <PersonalizationStudioTuneModePanel templateType="burial_vault_personalization_studio" />,
    )
    await waitFor(() => {
      expect(
        document.querySelector("[data-section='emblem-catalog']"),
      ).toBeInTheDocument()
    })
    const entries = document.querySelectorAll(
      "[data-section='emblem-catalog'] [data-slot='emblem-catalog-entry']",
    )
    expect(entries.length).toBe(FIXTURE_CONFIG.defaults.emblem_catalog.length)
  })

  it("emblem catalog entries reflect tenant's selected subset", async () => {
    render(
      <PersonalizationStudioTuneModePanel templateType="burial_vault_personalization_studio" />,
    )
    await waitFor(() => {
      expect(
        document.querySelector("[data-section='emblem-catalog']"),
      ).toBeInTheDocument()
    })
    // Tenant has 4 emblems selected; canonical default has 5.
    const activeEntries = document.querySelectorAll(
      "[data-section='emblem-catalog'] [data-slot='emblem-catalog-entry'][data-active='true']",
    )
    expect(activeEntries.length).toBe(FIXTURE_CONFIG.emblem_catalog.length)
    const inactiveEntries = document.querySelectorAll(
      "[data-section='emblem-catalog'] [data-slot='emblem-catalog-entry'][data-active='false']",
    )
    expect(inactiveEntries.length).toBe(
      FIXTURE_CONFIG.defaults.emblem_catalog.length -
        FIXTURE_CONFIG.emblem_catalog.length,
    )
  })

  it("clicking emblem entry toggles its active state", async () => {
    render(
      <PersonalizationStudioTuneModePanel templateType="burial_vault_personalization_studio" />,
    )
    await waitFor(() => {
      expect(
        document.querySelector("[data-section='emblem-catalog']"),
      ).toBeInTheDocument()
    })
    // 'wreath' starts inactive (in canonical default but not in tenant subset).
    const wreathBtn = document.querySelector(
      "[data-slot='emblem-catalog-entry'][data-entry-key='wreath']",
    ) as HTMLButtonElement
    expect(wreathBtn.getAttribute("data-active")).toBe("false")
    fireEvent.click(wreathBtn)
    expect(wreathBtn.getAttribute("data-active")).toBe("true")
    fireEvent.click(wreathBtn)
    expect(wreathBtn.getAttribute("data-active")).toBe("false")
  })

  it("'Select all' selects all canonical-default entries", async () => {
    render(
      <PersonalizationStudioTuneModePanel templateType="burial_vault_personalization_studio" />,
    )
    await waitFor(() => {
      expect(
        document.querySelector("[data-section='emblem-catalog']"),
      ).toBeInTheDocument()
    })
    const selectAllBtn = document.querySelector(
      "[data-slot='emblem-catalog-select-all']",
    ) as HTMLButtonElement
    fireEvent.click(selectAllBtn)
    const activeEntries = document.querySelectorAll(
      "[data-section='emblem-catalog'] [data-slot='emblem-catalog-entry'][data-active='true']",
    )
    expect(activeEntries.length).toBe(
      FIXTURE_CONFIG.defaults.emblem_catalog.length,
    )
  })

  it("'Select none' deselects all entries", async () => {
    render(
      <PersonalizationStudioTuneModePanel templateType="burial_vault_personalization_studio" />,
    )
    await waitFor(() => {
      expect(
        document.querySelector("[data-section='emblem-catalog']"),
      ).toBeInTheDocument()
    })
    const selectNoneBtn = document.querySelector(
      "[data-slot='emblem-catalog-select-none']",
    ) as HTMLButtonElement
    fireEvent.click(selectNoneBtn)
    const activeEntries = document.querySelectorAll(
      "[data-section='emblem-catalog'] [data-slot='emblem-catalog-entry'][data-active='true']",
    )
    expect(activeEntries.length).toBe(0)
  })

  it("save dispatches updateTenantPersonalizationConfig with draft body", async () => {
    const service = await import("@/services/workshop-service")
    vi.clearAllMocks()
    render(
      <PersonalizationStudioTuneModePanel templateType="burial_vault_personalization_studio" />,
    )
    await waitFor(() => {
      expect(
        document.querySelector("[data-section='display-labels']"),
      ).toBeInTheDocument()
    })
    const vinylInput = document.querySelector(
      "[data-slot='display-label-field'][data-option-type='vinyl'] input",
    ) as HTMLInputElement
    fireEvent.change(vinylInput, { target: { value: "Life's Reflections" } })

    fireEvent.click(
      document.querySelector("[data-slot='tune-mode-panel-save']")!,
    )
    await waitFor(() => {
      expect(service.updateTenantPersonalizationConfig).toHaveBeenCalledTimes(1)
    })
    const callArgs = (
      service.updateTenantPersonalizationConfig as ReturnType<typeof vi.fn>
    ).mock.calls[0]
    expect(callArgs[0]).toBe("burial_vault_personalization_studio")
    expect(callArgs[1].display_labels.vinyl).toBe("Life's Reflections")
  })

  it("'Discard changes' clears draft state without dispatching update", async () => {
    const service = await import("@/services/workshop-service")
    vi.clearAllMocks()
    render(
      <PersonalizationStudioTuneModePanel templateType="burial_vault_personalization_studio" />,
    )
    await waitFor(() => {
      expect(
        document.querySelector("[data-section='display-labels']"),
      ).toBeInTheDocument()
    })
    const vinylInput = document.querySelector(
      "[data-slot='display-label-field'][data-option-type='vinyl'] input",
    ) as HTMLInputElement
    fireEvent.change(vinylInput, { target: { value: "Life's Reflections" } })

    fireEvent.click(
      document.querySelector("[data-slot='tune-mode-panel-reset']")!,
    )
    expect(service.updateTenantPersonalizationConfig).not.toHaveBeenCalled()
    const panel = document.querySelector(
      "[data-slot='personalization-studio-tune-mode-panel']",
    ) as HTMLElement
    expect(panel.getAttribute("data-dirty")).toBe("false")
  })

  it("templateType prop dispatch (pattern-establisher for Step 2)", async () => {
    render(
      <PersonalizationStudioTuneModePanel templateType="burial_vault_personalization_studio" />,
    )
    await waitFor(() => {
      const panel = document.querySelector(
        "[data-slot='personalization-studio-tune-mode-panel']",
      )
      expect(panel).toBeInTheDocument()
      expect(panel?.getAttribute("data-template-type")).toBe(
        "burial_vault_personalization_studio",
      )
    })
  })

  it("save error from backend (HTTP 422 boundary violation) surfaces in chrome", async () => {
    const service = await import("@/services/workshop-service")
    vi.clearAllMocks()
    ;(
      service.updateTenantPersonalizationConfig as ReturnType<typeof vi.fn>
    ).mockRejectedValueOnce({
      response: {
        data: {
          detail: "emblem_catalog contains values not in canonical default",
        },
      },
    })

    render(
      <PersonalizationStudioTuneModePanel templateType="burial_vault_personalization_studio" />,
    )
    await waitFor(() => {
      expect(
        document.querySelector("[data-section='emblem-catalog']"),
      ).toBeInTheDocument()
    })
    const wreathBtn = document.querySelector(
      "[data-slot='emblem-catalog-entry'][data-entry-key='wreath']",
    ) as HTMLButtonElement
    fireEvent.click(wreathBtn)
    fireEvent.click(
      document.querySelector("[data-slot='tune-mode-panel-save']")!,
    )
    await waitFor(() => {
      expect(
        document.querySelector("[data-slot='tune-mode-panel-error']"),
      ).toBeInTheDocument()
    })
    expect(
      screen.getByText(/canonical default/),
    ).toBeInTheDocument()
  })
})
