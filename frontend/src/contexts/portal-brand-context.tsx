/**
 * PortalBrandProvider — Workflow Arc Phase 8e.2.
 *
 * Loads tenant branding from the public `/api/v1/portal/<slug>/branding`
 * endpoint + applies it as CSS custom properties on the portal root.
 *
 * Scope discipline ("wash, not reskin" — SPACES_ARCHITECTURE.md §10.6):
 *
 *   Brand color APPLIES to:
 *     - Portal header background
 *     - Primary CTA background (portal login button, bottom-nav
 *       active indicator)
 *     - Focus ring color for interactive portal elements
 *
 *   Brand color does NOT apply to:
 *     - Status colors (--status-success / -error / etc.) — always
 *       DESIGN_LANGUAGE tokens
 *     - Typography (stays IBM Plex Sans)
 *     - Surface tokens (stay accent-themed — the wash sits on top)
 *     - Border radius / motion curves — DESIGN_LANGUAGE
 *     - Shadow system — DESIGN_LANGUAGE
 *
 * The wash discipline keeps the portal feeling tenant-branded
 * without sacrificing the DESIGN_LANGUAGE consistency that Sessions
 * 1-3 established.
 */

import { createContext, useContext, useEffect, useState } from "react";

import { fetchPortalBranding } from "@/services/portal-service";
import type { PortalBranding } from "@/types/portal";

interface PortalBrandContextValue {
  branding: PortalBranding | null;
  isLoading: boolean;
  error: string | null;
}

const PortalBrandContext = createContext<PortalBrandContextValue | null>(null);

interface Props {
  slug: string;
  children: React.ReactNode;
}

/** Apply the tenant brand color to the `:root` via the
 *  `--portal-brand` CSS var. Also sets `--portal-brand-fg` to a
 *  safe white/black foreground based on luminance. */
function applyBrandColor(color: string) {
  const root = document.documentElement;
  root.style.setProperty("--portal-brand", color);
  // Compute readable foreground via luminance.
  const hex = color.replace("#", "");
  const r = parseInt(hex.slice(0, 2), 16);
  const g = parseInt(hex.slice(2, 4), 16);
  const b = parseInt(hex.slice(4, 6), 16);
  // Relative luminance per WCAG.
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  root.style.setProperty(
    "--portal-brand-fg",
    luminance > 0.5 ? "#1a1a1a" : "#ffffff",
  );
  // Mark the root so CSS selectors can scope portal-only rules.
  root.setAttribute("data-portal-brand", "true");
}

function clearBrandColor() {
  const root = document.documentElement;
  root.style.removeProperty("--portal-brand");
  root.style.removeProperty("--portal-brand-fg");
  root.removeAttribute("data-portal-brand");
}

export function PortalBrandProvider({ slug, children }: Props) {
  const [branding, setBranding] = useState<PortalBranding | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    void fetchPortalBranding(slug)
      .then((data) => {
        if (cancelled) return;
        setBranding(data);
        applyBrandColor(data.brand_color);
      })
      .catch((err) => {
        if (cancelled) return;
        const e = err as {
          response?: { data?: { detail?: string }; status?: number };
        };
        setError(
          e?.response?.status === 404
            ? "Portal not found."
            : e?.response?.data?.detail ?? "Failed to load portal.",
        );
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
      // Clear on unmount so a user logging out of the portal
      // doesn't carry tenant branding into unrelated surfaces.
      clearBrandColor();
    };
  }, [slug]);

  return (
    <PortalBrandContext.Provider value={{ branding, isLoading, error }}>
      {children}
    </PortalBrandContext.Provider>
  );
}

export function usePortalBrand(): PortalBrandContextValue {
  const ctx = useContext(PortalBrandContext);
  if (!ctx) {
    throw new Error(
      "usePortalBrand must be used within a PortalBrandProvider",
    );
  }
  return ctx;
}
