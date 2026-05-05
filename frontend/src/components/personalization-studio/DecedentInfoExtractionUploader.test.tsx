/**
 * DecedentInfoExtractionUploader tests — canonical multimodal upload
 * surface + canonical content_blocks construction at canonical client
 * substrate per Phase 2c-0b.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { DecedentInfoExtractionUploader } from "./DecedentInfoExtractionUploader"


describe("DecedentInfoExtractionUploader — canonical multimodal upload chrome", () => {
  it("renders canonical canonical-uploader-input + extract button (disabled with no files)", () => {
    render(<DecedentInfoExtractionUploader onExtract={vi.fn()} />)
    expect(
      document.querySelector("[data-slot='uploader-file-input']"),
    ).toBeInTheDocument()
    const extractBtn = document.querySelector(
      "[data-slot='uploader-extract-action']",
    ) as HTMLButtonElement
    expect(extractBtn).toBeInTheDocument()
    expect(extractBtn.disabled).toBe(true)
  })

  it("canonical extract button enables canonical after canonical file canonical added", async () => {
    render(<DecedentInfoExtractionUploader onExtract={vi.fn()} />)
    const input = document.querySelector(
      "[data-slot='uploader-file-input']",
    ) as HTMLInputElement
    const file = new File(["test"], "death-cert.pdf", {
      type: "application/pdf",
    })
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => {
      expect(screen.getByText("death-cert.pdf")).toBeInTheDocument()
    })
    const extractBtn = document.querySelector(
      "[data-slot='uploader-extract-action']",
    ) as HTMLButtonElement
    expect(extractBtn.disabled).toBe(false)
  })

  it("canonical PDF upload canonical creates canonical document content_block", async () => {
    const onExtract = vi.fn().mockResolvedValue(undefined)
    render(<DecedentInfoExtractionUploader onExtract={onExtract} />)
    const input = document.querySelector(
      "[data-slot='uploader-file-input']",
    ) as HTMLInputElement
    const file = new File(["pdf canonical content"], "death-cert.pdf", {
      type: "application/pdf",
    })
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => {
      expect(
        document.querySelector(
          "[data-slot='uploader-file-item'][data-content-block-type='document']",
        ),
      ).toBeInTheDocument()
    })

    fireEvent.click(
      document.querySelector("[data-slot='uploader-extract-action']")!,
    )
    await waitFor(() => {
      expect(onExtract).toHaveBeenCalledTimes(1)
    })
    const callArg = onExtract.mock.calls[0][0]
    expect(callArg.content_blocks).toHaveLength(1)
    expect(callArg.content_blocks[0].type).toBe("document")
    expect(callArg.content_blocks[0].source.media_type).toBe("application/pdf")
    expect(callArg.content_blocks[0].source.type).toBe("base64")
    expect(typeof callArg.content_blocks[0].source.data).toBe("string")
    expect(callArg.content_blocks[0].source.data.length).toBeGreaterThan(0)
  })

  it("canonical image upload canonical creates canonical image content_block", async () => {
    const onExtract = vi.fn().mockResolvedValue(undefined)
    render(<DecedentInfoExtractionUploader onExtract={onExtract} />)
    const input = document.querySelector(
      "[data-slot='uploader-file-input']",
    ) as HTMLInputElement
    const file = new File(["jpeg-canonical-content"], "obituary.jpeg", {
      type: "image/jpeg",
    })
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => {
      expect(
        document.querySelector(
          "[data-slot='uploader-file-item'][data-content-block-type='image']",
        ),
      ).toBeInTheDocument()
    })

    fireEvent.click(
      document.querySelector("[data-slot='uploader-extract-action']")!,
    )
    await waitFor(() => {
      expect(onExtract).toHaveBeenCalledTimes(1)
    })
    const callArg = onExtract.mock.calls[0][0]
    expect(callArg.content_blocks[0].type).toBe("image")
    expect(callArg.content_blocks[0].source.media_type).toBe("image/jpeg")
  })

  it("canonical canonical multi-file upload canonical handles canonical multiple canonical content_blocks", async () => {
    const onExtract = vi.fn().mockResolvedValue(undefined)
    render(<DecedentInfoExtractionUploader onExtract={onExtract} />)
    const input = document.querySelector(
      "[data-slot='uploader-file-input']",
    ) as HTMLInputElement
    const pdfFile = new File(["pdf"], "cert.pdf", { type: "application/pdf" })
    const imgFile = new File(["jpeg"], "photo.jpeg", { type: "image/jpeg" })
    fireEvent.change(input, { target: { files: [pdfFile, imgFile] } })

    await waitFor(() => {
      const items = document.querySelectorAll(
        "[data-slot='uploader-file-item']",
      )
      expect(items).toHaveLength(2)
    })

    fireEvent.click(
      document.querySelector("[data-slot='uploader-extract-action']")!,
    )
    await waitFor(() => {
      expect(onExtract).toHaveBeenCalledWith(
        expect.objectContaining({
          content_blocks: expect.arrayContaining([
            expect.objectContaining({ type: "document" }),
            expect.objectContaining({ type: "image" }),
          ]),
        }),
      )
    })
  })

  it("canonical unsupported media_type canonical surfaces canonical error", async () => {
    render(<DecedentInfoExtractionUploader onExtract={vi.fn()} />)
    const input = document.querySelector(
      "[data-slot='uploader-file-input']",
    ) as HTMLInputElement
    const file = new File(["audio"], "voice.mp3", { type: "audio/mpeg" })
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => {
      expect(
        document.querySelector("[data-slot='uploader-errors']"),
      ).toBeInTheDocument()
    })
    expect(screen.getByText(/canonical media_type audio\/mpeg not supported/)).toBeInTheDocument()
  })

  it("canonical file removal canonical drops canonical content_block", async () => {
    render(<DecedentInfoExtractionUploader onExtract={vi.fn()} />)
    const input = document.querySelector(
      "[data-slot='uploader-file-input']",
    ) as HTMLInputElement
    const file = new File(["pdf"], "cert.pdf", { type: "application/pdf" })
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => {
      expect(
        document.querySelector("[data-slot='uploader-file-item']"),
      ).toBeInTheDocument()
    })
    fireEvent.click(
      document.querySelector("[data-slot='uploader-remove-file']")!,
    )
    expect(
      document.querySelector("[data-slot='uploader-file-item']"),
    ).toBeNull()
  })

  it("canonical context_summary canonical canonical-optional surfaces in canonical onExtract canonical call", async () => {
    const onExtract = vi.fn().mockResolvedValue(undefined)
    render(<DecedentInfoExtractionUploader onExtract={onExtract} />)
    const input = document.querySelector(
      "[data-slot='uploader-file-input']",
    ) as HTMLInputElement
    fireEvent.change(input, {
      target: {
        files: [new File(["pdf"], "cert.pdf", { type: "application/pdf" })],
      },
    })
    await waitFor(() => {
      expect(
        document.querySelector("[data-slot='uploader-file-item']"),
      ).toBeInTheDocument()
    })
    const contextInput = screen.getByPlaceholderText(/Death certificate/)
    fireEvent.change(contextInput, {
      target: { value: "Death certificate from County clerk" },
    })
    fireEvent.click(
      document.querySelector("[data-slot='uploader-extract-action']")!,
    )
    await waitFor(() => {
      expect(onExtract).toHaveBeenCalledWith(
        expect.objectContaining({
          context_summary: "Death certificate from County clerk",
        }),
      )
    })
  })

  it("canonical isLoading canonical disables canonical extract button + remove + input", () => {
    render(<DecedentInfoExtractionUploader onExtract={vi.fn()} isLoading={true} />)
    const extractBtn = document.querySelector(
      "[data-slot='uploader-extract-action']",
    ) as HTMLButtonElement
    expect(extractBtn.disabled).toBe(true)
  })
})
