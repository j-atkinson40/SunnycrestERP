/**
 * Phase R-6.2b — intake field primitive coverage.
 *
 * Covers 7 field primitives (Text, Textarea, Email, Phone, Date,
 * Select, FileUpload). Each gets render + interaction tests.
 */

import { render, screen, fireEvent } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import type { IntakeFieldConfig } from "@/types/intake"

import { DateField } from "./DateField"
import { EmailField } from "./EmailField"
import { FileUploadField } from "./FileUploadField"
import { PhoneField } from "./PhoneField"
import { SelectField } from "./SelectField"
import { TextField } from "./TextField"
import { TextareaField } from "./TextareaField"

const baseTextConfig: IntakeFieldConfig = {
  id: "f1",
  type: "text",
  label: "Test field",
  required: true,
  max_length: 100,
}

describe("TextField", () => {
  it("renders label + asterisk for required", () => {
    render(
      <TextField config={baseTextConfig} value="" onChange={() => {}} />,
    )
    expect(screen.getByText("Test field")).toBeInTheDocument()
    expect(screen.getByTestId("intake-field-required-f1")).toBeInTheDocument()
  })

  it("calls onChange on input", () => {
    const onChange = vi.fn()
    render(
      <TextField config={baseTextConfig} value="" onChange={onChange} />,
    )
    fireEvent.change(screen.getByTestId("intake-input-f1"), {
      target: { value: "Hello" },
    })
    expect(onChange).toHaveBeenCalledWith("Hello")
  })

  it("renders error message when error prop set", () => {
    render(
      <TextField
        config={baseTextConfig}
        value=""
        onChange={() => {}}
        error="Required"
      />,
    )
    expect(screen.getByText("Required")).toBeInTheDocument()
  })
})

describe("TextareaField", () => {
  const cfg: IntakeFieldConfig = {
    id: "ta",
    type: "textarea",
    label: "Notes",
    max_length: 100,
  }
  it("renders character counter when max_length set", () => {
    render(
      <TextareaField config={cfg} value="abc" onChange={() => {}} />,
    )
    expect(screen.getByTestId("intake-counter-ta")).toHaveTextContent(
      "3 / 100",
    )
  })

  it("calls onChange on text input", () => {
    const onChange = vi.fn()
    render(<TextareaField config={cfg} value="" onChange={onChange} />)
    fireEvent.change(screen.getByTestId("intake-textarea-ta"), {
      target: { value: "longer" },
    })
    expect(onChange).toHaveBeenCalledWith("longer")
  })
})

describe("EmailField", () => {
  const cfg: IntakeFieldConfig = {
    id: "em",
    type: "email",
    label: "Email",
    required: true,
  }
  it("renders type=email + autoComplete=email", () => {
    render(<EmailField config={cfg} value="" onChange={() => {}} />)
    const input = screen.getByTestId("intake-input-em")
    expect(input).toHaveAttribute("type", "email")
    expect(input).toHaveAttribute("autocomplete", "email")
  })

  it("calls onChange on input", () => {
    const onChange = vi.fn()
    render(<EmailField config={cfg} value="" onChange={onChange} />)
    fireEvent.change(screen.getByTestId("intake-input-em"), {
      target: { value: "a@b.com" },
    })
    expect(onChange).toHaveBeenCalledWith("a@b.com")
  })
})

describe("PhoneField", () => {
  const cfg: IntakeFieldConfig = {
    id: "ph",
    type: "phone",
    label: "Phone",
  }
  it("renders type=tel + inputMode=tel", () => {
    render(<PhoneField config={cfg} value="" onChange={() => {}} />)
    const input = screen.getByTestId("intake-input-ph")
    expect(input).toHaveAttribute("type", "tel")
    expect(input).toHaveAttribute("inputmode", "tel")
  })
})

describe("DateField", () => {
  const cfg: IntakeFieldConfig = {
    id: "dt",
    type: "date",
    label: "Date",
  }
  it("renders type=date input", () => {
    render(<DateField config={cfg} value="2026-01-15" onChange={() => {}} />)
    const input = screen.getByTestId("intake-input-dt") as HTMLInputElement
    expect(input.type).toBe("date")
    expect(input.value).toBe("2026-01-15")
  })

  it("calls onChange with new date", () => {
    const onChange = vi.fn()
    render(<DateField config={cfg} value="" onChange={onChange} />)
    fireEvent.change(screen.getByTestId("intake-input-dt"), {
      target: { value: "2026-02-20" },
    })
    expect(onChange).toHaveBeenCalledWith("2026-02-20")
  })
})

