// log-production.tsx
// Route: /console/operations/product-entry
// Mobile-first production logging with mold-aware capacity tiles + partial pour support.

import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import {
  ChevronLeft,
  CheckCircle,
  Minus,
  Plus,
  Zap,
  AlertTriangle,
  Mic,
} from "lucide-react"
import { toast } from "sonner"
import apiClient from "@/lib/api-client"
import offlineQueue from "@/services/offline-queue"
import VoiceInputButton from "@/components/mobile/voice-input-button"
import type { Product } from "@/types/product"

// ─── Types ────────────────────────────────────────────────────────────────────

interface VoiceEntry {
  product_name: string
  quantity: number
  matched_product_id: string | null
}

interface VoiceResult {
  entries: VoiceEntry[]
  unrecognized: string[]
  notes: string | null
}

interface CapacityProduct {
  product_id: string
  product_name: string
  daily_capacity: number
  current_stock: number
  spare_covers: number
  spare_bases: number
}

interface PartialPour {
  product_id: string
  product_name: string
  component_type: "cover" | "base"
  quantity: number
  reason: string
}

interface SubmitEntry {
  product_id: string | null
  quantity: number
  product_name: string
  component_type: string
  component_reason: string | null
}

type Step = "entry" | "voice" | "manual" | "confirm" | "success"

// ─── Component ────────────────────────────────────────────────────────────────

