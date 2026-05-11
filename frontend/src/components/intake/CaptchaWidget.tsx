/**
 * Phase R-6.2b — CAPTCHA widget (Cloudflare Turnstile).
 *
 * Thin wrapper over @marsidev/react-turnstile. Surfaces the token via
 * onTokenChange(token | null). Token state managed internally; the
 * widget handles its own re-challenge on expiration.
 *
 * Test mode: when `VITE_TURNSTILE_SITE_KEY` is the Cloudflare canonical
 * always-passes test key `1x00000000000000000000AA`, the widget
 * succeeds immediately — natural for Playwright spec 36.
 *
 * When VITE_TURNSTILE_SITE_KEY is unset, this widget renders nothing
 * + invokes onTokenChange(null) once — backend graceful degradation
 * then allows submission in non-production environments.
 */

import { Turnstile } from "@marsidev/react-turnstile";
import { useEffect, useRef } from "react";

interface CaptchaWidgetProps {
  /** Called with a token on success, null on error or expiration. */
  onTokenChange: (token: string | null) => void;
}

export function CaptchaWidget({ onTokenChange }: CaptchaWidgetProps) {
  const siteKey = import.meta.env.VITE_TURNSTILE_SITE_KEY as
    | string
    | undefined;

  const calledRef = useRef(false);

  // When site key unset, fire null once and let backend graceful
  // degradation handle dev workflows.
  useEffect(() => {
    if (!siteKey && !calledRef.current) {
      calledRef.current = true;
      onTokenChange(null);
    }
  }, [siteKey, onTokenChange]);

  if (!siteKey) {
    return (
      <div
        className="mb-3 text-caption text-content-muted"
        data-testid="captcha-widget-disabled"
      >
        CAPTCHA disabled in this environment.
      </div>
    );
  }

  return (
    <div className="mb-3" data-testid="captcha-widget">
      <Turnstile
        siteKey={siteKey}
        onSuccess={(token) => onTokenChange(token)}
        onError={() => onTokenChange(null)}
        onExpire={() => onTokenChange(null)}
        options={{
          theme: "auto",
          size: "normal",
        }}
      />
    </div>
  );
}