describe("SelectField", () => {
  const cfg: IntakeFieldConfig = {
    id: "sel",
    type: "select",
    label: "Choose",
    options: [
      { value: "a", label: "Apple" },
      { value: "b", label: "Banana" },
    ],
  }
  it("renders options", () => {
    render(<SelectField config={cfg} value="" onChange={() => {}} />)
    expect(screen.getByText("Apple")).toBeInTheDocument()
    expect(screen.getByText("Banana")).toBeInTheDocument()
  })

  it("calls onChange with selected value", () => {
    const onChange = vi.fn()
    render(<SelectField config={cfg} value="" onChange={onChange} />)
    fireEvent.change(screen.getByTestId("intake-select-sel"), {
      target: { value: "b" },
    })
    expect(onChange).toHaveBeenCalledWith("b")
  })
})

describe("FileUploadField", () => {
  const cfg: IntakeFieldConfig = {
    id: "fu",
    type: "file_upload",
    label: "File",
    required: true,
  }
  const uploadCfg = {
    allowed_content_types: ["application/pdf"],
    max_file_size_bytes: 1_000_000,
    max_file_count: 1,
  }

  it("renders dropzone (with hidden CSS class for capability detection)", () => {
    render(
      <FileUploadField
        config={cfg}
        value={[]}
        onChange={() => {}}
        uploadConfig={uploadCfg}
      />,
    )
    const dropzone = screen.getByTestId("intake-dropzone-fu")
    expect(dropzone.className).toContain("intake-file-upload-drop-zone")
    expect(dropzone.className).toContain("hidden")
    expect(dropzone.className).toContain("hover:hover")
  })

  it("renders touch-friendly file picker button", () => {
    render(
      <FileUploadField
        config={cfg}
        value={[]}
        onChange={() => {}}
        uploadConfig={uploadCfg}
      />,
    )
    expect(
      screen.getByTestId("intake-file-picker-touch-fu"),
    ).toBeInTheDocument()
  })

  it("validates file size; over-cap files rejected", () => {
    const onChange = vi.fn()
    render(
      <FileUploadField
        config={cfg}
        value={[]}
        onChange={onChange}
        uploadConfig={uploadCfg}
      />,
    )
    const input = screen.getByTestId("intake-file-input-fu") as HTMLInputElement
    const bigFile = new File(["x".repeat(2_000_000)], "big.pdf", {
      type: "application/pdf",
    })
    Object.defineProperty(input, "files", { value: [bigFile] })
    fireEvent.change(input)
    expect(onChange).not.toHaveBeenCalled()
    expect(screen.getByText(/exceeds max size/i)).toBeInTheDocument()
  })

  it("validates content_type; disallowed types rejected", () => {
    const onChange = vi.fn()
    render(
      <FileUploadField
        config={cfg}
        value={[]}
        onChange={onChange}
        uploadConfig={uploadCfg}
      />,
    )
    const input = screen.getByTestId("intake-file-input-fu") as HTMLInputElement
    const exeFile = new File(["x"], "bad.exe", {
      type: "application/x-msdownload",
    })
    Object.defineProperty(input, "files", { value: [exeFile] })
    fireEvent.change(input)
    expect(onChange).not.toHaveBeenCalled()
    expect(screen.getByText(/is not allowed/i)).toBeInTheDocument()
  })

  it("accepts valid file + calls onChange with array", () => {
    const onChange = vi.fn()
    render(
      <FileUploadField
        config={cfg}
        value={[]}
        onChange={onChange}
        uploadConfig={uploadCfg}
      />,
    )
    const input = screen.getByTestId("intake-file-input-fu") as HTMLInputElement
    const goodFile = new File(["x"], "doc.pdf", { type: "application/pdf" })
    Object.defineProperty(input, "files", { value: [goodFile] })
    fireEvent.change(input)
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(Array.isArray(onChange.mock.calls[0][0])).toBe(true)
    expect((onChange.mock.calls[0][0] as File[])[0].name).toBe("doc.pdf")
  })

  it("renders progress bar when isUploading + uploadProgress set", () => {
    render(
      <FileUploadField
        config={cfg}
        value={[]}
        onChange={() => {}}
        uploadConfig={uploadCfg}
        isUploading
        uploadProgress={0.5}
      />,
    )
    expect(
      screen.getByTestId("intake-upload-progress-fu"),
    ).toBeInTheDocument()
    expect(screen.getByText(/50%/)).toBeInTheDocument()
  })
})
