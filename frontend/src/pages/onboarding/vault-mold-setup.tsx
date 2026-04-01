// vault-mold-setup.tsx
// Route: /onboarding/vault-molds
// Onboarding page for configuring vault production mold capacity.
// Only accessible when vault_fulfillment_mode = 'produce' or 'hybrid'.

import { useState, useEffect, useMemo } from "react"
import { useNavigate } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { ChevronLeft, Minus, Plus, Factory, Loader2 } from "lucide-react"

// ── Types ────────────────────────────────────────────────────────────────────

interface Product {
  id: string
  name: string
  product_line: string | null
  category_id: string | null
  is_active: boolean
}

interface MoldConfig {
  product_id: string
  daily_capacity: number
  is_active: boolean
  notes: string | null
}

interface ProductConfig {
  product: Product
  produces: boolean
  daily_capacity: number
  notes: string
}

// ── Component ────────────────────────────────────────────────────────────────

export default function VaultMoldSetupPage() {
  const navigate = useNavigate()
  const [configs, setConfigs] = useState<Map<string, ProductConfig>>(new Map())
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showNotes, setShowNotes] = useState<Set<string>>(new Set())

  // Load products and existing configs
  useEffect(() => {
    Promise.all([
      apiClient.get<Product[]>("/products"),
      apiClient.get<MoldConfig[]>("/vault-molds").catch(() => ({ data: [] })),
    ])
      .then(([prodRes, configRes]) => {
        // Filter to vault products only
        const vaultProducts = (prodRes.data || []).filter(
          (p) =>
            p.is_active &&
            (p.product_line?.toLowerCase().includes("vault") ||
              p.product_line?.toLowerCase().includes("burial") ||
              p.product_line?.toLowerCase().includes("urn"))
        )
        setProducts(vaultProducts)
        setExistingConfigs(configRes.data || [])

        // Build initial config map
        const configMap = new Map<string, ProductConfig>()
        const existingMap = new Map(
          (configRes.data || []).map((c: MoldConfig) => [c.product_id, c])
        )

        for (const product of vaultProducts) {
          const existing = existingMap.get(product.id)
          configMap.set(product.id, {
            product,
            produces: existing ? existing.is_active : true,
            daily_capacity: existing ? existing.daily_capacity : 1,
            notes: existing?.notes || "",
          })
        }
        setConfigs(configMap)
      })
      .catch(() => toast.error("Could not load products"))
      .finally(() => setLoading(false))
  }, [])

  // ── Config update helpers ─────────────────────────────────────────────

  function updateConfig(productId: string, updates: Partial<ProductConfig>) {
    setConfigs((prev) => {
      const next = new Map(prev)
      const current = next.get(productId)
      if (current) {
        next.set(productId, { ...current, ...updates })
      }
      return next
    })
  }

  function setAllProduce(value: boolean) {
    setConfigs((prev) => {
      const next = new Map(prev)
      for (const [id, cfg] of next) {
        next.set(id, { ...cfg, produces: value })
      }
      return next
    })
  }

  // ── Computed values ───────────────────────────────────────────────────

  const configList = useMemo(() => Array.from(configs.values()), [configs])

  const totalCapacity = useMemo(
    () =>
      configList
        .filter((c) => c.produces)
        .reduce((sum, c) => sum + c.daily_capacity, 0),
    [configList]
  )

  const producingCount = useMemo(
    () => configList.filter((c) => c.produces).length,
    [configList]
  )

  // ── Save ──────────────────────────────────────────────────────────────

  async function handleSave() {
    setSaving(true)
    try {
      const payload = configList
        .filter((c) => c.produces)
        .map((c) => ({
          product_id: c.product.id,
          daily_capacity: c.daily_capacity,
          is_active: true,
          notes: c.notes || null,
        }))

      await apiClient.post("/vault-molds", payload)
      toast.success("Vault production capacity saved")
      navigate("/onboarding")
    } catch {
      toast.error("Failed to save configuration")
    } finally {
      setSaving(false)
    }
  }

  // ── Loading state ─────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-50 pb-32">
      {/* Header */}
      <div className="bg-white border-b px-4 pt-4 pb-4">
        <button
          onClick={() => navigate("/onboarding")}
          className="flex items-center gap-1 text-sm text-gray-500 mb-3"
        >
          <ChevronLeft className="h-4 w-4" /> Back to checklist
        </button>
        <div className="flex items-center gap-2 mb-2">
          <Factory className="h-5 w-5 text-teal-600" />
          <h1 className="text-xl font-bold text-gray-900">
            Your vault production capacity
          </h1>
        </div>
        <p className="text-sm text-gray-600">
          Tell us which vaults you produce and how many you can pour per day.
          This makes production logging faster and helps track capacity.
        </p>
      </div>

      {/* Bulk actions */}
      <div className="px-4 py-3 flex gap-2">
        <button
          onClick={() => setAllProduce(true)}
          className="flex-1 py-2.5 bg-teal-600 text-white rounded-xl text-sm font-semibold"
        >
          We produce all vaults
        </button>
        <button
          onClick={() => setAllProduce(false)}
          className="flex-1 py-2.5 bg-gray-200 text-gray-700 rounded-xl text-sm font-semibold"
        >
          We buy all vaults
        </button>
      </div>

      {/* Product list */}
      <div className="px-4 space-y-3">
        {configList.map((cfg) => (
          <div
            key={cfg.product.id}
            className="bg-white rounded-xl border border-gray-200 p-4"
          >
            <h3 className="font-semibold text-base text-gray-900 mb-3">
              {cfg.product.name}
            </h3>

            {/* Yes/No toggle */}
            <p className="text-sm text-gray-600 mb-2">
              Do you produce this vault?
            </p>
            <div className="flex gap-2 mb-3">
              <button
                onClick={() =>
                  updateConfig(cfg.product.id, { produces: true })
                }
                className={`flex-1 py-2.5 rounded-xl text-sm font-semibold transition-colors ${
                  cfg.produces
                    ? "bg-teal-600 text-white"
                    : "bg-gray-100 text-gray-500"
                }`}
              >
                Yes, we pour this
              </button>
              <button
                onClick={() =>
                  updateConfig(cfg.product.id, { produces: false })
                }
                className={`flex-1 py-2.5 rounded-xl text-sm font-semibold transition-colors ${
                  !cfg.produces
                    ? "bg-gray-600 text-white"
                    : "bg-gray-100 text-gray-500"
                }`}
              >
                No, we buy it
              </button>
            </div>

            {/* Capacity input — only shown when produces = true */}
            {cfg.produces && (
              <>
                <p className="text-sm text-gray-600 mb-2">
                  Daily capacity (complete vaults):
                </p>
                <div className="flex items-center justify-center gap-4 mb-2">
                  <button
                    onClick={() =>
                      updateConfig(cfg.product.id, {
                        daily_capacity: Math.max(1, cfg.daily_capacity - 1),
                      })
                    }
                    className="w-12 h-12 rounded-xl bg-gray-100 flex items-center justify-center active:bg-gray-200"
                  >
                    <Minus className="h-5 w-5 text-gray-600" />
                  </button>
                  <span className="text-5xl font-bold text-gray-900 w-20 text-center tabular-nums">
                    {cfg.daily_capacity}
                  </span>
                  <button
                    onClick={() =>
                      updateConfig(cfg.product.id, {
                        daily_capacity: cfg.daily_capacity + 1,
                      })
                    }
                    className="w-12 h-12 rounded-xl bg-gray-100 flex items-center justify-center active:bg-gray-200"
                  >
                    <Plus className="h-5 w-5 text-gray-600" />
                  </button>
                </div>
                <p className="text-xs text-gray-400 text-center mb-2">
                  How many complete vaults (base + cover) can your molds produce
                  in one pour cycle?
                </p>

                {/* Notes toggle */}
                {!showNotes.has(cfg.product.id) ? (
                  <button
                    onClick={() =>
                      setShowNotes((prev) => new Set(prev).add(cfg.product.id))
                    }
                    className="text-xs text-teal-600 font-medium"
                  >
                    + Add notes
                  </button>
                ) : (
                  <textarea
                    placeholder='e.g. "Shares base mold with Salute"'
                    value={cfg.notes}
                    onChange={(e) =>
                      updateConfig(cfg.product.id, { notes: e.target.value })
                    }
                    className="w-full mt-1 p-2 border border-gray-200 rounded-lg text-sm resize-none h-16"
                  />
                )}
              </>
            )}
          </div>
        ))}
      </div>

      {/* Sticky bottom summary + save */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t shadow-lg px-4 py-3 z-40">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-600">
            Total daily capacity:
          </span>
          <span className="text-lg font-bold text-gray-900">
            {totalCapacity} vaults across {producingCount} products
          </span>
        </div>
        <button
          onClick={handleSave}
          disabled={saving || producingCount === 0}
          className="w-full py-4 bg-teal-600 text-white rounded-xl font-semibold text-base disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {saving && <Loader2 className="h-4 w-4 animate-spin" />}
          Save and Continue
        </button>
      </div>
    </div>
  )
}
