/**
 * External Accounts settings page
 *
 * Lets admins connect third-party service accounts used by
 * Playwright workflow automations (e.g. Uline, Grainger).
 * Credentials are stored encrypted server-side — never returned
 * to the client. This page only shows metadata (which fields are
 * saved, when last verified).
 */
import { useEffect, useState } from "react"
import {
  Shield, Plus, Trash2, CheckCircle, AlertCircle,
  RefreshCw, ChevronDown, ChevronUp, Lock, Eye, EyeOff,
  ExternalLink, Zap,
} from "lucide-react"
import apiClient from "@/lib/api-client"

// ─── Types ────────────────────────────────────────────────────────────

interface ExternalAccount {
  id: string
  service_name: string
  service_key: string
  credential_fields: string[]
  last_verified_at: string | null
  is_active: boolean
  created_at: string | null
}

interface AvailableScript {
  name: string
  service_key: string
  required_inputs: string[]
  outputs: string[]
}

// ─── Helpers ──────────────────────────────────────────────────────────

const SERVICE_META: Record<string, { label: string; url: string; credFields: string[] }> = {
  uline: {
    label: "Uline",
    url: "https://www.uline.com",
    credFields: ["username", "password"],
  },
  grainger: {
    label: "Grainger",
    url: "https://www.grainger.com",
    credFields: ["username", "password"],
  },
  staples: {
    label: "Staples Business",
    url: "https://www.staples.com",
    credFields: ["username", "password"],
  },
}

function timeAgo(iso: string | null): string {
  if (!iso) return "Never"
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 2) return "Just now"
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

// ─── Add/Edit credential form ─────────────────────────────────────────

function CredentialForm({
  serviceKey,
  serviceName,
  fields,
  onSave,
  onCancel,
  saving,
}: {
  serviceKey: string
  serviceName: string
  fields: string[]
  onSave: (creds: Record<string, string>) => void
  onCancel: () => void
  saving: boolean
}) {
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(fields.map((f) => [f, ""])),
  )
  const [show, setShow] = useState<Record<string, boolean>>({})

  const allFilled = fields.every((f) => (values[f] ?? "").trim() !== "")

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
      <div className="flex items-center gap-2">
        <Lock className="h-4 w-4 text-slate-400" />
        <span className="text-sm font-medium text-slate-700">
          Enter {serviceName} credentials
        </span>
      </div>

      <div className="space-y-3">
        {fields.map((field) => (
          <div key={field}>
            <label className="block text-xs font-medium text-slate-600 mb-1 capitalize">
              {field}
            </label>
            <div className="relative">
              <input
                type={field === "password" && !show[field] ? "password" : "text"}
                value={values[field] ?? ""}
                onChange={(e) =>
                  setValues((v) => ({ ...v, [field]: e.target.value }))
                }
                placeholder={field === "username" ? "your@email.com" : "••••••••"}
                className="w-full pr-10 pl-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                autoComplete="new-password"
              />
              {field === "password" && (
                <button
                  type="button"
                  onClick={() => setShow((s) => ({ ...s, [field]: !s[field] }))}
                  className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600"
                >
                  {show[field] ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="bg-blue-50 rounded-lg p-3 flex gap-2.5">
        <Shield className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
        <p className="text-xs text-blue-700">
          Credentials are encrypted with AES-256 before storage. They are
          never logged or returned to the browser after saving.
        </p>
      </div>

      <div className="flex gap-2 justify-end">
        <button
          onClick={onCancel}
          className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900"
        >
          Cancel
        </button>
        <button
          onClick={() => onSave(values)}
          disabled={!allFilled || saving}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save credentials"}
        </button>
      </div>
    </div>
  )
}

// ─── Account card ─────────────────────────────────────────────────────

function AccountCard({
  account,
  onUpdate,
  onDelete,
  onVerify,
}: {
  account: ExternalAccount
  onUpdate: (key: string, name: string) => void
  onDelete: (id: string) => void
  onVerify: (id: string) => Promise<void>
}) {
  const [expanded, setExpanded] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const meta = SERVICE_META[account.service_key]

  const isVerified = !!account.last_verified_at

  async function handleVerify() {
    setVerifying(true)
    try {
      await onVerify(account.id)
    } finally {
      setVerifying(false)
    }
  }

  async function handleDelete() {
    if (!confirm(`Remove ${account.service_name} credentials? Workflows using this service will stop working.`)) return
    setDeleting(true)
    onDelete(account.id)
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      <div className="flex items-center gap-4 px-5 py-4">
        {/* Status dot */}
        <div
          className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
            isVerified ? "bg-emerald-400" : "bg-amber-400"
          }`}
        />

        {/* Identity */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-900">
              {account.service_name}
            </span>
            {meta?.url && (
              <a
                href={meta.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-slate-400 hover:text-slate-600"
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Fields saved:{" "}
            <span className="font-medium text-slate-700">
              {account.credential_fields.join(", ")}
            </span>
          </p>
        </div>

        {/* Last verified badge */}
        <div className="text-right flex-shrink-0">
          {isVerified ? (
            <span className="inline-flex items-center gap-1 text-xs text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
              <CheckCircle className="h-3 w-3" />
              Verified {timeAgo(account.last_verified_at)}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-xs text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full">
              <AlertCircle className="h-3 w-3" />
              Not verified
            </span>
          )}
        </div>

        {/* Expand toggle */}
        <button
          onClick={() => setExpanded((e) => !e)}
          className="ml-1 p-1 text-slate-400 hover:text-slate-700"
        >
          {expanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </button>
      </div>

      {expanded && (
        <div className="border-t border-slate-100 px-5 py-3 bg-slate-50 flex gap-3 flex-wrap">
          <button
            onClick={handleVerify}
            disabled={verifying}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 px-3 py-1.5 rounded-lg hover:bg-slate-50 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${verifying ? "animate-spin" : ""}`} />
            {verifying ? "Verifying…" : "Mark as verified"}
          </button>
          <button
            onClick={() => onUpdate(account.service_key, account.service_name)}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 px-3 py-1.5 rounded-lg hover:bg-slate-50"
          >
            <Lock className="h-3.5 w-3.5" />
            Update credentials
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-red-600 bg-white border border-red-100 px-3 py-1.5 rounded-lg hover:bg-red-50 disabled:opacity-50 ml-auto"
          >
            <Trash2 className="h-3.5 w-3.5" />
            {deleting ? "Removing…" : "Remove"}
          </button>
        </div>
      )}
    </div>
  )
}

