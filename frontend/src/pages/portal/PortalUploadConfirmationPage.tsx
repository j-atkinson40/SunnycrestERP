/**
 * Phase R-6.2b — File upload confirmation page.
 *
 * Route: /portal/:tenantSlug/upload/:slug/confirmation
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
    "Your file has been uploaded successfully."

  return (
    <div
      className="mx-auto max-w-md py-12 text-center"
      data-testid="portal-upload-confirmation"
    >
      <CheckCircle2
        className="mx-auto mb-4 h-12 w-12 text-status-success"
        aria-hidden="true"
      />
      <h1 className="mb-3 text-h2 font-medium text-content-strong">
        Upload received
      </h1>
      <p className="mb-2 text-body text-content-base">{successMessage}</p>
      {branding?.display_name ? (
        <p className="text-body-sm text-content-muted">
          {branding.display_name} will follow up if anything else is needed.
        </p>
      ) : null}
    </div>
  )
}

export default function PortalUploadConfirmationPage() {
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
