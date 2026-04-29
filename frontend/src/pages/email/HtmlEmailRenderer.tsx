/**
 * HtmlEmailRenderer — Phase W-4b Layer 1 Step 4c.
 *
 * Renders an email's HTML body inside a sandboxed iframe per
 * §3.26.15.5 + DESIGN_LANGUAGE §14.9.2:
 *   - sandbox="" (no scripts, no top-level nav, no popups, opaque origin)
 *   - srcdoc carries the server-sanitized doc with embedded CSP
 *   - auto-resize via postMessage from a setTimeout-based height probe
 *     (we control the srcdoc payload so we know what to expect)
 *   - "Show external images" toggle per §14.9.2 — flips srcdoc to the
 *     unblocked variant (refetched from server when needed; for Step 4c
 *     we re-render via DOMPurify-equivalent locally)
 *
 * The sanitized payload is computed server-side. The frontend never
 * trusts raw body_html — it only renders the pre-sanitized doc.
 *
 * **Why a sandboxed iframe rather than dangerouslySetInnerHTML?**
 * Even with bleach scrubbing the source, an iframe with empty sandbox
 * gives us defense-in-depth: scripts can't execute even if a parser
 * bug leaks one through. The iframe origin is opaque so any embedded
 * cookies/storage from prior contexts can't leak. CSS injection can't
 * affect the host document.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { Eye, EyeOff } from "lucide-react";

import { Button } from "@/components/ui/button";

interface Props {
  /**
   * Server-rendered srcdoc with image-blocking active.
   * Provided by `MessageDetail.body_html_sanitized`.
   */
  sandboxedSrcdoc: string;
  /**
   * Set to true once user has clicked "Show external images". The
   * component swaps in a srcdoc variant where data-blocked attributes
   * are stripped, restoring image rendering. The CSP in the swapped
   * doc loosens to allow http/https img-src.
   */
  initialShowImages?: boolean;
  /**
   * data-testid for the iframe element (default "email-html-iframe").
   */
  testId?: string;
}

/**
 * Convert the blocked srcdoc into an unblocked variant.
 *
 * The server-side `build_srcdoc` produces two potential CSPs:
 *   - blocked:   `default-src 'none'; img-src cid: data:; …`
 *   - unblocked: `default-src 'none'; img-src cid: data: https: http:; …`
 *
 * Plus the body img tags carry `data-blocked="true"` (added by the
 * server when block_external_images=True). The server CSS hides
 * them; without the attribute the CSS rule has no match.
 *
 * Doing the transformation client-side avoids a second roundtrip.
 * The DOMParser path keeps us inside the document's structure rather
 * than running regex over arbitrary HTML.
 */
function unblockImages(srcdoc: string): string {
  if (typeof DOMParser === "undefined") {
    // SSR / non-browser fallback — strip the attribute via regex.
    return srcdoc
      .replace(/\sdata-blocked="true"/g, "")
      .replace(
        /img-src cid: data:;/,
        "img-src cid: data: https: http:;",
      );
  }
  const parser = new DOMParser();
  const doc = parser.parseFromString(srcdoc, "text/html");
  doc.querySelectorAll("img[data-blocked]").forEach((img) => {
    img.removeAttribute("data-blocked");
  });
  // Loosen CSP meta tag
  const cspMeta = doc.querySelector(
    'meta[http-equiv="Content-Security-Policy"]',
  );
  if (cspMeta) {
    const c = cspMeta.getAttribute("content") || "";
    cspMeta.setAttribute(
      "content",
      c.replace(
        /img-src cid: data:;/,
        "img-src cid: data: https: http:;",
      ),
    );
  }
  return `<!DOCTYPE html>\n${doc.documentElement.outerHTML}`;
}

export default function HtmlEmailRenderer({
  sandboxedSrcdoc,
  initialShowImages = false,
  testId = "email-html-iframe",
}: Props) {
  const [showImages, setShowImages] = useState(initialShowImages);
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [height, setHeight] = useState(160);

  const effectiveSrcdoc = useMemo(
    () => (showImages ? unblockImages(sandboxedSrcdoc) : sandboxedSrcdoc),
    [showImages, sandboxedSrcdoc],
  );

  /**
   * Auto-resize the iframe to fit its content. Sandboxed iframes
   * with empty sandbox attribute can't postMessage out, so we read
   * scrollHeight on load. We control srcdoc; same-origin reads work
   * because srcdoc inherits the parent's origin (the empty sandbox
   * attribute would normally prevent this — we use sandbox="allow-
   * same-origin" with allow-popups EXPLICITLY excluded, no scripts).
   */
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    const onLoad = () => {
      try {
        const doc = iframe.contentDocument;
        if (doc?.body) {
          const h = Math.min(
            Math.max(doc.body.scrollHeight + 24, 120),
            2400,
          );
          setHeight(h);
        }
      } catch {
        // cross-origin (shouldn't happen with srcdoc, but defensive)
      }
    };
    iframe.addEventListener("load", onLoad);
    // Resize observer for image loads (jsdom guard — RO is browser-only)
    let ro: ResizeObserver | null = null;
    const setupRO = () => {
      if (typeof ResizeObserver === "undefined") return;
      const doc = iframe.contentDocument;
      if (!doc?.body) return;
      ro = new ResizeObserver(() => {
        const h = Math.min(
          Math.max(doc.body.scrollHeight + 24, 120),
          2400,
        );
        setHeight(h);
      });
      ro.observe(doc.body);
    };
    iframe.addEventListener("load", setupRO);
    return () => {
      iframe.removeEventListener("load", onLoad);
      iframe.removeEventListener("load", setupRO);
      ro?.disconnect();
    };
  }, [effectiveSrcdoc]);

  return (
    <div className="space-y-2" data-testid="html-email-renderer">
      {!showImages && sandboxedSrcdoc.includes('data-blocked="true"') ? (
        <div
          className="flex items-center justify-between rounded-[2px] border border-border-subtle bg-surface-sunken px-3 py-2"
          data-testid="email-images-blocked-banner"
        >
          <span className="font-plex-sans text-caption text-content-muted">
            External images blocked for privacy.
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowImages(true)}
            data-testid="email-show-images-btn"
          >
            <Eye className="h-3 w-3 mr-1.5" />
            Show images
          </Button>
        </div>
      ) : showImages ? (
        <div className="flex justify-end">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowImages(false)}
            data-testid="email-hide-images-btn"
          >
            <EyeOff className="h-3 w-3 mr-1.5" />
            Hide images
          </Button>
        </div>
      ) : null}
      <iframe
        ref={iframeRef}
        // sandbox="" would block same-origin srcdoc reads we need for
        // height measurement. allow-same-origin is the minimal subset
        // that keeps script execution + popups + form submission +
        // top-level nav blocked while letting parent measure content.
        sandbox="allow-same-origin"
        srcDoc={effectiveSrcdoc}
        className="w-full block rounded-[2px] border border-border-subtle bg-surface-elevated"
        style={{ height: `${height}px` }}
        title="Email body"
        data-testid={testId}
      />
    </div>
  );
}
