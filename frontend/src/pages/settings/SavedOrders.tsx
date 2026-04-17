import { useCallback, useEffect, useMemo, useState } from "react"
import { Bookmark, Pencil, Trash2, Users, User as UserIcon } from "lucide-react"
import apiClient from "@/lib/api-client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

interface SavedOrder {
  id: string
  name: string
  workflow_id: string
  trigger_keywords: string[]
  product_type: string | null
  entry_intent: "order" | "quote"
  saved_fields: Record<string, unknown>
  scope: "user" | "company"
  use_count: number
  days_since_last_use: number | null
  created_by_user_id: string | null
  created_at: string | null
}

export default function SavedOrdersPage() {
  const [mine, setMine] = useState<SavedOrder[]>([])
  const [shared, setShared] = useState<SavedOrder[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<SavedOrder | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await apiClient.get<{ mine: SavedOrder[]; shared: SavedOrder[] }>(
        "/saved-orders",
      )
      setMine(data.mine || [])
      setShared(data.shared || [])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleDelete = async (so: SavedOrder) => {
    if (!confirm(`Delete saved order "${so.name}"?`)) return
    await apiClient.delete(`/saved-orders/${so.id}`)
    await load()
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-bold">
            <Bookmark className="h-7 w-7 text-indigo-600" />
            Saved Orders
          </h1>
          <p className="mt-1 text-muted-foreground">
            Templates that pre-fill the command bar when you type a trigger keyword.
          </p>
        </div>
      </div>

      <Section
        title="My Saved Orders"
        icon={<UserIcon className="h-4 w-4" />}
        rows={mine}
        loading={loading}
        onEdit={setEditing}
        onDelete={handleDelete}
        emptyHint="Save a template from the command bar overlay after creating any order."
      />

      <Section
        title="Team Saved Orders"
        icon={<Users className="h-4 w-4" />}
        rows={shared}
        loading={loading}
        onEdit={setEditing}
        onDelete={handleDelete}
        emptyHint="Templates shared with the whole team show up here."
      />

      {editing && (
        <EditSlideOver
          saved={editing}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null)
            await load()
          }}
        />
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────

function Section({
  title,
  icon,
  rows,
  loading,
  onEdit,
  onDelete,
  emptyHint,
}: {
  title: string
  icon: React.ReactNode
  rows: SavedOrder[]
  loading: boolean
  onEdit: (r: SavedOrder) => void
  onDelete: (r: SavedOrder) => void
  emptyHint: string
}) {
  return (
    <div>
      <h2 className="mb-2 flex items-center gap-2 text-lg font-semibold">
        {icon}
        {title}
        <span className="text-sm font-normal text-muted-foreground">
          ({rows.length})
        </span>
      </h2>
      {loading ? (
        <Card className="p-6 text-center text-muted-foreground">Loading…</Card>
      ) : rows.length === 0 ? (
        <Card className="p-6 text-center text-sm text-muted-foreground">
          {emptyHint}
        </Card>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {rows.map((r) => (
            <Card key={r.id} className="space-y-2 p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate font-semibold">{r.name}</p>
                  <p className="text-xs text-muted-foreground">
                    Used {r.use_count}×
                    {r.days_since_last_use !== null && ` · ${r.days_since_last_use}d ago`}
                    {r.product_type && ` · ${r.product_type}`}
                  </p>
                </div>
                <div className="flex flex-shrink-0 gap-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onEdit(r)}
                    title="Edit"
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onDelete(r)}
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4 text-rose-500" />
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap gap-1">
                {r.trigger_keywords.map((kw) => (
                  <Badge key={kw} variant="outline" className="text-[11px]">
                    {kw}
                  </Badge>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────

function EditSlideOver({
  saved,
  onClose,
  onSaved,
}: {
  saved: SavedOrder
  onClose: () => void
  onSaved: () => void
}) {
  const [name, setName] = useState(saved.name)
  const [keywordsText, setKeywordsText] = useState(saved.trigger_keywords.join(", "))
  const [scope, setScope] = useState<"user" | "company">(saved.scope)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const fieldEntries = useMemo(
    () => Object.entries(saved.saved_fields || {}),
    [saved.saved_fields],
  )

  const save = async () => {
    setSaving(true)
    setErr(null)
    try {
      const keywords = keywordsText
        .split(/[,\n]/)
        .map((k) => k.trim().toLowerCase())
        .filter(Boolean)
      await apiClient.patch(`/saved-orders/${saved.id}`, {
        name: name.trim(),
        trigger_keywords: keywords,
        scope,
      })
      onSaved()
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data
        ?.detail
      setErr(detail || "Could not save")
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1 bg-black/30" onClick={onClose} />
      <div className="w-[480px] overflow-y-auto bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">Edit Saved Order</h3>
          <button
            onClick={onClose}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Close
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Name
            </label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Trigger keywords (comma-separated)
            </label>
            <Input
              value={keywordsText}
              onChange={(e) => setKeywordsText(e.target.value)}
              placeholder="cement, reorder"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Scope
            </label>
            <div className="flex gap-2">
              <button
                onClick={() => setScope("user")}
                className={`flex-1 rounded-lg border px-3 py-2 text-xs font-medium ${
                  scope === "user"
                    ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                    : "border-gray-200 text-gray-500"
                }`}
              >
                Just me
              </button>
              <button
                onClick={() => setScope("company")}
                className={`flex-1 rounded-lg border px-3 py-2 text-xs font-medium ${
                  scope === "company"
                    ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                    : "border-gray-200 text-gray-500"
                }`}
              >
                Whole team
              </button>
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Pre-filled fields
            </label>
            <div className="space-y-1 rounded-lg border border-gray-200 bg-gray-50/50 p-3 text-xs">
              {fieldEntries.length === 0 ? (
                <p className="text-muted-foreground">No saved fields</p>
              ) : (
                fieldEntries.map(([k, v]) => (
                  <div key={k} className="flex gap-2">
                    <span className="w-32 flex-shrink-0 font-medium text-muted-foreground">
                      {k}
                    </span>
                    <span className="break-all text-gray-900">
                      {typeof v === "string" ? v : JSON.stringify(v)}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {err && (
          <div className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {err}
          </div>
        )}

        <div className="mt-6 flex gap-2">
          <Button variant="outline" className="flex-1" onClick={onClose}>
            Cancel
          </Button>
          <Button className="flex-1" onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </div>
  )
}
