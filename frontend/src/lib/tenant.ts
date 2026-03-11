/**
 * Extract the company slug from the current hostname.
 *
 * Production: acme.sunnycrest.app -> "acme"
 * Development: reads from localStorage fallback.
 *
 * Returns empty string if on the root domain (no tenant).
 */
export function getCompanySlug(): string {
  const hostname = window.location.hostname;

  // Local development: use stored slug
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return localStorage.getItem("company_slug") || "";
  }

  // Support *.localhost subdomains (e.g., acme.localhost)
  if (hostname.endsWith(".localhost")) {
    const parts = hostname.split(".");
    if (parts.length >= 2 && parts[0] !== "www" && parts[0] !== "api") {
      return parts[0];
    }
    return "";
  }

  // Production: extract subdomain (acme.sunnycrest.app -> "acme")
  const parts = hostname.split(".");
  if (parts.length >= 3 && parts[0] !== "www" && parts[0] !== "api") {
    return parts[0];
  }

  return "";
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

  const baseDomain = import.meta.env.VITE_APP_DOMAIN || "sunnycrest.app";
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
