/**
 * StudioRedirect — translates a standalone visual-editor / runtime-
 * editor URL to its Studio equivalent, preserving query params.
 *
 * Mounted at the 10 legacy routes in BridgeableAdminApp. Reads
 * `location.pathname + location.search`, runs them through
 * `redirectFromStandalone()`, and `<Navigate replace>`s to the result.
 */
import { Navigate, useLocation } from "react-router-dom"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import {
  readLastVertical,
  redirectFromStandalone,
} from "@/bridgeable-admin/lib/studio-routes"


export function StudioRedirect() {
  const location = useLocation()
  // Strip /bridgeable-admin prefix if present so the translation table
  // matches subdomain + path-prefix entries identically.
  const pathname = location.pathname.replace(/^\/bridgeable-admin/, "")
  const target = redirectFromStandalone(pathname, location.search, {
    lastVertical: readLastVertical(),
  })
  return <Navigate to={adminPath(target)} replace />
}
