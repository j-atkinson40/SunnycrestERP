/**
 * WorkflowReviewItemDisplay — R-6.0b triage item display for the
 * `workflow_review_triage` queue.
 *
 * Renders a paused-workflow review item: extracted Generation Focus
 * output (input_data) presented as readable cards with per-line-item
 * confidence badges where applicable. Three actions:
 *
 *   - Approve              → POST /api/v1/triage/workflow-review/{id}/decide
 *                            with { decision: "approve" }
 *   - Reject               → reason modal → POST with
 *                            { decision: "reject", decision_notes }
 *   - Edit & Approve       → JsonTextareaEditor → POST with
 *                            { decision: "edit_and_approve", edited_data }
 *
 * Bypasses the standard TriageActionPalette dispatch (POST
 * `/sessions/.../action`) — review-item decisions go directly to the
 * canonical R-6.0a decide endpoint, which routes through
 * `workflow_review_adapter.commit_decision` and resumes the workflow
 * run via `workflow_engine.advance_run`.
 *
 * After a successful decision, calls `onAdvance()` so the surrounding
 * triage page advances to the next item.
 */

import { Check, Edit3, X } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { JsonTextareaEditor } from "@/lib/triage/json-textarea-editor"
import { commitWorkflowReviewDecision } from "@/services/triage-service"
import type { TriageItem } from "@/types/triage"


export interface WorkflowReviewItemDisplayProps {
  item: TriageItem
  /** Called after a successful decision is committed. The surrounding
   *  triage session should `advance()` to the next item. */
  onAdvance?: () => void | Promise<void>
}


export function WorkflowReviewItemDisplay({
  item,
  onAdvance,
}: WorkflowReviewItemDisplayProps) {
  const itemId = item.entity_id
  const focusLabel = humanizeFocusId(
    typeof item.title === "string" ? item.title : "",
  )
  const workflowName =
    typeof item.subtitle === "string" && item.subtitle ? item.subtitle : null
  const triggerSource = readString(item, "trigger_source")
  const createdAt = readString(item, "created_at")
  const inputData = readInputData(item)

  const [submitting, setSubmitting] = useState<
    null | "approve" | "reject" | "edit_and_approve"
  >(null)
  const [rejectOpen, setRejectOpen] = useState(false)
  const [rejectReason, setRejectReason] = useState("")
  const [editOpen, setEditOpen] = useState(false)

  const handleApprove = async () => {
    setSubmitting("approve")
    const res = await commitWorkflowReviewDecision(itemId, "approve")
    setSubmitting(null)
    if (res.ok) {
      toast.success("Approved · workflow advanced")
      await onAdvance?.()
    } else {
      toast.error(res.error)
    }
  }

  const handleReject = async () => {
    setSubmitting("reject")
    const res = await commitWorkflowReviewDecision(
      itemId,
      "reject",
      undefined,
      rejectReason || undefined,
    )
    setSubmitting(null)
    setRejectOpen(false)
    setRejectReason("")
    if (res.ok) {
      toast.success("Rejected · workflow halted")
      await onAdvance?.()
    } else {
      toast.error(res.error)
    }
  }

  const handleEditApprove = async (edited: unknown) => {
    setSubmitting("edit_and_approve")
    const editedDict =
      edited && typeof edited === "object" && !Array.isArray(edited)
        ? (edited as Record<string, unknown>)
        : { value: edited }
    const res = await commitWorkflowReviewDecision(
      itemId,
      "edit_and_approve",
      editedDict,
    )
    setSubmitting(null)
    if (res.ok) {
      setEditOpen(false)
      toast.success("Edited + approved · workflow advanced")
      await onAdvance?.()
    } else {
      toast.error(res.error)
      // Keep the editor open so the operator can retry.
    }
  }

  return (
    <Card data-testid={`workflow-review-item-${itemId}`}>
      <CardHeader>
        <CardTitle className="text-lg">
          Review {focusLabel || "extraction"}
        </CardTitle>
        <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-sm text-muted-foreground">
          {workflowName ? (
            <span>
              Workflow: <span className="text-content-base">{workflowName}</span>
            </span>
          ) : null}
          {triggerSource ? <span>Trigger: {triggerSource}</span> : null}
          {createdAt ? <span>Paused at: {createdAt}</span> : null}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <InputDataPreview data={inputData} />

        <div
          className="flex flex-wrap items-center gap-2"
          data-testid="workflow-review-actions"
        >
          <Button
            type="button"
            onClick={handleApprove}
            disabled={submitting !== null}
            data-testid="workflow-review-approve"
          >
            <Check size={14} className="mr-1" />
            {submitting === "approve" ? "Approving…" : "Approve"}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => setEditOpen(true)}
            disabled={submitting !== null}
            data-testid="workflow-review-edit"
          >
            <Edit3 size={14} className="mr-1" />
            Edit & Approve
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={() => setRejectOpen(true)}
            disabled={submitting !== null}
            data-testid="workflow-review-reject"
          >
            <X size={14} className="mr-1" />
            Reject
          </Button>
        </div>
      </CardContent>

      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent
          className="max-w-md"
          data-testid="workflow-review-reject-dialog"
        >
          <DialogHeader>
            <DialogTitle>Reject review item</DialogTitle>
            <DialogDescription>
              The workflow run halts. The reason is logged with the
              decision.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Label htmlFor="workflow-review-reject-reason">
              Reason (optional)
            </Label>
            <Textarea
              id="workflow-review-reject-reason"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              rows={4}
              placeholder="Explain why this extraction is being rejected"
              data-testid="workflow-review-reject-reason"
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setRejectOpen(false)}
              disabled={submitting === "reject"}
              data-testid="workflow-review-reject-cancel"
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={handleReject}
              disabled={submitting === "reject"}
              data-testid="workflow-review-reject-confirm"
            >
              {submitting === "reject" ? "Rejecting…" : "Reject"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <JsonTextareaEditor
        open={editOpen}
        onClose={() => setEditOpen(false)}
        initialData={inputData}
        title="Edit & approve review item"
        description="Mutate the extraction payload before approving. The edited payload flows into the workflow's resume input."
        onSave={handleEditApprove}
      />
    </Card>
  )
}


