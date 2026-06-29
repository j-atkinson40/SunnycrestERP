import type { ReactNode } from "react"
import { Navigate, useLocation } from "react-router-dom"
import { useAdminAuth } from "../lib/admin-auth-context"
import { adminPath } from "../lib/admin-routes"
import { AdminHeader } from "./AdminHeader"
import { EnvironmentBanner } from "./EnvironmentBanner"
import { AdminCommandBarProvider } from "./AdminCommandBar"

/**
 * Routes that fill the frame below the nav (full width + height, no centered
 * box) instead of the default max-w-[1600px] padded box. OPT-IN — only the MoC
 * vertical page today (the "plant floor" treatment). Every other admin page is
 * unaffected: its <main> string is byte-identical to the pre-A.1 layout.
 */
function isFullBleedRoute(pathname: string): boolean {
  return /\/maps\/[^/]+/.test(pathname)
}

export function AdminLayout({ children }: { children: ReactNode }) {
  const { user, loading } = useAdminAuth()
  const { pathname } = useLocation()

  if (loading) {
    return <div className="p-8 text-center text-slate-500">Loading…</div>
  }
  if (!user) {
    return <Navigate to={adminPath("/login")} replace />
  }

  const fullBleed = isFullBleedRoute(pathname)

  return (
    <AdminCommandBarProvider>
      {/* Full-bleed routes get a flex column so <main> can flex-1 to fill the
          height below the nav. Non-full-bleed routes keep the EXACT pre-A.1
          shell + <main> (block parent, centered 1600 box) — byte-identical, so
          other admin pages are provably unaffected (the flex-col was what broke
          their <main> width when applied unconditionally). */}
      <div
        className={
          fullBleed
            ? "flex min-h-screen flex-col bg-slate-50"
            : "min-h-screen bg-slate-50"
        }
      >
        <EnvironmentBanner />
        <AdminHeader />
        {fullBleed ? (
          <main className="flex min-h-0 flex-1">{children}</main>
        ) : (
          <main className="px-6 py-6 max-w-[1600px] mx-auto">{children}</main>
        )}
      </div>
    </AdminCommandBarProvider>
  )
}
