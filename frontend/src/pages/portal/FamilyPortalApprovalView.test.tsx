/**
 * FamilyPortalApprovalView tests — canonical magic-link contextual
 * surface per §3.26.11.9 + §14.10.5 + §2.5 Portal Extension Pattern.
 *
 * Coverage:
 *   - Canonical loading + ready + submitted + error states
 *   - 3-outcome action vocabulary canonical surfaced
 *   - Anti-pattern 1: completion_note required for request_changes +
 *     decline; submit disabled until rationale filled
 *   - Anti-pattern 18: data-attributes mark canonical bounded scope
 *     (access_mode=portal_external, write_mode=limited,
 *     tenant-branded surface)
 *   - Canonical canvas snapshot rendering from canvas_state JSON
 *   - Outcome submission invokes commitFamilyApproval + transitions
 *     to submitted state
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"

import FamilyPortalApprovalView from "./FamilyPortalApprovalView"
import type { FamilyApprovalContextResponse } from "@/types/personalization-studio"


// Mock the service module canonical at module substrate.
vi.mock("@/services/personalization-studio-service", () => ({
  getFamilyApprovalContext: vi.fn(),
  commitFamilyApproval: vi.fn().mockResolvedValue({
    instance_id: "instance-1",
    outcome: "approve",
    action_status: "approved",
    family_approval_status: "approved",
    lifecycle_state: "committed",
  }),
}))


function _canonicalContext(
  overrides: Partial<FamilyApprovalContextResponse> = {},
): FamilyApprovalContextResponse {
  return {
    instance_id: "instance-1",
    decedent_name: "John Smith",
    fh_director_name: "Jane Director",
    action_status: "pending",
    outcomes: ["approve", "request_changes", "decline"],
    requires_completion_note: ["request_changes", "decline"],
    canvas: {
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
        family_approval_status: "requested",
      } as unknown as never, // CanvasState shape
      version_number: 1,
    },
    space: {
      template_id: "personalization_studio_family_approval",
      name: "Memorial Approval",
      icon: "heart",
      accent: "warm",
      access_mode: "portal_external",
      tenant_branding: true,
      write_mode: "limited",
      session_timeout_minutes: 60,
    },
    branding: {
      display_name: "Hopkins Funeral Home",
      logo_url: null,
      brand_color: "#7B3F00",
    },
    ...overrides,
  }
}


function _renderAt(token: string = "tok123") {
  return render(
    <MemoryRouter
      initialEntries={[
        `/portal/hopkins/personalization-studio/family-approval/${token}`,
      ]}
    >
      <Routes>
        <Route
          path="/portal/:tenantSlug/personalization-studio/family-approval/:token"
          element={<FamilyPortalApprovalView />}
        />
      </Routes>
    </MemoryRouter>,
  )
}


describe("FamilyPortalApprovalView", () => {
  it("renders canonical FH-tenant-branded surface with bounded scope attributes", async () => {
    const { getFamilyApprovalContext } = await import(
      "@/services/personalization-studio-service"
    )
    ;(
      getFamilyApprovalContext as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(_canonicalContext())

    _renderAt()

    await waitFor(() => {
      expect(
        screen.getByTestId("family-portal-approval-view"),
      ).toBeInTheDocument()
    })

    // Anti-pattern 18 + canonical Space modifier slice.
    const view = screen.getByTestId("family-portal-approval-view")
    expect(view).toHaveAttribute("data-access-mode", "portal_external")
    expect(view).toHaveAttribute("data-write-mode", "limited")
    expect(view).toHaveAttribute("data-tenant-branded", "true")

    // FH-tenant display name surfaces (in header + footer).
    expect(
      screen.getAllByText("Hopkins Funeral Home").length,
    ).toBeGreaterThan(0)
    // Decedent name surfaces (in page header + canvas snapshot).
    expect(
      screen.getAllByText("John Smith").length,
    ).toBeGreaterThan(0)
    expect(
      screen.getByText(/Prepared by Jane Director/i),
    ).toBeInTheDocument()
  })

  it("renders canonical 3-outcome action vocabulary", async () => {
    const { getFamilyApprovalContext } = await import(
      "@/services/personalization-studio-service"
    )
    ;(
      getFamilyApprovalContext as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(_canonicalContext())

    _renderAt()

    await waitFor(() => {
      expect(screen.getByTestId("outcome-approve")).toBeInTheDocument()
    })
    expect(
      screen.getByTestId("outcome-request_changes"),
    ).toBeInTheDocument()
    expect(screen.getByTestId("outcome-decline")).toBeInTheDocument()
  })

  it("disables submit until outcome selected; approve does NOT require note", async () => {
    const { getFamilyApprovalContext } = await import(
      "@/services/personalization-studio-service"
    )
    ;(
      getFamilyApprovalContext as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(_canonicalContext())

    _renderAt()

    await waitFor(() => {
      expect(screen.getByTestId("submit-decision")).toBeInTheDocument()
    })

    const submit = screen.getByTestId("submit-decision")
    expect(submit).toBeDisabled()

    fireEvent.click(screen.getByTestId("outcome-approve"))
    expect(submit).not.toBeDisabled()
    // Approve does NOT trigger completion-note input.
    expect(
      screen.queryByTestId("completion-note-input"),
    ).not.toBeInTheDocument()
  })

  it("Anti-pattern 1: request_changes requires completion_note rationale", async () => {
    const { getFamilyApprovalContext } = await import(
      "@/services/personalization-studio-service"
    )
    ;(
      getFamilyApprovalContext as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(_canonicalContext())

    _renderAt()

    await waitFor(() => {
      expect(
        screen.getByTestId("outcome-request_changes"),
      ).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("outcome-request_changes"))

    // Submit disabled — note required but empty.
    const submit = screen.getByTestId("submit-decision")
    expect(submit).toBeDisabled()
    expect(
      screen.getByTestId("completion-note-input"),
    ).toBeInTheDocument()

    fireEvent.change(screen.getByTestId("completion-note-input"), {
      target: { value: "Please change the font." },
    })
    expect(submit).not.toBeDisabled()
  })

  it("Anti-pattern 1: decline requires completion_note rationale", async () => {
    const { getFamilyApprovalContext } = await import(
      "@/services/personalization-studio-service"
    )
    ;(
      getFamilyApprovalContext as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(_canonicalContext())

    _renderAt()

    await waitFor(() => {
      expect(screen.getByTestId("outcome-decline")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId("outcome-decline"))
    expect(screen.getByTestId("submit-decision")).toBeDisabled()
    expect(
      screen.getByTestId("completion-note-input"),
    ).toBeInTheDocument()
  })

  it("submits approve and transitions to submitted state", async () => {
    const { getFamilyApprovalContext, commitFamilyApproval } =
      await import("@/services/personalization-studio-service")
    ;(
      getFamilyApprovalContext as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(_canonicalContext())

    _renderAt("tok-approve")

    await waitFor(() => {
      expect(screen.getByTestId("outcome-approve")).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId("outcome-approve"))
    fireEvent.click(screen.getByTestId("submit-decision"))

    await waitFor(() => {
      expect(commitFamilyApproval).toHaveBeenCalledWith(
        "hopkins",
        "tok-approve",
        { outcome: "approve", completion_note: null },
      )
    })
    // Submitted state — canonical thank-you copy.
    await waitFor(() => {
      expect(
        screen.getByText(/funeral home has been notified that you approved/i),
      ).toBeInTheDocument()
    })
  })

  it("renders canonical 401-style error state on invalid token", async () => {
    const { getFamilyApprovalContext } = await import(
      "@/services/personalization-studio-service"
    )
    ;(
      getFamilyApprovalContext as ReturnType<typeof vi.fn>
    ).mockRejectedValueOnce({
      response: {
        status: 401,
        data: { detail: "Token not found." },
      },
    })

    _renderAt("invalid")

    await waitFor(() => {
      expect(screen.getByText("Token not found.")).toBeInTheDocument()
    })
  })

  it("renders canonical 410 terminal-state error on consumed token", async () => {
    const { getFamilyApprovalContext } = await import(
      "@/services/personalization-studio-service"
    )
    ;(
      getFamilyApprovalContext as ReturnType<typeof vi.fn>
    ).mockRejectedValueOnce({
      response: {
        status: 410,
        data: { detail: "Token already consumed." },
      },
    })

    _renderAt("consumed")

    await waitFor(() => {
      expect(
        screen.getByText("Token already consumed."),
      ).toBeInTheDocument()
    })
  })

  it("renders canonical canvas snapshot fields from canvas_state JSON", async () => {
    const { getFamilyApprovalContext } = await import(
      "@/services/personalization-studio-service"
    )
    ;(
      getFamilyApprovalContext as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(_canonicalContext())

    _renderAt()

    await waitFor(() => {
      expect(screen.getByText("Bronze")).toBeInTheDocument()
    })
    expect(screen.getByText("serif")).toBeInTheDocument()
    expect(screen.getByText("1950 — 2026")).toBeInTheDocument()
  })

  it("renders 'finalizing' message when canvas_state is null", async () => {
    const { getFamilyApprovalContext } = await import(
      "@/services/personalization-studio-service"
    )
    ;(
      getFamilyApprovalContext as ReturnType<typeof vi.fn>
    ).mockResolvedValueOnce(
      _canonicalContext({
        canvas: { canvas_state: null, version_number: null },
      }),
    )

    _renderAt()

    await waitFor(() => {
      expect(
        screen.getByText(/funeral home is finalizing the design/i),
      ).toBeInTheDocument()
    })
  })
})
