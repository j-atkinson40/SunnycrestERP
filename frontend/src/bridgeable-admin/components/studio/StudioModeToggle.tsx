/**
 * StudioModeToggle — Edit / Live mode toggle.
 *
 * Live mode lands in 1a-i.A2 (impersonation handshake + RuntimeEditor
 * wrap). In 1a-i.A1 the Live tab navigates to the placeholder Live
 * page (`/studio/live`) so the route + chrome exist, but the operator
 * is shown a "Coming next sub-arc" panel.
 */
import { useNavigate } from "react-router-dom"
import { Eye, Pencil } from "lucide-react"
import {
  studioLivePath,
  studioPath,
  type StudioEditorKey,
} from "@/bridgeable-admin/lib/studio-routes"


export interface StudioModeToggleProps {
  /** Currently active mode. */
  mode: "edit" | "live"
  /** Active vertical slug (preserved on toggle). */
  activeVertical: string | null
  /** Active editor key (preserved on Live → Edit return, if any). */
  activeEditor: StudioEditorKey | null
}


export function StudioModeToggle({
  mode,
  activeVertical,
  activeEditor,
}: StudioModeToggleProps) {
  const navigate = useNavigate()

  const toEdit = () => {
    navigate(studioPath({ vertical: activeVertical, editor: activeEditor }))
  }
  const toLive = () => {
    navigate(studioLivePath({ vertical: activeVertical }))
  }

  return (
    <div
      className="flex items-center gap-0 rounded-sm border border-border-subtle bg-surface-elevated p-0.5"
      data-testid="studio-mode-toggle"
      data-active-mode={mode}
    >
      <button
        type="button"
        onClick={toEdit}
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
        onClick={toLive}
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
