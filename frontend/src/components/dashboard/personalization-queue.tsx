// personalization-queue.tsx — Operations Board widget showing today's + tomorrow's personalization tasks.

import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { CheckCircle, Loader2, ExternalLink } from "lucide-react"

interface PersTask {
  task_id: string
  task_type: string
  order_id: string
  funeral_home_name: string
  deceased_name: string
  service_time: string | null
  print_name: string | null
  print_image_url: string | null
  symbol: string | null
  inscription_name: string | null
  inscription_dates: string | null
  inscription_additional: string | null
  status: string
  legacy_photo_pending: boolean
  is_custom_legacy: boolean
  proof_url: string | null
}

interface QueueData {
  today: PersTask[]
  tomorrow: PersTask[]
}

const TYPE_BADGES: Record<string, { label: string; className: string }> = {
  nameplate: { label: "Nameplate", className: "bg-gray-100 text-gray-700" },
  cover_emblem: { label: "Cover Emblem", className: "bg-blue-100 text-blue-700" },
  lifes_reflections: { label: "Life's Reflections", className: "bg-purple-100 text-purple-700" },
  legacy_standard: { label: "Legacy Standard", className: "bg-teal-100 text-teal-700" },
  legacy_custom: { label: "Legacy Custom", className: "bg-amber-100 text-amber-700" },
}

export function PersonalizationQueue() {
  const navigate = useNavigate()
  const [data, setData] = useState<QueueData | null>(null)
  const [loading, setLoading] = useState(true)
  const [completing, setCompleting] = useState<string | null>(null)

  useEffect(() => {
    apiClient
      .get<QueueData>("/personalization/today-and-tomorrow")
      .then((r) => setData(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  async function handleComplete(taskId: string, orderId: string) {
    setCompleting(taskId)
    try {
      await apiClient.post(`/personalization/orders/${orderId}/personalization/tasks/${taskId}/complete`, {})
      setData((prev) => {
        if (!prev) return prev
        const update = (tasks: PersTask[]) =>
          tasks.map((t) => (t.task_id === taskId ? { ...t, status: "complete" } : t))
        return { today: update(prev.today), tomorrow: update(prev.tomorrow) }
      })
      toast.success("Task complete")
    } catch {
      toast.error("Failed to complete task")
    } finally {
      setCompleting(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-6">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!data || (data.today.length === 0 && data.tomorrow.length === 0)) return null

  function renderTask(task: PersTask) {
    const badge = TYPE_BADGES[task.task_type] || { label: task.task_type, className: "bg-gray-100 text-gray-700" }
    const isComplete = task.status === "complete"

    return (
      <div
        key={task.task_id}
        className={`rounded-lg border p-3 ${isComplete ? "opacity-50 border-green-200 bg-green-50/30" : "border-gray-200 bg-white"}`}
      >
        <div className="flex items-center justify-between mb-1.5">
          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${badge.className}`}>
            {badge.label}
          </span>
          {isComplete ? (
            <span className="text-[10px] text-green-600 flex items-center gap-0.5">
              <CheckCircle className="h-3 w-3" /> Complete
            </span>
          ) : (
            <span className="text-[10px] text-amber-600 font-medium">Pending</span>
          )}
        </div>

        <p className="text-sm font-medium text-gray-900">
          {task.funeral_home_name}
        </p>
        {task.deceased_name && (
          <p className="text-xs text-gray-500">RE: {task.deceased_name}</p>
        )}

        {/* Legacy/LR details */}
        {task.print_name && (
          <div className="flex items-center gap-2 mt-1.5">
            {task.print_image_url && (
              <img src={task.print_image_url} alt="" className="w-10 h-10 rounded object-cover border" />
            )}
            <span className="text-xs text-gray-700">Legacy: {task.print_name}</span>
          </div>
        )}
        {task.symbol && (
          <p className="text-xs text-gray-700 mt-1">Symbol: {task.symbol}</p>
        )}
        {task.is_custom_legacy && (
          <p className="text-xs text-amber-700 mt-1">Custom Legacy — see order for artwork</p>
        )}

        {/* Inscription */}
        {task.inscription_name && (
          <div className="mt-1.5 text-xs text-gray-600 space-y-0.5">
            <p>{task.inscription_name}</p>
            {task.inscription_dates && <p>{task.inscription_dates}</p>}
            {task.inscription_additional && <p className="text-gray-400">{task.inscription_additional}</p>}
          </div>
        )}

        {/* Service time */}
        {task.service_time && (
          <p className="text-[11px] text-gray-400 mt-1.5">Service: {task.service_time}</p>
        )}

        {/* Legacy photo warning */}
        {task.legacy_photo_pending && !isComplete && (
          <p className="text-xs text-amber-600 mt-1.5">
            No photos uploaded yet
          </p>
        )}

        {/* Proof thumbnail for legacy tasks */}
        {task.proof_url && (
          <img src={task.proof_url} alt="Proof" className="mt-1.5 w-full h-10 object-cover rounded border" />
        )}

        {/* Actions */}
        {!isComplete && (
          <div className="flex gap-2 mt-2">
            {task.proof_url && (task.task_type === "legacy_standard" || task.task_type === "legacy_custom") ? (
              <button
                onClick={() => navigate(`/legacy/proof/${task.order_id}`)}
                className="flex-1 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-medium"
              >
                Review proof
              </button>
            ) : (
              <button
                onClick={() => handleComplete(task.task_id, task.order_id)}
                disabled={completing === task.task_id}
                className="flex-1 py-1.5 bg-teal-600 text-white rounded-lg text-xs font-medium disabled:opacity-50"
              >
                {completing === task.task_id ? "..." : "Mark complete"}
              </button>
            )}
            <button
              onClick={() => navigate(`/ar/orders/${task.order_id}`)}
              className="px-3 py-1.5 border border-gray-200 rounded-lg text-xs text-gray-600 flex items-center gap-1"
            >
              <ExternalLink className="h-3 w-3" /> View
            </button>
          </div>
        )}
      </div>
    )
  }

  const pendingToday = data.today.filter((t) => t.status !== "complete")
  const completeToday = data.today.filter((t) => t.status === "complete")

  return (
    <div className="rounded-lg border bg-card p-4 space-y-3">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
        Personalization
      </h3>

      {data.today.length > 0 && (
        <div className="space-y-2">
          {pendingToday.map(renderTask)}
          {completeToday.map(renderTask)}
        </div>
      )}

      {data.tomorrow.length > 0 && (
        <div className="space-y-2 pt-3 border-t border-gray-100">
          <p className="text-[11px] text-gray-400 font-medium uppercase tracking-wider">
            Tomorrow — get ahead
          </p>
          {data.tomorrow.map(renderTask)}
        </div>
      )}
    </div>
  )
}
