import { useState, useEffect } from "react"
import { useParams, useNavigate } from "react-router-dom"
import {
  Loader2,
  Check,
  X,
  Send,
  FileText,
  Phone,
  ArrowLeft,
} from "lucide-react"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"

interface EngravingJob {
  id: string
  piece_label: string
  engraving_line_1: string | null
  engraving_line_2: string | null
  engraving_line_3: string | null
  engraving_line_4: string | null
  font_selection: string | null
  color_selection: string | null
  proof_status: string
  proof_file_id: string | null
  fh_approved_by_name: string | null
  fh_approved_at: string | null
  fh_change_request_notes: string | null
  approved_by: string | null
  approved_at: string | null
  rejection_notes: string | null
  resubmission_count: number
  verbal_approval_flagged: boolean
  submitted_at: string | null
}

interface Order {
  id: string
  funeral_home_name: string | null
  fh_contact_email: string | null
  urn_product_name: string | null
  fulfillment_type: string
  status: string
  need_by_date: string | null
  engraving_jobs: EngravingJob[]
}

function statusLabel(s: string) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

const PROOF_STATUS_COLORS: Record<string, string> = {
  not_submitted: "bg-gray-100 text-gray-700",
  awaiting_proof: "bg-yellow-100 text-yellow-700",
  proof_received: "bg-blue-100 text-blue-700",
  awaiting_fh_approval: "bg-purple-100 text-purple-700",
  fh_approved: "bg-green-100 text-green-700",
  fh_changes_requested: "bg-red-100 text-red-700",
  approved: "bg-emerald-200 text-emerald-800",
  rejected: "bg-red-200 text-red-800",
}

