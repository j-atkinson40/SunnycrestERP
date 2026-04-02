// legacy-detail.tsx — Legacy proof detail page with versions and actions
// Route: /legacy/library/:legacyId

import { useState, useEffect, useCallback } from "react"
import { useNavigate, useParams } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ChevronLeft, Download, Check, RotateCcw, Loader2, ExternalLink } from "lucide-react"

interface LegacyDetail {
  id: string
  source: string
  legacy_type: string
  print_name: string | null
  is_urn: boolean
  inscription_name: string | null
  inscription_dates: string | null
  inscription_additional: string | null
  customer_id: string | null
  customer_name: string | null
  deceased_name: string | null
  service_date: string | null
  status: string
  proof_url: string | null
  tif_url: string | null
  background_url: string | null
  approved_layout: Record<string, unknown> | null
  family_approved: boolean
  approved_at: string | null
  proof_emailed_at: string | null
  order_id: string | null
  version_count: number
  created_at: string | null
  versions: { id: string; version_number: number; proof_url: string | null; inscription_name: string | null; print_name: string | null; notes: string | null; kept: boolean; created_at: string | null }[]
}

const STATUS_STEPS = ["draft", "proof_generated", "approved", "sent_to_print", "printed"]
const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  proof_generated: "Proof generated",
  proof_sent: "Proof sent",
  approved: "Approved",
  sent_to_print: "Sent to print",
  printed: "Printed",
  cancelled: "Cancelled",
}

