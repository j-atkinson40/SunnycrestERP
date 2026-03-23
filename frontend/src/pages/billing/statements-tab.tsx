/**
 * Statements tab — monthly statement run workflow.
 */

import { useState, useEffect, useCallback } from "react"
import { toast } from "sonner"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  FileText,
  Send,
  Download,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  ChevronDown,
  ChevronUp,
  Users,
} from "lucide-react"
import { cn } from "@/lib/utils"
import apiClient from "@/lib/api-client"

interface EligibleCustomer {
  id: string
  name: string
  account_number: string | null
  billing_email: string | null
  delivery_method: string
  template_key: string | null
}

interface RunCustomer {
  id: string
  customer_id: string
  customer_name: string
  delivery_method: string
  status: string
  balance_due: string
  invoice_count: number
  email_sent_to: string | null
  send_error: string | null
  statement_pdf_url: string | null
}

interface RunStatus {
  id: string
  status: string
  month: number
  year: number
  total: number
  digital_count: number
  mail_count: number
  completed: number
  failed: number
  custom_message: string | null
  generated_at: string | null
  sent_at: string | null
  zip_file_url: string | null
  customers: RunCustomer[]
}

interface RunHistoryItem {
  id: string
  month: number
  year: number
  status: string
  total_customers: number
  digital_count: number
  mail_count: number
  sent_at: string | null
}

const MONTH_NAMES = [
  "", "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
]

