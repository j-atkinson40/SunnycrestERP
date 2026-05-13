/**
 * StudioTopBar — Studio shell header.
 *
 * Houses brand + back-to-admin link, scope switcher, mode toggle, and
 * user / environment controls (delegated to the existing AdminHeader
 * surface via env+user dropdowns kept in the right cluster).
 *
 * Studio 1a-i.A1 substrate. Live mode toggle is enabled but in A1 it
 * routes to the placeholder Live page.
 */
import { ArrowLeft } from "lucide-react"
import { Link } from "react-router-dom"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import { EnvironmentBanner } from "@/bridgeable-admin/components/EnvironmentBanner"
import { StudioScopeSwitcher } from "./StudioScopeSwitcher"
import { StudioModeToggle } from "./StudioModeToggle"
import type { StudioEditorKey } from "@/bridgeable-admin/lib/studio-routes"


export interface StudioTopBarProps {
  mode: "edit" | "live"
  activeVertical: string | null
  activeEditor: StudioEditorKey | null
}


export function StudioTopBar({
  mode,
  activeVertical,
  activeEditor,
}: StudioTopBarProps) {
  return (
    <>
      <EnvironmentBanner />
      <header
        className="border-b border-border-subtle bg-surface-elevated"
        data-testid="studio-top-bar"
      >
        <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4 px-6 py-3">
          <div className="flex items-center gap-3">
            <Link
              to={adminPath("/")}
              className="flex items-center gap-1.5 text-caption text-content-muted hover:text-content-strong"
              data-testid="studio-back-to-admin"
            >
              <ArrowLeft size={12} />
              Back to Admin
            </Link>
            <span className="text-content-subtle">·</span>
            <Link
              to={adminPath("/studio")}
              className="text-h4 font-plex-serif text-content-strong hover:text-accent"
              data-testid="studio-brand"
            >
              Bridgeable Studio
            </Link>
          </div>
          <div className="flex items-center gap-3">
            <StudioScopeSwitcher
              activeVertical={activeVertical}
              activeEditor={activeEditor}
              disabled={mode === "live"}
              readOnly={mode === "live"}
              liveModeDescription={
                mode === "live"
                  ? activeVertical
                    ? `Vertical: ${activeVertical}`
                    : "(pick a tenant)"
                  : null
              }
            />
            <StudioModeToggle
              mode={mode}
              activeVertical={activeVertical}
              activeEditor={activeEditor}
            />
          </div>
        </div>
      </header>
    </>
  )
}
