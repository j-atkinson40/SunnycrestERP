import { useEffect, useState } from "react"
import { AlertTriangle, X } from "lucide-react"
import { getAdminEnvironment, setAdminEnvironment, type AdminEnvironment } from "../lib/admin-api"

export function EnvironmentBanner() {
  const [env, setEnv] = useState<AdminEnvironment>(getAdminEnvironment())

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail as AdminEnvironment
      setEnv(detail)
    }
    window.addEventListener("admin-environment-changed", handler)
    return () => window.removeEventListener("admin-environment-changed", handler)
  }, [])

  if (env !== "staging") return null

  return (
    <div
      className="w-full bg-amber-500 text-black flex items-center justify-between px-4 py-2.5 border-b-2 border-amber-700 sticky top-0 z-50"
      role="alert"
    >
      <div className="flex items-center gap-3">
        <AlertTriangle className="h-5 w-5" />
        <span className="font-semibold">STAGING ENVIRONMENT</span>
        <span className="text-sm">— Changes here do not affect production</span>
      </div>
      <button
        onClick={() => {
          setAdminEnvironment("production")
          // Soft reload of the page after toggle
          window.location.reload()
        }}
        className="px-3 py-1 text-sm font-medium bg-amber-700 text-white rounded hover:bg-amber-800 flex items-center gap-1"
      >
        <X className="h-3.5 w-3.5" /> Exit staging
      </button>
    </div>
  )
}
