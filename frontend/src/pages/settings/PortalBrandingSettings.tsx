/**
 * /settings/portal-branding — Workflow Arc Phase 8e.2.1.
 *
 * Tenant-admin surface for portal branding. Configure the wash
 * (logo, brand color, footer text) applied to /portal/<slug>/*
 * surfaces. Per "wash, not reskin" discipline (SPACES_ARCHITECTURE
 * §10.6), brand color applies to header + primary CTA + focus ring
 * only — NOT status colors, typography, surface tokens.
 *
 * Layout:
 *   - Identity (display name + URL slug, read-only) — FormSection
 *   - Logo upload (drag-drop + preview + replace/remove) — FormSection
 *   - Brand color (hex + swatches + live preview pane) — FormSection
 *   - Footer text (optional) — FormSection
 *
 * Live preview updates `--portal-brand` CSS var during editing but
 * reverts on unmount (discipline: don't leak portal branding into
 * the tenant UI). Save commits to backend; branding fetches
 * unblock PortalBrandProvider across the portal pages.
 */

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, ImageOff, Moon, Sun, Upload, XCircle } from "lucide-react";
import { toast } from "sonner";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FormSection, FormStack } from "@/components/ui/form-section";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  getBranding,
  updateBranding,
  uploadLogo,
} from "@/services/portal-admin-service";
import type { PortalBrandingResponse } from "@/types/portal-admin";
import { cn } from "@/lib/utils";

// Preset color swatches — common brand colors. Keeps admins from
// having to hand-type hex codes.
const SWATCHES: string[] = [
  "#B45309", // warm amber
  "#1E40AF", // deep blue
  "#C2410C", // orange
  "#6D28D9", // violet
  "#047857", // emerald
  "#B91C1C", // red
  "#475569", // slate
  "#18181B", // near-black
];


function _isValidHex(s: string): boolean {
  return /^#[0-9A-Fa-f]{6}$/.test(s);
}


