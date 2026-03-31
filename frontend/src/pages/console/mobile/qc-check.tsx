// pages/console/mobile/qc-check.tsx
// Route: /console/operations/qc
// Mobile-first QC inspection flow: select product → card-by-card criteria → result + submit

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, CheckCircle, AlertTriangle, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import apiClient from '@/lib/api-client'
import offlineQueue from '@/services/offline-queue'
import VoiceInputButton from '@/components/mobile/voice-input-button'
import type { Product } from '@/types/product'
import '@/styles/mobile-console.css'

const QC_CRITERIA = [
  'Dimensional accuracy (within tolerance?)',
  'Surface finish (no cracks, voids, or honeycombing?)',
  'Gasket seat (clean, undamaged?)',
  'Hardware / lift points (secure?)',
  'Markings / labels (correct model, date?)',
]

interface CriterionResult {
  criterion: string
  passed: boolean | null
  note: string | null
}

type Disposition = 'rework' | 'scrap' | 'accept'

type Step = 'select-product' | 'criteria' | 'result' | 'success'

export default function QCCheck() {
  const navigate = useNavigate()

  const [step, setStep] = useState<Step>('select-product')
  const [products, setProducts] = useState<Product[]>([])
  const [loadingProducts, setLoadingProducts] = useState(true)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)

  // Criteria state
  const [currentIndex, setCurrentIndex] = useState(0)
  const [criteriaResults, setCriteriaResults] = useState<CriterionResult[]>(
    QC_CRITERIA.map((c) => ({ criterion: c, passed: null, note: null })),
  )
  const [showNoteFor, setShowNoteFor] = useState<number | null>(null)

  // Result state
  const [dispositions, setDispositions] = useState<Record<number, Disposition>>({})
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    apiClient
      .get<{ items: Product[] } | Product[]>('/products')
      .then((r) => {
        const data = r.data
        const items = Array.isArray(data) ? data : data.items ?? []
        setProducts(items.filter((p) => p.is_active))
      })
      .catch(() => toast.error('Could not load products'))
      .finally(() => setLoadingProducts(false))
  }, [])

  // --- Handlers ---

  function selectProduct(product: Product) {
    setSelectedProduct(product)
    // Reset criteria state when picking a new product
    setCriteriaResults(QC_CRITERIA.map((c) => ({ criterion: c, passed: null, note: null })))
    setCurrentIndex(0)
    setShowNoteFor(null)
    setDispositions({})
    setStep('criteria')
  }

  function handleAllPass() {
    setCriteriaResults(QC_CRITERIA.map((c) => ({ criterion: c, passed: true, note: null })))
    setStep('result')
  }

  function recordResult(index: number, passed: boolean) {
    setCriteriaResults((prev) => {
      const next = [...prev]
      next[index] = { ...next[index], passed }
      return next
    })

    if (!passed) {
      // Show note/voice capture for failures
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
    if (index < QC_CRITERIA.length - 1) {
      setCurrentIndex(index + 1)
    } else {
      setStep('result')
    }
  }

  function toggleDisposition(index: number, disposition: Disposition) {
    setDispositions((prev) => ({
      ...prev,
      [index]: prev[index] === disposition ? undefined! : disposition,
    }))
  }

  async function handleSubmit() {
    if (!selectedProduct) return
    setSubmitting(true)
    try {
      const payload = {
        product_id: selectedProduct.id,
        product_name: selectedProduct.name,
        results: criteriaResults,
        selected_dispositions: dispositions,
        submitted_at: new Date().toISOString(),
      }
      await offlineQueue.enqueue('qc_check', payload)
      setStep('success')
      setTimeout(() => navigate('/console/operations'), 3000)
    } catch {
      toast.error('Failed to save QC check')
    } finally {
      setSubmitting(false)
    }
  }

  const allPassed = criteriaResults.every((r) => r.passed === true)
  const failedItems = criteriaResults
    .map((r, i) => ({ ...r, index: i }))
    .filter((r) => r.passed === false)

  // --- Render ---

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
          <h1 className="text-xl font-bold text-gray-900">QC Check</h1>
        </div>

        {/* STEP 1: Select Product */}
        {step === 'select-product' && (
          <div>
            <p className="text-gray-500 mb-4">Select the product to inspect:</p>
            {loadingProducts ? (
              <div className="flex justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
              </div>
            ) : products.length === 0 ? (
              <p className="text-center text-gray-400 py-12">No products found.</p>
            ) : (
              <div>
                {products.map((product) => (
                  <button
                    key={product.id}
                    onClick={() => selectProduct(product)}
                    className="w-full text-left p-5 bg-white border-2 border-gray-200 rounded-xl mb-3 text-lg font-semibold hover:border-blue-400 transition-colors"
                  >
                    {product.name}
                    {product.sku && (
                      <span className="block text-sm font-normal text-gray-400 mt-1">
                        SKU: {product.sku}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* STEP 2: Criteria cards */}
        {step === 'criteria' && (
          <div>
            <p className="text-sm text-gray-500 mb-4">
              Inspecting: <span className="font-semibold text-gray-800">{selectedProduct?.name}</span>
            </p>

            {/* "All good" shortcut — shown before first criterion only */}
            {currentIndex === 0 && showNoteFor === null && (
              <>
                <button
                  onClick={handleAllPass}
                  className="w-full py-4 mb-4 border-2 border-green-200 bg-green-50 text-green-700 rounded-xl font-semibold text-base"
                >
                  ✓ All good — everything passes
                </button>
                <p className="text-center text-sm text-gray-400 mb-4">or go through each check:</p>
              </>
            )}

            {/* Note / voice capture for failed criterion */}
            {showNoteFor !== null ? (
              <div className="mobile-criterion-card bg-white border border-gray-200 shadow-sm">
                <p className="text-xs text-gray-400 mb-2">
                  Criterion {showNoteFor + 1} — FAILED
                </p>
                <h2 className="text-lg font-bold text-center mb-2">
                  {QC_CRITERIA[showNoteFor]}
                </h2>
                <p className="text-gray-500 text-sm text-center mb-6">
                  Add a note about the issue (optional)
                </p>
                <VoiceInputButton
                  context="qc_fail_note"
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
              /* Criterion card */
              <div className="mobile-criterion-card bg-white border border-gray-200 shadow-sm">
                <p className="text-xs text-gray-400 mb-4">
                  {currentIndex + 1} of {QC_CRITERIA.length}
                </p>
                <h2 className="text-xl font-bold text-center mb-8">
                  {QC_CRITERIA[currentIndex]}
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
              {QC_CRITERIA.map((_, i) => {
                const result = criteriaResults[i]
                return (
                  <div
                    key={i}
                    className={`w-2.5 h-2.5 rounded-full ${
                      result.passed === true
                        ? 'bg-green-500'
                        : result.passed === false
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

        {/* STEP 3: Result */}
        {step === 'result' && (
          <div>
            {/* Overall status banner */}
            <div
              className={`mobile-card flex items-center gap-3 ${
                allPassed ? 'bg-green-50 border-2 border-green-200' : 'bg-amber-50 border-2 border-amber-200'
              }`}
            >
              {allPassed ? (
                <>
                  <CheckCircle className="h-8 w-8 text-green-600 flex-shrink-0" />
                  <div>
                    <p className="font-bold text-green-800 text-lg">QC Passed</p>
                    <p className="text-green-700 text-sm">All {QC_CRITERIA.length} checks passed</p>
                  </div>
                </>
              ) : (
                <>
                  <AlertTriangle className="h-8 w-8 text-amber-600 flex-shrink-0" />
                  <div>
                    <p className="font-bold text-amber-800 text-lg">QC Issues Found</p>
                    <p className="text-amber-700 text-sm">
                      {failedItems.length} of {QC_CRITERIA.length} checks failed
                    </p>
                  </div>
                </>
              )}
            </div>

            {/* Per-criterion list */}
            <div className="mobile-card">
              <h3 className="font-bold text-gray-800 mb-3">Results</h3>
              {criteriaResults.map((r, i) => (
                <div key={i} className="flex items-start gap-3 py-2 border-b border-gray-100 last:border-0">
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

            {/* Disposition for failed items */}
            {failedItems.length > 0 && (
              <div className="mobile-card">
                <h3 className="font-bold text-gray-800 mb-3">Disposition for failed items</h3>
                {failedItems.map((item) => (
                  <div key={item.index} className="mb-4">
                    <p className="text-sm text-gray-600 mb-2 font-medium">{item.criterion}</p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => toggleDisposition(item.index, 'rework')}
                        style={{ minHeight: 52 }}
                        className={`flex-1 rounded-xl font-semibold text-sm transition-colors ${
                          dispositions[item.index] === 'rework'
                            ? 'bg-blue-600 text-white border-2 border-blue-600'
                            : 'bg-blue-50 text-blue-700 border-2 border-blue-200'
                        }`}
                      >
                        Rework
                      </button>
                      <button
                        onClick={() => toggleDisposition(item.index, 'scrap')}
                        style={{ minHeight: 52 }}
                        className={`flex-1 rounded-xl font-semibold text-sm transition-colors ${
                          dispositions[item.index] === 'scrap'
                            ? 'bg-red-600 text-white border-2 border-red-600'
                            : 'bg-red-50 text-red-700 border-2 border-red-200'
                        }`}
                      >
                        Scrap
                      </button>
                      <button
                        onClick={() => toggleDisposition(item.index, 'accept')}
                        style={{ minHeight: 52 }}
                        className={`flex-1 rounded-xl font-semibold text-sm transition-colors ${
                          dispositions[item.index] === 'accept'
                            ? 'bg-amber-500 text-white border-2 border-amber-500'
                            : 'bg-amber-50 text-amber-700 border-2 border-amber-200'
                        }`}
                      >
                        Accept
                      </button>
                    </div>
                  </div>
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
                'Submit QC Check'
              )}
            </button>
          </div>
        )}

        {/* STEP 4: Success */}
        {step === 'success' && (
          <div className="flex flex-col items-center justify-center min-h-[60vh] text-center gap-4">
            <CheckCircle className="h-20 w-20 text-green-500" />
            <h2 className="text-2xl font-bold text-gray-900">
              {allPassed ? 'QC Passed' : 'QC Check Saved'}
            </h2>
            <p className="text-gray-500">
              {selectedProduct?.name} — {allPassed ? 'all checks passed' : `${failedItems.length} issue(s) recorded`}
            </p>
            <p className="text-sm text-gray-400">Returning to Operations Board…</p>
          </div>
        )}
      </div>
    </div>
  )
}
