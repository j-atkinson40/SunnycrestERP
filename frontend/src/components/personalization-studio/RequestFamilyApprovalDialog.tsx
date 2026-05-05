/**
 * RequestFamilyApprovalDialog — Phase 1E FH-director-initiated request.
 *
 * Per §3.26.11.12.19 Personalization Studio canonical category +
 * §3.26.11.9 magic-link substrate + Phase 1E build prompt: this dialog
 * is the FH director's canonical commit affordance for sending the
 * canvas to the family for approval. The "Send to family for approval"
 * button is the canonical operator-agency commit point per §3.26.14.14.5
 * (FH director composes the action; system never auto-sends).
 *
 * **Canonical anti-pattern guards explicit at FE substrate**:
 *   - §3.26.11.12.16 Anti-pattern 1 (operator agency at canonical
 *     commit affordance) — FH director clicks "Send" explicitly; no
 *     auto-send on lifecycle transition.
 *   - §3.26.14.14.5 (operator-agency-at-commit-boundary discipline)
 *     — system can draft the email, but only the FH director's
 *     explicit click sends it.
 *
 * Mounts inside the canonical Personalization Studio canvas chrome
 * (FH-vertical authoring context only — Mfg-vertical contexts have no
 * family canonical participation per §3.26.11.12.19.3).
 */

import { useState } from "react"
import { Loader2, Mail } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { requestFamilyApproval } from "@/services/personalization-studio-service"
import type { RequestFamilyApprovalResponse } from "@/types/personalization-studio"


interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  instanceId: string
  /** Optional pre-fill (e.g., from FHCase informant email). */
  defaultFamilyEmail?: string | null
  defaultFamilyFirstName?: string | null
  /** Called when the request lands successfully. */
  onSent?: (resp: RequestFamilyApprovalResponse) => void
}


export function RequestFamilyApprovalDialog({
  open,
  onOpenChange,
  instanceId,
  defaultFamilyEmail,
  defaultFamilyFirstName,
  onSent,
}: Props) {
  const [familyEmail, setFamilyEmail] = useState(defaultFamilyEmail ?? "")
  const [familyFirstName, setFamilyFirstName] = useState(
    defaultFamilyFirstName ?? "",
  )
  const [optionalMessage, setOptionalMessage] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const emailValid = /\S+@\S+\.\S+/.test(familyEmail.trim())
  const submitDisabled = submitting || !emailValid

  async function handleSubmit() {
    setError(null)
    setSubmitting(true)
    try {
      const resp = await requestFamilyApproval(instanceId, {
        family_email: familyEmail.trim(),
        family_first_name: familyFirstName.trim() || null,
        optional_message: optionalMessage.trim() || null,
      })
      onSent?.(resp)
      onOpenChange(false)
    } catch (err) {
      type AxiosLikeError = {
        response?: { status?: number; data?: { detail?: string } }
      }
      const e = err as AxiosLikeError
      const message =
        e.response?.data?.detail ??
        "We could not send the approval request. Please try again."
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        data-testid="request-family-approval-dialog"
        className="sm:max-w-md"
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Mail className="h-4 w-4" aria-hidden />
            Send to family for approval
          </DialogTitle>
          <DialogDescription>
            We&apos;ll email a private link the family can use to review
            the design and approve it. The link expires in 7 days.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div>
            <Label htmlFor="family-email">Family email</Label>
            <Input
              id="family-email"
              data-testid="family-email-input"
              type="email"
              autoComplete="off"
              value={familyEmail}
              onChange={(e) => setFamilyEmail(e.target.value)}
              placeholder="family@example.com"
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="family-first-name">
              First name (optional)
            </Label>
            <Input
              id="family-first-name"
              data-testid="family-first-name-input"
              type="text"
              autoComplete="off"
              value={familyFirstName}
              onChange={(e) => setFamilyFirstName(e.target.value)}
              placeholder="For the email greeting"
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="optional-message">
              Personal note (optional)
            </Label>
            <Textarea
              id="optional-message"
              data-testid="optional-message-input"
              value={optionalMessage}
              onChange={(e) => setOptionalMessage(e.target.value)}
              rows={3}
              maxLength={2000}
              className="mt-1"
              placeholder="Anything you'd like to say to the family with the link"
            />
          </div>

          {error ? (
            <p
              data-testid="request-family-approval-error"
              className="text-caption text-status-error"
              role="alert"
            >
              {error}
            </p>
          ) : null}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button
            type="button"
            data-testid="request-family-approval-submit"
            onClick={handleSubmit}
            disabled={submitDisabled}
          >
            {submitting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : null}
            Send to family
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
