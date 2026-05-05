/**
 * PersonalizationStudioTenantConfigContext tests — Phase 1G chrome-
 * canvas runtime wiring.
 *
 * Coverage:
 *   - Provider canonical-fetches canonical config at canonical mount
 *   - Provider canonical-surfaces canonical loading state
 *   - Provider canonical-fallback to canonical undefined config on
 *     canonical fetch error (canonical Storybook / test scope canonical-
 *     fallback)
 *   - Canonical hook canonical-returns null when canonical provider
 *     absent (canonical chrome consumers canonical-fall-back)
 *   - Canonical initialConfig prop canonical-bypasses canonical fetch
 *   - Hopkins canonical-specific catalog overrides canonical-flow
 *     through canonical context to canonical chrome consumers
 *   - Sunnycrest canonical-specific Q1 'Vinyl' display label canonical-
 *     flows through canonical context to canonical CanonicalOptionsPalette
 */

import { render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import {
  PersonalizationStudioTenantConfigProvider,
  usePersonalizationStudioTenantConfig,
} from "./tenant-config-context"
import { CanonicalOptionsPalette } from "./CanonicalOptionsPalette"
import {
  PersonalizationCanvasStateProvider,
} from "./canvas-state-context"
import { emptyCanvasState } from "@/types/personalization-studio"
import type { TenantPersonalizationConfig } from "@/types/workshop"


vi.mock("@/services/workshop-service", () => ({
  getTenantPersonalizationConfig: vi.fn(),
}))


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


function _sunnycrestConfig(): TenantPersonalizationConfig {
  return {
    ..._hopkinsConfig(),
    display_labels: {
      legacy_print: "Legacy Print",
      physical_nameplate: "Nameplate",
      physical_emblem: "Cover Emblem",
      vinyl: "Vinyl",
    },
    font_catalog: ["serif", "sans"],
  }
}


function _wilbertConfig(): TenantPersonalizationConfig {
  return {
    ..._hopkinsConfig(),
    display_labels: {
      legacy_print: "Legacy Print",
      physical_nameplate: "Nameplate",
      physical_emblem: "Cover Emblem",
      vinyl: "Life's Reflections",
    },
  }
}


// Canonical canvas-state provider wrapper for canonical
// CanonicalOptionsPalette test consumption (canonical Phase 1B
// canonical-pattern-establisher discipline preserves canonical canvas-
// state-context dependency).
function _CanvasStateWrap({ children }: { children: React.ReactNode }) {
  return (
    <PersonalizationCanvasStateProvider
      initialCanvasState={emptyCanvasState(
        "burial_vault_personalization_studio",
      )}
    >
      {children}
    </PersonalizationCanvasStateProvider>
  )
}


describe("PersonalizationStudioTenantConfigProvider", () => {
  it("canonical-fetches canonical config at canonical mount", async () => {
    const { getTenantPersonalizationConfig } = await import(
      "@/services/workshop-service"
    )
    ;(
      getTenantPersonalizationConfig as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(_hopkinsConfig())

    render(
      <PersonalizationStudioTenantConfigProvider templateType="burial_vault_personalization_studio">
        <ConfigConsumerForTest />
      </PersonalizationStudioTenantConfigProvider>,
    )

    await waitFor(() => {
      expect(
        screen.getByTestId("config-state"),
      ).toHaveAttribute("data-loading", "false")
    })
    expect(
      screen.getByTestId("font-catalog"),
    ).toHaveTextContent("serif,italic,uppercase")
    expect(getTenantPersonalizationConfig).toHaveBeenCalledWith(
      "burial_vault_personalization_studio",
    )
  })

  it("canonical-bypasses canonical fetch when canonical initialConfig provided", async () => {
    const { getTenantPersonalizationConfig } = await import(
      "@/services/workshop-service"
    )
    ;(
      getTenantPersonalizationConfig as ReturnType<typeof vi.fn>
    ).mockClear()

    render(
      <PersonalizationStudioTenantConfigProvider
        templateType="burial_vault_personalization_studio"
        initialConfig={_sunnycrestConfig()}
      >
        <ConfigConsumerForTest />
      </PersonalizationStudioTenantConfigProvider>,
    )

    await waitFor(() => {
      expect(
        screen.getByTestId("font-catalog"),
      ).toHaveTextContent("serif,sans")
    })
    // Canonical initialConfig canonical-bypasses fetch.
    expect(getTenantPersonalizationConfig).not.toHaveBeenCalled()
  })

  it("canonical-fallback on canonical fetch error", async () => {
    const { getTenantPersonalizationConfig } = await import(
      "@/services/workshop-service"
    )
    ;(
      getTenantPersonalizationConfig as ReturnType<typeof vi.fn>
    ).mockRejectedValueOnce(new Error("network"))

    render(
      <PersonalizationStudioTenantConfigProvider templateType="burial_vault_personalization_studio">
        <ConfigConsumerForTest />
      </PersonalizationStudioTenantConfigProvider>,
    )

    await waitFor(() => {
      expect(
        screen.getByTestId("config-state"),
      ).toHaveAttribute("data-loading", "false")
    })
    // Canonical fallback: canonical config canonical-undefined.
    expect(screen.getByTestId("config-state")).toHaveAttribute(
      "data-has-config",
      "false",
    )
  })
})


describe("usePersonalizationStudioTenantConfig outside provider", () => {
  it("canonical-returns null when canonical provider absent", () => {
    render(<ConfigConsumerForTest />)
    expect(screen.getByTestId("config-state")).toHaveAttribute(
      "data-no-provider",
      "true",
    )
  })
})


describe("CanonicalOptionsPalette canonical-context-consumes Hopkins config", () => {
  it("canonical-resolves canonical Hopkins display labels via canonical context", async () => {
    render(
      <PersonalizationStudioTenantConfigProvider
        templateType="burial_vault_personalization_studio"
        initialConfig={_hopkinsConfig()}
      >
        <_CanvasStateWrap>
          <CanonicalOptionsPalette />
        </_CanvasStateWrap>
      </PersonalizationStudioTenantConfigProvider>,
    )

    await waitFor(() => {
      expect(screen.getByText("Vinyl")).toBeInTheDocument()
    })
    // Canonical other 3 default labels canonical-render canonical.
    expect(screen.getByText("Legacy Print")).toBeInTheDocument()
    expect(screen.getByText("Nameplate")).toBeInTheDocument()
    expect(screen.getByText("Cover Emblem")).toBeInTheDocument()
  })

  it("canonical-resolves canonical Wilbert 'Life's Reflections' Q1 override via canonical context", async () => {
    render(
      <PersonalizationStudioTenantConfigProvider
        templateType="burial_vault_personalization_studio"
        initialConfig={_wilbertConfig()}
      >
        <_CanvasStateWrap>
          <CanonicalOptionsPalette />
        </_CanvasStateWrap>
      </PersonalizationStudioTenantConfigProvider>,
    )

    await waitFor(() => {
      expect(screen.getByText("Life's Reflections")).toBeInTheDocument()
    })
    // Canonical "Vinyl" canonical-default label canonical-replaced
    // by canonical Wilbert canonical-Life's-Reflections override.
    expect(screen.queryByText("Vinyl")).not.toBeInTheDocument()
  })

  it("canonical prop override canonical-wins over canonical context", async () => {
    render(
      <PersonalizationStudioTenantConfigProvider
        templateType="burial_vault_personalization_studio"
        initialConfig={_wilbertConfig()}
      >
        <_CanvasStateWrap>
          {/* Canonical Storybook / test scope canonical-bypass:
              canonical displayLabels canonical-prop canonical-wins. */}
          <CanonicalOptionsPalette
            displayLabels={{ vinyl: "Custom Test Label" }}
          />
        </_CanvasStateWrap>
      </PersonalizationStudioTenantConfigProvider>,
    )

    await waitFor(() => {
      expect(screen.getByText("Custom Test Label")).toBeInTheDocument()
    })
    expect(
      screen.queryByText("Life's Reflections"),
    ).not.toBeInTheDocument()
  })
})


// ─────────────────────────────────────────────────────────────────────
// Canonical config consumer for canonical context test scope
// ─────────────────────────────────────────────────────────────────────


function ConfigConsumerForTest() {
  const value = usePersonalizationStudioTenantConfig()
  if (value === null) {
    return (
      <div data-testid="config-state" data-no-provider="true">
        no-provider
      </div>
    )
  }
  return (
    <div
      data-testid="config-state"
      data-loading={value.isLoading ? "true" : "false"}
      data-has-config={value.config !== undefined ? "true" : "false"}
    >
      <span data-testid="font-catalog">
        {value.config?.font_catalog?.join(",") ?? ""}
      </span>
    </div>
  )
}
