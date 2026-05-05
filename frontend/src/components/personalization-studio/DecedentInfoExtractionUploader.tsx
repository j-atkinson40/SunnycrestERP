/**
 * DecedentInfoExtractionUploader — canonical multimodal upload surface
 * per Phase 1C canonical AI-extraction-review pipeline + canonical
 * Phase 2c-0b multimodal content_blocks substrate.
 *
 * **Canonical operator-uploaded source materials canonical**:
 *   - PDFs (canonical media_type: application/pdf)
 *   - Images (canonical media_types: image/jpeg, image/png, image/gif,
 *     image/webp per canonical Anthropic-supported set)
 *
 * **Canonical multimodal content_blocks construction at canonical
 * client substrate**: each canonical operator-uploaded file converts
 * to canonical Anthropic content_block shape:
 *   {"type": "image" | "document",
 *    "source": {"type": "base64", "media_type": ..., "data": ...}}
 *
 * **Canonical anti-pattern guard explicit**: §3.26.11.12.16 Anti-pattern
 * 12 (parallel architectures for differently-sourced Generation Focus
 * inputs rejected): canonical multimodal content_blocks substrate
 * canonical at canonical extraction adapter category per §3.26.11.12.20.
 * Single canonical architecture for canonical operator-uploaded source
 * materials.
 */

import { Loader2, Upload, X } from "lucide-react"
import { useCallback, useState } from "react"
import type { ChangeEvent } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import type { ContentBlock } from "@/types/personalization-studio"


// Canonical Anthropic-supported image media_types per
// `_validate_content_blocks` _ALLOWED_IMAGE_MEDIA_TYPES.
const ALLOWED_IMAGE_MIME = ["image/jpeg", "image/png", "image/gif", "image/webp"]
// Canonical Anthropic-supported document media_types.
const ALLOWED_DOCUMENT_MIME = ["application/pdf"]
const ALLOWED_MIME = [...ALLOWED_IMAGE_MIME, ...ALLOWED_DOCUMENT_MIME]


export interface UploadedSourceFile {
  name: string
  size: number
  contentBlock: ContentBlock
}


export interface DecedentInfoExtractionUploaderProps {
  /** Canonical operator-initiated extraction request handler from
   *  canonical useAIExtractionReview hook. */
  onExtract: (params: {
    content_blocks: ContentBlock[]
    context_summary?: string
  }) => Promise<void>
  /** Canonical loading flag from canonical useAIExtractionReview hook. */
  isLoading?: boolean
}


