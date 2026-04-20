/**
 * Phase 7 — OnboardingTouch component.
 *
 * Renders a single dismissible first-run tooltip anchored to a
 * container element. Persists dismissal server-side via
 * `useOnboardingTouch(key)` — cross-device. Auto-dismisses after
 * `autoDismissMs` if set (default: no auto-dismiss; user must click).
 *
 * Style: small pill card floating inside the parent, positioned via
 * absolute + a `position` prop (top | bottom). The parent is
 * responsible for `position: relative`.
 *
 * Usage:
 *   <div className="relative">
 *     <SearchIcon />
 *     <OnboardingTouch
 *       touchKey="command_bar_intro"
 *       title="Press Cmd+K anytime."
 *       body="Search, create, or take any action."
 *     />
 *   </div>
 */

import { useEffect } from "react";
import { X } from "lucide-react";
import { useOnboardingTouch } from "@/hooks/useOnboardingTouch";
import { cn } from "@/lib/utils";

export interface OnboardingTouchProps {
  touchKey: string;
  title: string;
  body?: string;
  /** ms until auto-dismissal. Default 0 (no auto). */
  autoDismissMs?: number;
  /** Placement relative to parent. Default "bottom". */
  position?: "top" | "bottom" | "right";
  className?: string;
}

export function OnboardingTouch({
  touchKey,
  title,
  body,
  autoDismissMs = 0,
  position = "bottom",
  className,
}: OnboardingTouchProps) {
  const { shouldShow, dismiss } = useOnboardingTouch(touchKey);

  useEffect(() => {
    if (!shouldShow || !autoDismissMs) return;
    const t = window.setTimeout(dismiss, autoDismissMs);
    return () => window.clearTimeout(t);
  }, [shouldShow, dismiss, autoDismissMs]);

  if (!shouldShow) return null;

  const positionClass =
    position === "top"
      ? "bottom-full mb-2"
      : position === "right"
      ? "left-full ml-2 top-0"
      : "top-full mt-2";

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid={`onboarding-touch-${touchKey}`}
      className={cn(
        "absolute z-40 w-64 rounded-lg border bg-popover p-3 shadow-lg",
        "motion-safe:animate-in motion-safe:fade-in-0 motion-safe:zoom-in-95",
        positionClass,
        className,
      )}
    >
      <div className="flex items-start gap-2">
        <div className="flex-1 space-y-1">
          <div className="text-sm font-semibold">{title}</div>
          {body ? (
            <div className="text-xs text-muted-foreground leading-relaxed">
              {body}
            </div>
          ) : null}
        </div>
        <button
          type="button"
          onClick={dismiss}
          aria-label="Dismiss tooltip"
          className="shrink-0 rounded text-muted-foreground hover:text-foreground"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
