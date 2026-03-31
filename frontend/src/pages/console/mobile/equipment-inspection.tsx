// pages/console/mobile/equipment-inspection.tsx
// Route: /console/operations/inspection
// Mobile-first equipment inspection: select equipment → card-by-card criteria → result + submit

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, CheckCircle, AlertTriangle, Loader2, Wrench } from 'lucide-react'
import { toast } from 'sonner'
import apiClient from '@/lib/api-client'
import offlineQueue from '@/services/offline-queue'
import VoiceInputButton from '@/components/mobile/voice-input-button'
import '@/styles/mobile-console.css'

interface EquipmentItem {
  id: string
  name: string
  inspection_type: 'daily' | 'weekly' | 'monthly'
}

const EQUIPMENT_LIST: EquipmentItem[] = [
  { id: 'forklift-1', name: 'Forklift #1', inspection_type: 'daily' },
  { id: 'forklift-2', name: 'Forklift #2', inspection_type: 'daily' },
  { id: 'overhead-crane', name: 'Overhead Crane', inspection_type: 'daily' },
  { id: 'concrete-mixer', name: 'Concrete Mixer', inspection_type: 'weekly' },
  { id: 'pressure-washer', name: 'Pressure Washer', inspection_type: 'weekly' },
  { id: 'air-compressor', name: 'Air Compressor', inspection_type: 'monthly' },
]

const INSPECTION_CRITERIA: Record<string, string[]> = {
  daily: [
    'Fluid levels OK?',
    'No visible damage?',
    'Safety features operational?',
    'Area clear of hazards?',
  ],
  weekly: [
    'All daily checks pass?',
    'Moving parts lubricated?',
    'Belts and filters inspected?',
  ],
  monthly: [
    'All weekly checks pass?',
    'Professional service due?',
    'Documentation up to date?',
  ],
}

const INSPECTION_TYPE_BADGE: Record<string, string> = {
  daily: 'bg-blue-100 text-blue-700',
  weekly: 'bg-purple-100 text-purple-700',
  monthly: 'bg-gray-100 text-gray-700',
}

interface CriterionResult {
  criterion: string
  passed: boolean | null
  note: string | null
}

type Step = 'select-equipment' | 'quick-option' | 'criteria' | 'result' | 'success'