// ─── Add new service picker ────────────────────────────────────────────

function AddServicePanel({
  scripts,
  existingKeys,
  onAdd,
}: {
  scripts: AvailableScript[]
  existingKeys: Set<string>
  onAdd: (key: string, name: string) => void
}) {
  const available = Object.entries(SERVICE_META).filter(
    ([key]) => !existingKeys.has(key),
  )
  // Also include any scripts whose service isn't in SERVICE_META
  const scriptServices = scripts
    .filter((s) => !existingKeys.has(s.service_key) && !SERVICE_META[s.service_key])
    .map((s) => [s.service_key, { label: s.service_key, url: "", credFields: ["username", "password"] }] as [string, typeof SERVICE_META[string]])

  const allServices = [...available, ...scriptServices]

  if (allServices.length === 0) {
    return (
      <p className="text-sm text-slate-500 text-center py-6">
        All supported services are already connected.
      </p>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {allServices.map(([key, meta]) => (
        <button
          key={key}
          onClick={() => onAdd(key, meta.label)}
          className="flex items-center gap-3 p-4 rounded-xl border-2 border-dashed border-slate-200 hover:border-blue-400 hover:bg-blue-50 text-left transition group"
        >
          <div className="w-9 h-9 rounded-lg bg-slate-100 group-hover:bg-blue-100 flex items-center justify-center flex-shrink-0">
            <Zap className="h-4 w-4 text-slate-500 group-hover:text-blue-600" />
          </div>
          <div>
            <div className="text-sm font-medium text-slate-800">{meta.label}</div>
            {meta.url && (
              <div className="text-xs text-slate-400 truncate">{meta.url}</div>
            )}
          </div>
          <Plus className="h-4 w-4 text-slate-400 group-hover:text-blue-600 ml-auto" />
        </button>
      ))}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────

export default function ExternalAccountsPage() {
  const [accounts, setAccounts] = useState<ExternalAccount[]>([])
  const [scripts, setScripts] = useState<AvailableScript[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Form state
  const [addingKey, setAddingKey] = useState<string | null>(null)
  const [addingName, setAddingName] = useState<string>("")
  const [saving, setSaving] = useState(false)
  const [showAddPanel, setShowAddPanel] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    setError(null)
    try {
      const [accsRes, scriptsRes] = await Promise.all([
        apiClient.get("/external-accounts"),
        apiClient.get("/external-accounts/available-scripts"),
      ])
      setAccounts(accsRes.data)
      setScripts(scriptsRes.data)
    } catch {
      setError("Failed to load external accounts.")
    } finally {
      setLoading(false)
    }
  }

  async function handleSaveCredentials(
    serviceKey: string,
    serviceName: string,
    credentials: Record<string, string>,
  ) {
    setSaving(true)
    try {
      const res = await apiClient.post("/external-accounts", {
        service_key: serviceKey,
        service_name: serviceName,
        credentials,
      })
      setAccounts((prev) => {
        const idx = prev.findIndex((a) => a.service_key === serviceKey)
        if (idx >= 0) {
          const next = [...prev]
          next[idx] = res.data
          return next
        }
        return [...prev, res.data]
      })
      setAddingKey(null)
      setShowAddPanel(false)
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(msg ?? "Failed to save credentials.")
    } finally {
      setSaving(false)
    }
  }

  async function handleVerify(accountId: string) {
    const res = await apiClient.post(`/external-accounts/${accountId}/verify`)
    setAccounts((prev) =>
      prev.map((a) => (a.id === accountId ? res.data : a)),
    )
  }

  async function handleDelete(accountId: string) {
    await apiClient.delete(`/external-accounts/${accountId}`)
    setAccounts((prev) => prev.filter((a) => a.id !== accountId))
  }

  function startAdd(key: string, name: string) {
    setAddingKey(key)
    setAddingName(name)
    setShowAddPanel(false)
  }

  const existingKeys = new Set(accounts.map((a) => a.service_key))
  const addingMeta = addingKey ? (SERVICE_META[addingKey] ?? { label: addingName, url: "", credFields: ["username", "password"] }) : null

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">External Accounts</h1>
          <p className="text-sm text-slate-500 mt-1">
            Connect third-party service accounts for workflow automations.
            Credentials are AES-256 encrypted and never returned to the browser.
          </p>
        </div>
        <button
          onClick={() => { setShowAddPanel((v) => !v); setAddingKey(null) }}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 flex-shrink-0"
        >
          <Plus className="h-4 w-4" />
          Connect service
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Add service panel */}
      {showAddPanel && !addingKey && (
        <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
          <h2 className="text-sm font-semibold text-slate-900">Choose a service to connect</h2>
          <AddServicePanel
            scripts={scripts}
            existingKeys={existingKeys}
            onAdd={startAdd}
          />
        </div>
      )}

      {/* Credential entry form */}
      {addingKey && addingMeta && (
        <CredentialForm
          serviceKey={addingKey}
          serviceName={addingMeta.label}
          fields={addingMeta.credFields}
          onSave={(creds) => handleSaveCredentials(addingKey, addingMeta.label, creds)}
          onCancel={() => { setAddingKey(null); setShowAddPanel(false) }}
          saving={saving}
        />
      )}

      {/* Connected accounts list */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <RefreshCw className="h-5 w-5 text-slate-400 animate-spin" />
        </div>
      ) : accounts.length === 0 && !showAddPanel ? (
        <div className="rounded-xl border-2 border-dashed border-slate-200 text-center py-16 space-y-3">
          <div className="mx-auto w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center">
            <Zap className="h-6 w-6 text-slate-400" />
          </div>
          <p className="text-sm font-medium text-slate-700">No services connected yet</p>
          <p className="text-xs text-slate-400 max-w-xs mx-auto">
            Connect a service account to enable automated workflow steps like
            placing orders on Uline.
          </p>
          <button
            onClick={() => setShowAddPanel(true)}
            className="mt-2 inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 font-medium"
          >
            <Plus className="h-4 w-4" />
            Connect your first service
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {accounts.map((acc) => (
            <AccountCard
              key={acc.id}
              account={acc}
              onUpdate={startAdd}
              onDelete={handleDelete}
              onVerify={handleVerify}
            />
          ))}
        </div>
      )}

      {/* How it works */}
      <div className="rounded-xl border border-slate-100 bg-slate-50 p-5 space-y-3">
        <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
          How it works
        </h3>
        <ul className="space-y-2 text-sm text-slate-600">
          <li className="flex gap-2">
            <span className="text-slate-400 mt-0.5">1.</span>
            Connect a service account with your login credentials above.
          </li>
          <li className="flex gap-2">
            <span className="text-slate-400 mt-0.5">2.</span>
            Add a browser automation step to any workflow (e.g. "Place order on Uline").
          </li>
          <li className="flex gap-2">
            <span className="text-slate-400 mt-0.5">3.</span>
            When the workflow runs, Bridgeable logs in automatically, performs the action,
            and returns the result (order number, total, etc.) back to the workflow.
          </li>
          <li className="flex gap-2">
            <span className="text-slate-400 mt-0.5">4.</span>
            Steps marked "requires approval" will pause and ask you to confirm before
            taking any action on the external site.
          </li>
        </ul>
      </div>
    </div>
  )
}
