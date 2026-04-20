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
import { cn } from "@/lib/utils";

export interface PinStarProps {
  pinType: "nav_item" | "saved_view";
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

  if (!activeSpace) return null;

  const pinned = isPinned({ pinType, targetId });
  const label = pinned
    ? `Pinned to ${activeSpace.name} — click to unpin`
    : `Pin to ${activeSpace.name}`;

  async function handleClick() {
    try {
      await togglePinInActiveSpace({ pinType, targetId, labelOverride });
    } catch {
      // Error is surfaced via SpaceContext.error — no toast here
      // to keep the star silent on success and visible on failure.
    }
  }

  if (inline) {
    return (
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
    );
  }

  return (
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
  );
}