export default function EquipmentInspection() {
  const navigate = useNavigate()

  const [step, setStep] = useState<Step>('select-equipment')
  const [selectedEquipment, setSelectedEquipment] = useState<EquipmentItem | null>(null)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [criteriaResults, setCriteriaResults] = useState<CriterionResult[]>([])
  const [showNoteFor, setShowNoteFor] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)

  function selectEquipment(equipment: EquipmentItem) {
    setSelectedEquipment(equipment)
    const criteria = INSPECTION_CRITERIA[equipment.inspection_type] ?? []
    setCriteriaResults(criteria.map((c) => ({ criterion: c, passed: null, note: null })))
    setCurrentIndex(0)
    setShowNoteFor(null)
    setStep('quick-option')
  }

  function handleAllPass() {
    if (!selectedEquipment) return
    const criteria = INSPECTION_CRITERIA[selectedEquipment.inspection_type] ?? []
    setCriteriaResults(criteria.map((c) => ({ criterion: c, passed: true, note: null })))
    setStep('result')
  }

  function startCriteriaFlow() {
    setCurrentIndex(0)
    setStep('criteria')
  }

  function recordResult(index: number, passed: boolean) {
    setCriteriaResults((prev) => {
      const next = [...prev]
      next[index] = { ...next[index], passed }
      return next
    })

    if (!passed) {
      setShowNoteFor(index)
    } else {
      advanceAfterRecord(index)
    }
  }

  function handleNoteResult(result: Record<string, unknown>) {
    const note = (result.note as string) ?? (result.text as string) ?? null
    if (showNoteFor !== null) {
      setCriteriaResults((prev) => {
        const next = [...prev]
        next[showNoteFor] = { ...next[showNoteFor], note }
        return next
      })
      const idx = showNoteFor
      setShowNoteFor(null)
      advanceAfterRecord(idx)
    }
  }

  function skipNote() {
    if (showNoteFor !== null) {
      const idx = showNoteFor
      setShowNoteFor(null)
      advanceAfterRecord(idx)
    }
  }

  function advanceAfterRecord(index: number) {
    if (index < criteriaResults.length - 1) {
      setCurrentIndex(index + 1)
    } else {
      setStep('result')
    }
  }

  async function handleSubmit() {
    if (!selectedEquipment) return
    setSubmitting(true)

    const allPassed = criteriaResults.every((r) => r.passed === true)
    const payload = {
      equipment_id: selectedEquipment.id,
      equipment_name: selectedEquipment.name,
      inspection_type: selectedEquipment.inspection_type,
      results: criteriaResults,
      passed: allPassed,
      notes: criteriaResults
        .filter((r) => r.note)
        .map((r) => `${r.criterion}: ${r.note}`)
        .join('\n') || null,
      inspected_at: new Date().toISOString(),
    }

    try {
      await apiClient.post('/safety/inspections', payload)
      setStep('success')
      setTimeout(() => navigate('/console/operations'), 3000)
    } catch {
      // Try offline queue
      try {
        await offlineQueue.enqueue('inspection', payload as Record<string, unknown>)
        setStep('success')
        setTimeout(() => navigate('/console/operations'), 3000)
      } catch {
        toast.error('Could not save inspection — please try again')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const allPassed = criteriaResults.length > 0 && criteriaResults.every((r) => r.passed === true)
  const failedItems = criteriaResults
    .map((r, i) => ({ ...r, index: i }))
    .filter((r) => r.passed === false)

  // Sort equipment: daily first, then weekly, then monthly
  const sortedEquipment = [...EQUIPMENT_LIST].sort((a, b) => {
    const order = { daily: 0, weekly: 1, monthly: 2 }
    return order[a.inspection_type] - order[b.inspection_type]
  })

  const criteria = selectedEquipment
    ? INSPECTION_CRITERIA[selectedEquipment.inspection_type] ?? []
    : []

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
          <h1 className="text-xl font-bold text-gray-900">Equipment Inspection</h1>
        </div>

        {/* STEP 1: Select Equipment */}
        {step === 'select-equipment' && (
          <div>
            <p className="text-gray-500 mb-4">Select equipment to inspect:</p>
            {sortedEquipment.map((eq) => (
              <button
                key={eq.id}
                onClick={() => selectEquipment(eq)}
                className="w-full text-left p-5 bg-white border-2 border-gray-200 rounded-xl mb-3 hover:border-blue-400 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Wrench className="h-5 w-5 text-gray-500" />
                    <span className="font-semibold text-lg text-gray-900">{eq.name}</span>
                  </div>
                  <span
                    className={`text-xs font-semibold px-2.5 py-1 rounded-full capitalize ${
                      INSPECTION_TYPE_BADGE[eq.inspection_type]
                    }`}
                  >
                    {eq.inspection_type}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* STEP 2: Quick option */}
        {step === 'quick-option' && selectedEquipment && (
          <div>
            <p className="text-sm text-gray-500 mb-4">
              Inspecting:{' '}
              <span className="font-semibold text-gray-800">{selectedEquipment.name}</span>
              <span
                className={`ml-2 text-xs font-semibold px-2 py-0.5 rounded-full capitalize ${
                  INSPECTION_TYPE_BADGE[selectedEquipment.inspection_type]
                }`}
              >
                {selectedEquipment.inspection_type}
              </span>
            </p>

            <button
              onClick={handleAllPass}
              className="w-full p-5 bg-green-50 border-2 border-green-200 text-green-700 rounded-xl font-bold text-lg mb-4"
            >
              ✓ All good — everything passes
            </button>
            <p className="text-center text-sm text-gray-400 mb-4">or inspect each item:</p>

            <button
              onClick={startCriteriaFlow}
              className="mobile-primary-btn bg-blue-600 text-white"
            >
              Start Inspection ({criteria.length} checks)
            </button>
          </div>
        )}

        {/* STEP 3: Criteria cards */}
        {step === 'criteria' && selectedEquipment && (
          <div>
            <p className="text-sm text-gray-500 mb-4">
              <span className="font-semibold text-gray-800">{selectedEquipment.name}</span>
            </p>

            {/* Note/voice capture for failed criterion */}
            {showNoteFor !== null ? (
              <div className="mobile-criterion-card bg-white border border-gray-200 shadow-sm">
                <p className="text-xs text-gray-400 mb-2">
                  Check {showNoteFor + 1} — FAILED
                </p>
                <h2 className="text-lg font-bold text-center mb-2">
                  {criteria[showNoteFor]}
                </h2>
                <p className="text-gray-500 text-sm text-center mb-6">
                  Describe the issue (optional)
                </p>
                <VoiceInputButton
                  context="inspection"
                  onResult={handleNoteResult}
                  label="Describe the issue"
                  className="mb-4"
                />
                <button
                  onClick={skipNote}
                  className="text-blue-600 text-sm underline"
                >
                  Skip — continue without note
                </button>
              </div>
            ) : (
              <div className="mobile-criterion-card bg-white border border-gray-200 shadow-sm">
                <p className="text-xs text-gray-400 mb-4">
                  {currentIndex + 1} of {criteria.length}
                </p>
                <h2 className="text-xl font-bold text-center mb-8">
                  {criteria[currentIndex]}
                </h2>

                <div className="flex gap-4 w-full">
                  <button
                    onClick={() => recordResult(currentIndex, true)}
                    className="mobile-pass-btn"
                  >
                    ✓ PASS
                  </button>
                  <button
                    onClick={() => recordResult(currentIndex, false)}
                    className="mobile-fail-btn"
                  >
                    ✗ FAIL
                  </button>
                </div>
              </div>
            )}

            {/* Progress dots */}
            <div className="flex justify-center gap-2 mt-4">
              {criteria.map((_, i) => {
                const result = criteriaResults[i]
                return (
                  <div
                    key={i}
                    className={`w-2.5 h-2.5 rounded-full ${
                      result?.passed === true
                        ? 'bg-green-500'
                        : result?.passed === false
                          ? 'bg-red-500'
                          : i === currentIndex
                            ? 'bg-blue-500'
                            : 'bg-gray-300'
                    }`}
                  />
                )
              })}
            </div>
          </div>
        )}

        {/* STEP 4: Result */}
        {step === 'result' && selectedEquipment && (
          <div>
            {/* Overall status banner */}
            <div
              className={`mobile-card flex items-center gap-3 ${
                allPassed
                  ? 'bg-green-50 border-2 border-green-200'
                  : 'bg-amber-50 border-2 border-amber-200'
              }`}
            >
              {allPassed ? (
                <>
                  <CheckCircle className="h-8 w-8 text-green-600 flex-shrink-0" />
                  <div>
                    <p className="font-bold text-green-800 text-lg">Inspection Passed</p>
                    <p className="text-green-700 text-sm">{selectedEquipment.name} — all checks passed</p>
                  </div>
                </>
              ) : (
                <>
                  <AlertTriangle className="h-8 w-8 text-amber-600 flex-shrink-0" />
                  <div>
                    <p className="font-bold text-amber-800 text-lg">Issues Found</p>
                    <p className="text-amber-700 text-sm">
                      {failedItems.length} of {criteria.length} checks failed
                    </p>
                  </div>
                </>
              )}
            </div>

            {/* Per-criterion result list */}
            <div className="mobile-card">
              <h3 className="font-bold text-gray-800 mb-3">Inspection Results</h3>
              {criteriaResults.map((r, i) => (
                <div
                  key={i}
                  className="flex items-start gap-3 py-2 border-b border-gray-100 last:border-0"
                >
                  <span className={`mt-0.5 text-lg ${r.passed ? 'text-green-600' : 'text-red-600'}`}>
                    {r.passed ? '✓' : '✗'}
                  </span>
                  <div className="flex-1">
                    <p className={`text-sm font-medium ${r.passed ? 'text-gray-700' : 'text-red-700'}`}>
                      {r.criterion}
                    </p>
                    {r.note && (
                      <p className="text-xs text-gray-500 mt-0.5 italic">{r.note}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Issue notes summary */}
            {failedItems.length > 0 && (
              <div className="mobile-card bg-amber-50 border-2 border-amber-200">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="h-5 w-5 text-amber-600" />
                  <p className="font-semibold text-amber-800">Issue Notes</p>
                </div>
                {failedItems.map((item, i) => (
                  <p key={i} className="text-sm text-amber-700 mb-1">
                    • {item.criterion}
                    {item.note ? `: ${item.note}` : ' — no note added'}
                  </p>
                ))}
              </div>
            )}

            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="mobile-primary-btn bg-blue-600 text-white disabled:opacity-60"
            >
              {submitting ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="h-5 w-5 animate-spin" /> Saving…
                </span>
              ) : (
                'Submit Inspection'
              )}
            </button>
          </div>
        )}

        {/* STEP 5: Success */}
        {step === 'success' && selectedEquipment && (
          <div className="flex flex-col items-center justify-center min-h-[60vh] text-center gap-4">
            <CheckCircle className="h-20 w-20 text-green-500" />
            <h2 className="text-2xl font-bold text-gray-900">
              {allPassed ? 'Inspection Passed' : 'Inspection Submitted'}
            </h2>
            <p className="text-gray-500">{selectedEquipment.name}</p>
            {!allPassed && failedItems.length > 0 && (
              <p className="text-amber-600 text-sm">
                {failedItems.length} issue{failedItems.length > 1 ? 's' : ''} recorded for review.
              </p>
            )}
            <p className="text-sm text-gray-400">Returning to Operations Board…</p>
          </div>
        )}
      </div>
    </div>
  )
}
