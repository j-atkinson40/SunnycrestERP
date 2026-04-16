import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Shield } from "lucide-react"
import { useAdminAuth } from "../lib/admin-auth-context"
import { EnvironmentBanner } from "../components/EnvironmentBanner"
import { getAdminEnvironment, setAdminEnvironment } from "../lib/admin-api"

export function AdminLogin() {
  const { login } = useAdminAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [env, setEnv] = useState(getAdminEnvironment())
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email, password)
      navigate("/bridgeable-admin")
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || "Login failed")
    } finally {
      setSubmitting(false)
    }
  }

  const switchEnv = (e: "production" | "staging") => {
    setEnv(e)
    setAdminEnvironment(e)
  }

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col">
      <EnvironmentBanner />
      <div className="flex-1 flex items-center justify-center px-4">
        <div className="bg-white rounded-lg shadow-2xl max-w-md w-full p-8">
          <div className="flex items-center gap-2 mb-6 justify-center">
            <Shield className="h-6 w-6 text-amber-500" />
            <h1 className="text-xl font-semibold text-slate-900">Bridgeable Admin</h1>
          </div>

          <div className="mb-4 text-xs text-slate-500 text-center">
            Environment:{" "}
            <button
              onClick={() => switchEnv("production")}
              className={`px-2 py-1 rounded ${env === "production" ? "bg-slate-800 text-white" : "bg-slate-100"}`}
            >
              Production
            </button>{" "}
            <button
              onClick={() => switchEnv("staging")}
              className={`px-2 py-1 rounded ${env === "staging" ? "bg-amber-500 text-white" : "bg-slate-100"}`}
            >
              Staging
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-3 py-2 border border-slate-300 rounded text-sm outline-none focus:border-slate-500"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-700 block mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-3 py-2 border border-slate-300 rounded text-sm outline-none focus:border-slate-500"
              />
            </div>
            {error && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
                {error}
              </div>
            )}
            <button
              type="submit"
              disabled={submitting}
              className="w-full py-2 bg-slate-900 text-white rounded text-sm hover:bg-slate-800 disabled:opacity-50"
            >
              {submitting ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
