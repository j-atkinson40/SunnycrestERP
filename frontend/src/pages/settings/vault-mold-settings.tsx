// vault-mold-settings.tsx
// Route: /settings/vault-molds
// Post-onboarding settings page for vault production capacity management.

import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Factory, Minus, Plus, Loader2, CheckCircle } from "lucide-react"

interface MoldConfig {
  id: string
  product_id: string
  product_name: string
  product_category: string
  daily_capacity: number
  is_active: boolean
  notes: string | null
  current_stock: number
  spare_covers: number
  spare_bases: number
}

export default function VaultMoldSettingsPage() {
  const navigate = useNavigate()
  const [configs, setConfigs] = useState<MoldConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editCapacity, setEditCapacity] = useState(0)
  const [editNotes, setEditNotes] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    apiClient
      .get<MoldConfig[]>("/vault-molds")
      .then((r) => setConfigs(r.data || []))
      .catch(() => toast.error("Could not load mold configurations"))
      .finally(() => setLoading(false))
  }, [])

  function startEdit(cfg: MoldConfig) {
    setEditingId(cfg.product_id)
    setEditCapacity(cfg.daily_capacity)
    setEditNotes(cfg.notes || "")
  }

  async function saveEdit(productId: string) {
    setSaving(true)
    try {
      await apiClient.patch(`/vault-molds/${productId}`, {
        product_id: productId,
        daily_capacity: editCapacity,
        is_active: true,
        notes: editNotes || null,
      })
      setConfigs((prev) =>
        prev.map((c) =>
          c.product_id === productId
            ? { ...c, daily_capacity: editCapacity, notes: editNotes || null }
            : c
        )
      )
      setEditingId(null)
      toast.success("Capacity updated")
    } catch {
      toast.error("Failed to save")
    } finally {
      setSaving(false)
    }
  }

  async function handleAssemble(productId: string, maxPairs: number) {
    const qty = Math.min(maxPairs, 1)
    try {
      const res = await apiClient.post(`/vault-molds/assemble/${productId}`, { quantity: qty })
      setConfigs((prev) =>
        prev.map((c) =>
          c.product_id === productId
            ? {
                ...c,
                current_stock: res.data.quantity_on_hand,
                spare_covers: res.data.spare_covers,
                spare_bases: res.data.spare_bases,
              }
            : c
        )
      )
      toast.success(`Assembled ${qty} complete vault(s)`)
    } catch {
      toast.error("Assembly failed")
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  const spareConfigs = configs.filter(
    (c) => (c.spare_covers > 0 || c.spare_bases > 0)
  )
  const totalCapacity = configs.reduce((s, c) => s + c.daily_capacity, 0)

  return (
    <div className="space-y-6 p-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Factory className="h-6 w-6 text-teal-600" />
            Vault Production Capacity
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Total daily capacity: {totalCapacity} vaults across {configs.length} products
          </p>
        </div>
        <button
          onClick={() => navigate("/onboarding/vault-molds")}
          className="text-sm text-teal-600 font-medium"
        >
          Full setup
        </button>
      </div>

      {/* Product configs */}
      <div className="space-y-3">
        {configs.map((cfg) => (
          <div
            key={cfg.product_id}
            className="bg-white rounded-lg border border-gray-200 p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-base">{cfg.product_name}</h3>
              {editingId !== cfg.product_id ? (
                <button
                  onClick={() => startEdit(cfg)}
                  className="text-sm text-blue-600 font-medium"
                >
                  Edit
                </button>
              ) : (
                <button
                  onClick={() => saveEdit(cfg.product_id)}
                  disabled={saving}
                  className="text-sm text-teal-600 font-medium"
                >
                  {saving ? "Saving…" : "Save"}
                </button>
              )}
            </div>

            {editingId === cfg.product_id ? (
              <div className="space-y-3">
                <div className="flex items-center gap-4">
                  <span className="text-sm text-gray-600">Daily capacity:</span>
                  <button
                    onClick={() => setEditCapacity(Math.max(1, editCapacity - 1))}
                    className="w-9 h-9 rounded-lg bg-gray-100 flex items-center justify-center"
                  >
                    <Minus className="h-4 w-4" />
                  </button>
                  <span className="text-2xl font-bold w-10 text-center tabular-nums">
                    {editCapacity}
                  </span>
                  <button
                    onClick={() => setEditCapacity(editCapacity + 1)}
                    className="w-9 h-9 rounded-lg bg-gray-100 flex items-center justify-center"
                  >
                    <Plus className="h-4 w-4" />
                  </button>
                </div>
                <textarea
                  placeholder="Notes (optional)"
                  value={editNotes}
                  onChange={(e) => setEditNotes(e.target.value)}
                  className="w-full p-2 border border-gray-200 rounded-lg text-sm resize-none h-16"
                />
              </div>
            ) : (
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <span>Capacity: <strong>{cfg.daily_capacity}/day</strong></span>
                <span>Stock: <strong>{cfg.current_stock}</strong></span>
                {cfg.notes && <span className="text-gray-400">· {cfg.notes}</span>}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Spare components section */}
      {spareConfigs.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3">Spare Components</h2>
          <div className="space-y-3">
            {spareConfigs.map((cfg) => {
              const pairs = Math.min(cfg.spare_covers, cfg.spare_bases)
              return (
                <div
                  key={`spare-${cfg.product_id}`}
                  className="bg-amber-50 border border-amber-200 rounded-lg p-4"
                >
                  <h3 className="font-semibold text-sm mb-2">{cfg.product_name}</h3>
                  <div className="flex gap-4 text-sm text-gray-700 mb-2">
                    <span>Spare covers: {cfg.spare_covers}</span>
                    <span>Spare bases: {cfg.spare_bases}</span>
                  </div>
                  {pairs > 0 && (
                    <button
                      onClick={() => handleAssemble(cfg.product_id, pairs)}
                      className="flex items-center gap-1 text-sm text-teal-600 font-medium"
                    >
                      <CheckCircle className="h-3.5 w-3.5" />
                      Assemble {pairs} vault{pairs !== 1 ? "s" : ""}
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {configs.length === 0 && (
        <div className="text-center py-12">
          <Factory className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500 mb-4">No mold configurations set up yet.</p>
          <button
            onClick={() => navigate("/onboarding/vault-molds")}
            className="bg-teal-600 text-white px-6 py-2 rounded-lg font-semibold text-sm"
          >
            Set up production capacity
          </button>
        </div>
      )}
    </div>
  )
}
