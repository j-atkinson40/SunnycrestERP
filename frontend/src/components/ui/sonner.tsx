import { Toaster as Sonner, type ToasterProps } from "sonner"
import {
  CircleCheckIcon,
  InfoIcon,
  TriangleAlertIcon,
  OctagonXIcon,
  Loader2Icon,
} from "lucide-react"

/**
 * Bridgeable Toaster (Sonner wrapper) — Aesthetic Arc Session 3 refresh.
 *
 * Changes from Session 2:
 *   - `next-themes` removed. Bridgeable is Vite SPA; the platform mode
 *     switch lives on `document.documentElement[data-mode]` per
 *     DESIGN_LANGUAGE.md §9 and Session 1's theme-mode.ts runtime.
 *     Sonner reads `prefers-color-scheme` via theme="system"; the
 *     data-mode override cascades via the CSS variables below.
 *   - `richColors` enabled — Sonner now auto-tints toasts by status
 *     type (success/error/warning/info) using the CSS vars we map to
 *     DESIGN_LANGUAGE status-muted tokens.
 *   - All CSS vars point at DESIGN_LANGUAGE tokens — the refreshed
 *     overlay family composition (surface-raised + border-subtle +
 *     radius-md). Status variants map muted backgrounds with
 *     full-saturation borders + icons per Session 3 status-color
 *     recipe.
 *
 * Positioning: bottom-right default (Sonner's own default; matches
 * DESIGN_LANGUAGE §6 toast convention — "temporary overlays that sit
 * above everything").
 *
 * Icons: keep explicit Lucide icons to override Sonner's built-in
 * emoji fallbacks with our platform icon library (per §7).
 */
const Toaster = ({ ...props }: ToasterProps) => {
  return (
    <Sonner
      theme="system"
      richColors
      className="toaster group"
      icons={{
        success: <CircleCheckIcon className="size-4" />,
        info: <InfoIcon className="size-4" />,
        warning: <TriangleAlertIcon className="size-4" />,
        error: <OctagonXIcon className="size-4" />,
        loading: <Loader2Icon className="size-4 animate-spin" />,
      }}
      style={
        {
          // Neutral toast — overlay family composition (surface-raised
          // + border-subtle + content-base text + radius-md).
          "--normal-bg": "var(--surface-raised)",
          "--normal-text": "var(--content-base)",
          "--normal-border": "var(--border-subtle)",
          "--border-radius": "var(--radius-md)",
          // Status-tinted toasts (richColors). Each maps to the
          // DESIGN_LANGUAGE status recipe: muted background +
          // saturation text + saturation border.
          "--success-bg": "var(--status-success-muted)",
          "--success-text": "var(--status-success)",
          "--success-border": "var(--status-success)",
          "--error-bg": "var(--status-error-muted)",
          "--error-text": "var(--status-error)",
          "--error-border": "var(--status-error)",
          "--warning-bg": "var(--status-warning-muted)",
          "--warning-text": "var(--status-warning)",
          "--warning-border": "var(--status-warning)",
          "--info-bg": "var(--status-info-muted)",
          "--info-text": "var(--status-info)",
          "--info-border": "var(--status-info)",
        } as React.CSSProperties
      }
      toastOptions={{
        classNames: {
          toast: "cn-toast",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
