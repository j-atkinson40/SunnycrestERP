/**
 * StudioModeToggle — Edit / Live mode toggle.
 *
 * Studio 1a-i.A2 — uses `toggleMode()` to flip Edit ↔ Live preserving
 * vertical scope per the 5 canonical translation rules (investigation
 * §4). Tenant impersonation params drop on Live → Edit since Edit mode
 * has no concept of impersonated tenant.
 */
import { useLocation, useNavigate } from "react-router-dom"
import { Eye, Pencil } from "lucide-react"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import {
  toggleMode,
  type StudioEditorKey,
} from "@/bridgeable-admin/lib/studio-routes"


export interface StudioModeToggleProps {
  /** Currently active mode. */
  mode: "edit" | "live"
  /** Active vertical slug (preserved on toggle). Retained for API parity. */
  activeVertical: string | null
  /** Active editor key (preserved on Live → Edit return, if any). Retained for API parity. */
  activeEditor: StudioEditorKey | null
}


export function StudioModeToggle({
  mode,
}: StudioModeToggleProps) {
  const navigate = useNavigate()
  const location = useLocation()

  const flip = () => {
    const target = toggleMode(location.pathname, location.search)
    navigate(adminPath(target))
  }

  return (
    <div
      className="flex items-center gap-0 rounded-sm border border-border-subtle bg-surface-elevated p-0.5"
      data-testid="studio-mode-toggle"
      data-active-mode={mode}
    >
      <button
        type="button"
        onClick={mode === "edit" ? undefined : flip}
        data-testid="studio-mode-edit"
        data-active={mode === "edit" ? "true" : "false"}
        className={
          mode === "edit"
            ? "flex items-center gap-1.5 rounded-sm bg-accent-subtle px-2.5 py-1 text-body-sm font-medium text-accent"
            : "flex items-center gap-1.5 rounded-sm px-2.5 py-1 text-body-sm text-content-muted hover:text-content-strong"
        }
      >
        <Pencil size={12} />
        Edit
      </button>
      <button
        type="button"
        onClick={mode === "live" ? undefined : flip}
        data-testid="studio-mode-live"
        data-active={mode === "live" ? "true" : "false"}
        className={
          mode === "live"
            ? "flex items-center gap-1.5 rounded-sm bg-accent-subtle px-2.5 py-1 text-body-sm font-medium text-accent"
            : "flex items-center gap-1.5 rounded-sm px-2.5 py-1 text-body-sm text-content-muted hover:text-content-strong"
        }
      >
        <Eye size={12} />
        Live
      </button>
    </div>
  )
}
