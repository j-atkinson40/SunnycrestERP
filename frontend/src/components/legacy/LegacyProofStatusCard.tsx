// LegacyProofStatusCard — Shows legacy proof status on the sales order detail page.
// Polls for updates when proof is generating.

import { useState, useEffect, useRef } from "react"
import { useNavigate } from "react-router-dom"
import apiClient from "@/lib/api-client"
import { Card } from "@/components/ui/card"
import { Loader2 } from "lucide-react"

interface ProofStatus {
  status: "none" | "generating" | "proof_ready" | "approved" | "no_template" | "custom_photo_needed"
  proof_url: string | null
  legacy_proof_id: string | null
  print_name: string | null
  inscription_name: string | null
  inscription_dates: string | null
  task_id: string | null
  notes: string | null
  completed_at: string | null
  family_approved: boolean
}

export default function LegacyProofStatusCard({ orderId }: { orderId: string }) {
  const navigate = useNavigate()
  const [data, setData] = useState<ProofStatus | null>(null)
  const [loaded, setLoaded] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const startRef = useRef<number>(Date.now())

  function fetchStatus() {
    apiClient.get(`/personalization/orders/${orderId}/legacy-proof-status`)
      .then((r) => setData(r.data))
      .catch(() => {})
      .finally(() => setLoaded(true))
  }

  useEffect(() => {
    fetchStatus()
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orderId])

  // Poll when generating
  useEffect(() => {
    if (data?.status === "generating") {
      startRef.current = Date.now()
      intervalRef.current = setInterval(() => {
        if (Date.now() - startRef.current > 5 * 60 * 1000) {
          if (intervalRef.current) clearInterval(intervalRef.current)
          return
        }
        fetchStatus()
      }, 5000)
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.status])

  if (!loaded || !data || data.status === "none") return null

  const studioPath = data.legacy_proof_id
    ? `/legacy/library/${data.legacy_proof_id}`
    : "/legacy/library"

  // ── Generating ─────────────────────────────────────────────────
  if (data.status === "generating") {
    return (
      <Card className="p-4 border-amber-200 bg-amber-50/50">
        <div className="flex items-center gap-2 text-sm font-medium text-amber-800 mb-2">
          <Loader2 className="h-4 w-4 animate-spin" /> Generating legacy proof...
        </div>
        {data.print_name && <p className="text-sm text-gray-700">{data.print_name}</p>}
        {data.inscription_name && <p className="text-sm text-gray-700">{data.inscription_name}</p>}
        {data.inscription_dates && <p className="text-sm text-gray-500">{data.inscription_dates}</p>}
        <p className="text-xs text-gray-400 mt-2">The proof will appear in Legacy Studio shortly.</p>
        <button
          onClick={() => navigate(studioPath)}
          className="mt-2 text-xs text-blue-600 font-medium hover:underline"
        >
          View in Legacy Studio →
        </button>
      </Card>
    )
  }

  // ── Proof ready ────────────────────────────────────────────────
  if (data.status === "proof_ready") {
    return (
      <Card className="p-4 border-blue-200">
        <p className="text-sm font-medium text-blue-800 mb-2">Legacy proof ready</p>
        {data.proof_url && (
          <img
            src={data.proof_url}
            alt="Legacy proof"
            className="w-full rounded-lg border"
            style={{ maxWidth: 400, aspectRatio: "16 / 4.5", objectFit: "cover" }}
          />
        )}
        <p className="text-sm text-gray-600 mt-2">
          {data.print_name && <span>{data.print_name} · </span>}
          {data.inscription_name}
        </p>
        <p className="text-xs text-amber-600 mt-1">Awaiting your review</p>
        <button
          onClick={() => navigate(studioPath)}
          className="mt-2 text-xs text-blue-600 font-medium hover:underline"
        >
          Review in Legacy Studio →
        </button>
      </Card>
    )
  }

  // ── Approved ───────────────────────────────────────────────────
  if (data.status === "approved") {
    const approvedDate = data.completed_at
      ? new Date(data.completed_at).toLocaleDateString("en-US", { month: "long", day: "numeric" }) +
        " at " +
        new Date(data.completed_at).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })
      : null

    return (
      <Card className="p-4 border-green-200 bg-green-50/50">
        <div className="flex items-center gap-1.5 text-sm font-medium text-green-700 mb-2">
          <span>✓</span> Legacy approved
        </div>
        {data.proof_url && (
          <img
            src={data.proof_url}
            alt="Approved proof"
            className="w-full rounded-lg border"
            style={{ maxWidth: 400, aspectRatio: "16 / 4.5", objectFit: "cover" }}
          />
        )}
        <p className="text-sm text-gray-600 mt-2">
          {data.print_name && <span>{data.print_name} · </span>}
          {data.inscription_name}
        </p>
        {approvedDate && <p className="text-xs text-gray-400 mt-0.5">Approved {approvedDate}</p>}
        <button
          onClick={() => navigate(studioPath)}
          className="mt-2 text-xs text-blue-600 font-medium hover:underline"
        >
          View in Legacy Studio →
        </button>
      </Card>
    )
  }

  // ── No template ────────────────────────────────────────────────
  if (data.status === "no_template") {
    return (
      <Card className="p-4 border-yellow-200 bg-yellow-50/50">
        <p className="text-sm font-medium text-yellow-800 mb-1">Legacy — manual design</p>
        {data.print_name && <p className="text-sm text-gray-700">{data.print_name}</p>}
        <p className="text-xs text-gray-500 mt-1">No template available yet — design manually in Photoshop</p>
        <button
          onClick={() => navigate(studioPath)}
          className="mt-2 text-xs text-blue-600 font-medium hover:underline"
        >
          View order details →
        </button>
      </Card>
    )
  }

  // ── Custom photo needed ────────────────────────────────────────
  if (data.status === "custom_photo_needed") {
    return (
      <Card className="p-4 border-blue-200 bg-blue-50/50">
        <p className="text-sm font-medium text-blue-800 mb-1">Custom legacy</p>
        {data.inscription_name && <p className="text-sm text-gray-700">{data.inscription_name}</p>}
        <p className="text-xs text-amber-600 mt-1">Background photo needed</p>
        <p className="text-xs text-gray-500">Upload the background photo in Legacy Studio to generate the proof.</p>
        <button
          onClick={() => navigate(studioPath)}
          className="mt-2 text-xs text-blue-600 font-medium hover:underline"
        >
          Upload in Legacy Studio →
        </button>
      </Card>
    )
  }

  return null
}
