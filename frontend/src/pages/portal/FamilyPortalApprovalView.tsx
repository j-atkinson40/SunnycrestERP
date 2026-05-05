/**
 * FamilyPortalApprovalView — Phase 1E magic-link contextual surface.
 *
 * Per §3.26.11.9 + Path B substrate + §2.5 Portal Extension Pattern +
 * Phase 1E build prompt: rendered at
 * `/portal/{tenant-slug}/personalization-studio/family-approval/{token}`.
 *
 * The family is non-Bridgeable identity; the magic-link token IS the
 * canonical authentication factor (§3.26.11.9 kill-the-portal canon).
 *
 * **Canonical chrome per §14.10.5 magic-link contextual surface**:
 *   - FH-tenant-branded header (h-12, --portal-brand wash)
 *   - Mobile-first single-column layout (max-w-md)
 *   - Read-only canvas snapshot
 *   - 3-outcome action vocabulary (approve / request_changes / decline)
 *   - Bounded affordances filtered (no DotNav, no command bar, no
 *     settings — write_mode=limited per FAMILY_PORTAL_SPACE_TEMPLATE)
 *
 * **Canonical anti-pattern guards explicit at FE substrate**:
 *   - §2.5.4 Anti-pattern 18 (portal-as-replacement-for-tenant-UX
 *     rejected) — narrow scope: read-only canvas + 3-outcome action
 *     vocabulary; no parallel tenant UX.
 *   - §3.26.11.12.16 Anti-pattern 1 (operator agency at canonical
 *     commit affordance) — family selects outcome explicitly; no
 *     auto-commit on dwell or scroll.
 *   - §3.26.11.12.16 Anti-pattern 11 (UI-coupled Generation Focus
 *     design rejected) — chrome operates on canvas state JSON shape;
 *     UI surface is independent.
 */

import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import { Heart, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  commitFamilyApproval,
  getFamilyApprovalContext,
} from "@/services/personalization-studio-service"
import type {
  FamilyApprovalContextResponse,
  FamilyApprovalOutcome,
} from "@/types/personalization-studio"
import {
  FAMILY_APPROVAL_OUTCOMES,
  FAMILY_APPROVAL_REQUIRES_NOTE,
} from "@/types/personalization-studio"

type LoadState =
  | { status: "loading" }
  | { status: "ready"; data: FamilyApprovalContextResponse }
  | { status: "error"; code: number; message: string }
  | { status: "submitted"; outcome: FamilyApprovalOutcome }

const OUTCOME_LABELS: Record<FamilyApprovalOutcome, string> = {
  approve: "Approve",
  request_changes: "Request changes",
  decline: "Decline",
}

const OUTCOME_DESCRIPTIONS: Record<FamilyApprovalOutcome, string> = {
  approve: "I approve this design",
  request_changes:
    "Some details need to change before I approve",
  decline: "I do not want to proceed with this design",
}

