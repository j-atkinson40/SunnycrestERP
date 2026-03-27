/**
 * Extract the company slug from the current hostname.
 *
 * Production: acme.getbridgeable.com -> "acme"
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
    if (parts.length >= 2 && parts[0] !== "www" && parts[0] !== "api" && parts[0] !== "admin") {
      return parts[0];
    }
    return "";
  }

  // Production: extract subdomain only if we know the base domain
  // e.g., acme.getbridgeable.com -> "acme" (base domain = "getbridgeable.com")
  const baseDomain = import.meta.env.VITE_APP_DOMAIN;
  if (baseDomain && hostname.endsWith(`.${baseDomain}`)) {
    const slug = hostname.slice(0, -(baseDomain.length + 1));
    if (slug && slug !== "www" && slug !== "api" && slug !== "admin") {
      return slug;
    }
    return "";
  }

  // No custom domain configured — fall back to localStorage
  // (covers Railway URLs like xxx.up.railway.app)
  return localStorage.getItem("company_slug") || "";
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
