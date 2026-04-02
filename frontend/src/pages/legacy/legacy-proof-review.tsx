// legacy-proof-review.tsx — Manufacturer proof review and approval page.
// Route: /legacy/proof/:orderId

import { useState, useEffect, useCallback } from "react"
import { useNavigate, useParams } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ChevronLeft, Loader2 } from "lucide-react"
import LegacyCompositor from "@/components/legacy/LegacyCompositor"
import type { LegacyLayout, GenerateResult } from "@/components/legacy/LegacyCompositor"

interface TaskData {
  id: string
  task_type: string
  inscription_name: string | null
  inscription_dates: string | null
  inscription_additional: string | null
  print_name: string | null
  print_image_url: string | null
  symbol: string | null
  is_custom_legacy: boolean
  status: string
  proof_url: string | null
  tif_url: string | null
  default_layout: Record<string, unknown> | null
  notes: string | null
}

interface OrderInfo {
  id: string
  number: string
  customer_name: string | null
  deceased_name: string | null
  scheduled_date: string | null
  service_time: string | null
}

export default function LegacyProofReviewPage() {
  const { orderId } = useParams<{ orderId: string }>()
  const navigate = useNavigate()
  const [task, setTask] = useState<TaskData | null>(null)
  const [order, setOrder] = useState<OrderInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [backgroundUrl, setBackgroundUrl] = useState<string | null>(null)
  const [polling, setPolling] = useState(false)

  const loadData = useCallback(async () => {
    if (!orderId) return
    try {
      // Load personalization tasks for this order
      const persRes = await apiClient.get(`/personalization/orders/${orderId}/personalization`)
      const legacyTask = persRes.data.tasks?.find(
        (t: TaskData) => t.task_type === "legacy_standard" || t.task_type === "legacy_custom"
      )
      if (legacyTask) {
        setTask(legacyTask)

        // If proof is being generated, poll
        if (legacyTask.status === "pending" && !legacyTask.proof_url) {
          setPolling(true)
        } else {
          setPolling(false)
        }

        // Get background URL for the template
        if (legacyTask.print_name && !legacyTask.is_custom_legacy) {
          try {
            const bgRes = await apiClient.post("/legacy/background", {
              print_name: legacyTask.print_name,
              is_urn: false,
            })
            setBackgroundUrl(bgRes.data.background_url)
          } catch {
            // Template may not be available
          }
        }
      }

      // Load order info
      try {
        const orderRes = await apiClient.get(`/sales/orders/${orderId}`)
        setOrder(orderRes.data)
      } catch {
        // Non-critical
      }
    } catch {
      toast.error("Could not load proof data")
    } finally {
      setLoading(false)
    }
  }, [orderId])

  useEffect(() => { loadData() }, [loadData])

  // Polling for proof generation
  useEffect(() => {
    if (!polling || !task) return
    const interval = setInterval(async () => {
      try {
        const res = await apiClient.get(`/legacy/proof-status/${task.id}`)
        if (res.data.proof_url) {
          setTask((prev) => prev ? { ...prev, ...res.data } : prev)
          setPolling(false)
        }
      } catch {
        // Continue polling
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [polling, task])

  async function handleGenerate(layout: LegacyLayout): Promise<GenerateResult> {
    const res = await apiClient.post("/legacy/generate", {
      order_id: orderId,
      print_name: task?.print_name,
      is_urn: false,
      is_custom: task?.is_custom_legacy || false,
      layout,
    })
    setTask((prev) => prev ? { ...prev, proof_url: res.data.proof_url, tif_url: res.data.tif_url } : prev)
    return res.data
  }

  async function handleApprove(layout: LegacyLayout, proofUrl: string, tifUrl: string) {
    if (!task || !orderId) return
    try {
      await apiClient.post(`/personalization/orders/${orderId}/personalization/tasks/${task.id}/complete`, {
        notes: `Proof approved. Layout: ${JSON.stringify(layout)}`,
      })
      toast.success("Proof approved — ready for print")
      navigate(-1)
    } catch {
      toast.error("Failed to approve proof")
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (!task) {
    return (
      <div className="max-w-3xl mx-auto p-6 text-center">
        <p className="text-gray-500">No legacy task found for this order.</p>
        <Button variant="outline" onClick={() => navigate(-1)} className="mt-4">
          Back
        </Button>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm text-gray-500 mb-2">
            <ChevronLeft className="h-4 w-4" /> Back
          </button>
          <h1 className="text-2xl font-bold text-gray-900">
            Legacy Proof{task.print_name ? ` — ${task.print_name}` : ""}
          </h1>
          {order && (
            <p className="text-sm text-gray-500 mt-1">
              {order.customer_name} · RE: {order.deceased_name || "—"}
              {order.scheduled_date && ` · Service: ${order.scheduled_date}`}
            </p>
          )}
        </div>
        <Badge variant="outline" className={task.status === "complete" ? "border-green-300 text-green-700" : "border-amber-300 text-amber-700"}>
          {task.status === "complete" ? "Approved" : task.status === "in_progress" ? "Ready for review" : "Pending"}
        </Badge>
      </div>

      {/* Order summary card */}
      <Card className="p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-xs text-gray-500 block">Type</span>
            <span className="font-medium">{task.is_custom_legacy ? "Custom Legacy" : "Standard Legacy"}</span>
          </div>
          {task.print_name && (
            <div>
              <span className="text-xs text-gray-500 block">Print</span>
              <span className="font-medium">{task.print_name}</span>
            </div>
          )}
          <div>
            <span className="text-xs text-gray-500 block">Name</span>
            <span className="font-medium">{task.inscription_name || "—"}</span>
          </div>
          <div>
            <span className="text-xs text-gray-500 block">Dates</span>
            <span className="font-medium">{task.inscription_dates || "—"}</span>
          </div>
        </div>
      </Card>

      {/* Proof area */}
      {polling && !task.proof_url && (
        <Card className="p-8 text-center">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400 mx-auto mb-3" />
          <p className="text-gray-600 font-medium">Generating proof...</p>
          <p className="text-sm text-gray-400 mt-1">This typically takes 5-15 seconds</p>
        </Card>
      )}

      {task.notes?.includes("Template not yet available") && (
        <Card className="p-6 bg-amber-50 border-amber-200 text-center">
          <p className="text-amber-800 font-medium">Template not available for auto-generation</p>
          <p className="text-sm text-amber-700 mt-1">
            {task.print_name} needs to be designed manually in Photoshop.
          </p>
        </Card>
      )}

      {backgroundUrl && !polling && (
        <LegacyCompositor
          backgroundUrl={backgroundUrl}
          mode="manufacturer"
          initialLayout={task.default_layout as LegacyLayout | undefined}
          name={task.inscription_name || ""}
          dates={task.inscription_dates || ""}
          additionalText={task.inscription_additional || ""}
          defaultTextColor="white"
          onGenerate={handleGenerate}
          onApprove={handleApprove}
          onCancel={() => navigate(-1)}
          generatedProofUrl={task.proof_url || undefined}
        />
      )}
    </div>
  )
}
