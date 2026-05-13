/**
 * VisualEditorIndex — legacy entry, now redirects to Studio.
 *
 * Pre-Studio (May 2026) this page rendered a card grid for the 9
 * visual editor surfaces. Studio 1a-i.A1 consolidates those surfaces
 * under `/studio` with a persistent rail; this index is preserved as
 * a redirect so any inbound bookmark + deep link lands cleanly.
 *
 * The route-level redirect in BridgeableAdminApp.tsx also catches
 * /visual-editor independently; this component-level redirect is a
 * safety net for callers that mount VisualEditorIndex directly.
 */
import { Navigate } from "react-router-dom"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"


export default function VisualEditorIndex() {
  return <Navigate to={adminPath("/studio")} replace />
}
