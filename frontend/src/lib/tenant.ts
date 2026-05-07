/**
 * On first load, check for a ?slug= query parameter and persist it.
 * This lets staging/Railway URLs enter tenant context via:
 *   https://determined-renewal-staging.up.railway.app?slug=testco
 *
 * Runs once at module load time before any component renders.
 */
(function bootstrapSlugFromUrl() {
  try {
    const params = new URLSearchParams(window.location.search);
    const slugParam = params.get("slug");
    if (slugParam) {
      localStorage.setItem("company_slug", slugParam);
      // Strip the ?slug= param from the URL so it doesn't persist in the address bar
      params.delete("slug");
      const clean = params.toString();
      const newUrl =
        window.location.pathname + (clean ? `?${clean}` : "") + window.location.hash;
      window.history.replaceState(null, "", newUrl);
    }
  } catch {
    // Ignore — localStorage or URL API unavailable
  }
})();

/**
 * Extract the company slug from the current hostname.
 *
 * Resolution order:
 *   1. Local dev (`localhost` / `127.0.0.1`) → localStorage.
 *   2. *.localhost subdomain → first segment (excluding reserved
 *      `www` / `api` / `admin`).
 *   3. R-1.6.8: Railway-issued hostnames (`*.railway.app`) → localStorage.
 *      These are NEVER tenant subdomains regardless of `VITE_APP_DOMAIN`.
 *   4. R-1.6.8: Admin hostnames (first segment === `"admin"`) → localStorage.
 *      Admin tree never carries a tenant slug in its hostname; localStorage
 *      is the canonical source (set by TenantUserPicker on impersonation).
 *   5. Production tenant subdomain (`<slug>.<VITE_APP_DOMAIN>`, slug not
 *      reserved) → extract slug.
 *   6. Otherwise → localStorage.
 *
 * R-1.6.8 history: pre-fix, with `VITE_APP_DOMAIN=up.railway.app` set on
 * the staging frontend service, `sunnycresterp-staging.up.railway.app`
 * incorrectly extracted `"sunnycresterp-staging"` as a tenant slug —
 * surfaced as 404 from `/api/v1/auth/me` with body
 * `Company 'sunnycresterp-staging' not found or is inactive.` Fix
 * rejects Railway hostnames + admin hostnames before the
 * `VITE_APP_DOMAIN` extraction path, and changes empty-slug fallthroughs
 * to read localStorage so the impersonation flow's
 * `localStorage.company_slug` write is honored.
 */
export function getCompanySlug(): string {
  const hostname = window.location.hostname;
  const stored = localStorage.getItem("company_slug") || "";

  // Local development: use stored slug.
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return stored;
  }

  // Support *.localhost subdomains (e.g., acme.localhost) for dev.
  if (hostname.endsWith(".localhost")) {
    const parts = hostname.split(".");
    if (
      parts.length >= 2 &&
      parts[0] !== "www" &&
      parts[0] !== "api" &&
      parts[0] !== "admin"
    ) {
      return parts[0];
    }
    return stored;
  }

  // R-1.6.8: Railway-issued hostnames are NEVER tenant subdomains.
  // VITE_APP_DOMAIN may be set to "up.railway.app" or similar on staging,
  // which would let the suffix-strip path below incorrectly extract a
  // pseudo-slug from the Railway URL. Reject up-front.
  if (hostname.endsWith(".railway.app") || hostname === "railway.app") {
    return stored;
  }

  // R-1.6.8: Reject admin hostnames at any level (`admin.getbridgeable.com`,
  // `admin.staging.getbridgeable.com`, `admin.localhost.dev`, etc.). Admin
  // tree never carries a tenant slug in its hostname; the runtime editor's
  // TenantUserPicker writes localStorage.company_slug on impersonation, so
  // localStorage is the canonical source for admin-mounted tenant context.
  const firstSegment = hostname.split(".")[0];
  if (firstSegment === "admin") {
    return stored;
  }

  // Production: extract subdomain only when hostname strictly ends with the
  // configured base domain. e.g. acme.getbridgeable.com → "acme".
  const baseDomain = import.meta.env.VITE_APP_DOMAIN;
  if (baseDomain && hostname.endsWith(`.${baseDomain}`)) {
    const slug = hostname.slice(0, -(baseDomain.length + 1));
    if (slug && slug !== "www" && slug !== "api" && slug !== "admin") {
      return slug;
    }
    return stored;
  }

  // No tenant-subdomain match — fall back to localStorage (covers ?slug=
  // bootstrap, Railway URLs not caught above, dev environments).
  return stored;
}

/**
 * Check if we are on a company subdomain (tenant context).
 */
export function isTenantContext(): boolean {
  return getCompanySlug() !== "";
}

/**
 * Build the URL for a specific company's subdomain.
 */
export function getCompanyUrl(slug: string): string {
  const hostname = window.location.hostname;

  // In development, stay on same host
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return window.location.origin;
  }

  const baseDomain = import.meta.env.VITE_APP_DOMAIN || "getbridgeable.com";
  const protocol = window.location.protocol;
  return `${protocol}//${slug}.${baseDomain}`;
}

/**
 * Store the company slug for local development use.
 */
export function setCompanySlug(slug: string): void {
  localStorage.setItem("company_slug", slug);
}

/**
 * Clear the stored company slug.
 */
export function clearCompanySlug(): void {
  localStorage.removeItem("company_slug");
}