// ── Helpers ─────────────────────────────────────────────────────────


function readString(item: TriageItem, key: string): string | null {
  const direct = (item as Record<string, unknown>)[key]
  if (typeof direct === "string" && direct.length > 0) return direct
  const extras = (item as Record<string, unknown>)["extras"]
  if (extras && typeof extras === "object" && !Array.isArray(extras)) {
    const v = (extras as Record<string, unknown>)[key]
    if (typeof v === "string" && v.length > 0) return v
  }
  return null
}


function readInputData(item: TriageItem): unknown {
  // Backend r6.0a `_dq_workflow_review` writes `input_data` onto the
  // row; `_row_to_item_summary` carries it through `extras` because
  // it's listed in `body_fields` (R-6.0b platform_defaults change).
  const direct = (item as Record<string, unknown>)["input_data"]
  if (direct !== undefined) return direct
  const extras = (item as Record<string, unknown>)["extras"]
  if (extras && typeof extras === "object" && !Array.isArray(extras)) {
    const v = (extras as Record<string, unknown>)["input_data"]
    if (v !== undefined) return v
  }
  return null
}


function humanizeFocusId(slug: string): string {
  if (!slug) return ""
  return slug
    .replace(/_/g, " ")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
}


// ── Input data preview ──────────────────────────────────────────────


function InputDataPreview({ data }: { data: unknown }) {
  if (data == null) {
    return (
      <p className="text-sm text-muted-foreground">
        No payload preview available.
      </p>
    )
  }
  if (typeof data !== "object" || Array.isArray(data)) {
    return (
      <pre
        className="overflow-auto rounded-md border border-border-subtle bg-surface-sunken p-3 font-plex-mono text-caption text-content-base"
        data-testid="workflow-review-input-data"
      >
        {safeStringify(data)}
      </pre>
    )
  }
  const entries = Object.entries(data as Record<string, unknown>)
  if (entries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">Empty payload.</p>
    )
  }
  return (
    <dl
      className="space-y-2 text-sm"
      data-testid="workflow-review-input-data"
    >
      {entries.map(([key, value]) => (
        <FieldRow key={key} label={key} value={value} />
      ))}
    </dl>
  )
}


function FieldRow({ label, value }: { label: string; value: unknown }) {
  // Confidence-scored line-items shape — array of objects each with
  // `confidence` numeric. Render as per-item cards with badges.
  if (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every(
      (v) =>
        v &&
        typeof v === "object" &&
        !Array.isArray(v) &&
        "confidence" in (v as Record<string, unknown>),
    )
  ) {
    return (
      <div className="flex flex-col gap-1">
        <dt className="text-micro uppercase tracking-wider text-content-muted">
          {humanizeFocusId(label)}
        </dt>
        <dd className="space-y-1.5">
          {(value as Array<Record<string, unknown>>).map((row, idx) => (
            <LineItemCard key={idx} row={row} />
          ))}
        </dd>
      </div>
    )
  }
  return (
    <div className="grid grid-cols-[140px_1fr] gap-x-3 gap-y-0.5">
      <dt className="text-micro uppercase tracking-wider text-content-muted">
        {humanizeFocusId(label)}
      </dt>
      <dd className="text-content-base">
        {renderScalar(value)}
      </dd>
    </div>
  )
}


function LineItemCard({ row }: { row: Record<string, unknown> }) {
  const confidence =
    typeof row.confidence === "number" ? row.confidence : null
  const tone = confidenceTone(confidence)
  const label = readScalar(row, "label") ?? readScalar(row, "field")
  const valueText = readScalar(row, "value") ?? readScalar(row, "text")

  return (
    <div className="rounded-md border border-border-subtle bg-surface-elevated p-2.5">
      <div className="mb-1 flex items-start justify-between gap-2">
        <div className="flex-1 text-content-base">
          {label ? (
            <span className="font-medium">{label}</span>
          ) : null}
          {label && valueText ? <span className="mx-1.5">·</span> : null}
          {valueText ? <span>{valueText}</span> : null}
          {!label && !valueText ? (
            <code className="font-plex-mono text-caption text-content-muted">
              {safeStringify(row)}
            </code>
          ) : null}
        </div>
        {confidence !== null ? (
          <Badge variant={tone}>{Math.round(confidence * 100)}%</Badge>
        ) : null}
      </div>
    </div>
  )
}


function confidenceTone(
  confidence: number | null,
): "success" | "warning" | "error" | "outline" {
  if (confidence === null || Number.isNaN(confidence)) return "outline"
  if (confidence >= 0.85) return "success"
  if (confidence >= 0.5) return "warning"
  return "error"
}


function readScalar(
  row: Record<string, unknown>,
  key: string,
): string | null {
  const v = row[key]
  if (v == null) return null
  if (typeof v === "string") return v
  if (typeof v === "number" || typeof v === "boolean") return String(v)
  return null
}


function renderScalar(value: unknown) {
  if (value == null) return <span className="text-content-muted">—</span>
  if (typeof value === "string") {
    return <span>{value}</span>
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return <span className="font-plex-mono">{String(value)}</span>
  }
  return (
    <code className="font-plex-mono text-caption text-content-muted">
      {safeStringify(value)}
    </code>
  )
}


function safeStringify(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}