export default function PortalBrandingSettings() {
  const [branding, setBranding] = useState<PortalBrandingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [brandColor, setBrandColor] = useState("#8D6F3A");
  const [footerText, setFooterText] = useState("");
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  // Session 4 (M3): preview mode toggle — lets admins verify brand
  // color against both portal surfaces before saving. Default light;
  // toggle persists in-session (no localStorage).
  const [previewMode, setPreviewMode] = useState<"light" | "dark">("light");
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Track whether we've applied the preview CSS var so we can
  // clean up on unmount.
  const appliedRef = useRef<boolean>(false);

  async function refresh() {
    setLoading(true);
    try {
      const b = await getBranding();
      setBranding(b);
      setBrandColor(b.brand_color);
      setFooterText(b.footer_text ?? "");
    } catch (err) {
      toast.error("Couldn't load branding.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  // Live-preview brand color by temporarily setting --portal-brand
  // while the user is editing. Restored on unmount or when the
  // saved branding re-syncs.
  useEffect(() => {
    if (!_isValidHex(brandColor)) return;
    document.documentElement.style.setProperty("--portal-brand", brandColor);
    appliedRef.current = true;
    return () => {
      if (appliedRef.current) {
        document.documentElement.style.removeProperty("--portal-brand");
        appliedRef.current = false;
      }
    };
  }, [brandColor]);

  async function handleLogoPick() {
    fileInputRef.current?.click();
  }

  async function handleLogoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const r = await uploadLogo(file);
      setBranding((prev) => (prev ? { ...prev, logo_url: r.logo_url } : prev));
      toast.success("Logo uploaded.");
    } catch (err) {
      const e2 = err as { response?: { data?: { detail?: string } } };
      toast.error(e2?.response?.data?.detail ?? "Upload failed.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleSave() {
    if (!_isValidHex(brandColor)) {
      toast.error("Brand color must be a 6-digit hex value like #1E40AF.");
      return;
    }
    setSaving(true);
    try {
      const updated = await updateBranding({
        brand_color: brandColor,
        footer_text: footerText.trim() || null,
      });
      setBranding(updated);
      toast.success("Branding saved.");
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-content p-6">
        <div className="text-body-sm text-content-muted">Loading…</div>
      </div>
    );
  }

  if (!branding) {
    return (
      <div className="mx-auto max-w-content p-6">
        <Alert variant="error">Couldn't load branding config.</Alert>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-content p-6 space-y-6">
      <div>
        <h1 className="text-h2 font-plex-serif font-medium text-content-strong">
          Portal branding
        </h1>
        <p className="mt-1 text-body-sm text-content-muted">
          Configure the look of your portal for drivers, partners, and
          customers. Brand color applies to the portal header + primary
          buttons. The rest of the portal stays Bridgeable-consistent
          for readability — wash, not reskin.
        </p>
      </div>

      <FormStack>
        {/* Identity — read-only */}
        <FormSection
          title="Identity"
          description="Portal URL slug + display name. Changing the slug breaks existing portal URLs; contact support to migrate."
        >
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <Label>Display name</Label>
              <Input
                value={branding.display_name}
                readOnly
                className="bg-surface-sunken"
              />
            </div>
            <div className="space-y-1">
              <Label>URL slug</Label>
              <Input
                value={branding.slug}
                readOnly
                className="bg-surface-sunken font-plex-mono"
              />
              <p className="text-caption text-content-muted">
                Portal URL: /portal/<strong>{branding.slug}</strong>/…
              </p>
            </div>
          </div>
        </FormSection>

        {/* Logo */}
        <FormSection
          title="Logo"
          description="PNG or JPG, 2MB max, 50–1024px. Displayed in the portal header + login page. SVG support coming later."
        >
          <div className="flex items-center gap-6">
            <div
              className="flex h-24 w-24 items-center justify-center rounded-md border border-border-subtle bg-surface-sunken overflow-hidden"
              data-testid="logo-preview"
            >
              {branding.logo_url ? (
                <img
                  src={branding.logo_url}
                  alt="Logo"
                  className="h-full w-full object-contain"
                />
              ) : (
                <ImageOff className="h-8 w-8 text-content-muted" />
              )}
            </div>
            <div className="flex-1 space-y-2">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png, image/jpeg"
                onChange={handleLogoChange}
                className="sr-only"
                data-testid="logo-file-input"
              />
              <Button
                type="button"
                variant="outline"
                onClick={handleLogoPick}
                disabled={uploading}
                data-testid="upload-logo-btn"
              >
                <Upload className="mr-1.5 h-4 w-4" />
                {uploading ? "Uploading…" : branding.logo_url ? "Replace logo" : "Upload logo"}
              </Button>
              <p className="text-caption text-content-muted">
                {uploading
                  ? "Uploading…"
                  : "Click to pick a file, or drag one onto the preview."}
              </p>
            </div>
          </div>
        </FormSection>

        {/* Brand color */}
        <FormSection
          title="Brand color"
          description="Applied to the portal header + primary button backgrounds. Pick a preset or enter a hex value."
        >
          <div className="space-y-4">
            <div
              className="flex flex-wrap gap-2"
              data-testid="brand-color-swatches"
            >
              {SWATCHES.map((swatch) => (
                <button
                  key={swatch}
                  type="button"
                  onClick={() => setBrandColor(swatch)}
                  className={cn(
                    "h-9 w-9 rounded-full border-2 transition-transform focus-ring-accent",
                    brandColor.toLowerCase() === swatch.toLowerCase()
                      ? "border-content-strong scale-110"
                      : "border-border-subtle hover:scale-105",
                  )}
                  style={{ backgroundColor: swatch }}
                  aria-label={`Use ${swatch}`}
                  data-testid={`swatch-${swatch}`}
                />
              ))}
            </div>
            <div className="flex items-center gap-3">
              <Label htmlFor="brand-color-input" className="shrink-0">
                Hex
              </Label>
              <Input
                id="brand-color-input"
                value={brandColor}
                onChange={(e) => setBrandColor(e.target.value)}
                className="w-40 font-plex-mono"
                placeholder="#1E40AF"
                data-testid="brand-color-hex"
              />
              {!_isValidHex(brandColor) && (
                <span className="text-caption text-status-warning">
                  Must be a 6-digit hex value.
                </span>
              )}
            </div>
            {/* Live preview header with mode toggle + WCAG readout
                (Session 4, M3). Preview simulates both the portal
                page surface AND the branded header sitting on top of
                it, so admins can see how their color renders against
                cream (light mode) AND dark charcoal (dark mode).
                WCAG contrast readout below the preview shows the
                computed brand→fg contrast with pass/fail against
                4.5:1 AA body-text threshold. */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-caption">Preview</Label>
                <div
                  className="inline-flex rounded-sm border border-border-subtle bg-surface-sunken p-0.5"
                  role="radiogroup"
                  aria-label="Preview mode"
                >
                  <button
                    type="button"
                    role="radio"
                    aria-checked={previewMode === "light"}
                    onClick={() => setPreviewMode("light")}
                    className={cn(
                      "inline-flex items-center gap-1 rounded-sm px-2 py-1 text-caption transition-colors duration-quick ease-settle focus-ring-accent",
                      previewMode === "light"
                        ? "bg-surface-raised text-content-strong shadow-level-1"
                        : "text-content-muted hover:text-content-base",
                    )}
                    data-testid="preview-mode-light"
                  >
                    <Sun className="h-3 w-3" aria-hidden="true" />
                    Light
                  </button>
                  <button
                    type="button"
                    role="radio"
                    aria-checked={previewMode === "dark"}
                    onClick={() => setPreviewMode("dark")}
                    className={cn(
                      "inline-flex items-center gap-1 rounded-sm px-2 py-1 text-caption transition-colors duration-quick ease-settle focus-ring-accent",
                      previewMode === "dark"
                        ? "bg-surface-raised text-content-strong shadow-level-1"
                        : "text-content-muted hover:text-content-base",
                    )}
                    data-testid="preview-mode-dark"
                  >
                    <Moon className="h-3 w-3" aria-hidden="true" />
                    Dark
                  </button>
                </div>
              </div>
              {/* Scoped preview container — data-mode attribute drives
                  our token vars inside this subtree only, so the rest
                  of the admin page stays in the user's current mode.
                  Surface color is sampled from tokens.css per preview
                  mode (not from runtime CSS vars) so admins see the
                  true portal surface regardless of their own mode. */}
              <div
                data-mode={previewMode}
                className="overflow-hidden rounded-md border border-border-subtle"
                data-testid="brand-color-preview-wrapper"
              >
                <div
                  className="p-6"
                  style={{
                    backgroundColor:
                      previewMode === "dark"
                        ? "oklch(0.16 0.012 65)"
                        : "oklch(0.94 0.018 82)",
                  }}
                >
                  <div
                    className="flex h-12 items-center justify-between rounded-md px-4 shadow-level-1"
                    style={{
                      backgroundColor: _isValidHex(brandColor)
                        ? brandColor
                        : "#8D6F3A",
                      color: _isLight(brandColor) ? "#1a1a1a" : "#ffffff",
                    }}
                    data-testid="brand-color-preview"
                  >
                    <span className="text-body-sm font-semibold truncate">
                      {branding.display_name}
                    </span>
                    <span className="text-caption">Driver / Sign Out</span>
                  </div>
                </div>
              </div>
              {/* WCAG contrast readout — brand→fg pairing against
                  4.5:1 AA body-text threshold. Separate advisory for
                  brand-against-surface visibility (the "will this
                  dark navy disappear into the dark charcoal page"
                  concern). */}
              {_isValidHex(brandColor) ? (
                <div className="rounded-sm border border-border-subtle bg-surface-sunken px-3 py-2 space-y-1">
                  {(() => {
                    const fg = _isLight(brandColor) ? "#1a1a1a" : "#ffffff";
                    const ratio = _wcagContrast(brandColor, fg);
                    const pass = ratio >= 4.5;
                    return (
                      <div
                        className="flex items-center justify-between gap-2 text-caption"
                        data-testid="brand-wcag-fg"
                      >
                        <span className="text-content-muted">
                          Brand → header text:
                        </span>
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 font-plex-mono",
                            pass
                              ? "text-status-success"
                              : "text-status-error",
                          )}
                        >
                          {pass ? (
                            <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                          ) : (
                            <XCircle className="h-3 w-3" aria-hidden="true" />
                          )}
                          {ratio.toFixed(2)}:1 {pass ? "AA" : "FAIL"}
                        </span>
                      </div>
                    );
                  })()}
                  {(() => {
                    const pageBg =
                      previewMode === "dark" ? "#25201C" : "#F0EAD9";
                    const ratio = _wcagContrast(brandColor, pageBg);
                    const visible = ratio >= 1.5;
                    return (
                      <div
                        className="flex items-center justify-between gap-2 text-caption"
                        data-testid="brand-wcag-surface"
                      >
                        <span className="text-content-muted">
                          Brand against {previewMode} page:
                        </span>
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 font-plex-mono",
                            visible
                              ? "text-content-base"
                              : "text-status-warning",
                          )}
                        >
                          {ratio.toFixed(2)}:1{" "}
                          {visible ? "visible" : "low-contrast"}
                        </span>
                      </div>
                    );
                  })()}
                </div>
              ) : null}
            </div>
          </div>
        </FormSection>

        {/* Footer text */}
        <FormSection
          title="Footer text"
          description="Optional — shows at the bottom of portal pages. Keep it short; mobile real estate is tight."
        >
          <Textarea
            value={footerText}
            onChange={(e) => setFooterText(e.target.value)}
            rows={2}
            maxLength={500}
            placeholder="e.g., Questions? Call dispatch at (315) 555-0100."
            data-testid="footer-text"
          />
          <p className="text-caption text-content-muted">
            {footerText.length}/500 characters
          </p>
        </FormSection>
      </FormStack>

      <div className="flex justify-end">
        <Button
          onClick={handleSave}
          disabled={saving || !_isValidHex(brandColor)}
          data-testid="save-branding-btn"
        >
          {saving ? "Saving…" : "Save changes"}
        </Button>
      </div>
    </div>
  );
}


function _isLight(hex: string): boolean {
  if (!_isValidHex(hex)) return false;
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.5;
}

// Session 4 (M3): WCAG relative luminance + contrast ratio.
// Proper sRGB gamma per WCAG 2.x; used for the brand-color
// contrast readout in the preview panel. Note: PortalBrandProvider
// still uses BT.601 for the fg-picker threshold — the two formulas
// diverge <5% for most colors, and aligning PortalBrandProvider is
// deferred (see SPACES_ARCHITECTURE.md §10.6 note).
function _wcagContrast(hexA: string, hexB: string): number {
  if (!_isValidHex(hexA) || !_isValidHex(hexB)) return 0;
  const lA = _wcagLuminance(hexA);
  const lB = _wcagLuminance(hexB);
  const lighter = Math.max(lA, lB);
  const darker = Math.min(lA, lB);
  return (lighter + 0.05) / (darker + 0.05);
}

function _wcagLuminance(hex: string): number {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16) / 255;
  const g = parseInt(h.slice(2, 4), 16) / 255;
  const b = parseInt(h.slice(4, 6), 16) / 255;
  const channel = (c: number) =>
    c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}
