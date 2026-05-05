/**
 * PtrConsentErrorBanner — Phase 1F FH-director-side PTR consent error
 * chrome at canonical `_handle_approve` flow.
 *
 * Per Phase 1F build prompt: when canonical Phase 1F post-commit
 * DocumentShare grant fire fails on canonical PTR consent precondition
 * (4 failure modes: ptr_missing | consent_default |
 * consent_pending_outbound | consent_pending_inbound), the canonical
 * Phase 1E commit response surfaces canonical
 * `ShareDispatchResponse` payload at the `share_dispatch` field. This
 * component renders that payload as canonical FH-director-side error
 * chrome with canonical "Request consent" affordance linking to the
 * canonical settings page consuming r75 service
 * `request_personalization_studio_consent`.
 *
 * Component is content-only — renders inside whatever surface mounts
 * it (canonical Personalization Studio canvas page; canonical
 * notification detail page; canonical dashboard alert surface).
 *
 * **Canonical anti-pattern guards explicit at FE substrate**:
 *   - §3.26.11.12.16 Anti-pattern 1 (operator agency) — canonical
 *     "Request consent" affordance is canonical FH-director-initiated;
 *     no auto-request on error surface.
 */

import { ShieldAlert, ExternalLink } from "lucide-react"
import { Link } from "react-router-dom"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { buttonVariants } from "@/components/ui/button"
import type { ShareDispatchResponse } from "@/types/personalization-studio"

interface Props {
  /** Canonical Phase 1E commit response `share_dispatch` payload —
   *  null when canonical grant fire succeeded; renders the canonical
   *  error chrome only on canonical failure outcomes. */
  shareDispatch: ShareDispatchResponse | null | undefined
}

const CONSENT_SETTINGS_ROUTE =
  "/settings/personalization-studio/cross-tenant-sharing-consent"

const CANONICAL_FAILURE_OUTCOMES = new Set([
  "ptr_missing",
  "consent_default",
  "consent_pending_outbound",
  "consent_pending_inbound",
])

const ACTION_LABEL_BY_OUTCOME: Record<string, string> = {
  consent_default: "Request consent",
  consent_pending_outbound: "Open consent settings",
  consent_pending_inbound: "Review pending consent request",
  ptr_missing: "Connect manufacturer",
}

export function PtrConsentErrorBanner({ shareDispatch }: Props) {
  if (
    shareDispatch == null ||
    !CANONICAL_FAILURE_OUTCOMES.has(shareDispatch.outcome)
  ) {
    return null
  }

  const errorDetail =
    shareDispatch.error_detail ??
    "Approved memorial design could not be shared with the manufacturer."

  // Canonical "Request consent" affordance routes to canonical settings
  // page per r75 canon (`/settings/personalization-studio/cross-tenant-
  // sharing-consent`); per-outcome label varies per canonical action
  // semantics (request vs review vs accept vs connect).
  //
  // For `ptr_missing`: deep-link to canonical platform tenant
  // relationship management page (canonical /settings/platform-tenant-
  // relationships per existing canonical platform admin canon).
  const isMissingPtr = shareDispatch.outcome === "ptr_missing"
  const linkRoute = isMissingPtr
    ? "/settings/platform-tenant-relationships"
    : CONSENT_SETTINGS_ROUTE
  const actionLabel =
    ACTION_LABEL_BY_OUTCOME[shareDispatch.outcome] ?? "Open settings"

  return (
    <Alert
      variant="warning"
      data-testid="ptr-consent-error-banner"
      data-outcome={shareDispatch.outcome}
    >
      <ShieldAlert className="h-4 w-4" aria-hidden />
      <AlertTitle>
        Approved design not yet shared with manufacturer
      </AlertTitle>
      <AlertDescription>
        <p data-testid="ptr-consent-error-detail">{errorDetail}</p>
        <p className="mt-3">
          <Link
            to={linkRoute}
            data-testid="ptr-consent-action-link"
            className={buttonVariants({
              variant: "outline",
              size: "sm",
            })}
          >
            {actionLabel}
            <ExternalLink className="ml-1.5 h-3 w-3" aria-hidden />
          </Link>
        </p>
      </AlertDescription>
    </Alert>
  )
}