export function DecedentInfoExtractionUploader({
  onExtract,
  isLoading = false,
}: DecedentInfoExtractionUploaderProps) {
  const [files, setFiles] = useState<UploadedSourceFile[]>([])
  const [contextSummary, setContextSummary] = useState("")
  const [errors, setErrors] = useState<string[]>([])
  const [isProcessingUpload, setIsProcessingUpload] = useState(false)

  const handleFileChange = useCallback(
    async (e: ChangeEvent<HTMLInputElement>) => {
      const fileList = e.target.files
      if (!fileList) return
      setErrors([])
      setIsProcessingUpload(true)
      try {
        const newFiles: UploadedSourceFile[] = []
        const newErrors: string[] = []
        for (const file of Array.from(fileList)) {
          if (!ALLOWED_MIME.includes(file.type)) {
            newErrors.push(
              `${file.name}: canonical media_type ${file.type} not supported. ` +
                `Canonical accepted: PDF, JPEG, PNG, GIF, WEBP.`,
            )
            continue
          }
          try {
            const base64 = await fileToBase64(file)
            const contentBlock: ContentBlock = {
              type: ALLOWED_IMAGE_MIME.includes(file.type) ? "image" : "document",
              source: {
                type: "base64",
                media_type: file.type,
                data: base64,
              },
            }
            newFiles.push({
              name: file.name,
              size: file.size,
              contentBlock,
            })
          } catch (err) {
            newErrors.push(
              `${file.name}: failed to read file (${
                (err as Error).message || "unknown error"
              })`,
            )
          }
        }
        setFiles((prev) => [...prev, ...newFiles])
        if (newErrors.length > 0) setErrors(newErrors)
      } finally {
        setIsProcessingUpload(false)
        // Canonical input reset — canonical operator can re-upload same
        // file canonical.
        e.target.value = ""
      }
    },
    [],
  )

  const handleRemoveFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }, [])

  const handleExtract = useCallback(async () => {
    if (files.length === 0) return
    await onExtract({
      content_blocks: files.map((f) => f.contentBlock),
      context_summary: contextSummary || undefined,
    })
  }, [files, contextSummary, onExtract])

  return (
    <div
      data-slot="decedent-info-extraction-uploader"
      className={cn(
        "rounded-md border border-border-subtle bg-surface-raised p-4",
        "flex flex-col gap-3",
      )}
    >
      <div className="flex items-center justify-between">
        <div
          data-slot="uploader-title"
          className="text-caption font-medium uppercase tracking-wider text-content-muted"
        >
          Source materials — death certificate / obituary / photos
        </div>
      </div>

      {/* Canonical file input — canonical multi-file canonical accepted. */}
      <label
        data-slot="uploader-input-label"
        className={cn(
          "flex cursor-pointer items-center justify-center gap-2",
          "rounded-md border-2 border-dashed border-border-base",
          "bg-surface-base px-4 py-6 transition-colors",
          "hover:bg-surface-elevated",
        )}
      >
        <Upload className="h-4 w-4 text-content-muted" />
        <span className="text-body-sm text-content-strong">
          {isProcessingUpload
            ? "Reading files…"
            : "Click to upload PDFs or images"}
        </span>
        <input
          type="file"
          accept={ALLOWED_MIME.join(",")}
          multiple
          onChange={handleFileChange}
          className="hidden"
          disabled={isProcessingUpload || isLoading}
          data-slot="uploader-file-input"
        />
      </label>

      {/* Canonical errors */}
      {errors.length > 0 && (
        <div
          data-slot="uploader-errors"
          className="flex flex-col gap-1 rounded-sm bg-status-error-muted px-3 py-2"
        >
          {errors.map((err, i) => (
            <div key={i} className="text-caption text-status-error">
              {err}
            </div>
          ))}
        </div>
      )}

      {/* Canonical uploaded file list */}
      {files.length > 0 && (
        <div
          data-slot="uploader-file-list"
          className="flex flex-col gap-1"
        >
          {files.map((f, i) => (
            <div
              key={`${f.name}-${i}`}
              data-slot="uploader-file-item"
              data-content-block-type={f.contentBlock.type}
              className={cn(
                "flex items-center justify-between gap-2",
                "rounded-sm border border-border-subtle bg-surface-elevated px-3 py-2",
              )}
            >
              <div className="flex flex-col">
                <span className="text-body-sm font-medium text-content-strong">
                  {f.name}
                </span>
                <span className="text-caption text-content-muted">
                  {f.contentBlock.type} · {(f.size / 1024).toFixed(1)} KB
                </span>
              </div>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => handleRemoveFile(i)}
                disabled={isLoading}
                data-slot="uploader-remove-file"
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          ))}
        </div>
      )}

      {/* Canonical context summary input — optional canonical operator-
          supplied text context. */}
      <label className="flex flex-col gap-1">
        <span className="text-caption text-content-muted">
          Context (optional) — what are these source materials?
        </span>
        <Input
          value={contextSummary}
          onChange={(e: ChangeEvent<HTMLInputElement>) =>
            setContextSummary(e.target.value)
          }
          placeholder="e.g., Death certificate from County clerk; obituary from local newspaper"
          disabled={isLoading}
        />
      </label>

      {/* Canonical extract action — canonical operator agency canonical
          per §3.26.11.12.16 Anti-pattern 1. */}
      <div className="flex justify-end">
        <Button
          type="button"
          variant="default"
          onClick={handleExtract}
          disabled={files.length === 0 || isLoading}
          data-slot="uploader-extract-action"
        >
          {isLoading ? (
            <>
              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
              Extracting…
            </>
          ) : (
            <>Extract decedent info</>
          )}
        </Button>
      </div>
    </div>
  )
}


/** Canonical file-to-base64 helper. Returns canonical base64 string
 *  (canonical no `data:...;base64,` prefix per canonical Anthropic
 *  content_block.source.data shape). */
async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result
      if (typeof result !== "string") {
        reject(new Error("FileReader returned non-string result"))
        return
      }
      // Strip canonical data URI prefix per canonical content_block
      // source.data shape.
      const idx = result.indexOf("base64,")
      resolve(idx >= 0 ? result.slice(idx + "base64,".length) : result)
    }
    reader.onerror = () => reject(reader.error || new Error("FileReader error"))
    reader.readAsDataURL(file)
  })
}
