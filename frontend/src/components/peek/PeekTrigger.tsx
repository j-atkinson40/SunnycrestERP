/**
 * PeekTrigger — wrap an interactive element to make it peek-capable.
 *
 * Two modes:
 *   triggerType="click" — click opens click-mode peek (pinned)
 *   triggerType="hover" — hover opens hover-mode peek (transient,
 *                         info-only); promotes to click if user
 *                         moves into the panel
 *
 * Per arc-finale UX discipline: command-bar uses an icon-only
 * variant for click peeks (preserves "Cmd+K, type, Enter" muscle
 * memory). Other surfaces wrap text/title elements directly.
 *
 * Mobile degradation: hover triggers don't fire on touch — touch
 * devices tap to open click-mode directly. The `triggerType="hover"`
 * variant detects coarse-pointer environments and switches to click
 * semantics so peeks stay reachable on mobile.
 *
 * Keyboard accessibility:
 *   Tab focuses peekable references (button or anchor element).
 *   Enter/Space opens peek in click mode.
 *   Escape closes (handled by PeekHost).
 *   Focus returns to trigger on close (handled by PeekHost).
 */

import {
  Children,
  cloneElement,
  isValidElement,
  type MouseEvent,
  type KeyboardEvent,
  type ReactElement,
  type ReactNode,
  useCallback,
  useRef,
} from "react";

import { usePeekOptional } from "@/contexts/peek-context";
import type { PeekEntityType, PeekTriggerType } from "@/types/peek";


export interface PeekTriggerProps {
  entityType: PeekEntityType;
  entityId: string;
  triggerType?: PeekTriggerType;
  /** When true, also call openPeek on focus (keyboard fallback for
   *  hover triggers). Default true for hover, false for click. */
  openOnFocus?: boolean;
  /** Suppress wrapping behavior — caller provides their own
   *  `onClick` that calls `openPeek` directly. Useful for command
   *  bar's icon-only trigger which doesn't wrap a single child. */
  asChild?: boolean;
  className?: string;
  children: ReactNode;
}


function _isCoarsePointer(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.matchMedia("(pointer: coarse)").matches;
  } catch {
    return false;
  }
}


/**
 * Wraps a child element. Click handler attaches inline; hover
 * handler attaches via mouseenter on the wrapper span. The wrapper
 * is a `<span>` so it can host any inline trigger.
 */
export function PeekTrigger({
  entityType,
  entityId,
  triggerType = "click",
  openOnFocus,
  className,
  children,
}: PeekTriggerProps) {
  const peek = usePeekOptional();
  const wrapperRef = useRef<HTMLSpanElement | null>(null);

  // Coarse-pointer (touch) devices: collapse hover to click so
  // peeks stay reachable.
  const effectiveTriggerType: PeekTriggerType =
    triggerType === "hover" && _isCoarsePointer() ? "click" : triggerType;

  const open = useCallback(
    (anchor: HTMLElement) => {
      if (!peek) return;
      peek.openPeek({
        entityType,
        entityId,
        triggerType: effectiveTriggerType,
        anchorElement: anchor,
      });
    },
    [peek, entityType, entityId, effectiveTriggerType],
  );

  const onClick = useCallback(
    (e: MouseEvent<HTMLSpanElement>) => {
      if (!peek) return;
      // Stop the click from bubbling into a parent navigation
      // handler (e.g., a saved-view row Link). Without this, click
      // would fire both peek + navigate.
      e.stopPropagation();
      e.preventDefault();
      const anchor = wrapperRef.current ?? (e.currentTarget as HTMLElement);
      open(anchor);
    },
    [peek, open],
  );

  const onKeyDown = useCallback(
    (e: KeyboardEvent<HTMLSpanElement>) => {
      if (!peek) return;
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        const anchor = wrapperRef.current ?? (e.currentTarget as HTMLElement);
        open(anchor);
      }
    },
    [peek, open],
  );

  const onMouseEnter = useCallback(() => {
    if (!peek) return;
    if (effectiveTriggerType !== "hover") return;
    const anchor = wrapperRef.current;
    if (anchor) open(anchor);
  }, [peek, effectiveTriggerType, open]);

  const onFocus = useCallback(() => {
    if (!peek) return;
    const shouldOpen =
      openOnFocus ?? (effectiveTriggerType === "hover");
    if (!shouldOpen) return;
    const anchor = wrapperRef.current;
    if (anchor) open(anchor);
  }, [peek, openOnFocus, effectiveTriggerType, open]);

  return (
    <span
      ref={wrapperRef}
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={onKeyDown}
      onMouseEnter={onMouseEnter}
      onFocus={onFocus}
      data-testid="peek-trigger"
      data-peek-entity-type={entityType}
      data-peek-entity-id={entityId}
      data-peek-trigger-type={effectiveTriggerType}
      className={className}
      aria-label={`Preview ${entityType.replace("_", " ")}`}
    >
      {children}
    </span>
  );
}


/**
 * IconOnlyPeekTrigger — variant for the command bar tile + similar
 * surfaces where the peek affordance is a small icon distinct from
 * the primary tile interaction. Renders the child element (typically
 * an icon button) and binds peek-open to its click without wrapping
 * a span (so the focus + cursor target is the icon itself).
 */
export interface IconOnlyPeekTriggerProps {
  entityType: PeekEntityType;
  entityId: string;
  /** The icon button element. Must accept `onClick`, `ref`, `tabIndex`
   *  and forward them to a real DOM button. */
  children: ReactElement<{
    onClick?: (e: MouseEvent<HTMLElement>) => void;
    ref?: React.Ref<HTMLElement>;
  }>;
}


export function IconOnlyPeekTrigger({
  entityType,
  entityId,
  children,
}: IconOnlyPeekTriggerProps) {
  const peek = usePeekOptional();
  const child = Children.only(children);
  if (!isValidElement(child)) return child as unknown as ReactElement;

  const handleClick = (e: MouseEvent<HTMLElement>) => {
    e.stopPropagation();
    e.preventDefault();
    if (!peek) return;
    const anchor = e.currentTarget as HTMLElement;
    peek.openPeek({
      entityType,
      entityId,
      triggerType: "click",
      anchorElement: anchor,
    });
  };

  return cloneElement(child, {
    onClick: handleClick,
  });
}
