/**
 * Phase R-6.2b — PortalFormPage.
 *
 * Public anonymous form rendering page. Route:
 *   /portal/:tenantSlug/intake/:slug
 *
 * On mount: GET /api/v1/intake-adapters/forms/{tenantSlug}/{slug}
 * Renders form fields via IntakeFieldDispatcher.
 * CAPTCHA widget below fields.
 * Submit: validates → POST /submit → navigates to /confirmation.
 *
 * Wrapped in PublicPortalLayout (PortalBrandProvider above in PortalApp).
 */

import { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { AlertCircle, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { CaptchaWidget } from "@/components/intake/CaptchaWidget"
import { IntakeFieldDispatcher } from "@/components/intake/IntakeFieldDispatcher"
import { PublicPortalLayout } from "@/components/portal/PublicPortalLayout"
import { PortalBrandProvider } from "@/contexts/portal-brand-context"
import { getFormConfig, submitForm } from "@/services/intake"
import type { IntakeFormConfig } from "@/types/intake"

type LoadState =
  | { kind: "loading" }
  | { kind: "ready"; config: IntakeFormConfig }
  | { kind: "error"; message: string }

function isEmail(value: string): boolean {
  // Loose RFC 5322-ish — UX validation only; backend canonical.
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

function PortalFormPageInner() {
  const { tenantSlug, slug } = useParams<{
    tenantSlug: string
    slug: string
  }>()
  const navigate = useNavigate()

  const [state, setState] = useState<LoadState>({ kind: "loading" })
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [captchaToken, setCaptchaToken] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => {
    if (!tenantSlug || !slug) {
      setState({ kind: "error", message: "Invalid form URL." })
      return
    }
    let cancelled = false
    setState({ kind: "loading" })
    void getFormConfig(tenantSlug, slug)
      .then((config) => {
        if (cancelled) return
        setState({ kind: "ready", config })
      })
      .catch((err) => {
        if (cancelled) return
        const e = err as { response?: { status?: number; data?: { detail?: string } } }
        const message =
          e?.response?.status === 404
            ? "Form not found."
            : e?.response?.data?.detail ?? "Failed to load form."
        setState({ kind: "error", message })
      })
    return () => {
      cancelled = true
    }
  }, [tenantSlug, slug])

  const handleFieldChange = useCallback(
    (fieldId: string) => (next: unknown) => {
      setValues((prev) => ({ ...prev, [fieldId]: next }))
      setErrors((prev) => {
        if (!prev[fieldId]) return prev
        const { [fieldId]: _removed, ...rest } = prev
        return rest
      })
    },
    [],
  )

  const config = state.kind === "ready" ? state.config : null
  const fields = useMemo(() => config?.form_schema.fields ?? [], [config])

  function validateAll(): Record<string, string> {
    const next: Record<string, string> = {}
    for (const field of fields) {
      if (field.type === "file_upload") continue // not rendered on form page
      const raw = values[field.id]
      const str = typeof raw === "string" ? raw.trim() : ""
      if (field.required && !str) {
        next[field.id] = "This field is required."
        continue
      }
      if (str && field.type === "email" && !isEmail(str)) {
        next[field.id] = "Please enter a valid email address."
      }
      if (
        str &&
        typeof field.max_length === "number" &&
        field.max_length > 0 &&
        str.length > field.max_length
      ) {
        next[field.id] = `Maximum ${field.max_length} characters.`
      }
    }
    return next
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!tenantSlug || !slug || !config) return
    const validationErrors = validateAll()
    setErrors(validationErrors)
    if (Object.keys(validationErrors).length > 0) return

    setSubmitting(true)
    setSubmitError(null)
    try {
      const result = await submitForm(tenantSlug, slug, values, captchaToken)
      navigate(
        `/portal/${tenantSlug}/intake/${slug}/confirmation`,
        { state: { successMessage: result.success_message } },
      )
    } catch (err) {
      const e = err as {
        response?: { status?: number; data?: { detail?: string | { message?: string } } }
      }
      const detail = e?.response?.data?.detail
      let message: string
      if (typeof detail === "string") {
        message = detail
      } else if (detail && typeof detail === "object" && "message" in detail) {
        message = (detail.message as string) ?? "Failed to submit."
      } else {
        message = "Failed to submit. Please try again."
      }
      setSubmitError(message)
    } finally {
      setSubmitting(false)
    }
  }

  if (state.kind === "loading") {
    return (
      <div
        className="mx-auto max-w-md py-12 text-center"
        data-testid="portal-form-loading"
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
        data-testid="portal-form-error"
      >
        <AlertCircle
          className="mx-auto mb-3 h-8 w-8 text-status-error"
          aria-hidden="true"
        />
        <h1 className="mb-2 text-h3 font-medium text-content-strong">
          Form not available
        </h1>
        <p className="text-body-sm text-content-muted">{state.message}</p>
      </div>
    )
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-auto max-w-md"
      data-testid="portal-form-page"
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

      {fields.map((field) =>
        field.type === "file_upload" ? null : (
          <IntakeFieldDispatcher
            key={field.id}
            config={field}
            value={values[field.id]}
            onChange={handleFieldChange(field.id)}
            error={errors[field.id]}
          />
        ),
      )}

      {config!.form_schema.captcha_required ? (
        <CaptchaWidget onTokenChange={setCaptchaToken} />
      ) : null}

      {submitError ? (
        <div
          className="mb-3 rounded border border-status-error bg-status-error-muted p-3 text-body-sm text-status-error"
          role="alert"
          data-testid="portal-form-submit-error"
        >
          {submitError}
        </div>
      ) : null}

      <Button
        type="submit"
        disabled={submitting}
        className="w-full min-h-11"
        data-testid="portal-form-submit"
      >
        {submitting ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Submitting…
          </>
        ) : (
          "Submit"
        )}
      </Button>
    </form>
  )
}

export default function PortalFormPage() {
  const { tenantSlug } = useParams<{ tenantSlug: string }>()
  if (!tenantSlug) return null
  return (
    <PortalBrandProvider slug={tenantSlug}>
      <PublicPortalLayout>
        <PortalFormPageInner />
      </PublicPortalLayout>
    </PortalBrandProvider>
  )
}
