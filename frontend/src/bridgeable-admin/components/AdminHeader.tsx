import { useState } from "react"
import { ChevronDown, LogOut, Shield } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"
import {
  getAdminEnvironment,
  setAdminEnvironment,
  type AdminEnvironment,
} from "../lib/admin-api"
import { adminPath } from "../lib/admin-routes"
import { useAdminAuth } from "../lib/admin-auth-context"

export function AdminHeader() {
  const { user, logout } = useAdminAuth()
  const navigate = useNavigate()
  const [envOpen, setEnvOpen] = useState(false)
  const [userOpen, setUserOpen] = useState(false)
  const env = getAdminEnvironment()

  const switchEnv = (e: AdminEnvironment) => {
    setAdminEnvironment(e)
    setEnvOpen(false)
    window.location.reload()
  }

  return (
    <header className="bg-slate-900 text-white border-b border-slate-700">
      <div className="flex items-center justify-between px-6 py-3">
        <div className="flex items-center gap-6">
          <Link to={adminPath("/")} className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-amber-400" />
            <span className="font-semibold text-base">Bridgeable Admin</span>
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link to={adminPath("/")} className="hover:text-amber-300">Health</Link>
            <Link to={adminPath("/tenants")} className="hover:text-amber-300">Tenants</Link>
            <Link to={adminPath("/audit")} className="hover:text-amber-300">Audit</Link>
            <Link to={adminPath("/migrations")} className="hover:text-amber-300">Migrations</Link>
            <Link to={adminPath("/feature-flags")} className="hover:text-amber-300">Feature Flags</Link>
            <Link to={adminPath("/deployments")} className="hover:text-amber-300">Deployments</Link>
            <Link to={adminPath("/staging")} className="hover:text-amber-300">Staging</Link>
            <Link
              to={adminPath("/verticals")}
              className="hover:text-amber-300"
              data-testid="admin-nav-verticals"
            >
              Verticals
            </Link>
            <Link
              to={adminPath("/studio")}
              className="hover:text-amber-300"
              data-testid="admin-nav-visual-editor"
            >
              Studio
            </Link>
          </nav>
        </div>

        <div className="flex items-center gap-3">
          {/* Environment selector */}
          <div className="relative">
            <button
              onClick={() => setEnvOpen((o) => !o)}
              className={`px-3 py-1.5 rounded text-sm font-medium flex items-center gap-2 ${
                env === "staging"
                  ? "bg-amber-600 text-white"
                  : "bg-slate-700 text-white hover:bg-slate-600"
              }`}
            >
              {env === "staging" ? "Staging" : "Production"}
              <ChevronDown className="h-3.5 w-3.5" />
            </button>
            {envOpen && (
              <div className="absolute right-0 top-full mt-1 bg-white text-slate-900 rounded shadow-lg z-40 min-w-[160px]">
                <button
                  onClick={() => switchEnv("production")}
                  className={`w-full text-left px-3 py-2 hover:bg-slate-100 text-sm ${
                    env === "production" ? "font-semibold" : ""
                  }`}
                >
                  Production (default)
                </button>
                <button
                  onClick={() => switchEnv("staging")}
                  className={`w-full text-left px-3 py-2 hover:bg-slate-100 text-sm ${
                    env === "staging" ? "font-semibold" : ""
                  }`}
                >
                  Staging
                </button>
              </div>
            )}
          </div>

          {/* User menu */}
          <div className="relative">
            <button
              onClick={() => setUserOpen((o) => !o)}
              className="px-3 py-1.5 text-sm flex items-center gap-2 hover:text-amber-300"
            >
              {user ? `${user.first_name} ${user.last_name}` : "Guest"}
              <ChevronDown className="h-3.5 w-3.5" />
            </button>
            {userOpen && (
              <div className="absolute right-0 top-full mt-1 bg-white text-slate-900 rounded shadow-lg z-40 min-w-[160px]">
                <button
                  onClick={() => {
                    logout()
                    navigate(adminPath("/login"))
                  }}
                  className="w-full text-left px-3 py-2 hover:bg-slate-100 text-sm flex items-center gap-2"
                >
                  <LogOut className="h-3.5 w-3.5" /> Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