export default function ProofReview() {
  const { orderId } = useParams<{ orderId: string }>()
  const navigate = useNavigate()
  const [order, setOrder] = useState<Order | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [editJob, setEditJob] = useState<EngravingJob | null>(null)
  const [editForm, setEditForm] = useState({
    engraving_line_1: "",
    engraving_line_2: "",
    engraving_line_3: "",
    engraving_line_4: "",
    font_selection: "",
    color_selection: "",
  })
  const [rejectNotes, setRejectNotes] = useState("")
  const [showReject, setShowReject] = useState<string | null>(null)

  const load = () => {
    if (!orderId) return
    setLoading(true)
    apiClient
      .get(`/urns/orders/${orderId}`)
      .then((r) => setOrder(r.data))
      .catch(() => toast.error("Failed to load order"))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [orderId])

  const confirmOrder = () => {
    setActionLoading("confirm")
    apiClient
      .post(`/urns/orders/${orderId}/confirm`)
      .then(() => {
        toast.success("Order confirmed")
        load()
      })
      .catch(() => toast.error("Failed to confirm"))
      .finally(() => setActionLoading(null))
  }

  const submitToWilbert = () => {
    setActionLoading("submit")
    apiClient
      .post(`/urns/orders/${orderId}/submit-to-wilbert`)
      .then(() => {
        toast.success("Submitted to Wilbert")
        load()
      })
      .catch(() => toast.error("Failed to submit"))
      .finally(() => setActionLoading(null))
  }

  const downloadForm = () => {
    apiClient
      .post(`/urns/orders/${orderId}/wilbert-form/pdf`, {}, { responseType: "blob" })
      .then((r) => {
        const url = URL.createObjectURL(r.data)
        const a = document.createElement("a")
        a.href = url
        a.download = `engraving-${orderId?.slice(0, 8)}.pdf`
        a.click()
        URL.revokeObjectURL(url)
      })
      .catch(() => toast.error("Failed to download form"))
  }

  const staffApprove = (jobId: string) => {
    setActionLoading(jobId)
    apiClient
      .post(`/urns/engraving/${jobId}/staff-approve`)
      .then(() => {
        toast.success("Proof approved")
        load()
      })
      .catch(() => toast.error("Approval failed"))
      .finally(() => setActionLoading(null))
  }

  const staffReject = () => {
    if (!showReject || !rejectNotes.trim()) return
    setActionLoading(showReject)
    apiClient
      .post(`/urns/engraving/${showReject}/staff-reject?notes=${encodeURIComponent(rejectNotes)}`)
      .then(() => {
        toast.success("Proof rejected — resubmission required")
        setShowReject(null)
        setRejectNotes("")
        load()
      })
      .catch(() => toast.error("Rejection failed"))
      .finally(() => setActionLoading(null))
  }

  const sendFhApproval = (jobId: string) => {
    setActionLoading(jobId + "-fh")
    apiClient
      .post(`/urns/engraving/${jobId}/send-fh-approval`)
      .then(() => {
        toast.success("FH approval email sent")
        load()
      })
      .catch(() => toast.error("Failed to send email"))
      .finally(() => setActionLoading(null))
  }

  const openEditJob = (job: EngravingJob) => {
    setEditJob(job)
    setEditForm({
      engraving_line_1: job.engraving_line_1 || "",
      engraving_line_2: job.engraving_line_2 || "",
      engraving_line_3: job.engraving_line_3 || "",
      engraving_line_4: job.engraving_line_4 || "",
      font_selection: job.font_selection || "",
      color_selection: job.color_selection || "",
    })
  }

  const saveSpecs = () => {
    if (!editJob) return
    apiClient
      .patch(`/urns/engraving/${editJob.id}/specs`, editForm)
      .then(() => {
        toast.success("Specs updated")
        setEditJob(null)
        load()
      })
      .catch(() => toast.error("Failed to update"))
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!order) {
    return (
      <div className="p-6 text-center text-muted-foreground">
        Order not found
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate("/urns/orders")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">
            Order {order.id.slice(0, 8)}
          </h1>
          <p className="text-sm text-muted-foreground">
            {order.urn_product_name} &middot; {order.funeral_home_name || "No FH"}
          </p>
        </div>
        <Badge className="ml-auto">{statusLabel(order.status)}</Badge>
      </div>

      {/* Order actions */}
      <Card className="flex items-center gap-3 p-4">
        {order.status === "draft" && (
          <Button onClick={confirmOrder} disabled={actionLoading === "confirm"}>
            {actionLoading === "confirm" ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Check className="mr-2 h-4 w-4" />
            )}
            Confirm Order
          </Button>
        )}
        {order.status === "engraving_pending" && (
          <>
            <Button onClick={submitToWilbert} disabled={actionLoading === "submit"}>
              {actionLoading === "submit" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Send className="mr-2 h-4 w-4" />
              )}
              Submit to Wilbert
            </Button>
            <Button variant="outline" onClick={downloadForm}>
              <FileText className="mr-2 h-4 w-4" />
              Download Form
            </Button>
          </>
        )}
        {["delivered", "cancelled"].includes(order.status) && (
          <span className="text-sm text-muted-foreground">
            This order is {order.status}.
          </span>
        )}
      </Card>

      {/* Engraving jobs */}
      {order.engraving_jobs.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Engraving Jobs</h2>
          {order.engraving_jobs.map((job) => (
            <Card key={job.id} className="p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-medium capitalize">
                    {job.piece_label.replace(/_/g, " ")}
                  </span>
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${PROOF_STATUS_COLORS[job.proof_status] || "bg-gray-100"}`}
                  >
                    {statusLabel(job.proof_status)}
                  </span>
                  {job.verbal_approval_flagged && (
                    <Badge variant="outline" className="text-xs">
                      <Phone className="mr-1 h-3 w-3" />
                      Verbal Approval
                    </Badge>
                  )}
                  {job.resubmission_count > 0 && (
                    <Badge variant="outline" className="text-xs">
                      Rev {job.resubmission_count}
                    </Badge>
                  )}
                </div>
                <Button size="sm" variant="outline" onClick={() => openEditJob(job)}>
                  Edit Specs
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
                <div>
                  <span className="text-muted-foreground">Line 1:</span>{" "}
                  {job.engraving_line_1 || "—"}
                </div>
                <div>
                  <span className="text-muted-foreground">Font:</span>{" "}
                  {job.font_selection || "—"}
                </div>
                <div>
                  <span className="text-muted-foreground">Line 2:</span>{" "}
                  {job.engraving_line_2 || "—"}
                </div>
                <div>
                  <span className="text-muted-foreground">Color:</span>{" "}
                  {job.color_selection || "—"}
                </div>
                <div>
                  <span className="text-muted-foreground">Line 3:</span>{" "}
                  {job.engraving_line_3 || "—"}
                </div>
                <div>
                  <span className="text-muted-foreground">Line 4:</span>{" "}
                  {job.engraving_line_4 || "—"}
                </div>
              </div>

              {/* FH approval info */}
              {job.fh_approved_by_name && (
                <div className="rounded-md bg-green-50 p-2 text-sm text-green-700">
                  FH Approved by {job.fh_approved_by_name}
                  {job.fh_approved_at && (
                    <> on {new Date(job.fh_approved_at).toLocaleDateString()}</>
                  )}
                </div>
              )}
              {job.fh_change_request_notes && (
                <div className="rounded-md bg-red-50 p-2 text-sm text-red-700">
                  FH Change Request: {job.fh_change_request_notes}
                </div>
              )}
              {job.rejection_notes && (
                <div className="rounded-md bg-red-50 p-2 text-sm text-red-700">
                  Rejected: {job.rejection_notes}
                </div>
              )}

              {/* Job actions */}
              <div className="flex gap-2">
                {job.proof_status === "proof_received" && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => sendFhApproval(job.id)}
                    disabled={actionLoading === job.id + "-fh"}
                  >
                    Send FH Approval
                  </Button>
                )}
                {["fh_approved", "proof_received"].includes(job.proof_status) && (
                  <>
                    <Button
                      size="sm"
                      onClick={() => staffApprove(job.id)}
                      disabled={actionLoading === job.id}
                    >
                      <Check className="mr-1 h-3.5 w-3.5" />
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => setShowReject(job.id)}
                    >
                      <X className="mr-1 h-3.5 w-3.5" />
                      Reject
                    </Button>
                  </>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Edit specs dialog */}
      <Dialog open={!!editJob} onOpenChange={() => setEditJob(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Edit Engraving — {editJob?.piece_label.replace(/_/g, " ")}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Line 1 (Decedent Name)</Label>
              <Input
                value={editForm.engraving_line_1}
                onChange={(e) =>
                  setEditForm({ ...editForm, engraving_line_1: e.target.value })
                }
              />
            </div>
            <div>
              <Label>Line 2</Label>
              <Input
                value={editForm.engraving_line_2}
                onChange={(e) =>
                  setEditForm({ ...editForm, engraving_line_2: e.target.value })
                }
              />
            </div>
            <div>
              <Label>Line 3</Label>
              <Input
                value={editForm.engraving_line_3}
                onChange={(e) =>
                  setEditForm({ ...editForm, engraving_line_3: e.target.value })
                }
              />
            </div>
            <div>
              <Label>Line 4</Label>
              <Input
                value={editForm.engraving_line_4}
                onChange={(e) =>
                  setEditForm({ ...editForm, engraving_line_4: e.target.value })
                }
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Font</Label>
                <Input
                  value={editForm.font_selection}
                  onChange={(e) =>
                    setEditForm({ ...editForm, font_selection: e.target.value })
                  }
                />
              </div>
              <div>
                <Label>Color</Label>
                <Input
                  value={editForm.color_selection}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      color_selection: e.target.value,
                    })
                  }
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditJob(null)}>
              Cancel
            </Button>
            <Button onClick={saveSpecs}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reject dialog */}
      <Dialog open={!!showReject} onOpenChange={() => setShowReject(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Proof</DialogTitle>
          </DialogHeader>
          <div>
            <Label>Rejection Notes</Label>
            <textarea
              className="w-full rounded-md border px-3 py-2 text-sm"
              rows={4}
              value={rejectNotes}
              onChange={(e) => setRejectNotes(e.target.value)}
              placeholder="Describe what needs to be corrected..."
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowReject(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={staffReject}
              disabled={!rejectNotes.trim()}
            >
              Reject
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
