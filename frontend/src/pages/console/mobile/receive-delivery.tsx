// pages/console/mobile/receive-delivery.tsx
// Route: /console/operations/receive  AND  /console/operations/receive/:poId
// Mobile-first PO receiving flow: select PO → count items → confirm → success

import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Package, CheckCircle, Loader2, AlertTriangle } from 'lucide-react'
import { toast } from 'sonner'
import apiClient from '@/lib/api-client'
import VoiceInputButton from '@/components/mobile/voice-input-button'
import '@/styles/mobile-console.css'

interface POLineItem {
  id: string
  product_name: string
  quantity_ordered: number
  quantity_received: number
}

interface ExpectedPO {
  id: string
  po_number: string
  vendor_name: string
  total_amount: number
  expected_delivery_date: string | null
  status: string
  lines?: POLineItem[]
}

interface LineState {
  lineId: string
  product_name: string
  quantity_ordered: number
  receivedQty: number
  hasIssue: boolean
  issueNote: string | null
}

type Step = 'select-po' | 'count-items' | 'confirm' | 'success'

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'TBD'
  try {
    return new Date(dateStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  } catch {
    return dateStr
  }
}

export default function ReceiveDelivery() {
  const navigate = useNavigate()
  const { poId } = useParams<{ poId?: string }>()

  const [step, setStep] = useState<Step>(poId ? 'count-items' : 'select-po')
  const [openPOs, setOpenPOs] = useState<ExpectedPO[]>([])
  const [loadingPOs, setLoadingPOs] = useState(!poId)
  const [selectedPO, setSelectedPO] = useState<ExpectedPO | null>(null)
  const [lineStates, setLineStates] = useState<LineState[]>([])
  const [currentLineIndex, setCurrentLineIndex] = useState(0)
  const [showIssue, setShowIssue] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [receivedCount, setReceivedCount] = useState(0)

  // Load open POs if no poId provided
  useEffect(() => {
    if (poId) return
    apiClient
      .get<ExpectedPO[]>('/purchase-orders?status=approved,sent,partial')
      .then((r) => setOpenPOs(Array.isArray(r.data) ? r.data : []))
      .catch(() => toast.error('Could not load purchase orders'))
      .finally(() => setLoadingPOs(false))
  }, [poId])

  // If poId is provided, load that PO directly
  useEffect(() => {
    if (!poId) return
    apiClient
      .get<ExpectedPO>(`/purchase-orders/${poId}`)
      .then((r) => {
        initPO(r.data)
      })
      .catch(() => toast.error('Could not load purchase order'))
  }, [poId])

  function initPO(po: ExpectedPO) {
    setSelectedPO(po)
    const lines: LineState[] = (po.lines ?? []).map((line) => ({
      lineId: line.id,
      product_name: line.product_name,
      quantity_ordered: line.quantity_ordered,
      receivedQty: line.quantity_ordered, // default to expected qty
      hasIssue: false,
      issueNote: null,
    }))
    // If no lines, create a placeholder so the UI still works
    if (lines.length === 0) {
      lines.push({
        lineId: 'unknown',
        product_name: 'Items',
        quantity_ordered: 0,
        receivedQty: 0,
        hasIssue: false,
        issueNote: null,
      })
    }
    setLineStates(lines)
    setCurrentLineIndex(0)
    setStep('count-items')
  }

  function selectPO(po: ExpectedPO) {
    initPO(po)
  }

  function adjustQty(delta: number) {
    setLineStates((prev) => {
      const next = [...prev]
      const current = next[currentLineIndex]
      next[currentLineIndex] = {
        ...current,
        receivedQty: Math.max(0, current.receivedQty + delta),
      }
      return next
    })
  }

  function handleAllGood() {
    setLineStates((prev) => {
      const next = [...prev]
      next[currentLineIndex] = {
        ...next[currentLineIndex],
        hasIssue: false,
        issueNote: null,
      }
      return next
    })
    handleNext()
  }

  function handleNext() {
    setShowIssue(false)
    if (currentLineIndex < lineStates.length - 1) {
      setCurrentLineIndex((i) => i + 1)
    } else {
      setStep('confirm')
    }
  }

  function handleIssueResult(result: Record<string, unknown>) {
    const note = (result.note as string) ?? (result.text as string) ?? null
    setLineStates((prev) => {
      const next = [...prev]
      next[currentLineIndex] = {
        ...next[currentLineIndex],
        hasIssue: true,
        issueNote: note,
      }
      return next
    })
    setShowIssue(false)
  }

  async function handleCompleteReceiving() {
    if (!selectedPO) return
    setSubmitting(true)
    try {
      const payload = {
        lines: lineStates.map((ls) => ({
          line_id: ls.lineId,
          quantity_received: ls.receivedQty,
          has_issue: ls.hasIssue,
          issue_note: ls.issueNote,
        })),
        received_at: new Date().toISOString(),
      }
      await apiClient.post(`/purchase-orders/${selectedPO.id}/receive`, payload)
      setReceivedCount(lineStates.reduce((sum, ls) => sum + ls.receivedQty, 0))
      setStep('success')
      setTimeout(() => navigate('/console/operations'), 3000)
    } catch {
      toast.error('Failed to record receiving. Saving offline…')
      // Fall back to offline queue
      try {
        await import('@/services/offline-queue').then((m) =>
          m.default.enqueue('receiving', {
            po_id: selectedPO.id,
            lines: lineStates.map((ls) => ({
              line_id: ls.lineId,
              quantity_received: ls.receivedQty,
              has_issue: ls.hasIssue,
              issue_note: ls.issueNote,
            })),
            received_at: new Date().toISOString(),
          }),
        )
        setReceivedCount(lineStates.reduce((sum, ls) => sum + ls.receivedQty, 0))
        setStep('success')
        setTimeout(() => navigate('/console/operations'), 3000)
      } catch {
        toast.error('Could not save — please try again')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const currentLine = lineStates[currentLineIndex]
  const isLastItem = currentLineIndex === lineStates.length - 1
  const issueItems = lineStates.filter((ls) => ls.hasIssue)

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
          <h1 className="text-xl font-bold text-gray-900">Receive Delivery</h1>
        </div>

        {/* STEP 1: Select PO */}
        {step === 'select-po' && (
          <div>
            <p className="text-gray-500 mb-4">Select the incoming delivery:</p>
            {loadingPOs ? (
              <div className="flex justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
              </div>
            ) : openPOs.length === 0 ? (
              <div className="mobile-card text-center py-8">
                <Package className="h-10 w-10 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500">No open purchase orders found.</p>
              </div>
            ) : (
              <div>
                {openPOs.map((po) => (
                  <button
                    key={po.id}
                    onClick={() => selectPO(po)}
                    className="w-full text-left p-5 bg-white border-2 border-gray-200 rounded-xl mb-3 hover:border-blue-400 transition-colors"
                  >
                    <div className="flex items-center gap-3 mb-1">
                      <Package className="h-5 w-5 text-blue-600 flex-shrink-0" />
                      <span className="font-bold text-lg">{po.vendor_name}</span>
                    </div>
                    <p className="text-gray-500">PO #{po.po_number}</p>
                    <p className="text-gray-500 text-sm">
                      Expected: {formatDate(po.expected_delivery_date)}
                    </p>
                    <div className="mt-3">
                      <span className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-semibold">
                        Receive This →
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* STEP 2: Count Items */}
        {step === 'count-items' && currentLine && (
          <div>
            {selectedPO && (
              <p className="text-sm text-gray-500 mb-4">
                <span className="font-semibold text-gray-800">{selectedPO.vendor_name}</span>
                {' — '}PO #{selectedPO.po_number}
              </p>
            )}

            {/* Line item counter card */}
            <div className="mobile-card">
              <div className="flex items-center justify-between mb-1">
                <h2 className="text-xl font-bold">{currentLine.product_name}</h2>
                <span className="text-xs text-gray-400">
                  {currentLineIndex + 1} / {lineStates.length}
                </span>
              </div>
              <p className="text-gray-500 mb-6">Expected: {currentLine.quantity_ordered}</p>

              {/* Qty stepper */}
              <div className="flex items-center justify-center gap-6 mb-6">
                <button
                  onClick={() => adjustQty(-1)}
                  className="w-16 h-16 bg-gray-100 rounded-xl text-2xl font-bold text-gray-700 active:bg-gray-200"
                >
                  −
                </button>
                <span className="text-5xl font-bold w-16 text-center">
                  {currentLine.receivedQty}
                </span>
                <button
                  onClick={() => adjustQty(+1)}
                  className="w-16 h-16 bg-gray-100 rounded-xl text-2xl font-bold text-gray-700 active:bg-gray-200"
                >
                  +
                </button>
              </div>

              {/* All good / Report issue */}
              <div className="flex gap-3">
                <button
                  onClick={handleAllGood}
                  className="flex-1 py-4 bg-green-50 border-2 border-green-200 text-green-700 rounded-xl font-semibold"
                >
                  ✓ All good
                </button>
                <button
                  onClick={() => setShowIssue(true)}
                  className="flex-1 py-4 bg-amber-50 border-2 border-amber-200 text-amber-700 rounded-xl font-semibold"
                >
                  Report issue
                </button>
              </div>
            </div>

            {/* Issue voice capture */}
            {showIssue && (
              <div className="mobile-card">
                <p className="text-sm font-semibold text-gray-700 mb-3">Describe the issue:</p>
                <VoiceInputButton
                  context="inspection"
                  onResult={handleIssueResult}
                  label="Describe the issue"
                  className="mb-3"
                />
                <button
                  onClick={() => setShowIssue(false)}
                  className="text-sm text-gray-400 underline w-full text-center"
                >
                  Cancel
                </button>
              </div>
            )}

            {/* Navigation */}
            <div className="flex gap-3 mt-4">
              {currentLineIndex > 0 && (
                <button
                  onClick={() => { setShowIssue(false); setCurrentLineIndex((i) => i - 1) }}
                  className="flex-1 mobile-action-btn bg-gray-100 text-gray-700"
                >
                  ← Previous
                </button>
              )}
              <button
                onClick={handleNext}
                className="flex-1 mobile-action-btn bg-blue-600 text-white"
              >
                {isLastItem ? 'Review →' : 'Next →'}
              </button>
            </div>
          </div>
        )}

        {/* STEP 3: Confirm */}
        {step === 'confirm' && selectedPO && (
          <div>
            <div className="mobile-card">
              <h3 className="font-bold text-gray-800 text-lg mb-1">{selectedPO.vendor_name}</h3>
              <p className="text-gray-500 text-sm mb-4">PO #{selectedPO.po_number}</p>

              {lineStates.map((ls, i) => (
                <div
                  key={i}
                  className={`flex items-center justify-between py-3 border-b border-gray-100 last:border-0 ${
                    ls.hasIssue ? 'text-amber-700' : 'text-gray-700'
                  }`}
                >
                  <div>
                    <p className="font-medium">{ls.product_name}</p>
                    {ls.hasIssue && ls.issueNote && (
                      <p className="text-xs text-amber-600 mt-0.5 italic">{ls.issueNote}</p>
                    )}
                    {ls.hasIssue && !ls.issueNote && (
                      <p className="text-xs text-amber-600 mt-0.5">Issue reported</p>
                    )}
                  </div>
                  <span className="font-bold text-lg">{ls.receivedQty}</span>
                </div>
              ))}
            </div>

            {issueItems.length > 0 && (
              <div className="mobile-card bg-amber-50 border-2 border-amber-200">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="h-5 w-5 text-amber-600" />
                  <p className="font-semibold text-amber-800">
                    {issueItems.length} item{issueItems.length > 1 ? 's' : ''} with issues
                  </p>
                </div>
                {issueItems.map((ls, i) => (
                  <p key={i} className="text-sm text-amber-700">
                    • {ls.product_name}{ls.issueNote ? `: ${ls.issueNote}` : ''}
                  </p>
                ))}
              </div>
            )}

            <button
              onClick={handleCompleteReceiving}
              disabled={submitting}
              className="mobile-primary-btn bg-green-600 text-white disabled:opacity-60"
            >
              {submitting ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="h-5 w-5 animate-spin" /> Saving…
                </span>
              ) : (
                'Complete Receiving'
              )}
            </button>
          </div>
        )}

        {/* STEP 4: Success */}
        {step === 'success' && (
          <div className="flex flex-col items-center justify-center min-h-[60vh] text-center gap-4">
            <CheckCircle className="h-20 w-20 text-green-500" />
            <h2 className="text-2xl font-bold text-gray-900">
              ✓ {receivedCount} unit{receivedCount !== 1 ? 's' : ''} received
            </h2>
            <p className="text-gray-500">Inventory has been updated.</p>
            {issueItems.length > 0 && (
              <p className="text-amber-600 text-sm">
                {issueItems.length} issue{issueItems.length > 1 ? 's' : ''} recorded for review.
              </p>
            )}
            <p className="text-sm text-gray-400">Returning to Operations Board…</p>
          </div>
        )}
      </div>
    </div>
  )
}