export function StatementsTab() {
  const [eligible, setEligible] = useState<EligibleCustomer[]>([])
  const [history, setHistory] = useState<RunHistoryItem[]>([])
  const [activeRun, setActiveRun] = useState<RunStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [sending, setSending] = useState(false)
  const [showCustomerList, setShowCustomerList] = useState(false)
  const [customMessage, setCustomMessage] = useState("")
  const [_polling, setPolling] = useState(false)

  const now = new Date()
  // Statement month is the prior month
  const stmtMonth = now.getMonth() === 0 ? 12 : now.getMonth()
  const stmtYear = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear()

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [eligibleRes, historyRes] = await Promise.all([
        apiClient.get("/statements/eligible-customers"),
        apiClient.get("/statements/runs/history"),
      ])
      setEligible(eligibleRes.data)
      setHistory(historyRes.data)

      // Check if there's an active run for this period
      const activeInHistory = historyRes.data.find(
        (r: RunHistoryItem) =>
          r.month === stmtMonth &&
          r.year === stmtYear &&
          !["complete"].includes(r.status)
      )
      if (activeInHistory) {
        const statusRes = await apiClient.get(
          `/statements/runs/${activeInHistory.id}/status`
        )
        setActiveRun(statusRes.data)
      }
    } catch {
      toast.error("Failed to load statement data")
    } finally {
      setLoading(false)
    }
  }, [stmtMonth, stmtYear])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Poll for active generating run
  useEffect(() => {
    if (!activeRun || activeRun.status !== "generating") return
    setPolling(true)
    const interval = setInterval(async () => {
      try {
        const res = await apiClient.get(
          `/statements/runs/${activeRun.id}/status`
        )
        setActiveRun(res.data)
        if (res.data.status !== "generating") {
          clearInterval(interval)
          setPolling(false)
        }
      } catch {
        clearInterval(interval)
        setPolling(false)
      }
    }, 2000)
    return () => {
      clearInterval(interval)
      setPolling(false)
    }
  }, [activeRun?.id, activeRun?.status])

  const startRun = async () => {
    setStarting(true)
    try {
      const res = await apiClient.post("/statements/runs", {
        month: stmtMonth,
        year: stmtYear,
        custom_message: customMessage.trim() || null,
      })
      const statusRes = await apiClient.get(
        `/statements/runs/${res.data.id}/status`
      )
      setActiveRun(statusRes.data)
      toast.success("Statement run started")
    } catch {
      toast.error("Failed to start statement run")
    } finally {
      setStarting(false)
    }
  }

  const sendDigital = async () => {
    if (!activeRun) return
    setSending(true)
    try {
      const res = await apiClient.post(
        `/statements/runs/${activeRun.id}/send-digital`
      )
      toast.success(`${res.data.sent} statements sent`)
      // Refresh run status
      const statusRes = await apiClient.get(
        `/statements/runs/${activeRun.id}/status`
      )
      setActiveRun(statusRes.data)
    } catch {
      toast.error("Failed to send statements")
    } finally {
      setSending(false)
    }
  }

  const [deliveringPlatform, setDeliveringPlatform] = useState(false)
  const [sendingAll, setSendingAll] = useState(false)

  const deliverPlatform = async () => {
    if (!activeRun) return
    setDeliveringPlatform(true)
    try {
      const res = await apiClient.post(
        `/statements/runs/${activeRun.id}/deliver-platform`
      )
      toast.success(`${res.data.delivered} platform statements delivered`)
      const statusRes = await apiClient.get(
        `/statements/runs/${activeRun.id}/status`
      )
      setActiveRun(statusRes.data)
    } catch {
      toast.error("Failed to deliver platform statements")
    } finally {
      setDeliveringPlatform(false)
    }
  }

  const sendAll = async () => {
    if (!activeRun) return
    setSendingAll(true)
    try {
      const res = await apiClient.post(
        `/statements/runs/${activeRun.id}/send-all`
      )
      toast.success(
        `Platform: ${res.data.platform.delivered}, Digital: ${res.data.digital.sent} sent`
      )
      const statusRes = await apiClient.get(
        `/statements/runs/${activeRun.id}/status`
      )
      setActiveRun(statusRes.data)
    } catch {
      toast.error("Failed to send statements")
    } finally {
      setSendingAll(false)
    }
  }

  const digitalCount = eligible.filter(
    (c) => c.delivery_method === "digital"
  ).length
  const mailCount = eligible.filter(
    (c) => c.delivery_method === "mail"
  ).length
  const platformCount = eligible.filter(
    (c) => c.delivery_method === "platform"
  ).length

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <RefreshCw className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    )
  }

  // ── Active run view ──

  if (activeRun) {
    const isGenerating = activeRun.status === "generating"
    const isReady =
      activeRun.status === "ready" || activeRun.status === "partial"
    const isComplete = activeRun.status === "complete"
    const completedCount = activeRun.completed
    const totalCount = activeRun.customers.length

    return (
      <div className="space-y-4">
        {/* Run header */}
        <Card>
          <CardContent className="p-5">
            <h3 className="text-base font-semibold text-gray-900 mb-1">
              {MONTH_NAMES[activeRun.month]} {activeRun.year} Statements
              {isComplete && (
                <span className="ml-2 text-sm text-green-600 font-normal">
                  — Complete
                </span>
              )}
            </h3>

            {/* Progress bar */}
            {isGenerating && (
              <div className="mt-3">
                <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                  <span>Generating statements...</span>
                  <span>
                    {completedCount} of {totalCount}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all"
                    style={{
                      width: `${totalCount > 0 ? (completedCount / totalCount) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>
            )}

            {/* Ready state — send/download actions */}
            {isReady && (
              <div className="mt-4 space-y-4">
                <div className="text-sm text-gray-600">
                  ✓ {completedCount} statements generated
                  {activeRun.customers.filter(c => c.delivery_method === "platform").length > 0 && (
                    <> · {activeRun.customers.filter(c => c.delivery_method === "platform").length} platform</>
                  )}
                  {" "}· {activeRun.digital_count} digital · {activeRun.mail_count}{" "}
                  mail
                  {activeRun.failed > 0 && (
                    <span className="text-red-600 ml-2">
                      · {activeRun.failed} failed
                    </span>
                  )}
                </div>

                {/* Combined send-all button */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <Button
                    onClick={sendAll}
                    disabled={sendingAll}
                    className="w-full gap-2"
                    size="lg"
                  >
                    <Send className="h-4 w-4" />
                    {sendingAll
                      ? "Sending all..."
                      : "Send all statements — platform + email + mail"}
                  </Button>
                  <p className="text-xs text-blue-600 mt-2 text-center">
                    Delivers to platforms, emails digital, saves mail for printing
                  </p>
                </div>

                {/* Platform section */}
                {activeRun.customers.filter(c => c.delivery_method === "platform").length > 0 && (
                  <div className="border rounded-lg p-4">
                    <h4 className="text-sm font-medium text-gray-900 mb-2">
                      Platform Statements
                    </h4>
                    <p className="text-sm text-gray-500 mb-2">
                      {activeRun.customers.filter(c => c.delivery_method === "platform").length} statements
                      ready for cross-tenant delivery
                    </p>
                    <div className="space-y-1 mb-3">
                      {activeRun.customers
                        .filter(c => c.delivery_method === "platform")
                        .map(c => (
                          <div key={c.id} className="flex items-center justify-between text-sm">
                            <span className="text-gray-700">{c.customer_name}</span>
                            <span className="text-gray-500">${c.balance_due} due</span>
                          </div>
                        ))}
                    </div>
                    <Button
                      onClick={deliverPlatform}
                      disabled={deliveringPlatform}
                      variant="outline"
                      size="sm"
                      className="gap-1.5"
                    >
                      <CheckCircle className="h-3.5 w-3.5" />
                      {deliveringPlatform ? "Delivering..." : "Deliver to platforms"}
                    </Button>
                  </div>
                )}

                {/* Digital section */}
                {activeRun.digital_count > 0 && (
                  <div className="border rounded-lg p-4">
                    <h4 className="text-sm font-medium text-gray-900 mb-2">
                      Digital Statements
                    </h4>
                    <p className="text-sm text-gray-500 mb-3">
                      {activeRun.digital_count} statements ready to email
                    </p>
                    <Button
                      onClick={sendDigital}
                      disabled={sending}
                      className="gap-1.5"
                    >
                      <Send className="h-3.5 w-3.5" />
                      {sending ? "Sending..." : "Send all digital"}
                    </Button>
                  </div>
                )}

                {/* Mail section */}
                {activeRun.mail_count > 0 && (
                  <div className="border rounded-lg p-4">
                    <h4 className="text-sm font-medium text-gray-900 mb-2">
                      Mail Statements
                    </h4>
                    <p className="text-sm text-gray-500 mb-3">
                      {activeRun.mail_count} statements saved for printing
                    </p>
                    <Button variant="outline" className="gap-1.5">
                      <Download className="h-3.5 w-3.5" />
                      Download mail PDFs as ZIP
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* Complete state */}
            {isComplete && activeRun.sent_at && (
              <p className="mt-2 text-sm text-green-600">
                ✓ Sent{" "}
                {new Date(activeRun.sent_at).toLocaleDateString([], {
                  month: "long",
                  day: "numeric",
                })}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Customer list */}
        <Card>
          <CardContent className="p-0">
            <div className="divide-y divide-gray-100">
              {activeRun.customers.map((cust) => (
                <div
                  key={cust.id}
                  className="flex items-center justify-between px-4 py-2.5 text-sm"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    {cust.status === "ready" || cust.status === "sent" ? (
                      <CheckCircle className="h-4 w-4 text-green-500 shrink-0" />
                    ) : cust.status === "failed" ? (
                      <XCircle className="h-4 w-4 text-red-500 shrink-0" />
                    ) : cust.status === "generating" ? (
                      <RefreshCw className="h-4 w-4 text-blue-500 animate-spin shrink-0" />
                    ) : (
                      <Clock className="h-4 w-4 text-gray-300 shrink-0" />
                    )}
                    <span className="font-medium text-gray-900 truncate">
                      {cust.customer_name}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-500 shrink-0">
                    <span
                      className={cn(
                        "capitalize",
                        cust.delivery_method === "digital"
                          ? "text-blue-600"
                          : "text-amber-600"
                      )}
                    >
                      {cust.delivery_method}
                    </span>
                    <span
                      className={cn(
                        cust.status === "ready" && "text-green-600",
                        cust.status === "sent" && "text-green-600",
                        cust.status === "failed" && "text-red-600"
                      )}
                    >
                      {cust.status === "sent"
                        ? "Sent"
                        : cust.status.charAt(0).toUpperCase() +
                          cust.status.slice(1)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // ── Default state — no active run ──

  const lastRun = history[0]

  return (
    <div className="space-y-4">
      {/* Last run summary */}
      {lastRun && (
        <Card>
          <CardContent className="p-4 flex items-center justify-between">
            <div className="text-sm text-gray-600">
              <span className="font-medium">Last run: </span>
              {MONTH_NAMES[lastRun.month]} {lastRun.year}
              {lastRun.sent_at && (
                <>
                  {" "}
                  · Sent{" "}
                  {new Date(lastRun.sent_at).toLocaleDateString([], {
                    month: "long",
                    day: "numeric",
                  })}
                </>
              )}
              <br />
              {lastRun.total_customers} statements · {lastRun.digital_count}{" "}
              digital · {lastRun.mail_count} mail
            </div>
          </CardContent>
        </Card>
      )}

      {/* Start new run */}
      <Card>
        <CardContent className="p-5">
          <h3 className="text-base font-semibold text-gray-900 mb-1">
            Ready to run {MONTH_NAMES[stmtMonth]} {stmtYear} statements?
          </h3>
          <div className="mt-3 text-sm text-gray-600 space-y-1">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-gray-400" />
              <span>
                {eligible.length} customers eligible
                {platformCount > 0 && <> · {platformCount} platform</>}
                {" "}· {digitalCount} digital ·{" "}
                {mailCount} mail
              </span>
            </div>
          </div>

          {/* Optional message */}
          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Optional message for this month
            </label>
            <textarea
              value={customMessage}
              onChange={(e) => setCustomMessage(e.target.value)}
              rows={2}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              placeholder="Included on all statements sent this month"
            />
          </div>

          {/* Customer preview toggle */}
          <button
            onClick={() => setShowCustomerList(!showCustomerList)}
            className="mt-3 flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700"
          >
            {showCustomerList ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
            Preview customer list
          </button>

          {showCustomerList && (
            <div className="mt-2 border rounded-lg max-h-64 overflow-y-auto">
              <div className="divide-y divide-gray-100">
                {eligible.map((c) => (
                  <div
                    key={c.id}
                    className="flex items-center justify-between px-3 py-2 text-sm"
                  >
                    <div>
                      <span className="font-medium text-gray-900">
                        {c.name}
                      </span>
                      {c.billing_email && (
                        <span className="text-xs text-gray-400 ml-2">
                          {c.billing_email}
                        </span>
                      )}
                    </div>
                    <span
                      className={cn(
                        "text-xs capitalize",
                        c.delivery_method === "digital"
                          ? "text-blue-600"
                          : "text-amber-600"
                      )}
                    >
                      {c.delivery_method}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="mt-4">
            <Button
              onClick={startRun}
              disabled={starting || eligible.length === 0}
              className="gap-1.5"
            >
              <FileText className="h-4 w-4" />
              {starting ? "Starting..." : "Start statement run"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Run history */}
      {history.length > 0 && (
        <Card>
          <CardContent className="p-4">
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
              Past Statements
            </h4>
            <div className="space-y-2">
              {history.map((run) => (
                <div
                  key={run.id}
                  className="flex items-center justify-between text-sm py-1.5"
                >
                  <span className="text-gray-700">
                    {MONTH_NAMES[run.month]} {run.year}
                  </span>
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    <span>
                      {run.total_customers} customers · {run.digital_count}{" "}
                      digital · {run.mail_count} mail
                    </span>
                    {run.sent_at && (
                      <span className="text-green-600">
                        Sent{" "}
                        {new Date(run.sent_at).toLocaleDateString([], {
                          month: "short",
                          day: "numeric",
                        })}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
