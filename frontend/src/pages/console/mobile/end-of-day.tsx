// pages/console/mobile/end-of-day.tsx
// Route: /console/operations/end-of-day
// End-of-day summary: auto-aggregates today's production, safety, receiving into a daily wrap-up.

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  CheckCircle,
  AlertCircle,
  Loader2,
  Package,
  ShieldCheck,
  StickyNote,
} from 'lucide-react'
import { toast } from 'sonner'
import apiClient from '@/lib/api-client'
import VoiceInputButton from '@/components/mobile/voice-input-button'
import '@/styles/mobile-console.css'

interface ProductionEntry {
  id: string
  product_name: string
  quantity: number
  created_at: string
}

interface SafetyIncident {
  id: string
  description: string
  created_at: string
}

interface PendingSummary {
  id: string
  description: string
}

type Step = 'summary' | 'success'

export default function EndOfDay() {
  const navigate = useNavigate()

  const [step, setStep] = useState<Step>('summary')
  const [loading, setLoading] = useState(true)

  const [productionEntries, setProductionEntries] = useState<ProductionEntry[]>([])
  const [incidentCount, setIncidentCount] = useState(0)
  const [pendingSummaries, setPendingSummaries] = useState<PendingSummary[]>([])
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [agentSummary, setAgentSummary] = useState('')

  useEffect(() => {
    let didCancel = false

    async function fetchData() {
      try {
        const [productionRes, incidentsRes, pendingRes] = await Promise.allSettled([
          apiClient.get<ProductionEntry[] | { items: ProductionEntry[] }>(
            '/operations-board/production-log/today',
          ),
          apiClient.get<SafetyIncident[] | { items: SafetyIncident[] }>(
            '/safety/incidents?created_today=true',
          ),
          apiClient.get<PendingSummary[] | { items: PendingSummary[] }>(
            '/operations-board/summaries/pending',
          ),
        ])

        if (didCancel) return

        if (productionRes.status === 'fulfilled') {
          const d = productionRes.value.data
          setProductionEntries(Array.isArray(d) ? d : d.items ?? [])
        }

        if (incidentsRes.status === 'fulfilled') {
          const d = incidentsRes.value.data
          const items = Array.isArray(d) ? d : d.items ?? []
          setIncidentCount(items.length)
        }

        if (pendingRes.status === 'fulfilled') {
          const d = pendingRes.value.data
          setPendingSummaries(Array.isArray(d) ? d : d.items ?? [])
        }
      } catch {
        // Non-fatal — show empty state
      } finally {
        if (!didCancel) setLoading(false)
      }
    }

    fetchData()
    return () => { didCancel = true }
  }, [])

  function handleNoteResult(result: Record<string, unknown>) {
    const text = (result.text as string) ?? (result.note as string) ?? ''
    if (text) {
      setNotes((prev) => (prev ? `${prev}\n${text}` : text))
    }
  }

  async function handleSubmit() {
    setSubmitting(true)
    try {
      const today = new Date().toISOString().slice(0, 10)
      const payload = {
        notes,
        entries: productionEntries,
        date: today,
        incident_count: incidentCount,
      }
      await apiClient.post('/operations-board/summary/submit', payload)
      const totalUnits = productionEntries.reduce((s, e) => s + (e.quantity ?? 0), 0)
      const incidentLine =
        incidentCount === 0
          ? 'No safety incidents.'
          : `${incidentCount} safety incident${incidentCount > 1 ? 's' : ''} on record.`
      setAgentSummary(
        `${totalUnits} vault${totalUnits !== 1 ? 's' : ''} produced today. ${incidentLine}${notes ? ' Notes recorded.' : ''}`,
      )
      setStep('success')
      setTimeout(() => navigate('/console/operations'), 3000)
    } catch {
      toast.error('Could not submit end-of-day summary. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const totalUnits = productionEntries.reduce((s, e) => s + (e.quantity ?? 0), 0)

  // Group production entries by product
  const productionByProduct = productionEntries.reduce<Record<string, number>>((acc, e) => {
    acc[e.product_name] = (acc[e.product_name] ?? 0) + (e.quantity ?? 0)
    return acc
  }, {})

  const unresolvedCount = pendingSummaries.length

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-lg mx-auto mobile-page-container pt-4">

        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <button
            onClick={() => navigate('/console/operations')}
            className="p-2 rounded-xl bg-white border border-gray-200 text-gray-600"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-gray-900">End of Day</h1>
            <p className="text-xs text-gray-400">
              {new Date().toLocaleDateString(undefined, {
                weekday: 'long',
                month: 'long',
                day: 'numeric',
              })}
            </p>
          </div>
        </div>

        {/* STEP 1: Summary + submit */}
        {step === 'summary' && (
          <div>
            {loading ? (
              <div className="flex justify-center py-16">
                <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
              </div>
            ) : (
              <>
                {/* Production section */}
                <div className="mobile-card">
                  <div className="flex items-center gap-2 mb-3">
                    {productionEntries.length > 0 ? (
                      <CheckCircle className="h-5 w-5 text-green-500" />
                    ) : (
                      <AlertCircle className="h-5 w-5 text-amber-500" />
                    )}
                    <h3 className="font-bold text-lg text-gray-900">Production</h3>
                  </div>

                  {productionEntries.length > 0 ? (
                    <>
                      <p className="text-gray-700 font-semibold mb-2">
                        {totalUnits} vault{totalUnits !== 1 ? 's' : ''} produced
                      </p>
                      <div className="space-y-1">
                        {Object.entries(productionByProduct).map(([name, qty]) => (
                          <div key={name} className="flex items-center justify-between text-sm">
                            <span className="text-gray-600 flex items-center gap-2">
                              <Package className="h-4 w-4 text-gray-400" />
                              {name}
                            </span>
                            <span className="font-semibold text-gray-800">{qty}</span>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <>
                      <p className="text-amber-600 mb-2">Nothing logged yet</p>
                      <button
                        onClick={() => navigate('/console/operations/product-entry')}
                        className="text-blue-600 text-sm underline"
                      >
                        Log production →
                      </button>
                    </>
                  )}
                </div>

                {/* Safety section */}
                <div className="mobile-card">
                  <div className="flex items-center gap-2 mb-3">
                    {incidentCount === 0 ? (
                      <CheckCircle className="h-5 w-5 text-green-500" />
                    ) : (
                      <AlertCircle className="h-5 w-5 text-amber-500" />
                    )}
                    <h3 className="font-bold text-lg text-gray-900">Safety</h3>
                  </div>
                  {incidentCount === 0 ? (
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="h-5 w-5 text-green-500" />
                      <p className="text-gray-700">No incidents today</p>
                    </div>
                  ) : (
                    <p className="text-amber-700 font-semibold">
                      {incidentCount} incident{incidentCount > 1 ? 's' : ''} recorded today
                    </p>
                  )}
                </div>

                {/* Notes section */}
                <div className="mobile-card">
                  <div className="flex items-center gap-2 mb-3">
                    <StickyNote className="h-5 w-5 text-blue-500" />
                    <h3 className="font-bold text-lg text-gray-900">Notes for tomorrow</h3>
                  </div>

                  <VoiceInputButton
                    context="inspection"
                    onResult={handleNoteResult}
                    label="Add a note"
                    className="mb-4"
                  />

                  <textarea
                    className="w-full mt-1 border border-gray-200 rounded-xl p-3 text-base min-h-[80px] focus:outline-none focus:ring-2 focus:ring-blue-300 resize-none"
                    placeholder="Any notes for the morning shift…"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                  />
                </div>

                {/* Submit */}
                <button
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="mobile-primary-btn bg-green-600 text-white disabled:opacity-60"
                >
                  {submitting ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="h-5 w-5 animate-spin" /> Submitting…
                    </span>
                  ) : unresolvedCount > 0 ? (
                    `Submit End of Day (${unresolvedCount} unresolved)`
                  ) : (
                    'Submit End of Day'
                  )}
                </button>
              </>
            )}
          </div>
        )}

        {/* STEP 2: Success */}
        {step === 'success' && (
          <div className="flex flex-col items-center justify-center min-h-[60vh] text-center gap-4">
            <CheckCircle className="h-20 w-20 text-green-500" />
            <h2 className="text-2xl font-bold text-gray-900">Day complete</h2>
            {agentSummary && (
              <p className="text-gray-600 max-w-xs leading-relaxed">{agentSummary}</p>
            )}
            <p className="text-sm text-gray-400">Returning to Operations Board…</p>
          </div>
        )}
      </div>
    </div>
  )
}
