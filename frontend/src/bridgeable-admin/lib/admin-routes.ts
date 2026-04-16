/**
 * Build admin paths that work whether accessed via:
 *   - admin.getbridgeable.com (root paths: /, /tenants, /audit)
 *   - app.getbridgeable.com/bridgeable-admin (prefixed: /bridgeable-admin, /bridgeable-admin/tenants)
 */

export function adminPath(path: string): string {
  if (typeof window === "undefined") return path
  const host = window.location.hostname
  const isAdminSubdomain =
    host === "admin.localhost" ||
    host.startsWith("admin.") ||
    localStorage.getItem("platform_mode") === "true"
  const prefix = isAdminSubdomain ? "" : "/bridgeable-admin"
  const clean = path.startsWith("/") ? path : `/${path}`
  return `${prefix}${clean}` || "/"
}

export function isAdminSubdomain(): boolean {
  if (typeof window === "undefined") return false
  const host = window.location.hostname
  return (
    host === "admin.localhost" ||
    host.startsWith("admin.") ||
    localStorage.getItem("platform_mode") === "true"
  )
}
