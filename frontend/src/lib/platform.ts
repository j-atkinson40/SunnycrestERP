/**
 * Platform admin detection and utilities.
 *
 * The platform admin interface is served on the "admin" subdomain:
 * - Development: admin.localhost:5173
 * - Production: admin.<VITE_APP_DOMAIN>
 */

/**
 * Check if the current hostname is the platform admin subdomain.
 */
export function isPlatformAdmin(): boolean {
  const hostname = window.location.hostname;

  // Local dev: admin.localhost
  if (hostname === "admin.localhost") return true;

  // Production: admin.<base domain>
  const baseDomain = import.meta.env.VITE_APP_DOMAIN;
  if (baseDomain && hostname === `admin.${baseDomain}`) return true;

  // Hardened fallback: detect any hostname starting with "admin."
  // This catches cases where VITE_APP_DOMAIN wasn't set at build time
  if (hostname.startsWith("admin.") && !hostname.endsWith(".localhost")) return true;

  // Fallback for Railway URLs and non-subdomain setups:
  // Check localStorage flag (set via /platform-admin entry point)
  if (localStorage.getItem("platform_mode") === "true") return true;

  return false;
}

/**
 * Get the API base URL for platform endpoints.
 * Platform routes live under /api/platform/.
 */
export function getPlatformApiBaseUrl(): string {
  const apiUrl = import.meta.env.VITE_API_URL || "";
  return `${apiUrl}/api/platform`;
}

/**
 * Enable platform mode (for Railway/non-subdomain setups).
 */
export function enablePlatformMode(): void {
  localStorage.setItem("platform_mode", "true");
}

/**
 * Disable platform mode and return to tenant mode.
 */
export function disablePlatformMode(): void {
  localStorage.removeItem("platform_mode");
  localStorage.removeItem("platform_access_token");
  localStorage.removeItem("platform_refresh_token");
}
