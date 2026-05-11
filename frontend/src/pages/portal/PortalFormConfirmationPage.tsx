/**
 * Phase R-6.2b — Form submission confirmation page.
 *
 * Route: /portal/:tenantSlug/intake/:slug/confirmation
 *
 * Generic tenant-branded thank-you. Reads `successMessage` from
 * `useLocation().state` when present (passed via navigate). Falls
 * back to canonical default ("Thank you. We've received your
 * submission.") when state is missing (deep-link tolerant).
 */

import { CheckCircle2 } from "lucide-react"
import { useLocation, useParams } from "react-router-dom"

import { PublicPortalLayout } from "@/components/portal/PublicPortalLayout"
import { PortalBrandProvider, usePortalBrand } from "@/contexts/portal-brand-context"

interface LocationState {
  successMessage?: string | null
}

function ConfirmationInner() {
  const location = useLocation()
  const { branding } = usePortalBrand()
  const state = (location.state as LocationState | null) ?? null
  const successMessage =
    state?.successMessage ??
    "Thank you. We've received your submission."

  return (
    <div
      className="mx-auto max-w-md py-12 text-center"
      data-testid="portal-form-confirmation"
    >
      <CheckCircle2
        className="mx-auto mb-4 h-12 w-12 text-status-success"
        aria-hidden="true"
      />
      <h1 className="mb-3 text-h2 font-medium text-content-strong">
        Submission received
      </h1>
      <p className="mb-2 text-body text-content-base">{successMessage}</p>
      {branding?.display_name ? (
        <p className="text-body-sm text-content-muted">
          {branding.display_name} will be in touch.
        </p>
      ) : null}
    </div>
  )
}

export default function PortalFormConfirmationPage() {
  const { tenantSlug } = useParams<{ tenantSlug: string }>()
  if (!tenantSlug) return null
  return (
    <PortalBrandProvider slug={tenantSlug}>
      <PublicPortalLayout>
        <ConfirmationInner />
      </PublicPortalLayout>
    </PortalBrandProvider>
  )
}