export default function LegacyDetailPage() {
  const { legacyId } = useParams<{ legacyId: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<LegacyDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)

  const loadData = useCallback(async () => {
    if (!legacyId) return
    try {
      const res = await apiClient.get(`/legacy-studio/${legacyId}`)
      setData(res.data)
    } catch {
      toast.error("Could not load legacy proof")
    } finally {
      setLoading(false)
    }
  }, [legacyId])

  useEffect(() => { loadData() }, [loadData])

  async function handleApprove() {
    if (!legacyId) return
    setActing(true)
    try {
      await apiClient.post(`/legacy-studio/${legacyId}/approve`, {})
      toast.success("Proof approved")
      loadData()
    } catch { toast.error("Failed to approve") }
    finally { setActing(false) }
  }

  async function handleMarkPrinted() {
    if (!legacyId) return
    setActing(true)
    try {
      await apiClient.post(`/legacy-studio/${legacyId}/mark-printed`, {})
      toast.success("Marked as printed")
      loadData()
    } catch { toast.error("Failed") }
    finally { setActing(false) }
  }

  async function handleRevise() {
    if (!legacyId) return
    setActing(true)
    try {
      await apiClient.post(`/legacy-studio/${legacyId}/revise`, { keep_original: true })
      toast.success("New version created")
      navigate(`/legacy/generator?legacyId=${legacyId}`)
    } catch { toast.error("Failed to create revision") }
    finally { setActing(false) }
  }

  async function handleConvertToOrder() {
    if (!legacyId) return
    setActing(true)
    try {
      const res = await apiClient.post(`/legacy-studio/${legacyId}/convert-to-order`, {})
      toast.success(res.data.action === "created" ? "Draft order created" : "Linked to order")
      navigate(`/ar/orders/${res.data.order_id}`)
    } catch { toast.error("Failed to create order") }
    finally { setActing(false) }
  }

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-gray-400" /></div>
  }

  if (!data) {
    return <div className="max-w-3xl mx-auto p-6 text-center"><p className="text-gray-500">Not found</p></div>
  }

  const currentStepIdx = STATUS_STEPS.indexOf(data.status)

  return (
    <div className="max-w-6xl mx-auto px-6 py-6 space-y-6">
      <button onClick={() => navigate("/legacy/library")} className="flex items-center gap-1 text-sm text-gray-500">
        <ChevronLeft className="h-4 w-4" /> Back to library
      </button>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{data.inscription_name || "Legacy Proof"}</h1>
          <p className="text-sm text-gray-500 mt-1">
            {data.print_name || "Custom"} · {data.customer_name || "No funeral home"}{data.service_date ? ` · Service: ${data.service_date}` : ""}
          </p>
        </div>
        <Badge className={data.status === "approved" || data.status === "printed" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-700"}>
          {STATUS_LABELS[data.status] || data.status}
        </Badge>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* LEFT — Proof + versions */}
        <div className="lg:col-span-3 space-y-4">
          {data.proof_url ? (
            <Card className="overflow-hidden">
              <img src={data.proof_url} alt="Legacy proof" className="w-full" />
              <div className="p-3 flex gap-2">
                <a href={data.proof_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs text-blue-600">
                  <Download className="h-3.5 w-3.5" /> Proof JPEG
                </a>
                {data.tif_url && (data.status === "approved" || data.status === "printed") && (
                  <a href={data.tif_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs text-blue-600">
                    <Download className="h-3.5 w-3.5" /> Print TIF
                  </a>
                )}
              </div>
            </Card>
          ) : (
            <Card className="p-8 text-center">
              <p className="text-gray-500 mb-3">No proof generated yet</p>
              <Button onClick={() => navigate(`/legacy/generator?legacyId=${legacyId}`)}>
                Open in Proof Generator
              </Button>
            </Card>
          )}

          {/* Version history */}
          {data.versions && data.versions.length > 0 && (
            <Card className="p-4">
              <h3 className="text-sm font-semibold mb-3">Version history ({data.versions.length})</h3>
              <div className="space-y-2">
                {data.versions.map((v) => (
                  <div key={v.id} className={`flex items-center gap-3 text-xs ${!v.kept ? "opacity-40" : ""}`}>
                    <span className="font-medium text-gray-600">v{v.version_number}</span>
                    {v.proof_url && (
                      <img src={v.proof_url} alt="" className="w-20 h-6 object-cover rounded border" />
                    )}
                    <span className="text-gray-500">{v.print_name} · {v.inscription_name}</span>
                    {!v.kept && <Badge variant="outline" className="text-[10px]">Deleted</Badge>}
                    <span className="text-gray-400 ml-auto">{v.created_at ? new Date(v.created_at).toLocaleDateString() : ""}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>

        {/* RIGHT — Status + details + actions */}
        <div className="lg:col-span-2 space-y-4">
          {/* Status timeline */}
          <Card className="p-4">
            <h3 className="text-sm font-semibold mb-3">Status</h3>
            <div className="space-y-2">
              {STATUS_STEPS.map((step, idx) => (
                <div key={step} className="flex items-center gap-2 text-xs">
                  {idx <= currentStepIdx ? (
                    <Check className="h-3.5 w-3.5 text-green-600" />
                  ) : (
                    <span className="h-3.5 w-3.5 rounded-full border border-gray-300 inline-block" />
                  )}
                  <span className={idx <= currentStepIdx ? "text-gray-900 font-medium" : "text-gray-400"}>
                    {STATUS_LABELS[step]}
                  </span>
                </div>
              ))}
            </div>

            {/* Action buttons */}
            <div className="mt-4 space-y-2">
              {data.status === "proof_generated" && (
                <>
                  <Button onClick={handleApprove} loading={acting} className="w-full bg-green-600 hover:bg-green-700">
                    <Check className="h-4 w-4 mr-1" /> Approve proof
                  </Button>
                  <Button variant="outline" onClick={handleRevise} loading={acting} className="w-full">
                    <RotateCcw className="h-4 w-4 mr-1" /> Revise
                  </Button>
                </>
              )}
              {data.status === "approved" && (
                <>
                  <Button onClick={handleMarkPrinted} loading={acting} className="w-full">
                    Mark as printed
                  </Button>
                  <Button variant="outline" onClick={handleRevise} loading={acting} className="w-full">
                    <RotateCcw className="h-4 w-4 mr-1" /> Revise
                  </Button>
                </>
              )}
              {data.status === "printed" && (
                <Button variant="outline" onClick={handleRevise} loading={acting} className="w-full">
                  <RotateCcw className="h-4 w-4 mr-1" /> Create new version
                </Button>
              )}
            </div>
          </Card>

          {/* Details */}
          <Card className="p-4 text-sm space-y-2">
            <h3 className="font-semibold mb-2">Details</h3>
            <div><span className="text-gray-500">Type:</span> {data.legacy_type === "custom" ? "Custom Legacy" : "Standard Legacy"}</div>
            {data.print_name && <div><span className="text-gray-500">Print:</span> {data.print_name}</div>}
            {data.inscription_name && <div><span className="text-gray-500">Name:</span> {data.inscription_name}</div>}
            {data.inscription_dates && <div><span className="text-gray-500">Dates:</span> {data.inscription_dates}</div>}
            {data.inscription_additional && <div><span className="text-gray-500">Additional:</span> {data.inscription_additional}</div>}
            {data.customer_name && <div><span className="text-gray-500">Funeral home:</span> {data.customer_name}</div>}
            {data.deceased_name && <div><span className="text-gray-500">Deceased:</span> {data.deceased_name}</div>}
            <div><span className="text-gray-500">Source:</span> {data.source === "order" ? `Order linked` : "Standalone"}</div>
          </Card>

          {/* Order link */}
          <Card className="p-4">
            {data.order_id ? (
              <div>
                <p className="text-sm font-medium">Linked to order</p>
                <Button variant="outline" size="sm" className="mt-2" onClick={() => navigate(`/ar/orders/${data.order_id}`)}>
                  <ExternalLink className="h-3.5 w-3.5 mr-1" /> View order
                </Button>
              </div>
            ) : (
              <div className="space-y-2">
                <Button variant="outline" size="sm" onClick={handleConvertToOrder} loading={acting} className="w-full">
                  Convert to new order
                </Button>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
