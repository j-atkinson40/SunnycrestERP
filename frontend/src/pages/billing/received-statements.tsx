/**
 * Received Statements — funeral home side of cross-tenant billing.
 * Shows statements received from connected manufacturers with payment form.
 */

import { useState, useEffect, useCallback } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  FileText,
  DollarSign,
  AlertTriangle,
  RefreshCw,
  ArrowLeft,
  ExternalLink,
} from "lucide-react"
import { cn } from "@/lib/utils"
import apiClient from "@/lib/api-client"

const MONTH_NAMES = [
  "",
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
]

const RELATIONSHIP_TYPE_LABELS: Record<string, string> = {
  manufacturer_funeral_home: "Manufacturer",
  supplier_manufacturer: "Supplier",
  wilbert_licensee: "Wilbert",
}

interface ReceivedStatement {
  id: string
  from_tenant_name: string
  relationship_type: string
  month: number
  year: number
  balance_due: string
  invoice_count: number
  status: string
  received_at: string | null
  read_at: string | null
  statement_pdf_url: string | null
}

interface StatementDetail extends ReceivedStatement {
  previous_balance: string
  new_charges: string
  payments_received: string
  dispute_notes: string | null
  payments: {
    id: string
    amount: string
    payment_method: string
    payment_reference: string | null
    payment_date: string
    notes: string | null
    acknowledged: boolean
  }[]
}

// ── List view ──

