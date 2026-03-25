/**
 * Cross-Licensee Transfers page — /transfers
 */

import { useState, useEffect, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Plus, ArrowRight, MapPin, Calendar, Package, Check, X } from "lucide-react"
import { cn } from "@/lib/utils"
import apiClient from "@/lib/api-client"

interface Transfer {
  id: string
  transfer_number: string
  status: string
  is_platform_transfer: boolean
  area_licensee_name: string | null
  funeral_home_name: string | null
  deceased_name: string | null
  service_date: string | null
  cemetery_name: string | null
  cemetery_city: string | null
  cemetery_state: string | null
  cemetery_county: string | null
  transfer_items: { description: string; quantity: number }[]
  area_charge_amount: number | null
  markup_percentage: number
  passthrough_amount: number | null
  requested_at: string | null
  accepted_at: string | null
  fulfilled_at: string | null
  direction: "outgoing" | "incoming"
}

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  pending: { label: "Pending", color: "bg-gray-100 text-gray-700" },
  accepted: { label: "Accepted", color: "bg-blue-100 text-blue-700" },
  in_progress: { label: "In Progress", color: "bg-purple-100 text-purple-700" },
  fulfilled: { label: "Fulfilled", color: "bg-teal-100 text-teal-700" },
  invoiced: { label: "Invoiced", color: "bg-amber-100 text-amber-700" },
  billed_through: { label: "Billed", color: "bg-green-100 text-green-700" },
  settled: { label: "Settled", color: "bg-gray-100 text-gray-600" },
  declined: { label: "Declined", color: "bg-red-100 text-red-700" },
  cancelled: { label: "Cancelled", color: "bg-red-100 text-red-700" },
  manual_coordination: { label: "Manual", color: "bg-amber-100 text-amber-700" },
}

type TabKey = "outgoing" | "incoming" | "all"

export default function TransfersPage() {
  const navigate = useNavigate()
  const [transfers, setTransfers] = useState<Transfer[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<TabKey>("outgoing")

  const fetchTransfers = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiClient.get(`/transfers?direction=${tab}`)
      setTransfers(res.data)
    } catch {
      toast.error("Failed to load transfers")
    } finally {
      setLoading(false)
    }
  }, [tab])

  useEffect(() => {
    fetchTransfers()
  }, [fetchTransfers])

  const handleAccept = async (id: string) => {
    try {
      await apiClient.post(`/transfers/${id}/accept`)
      toast.success("Transfer accepted")
      fetchTransfers()
    } catch {
      toast.error("Failed to accept transfer")
    }
  }

  const handleDecline = async (id: string) => {
    const reason = prompt("Reason for declining:")
    if (!reason) return
    try {
      await apiClient.post(`/transfers/${id}/decline`, { reason })
      toast.success("Transfer declined")
      fetchTransfers()
    } catch {
      toast.error("Failed to decline")
    }
  }

  const handleFulfill = async (id: string) => {
    try {
      await apiClient.post(`/transfers/${id}/fulfill`)
      toast.success("Transfer marked as fulfilled")
      fetchTransfers()
    } catch {
      toast.error("Failed to mark fulfilled")
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Cross-Licensee Transfers</h1>
          <p className="text-sm text-gray-500 mt-1">
            Transfer orders to area licensees for out-of-territory fulfillment
          </p>
        </div>
        <Button onClick={() => navigate("/transfers/new")} className="gap-1.5">
          <Plus className="h-4 w-4" /> New Transfer
        </Button>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex gap-6">
          {(["outgoing", "incoming", "all"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "pb-3 text-sm font-medium border-b-2 transition-colors capitalize",
                tab === t
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              )}
            >
              {t}
            </button>
          ))}
        </nav>
      </div>

      {/* Transfer list */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
        </div>
      ) : transfers.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <Package className="mx-auto h-10 w-10 text-gray-300 mb-3" />
            <p className="text-sm text-gray-500">
              No {tab === "all" ? "" : tab} transfers found.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {transfers.map((t) => {
            const statusCfg = STATUS_CONFIG[t.status] || STATUS_CONFIG.pending
            const isIncoming = t.direction === "incoming"

            return (
              <Card key={t.id} className="hover:shadow-sm transition-shadow">
                <CardContent className="p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-gray-900">
                        {t.transfer_number}
                      </span>
                      <span className={cn("text-xs px-2 py-0.5 rounded-full font-medium", statusCfg.color)}>
                        {statusCfg.label}
                      </span>
                      {!t.is_platform_transfer && (
                        <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                          Manual
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-gray-400">
                      {t.requested_at && new Date(t.requested_at).toLocaleDateString()}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm mb-3">
                    {t.funeral_home_name && (
                      <div className="flex items-center gap-1.5 text-gray-600">
                        <Package className="h-3.5 w-3.5 text-gray-400" />
                        {t.funeral_home_name}
                      </div>
                    )}
                    {t.cemetery_name && (
                      <div className="flex items-center gap-1.5 text-gray-600">
                        <MapPin className="h-3.5 w-3.5 text-gray-400" />
                        {t.cemetery_name}, {t.cemetery_city}, {t.cemetery_state}
                      </div>
                    )}
                    {t.service_date && (
                      <div className="flex items-center gap-1.5 text-gray-600">
                        <Calendar className="h-3.5 w-3.5 text-gray-400" />
                        {new Date(t.service_date).toLocaleDateString()}
                      </div>
                    )}
                    {t.area_licensee_name && (
                      <div className="flex items-center gap-1.5 text-gray-600">
                        <ArrowRight className="h-3.5 w-3.5 text-gray-400" />
                        {isIncoming ? "From: " : "To: "}{t.area_licensee_name}
                      </div>
                    )}
                  </div>

                  {t.transfer_items.length > 0 && (
                    <p className="text-xs text-gray-500 mb-3">
                      Items: {t.transfer_items.map((i) => `${i.quantity}x ${i.description}`).join(", ")}
                    </p>
                  )}

                  {t.area_charge_amount !== null && (
                    <div className="text-xs text-gray-500 mb-3">
                      Transfer charge: ${t.area_charge_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      {t.passthrough_amount !== null && (
                        <> · Passthrough: ${t.passthrough_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</>
                      )}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => navigate(`/transfers/${t.id}`)}
                    >
                      View Details
                    </Button>

                    {/* Incoming: pending → accept/decline */}
                    {isIncoming && t.status === "pending" && (
                      <>
                        <Button size="sm" onClick={() => handleAccept(t.id)} className="gap-1">
                          <Check className="h-3.5 w-3.5" /> Accept
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => handleDecline(t.id)} className="gap-1 text-red-600">
                          <X className="h-3.5 w-3.5" /> Decline
                        </Button>
                      </>
                    )}

                    {/* Incoming: accepted → fulfill */}
                    {isIncoming && (t.status === "accepted" || t.status === "in_progress") && (
                      <Button size="sm" onClick={() => handleFulfill(t.id)} className="gap-1">
                        <Check className="h-3.5 w-3.5" /> Mark Fulfilled
                      </Button>
                    )}

                    {/* Outgoing: invoiced → create passthrough */}
                    {!isIncoming && t.status === "invoiced" && (
                      <Button size="sm" onClick={() => navigate(`/transfers/${t.id}/passthrough`)}>
                        Create Passthrough
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
