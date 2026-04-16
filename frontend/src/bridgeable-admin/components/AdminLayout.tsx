import { ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { useAdminAuth } from "../lib/admin-auth-context"
import { AdminHeader } from "./AdminHeader"
import { EnvironmentBanner } from "./EnvironmentBanner"
import { AdminCommandBarProvider } from "./AdminCommandBar"

export function AdminLayout({ children }: { children: ReactNode }) {
  const { user, loading } = useAdminAuth()

  if (loading) {
    return <div className="p-8 text-center text-slate-500">Loading…</div>
  }
  if (!user) {
    return <Navigate to="/bridgeable-admin/login" replace />
  }

  return (
    <AdminCommandBarProvider>
      <div className="min-h-screen bg-slate-50">
        <EnvironmentBanner />
        <AdminHeader />
        <main className="px-6 py-6 max-w-[1600px] mx-auto">{children}</main>
      </div>
    </AdminCommandBarProvider>
  )
}
