/**
 * ManufacturerPersonalizationStudioFromShareView — Phase 1F Mfg-side
 * canonical entry point at canonical `manufacturer_from_fh_share`
 * authoring context.
 *
 * Per §3.26.11.12.19.3 Q3 canonical pairing + §3.26.11.12.19.4 cross-
 * tenant DocumentShare grant timing canonical (Q2 baked: full
 * disclosure per-instance via grant) + Q9c canonical-discipline
 * guidance (read-only chrome at canvas-frame-level; canvas-element-
 * level visibility canonical regardless of authoring context).
 *
 * **Canonical chrome per §14.10.5 + §14.14.5**:
 *   - Read-only badge at canonical canvas-frame substrate (Q9c)
 *   - "Shared from {fh_tenant_name}" canonical attribution
 *   - "Mark reviewed" canonical commit affordance per canonical
 *     per-authoring-context label canon at §14.14.5
 *   - Canvas elements canonical-render at canonical visibility (no
 *     read-only-mode element styling distinction; Anti-pattern 14
 *     portal-specific feature creep guard preserved)
 *   - Canvas interactions canonical-disabled at canonical chrome
 *     substrate (drag + selection + editing canonical-disabled per
 *     canonical Mfg-tenant scope)
 *
 * **Canonical anti-pattern guards explicit at FE substrate**:
 *   - §3.26.11.12.16 Anti-pattern 12 (parallel architectures rejected)
 *     — canonical Mfg-tenant entry point shares canonical canvas
 *     component substrate with canonical FH-tenant authoring context;
 *     canonical authoring_context discriminator dispatches canonical
 *     chrome at canonical chrome substrate.
 *   - §2.5.4 Anti-pattern 17 (canonical action vocabulary bypassing
 *     rejected) — canonical "Mark reviewed" commit canonical only;
 *     canonical canvas mutations canonical-rejected at service layer
 *     with canonical 403.
 */

import { useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { CheckCircle2, ChevronLeft, Eye, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  commitInstance,
  openInstanceFromShare,
} from "@/services/personalization-studio-service"
import type {
  CanvasState,
  FromShareInstanceResponse,
  GenerationFocusInstance,
} from "@/types/personalization-studio"


type LoadState =
  | { status: "loading" }
  | { status: "ready"; data: FromShareInstanceResponse }
  | { status: "reviewed"; data: FromShareInstanceResponse }
  | { status: "error"; code: number; message: string }


export default function ManufacturerPersonalizationStudioFromShareView() {
  const params = useParams<{ documentShareId: string }>()
  const navigate = useNavigate()
  const documentShareId = params.documentShareId ?? ""

  const [state, setState] = useState<LoadState>({ status: "loading" })
  const [committing, setCommitting] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const data = await openInstanceFromShare(documentShareId)
        if (cancelled) return
        // Canonical lifecycle_state at canonical "committed" surfaces
        // canonical reviewed-state chrome (canonical re-open at
        // canonical Mfg-tenant scope post-Mark-reviewed).
        if (data.instance.lifecycle_state === "committed") {
          setState({ status: "reviewed", data })
        } else {
          setState({ status: "ready", data })
        }
      } catch (err) {
        if (cancelled) return
        type AxiosLikeError = {
          response?: { status?: number; data?: { detail?: string } }
        }
        const e = err as AxiosLikeError
        const code = e.response?.status ?? 500
        const message =
          e.response?.data?.detail ??
          (code === 404
            ? "This shared design is not available."
            : code === 403
              ? "Access to this shared design has been revoked."
              : "We could not load this shared design.")
        setState({ status: "error", code, message })
      }
    }
    if (documentShareId) load()
    return () => {
      cancelled = true
    }
  }, [documentShareId])

  if (state.status === "loading") {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-content-muted" />
      </div>
    )
  }

  if (state.status === "error") {
    return (
      <div className="mx-auto max-w-2xl px-6 py-12 text-center">
        <p className="text-body text-content-strong">
          {state.message}
        </p>
        <Button
          type="button"
          variant="outline"
          className="mt-6"
          onClick={() => navigate(-1)}
        >
          <ChevronLeft className="mr-1 h-4 w-4" />
          Back
        </Button>
      </div>
    )
  }

  const data = state.data
  const reviewed = state.status === "reviewed"

  async function handleMarkReviewed() {
    if (state.status !== "ready") return
    setCommitting(true)
    try {
      const updated = await commitInstance(state.data.instance.id)
      setState({
        status: "reviewed",
        data: { ...state.data, instance: updated },
      })
    } catch (err) {
      type AxiosLikeError = {
        response?: { status?: number; data?: { detail?: string } }
      }
      const e = err as AxiosLikeError
      const code = e.response?.status ?? 500
      const message =
        e.response?.data?.detail ??
        "We could not mark this design as reviewed."
      setState({ status: "error", code, message })
    } finally {
      setCommitting(false)
    }
  }

  return (
    <div
      data-testid="manufacturer-personalization-studio-from-share-view"
      data-authoring-context="manufacturer_from_fh_share"
      data-write-mode="read_only"
      className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6"
    >
      {/* Read-only attribution + canvas-frame chrome per §14.10.5 +
          Q9c canonical-discipline. */}
      <header className="mb-6">
        <div className="flex items-center gap-2 text-caption text-content-muted">
          <Eye className="h-3.5 w-3.5" aria-hidden />
          <span data-testid="read-only-badge">Read-only</span>
          <span aria-hidden>·</span>
          <span data-testid="shared-from-attribution">
            Shared from{" "}
            <span className="font-medium text-content-strong">
              {data.owner_company_name ?? "the funeral home"}
            </span>
          </span>
        </div>
        <h1 className="mt-3 text-h2 font-plex-serif text-content-strong">
          Memorial design — fulfillment review
        </h1>
        {data.decedent_name ? (
          <p className="mt-1 text-body text-content-muted">
            For{" "}
            <span className="text-content-strong">
              {data.decedent_name}
            </span>
          </p>
        ) : null}
      </header>

      {/* Read-only canvas snapshot. Q9c: canvas elements render at
          canonical visibility; chrome-frame distinction marks the
          authoring-context-bounded action vocabulary. */}
      <section
        aria-label="Memorial design"
        data-testid="readonly-canvas-frame"
        className="rounded border border-border-subtle bg-surface-elevated p-4"
      >
        {data.canvas_state == null ? (
          <p className="text-body-sm text-content-muted">
            The funeral home has not committed a canvas state for this
            design yet.
          </p>
        ) : (
          <CanvasReadonlyPreview canvas={data.canvas_state} />
        )}
      </section>

      {/* Action footer — canonical "Mark reviewed" commit affordance per
          §14.14.5 canonical per-authoring-context labels. Canonical
          Anti-pattern 17: action vocabulary canonically bounded;
          canvas-mutation affordances canonically absent. */}
      <footer className="mt-8 flex items-center justify-between">
        <Button
          type="button"
          variant="outline"
          onClick={() => navigate(-1)}
        >
          <ChevronLeft className="mr-1 h-4 w-4" />
          Back
        </Button>
        {reviewed ? (
          <span
            data-testid="mark-reviewed-confirmation"
            className="inline-flex items-center gap-2 text-body-sm text-status-success"
          >
            <CheckCircle2 className="h-4 w-4" aria-hidden />
            Marked reviewed
          </span>
        ) : (
          <Button
            type="button"
            data-testid="mark-reviewed-button"
            onClick={handleMarkReviewed}
            disabled={committing}
          >
            {committing ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : null}
            Mark reviewed
          </Button>
        )}
      </footer>
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────────
// Canonical canvas read-only preview — Phase 1F Mfg-side surface.
//
// Mirrors canonical Phase 1E FamilyPortalApprovalView read-only canvas
// snapshot shape (Phase 1F substrate-shares canonical canvas state JSON
// read pattern at canonical Mfg-tenant scope; Phase 1G deepens to
// canvas-compositor-render-in-read-only-mode per §14.10.5 canonical
// visual fidelity).
// ─────────────────────────────────────────────────────────────────────


function CanvasReadonlyPreview({ canvas }: { canvas: CanvasState }) {
  const canvasAny = canvas as unknown as Record<string, unknown>
  const vault = canvasAny["vault_product"] as
    | { vault_product_name?: string | null }
    | null
    | undefined
  const nameDisplay = canvasAny["name_display"] as string | null | undefined
  const nameplate = canvasAny["nameplate_text"] as string | null | undefined
  const emblem = canvasAny["emblem_key"] as string | null | undefined
  const font = canvasAny["font"] as string | null | undefined
  const birthDate = canvasAny["birth_date_display"] as
    | string
    | null
    | undefined
  const deathDate = canvasAny["death_date_display"] as
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


// Canonical export for App.tsx route registration (canonical re-export
// at module level per existing canonical pattern).
export type { FromShareInstanceResponse, GenerationFocusInstance }
