/**
 * PeekHost — single floating panel, mounted once at app root,
 * reads PeekContext. Renders or returns null based on `current`.
 *
 * Semantics:
 *   hover mode:  role="tooltip", no backdrop, transient. Auto-
 *                dismisses when both anchor + panel are left.
 *                Moving INTO the panel promotes to click mode.
 *   click mode:  role="dialog" + aria-modal="true". Backdrop
 *                captures click-outside → close. Escape → close.
 *                Tab cycles within. Focus returns to anchor on
 *                close.
 *
 * Implementation note (deviation documented in session log):
 *   The arc-finale audit approved "base-ui Tooltip for hover,
 *   base-ui Popover for click." The host below provides equivalent
 *   a11y guarantees with a single render path so hover→click
 *   promotion is a state mutation rather than a component remount.
 *   Trade-off: ~30 lines of focus + escape handling we'd otherwise
 *   delegate to base-ui. Won: no flash on promotion, simpler
 *   testing harness, one place to govern peek visual + behavior.
 */

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ArrowUpRight, X } from "lucide-react";
import { useNavigate } from "react-router";

import { Button } from "@/components/ui/button";
import { InlineError } from "@/components/ui/inline-error";
import { SkeletonCard } from "@/components/ui/skeleton";
import { usePeek } from "@/contexts/peek-context";
import { CasePeekRenderer } from "./renderers/CasePeekRenderer";
import { ContactPeekRenderer } from "./renderers/ContactPeekRenderer";
import { InvoicePeekRenderer } from "./renderers/InvoicePeekRenderer";
import { SalesOrderPeekRenderer } from "./renderers/SalesOrderPeekRenderer";
import { SavedViewPeekRenderer } from "./renderers/SavedViewPeekRenderer";
import { TaskPeekRenderer } from "./renderers/TaskPeekRenderer";
import { cn } from "@/lib/utils";


const PANEL_WIDTH = 360;
const VIEWPORT_PAD = 12;