export default function FamilyPortalApprovalView() {
  const params = useParams<{
    tenantSlug: string
    token: string
  }>()
  const tenantSlug = params.tenantSlug ?? ""
  const token = params.token ?? ""

  const [state, setState] = useState<LoadState>({ status: "loading" })
  const [outcome, setOutcome] = useState<FamilyApprovalOutcome | null>(null)
  const [completionNote, setCompletionNote] = useState("")
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const data = await getFamilyApprovalContext(tenantSlug, token)
        if (!cancelled) setState({ status: "ready", data })
      } catch (err) {
        if (cancelled) return
        // Best-effort error classification for canonical 401/410/etc.
        type AxiosLikeError = { response?: { status?: number; data?: { detail?: string } } }
        const e = err as AxiosLikeError
        const code = e.response?.status ?? 500
        const message =
          e.response?.data?.detail ??
          (code === 401
            ? "This approval link is not valid."
            : code === 410
              ? "This approval link has expired or already been used."
              : "We could not load this approval link.")
        setState({ status: "error", code, message })
      }
    }
    if (tenantSlug && token) load()
    return () => {
      cancelled = true
    }
  }, [tenantSlug, token])

  // Apply canonical tenant branding wash via inline CSS vars.
  useEffect(() => {
    if (state.status !== "ready") return
    const root = document.documentElement
    root.style.setProperty(
      "--portal-brand",
      state.data.branding.brand_color,
    )
    return () => {
      root.style.removeProperty("--portal-brand")
    }
  }, [state])

  if (state.status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-base">
        <Loader2 className="h-6 w-6 animate-spin text-content-muted" />
      </div>
    )
  }

  if (state.status === "error") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-surface-base px-6">
        <div className="max-w-md text-center">
          <Heart
            className="mx-auto mb-4 h-10 w-10 text-content-muted"
            aria-hidden
          />
          <p className="text-body text-content-strong">
            {state.message}
          </p>
          <p className="mt-2 text-caption text-content-muted">
            If you believe this is an error, please contact the funeral
            home that sent you this link.
          </p>
        </div>
      </div>
    )
  }

  if (state.status === "submitted") {
    const submittedCopy: Record<FamilyApprovalOutcome, string> = {
      approve:
        "Thank you. The funeral home has been notified that you approved the design.",
      request_changes:
        "Thank you. The funeral home has been notified that you requested changes and will follow up with you.",
      decline:
        "Thank you. The funeral home has been notified of your decision.",
    }
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-surface-base px-6">
        <div className="max-w-md text-center">
          <Heart
            className="mx-auto mb-4 h-10 w-10 text-status-success"
            aria-hidden
          />
          <p className="text-body text-content-strong">
            {submittedCopy[state.outcome]}
          </p>
          <p className="mt-3 text-caption text-content-muted">
            You can close this window now.
          </p>
        </div>
      </div>
    )
  }

  // state.status === "ready"
  const data = state.data
  const requiresNote =
    outcome != null && FAMILY_APPROVAL_REQUIRES_NOTE.includes(outcome)
  const noteFilled = completionNote.trim().length > 0
  const submitDisabled =
    submitting ||
    outcome == null ||
    (requiresNote && !noteFilled)

  async function handleSubmit() {
    if (outcome == null) return
    setSubmitting(true)
    try {
      await commitFamilyApproval(tenantSlug, token, {
        outcome,
        completion_note: completionNote.trim() || null,
      })
      setState({ status: "submitted", outcome })
    } catch (err) {
      type AxiosLikeError = { response?: { status?: number; data?: { detail?: string } } }
      const e = err as AxiosLikeError
      const code = e.response?.status ?? 500
      const message =
        e.response?.data?.detail ??
        (code === 409
          ? "This approval has already been recorded."
          : "We could not submit your decision. Please try again.")
      setState({ status: "error", code, message })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      data-testid="family-portal-approval-view"
      data-access-mode="portal_external"
      data-write-mode="limited"
      data-tenant-branded="true"
      className="min-h-screen bg-surface-base"
    >
      {/* FH-tenant-branded header (h-12, brand wash). Per §10.6 wash-not-reskin. */}
      <header
        className="flex h-12 items-center px-4 shadow-level-1"
        style={{
          backgroundColor:
            "var(--portal-brand, var(--accent))",
          color: "var(--content-on-accent)",
        }}
      >
        {data.branding.logo_url ? (
          <img
            src={data.branding.logo_url}
            alt={data.branding.display_name}
            className="h-7 w-auto"
          />
        ) : (
          <span className="text-body-sm font-medium">
            {data.branding.display_name}
          </span>
        )}
      </header>

      {/* Mobile-first single-column layout — max-w-md per §14.10.5. */}
      <main className="mx-auto w-full max-w-md px-4 py-6 sm:py-10">
        <h1 className="text-h2 font-plex-serif text-content-strong">
          Memorial design approval
        </h1>
        {data.decedent_name ? (
          <p className="mt-2 text-body text-content-muted">
            For{" "}
            <span className="text-content-strong">
              {data.decedent_name}
            </span>
          </p>
        ) : null}
        {data.fh_director_name ? (
          <p className="mt-1 text-body-sm text-content-muted">
            Prepared by {data.fh_director_name}
          </p>
        ) : null}

        {/* Read-only canvas snapshot. Phase 1E ships the canonical
            canvas-state JSON read; visual canvas rendering deferred to
            Phase 1F (canonical compositor render in read-only mode). */}
        <section
          aria-label="Memorial design preview"
          className="mt-6 rounded border border-border-subtle bg-surface-elevated p-4"
        >
          {data.canvas.canvas_state == null ? (
            <p className="text-body-sm text-content-muted">
              The funeral home is finalizing the design.
            </p>
          ) : (
            <CanvasReadonlyPreview
              canvas={
                data.canvas.canvas_state as unknown as Record<
                  string,
                  unknown
                >
              }
            />
          )}
        </section>

        {/* 3-outcome action vocabulary per §3.26.11.12.21. */}
        <section
          aria-label="Your decision"
          className="mt-8 space-y-3"
        >
          <p className="text-body-sm font-medium text-content-strong">
            What would you like to do?
          </p>
          {FAMILY_APPROVAL_OUTCOMES.map((opt) => (
            <button
              key={opt}
              type="button"
              data-testid={`outcome-${opt}`}
              data-selected={outcome === opt ? "true" : "false"}
              onClick={() => setOutcome(opt)}
              className={
                "block w-full rounded border px-4 py-3 text-left transition " +
                (outcome === opt
                  ? "border-accent bg-accent-subtle"
                  : "border-border-subtle bg-surface-base hover:bg-surface-sunken")
              }
            >
              <p className="text-body-sm font-medium text-content-strong">
                {OUTCOME_LABELS[opt]}
              </p>
              <p className="mt-1 text-caption text-content-muted">
                {OUTCOME_DESCRIPTIONS[opt]}
              </p>
            </button>
          ))}

          {requiresNote ? (
            <div className="pt-2">
              <label
                htmlFor="completion-note"
                className="block text-body-sm font-medium text-content-strong"
              >
                Please share what should change
                <span className="ml-1 text-status-error">*</span>
              </label>
              <Textarea
                id="completion-note"
                data-testid="completion-note-input"
                value={completionNote}
                onChange={(e) => setCompletionNote(e.target.value)}
                rows={4}
                maxLength={4000}
                className="mt-2"
                placeholder={
                  outcome === "request_changes"
                    ? "What would you like the funeral home to adjust?"
                    : "Why are you declining this design?"
                }
              />
            </div>
          ) : null}

          <div className="pt-4">
            <Button
              data-testid="submit-decision"
              type="button"
              size="lg"
              className="w-full"
              disabled={submitDisabled}
              onClick={handleSubmit}
            >
              {submitting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Submit decision
            </Button>
          </div>
        </section>

        <footer className="mt-10 text-center text-caption text-content-muted">
          Sent by {data.branding.display_name}.
        </footer>
      </main>
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────────
// Canonical read-only canvas snapshot — Phase 1E text summary.
//
// Phase 1E ships the canonical text summary; Phase 1F adds the canvas
// compositor render in read-only mode (canonical visual fidelity per
// §14.10.5). The canonical canvas-state JSON shape is read here per
// §3.26.11.12.5 substrate-consumption canonical.
// ─────────────────────────────────────────────────────────────────────


function CanvasReadonlyPreview({
  canvas,
}: {
  canvas: Record<string, unknown>
}) {
  // Per discovery output Section 2a + Phase 1A canvas state shape:
  // pull canonical fields without coupling FE chrome to canvas-element
  // shape. Phase 1F upgrades this to the canonical compositor render.
  const vault = canvas["vault_product"] as
    | { vault_product_name?: string | null }
    | null
    | undefined
  const nameDisplay = canvas["name_display"] as string | null | undefined
  const nameplate = canvas["nameplate_text"] as string | null | undefined
  const emblem = canvas["emblem_key"] as string | null | undefined
  const font = canvas["font"] as string | null | undefined
  const birthDate = canvas["birth_date_display"] as
    | string
    | null
    | undefined
  const deathDate = canvas["death_date_display"] as
    | string
    | null
    | undefined

  return (
    <dl className="space-y-3 text-body-sm">
      {vault?.vault_product_name ? (
        <FieldRow label="Vault" value={vault.vault_product_name} />
      ) : null}
      {nameDisplay ? <FieldRow label="Name" value={nameDisplay} /> : null}
      {birthDate || deathDate ? (
        <FieldRow
          label="Dates"
          value={[birthDate, deathDate].filter(Boolean).join(" — ")}
        />
      ) : null}
      {nameplate ? (
        <FieldRow label="Nameplate" value={nameplate} />
      ) : null}
      {emblem ? <FieldRow label="Emblem" value={emblem} /> : null}
      {font ? <FieldRow label="Font" value={font} /> : null}
    </dl>
  )
}


function FieldRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-caption text-content-muted">{label}</dt>
      <dd className="text-body-sm text-content-strong">{value}</dd>
    </div>
  )
}
