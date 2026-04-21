/**
 * PinStar — one-click pin toggle for the current active space.
 *
 * Usage: drop <PinStar pinType="saved_view" targetId={view.id} />
 * in any header. Click star → pin to active space. Click again →
 * unpin. De-duped server-side so rapid-fire clicks never create
 * multiple pins.
 *
 * Renders nothing when no active space exists (new user before
 * seed, or deleted their only space). That's intentional — the
 * empty state belongs in the SpaceSwitcher, not bleeding into
 * every pinnable surface.
 */

import { Star } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useSpaces } from "@/contexts/space-context";
import { useAffinityVisit } from "@/hooks/useAffinityVisit";
import { cn } from "@/lib/utils";
import { OnboardingTouch } from "@/components/onboarding/OnboardingTouch";

export interface PinStarProps {
  pinType: "nav_item" | "saved_view" | "triage_queue";
  targetId: string;
  /** Optional custom label for the pin. Defaults to the server's
   *  resolution (saved-view title / nav label table). */
  labelOverride?: string;
  className?: string;
  /** Render as inline text+icon rather than an icon button. */
  inline?: boolean;
}

export function PinStar({
  pinType,
  targetId,
  labelOverride,
  className,
  inline = false,
}: PinStarProps) {
  const { activeSpace, isPinned, togglePinInActiveSpace } = useSpaces();
  const { recordVisit } = useAffinityVisit();

  if (!activeSpace) return null;

  const pinned = isPinned({ pinType, targetId });
  const label = pinned
    ? `Pinned to ${activeSpace.name} — click to unpin`
    : `Pin to ${activeSpace.name}`;

  // Phase 8e — `pin_this_view` onboarding touch. Fires the FIRST time
  // the user sees any PinStar. Suppressed when the user has already
  // pinned this target (nothing to teach) + when they're an
  // unauthenticated edge-case (no active space — `activeSpace` guard
  // above already returns null). Touch is server-persisted cross-
  // device; once dismissed, PinStars everywhere stop showing it.
  const showPinTouch = !pinned;

  async function handleClick() {
    // Phase 8e.1 — capture pre-toggle state; only record affinity
    // on the pin-TO-pinned transition. Unpinning is not intent;
    // don't record.
    const wasPinned = pinned;
    try {
      await togglePinInActiveSpace({ pinType, targetId, labelOverride });
      if (!wasPinned) {
        recordVisit({ targetType: pinType, targetId });
      }
    } catch {
      // Error is surfaced via SpaceContext.error — no toast here
      // to keep the star silent on success and visible on failure.
    }
  }

  if (inline) {
    return (
      <span className="relative inline-flex">
        <button
          type="button"
          onClick={handleClick}
          title={label}
          aria-label={label}
          className={cn(
            "inline-flex items-center gap-1 text-xs hover:underline",
            pinned ? "text-[color:var(--space-accent,var(--preset-accent))]" : "text-muted-foreground",
            className,
          )}
          data-testid="pin-star-inline"
          data-pinned={pinned ? "true" : "false"}
        >
          <Star
            className={cn("size-3.5", pinned && "fill-current")}
          />
          {pinned ? "Pinned" : "Pin to space"}
        </button>
        {showPinTouch ? (
          <OnboardingTouch
            touchKey="pin_this_view"
            title={`Pin to ${activeSpace.name}.`}
            body={
              "Pinned items live in this space's sidebar section. " +
              "Each space keeps its own pins."
            }
            position="bottom"
            className="left-0 w-64"
          />
        ) : null}
      </span>
    );
  }

  return (
    <span className="relative inline-flex">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={handleClick}
        title={label}
        aria-label={label}
        className={cn(
          "size-8",
          pinned && "text-[color:var(--space-accent,var(--preset-accent))]",
          className,
        )}
        data-testid="pin-star"
        data-pinned={pinned ? "true" : "false"}
      >
        <Star className={cn("size-4", pinned && "fill-current")} />
      </Button>
      {showPinTouch ? (
        <OnboardingTouch
          touchKey="pin_this_view"
          title={`Pin to ${activeSpace.name}.`}
          body={
            "Pinned items live in this space's sidebar section. " +
            "Each space keeps its own pins."
          }
          position="bottom"
          className="right-0 w-64"
        />
      ) : null}
    </span>
  );
}