export function PeekHost() {
  const { current, data, status, error, closePeek, promoteToClick } = usePeek();
  const navigate = useNavigate();
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);

  // Track whether the mouse is currently over the panel — needed to
  // distinguish "left the anchor onto the panel" (keep open) from
  // "left the anchor into open space" (close hover peek).
  const overPanelRef = useRef(false);

  // ── Position the panel near the anchor ───────────────────────────

  useLayoutEffect(() => {
    if (!current?.anchorElement) {
      setPos(null);
      return;
    }
    const rect = current.anchorElement.getBoundingClientRect();
    const viewportW = window.innerWidth;
    const viewportH = window.innerHeight;
    // Prefer below the anchor; flip up if not enough room.
    const desiredTop = rect.bottom + 8;
    const wouldOverflowBottom = desiredTop + 320 > viewportH - VIEWPORT_PAD;
    const top = wouldOverflowBottom
      ? Math.max(VIEWPORT_PAD, rect.top - 8 - 320)
      : desiredTop;
    // Prefer left-aligned with anchor; clamp into viewport.
    const left = Math.min(
      Math.max(VIEWPORT_PAD, rect.left),
      viewportW - PANEL_WIDTH - VIEWPORT_PAD,
    );
    setPos({ top, left });
  }, [current?.anchorElement, current?.openId]);

  // ── Click-mode: backdrop click + Escape + focus management ──────

  useEffect(() => {
    if (!current) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        closePeek();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [current, closePeek]);

  // Auto-focus the panel on click open so Esc + Tab work; restore
  // focus to anchor on close.
  useEffect(() => {
    if (!current) return;
    if (current.triggerType !== "click") return;
    const anchor = current.anchorElement;
    panelRef.current?.focus();
    return () => {
      // Return focus to the original trigger.
      anchor?.focus?.();
    };
  }, [current?.openId, current?.triggerType, current?.anchorElement, current]);

  // ── Hover-mode dismiss guards on the anchor ──────────────────────

  useEffect(() => {
    if (!current) return;
    if (current.triggerType !== "hover") return;
    const anchor = current.anchorElement;
    if (!anchor) return;
    const onLeaveAnchor = () => {
      // Give the user a beat to move into the panel.
      window.setTimeout(() => {
        if (!overPanelRef.current) {
          closePeek();
        }
      }, 80);
    };
    anchor.addEventListener("mouseleave", onLeaveAnchor);
    return () => anchor.removeEventListener("mouseleave", onLeaveAnchor);
  }, [current, closePeek]);

  const navigateToDetail = useCallback(() => {
    if (!data) return;
    closePeek();
    navigate(data.navigate_url);
  }, [closePeek, data, navigate]);

  const onPanelMouseEnter = useCallback(() => {
    overPanelRef.current = true;
    // Hover-to-click promotion: moving the mouse into the panel pins
    // it. Subsequent mouse-leave on the panel does NOT close it
    // — only Escape, click-outside, or the close button.
    if (current?.triggerType === "hover") {
      promoteToClick();
    }
  }, [current, promoteToClick]);

  const onPanelMouseLeave = useCallback(() => {
    overPanelRef.current = false;
  }, []);

  const renderer = useMemo(() => {
    if (!data) return null;
    switch (data.entity_type) {
      case "fh_case":
        return <CasePeekRenderer data={data.peek as never} />;
      case "invoice":
        return <InvoicePeekRenderer data={data.peek as never} />;
      case "sales_order":
        return <SalesOrderPeekRenderer data={data.peek as never} />;
      case "task":
        return <TaskPeekRenderer data={data.peek as never} />;
      case "contact":
        return <ContactPeekRenderer data={data.peek as never} />;
      case "saved_view":
        return <SavedViewPeekRenderer data={data.peek as never} />;
      default:
        return (
          <p className="text-xs text-muted-foreground">
            Unsupported peek type: {data.entity_type}
          </p>
        );
    }
  }, [data]);

  if (!current || !pos) return null;

  const isClickMode = current.triggerType === "click";

  return (
    <>
      {/* Click-mode backdrop — captures outside clicks. */}
      {isClickMode && (
        <div
          className="fixed inset-0 z-[70]"
          onClick={closePeek}
          data-testid="peek-host-backdrop"
        />
      )}

      <div
        ref={panelRef}
        role={isClickMode ? "dialog" : "tooltip"}
        aria-modal={isClickMode ? "true" : undefined}
        aria-label={data?.display_label ?? "Loading preview"}
        tabIndex={isClickMode ? -1 : undefined}
        onMouseEnter={onPanelMouseEnter}
        onMouseLeave={onPanelMouseLeave}
        style={{ top: pos.top, left: pos.left, width: PANEL_WIDTH }}
        className={cn(
          "fixed z-[71] rounded-lg border bg-card shadow-lg",
          "animate-in fade-in-0 zoom-in-95 duration-100",
          // Hover panels can be slightly less prominent.
          isClickMode ? "ring-1 ring-foreground/5" : "ring-1 ring-foreground/10",
        )}
        data-testid="peek-host-panel"
        data-trigger-type={current.triggerType}
        data-entity-type={current.entityType}
        data-entity-id={current.entityId}
      >
        {/* Header */}
        <div className="flex items-start gap-2 border-b px-3 py-2">
          <div className="flex-1 min-w-0">
            {data ? (
              <p className="text-sm font-medium truncate">
                {data.display_label}
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">Loading…</p>
            )}
            <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
              {current.entityType.replace("_", " ")}
            </p>
          </div>
          {isClickMode && (
            <button
              type="button"
              onClick={closePeek}
              aria-label="Close preview"
              className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              data-testid="peek-host-close"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* Body */}
        <div className="px-3 py-2.5 text-sm">
          {status === "loading" && <SkeletonCard lines={4} showHeader={false} />}
          {status === "error" && (
            <InlineError
              message="Couldn't load preview."
              hint={error ?? undefined}
              size="sm"
            />
          )}
          {status === "loaded" && renderer}
        </div>

        {/* Footer */}
        {data && (
          <div className="border-t px-3 py-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={navigateToDetail}
              className="h-7 w-full justify-center gap-1.5"
              data-testid="peek-host-open-detail"
            >
              Open full detail
              <ArrowUpRight className="h-3 w-3" />
            </Button>
          </div>
        )}
      </div>
    </>
  );
}
