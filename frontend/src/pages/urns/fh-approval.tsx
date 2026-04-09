import { useState, useEffect } from "react"
import { useParams, useSearchParams } from "react-router-dom"
import { Loader2, Check, MessageSquare } from "lucide-react"
import apiClient from "@/lib/api-client"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

interface ProofData {
  job_id: string
  piece_label: string
  engraving_line_1: string | null
  engraving_line_2: string | null
  engraving_line_3: string | null
  engraving_line_4: string | null
  font_selection: string | null
  color_selection: string | null
  proof_file_id: string | null
}

export default function FHApproval() {
  const { token } = useParams<{ token: string }>()
  const [searchParams] = useSearchParams()
  const action = searchParams.get("action")

  const [proof, setProof] = useState<ProofData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)

  // Approval form
  const [approverName, setApproverName] = useState("")
  const [approverEmail, setApproverEmail] = useState("")

  // Change request form
  const [changeNotes, setChangeNotes] = useState("")

  const [mode, setMode] = useState<"approve" | "changes">(
    action === "changes" ? "changes" : "approve"
  )

  useEffect(() => {
    if (!token) return
    apiClient
      .get(`/urns/proof-approval/${token}`)
      .then((r) => setProof(r.data))
      .catch((e) => {
        if (e.response?.status === 410) {
          setError("This approval link has expired. Please contact the manufacturer for a new link.")
        } else {
          setError("Invalid or expired approval link.")
        }
      })
      .finally(() => setLoading(false))
  }, [token])

  const handleApprove = () => {
    if (!approverName.trim()) {
      toast.error("Please enter your name")
      return
    }
    setSubmitting(true)
    apiClient
      .post(`/urns/proof-approval/${token}/approve`, {
        approved_by_name: approverName,
        approved_by_email: approverEmail || null,
      })
      .then(() => setDone(true))
      .catch(() => toast.error("Approval failed. The link may have expired."))
      .finally(() => setSubmitting(false))
  }

  const handleChangeRequest = () => {
    if (!changeNotes.trim()) {
      toast.error("Please describe the changes needed")
      return
    }
    setSubmitting(true)
    apiClient
      .post(`/urns/proof-approval/${token}/request-changes`, {
        notes: changeNotes,
      })
      .then(() => setDone(true))
      .catch(() => toast.error("Request failed. The link may have expired."))
      .finally(() => setSubmitting(false))
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <Card className="max-w-md p-8 text-center">
          <p className="text-lg text-red-600">{error}</p>
        </Card>
      </div>
    )
  }

  if (done) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <Card className="max-w-md p-8 text-center space-y-4">
          {mode === "approve" ? (
            <>
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
                <Check className="h-8 w-8 text-green-600" />
              </div>
              <h2 className="text-xl font-bold">Proof Approved</h2>
              <p className="text-muted-foreground">
                Thank you for approving the engraving proof. Production will
                proceed as specified.
              </p>
            </>
          ) : (
            <>
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-yellow-100">
                <MessageSquare className="h-8 w-8 text-yellow-600" />
              </div>
              <h2 className="text-xl font-bold">Changes Requested</h2>
              <p className="text-muted-foreground">
                Your change request has been submitted. You will receive a new
                proof for review once the corrections are made.
              </p>
            </>
          )}
        </Card>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-lg space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold">Engraving Proof Review</h1>
          <p className="text-muted-foreground">
            Please review the engraving details below
          </p>
        </div>

        {proof && (
          <Card className="p-6 space-y-4">
            <h2 className="font-semibold capitalize">
              {proof.piece_label.replace(/_/g, " ")} Piece
            </h2>

            <div className="space-y-2 rounded-md bg-muted p-4">
              {proof.engraving_line_1 && (
                <div className="text-center text-lg font-medium">
                  {proof.engraving_line_1}
                </div>
              )}
              {proof.engraving_line_2 && (
                <div className="text-center">{proof.engraving_line_2}</div>
              )}
              {proof.engraving_line_3 && (
                <div className="text-center text-sm">
                  {proof.engraving_line_3}
                </div>
              )}
              {proof.engraving_line_4 && (
                <div className="text-center text-sm">
                  {proof.engraving_line_4}
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Font:</span>{" "}
                {proof.font_selection || "Not specified"}
              </div>
              <div>
                <span className="text-muted-foreground">Color:</span>{" "}
                {proof.color_selection || "Not specified"}
              </div>
            </div>
          </Card>
        )}

        {/* Mode toggle */}
        <div className="flex rounded-lg border">
          <button
            className={`flex-1 rounded-l-lg px-4 py-2 text-sm font-medium transition ${
              mode === "approve"
                ? "bg-green-600 text-white"
                : "hover:bg-muted"
            }`}
            onClick={() => setMode("approve")}
          >
            Approve
          </button>
          <button
            className={`flex-1 rounded-r-lg px-4 py-2 text-sm font-medium transition ${
              mode === "changes"
                ? "bg-red-600 text-white"
                : "hover:bg-muted"
            }`}
            onClick={() => setMode("changes")}
          >
            Request Changes
          </button>
        </div>

        {mode === "approve" ? (
          <Card className="p-6 space-y-4">
            <div>
              <Label>Your Name *</Label>
              <Input
                value={approverName}
                onChange={(e) => setApproverName(e.target.value)}
                placeholder="Enter your full name"
              />
            </div>
            <div>
              <Label>Your Email (optional)</Label>
              <Input
                type="email"
                value={approverEmail}
                onChange={(e) => setApproverEmail(e.target.value)}
                placeholder="your@email.com"
              />
            </div>
            <Button
              className="w-full"
              onClick={handleApprove}
              disabled={submitting || !approverName.trim()}
            >
              {submitting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Check className="mr-2 h-4 w-4" />
              )}
              Approve Proof
            </Button>
          </Card>
        ) : (
          <Card className="p-6 space-y-4">
            <div>
              <Label>What changes are needed? *</Label>
              <textarea
                className="w-full rounded-md border px-3 py-2 text-sm"
                rows={5}
                value={changeNotes}
                onChange={(e) => setChangeNotes(e.target.value)}
                placeholder="Please describe the corrections needed..."
              />
            </div>
            <Button
              className="w-full"
              variant="destructive"
              onClick={handleChangeRequest}
              disabled={submitting || !changeNotes.trim()}
            >
              {submitting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <MessageSquare className="mr-2 h-4 w-4" />
              )}
              Submit Change Request
            </Button>
          </Card>
        )}
      </div>
    </div>
  )
}
