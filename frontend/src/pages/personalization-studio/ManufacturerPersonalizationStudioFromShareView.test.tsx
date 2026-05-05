/**
 * ManufacturerPersonalizationStudioFromShareView tests — Phase 1F
 * Mfg-tenant read-only canvas chrome at canonical
 * `manufacturer_from_fh_share` authoring context.
 *
 * Coverage:
 *   - Canonical loading + ready + reviewed + error states
 *   - Read-only chrome (Q9c canonical-discipline): read-only badge +
 *     "shared from {fh_tenant_name}" attribution + "Mark reviewed"
 *     commit affordance (per §14.14.5 canonical per-authoring-context
 *     labels)
 *   - Anti-pattern 17: canonical action vocabulary canonically bounded —
 *     NO canvas-mutation affordances surface at FE chrome substrate
 *   - Anti-pattern 18: data-attributes mark canonical bounded scope
 *     (authoring_context=manufacturer_from_fh_share, write_mode=read_only)
 *   - Canonical canvas snapshot rendering from canvas_state JSON
 *   - "Mark reviewed" commit invokes commitInstance + transitions to
 *     reviewed state
 *   - Canonical re-open at canonical committed lifecycle_state surfaces
 *     reviewed-state chrome
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import ManufacturerPersonalizationStudioFromShareView from "./ManufacturerPersonalizationStudioFromShareView"
import type { FromShareInstanceResponse } from "@/types/personalization-studio"


vi.mock("@/services/personalization-studio-service", () => ({
  openInstanceFromShare: vi.fn(),
  commitInstance: vi.fn().mockResolvedValue({
    id: "mfg-instance-1",
    company_id: "mfg-co",
    template_type: "burial_vault_personalization_studio",
    authoring_context: "manufacturer_from_fh_share",
    lifecycle_state: "committed",
    linked_entity_type: "document_share",
    linked_entity_id: "share-1",
    document_id: "doc-1",
    opened_at: "2026-05-05T00:00:00Z",
    opened_by_user_id: "mfg-user",
    last_active_at: "2026-05-05T00:01:00Z",
    committed_at: "2026-05-05T00:01:00Z",
    committed_by_user_id: "mfg-user",
    abandoned_at: null,
    abandoned_by_user_id: null,
    family_approval_status: null,
    family_approval_requested_at: null,
    family_approval_decided_at: null,
  }),
}))


function _canonicalResponse(
  overrides: Partial<FromShareInstanceResponse> = {},
): FromShareInstanceResponse {
  return {
    instance: {
      id: "mfg-instance-1",
      company_id: "mfg-co",
      template_type: "burial_vault_personalization_studio",
      authoring_context: "manufacturer_from_fh_share",
      lifecycle_state: "active",
      linked_entity_type: "document_share",
      linked_entity_id: "share-1",
      document_id: "doc-1",
      opened_at: "2026-05-05T00:00:00Z",
      opened_by_user_id: "mfg-user",
      last_active_at: "2026-05-05T00:00:00Z",
      committed_at: null,
      committed_by_user_id: null,
      abandoned_at: null,
      abandoned_by_user_id: null,
      family_approval_status: null,
      family_approval_requested_at: null,
      family_approval_decided_at: null,
    },
    canvas_state: {
      schema_version: 1,
      template_type: "burial_vault_personalization_studio",
      canvas_layout: { elements: [] },
      vault_product: {
        vault_product_id: null,
        vault_product_name: "Bronze",
      },
      emblem_key: null,
      name_display: "John Smith",
      font: "serif",
      birth_date_display: "1950",
      death_date_display: "2026",
      nameplate_text: null,
      options: {
        legacy_print: null,
        physical_nameplate: null,
        physical_emblem: null,
        vinyl: null,
      },
      family_approval_status: "approved",
    } as unknown as never,
    document_share_id: "share-1",
    owner_company_id: "fh-co",
    owner_company_name: "Hopkins Funeral Home",
    granted_at: "2026-05-05T00:00:00Z",
    decedent_name: "John Smith",
    ...overrides,
  }
}


function _renderAt(documentShareId = "share-1") {
  return render(
    <MemoryRouter
      initialEntries={[
        `/personalization-studio/from-share/${documentShareId}`,
      ]}
    >
      <Routes>
        <Route
          path="/personalization-studio/from-share/:documentShareId"
          element={<ManufacturerPersonalizationStudioFromShareView />}
        />
      </Routes>
    </MemoryRouter>,
  )
}


describe("ManufacturerPersonalizationStudioFromShareView", () => {
  it("renders canonical Mfg-tenant read-only chrome with bounded-scope attributes", async () => {
    const { openInstanceFromShare } = await import(
      "@/services/personalization-studio-service"
    )
    ;(
      openInstanceFromShare as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(_canonicalResponse())

    _renderAt()

    await waitFor(() => {
      expect(
        screen.getByTestId(
          "manufacturer-personalization-studio-from-share-view",
        ),
      ).toBeInTheDocument()
    })

    // Anti-pattern 18 + canonical Q9c canonical-discipline.
    const view = screen.getByTestId(
      "manufacturer-personalization-studio-from-share-view",
    )
    expect(view).toHaveAttribute(
      "data-authoring-context",
      "manufacturer_from_fh_share",
    )
    expect(view).toHaveAttribute("data-write-mode", "read_only")

    // Read-only badge canonical at canonical canvas-frame chrome.
    expect(screen.getByTestId("read-only-badge")).toHaveTextContent(
      "Read-only",
    )

    // Canonical "Shared from {fh_tenant_name}" attribution.
    expect(
      screen.getByTestId("shared-from-attribution"),
    ).toHaveTextContent(/Hopkins Funeral Home/i)
  })

  it("renders canonical canvas snapshot fields verbatim (full-disclosure per §3.26.11.12.19.4)", async () => {
    const { openInstanceFromShare } = await import(
      "@/services/personalization-studio-service"
    )
    ;(
      openInstanceFromShare as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(_canonicalResponse())

    _renderAt()

    await waitFor(() => {
      expect(screen.getByText("Bronze")).toBeInTheDocument()
    })
    expect(screen.getByText("serif")).toBeInTheDocument()
    expect(screen.getByText("1950 — 2026")).toBeInTheDocument()
    // Canonical full-disclosure: decedent_name surfaces verbatim.
    expect(
      screen.getAllByText("John Smith").length,
    ).toBeGreaterThan(0)
  })

  it("renders canonical 'Mark reviewed' canonical commit affordance per §14.14.5", async () => {
    const { openInstanceFromShare } = await import(
      "@/services/personalization-studio-service"
    )
    ;(
      openInstanceFromShare as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(_canonicalResponse())

    _renderAt()

    await waitFor(() => {
      expect(
        screen.getByTestId("mark-reviewed-button"),
      ).toBeInTheDocument()
    })
    expect(
      screen.getByTestId("mark-reviewed-button"),
    ).toHaveTextContent("Mark reviewed")
  })

  it("Anti-pattern 17: canonical canvas-mutation affordances absent", async () => {
    const { openInstanceFromShare } = await import(
      "@/services/personalization-studio-service"
    )
    ;(
      openInstanceFromShare as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(_canonicalResponse())

    _renderAt()

    await waitFor(() => {
      expect(screen.getByTestId("readonly-canvas-frame")).toBeInTheDocument()
    })

    // Canonical action vocabulary bounded — NO canvas-mutation affordances
    // canonical-render at canonical Mfg-tenant scope. Verify by absence
    // of canonical FH-side affordance test-ids.
    expect(
      screen.queryByTestId("canvas-add-element"),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByTestId("canvas-edit-element"),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByTestId("commit-canvas-state-button"),
    ).not.toBeInTheDocument()
    // Canonical commit_canvas_state action canonical-absent — only
    // canonical commit_instance ("Mark reviewed") canonical-surfaces.
  })

  it("'Mark reviewed' click invokes commitInstance + transitions to reviewed state", async () => {
    const { openInstanceFromShare, commitInstance } = await import(
      "@/services/personalization-studio-service"
    )
    ;(
      openInstanceFromShare as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(_canonicalResponse())

    _renderAt()

    await waitFor(() => {
      expect(
        screen.getByTestId("mark-reviewed-button"),
      ).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("mark-reviewed-button"))

    await waitFor(() => {
      expect(commitInstance).toHaveBeenCalledWith("mfg-instance-1")
    })
    await waitFor(() => {
      expect(
        screen.getByTestId("mark-reviewed-confirmation"),
      ).toBeInTheDocument()
    })
    expect(
      screen.getByTestId("mark-reviewed-confirmation"),
    ).toHaveTextContent(/marked reviewed/i)
  })

  it("renders reviewed-state chrome on canonical re-open at committed lifecycle_state", async () => {
    const { openInstanceFromShare } = await import(
      "@/services/personalization-studio-service"
    )
    const reopened = _canonicalResponse({
      instance: {
        ..._canonicalResponse().instance,
        lifecycle_state: "committed",
        committed_at: "2026-05-05T00:01:00Z",
        committed_by_user_id: "mfg-user",
      },
    })
    ;(
      openInstanceFromShare as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(reopened)

    _renderAt()

    await waitFor(() => {
      expect(
        screen.getByTestId("mark-reviewed-confirmation"),
      ).toBeInTheDocument()
    })
    // Mark reviewed button NOT canonical-rendered when canonical
    // committed lifecycle_state.
    expect(
      screen.queryByTestId("mark-reviewed-button"),
    ).not.toBeInTheDocument()
  })

  it("renders canonical 404-style error on missing share", async () => {
    const { openInstanceFromShare } = await import(
      "@/services/personalization-studio-service"
    )
    ;(
      openInstanceFromShare as ReturnType<typeof vi.fn>
    ).mockRejectedValueOnce({
      response: { status: 404, data: { detail: "Share not found." } },
    })

    _renderAt()

    await waitFor(() => {
      expect(screen.getByText("Share not found.")).toBeInTheDocument()
    })
  })

  it("renders canonical 403-style error on revoked share", async () => {
    const { openInstanceFromShare } = await import(
      "@/services/personalization-studio-service"
    )
    ;(
      openInstanceFromShare as ReturnType<typeof vi.fn>
    ).mockRejectedValueOnce({
      response: { status: 403, data: { detail: "Share has been revoked." } },
    })

    _renderAt()

    await waitFor(() => {
      expect(
        screen.getByText("Share has been revoked."),
      ).toBeInTheDocument()
    })
  })
})
