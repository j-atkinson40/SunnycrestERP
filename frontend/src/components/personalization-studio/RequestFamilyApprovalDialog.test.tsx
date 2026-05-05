/**
 * RequestFamilyApprovalDialog tests — canonical FH-director-initiated
 * commit affordance per §3.26.11.12.16 Anti-pattern 1 + §3.26.14.14.5
 * operator-agency-at-commit-boundary discipline.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { RequestFamilyApprovalDialog } from "./RequestFamilyApprovalDialog"

// Mock the service module canonical at module substrate.
vi.mock("@/services/personalization-studio-service", () => ({
  requestFamilyApproval: vi.fn().mockResolvedValue({
    instance_id: "instance-1",
    action_idx: 0,
    family_email: "family@example.com",
    family_approval_status: "requested",
    delivery_id: "delivery-1",
  }),
}))


describe("RequestFamilyApprovalDialog", () => {
  it("renders canonical dialog title + description", () => {
    render(
      <RequestFamilyApprovalDialog
        open={true}
        onOpenChange={() => {}}
        instanceId="instance-1"
      />,
    )
    expect(
      screen.getByText("Send to family for approval"),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        /We'll email a private link/i,
      ),
    ).toBeInTheDocument()
  })

  it("disables submit button until canonical email is valid", () => {
    render(
      <RequestFamilyApprovalDialog
        open={true}
        onOpenChange={() => {}}
        instanceId="instance-1"
      />,
    )
    const submit = screen.getByTestId("request-family-approval-submit")
    // Disabled by default (no email).
    expect(submit).toBeDisabled()

    const emailInput = screen.getByTestId("family-email-input")
    fireEvent.change(emailInput, { target: { value: "not-an-email" } })
    expect(submit).toBeDisabled()

    fireEvent.change(emailInput, {
      target: { value: "family@example.com" },
    })
    expect(submit).not.toBeDisabled()
  })

  it("submits canonical request body + invokes onSent callback", async () => {
    const { requestFamilyApproval } = await import(
      "@/services/personalization-studio-service"
    )
    const onSent = vi.fn()
    const onOpenChange = vi.fn()

    render(
      <RequestFamilyApprovalDialog
        open={true}
        onOpenChange={onOpenChange}
        instanceId="instance-1"
        defaultFamilyEmail="family@example.com"
        onSent={onSent}
      />,
    )

    fireEvent.click(
      screen.getByTestId("request-family-approval-submit"),
    )

    await waitFor(() => {
      expect(requestFamilyApproval).toHaveBeenCalledWith("instance-1", {
        family_email: "family@example.com",
        family_first_name: null,
        optional_message: null,
      })
    })
    await waitFor(() => {
      expect(onSent).toHaveBeenCalled()
    })
    // Anti-pattern 1: dialog closes on successful commit; the FH
    // director's explicit click is the canonical commit boundary.
    await waitFor(() => {
      expect(onOpenChange).toHaveBeenCalledWith(false)
    })
  })

  it("pre-fills canonical default email + first name", () => {
    render(
      <RequestFamilyApprovalDialog
        open={true}
        onOpenChange={() => {}}
        instanceId="instance-1"
        defaultFamilyEmail="mary@example.com"
        defaultFamilyFirstName="Mary"
      />,
    )
    expect(screen.getByTestId("family-email-input")).toHaveValue(
      "mary@example.com",
    )
    expect(
      screen.getByTestId("family-first-name-input"),
    ).toHaveValue("Mary")
  })

  it("renders error feedback on commit failure", async () => {
    const { requestFamilyApproval } = await import(
      "@/services/personalization-studio-service"
    )
    ;(requestFamilyApproval as ReturnType<typeof vi.fn>).mockRejectedValueOnce({
      response: {
        status: 400,
        data: { detail: "Family approval is canonical FH-vertical only." },
      },
    })

    render(
      <RequestFamilyApprovalDialog
        open={true}
        onOpenChange={() => {}}
        instanceId="instance-1"
        defaultFamilyEmail="family@example.com"
      />,
    )

    fireEvent.click(
      screen.getByTestId("request-family-approval-submit"),
    )

    await waitFor(() => {
      expect(
        screen.getByTestId("request-family-approval-error"),
      ).toHaveTextContent(/canonical FH-vertical only/i)
    })
  })
})