export function ReceivedStatementsList() {
  const [statements, setStatements] = useState<ReceivedStatement[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiClient.get("/statements/received")
      setStatements(res.data)
    } catch {
      toast.error("Failed to load received statements")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <RefreshCw className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    )
  }

  if (statements.length === 0) {
    return (
      <Card>
        <CardContent className="p-8 text-center">
          <FileText className="mx-auto h-10 w-10 text-gray-300 mb-3" />
          <p className="text-sm text-gray-600">
            No statements received yet. Statements from connected suppliers will
            appear here.
          </p>
        </CardContent>
      </Card>
    )
  }

  // Group by manufacturer
  const grouped = statements.reduce(
    (acc, s) => {
      if (!acc[s.from_tenant_name]) acc[s.from_tenant_name] = []
      acc[s.from_tenant_name].push(s)
      return acc
    },
    {} as Record<string, ReceivedStatement[]>
  )

  return (
    <div className="space-y-4">
      {Object.entries(grouped).map(([manufacturer, stmts]) => (
        <Card key={manufacturer}>
          <CardContent className="p-4">
            <h4 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-3">
              From: {manufacturer}
            </h4>
            <div className="space-y-2">
              {stmts.map((s) => (
                <button
                  key={s.id}
                  onClick={() => navigate(`/billing/received/${s.id}`)}
                  className="w-full flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-gray-50 transition-colors text-left"
                >
                  <div className="flex items-center gap-3">
                    {s.status === "unread" && (
                      <span className="h-2.5 w-2.5 rounded-full bg-blue-500 shrink-0" />
                    )}
                    <div>
                      <span className="text-sm font-medium text-gray-900">
                        {MONTH_NAMES[s.month]} {s.year}
                      </span>
                      <span className="text-sm text-gray-500 ml-3">
                        Balance: ${s.balance_due}
                      </span>
                    </div>
                  </div>
                  <span
                    className={cn(
                      "text-xs font-medium",
                      s.status === "unread" && "text-blue-600",
                      s.status === "read" && "text-gray-500",
                      s.status === "paid" && "text-green-600",
                      s.status === "payment_initiated" && "text-amber-600",
                      s.status === "disputed" && "text-red-600"
                    )}
                  >
                    {s.status === "unread"
                      ? "● Unread"
                      : s.status === "paid"
                        ? "✓ Paid"
                        : s.status === "payment_initiated"
                          ? "⏳ Payment sent"
                          : s.status === "disputed"
                            ? "⚠ Disputed"
                            : "Read"}
                  </span>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

// ── Detail view ──

export function ReceivedStatementDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [detail, setDetail] = useState<StatementDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [showPayment, setShowPayment] = useState(false)
  const [showDispute, setShowDispute] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Payment form
  const [paymentMethod, setPaymentMethod] = useState("other")
  const [paymentRef, setPaymentRef] = useState("")
  const [paymentDate, setPaymentDate] = useState(
    new Date().toISOString().split("T")[0]
  )
  const [paymentAmount, setPaymentAmount] = useState("")
  const [paymentNotes, setPaymentNotes] = useState("")

  // Dispute form
  const [disputeNotes, setDisputeNotes] = useState("")

  useEffect(() => {
    if (!id) return
    setLoading(true)
    apiClient
      .get(`/statements/received/${id}`)
      .then((res) => {
        setDetail(res.data)
        setPaymentAmount(res.data.balance_due)
      })
      .catch(() => toast.error("Failed to load statement"))
      .finally(() => setLoading(false))
  }, [id])

  const recordPayment = async () => {
    if (!id || !paymentAmount) return
    setSubmitting(true)
    try {
      await apiClient.post(`/statements/received/${id}/pay`, {
        amount: parseFloat(paymentAmount),
        payment_method: paymentMethod,
        payment_date: paymentDate,
        payment_reference: paymentRef.trim() || null,
        notes: paymentNotes.trim() || null,
      })
      toast.success("Payment recorded")
      // Refresh detail
      const res = await apiClient.get(`/statements/received/${id}`)
      setDetail(res.data)
      setShowPayment(false)
    } catch {
      toast.error("Failed to record payment")
    } finally {
      setSubmitting(false)
    }
  }

  const submitDispute = async () => {
    if (!id || !disputeNotes.trim()) return
    setSubmitting(true)
    try {
      await apiClient.post(`/statements/received/${id}/dispute`, {
        notes: disputeNotes.trim(),
      })
      toast.success("Dispute submitted")
      const res = await apiClient.get(`/statements/received/${id}`)
      setDetail(res.data)
      setShowDispute(false)
    } catch {
      toast.error("Failed to submit dispute")
    } finally {
      setSubmitting(false)
    }
  }

  if (loading || !detail) {
    return (
      <div className="flex justify-center py-12">
        <RefreshCw className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    )
  }

  const isPaid = detail.status === "paid"
  const isDisputed = detail.status === "disputed"
  const balanceDue = parseFloat(detail.balance_due)

  return (
    <div className="space-y-4">
      <button
        onClick={() => navigate("/billing?tab=received")}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700"
      >
        <ArrowLeft className="h-4 w-4" /> Back to received statements
      </button>

      {/* Statement summary */}
      <Card>
        <CardContent className="p-5">
          <h3 className="text-lg font-semibold text-gray-900 mb-1">
            Statement from {detail.from_tenant_name}
          </h3>
          <p className="text-sm text-gray-500 mb-4">
            {RELATIONSHIP_TYPE_LABELS[detail.relationship_type] || detail.relationship_type} · {MONTH_NAMES[detail.month]} {detail.year}
          </p>

          <div className="grid grid-cols-2 gap-4 text-sm mb-4">
            <div>
              <span className="text-gray-500">Previous Balance</span>
              <p className="font-medium">${detail.previous_balance}</p>
            </div>
            <div>
              <span className="text-gray-500">New Charges</span>
              <p className="font-medium">${detail.new_charges}</p>
            </div>
            <div>
              <span className="text-gray-500">Payments Received</span>
              <p className="font-medium text-green-600">
                (${detail.payments_received})
              </p>
            </div>
            <div>
              <span className="text-gray-500">Balance Due</span>
              <p className="font-semibold text-lg">${detail.balance_due}</p>
            </div>
          </div>

          <p className="text-sm text-gray-500">
            {detail.invoice_count} invoices included
          </p>

          {detail.statement_pdf_url && (
            <Button
              variant="outline"
              size="sm"
              className="mt-3 gap-1.5"
              onClick={() => window.open(detail.statement_pdf_url!, "_blank")}
            >
              <ExternalLink className="h-3.5 w-3.5" />
              View Full Statement PDF
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Payment section */}
      {!isPaid && !isDisputed && (
        <Card>
          <CardContent className="p-5">
            <h4 className="text-sm font-semibold text-gray-900 mb-3">
              Payment
            </h4>

            {!showPayment ? (
              <Button onClick={() => setShowPayment(true)} className="gap-1.5">
                <DollarSign className="h-4 w-4" />
                Record Payment
              </Button>
            ) : (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Payment method
                  </label>
                  <select
                    value={paymentMethod}
                    onChange={(e) => setPaymentMethod(e.target.value)}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  >
                    <option value="ach">ACH / Bank transfer</option>
                    <option value="check">Check</option>
                    <option value="credit_card">Credit card</option>
                    <option value="other">Other / Manual</option>
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">
                      Amount
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      value={paymentAmount}
                      onChange={(e) => setPaymentAmount(e.target.value)}
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">
                      Payment date
                    </label>
                    <input
                      type="date"
                      value={paymentDate}
                      onChange={(e) => setPaymentDate(e.target.value)}
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Reference (optional)
                  </label>
                  <input
                    type="text"
                    value={paymentRef}
                    onChange={(e) => setPaymentRef(e.target.value)}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                    placeholder="Check number, transaction ID"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Notes (optional)
                  </label>
                  <textarea
                    value={paymentNotes}
                    onChange={(e) => setPaymentNotes(e.target.value)}
                    rows={2}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  />
                </div>

                <div className="flex gap-2">
                  <Button
                    onClick={recordPayment}
                    disabled={submitting}
                    className="gap-1.5"
                  >
                    <DollarSign className="h-3.5 w-3.5" />
                    {submitting ? "Recording..." : "Record Payment"}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => setShowPayment(false)}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Payment history */}
      {detail.payments.length > 0 && (
        <Card>
          <CardContent className="p-4">
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
              Payments
            </h4>
            <div className="space-y-2">
              {detail.payments.map((p) => (
                <div
                  key={p.id}
                  className="flex items-center justify-between text-sm py-1.5 border-b border-gray-100 last:border-0"
                >
                  <div>
                    <span className="font-medium">${p.amount}</span>
                    <span className="text-gray-500 ml-2">
                      {p.payment_method} · {p.payment_date}
                    </span>
                    {p.payment_reference && (
                      <span className="text-gray-400 ml-2">
                        #{p.payment_reference}
                      </span>
                    )}
                  </div>
                  <span
                    className={cn(
                      "text-xs",
                      p.acknowledged ? "text-green-600" : "text-amber-600"
                    )}
                  >
                    {p.acknowledged ? "✓ Acknowledged" : "⏳ Pending"}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Status badges */}
      {isPaid && (
        <Card className="border-green-200 bg-green-50/50">
          <CardContent className="p-4 text-center text-sm text-green-700">
            ✓ This statement has been paid in full
          </CardContent>
        </Card>
      )}

      {isDisputed && (
        <Card className="border-red-200 bg-red-50/50">
          <CardContent className="p-4 text-sm text-red-700">
            <p className="font-medium">⚠ This statement is disputed</p>
            {detail.dispute_notes && (
              <p className="mt-1 text-red-600">{detail.dispute_notes}</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Dispute button */}
      {!isPaid && !isDisputed && balanceDue > 0 && (
        <div className="pt-2">
          {!showDispute ? (
            <button
              onClick={() => setShowDispute(true)}
              className="text-sm text-red-500 hover:text-red-600 flex items-center gap-1.5"
            >
              <AlertTriangle className="h-3.5 w-3.5" />
              Dispute this statement
            </button>
          ) : (
            <Card className="border-red-200">
              <CardContent className="p-4">
                <h4 className="text-sm font-medium text-gray-900 mb-2">
                  Dispute Statement
                </h4>
                <textarea
                  value={disputeNotes}
                  onChange={(e) => setDisputeNotes(e.target.value)}
                  rows={3}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm mb-3"
                  placeholder="Describe the issue..."
                />
                <div className="flex gap-2">
                  <Button
                    onClick={submitDispute}
                    disabled={submitting || !disputeNotes.trim()}
                    variant="destructive"
                    size="sm"
                  >
                    {submitting ? "Submitting..." : "Submit Dispute"}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowDispute(false)}
                  >
                    Cancel
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
