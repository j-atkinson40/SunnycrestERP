/**
 * VerticalsAdminPage UI test coverage.
 *
 * Verifies:
 *   - 4 rows render after fetch via mock adminApi.
 *   - Click "Edit" opens the modal pre-filled with the row's values.
 *   - Save fires adminApi.patch with the updated fields; modal closes
 *     + list refetches.
 *   - Slug renders as a <code> element (NOT an input) inside the
 *     edit modal.
 */
import { afterEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, waitFor } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"


vi.mock("@/bridgeable-admin/lib/admin-api", () => ({
  adminApi: {
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
  },
}))


import { adminApi } from "@/bridgeable-admin/lib/admin-api"
import VerticalsAdminPage from "./VerticalsAdminPage"


const CANONICAL_ROWS = [
  {
    slug: "manufacturing",
    display_name: "Manufacturing",
    description: null,
    status: "published",
    icon: null,
    sort_order: 10,
    created_at: "2026-05-13T00:00:00",
    updated_at: "2026-05-13T00:00:00",
  },
  {
    slug: "funeral_home",
    display_name: "Funeral Home",
    description: null,
    status: "published",
    icon: null,
    sort_order: 20,
    created_at: "2026-05-13T00:00:00",
    updated_at: "2026-05-13T00:00:00",
  },
  {
    slug: "cemetery",
    display_name: "Cemetery",
    description: null,
    status: "published",
    icon: null,
    sort_order: 30,
    created_at: "2026-05-13T00:00:00",
    updated_at: "2026-05-13T00:00:00",
  },
  {
    slug: "crematory",
    display_name: "Crematory",
    description: null,
    status: "published",
    icon: null,
    sort_order: 40,
    created_at: "2026-05-13T00:00:00",
    updated_at: "2026-05-13T00:00:00",
  },
]


afterEach(() => {
  vi.clearAllMocks()
})


describe("VerticalsAdminPage", () => {
  it("renders 4 rows after fetch", async () => {
    (adminApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: CANONICAL_ROWS,
    })
    const result = render(
      <MemoryRouter>
        <VerticalsAdminPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(result.getByTestId("verticals-row-manufacturing")).toBeTruthy()
      expect(result.getByTestId("verticals-row-funeral_home")).toBeTruthy()
      expect(result.getByTestId("verticals-row-cemetery")).toBeTruthy()
      expect(result.getByTestId("verticals-row-crematory")).toBeTruthy()
    })
    // include_archived=true is passed because the admin page wants to
    // show every row (including archived) for full visibility.
    expect(adminApi.get).toHaveBeenCalledWith(
      "/api/platform/admin/verticals/",
      { params: { include_archived: true } },
    )
  })

  it("opens edit modal with pre-filled values on Edit click", async () => {
    (adminApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: CANONICAL_ROWS,
    })
    const result = render(
      <MemoryRouter>
        <VerticalsAdminPage />
      </MemoryRouter>,
    )
    const editBtn = await waitFor(() =>
      result.getByTestId("verticals-row-manufacturing-edit"),
    )
    fireEvent.click(editBtn)
    await waitFor(() => {
      expect(result.getByTestId("verticals-edit-dialog")).toBeTruthy()
    })
    // Slug renders as <code>, NOT an input.
    const slugEl = result.getByTestId("verticals-edit-slug")
    expect(slugEl.tagName.toLowerCase()).toBe("code")
    expect(slugEl.textContent).toBe("manufacturing")
    // Display name field is pre-filled.
    const displayNameInput = result.getByTestId(
      "verticals-edit-display-name",
    ) as HTMLInputElement
    expect(displayNameInput.value).toBe("Manufacturing")
  })

  it("Save fires adminApi.patch with updated fields + modal closes + refetches", async () => {
    (adminApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: CANONICAL_ROWS,
    })
    ;(adminApi.patch as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { ...CANONICAL_ROWS[0], display_name: "Mfg Edited" },
    })

    const result = render(
      <MemoryRouter>
        <VerticalsAdminPage />
      </MemoryRouter>,
    )
    const editBtn = await waitFor(() =>
      result.getByTestId("verticals-row-manufacturing-edit"),
    )
    fireEvent.click(editBtn)
    await waitFor(() =>
      expect(result.getByTestId("verticals-edit-dialog")).toBeTruthy(),
    )

    const displayNameInput = result.getByTestId(
      "verticals-edit-display-name",
    ) as HTMLInputElement
    fireEvent.change(displayNameInput, { target: { value: "Mfg Edited" } })

    const saveBtn = result.getByTestId("verticals-edit-save")
    fireEvent.click(saveBtn)

    await waitFor(() => {
      expect(adminApi.patch).toHaveBeenCalled()
    })

    const patchCall = (adminApi.patch as ReturnType<typeof vi.fn>).mock
      .calls[0]
    expect(patchCall[0]).toBe(
      "/api/platform/admin/verticals/manufacturing",
    )
    expect(patchCall[1]).toMatchObject({ display_name: "Mfg Edited" })
    // Slug is NOT in the PATCH payload (immutable).
    expect(patchCall[1]).not.toHaveProperty("slug")

    // Modal closes after save.
    await waitFor(() => {
      expect(result.queryByTestId("verticals-edit-dialog")).toBeFalsy()
    })

    // List refetches after save (initial fetch + post-save refetch = 2).
    expect(adminApi.get).toHaveBeenCalledTimes(2)
  })

  it("slug field in modal is <code>, not an input", async () => {
    (adminApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: CANONICAL_ROWS,
    })
    const result = render(
      <MemoryRouter>
        <VerticalsAdminPage />
      </MemoryRouter>,
    )
    const editBtn = await waitFor(() =>
      result.getByTestId("verticals-row-funeral_home-edit"),
    )
    fireEvent.click(editBtn)
    await waitFor(() =>
      expect(result.getByTestId("verticals-edit-dialog")).toBeTruthy(),
    )
    const slugEl = result.getByTestId("verticals-edit-slug")
    // It must be a <code> element, NOT an <input>.
    expect(slugEl.tagName.toLowerCase()).toBe("code")
    // No <input> with the slug value anywhere in the dialog.
    const dialog = result.getByTestId("verticals-edit-dialog")
    const inputs = dialog.querySelectorAll("input")
    for (const input of inputs) {
      expect(input.value).not.toBe("funeral_home")
    }
  })
})
