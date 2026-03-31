// log-production.tsx
// Route: /console/operations/product-entry
// 3-step mobile-first production logging flow: VOICE → CONFIRM → SUCCESS

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronLeft, CheckCircle, Minus, Plus } from 'lucide-react'
import { toast } from 'sonner'
import apiClient from '@/lib/api-client'
import offlineQueue from '@/services/offline-queue'
import VoiceInputButton from '@/components/mobile/voice-input-button'
import type { Product } from '@/types/product'

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

type Step = 'voice' | 'manual' | 'confirm' | 'success'

// ─── Component ────────────────────────────────────────────────────────────────

export default function LogProduction() {
  const navigate = useNavigate()

  const [step, setStep] = useState<Step>('voice')
  const [products, setProducts] = useState<Product[]>([])
  const [voiceEntries, setVoiceEntries] = useState<VoiceEntry[]>([])
  const [unrecognized, setUnrecognized] = useState<string[]>([])
  const [isOffline, setIsOffline] = useState(!navigator.onLine)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Manual mode: map of product.id -> quantity
  const [manualQtys, setManualQtys] = useState<Record<string, number>>({})

  // Load products on mount
  useEffect(() => {
    apiClient
      .get<Product[]>('/products')
      .then((r) => setProducts(r.data))
      .catch(() => toast.error('Could not load products'))
  }, [])

  // Track online status
  useEffect(() => {
    const onOnline = () => setIsOffline(false)
    const onOffline = () => setIsOffline(true)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [])

  // Auto-navigate back after success
  useEffect(() => {
    if (step === 'success') {
      const t = setTimeout(() => navigate('/console/operations'), 3000)
      return () => clearTimeout(t)
    }
  }, [step, navigate])

  // ─── Voice result handler ──────────────────────────────────────────────────

  function handleVoiceResult(raw: Record<string, unknown>) {
    const result = raw as VoiceResult
    setVoiceEntries(result.entries ?? [])
    setUnrecognized(result.unrecognized ?? [])
    setStep('confirm')
  }

  // ─── Confirm step helpers ──────────────────────────────────────────────────

  function adjustQty(index: number, delta: number) {
    setVoiceEntries((prev) =>
      prev.map((e, i) =>
        i === index ? { ...e, quantity: Math.max(0, e.quantity + delta) } : e,
      ),
    )
  }

  function handleUnrecognizedProduct(
    e: React.ChangeEvent<HTMLSelectElement>,
    term: string,
  ) {
    const productId = e.target.value
    if (!productId) return
    const product = products.find((p) => p.id === productId)
    if (!product) return
    setVoiceEntries((prev) => [
      ...prev,
      { product_name: product.name, quantity: 1, matched_product_id: product.id },
    ])
    setUnrecognized((prev) => prev.filter((u) => u !== term))
  }

  // ─── Manual mode helpers ───────────────────────────────────────────────────

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
    setStep('confirm')
  }

  // ─── Submit ────────────────────────────────────────────────────────────────

  async function handleSubmit() {
    const validEntries = voiceEntries.filter((e) => e.quantity > 0)
    if (validEntries.length === 0) {
      toast.error('No quantities to submit')
      return
    }
    setIsSubmitting(true)
    const payload = {
      entries: validEntries.map((e) => ({
        product_id: e.matched_product_id,
        quantity: e.quantity,
        product_name: e.product_name,
      })),
    }

    try {
      if (navigator.onLine) {
        await apiClient.post('/operations-board/production-log/bulk', payload)
      } else {
        await offlineQueue.enqueue('production_log', payload as Record<string, unknown>)
      }
      setStep('success')
    } catch {
      toast.error('Failed to submit — saved offline')
      await offlineQueue.enqueue('production_log', payload as Record<string, unknown>)
      setStep('success')
    } finally {
      setIsSubmitting(false)
    }
  }

  // ─── Derived ───────────────────────────────────────────────────────────────

  const totalUnits = voiceEntries.reduce((sum, e) => sum + e.quantity, 0)
  const manualHasEntries = products.some((p) => (manualQtys[p.id] ?? 0) > 0)

  const productSlimList = products.map((p) => ({ id: p.id, name: p.name }))

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="mobile-page-container">
      <div className="max-w-lg mx-auto min-h-screen flex flex-col">

        {/* SUCCESS */}
        {step === 'success' && (
          <div className="flex-1 flex flex-col items-center justify-center bg-green-50 px-6">
            <CheckCircle className="h-24 w-24 text-green-500 mx-auto" />
            <h2 className="text-3xl font-bold text-center text-green-800 mt-4">
              Production logged
            </h2>
            <p className="text-center text-green-700 mt-2">
              {totalUnits} {totalUnits === 1 ? 'vault' : 'vaults'} ·{' '}
              {voiceEntries.filter((e) => e.quantity > 0).length} products
            </p>
            {isOffline && (
              <p className="text-amber-600 text-center text-sm mt-2">
                Queued for sync
              </p>
            )}
          </div>
        )}

        {/* VOICE */}
        {step === 'voice' && (
          <>
            {/* Header */}
            <div className="flex items-center gap-3 px-4 pt-safe pt-4 pb-4 border-b border-gray-100">
              <button
                onClick={() => navigate('/console/operations')}
                className="p-2 -ml-2 rounded-lg active:bg-gray-100"
                aria-label="Back"
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
                  onClick={() => setStep('manual')}
                  className="text-sm text-blue-600 underline"
                >
                  Or add manually
                </button>
              </div>
            </div>
          </>
        )}

        {/* MANUAL */}
        {step === 'manual' && (
          <>
            {/* Header */}
            <div className="flex items-center gap-3 px-4 pt-safe pt-4 pb-4 border-b border-gray-100">
              <button
                onClick={() => setStep('voice')}
                className="p-2 -ml-2 rounded-lg active:bg-gray-100"
                aria-label="Back"
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
                        qty > 0 ? 'border-blue-300 bg-blue-50' : 'border-gray-200'
                      }`}
                    >
                      <div className="flex-1 min-w-0 mr-4">
                        <div className="text-base font-medium truncate">
                          {product.name}
                        </div>
                        {product.sku && (
                          <div className="text-xs text-gray-400">{product.sku}</div>
                        )}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={() => adjustManualQty(product.id, -1)}
                          className="w-11 h-11 rounded-lg border border-gray-300 bg-white flex items-center justify-center active:bg-gray-100"
                          aria-label="Decrease"
                        >
                          <Minus className="h-4 w-4 text-gray-600" />
                        </button>
                        <span className="text-xl font-bold w-8 text-center tabular-nums">
                          {qty}
                        </span>
                        <button
                          onClick={() => adjustManualQty(product.id, 1)}
                          className="w-11 h-11 rounded-lg border border-gray-300 bg-white flex items-center justify-center active:bg-gray-100"
                          aria-label="Increase"
                        >
                          <Plus className="h-4 w-4 text-gray-600" />
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            <div className="px-4 pb-safe pb-6 pt-3 border-t border-gray-100 bg-white">
              <button
                onClick={submitManual}
                disabled={!manualHasEntries}
                className="mobile-primary-btn w-full bg-blue-600 text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Review & Submit
              </button>
            </div>
          </>
        )}

        {/* CONFIRM */}
        {step === 'confirm' && (
          <>
            {/* Header */}
            <div className="flex items-center gap-3 px-4 pt-safe pt-4 pb-4 border-b border-gray-100">
              <button
                onClick={() => setStep('voice')}
                className="p-2 -ml-2 rounded-lg active:bg-gray-100"
                aria-label="Back"
              >
                <ChevronLeft className="h-6 w-6 text-gray-600" />
              </button>
              <h1 className="text-xl font-bold">Log Production</h1>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-4">
              <h2 className="text-lg font-semibold mb-4">Here's what I heard:</h2>

              {voiceEntries.map((entry, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-4 bg-white rounded-xl border border-gray-200 mb-2"
                >
                  <div className="flex-1 min-w-0 mr-4">
                    <div className="font-semibold text-lg leading-tight">
                      {entry.product_name}
                    </div>
                    {entry.matched_product_id ? (
                      <div className="text-xs text-green-600 mt-0.5">
                        ✓ Matched
                      </div>
                    ) : (
                      <div className="text-xs text-amber-600 mt-0.5">
                        ⚠ Not matched
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <button
                      onClick={() => adjustQty(i, -1)}
                      className="w-10 h-10 rounded-lg border border-gray-300 bg-white flex items-center justify-center active:bg-gray-100"
                      aria-label="Decrease"
                    >
                      <Minus className="h-4 w-4 text-gray-600" />
                    </button>
                    <span className="text-2xl font-bold w-10 text-center tabular-nums">
                      {entry.quantity}
                    </span>
                    <button
                      onClick={() => adjustQty(i, 1)}
                      className="w-10 h-10 rounded-lg border border-gray-300 bg-white flex items-center justify-center active:bg-gray-100"
                      aria-label="Increase"
                    >
                      <Plus className="h-4 w-4 text-gray-600" />
                    </button>
                  </div>
                </div>
              ))}

              {unrecognized.length > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-4">
                  <p className="text-sm text-amber-800">
                    I didn&apos;t catch: {unrecognized.join(', ')}
                  </p>
                  {unrecognized.map((term) => (
                    <select
                      key={term}
                      className="mt-2 w-full border border-amber-300 rounded-lg p-3 text-base bg-white"
                      defaultValue=""
                      onChange={(e) => handleUnrecognizedProduct(e, term)}
                    >
                      <option value="">What was &ldquo;{term}&rdquo;?</option>
                      {products.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  ))}
                </div>
              )}
            </div>

            <div className="px-4 pb-safe pb-6 pt-3 border-t border-gray-100 bg-white space-y-2">
              <button
                onClick={handleSubmit}
                disabled={
                  isSubmitting ||
                  voiceEntries.filter((e) => e.quantity > 0).length === 0
                }
                className="mobile-primary-btn w-full bg-blue-600 text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting ? 'Submitting…' : 'Looks right — Submit'}
              </button>
              <button
                onClick={() => setStep('voice')}
                className="mobile-action-btn w-full border border-gray-300"
              >
                Start over
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
