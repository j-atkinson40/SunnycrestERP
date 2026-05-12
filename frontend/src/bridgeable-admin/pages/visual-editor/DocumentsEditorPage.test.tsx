/**
 * Arc-3.x-deep-link-retrofit — DocumentsEditorPage return-to banner tests.
 *
 * Mirrors Arc 3a FocusEditorPage canon + WorkflowEditorPage retrofit
 * test shape.
 */
import { afterEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom"

import DocumentsEditorPage from "./DocumentsEditorPage"


vi.mock(
  "@/bridgeable-admin/services/document-blocks-service",
  async () => {
    const actual = await vi.importActual<
      typeof import("@/bridgeable-admin/services/document-blocks-service")
    >("@/bridgeable-admin/services/document-blocks-service")
    return {
      ...actual,
      documentBlocksService: {
        listDocumentTypes: vi.fn().mockResolvedValue({
          categories: [],
          types: [],
        }),
        listBlockKinds: vi.fn().mockResolvedValue([]),
        listBlocks: vi.fn().mockResolvedValue([]),
      },
    }
  },
)

vi.mock(
  "@/services/documents-v2-service",
  async () => {
    const actual = await vi.importActual<
      typeof import("@/services/documents-v2-service")
    >("@/services/documents-v2-service")
    return {
      ...actual,
      documentsV2Service: {
        listTemplates: vi.fn().mockResolvedValue({ items: [] }),
        getTemplate: vi.fn().mockResolvedValue({
          id: "tpl-1",
          template_key: "test",
          document_type: "invoice",
          scope: "platform",
          versions: [],
        }),
        getTemplateVersion: vi.fn().mockResolvedValue({
          id: "ver-1",
          version_number: 1,
          status: "draft",
          body_template: "",
          subject_template: null,
          variable_schema: {},
          css_variables: {},
        }),
      },
    }
  },
)


function LocationProbe({ onLocation }: { onLocation: (path: string) => void }) {
  const loc = useLocation()
  onLocation(loc.pathname + loc.search)
  return null
}


afterEach(() => {
  vi.clearAllMocks()
})


describe("DocumentsEditorPage — Arc-3.x-deep-link-retrofit return-to banner", () => {
  it("does NOT render return-to banner when no return_to URL param", async () => {
    const result = render(
      <MemoryRouter initialEntries={["/visual-editor/documents"]}>
        <DocumentsEditorPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(result.getByTestId("documents-editor")).toBeTruthy()
    })
    expect(
      result.queryByTestId("documents-editor-return-to-banner"),
    ).toBeFalsy()
  })

  it("renders 'Back to runtime editor' affordance when return_to param present", async () => {
    const returnTo = encodeURIComponent(
      "/bridgeable-admin/runtime-editor/?tenant=hopkins-fh&user=u1",
    )
    const result = render(
      <MemoryRouter
        initialEntries={[
          `/visual-editor/documents?return_to=${returnTo}&template_id=tpl-1&scope=both`,
        ]}
      >
        <DocumentsEditorPage />
      </MemoryRouter>,
    )
    await waitFor(() => {
      expect(
        result.getByTestId("documents-editor-return-to-banner"),
      ).toBeTruthy()
    })
    expect(
      result.getByTestId("documents-editor-return-to-back"),
    ).toBeTruthy()
  })

  it("click 'Back to runtime editor' navigates to decoded return_to value", async () => {
    let capturedPath = ""
    const returnTo =
      "/bridgeable-admin/runtime-editor/?tenant=hopkins-fh&user=u1"
    const encoded = encodeURIComponent(returnTo)

    const result = render(
      <MemoryRouter
        initialEntries={[
          `/visual-editor/documents?return_to=${encoded}`,
        ]}
      >
        <Routes>
          <Route
            path="/visual-editor/documents"
            element={
              <>
                <LocationProbe onLocation={(p) => (capturedPath = p)} />
                <DocumentsEditorPage />
              </>
            }
          />
          <Route
            path="/bridgeable-admin/runtime-editor/"
            element={
              <LocationProbe onLocation={(p) => (capturedPath = p)} />
            }
          />
        </Routes>
      </MemoryRouter>,
    )
    const backBtn = await waitFor(() =>
      result.getByTestId("documents-editor-return-to-back"),
    )
    fireEvent.click(backBtn)
    await waitFor(() => {
      expect(capturedPath).toContain("/bridgeable-admin/runtime-editor")
      expect(capturedPath).toContain("tenant=hopkins-fh")
    })
  })
})
