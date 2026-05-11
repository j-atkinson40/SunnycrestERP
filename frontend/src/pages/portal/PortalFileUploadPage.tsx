/**
 * Phase R-6.2b — PortalFileUploadPage.
 *
 * Public anonymous file upload page. Route:
 *   /portal/:tenantSlug/upload/:slug
 *
 * Flow:
 *   1. GET /uploads/{tenantSlug}/{slug} for config
 *   2. Render uploader metadata fields + FileUploadField
 *   3. CAPTCHA widget
 *   4. On submit: per file in sequence:
 *      a. POST /presign  (carries captcha_token)
 *      b. XHR PUT bytes to R2 (with progress)
 *      c. POST /complete (carries metadata + captcha_token)
 *   5. Navigate to /confirmation
 */

import { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { AlertCircle, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { CaptchaWidget } from "@/components/intake/CaptchaWidget"
import { FileUploadField } from "@/components/intake/fields/FileUploadField"
import { IntakeFieldDispatcher } from "@/components/intake/IntakeFieldDispatcher"
import { PublicPortalLayout } from "@/components/portal/PublicPortalLayout"
import { PortalBrandProvider } from "@/contexts/portal-brand-context"
import {
  completeUpload,
  getUploadConfig,
  presignUpload,
  uploadToR2,
} from "@/services/intake"
import type { IntakeFileConfig } from "@/types/intake"

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; config: IntakeFileConfig }
  | { kind: "error"; message: string }

function isEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

function PortalFileUploadPageInner() {
  const { tenantSlug, slug } = useParams<{
    tenantSlug: string
    slug: string
  }>()
  const navigate = useNavigate()

  const [state, setState] = useState<LoadState>({ kind: "loading" })
  const [metadata, setMetadata] = useState<Record<string, unknown>>({})
  const [files, setFiles] = useState<File[]>([])
  const [metadataErrors, setMetadataErrors] = useState<Record<string, string>>(
    {},
  )
  const [fileError, setFileError] = useState<string | undefined>(undefined)
  const [captchaToken, setCaptchaToken] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState<number>(0)
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => {
    if (!tenantSlug || !slug) {
      setState({ kind: "error", message: "Invalid upload URL." })
      return
    }
    let cancelled = false
    setState({ kind: "loading" })
    void getUploadConfig(tenantSlug, slug)
      .then((config) => {
        if (cancelled) return
        setState({ kind: "ready", config })
      })
      .catch((err) => {
        if (cancelled) return
        const e = err as {
          response?: { status?: number; data?: { detail?: string } }
        }
        const message =
          e?.response?.status === 404
            ? "Upload not found."
            : e?.response?.data?.detail ?? "Failed to load upload."
        setState({ kind: "error", message })
      })
    return () => {
      cancelled = true
    }
  }, [tenantSlug, slug])

  const config = state.kind === "ready" ? state.config : null
  const fields = useMemo(
    () => config?.metadata_schema.fields ?? [],
    [config],
  )

  const handleFieldChange = useCallback(
    (fieldId: string) => (next: unknown) => {
      setMetadata((prev) => ({ ...prev, [fieldId]: next }))
      setMetadataErrors((prev) => {
        if (!prev[fieldId]) return prev
        const { [fieldId]: _removed, ...rest } = prev
        return rest
      })
    },
    [],
  )

  function validateMetadata(): Record<string, string> {
    const next: Record<string, string> = {}
    for (const field of fields) {
      if (field.type === "file_upload") continue
      const raw = metadata[field.id]
      const str = typeof raw === "string" ? raw.trim() : ""
      if (field.required && !str) {
        next[field.id] = "This field is required."
        continue
      }
      if (str && field.type === "email" && !isEmail(str)) {
        next[field.id] = "Please enter a valid email address."
      }
    }
    return next
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!tenantSlug || !slug || !config) return

    const errs = validateMetadata()
    setMetadataErrors(errs)
    if (Object.keys(errs).length > 0) return
    if (files.length === 0) {
      setFileError("Please choose at least one file.")
      return
    }
    setFileError(undefined)

    setUploading(true)
    setProgress(0)
    setSubmitError(null)
    try {
      let cumulativeLoaded = 0
      const totalBytes = files.reduce((acc, f) => acc + f.size, 0)
      for (const file of files) {
        const signed = await presignUpload(
          tenantSlug,
          slug,
          {
            original_filename: file.name,
            content_type: file.type || "application/octet-stream",
            size_bytes: file.size,
          },
          captchaToken,
        )
        await uploadToR2(signed, file, (loaded, _total) => {
          const aggregate = (cumulativeLoaded + loaded) / Math.max(totalBytes, 1)
          setProgress(Math.min(aggregate, 1))
        })
        cumulativeLoaded += file.size
        const r2Key = signed.r2_key ?? signed.key ?? ""
        await completeUpload(tenantSlug, slug, {
          r2_key: r2Key,
          original_filename: file.name,
          content_type: file.type || "application/octet-stream",
          size_bytes: file.size,
          uploader_metadata: metadata,
          captcha_token: captchaToken,
        })
      }
      navigate(`/portal/${tenantSlug}/upload/${slug}/confirmation`, {
        state: { successMessage: config.success_message },
      })
    } catch (err) {
      const e = err as {
        message?: string
        response?: { data?: { detail?: string | { message?: string } } }
      }
      const detail = e?.response?.data?.detail
      let message: string
      if (typeof detail === "string") {
        message = detail
      } else if (detail && typeof detail === "object" && "message" in detail) {
        message = (detail.message as string) ?? e?.message ?? "Upload failed."
      } else {
        message = e?.message ?? "Upload failed. Please try again."
      }
      setSubmitError(message)
    } finally {
      setUploading(false)
    }
  }

  if (state.kind === "loading") {
    return (
      <div
        className="mx-auto max-w-md py-12 text-center"
        data-testid="portal-upload-loading"
      >
        <Loader2
          className="mx-auto mb-3 h-6 w-6 animate-spin text-content-muted"
          aria-hidden="true"
        />
        <p className="text-body-sm text-content-muted">Loading…</p>
      </div>
    )
  }

  if (state.kind === "error") {
    return (
      <div
        className="mx-auto max-w-md py-12 text-center"
        data-testid="portal-upload-error"
      >
        <AlertCircle
          className="mx-auto mb-3 h-8 w-8 text-status-error"
          aria-hidden="true"
        />
        <h1 className="mb-2 text-h3 font-medium text-content-strong">
          Upload not available
        </h1>
        <p className="text-body-sm text-content-muted">{state.message}</p>
      </div>
    )
  }

  const fileFieldConfig = {
    id: "file",
    type: "file_upload" as const,
    label: "File",
    required: true,
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-auto max-w-md"
      data-testid="portal-upload-page"
      noValidate
    >
      <h1 className="mb-2 text-h2 font-medium text-content-strong">
        {config!.name}
      </h1>
      {config!.description ? (
        <p className="mb-6 text-body-sm text-content-muted">
          {config!.description}
        </p>
      ) : (
        <div className="mb-6" />
      )}

      {fields.map((field) => (
        <IntakeFieldDispatcher
          key={field.id}
          config={field}
          value={metadata[field.id]}
          onChange={handleFieldChange(field.id)}
          error={metadataErrors[field.id]}
        />
      ))}

      <FileUploadField
        config={fileFieldConfig}
        value={files}
        onChange={(next) => setFiles(Array.isArray(next) ? (next as File[]) : [])}
        error={fileError}
        uploadConfig={{
          allowed_content_types: config!.allowed_content_types,
          max_file_size_bytes: config!.max_file_size_bytes,
          max_file_count: config!.max_file_count,
        }}
        uploadProgress={uploading ? progress : null}
        isUploading={uploading}
      />

      {config!.metadata_schema.captcha_required ? (
        <CaptchaWidget onTokenChange={setCaptchaToken} />
      ) : null}

      {submitError ? (
        <div
          className="mb-3 rounded border border-status-error bg-status-error-muted p-3 text-body-sm text-status-error"
          role="alert"
          data-testid="portal-upload-submit-error"
        >
          {submitError}
        </div>
      ) : null}

      <Button
        type="submit"
        disabled={uploading || files.length === 0}
        className="w-full min-h-11"
        data-testid="portal-upload-submit"
      >
        {uploading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Uploading…
          </>
        ) : (
          "Upload"
        )}
      </Button>
    </form>
  )
}

export default function PortalFileUploadPage() {
  const { tenantSlug } = useParams<{ tenantSlug: string }>()
  if (!tenantSlug) return null
  return (
    <PortalBrandProvider slug={tenantSlug}>
      <PublicPortalLayout>
        <PortalFileUploadPageInner />
      </PublicPortalLayout>
    </PortalBrandProvider>
  )
}
