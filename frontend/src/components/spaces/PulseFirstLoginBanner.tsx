/**
 * Pulse first-login banner — Phase W-4a Commit 5.
 *
 * Surfaces an inline banner at the top of PulseSurface when the
 * user hasn't completed the operator-onboarding flow yet (per D4).
 * "Set your work areas → personalized Pulse" with a link to
 * /onboarding/operator-profile.
 *
 * Persistence: uses the canonical `useOnboardingTouch` hook
 * (`pulse_first_login_banner` key) so dismissal is server-side +
 * cross-device.
 *
 * Suppression conditions (banner does NOT render):
 *   1. composition.metadata.vertical_default_applied === false
 *      (user has work_areas set — banner is moot)
 *   2. The onboarding-touch flag is already dismissed (user
 *      dismissed the banner before)
 *
 * NOT a tooltip — this is an inline banner. The OnboardingTouch
 * primitive is a floating tooltip; we share the persistence hook
 * but render inline at the top of Pulse.
 */

import { Link } from "react-router-dom"
import { Sparkles, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useOnboardingTouch } from "@/hooks/useOnboardingTouch"
import { cn } from "@/lib/utils"


export interface PulseFirstLoginBannerProps {
  /** True when the composition fell back to vertical-default
   *  (user.work_areas is empty/null). Banner only renders when
   *  this is true. */
  verticalDefaultApplied: boolean
}


export function PulseFirstLoginBanner({
  verticalDefaultApplied,
}: PulseFirstLoginBannerProps) {
  const { shouldShow, dismiss } = useOnboardingTouch(
    "pulse_first_login_banner",
  )

  // Only render when both:
  //   1. composition is on vertical default (user hasn't onboarded), AND
  //   2. the user hasn't dismissed the banner before (touch flag).
  if (!verticalDefaultApplied || !shouldShow) return null

  return (
    <div
      role="status"
      data-slot="pulse-first-login-banner"
      className={cn(
        "flex items-center gap-3 px-4 py-3 mb-4",
        "rounded-[2px] border border-accent/30 bg-accent-subtle",
      )}
    >
      <Sparkles
        className="h-4 w-4 text-accent flex-shrink-0"
        aria-hidden
      />
      <div className="flex-1 min-w-0">
        <p className="text-body-sm font-medium text-content-strong font-sans leading-tight">
          Personalize your Pulse
        </p>
        <p className="text-caption text-content-muted font-sans leading-tight mt-0.5">
          Tell us what you do — we'll surface what matters most.
        </p>
      </div>
      <Button
        size="sm"
        render={<Link to="/onboarding/operator-profile" />}
        data-slot="pulse-first-login-banner-cta"
      >
        Set work areas
      </Button>
      <button
        type="button"
        onClick={dismiss}
        aria-label="Dismiss banner"
        data-slot="pulse-first-login-banner-dismiss"
        className={cn(
          "flex h-7 w-7 items-center justify-center rounded-sm",
          "text-content-subtle hover:text-content-base",
          "hover:bg-surface-elevated",
          "focus-ring-accent outline-none",
          "transition-colors duration-quick ease-settle",
          "flex-shrink-0",
        )}
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  )
}


export default PulseFirstLoginBanner