export default function LogProduction() {
  const navigate = useNavigate()

  const [step, setStep] = useState<Step>("entry")
  const [products, setProducts] = useState<Product[]>([])
  const [capacityProducts, setCapacityProducts] = useState<CapacityProduct[]>([])
  const [hasMoldConfigs, setHasMoldConfigs] = useState(false)

  // Mold-aware quantities: productId -> quantity
  const [moldQtys, setMoldQtys] = useState<Record<string, number>>({})

  // Partial pours
  const [partialPours, setPartialPours] = useState<PartialPour[]>([])
  const [showPartialForm, setShowPartialForm] = useState(false)
  const [partialType, setPartialType] = useState<"cover" | "base">("cover")
  const [partialProductId, setPartialProductId] = useState("")
  const [partialQty, setPartialQty] = useState(1)
  const [partialReason, setPartialReason] = useState("replacement_damaged")

  // Voice/manual fallback state
  const [voiceEntries, setVoiceEntries] = useState<VoiceEntry[]>([])
  const [unrecognized, setUnrecognized] = useState<string[]>([])
  const [manualQtys, setManualQtys] = useState<Record<string, number>>({})

  const [isOffline, setIsOffline] = useState(!navigator.onLine)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [capacityWarnings, setCapacityWarnings] = useState<Record<string, string>>({})

  // All entries combined for submission
  const [allEntries, setAllEntries] = useState<SubmitEntry[]>([])

  // ─── Load data ────────────────────────────────────────────────────────────

  useEffect(() => {
    Promise.all([
      apiClient.get<Product[]>("/products"),
      apiClient.get<CapacityProduct[]>("/vault-molds/capacity-summary").catch(() => ({ data: [] })),
    ]).then(([prodRes, capRes]) => {
      setProducts(prodRes.data || [])
      const caps = capRes.data || []
      setCapacityProducts(caps)
      setHasMoldConfigs(caps.length > 0)

      if (caps.length > 0) {
        // Pre-select daily capacity for all products (full production day default)
        const initial: Record<string, number> = {}
        for (const cp of caps) {
          initial[cp.product_id] = cp.daily_capacity
        }
        setMoldQtys(initial)
        setStep("entry")
      } else {
        setStep("voice")
      }
    }).catch(() => toast.error("Could not load products"))
  }, [])

  useEffect(() => {
    const onOnline = () => setIsOffline(false)
    const onOffline = () => setIsOffline(true)
    window.addEventListener("online", onOnline)
    window.addEventListener("offline", onOffline)
    return () => {
      window.removeEventListener("online", onOnline)
      window.removeEventListener("offline", onOffline)
    }
  }, [])

  useEffect(() => {
    if (step === "success") {
      const t = setTimeout(() => navigate("/console/operations"), 3000)
      return () => clearTimeout(t)
    }
  }, [step, navigate])

  // ─── Mold capacity helpers ────────────────────────────────────────────────

  function setMoldQty(productId: string, qty: number) {
    const cap = capacityProducts.find((p) => p.product_id === productId)
    const maxCap = cap?.daily_capacity ?? 99

    if (qty > maxCap) {
      setCapacityWarnings((prev) => ({
        ...prev,
        [productId]: `Maximum capacity is ${maxCap}/day`,
      }))
      return
    }

    setCapacityWarnings((prev) => {
      const next = { ...prev }
      delete next[productId]
      return next
    })
    setMoldQtys((prev) => ({ ...prev, [productId]: Math.max(0, qty) }))
  }

  function setAllToCapacity() {
    const initial: Record<string, number> = {}
    for (const cp of capacityProducts) {
      initial[cp.product_id] = cp.daily_capacity
    }
    setMoldQtys(initial)
    setCapacityWarnings({})
  }

  // ─── Partial pour helpers ─────────────────────────────────────────────────

  function addPartialPour() {
    if (!partialProductId || partialQty <= 0) return
    const product = capacityProducts.find((p) => p.product_id === partialProductId)
    setPartialPours((prev) => [
      ...prev,
      {
        product_id: partialProductId,
        product_name: product?.product_name || "Unknown",
        component_type: partialType,
        quantity: partialQty,
        reason: partialReason,
      },
    ])
    setShowPartialForm(false)
    setPartialQty(1)
  }

  function removePartialPour(index: number) {
    setPartialPours((prev) => prev.filter((_, i) => i !== index))
  }

  // ─── Voice result handler ─────────────────────────────────────────────────

  function handleVoiceResult(raw: Record<string, unknown>) {
    const result = raw as unknown as VoiceResult
    const entries = result.entries ?? []

    // Validate against capacity
    if (hasMoldConfigs) {
      const warnings: Record<string, string> = {}
      for (const entry of entries) {
        if (!entry.matched_product_id) continue
        const cap = capacityProducts.find((p) => p.product_id === entry.matched_product_id)
        if (cap && entry.quantity > cap.daily_capacity) {
          warnings[entry.matched_product_id] =
            `${entry.product_name}: ${entry.quantity} exceeds capacity of ${cap.daily_capacity}/day`
        }
      }
      if (Object.keys(warnings).length > 0) {
        setCapacityWarnings(warnings)
      }
    }

    setVoiceEntries(entries)
    setUnrecognized(result.unrecognized ?? [])
    setStep("confirm")
  }

  // ─── Build confirm entries ────────────────────────────────────────────────

  function prepareConfirm() {
    const entries: SubmitEntry[] = []

    if (hasMoldConfigs) {
      for (const cp of capacityProducts) {
        const qty = moldQtys[cp.product_id] ?? 0
        if (qty > 0) {
          entries.push({
            product_id: cp.product_id,
            quantity: qty,
            product_name: cp.product_name,
            component_type: "complete",
            component_reason: null,
          })
        }
      }
    } else {
      for (const e of voiceEntries) {
        if (e.quantity > 0) {
          entries.push({
            product_id: e.matched_product_id,
            quantity: e.quantity,
            product_name: e.product_name,
            component_type: "complete",
            component_reason: null,
          })
        }
      }
    }

    // Add partial pours
    for (const pp of partialPours) {
      entries.push({
        product_id: pp.product_id,
        quantity: pp.quantity,
        product_name: pp.product_name,
        component_type: pp.component_type,
        component_reason: pp.reason,
      })
    }

    setAllEntries(entries)
    setStep("confirm")
  }

  // ─── Manual mode helpers ──────────────────────────────────────────────────

  function adjustManualQty(productId: string, delta: number) {
    setManualQtys((prev) => ({
      ...prev,
      [productId]: Math.max(0, (prev[productId] ?? 0) + delta),
    }))
  }

  function submitManual() {
    const entries = products
      .filter((p) => (manualQtys[p.id] ?? 0) > 0)
      .map((p) => ({
        product_name: p.name,
        quantity: manualQtys[p.id],
        matched_product_id: p.id,
      }))
    if (entries.length === 0) return
    setVoiceEntries(entries)
    setUnrecognized([])
    setStep("confirm")
  }

  // ─── Submit ───────────────────────────────────────────────────────────────

  async function handleSubmit() {
    const entries = allEntries.length > 0 ? allEntries : voiceEntries
      .filter((e) => e.quantity > 0)
      .map((e) => ({
        product_id: e.matched_product_id,
        quantity: e.quantity,
        product_name: e.product_name,
        component_type: "complete" as const,
        component_reason: null,
      }))

    if (entries.length === 0) {
      toast.error("No quantities to submit")
      return
    }

    setIsSubmitting(true)
    const payload = {
      entries: entries.map((e) => ({
        product_id: e.product_id,
        quantity: e.quantity,
        product_name_raw: e.product_name,
        component_type: e.component_type,
        component_reason: e.component_reason,
      })),
    }

    try {
      if (navigator.onLine) {
        await apiClient.post("/operations-board/production-log/bulk", payload.entries)
      } else {
        await offlineQueue.enqueue("production_log", payload as Record<string, unknown>)
      }
      setStep("success")
    } catch {
      toast.error("Failed to submit — saved offline")
      await offlineQueue.enqueue("production_log", payload as Record<string, unknown>)
      setStep("success")
    } finally {
      setIsSubmitting(false)
    }
  }

  // ─── Derived ──────────────────────────────────────────────────────────────

  const totalComplete = hasMoldConfigs
    ? Object.values(moldQtys).reduce((s, q) => s + q, 0)
    : voiceEntries.reduce((s, e) => s + e.quantity, 0)
  const totalPartial = partialPours.reduce((s, p) => s + p.quantity, 0)
  const hasCapacityErrors = Object.keys(capacityWarnings).length > 0
  const hasEntries = totalComplete > 0 || totalPartial > 0

  const productSlimList = products.map((p) => ({ id: p.id, name: p.name }))

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="mobile-page-container">
      <div className="max-w-lg mx-auto min-h-screen flex flex-col">

        {/* SUCCESS */}
        {step === "success" && (
          <div className="flex-1 flex flex-col items-center justify-center bg-green-50 px-6">
            <CheckCircle className="h-24 w-24 text-green-500 mx-auto" />
            <h2 className="text-3xl font-bold text-center text-green-800 mt-4">
              Production logged
            </h2>
            <p className="text-center text-green-700 mt-2">
              {totalComplete > 0 && `${totalComplete} complete vault${totalComplete !== 1 ? "s" : ""}`}
              {totalComplete > 0 && totalPartial > 0 && " + "}
              {totalPartial > 0 && `${totalPartial} partial pour${totalPartial !== 1 ? "s" : ""}`}
            </p>
            {isOffline && (
              <p className="text-amber-600 text-center text-sm mt-2">Queued for sync</p>
            )}
          </div>
        )}

        {/* MOLD-AWARE ENTRY */}
        {step === "entry" && hasMoldConfigs && (
          <>
            <div className="flex items-center gap-3 px-4 pt-4 pb-4 border-b border-gray-100">
              <button
                onClick={() => navigate("/console/operations")}
                className="p-2 -ml-2 rounded-lg active:bg-gray-100"
              >
                <ChevronLeft className="h-6 w-6 text-gray-600" />
              </button>
              <h1 className="text-xl font-bold">Log Production</h1>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-4 pb-48">
              {/* Full production day shortcut */}
              <button
                onClick={setAllToCapacity}
                className="w-full mb-4 p-4 bg-teal-50 border border-teal-200 rounded-xl text-left"
              >
                <div className="flex items-center gap-2">
                  <Zap className="h-5 w-5 text-teal-600" />
                  <span className="font-semibold text-teal-800">Full production day</span>
                </div>
                <p className="text-sm text-teal-700 mt-1">All molds ran at capacity</p>
              </button>

              {/* Capacity tiles per product */}
              <div className="space-y-3">
                {capacityProducts.map((cp) => {
                  const qty = moldQtys[cp.product_id] ?? 0
                  const warning = capacityWarnings[cp.product_id]
                  const atCapacity = qty === cp.daily_capacity

                  return (
                    <div
                      key={cp.product_id}
                      className="bg-white rounded-xl border border-gray-200 p-4"
                    >
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="font-semibold text-base">{cp.product_name}</h3>
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                          atCapacity
                            ? "bg-green-100 text-green-700"
                            : "bg-gray-100 text-gray-600"
                        }`}>
                          capacity: {cp.daily_capacity}/day
                        </span>
                      </div>

                      {/* Number selector */}
                      <div className="flex items-center justify-center gap-4">
                        <button
                          onClick={() => setMoldQty(cp.product_id, qty - 1)}
                          className="w-12 h-12 rounded-xl bg-gray-100 flex items-center justify-center active:bg-gray-200"
                        >
                          <Minus className="h-5 w-5 text-gray-600" />
                        </button>
                        <span className="text-5xl font-bold w-20 text-center tabular-nums">
                          {qty}
                        </span>
                        <button
                          onClick={() => setMoldQty(cp.product_id, qty + 1)}
                          className="w-12 h-12 rounded-xl bg-gray-100 flex items-center justify-center active:bg-gray-200"
                        >
                          <Plus className="h-5 w-5 text-gray-600" />
                        </button>
                      </div>

                      {warning && (
                        <p className="text-red-600 text-sm mt-2 flex items-center gap-1">
                          <AlertTriangle className="h-3.5 w-3.5" /> {warning}
                        </p>
                      )}

                      <p className="text-xs text-gray-400 text-center mt-2">
                        Stock: {cp.current_stock} on hand
                      </p>
                    </div>
                  )
                })}
              </div>

              {/* Voice fallback */}
              <div className="mt-4 text-center">
                <button
                  onClick={() => setStep("voice")}
                  className="text-sm text-blue-600 flex items-center gap-1 justify-center"
                >
                  <Mic className="h-3.5 w-3.5" /> Or use voice
                </button>
              </div>

              {/* Partial pour section */}
              <div className="mt-6 pt-4 border-t border-gray-200">
                <p className="text-sm text-gray-500 mb-2">Replacement component?</p>
                {partialPours.map((pp, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between bg-amber-50 border border-amber-200 rounded-xl p-3 mb-2"
                  >
                    <div>
                      <span className="font-medium text-sm">{pp.product_name}</span>
                      <span className="text-xs text-amber-700 ml-2">
                        {pp.component_type} only x{pp.quantity}
                      </span>
                    </div>
                    <button
                      onClick={() => removePartialPour(i)}
                      className="text-xs text-red-600 font-medium"
                    >
                      Remove
                    </button>
                  </div>
                ))}

                {!showPartialForm ? (
                  <button
                    onClick={() => {
                      setShowPartialForm(true)
                      if (capacityProducts.length > 0 && !partialProductId) {
                        setPartialProductId(capacityProducts[0].product_id)
                      }
                    }}
                    className="text-sm text-teal-600 font-medium"
                  >
                    + Log partial pour
                  </button>
                ) : (
                  <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-3">
                    <h4 className="font-semibold text-sm">Partial pour</h4>

                    {/* Component type */}
                    <div className="flex gap-2">
                      <button
                        onClick={() => setPartialType("cover")}
                        className={`flex-1 py-2 rounded-lg text-sm font-medium ${
                          partialType === "cover"
                            ? "bg-teal-600 text-white"
                            : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        Cover only
                      </button>
                      <button
                        onClick={() => setPartialType("base")}
                        className={`flex-1 py-2 rounded-lg text-sm font-medium ${
                          partialType === "base"
                            ? "bg-teal-600 text-white"
                            : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        Base only
                      </button>
                    </div>

                    {/* Product */}
                    <select
                      value={partialProductId}
                      onChange={(e) => setPartialProductId(e.target.value)}
                      className="w-full border border-gray-200 rounded-lg p-2.5 text-sm"
                    >
                      {capacityProducts.map((cp) => (
                        <option key={cp.product_id} value={cp.product_id}>
                          {cp.product_name}
                        </option>
                      ))}
                    </select>

                    {/* Quantity */}
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-gray-600">Qty:</span>
                      <button
                        onClick={() => setPartialQty(Math.max(1, partialQty - 1))}
                        className="w-9 h-9 rounded-lg bg-gray-100 flex items-center justify-center"
                      >
                        <Minus className="h-4 w-4" />
                      </button>
                      <span className="text-lg font-bold w-8 text-center">{partialQty}</span>
                      <button
                        onClick={() => setPartialQty(partialQty + 1)}
                        className="w-9 h-9 rounded-lg bg-gray-100 flex items-center justify-center"
                      >
                        <Plus className="h-4 w-4" />
                      </button>
                    </div>

                    {/* Reason */}
                    <div className="space-y-1">
                      {[
                        { value: "replacement_damaged", label: "Replacing damaged component" },
                        { value: "spare_stock", label: "Building spare stock" },
                        { value: "other", label: "Other" },
                      ].map((r) => (
                        <label key={r.value} className="flex items-center gap-2 text-sm">
                          <input
                            type="radio"
                            name="partial-reason"
                            checked={partialReason === r.value}
                            onChange={() => setPartialReason(r.value)}
                            className="accent-teal-600"
                          />
                          {r.label}
                        </label>
                      ))}
                    </div>

                    <div className="flex gap-2">
                      <button
                        onClick={addPartialPour}
                        className="flex-1 py-2 bg-teal-600 text-white rounded-lg text-sm font-semibold"
                      >
                        Add to log
                      </button>
                      <button
                        onClick={() => setShowPartialForm(false)}
                        className="flex-1 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm font-semibold"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Bottom bar */}
            <div className="fixed bottom-0 left-0 right-0 bg-white border-t shadow-lg px-4 py-3 z-40">
              <button
                onClick={prepareConfirm}
                disabled={!hasEntries || hasCapacityErrors}
                className="w-full py-4 bg-blue-600 text-white rounded-xl font-semibold text-base disabled:opacity-50 flex items-center justify-center gap-2"
              >
                Review & Submit ({totalComplete + totalPartial} vaults)
              </button>
            </div>
          </>
        )}

        {/* VOICE (fallback when no mold configs, or user chose voice) */}
        {step === "voice" && (
          <>
            <div className="flex items-center gap-3 px-4 pt-4 pb-4 border-b border-gray-100">
              <button
                onClick={() => hasMoldConfigs ? setStep("entry") : navigate("/console/operations")}
                className="p-2 -ml-2 rounded-lg active:bg-gray-100"
              >
                <ChevronLeft className="h-6 w-6 text-gray-600" />
              </button>
              <h1 className="text-xl font-bold">Log Production</h1>
            </div>

            <div className="flex-1 flex flex-col px-6 py-4">
              <h2 className="text-2xl font-bold text-center mt-8 mb-2">
                What did you pour today?
              </h2>
              <p className="text-gray-500 text-center mb-8">
                Tap the mic and tell me what was produced
              </p>

              <div className="flex justify-center">
                <VoiceInputButton
                  context="production_log"
                  onResult={handleVoiceResult}
                  availableProducts={productSlimList}
                />
              </div>

              <div className="mt-8 text-center">
                <button
                  onClick={() => setStep("manual")}
                  className="text-sm text-blue-600 underline"
                >
                  Or add manually
                </button>
              </div>
            </div>
          </>
        )}

        {/* MANUAL */}
        {step === "manual" && (
          <>
            <div className="flex items-center gap-3 px-4 pt-4 pb-4 border-b border-gray-100">
              <button
                onClick={() => setStep("voice")}
                className="p-2 -ml-2 rounded-lg active:bg-gray-100"
              >
                <ChevronLeft className="h-6 w-6 text-gray-600" />
              </button>
              <h1 className="text-xl font-bold">Log Production</h1>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-4">
              <p className="text-gray-500 text-sm mb-4">
                Set quantities for products produced today.
              </p>
              <div className="space-y-2">
                {products.map((product) => {
                  const qty = manualQtys[product.id] ?? 0
                  return (
                    <div
                      key={product.id}
                      className={`flex items-center justify-between p-4 bg-white rounded-xl border ${
                        qty > 0 ? "border-blue-300 bg-blue-50" : "border-gray-200"
                      }`}
                    >
                      <div className="flex-1 min-w-0 mr-4">
                        <div className="text-base font-medium truncate">{product.name}</div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={() => adjustManualQty(product.id, -1)}
                          className="w-11 h-11 rounded-lg border border-gray-300 bg-white flex items-center justify-center active:bg-gray-100"
                        >
                          <Minus className="h-4 w-4 text-gray-600" />
                        </button>
                        <span className="text-xl font-bold w-8 text-center tabular-nums">
                          {qty}
                        </span>
                        <button
                          onClick={() => adjustManualQty(product.id, 1)}
                          className="w-11 h-11 rounded-lg border border-gray-300 bg-white flex items-center justify-center active:bg-gray-100"
                        >
                          <Plus className="h-4 w-4 text-gray-600" />
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            <div className="px-4 pb-6 pt-3 border-t border-gray-100 bg-white">
              <button
                onClick={submitManual}
                disabled={!products.some((p) => (manualQtys[p.id] ?? 0) > 0)}
                className="mobile-primary-btn w-full bg-blue-600 text-white disabled:opacity-50"
              >
                Review & Submit
              </button>
            </div>
          </>
        )}

        {/* CONFIRM */}
        {step === "confirm" && (
          <>
            <div className="flex items-center gap-3 px-4 pt-4 pb-4 border-b border-gray-100">
              <button
                onClick={() => hasMoldConfigs ? setStep("entry") : setStep("voice")}
                className="p-2 -ml-2 rounded-lg active:bg-gray-100"
              >
                <ChevronLeft className="h-6 w-6 text-gray-600" />
              </button>
              <h1 className="text-xl font-bold">Confirm Production</h1>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-4">
              {/* Complete vault entries */}
              {allEntries.filter((e) => e.component_type === "complete").map((entry, i) => (
                <div
                  key={`c-${i}`}
                  className="flex items-center justify-between p-4 bg-white rounded-xl border border-gray-200 mb-2"
                >
                  <div>
                    <span className="font-semibold text-lg">{entry.product_name}</span>
                    <span className="text-xs text-green-600 ml-2">complete</span>
                  </div>
                  <span className="text-2xl font-bold tabular-nums">x{entry.quantity}</span>
                </div>
              ))}

              {/* Voice-based entries (when no mold configs) */}
              {allEntries.length === 0 && voiceEntries.map((entry, i) => (
                <div
                  key={`v-${i}`}
                  className="flex items-center justify-between p-4 bg-white rounded-xl border border-gray-200 mb-2"
                >
                  <div>
                    <span className="font-semibold text-lg">{entry.product_name}</span>
                    {entry.matched_product_id ? (
                      <span className="text-xs text-green-600 ml-2">matched</span>
                    ) : (
                      <span className="text-xs text-amber-600 ml-2">unmatched</span>
                    )}
                  </div>
                  <span className="text-2xl font-bold tabular-nums">x{entry.quantity}</span>
                </div>
              ))}

              {/* Partial pour entries */}
              {allEntries.filter((e) => e.component_type !== "complete").map((entry, i) => (
                <div
                  key={`p-${i}`}
                  className="flex items-center justify-between p-4 bg-amber-50 rounded-xl border border-amber-200 mb-2"
                >
                  <div>
                    <span className="font-semibold text-base">{entry.product_name}</span>
                    <span className="text-xs text-amber-700 ml-2">
                      {entry.component_type} only
                    </span>
                    {entry.component_reason && (
                      <p className="text-xs text-gray-500 mt-0.5">
                        {entry.component_reason.replace(/_/g, " ")}
                      </p>
                    )}
                  </div>
                  <span className="text-xl font-bold tabular-nums">x{entry.quantity}</span>
                </div>
              ))}

              {/* Unrecognized (voice mode) */}
              {unrecognized.length > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-4">
                  <p className="text-sm text-amber-800">
                    Not recognized: {unrecognized.join(", ")}
                  </p>
                </div>
              )}
            </div>

            <div className="px-4 pb-6 pt-3 border-t border-gray-100 bg-white space-y-2">
              <button
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="mobile-primary-btn w-full bg-blue-600 text-white disabled:opacity-50"
              >
                {isSubmitting ? "Submitting…" : "Looks right — Submit"}
              </button>
              <button
                onClick={() => hasMoldConfigs ? setStep("entry") : setStep("voice")}
                className="mobile-action-btn w-full border border-gray-300"
              >
                Edit quantities
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
