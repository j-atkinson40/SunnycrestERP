/**
 * Phase R-1 — Runtime Editor entry: tenant + user picker.
 *
 * Rendered when the operator opens the runtime editor without
 * tenant + user search params. Once the operator picks a tenant via
 * the canonical TenantPicker (used by the visual editor scope
 * surfaces), they confirm with an optional user_id. Submitting calls
 * `POST /api/platform/impersonation/impersonate` which:
 *   - returns a 30-min tenant-realm impersonation token,
 *   - persists it via the platform impersonation banner contract
 *     (localStorage `access_token` / `tenant_slug` are managed by
 *     the existing `dual-token-client.ts` reads — the response also
 *     carries `tenant_slug` + `impersonated_user_id` we forward
 *     into the editor URL).
 *
 * On success, navigates to `/runtime-editor/?tenant=<slug>&user=<id>`
 * (or the path-prefixed variant when the admin tree is mounted under
 * `/bridgeable-admin/`). The shell on that route reads the search
 * params + the impersonation token from localStorage to render the
 * impersonated tenant route.
 *
 * Optional `user_id` field: when blank, the impersonate endpoint
 * picks the tenant's first admin (per ImpersonateRequest schema).
 */
import { useState } from "react"
import { useNavigate } from "react-router-dom"

import { TenantPicker, type TenantSummary } from "@/bridgeable-admin/components/TenantPicker"
import { adminApi } from "@/bridgeable-admin/lib/admin-api"
import { adminPath } from "@/bridgeable-admin/lib/admin-routes"


interface ImpersonateResponse {
  access_token: string
  token_type: string
  tenant_slug: string
  tenant_name: string
  impersonated_user_id: string
  impersonated_user_name: string
  expires_in_minutes: number
  session_id: string
}


export default function TenantUserPicker() {
  const navigate = useNavigate()
  const [tenant, setTenant] = useState<TenantSummary | null>(null)
  const [userId, setUserId] = useState("")
  const [reason, setReason] = useState("")
  const [isStarting, setIsStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleStart() {
    if (!tenant) {
      setError("Pick a tenant before starting the editor.")
      return
    }
    setIsStarting(true)
    setError(null)
    try {
      const response = await adminApi.post<ImpersonateResponse>(
        "/api/platform/impersonation/impersonate",
        {
          tenant_id: tenant.id,
          user_id: userId.trim() || null,
          reason: reason.trim() || "runtime-editor",
        },
      )
      const data = response.data

      // Persist the impersonation token via the same localStorage
      // keys the impersonation banner uses; tenant-side AuthProvider
      // picks it up automatically when TenantProviders mount.
      try {
        localStorage.setItem("access_token", data.access_token)
        localStorage.setItem("company_slug", data.tenant_slug)
        // Mark this as a runtime-editor impersonation session — the
        // shell reads this to know the editor instance owns lifecycle.
        localStorage.setItem(
          "runtime_editor_session",
          JSON.stringify({
            session_id: data.session_id,
            tenant_slug: data.tenant_slug,
            impersonated_user_id: data.impersonated_user_id,
          }),
        )
      } catch (e) {
        // eslint-disable-next-line no-console
        console.warn("[runtime-editor] localStorage write failed", e)
      }

      navigate(
        adminPath(
          `/runtime-editor/?tenant=${encodeURIComponent(data.tenant_slug)}&user=${encodeURIComponent(data.impersonated_user_id)}`,
        ),
      )
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error("[runtime-editor] impersonate failed", err)
      const detail =
        err instanceof Error ? err.message : "Failed to start impersonation."
      setError(detail)
    } finally {
      setIsStarting(false)
    }
  }

  return (
    <div
      className="mx-auto max-w-2xl px-6 py-12"
      data-testid="runtime-editor-picker"
    >
      <h1 className="text-h2 font-plex-serif text-content-strong">
        Open the runtime editor
      </h1>
      <p className="mt-2 text-body-sm text-content-muted">
        Select a tenant to render. The platform issues a 30-minute
        impersonation token; every commit through the inspector writes
        through your platform-admin credentials. Tenant-side mutations
        are read-only by default — the editor authors at platform /
        vertical / tenant scopes via the canonical visual editor
        services.
      </p>

      <div className="mt-8 flex flex-col gap-5">
        <div>
          <label className="mb-1 block text-caption font-medium text-content-strong">
            Tenant
          </label>
          <TenantPicker selected={tenant} onSelect={setTenant} />
        </div>

        <div>
          <label
            className="mb-1 block text-caption font-medium text-content-strong"
            htmlFor="runtime-editor-user-id"
          >
            User to impersonate (optional)
          </label>
          <input
            id="runtime-editor-user-id"
            type="text"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="Leave blank for tenant's first admin"
            className="w-full rounded-sm border border-border-base bg-surface-raised px-3 py-2 text-body-sm text-content-strong outline-none focus:border-accent"
            data-testid="runtime-editor-picker-user-id"
          />
        </div>

        <div>
          <label
            className="mb-1 block text-caption font-medium text-content-strong"
            htmlFor="runtime-editor-reason"
          >
            Reason (logged for audit)
          </label>
          <input
            id="runtime-editor-reason"
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. authoring vertical defaults for FH"
            className="w-full rounded-sm border border-border-base bg-surface-raised px-3 py-2 text-body-sm text-content-strong outline-none focus:border-accent"
            data-testid="runtime-editor-picker-reason"
          />
        </div>

        {error && (
          <div
            className="rounded-sm bg-status-error-muted px-3 py-2 text-caption text-status-error"
            data-testid="runtime-editor-picker-error"
          >
            {error}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={handleStart}
            disabled={!tenant || isStarting}
            className="rounded-sm bg-accent px-4 py-2 text-body-sm font-medium text-content-on-accent hover:bg-accent-hover disabled:opacity-50"
            data-testid="runtime-editor-picker-start"
          >
            {isStarting ? "Starting…" : "Start editing"}
          </button>
        </div>
      </div>
    </div>
  )
}
