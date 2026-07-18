/**
 * The Ponder — a staged, calm, scrubbable walkthrough of HOW an automation
 * works (P1). Live-rendered from the derivation endpoint — never baked.
 *
 * DESIGN COMMITMENTS (DESIGN_LANGUAGE.md):
 * - The ponder is a lights-down moment: the stage deliberately commits to the
 *   evening look in BOTH modes (a dimmed warm-black room; DL sanctions a
 *   single-look surface when the design commits). The accent is the DL
 *   terracotta — a single value across modes, so var(--accent) is safe here.
 * - SLOW IS A FEATURE: beats hold ~4.5s on autoplay; entrances settle
 *   (duration-arrive / ease-settle — things ARRIVE), exits recede
 *   (ease-gentle). No new animation library — staged CSS + one SVG line-draw.
 * - Reduced motion honored: beats become plain cross-fades, no line-draw,
 *   no translate.
 *
 * EDIT MODE (P1's ride-along, platform-admin scope — this whole tree is the
 * admin app): click a beat's text, write the caption, save to the task row's
 * ponder JSONB. Authoring happens where the teaching lives — WYSIWYG by
 * construction. Cleared captions fall back to the derived text (plainer,
 * never stale). Orphaned captions (their beat key no longer exists) surface
 * ONLY in edit mode, reclaimable — they never render to viewers.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  ArrowRight, BarChart3, BookOpen, ChevronLeft, ChevronRight, Clock, Inbox,
  LayoutPanelTop, Pause, PauseCircle, Pencil, Play, RotateCcw, Trash2,
  Landmark, Workflow as WorkflowIcon, X,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  type PonderBeat, type PonderScript,
} from "@/bridgeable-admin/services/moc-service"
import { usePonderService } from "./ponder-service-context"
import { MotifScene } from "./ponder-motifs"
import { ArtifactPreview, AudienceLine } from "./PonderArtifacts"
import { LiveEditConfirm, useLiveEditGate } from "./LiveEditConfirm"
import { PonderFiresStrip } from "./PonderFiresStrip"
import { PonderParamFields } from "./PonderParamFields"
import { PonderTriggerEditor } from "./PonderTriggerEditor"
import { AdoptScheduleConfirm } from "./AdoptScheduleConfirm"
import { TaskOfferPublishBar } from "./TaskOfferPublishBar"

const BEAT_HOLD_MS = 4500

/** The stage's committed evening palette (deliberate single-look surface). */
const STAGE = {
  text: "#EAE3DA",
  muted: "#A79B8E",
  faint: "#6E6459",
  card: "rgba(255,251,245,0.055)",
  cardBorder: "rgba(234,227,218,0.14)",
}

const KIND_GLYPH = {
  when: Clock,
  step: WorkflowIcon,
  pause: PauseCircle,
  focus: LayoutPanelTop,
  downstream: Inbox,
  garnish: BarChart3,
  setup: Landmark,
  // Map Home — the composition kinds (area/onboarding ponders).
  opening: BookOpen,
  task: WorkflowIcon,
  closing: ArrowRight,
} as const

const KIND_EYEBROW: Record<PonderBeat["kind"], string> = {
  when: "When",
  step: "Then",
  pause: "The run pauses for you",
  focus: "Where you work",
  downstream: "Where it lands",
  garnish: "Last time it ran",
  setup: "The feed",
  // Map Home — the composition kinds.
  opening: "How this area thinks",
  task: "What runs here",
  closing: "Where to go",
}

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false,
  )
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)")
    const on = () => setReduced(mq.matches)
    mq.addEventListener("change", on)
    return () => mq.removeEventListener("change", on)
  }, [])
  return reduced
}

export function PonderOverlay({
  taskId, onClose, canEdit = true, onRequestEdit, onViewed, onCompleted,
  onNavigate, onOpenPonder,
}: {
  taskId: string
  onClose: () => void
  /** P2 — role mirror-honesty: false renders ZERO edit affordances. */
  canEdit?: boolean
  /** P2 — the fork gate: asked before ENTERING edit mode (resolve false →
   * stay in view mode; the tenant page forks + swaps taskId on accept). */
  onRequestEdit?: () => Promise<boolean>
  /** Map Home — the QUIET engagement hooks: fired once on open / once on
   * reaching the final beat. Fire-and-forget; the overlay never waits. */
  onViewed?: () => void
  onCompleted?: () => void
  /** Map Home — a beat's deep link (the closing beat). The page supplies
   * SPA navigation; the overlay closes first. */
  onNavigate?: (href: string) => void
  /** Reframe R-2 — a beat that opens ANOTHER ponder (the job's automation
   * beats → the automation's full walkthrough). The page swaps the overlay
   * id; without the prop the affordance stays hidden (honest absence). */
  onOpenPonder?: (overlayId: string) => void
}) {
  const svc = usePonderService()
  const [script, setScript] = useState<PonderScript | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [editMode, setEditMode] = useState(false)
  const [draft, setDraft] = useState<string | null>(null) // null = not editing this beat
  const [saving, setSaving] = useState(false)
  const [adopting, setAdopting] = useState(false) // T-1 — the adopt confirm
  const reduced = usePrefersReducedMotion()
  const timerRef = useRef<number | null>(null)
  const completedRef = useRef(false)
  // The live-edit gravity: one confirm gate, all editors. Dry-run tasks
  // pass straight through (no dialog).
  const { confirmGate, pending, settle } = useLiveEditGate(script?.is_live)

  useEffect(() => {
    // A taskId swap (the R-2 ponder deep-link) is a fresh walkthrough:
    // rewind, resume autoplay, re-arm completion.
    setScript(null)
    setIndex(0)
    setPlaying(true)
    completedRef.current = false
    svc.getPonderScript(taskId)
      .then(setScript)
      .catch(() => setError("Couldn't derive this walkthrough."))
    onViewed?.()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId])

  // Map Home — completion fires ONCE when the final beat is reached
  // (per walkthrough — the taskId effect re-arms it).
  useEffect(() => {
    if (!script || beats.length === 0) return
    if (index >= beats.length - 1 && !completedRef.current) {
      completedRef.current = true
      onCompleted?.()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, script])

  const beats = script?.beats ?? []
  const beat: PonderBeat | undefined = beats[index]
  const atEnd = index >= beats.length - 1

  // Autoplay — SLOW is a feature. Stops on scrub/edit; resumes via the toggle.
  useEffect(() => {
    if (!playing || editMode || !script || atEnd) return
    timerRef.current = window.setTimeout(
      () => setIndex((i) => Math.min(i + 1, beats.length - 1)),
      BEAT_HOLD_MS,
    )
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current)
    }
  }, [playing, editMode, script, index, atEnd, beats.length])

  const jump = useCallback((i: number) => {
    setPlaying(false) // a scrub is a claim of control; hold it
    setDraft(null)
    setIndex(Math.max(0, Math.min(i, beats.length - 1)))
  }, [beats.length])

  // Keys: Esc closes; arrows scrub; space toggles play.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === "TEXTAREA" || t.tagName === "INPUT")) {
        if (e.key === "Escape") setDraft(null)
        return
      }
      if (e.key === "Escape") onClose()
      else if (e.key === "ArrowRight") jump(index + 1)
      else if (e.key === "ArrowLeft") jump(index - 1)
      else if (e.key === " ") { e.preventDefault(); setPlaying((p) => !p) }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose, jump, index])

  async function saveCaption(text: string | null) {
    if (!script || !beat) return
    setSaving(true)
    try {
      await svc.savePonderCaption(script.task_id, beat.key, text)
      const fresh = await svc.getPonderScript(script.task_id)
      setScript(fresh)
      setDraft(null)
    } catch {
      setError("Couldn't save the caption.")
    } finally {
      setSaving(false)
    }
  }

  async function reclaimOrphan(key: string) {
    if (!script) return
    await svc.savePonderCaption(script.task_id, key, null)
    setScript(await svc.getPonderScript(script.task_id))
  }

  const stepBeats = useMemo(
    () => beats.filter((b) => b.kind === "step" || b.kind === "pause"),
    [beats],
  )
  const stepPosition = beat && (beat.kind === "step" || beat.kind === "pause")
    ? stepBeats.findIndex((b) => b.key === beat.key) + 1
    : null

  const Glyph = beat ? KIND_GLYPH[beat.kind] : Clock

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col"
      style={{ background: "rgba(23, 19, 16, 0.96)", backdropFilter: "blur(6px)" }}
      role="dialog"
      aria-modal="true"
      aria-label={`How ${script?.task_name ?? "this"} works`}
      data-testid="ponder-overlay"
    >
      <style>{`
        @keyframes ponder-arrive {
          from { opacity: 0; transform: translateY(14px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes ponder-fade {
          from { opacity: 0; } to { opacity: 1; }
        }
        @keyframes ponder-draw {
          from { stroke-dashoffset: 48; } to { stroke-dashoffset: 0; }
        }
        .ponder-beat-enter {
          animation: ponder-arrive var(--duration-arrive, 400ms) var(--ease-settle, cubic-bezier(0.2,0,0.1,1)) both;
        }
        .ponder-beat-enter-reduced { animation: ponder-fade 300ms ease both; }
        @keyframes ponder-breathe {
          0%, 100% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.06); opacity: 0.82; }
        }
        .ponder-breathe { animation: ponder-breathe 2600ms var(--ease-gentle, cubic-bezier(0.4,0,0.4,1)) infinite; }
        .ponder-line-draw {
          stroke-dasharray: 48; stroke-dashoffset: 48;
          animation: ponder-draw 600ms var(--ease-settle, cubic-bezier(0.2,0,0.1,1)) 120ms forwards;
        }
      `}</style>

      {/* Top chrome */}
      <div className="flex items-center justify-between px-6 py-4">
        <div className="min-w-0">
          <p className="text-caption uppercase tracking-wide" style={{ color: STAGE.faint }}>
            How this works
          </p>
          <p className="truncate text-h3 font-medium" style={{ color: STAGE.text }}>
            {script?.task_name ?? "…"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {canEdit ? (
            <button
              type="button"
              onClick={() => {
                if (editMode) { setEditMode(false); setDraft(null); return }
                const enter = () => { setEditMode(true); setPlaying(false); setDraft(null) }
                if (onRequestEdit) { void onRequestEdit().then((ok) => { if (ok) enter() }) }
                else enter()
              }}
              className="focus-ring-accent inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-body-sm transition-colors duration-quick"
              style={{ color: editMode ? "var(--accent)" : STAGE.muted }}
              data-testid="ponder-edit-toggle"
            >
              <Pencil size={14} />
              {editMode ? "Done editing" : "Edit"}
            </button>
          ) : null}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="focus-ring-accent rounded-md p-2 transition-colors duration-quick hover:text-white"
            style={{ color: STAGE.muted }}
            data-testid="ponder-close"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* The stage */}
      <div className="flex min-h-0 flex-1 items-center justify-center px-6">
        {error ? (
          <p className="text-body" style={{ color: STAGE.muted }}>{error}</p>
        ) : !script || !beat ? (
          <p className="text-body" style={{ color: STAGE.faint }}>Deriving…</p>
        ) : (
          <div
            key={beat.key}
            className={`w-full max-w-2xl ${reduced ? "ponder-beat-enter-reduced" : "ponder-beat-enter"}`}
            data-testid={`ponder-beat-${beat.key}`}
          >
            {/* Ponder Enrichment — the artifact ABOVE everything: the real
                document/focus floats on top; the beloved beat block below,
                exactly as it always was, nudged a little lower. */}
            {beat.artifact ? (
              <div className="mb-8 flex justify-center">
                <ArtifactPreview artifact={beat.artifact} />
              </div>
            ) : null}

            {/* Connector line-draw (skipped under reduced motion) */}
            {!reduced && (beat.kind === "step" || beat.kind === "pause") && index > 1 ? (
              <svg width="2" height="48" className="mx-auto mb-2 block" aria-hidden>
                <line
                  x1="1" y1="0" x2="1" y2="48"
                  stroke={STAGE.cardBorder} strokeWidth="2"
                  className="ponder-line-draw"
                />
              </svg>
            ) : null}

            <div className={`flex items-start gap-5 ${beat.artifact ? "justify-center text-center" : ""}`}>
              <div
                className={`mt-1 flex h-12 w-12 shrink-0 items-center justify-center rounded-full ${beat.kind === "pause" && !reduced ? "ponder-breathe" : ""}`}
                style={{
                  background: beat.kind === "pause" ? "rgba(156,86,64,0.18)" : STAGE.card,
                  border: `1px solid ${beat.kind === "pause" ? "var(--accent)" : STAGE.cardBorder}`,
                  color: beat.kind === "pause" ? "var(--accent)" : STAGE.muted,
                }}
              >
                <Glyph size={22} strokeWidth={1.6} />
              </div>
              <div className={beat.artifact ? "min-w-0 max-w-lg" : "min-w-0 flex-1"}>
                <p className={`mb-1 flex items-center gap-2 text-caption uppercase tracking-wide ${beat.artifact ? "justify-center" : ""}`} style={{ color: STAGE.faint }}>
                  {KIND_EYEBROW[beat.kind]}
                  {stepPosition ? (
                    <span>· step {stepPosition} of {stepBeats.length}</span>
                  ) : null}
                  {editMode ? (
                    <span
                      className="rounded-full px-1.5 py-0.5 text-micro"
                      style={{
                        background: beat.authored ? "rgba(156,86,64,0.22)" : STAGE.card,
                        color: beat.authored ? "var(--accent)" : STAGE.faint,
                      }}
                    >
                      {beat.authored ? "authored" : "derived"}
                    </span>
                  ) : null}
                </p>
                {beat.label ? (
                  <p className="text-h4 font-medium capitalize" style={{ color: STAGE.text }}>
                    {beat.label}
                  </p>
                ) : null}

                {beat.kind !== "pause" ? (
                  <div className={`mt-2 ${beat.artifact ? "flex justify-center" : ""}`}>
                    <MotifScene motif={beat.motif} reduced={reduced} />
                  </div>
                ) : null}

                {editMode && draft !== null ? (
                  <div className="mt-2" data-testid="ponder-caption-editor">
                    <Textarea
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      rows={3}
                      autoFocus
                      placeholder={beat.derived_text}
                      className="bg-transparent text-body"
                      style={{ color: STAGE.text, borderColor: STAGE.cardBorder }}
                    />
                    <div className="mt-2 flex items-center gap-2">
                      <Button size="sm" disabled={saving} onClick={() => void saveCaption(draft)}>
                        Save caption
                      </Button>
                      {beat.authored ? (
                        <Button size="sm" variant="ghost" disabled={saving}
                          onClick={() => void saveCaption(null)}>
                          Clear → derived
                        </Button>
                      ) : null}
                      <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <p
                    className={`mt-1 text-xl leading-relaxed ${editMode ? "cursor-text rounded-md px-1 -mx-1 transition-colors duration-quick hover:bg-white/5" : ""}`}
                    style={{ color: STAGE.text, fontWeight: 350, whiteSpace: "pre-line" }}
                    onClick={editMode ? () => setDraft(beat.authored ? beat.text : "") : undefined}
                    title={editMode ? "Click to author this beat's caption" : undefined}
                  >
                    {beat.text}
                  </p>
                )}

                {beat.kind === "downstream" && beat.queue_label ? (
                  <p className="mt-2 text-body-sm" style={{ color: STAGE.muted }}>
                    → {beat.queue_label}
                  </p>
                ) : null}

                <AudienceLine audience={beat.audience} />

                {/* Reframe R-2 — the beat's ponder deep-link (the job's
                    automation beats walk into the automation's own story). */}
                {beat.ponder_ref && onOpenPonder ? (
                  <button
                    type="button"
                    onClick={() => onOpenPonder(beat.ponder_ref!.overlay_id)}
                    className="focus-ring-accent mt-3 inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-body-sm font-medium"
                    style={{ background: STAGE.card, border: `1px solid ${STAGE.cardBorder}`, color: STAGE.text }}
                    data-testid="ponder-beat-ponder-ref"
                  >
                    {beat.ponder_ref.label}
                    <ArrowRight size={13} />
                  </button>
                ) : null}

                {/* Map Home — the closing beat's deep link. */}
                {beat.link ? (
                  <button
                    type="button"
                    onClick={() => {
                      const href = beat.link!.href
                      onClose()
                      onNavigate?.(href)
                    }}
                    className="focus-ring-accent mt-3 inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-body-sm font-medium"
                    style={{ background: STAGE.card, border: `1px solid ${STAGE.cardBorder}`, color: STAGE.text }}
                    data-testid="ponder-beat-link"
                  >
                    {beat.link.label}
                    <ArrowRight size={13} />
                  </button>
                ) : null}

                {/* T-0 — the authority badge: the standard scheduler is the
                    firing truth for this beat (quiet, informative). */}
                {beat.kind === "when" && beat.managed_by === "standard_scheduler" ? (
                  <p
                    className="mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-caption"
                    style={{ background: STAGE.card, border: `1px solid ${STAGE.cardBorder}`, color: STAGE.muted }}
                    data-testid="ponder-when-managed-badge"
                  >
                    managed by the standard scheduler
                  </p>
                ) : null}

                {/* T-0 — the fork's honest preview line: their composed
                    schedule previews in dry-run; the standard still runs
                    the real fires until the transfer. */}
                {beat.kind === "when" && script?.owned &&
                 script?.task_scope === "tenant_override" &&
                 script?.schedule_authority === "runtime_scheduler" ? (
                  <p className="mt-2 text-caption" style={{ color: STAGE.faint }}
                    data-testid="ponder-when-fork-preview-note">
                    Previewing in dry-run — the standard schedule still runs
                    the real fires until the transfer.
                  </p>
                ) : null}

                {/* T-0 — THE COMPOSER BLOCKS on runtime-scheduled mirrors,
                    with the reason. A composer that writes non-authoritative
                    schedules is a half-told lie; block until the transfer. */}
                {editMode && beat.kind === "when" && !beat.editable &&
                 beat.managed_by === "standard_scheduler" ? (
                  <div
                    className="mt-3 rounded-md p-3 text-left"
                    style={{ background: STAGE.card, border: `1px solid ${STAGE.cardBorder}` }}
                    data-testid="ponder-composer-blocked"
                  >
                    <p className="text-body-sm" style={{ color: STAGE.muted }}>
                      This automation's schedule is managed by the standard
                      scheduler — editing arrives with the transfer.
                    </p>
                    {/* T-1 — the transfer itself (admin only: the tenant
                        service carries no adoptSchedule, so the affordance
                        structurally can't render there). */}
                    {svc.adoptSchedule && script ? (
                      <Button
                        size="sm" variant="outline" className="mt-2"
                        onClick={() => setAdopting(true)}
                        data-testid="ponder-adopt-schedule-button"
                      >
                        Adopt this schedule…
                      </Button>
                    ) : null}
                    {adopting && svc.adoptSchedule && script ? (
                      <AdoptScheduleConfirm
                        taskName={script.task_name}
                        scheduleProse={beat.text}
                        onCancel={() => setAdopting(false)}
                        onConfirm={async () => {
                          await svc.adoptSchedule!(script.task_id)
                          // The honesty guard reflects the transfer: refetch —
                          // the badge flips (authority moc), the composer
                          // unblocks, the WHEN beat derives from the carried
                          // trigger.
                          setScript(await svc.getPonderScript(script.task_id))
                          setAdopting(false)
                        }}
                      />
                    ) : null}
                  </div>
                ) : null}

                {/* Tenant Ponder-Editor P1 — the WHEN beat's trigger editor.
                    Editing happens where the teaching lives; on save the
                    script refetches and the beat visibly re-derives. */}
                {editMode && beat.kind === "when" && beat.editable && script ? (
                  <PonderTriggerEditor
                    taskId={script.task_id}
                    vertical={script.vertical}
                    triggers={beat.triggers ?? []}
                    onSaved={async () => setScript(await svc.getPonderScript(script.task_id))}
                    confirmGate={confirmGate}
                  />
                ) : null}

                {/* Step beats: the declared params as fields (email settings,
                    audience roles, thresholds) — write-what-you-read; the
                    beat re-derives on save. */}
                {editMode && beat.kind === "step" && beat.params && script?.workflow_id ? (
                  <PonderParamFields
                    workflowId={script.workflow_id}
                    params={beat.params}
                    onSaved={async () => setScript(await svc.getPonderScript(script.task_id))}
                    confirmGate={confirmGate}
                  />
                ) : null}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Edit mode: orphaned captions, reclaimable — never shown to viewers */}
      {editMode && script && Object.keys(script.orphaned_captions).length > 0 ? (
        <div className="mx-auto mb-2 w-full max-w-2xl rounded-md px-4 py-3"
          style={{ background: STAGE.card, border: `1px solid ${STAGE.cardBorder}` }}
          data-testid="ponder-orphans"
        >
          <p className="mb-1 text-caption uppercase tracking-wide" style={{ color: STAGE.faint }}>
            Orphaned captions (their step no longer exists)
          </p>
          {Object.entries(script.orphaned_captions).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between gap-3 py-1">
              <p className="min-w-0 truncate text-body-sm" style={{ color: STAGE.muted }}>
                <span className="font-mono text-micro" style={{ color: STAGE.faint }}>{k}</span>
                {"  "}{v}
              </p>
              <button type="button" onClick={() => void reclaimOrphan(k)}
                className="focus-ring-accent shrink-0 rounded p-1"
                style={{ color: STAGE.faint }} aria-label={`Remove orphaned caption ${k}`}>
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>
      ) : null}

      {/* The scrub rail */}
      <div className="flex items-center justify-center gap-4 px-6 pb-6 pt-2" data-testid="ponder-dot-rail">
        <button type="button" onClick={() => jump(index - 1)} disabled={index === 0}
          aria-label="Previous beat"
          className="focus-ring-accent rounded-md p-1.5 disabled:opacity-30"
          style={{ color: STAGE.muted }}>
          <ChevronLeft size={18} />
        </button>
        <div className="flex items-center gap-2">
          {beats.map((b, i) => (
            <button
              key={b.key}
              type="button"
              onClick={() => jump(i)}
              aria-label={`Beat ${i + 1}`}
              className="focus-ring-accent rounded-full transition-all duration-settle"
              style={{
                width: i === index ? 22 : 8,
                height: 8,
                background: i === index
                  ? "var(--accent)"
                  : i < index ? STAGE.muted : "rgba(234,227,218,0.18)",
              }}
            />
          ))}
        </div>
        <button type="button" onClick={() => jump(index + 1)} disabled={atEnd}
          aria-label="Next beat"
          className="focus-ring-accent rounded-md p-1.5 disabled:opacity-30"
          style={{ color: STAGE.muted }}>
          <ChevronRight size={18} />
        </button>
        <div className="ml-2 flex items-center gap-1">
          {atEnd ? (
            <button type="button" onClick={() => { setIndex(0); setPlaying(true) }}
              aria-label="Replay"
              className="focus-ring-accent inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-body-sm"
              style={{ color: STAGE.muted }} data-testid="ponder-replay">
              <RotateCcw size={14} /> Replay
            </button>
          ) : (
            <button type="button" onClick={() => setPlaying((p) => !p)}
              aria-label={playing ? "Pause" : "Play"}
              className="focus-ring-accent rounded-md p-1.5"
              style={{ color: playing ? STAGE.muted : "var(--accent)" }}>
              {playing ? <Pause size={16} /> : <Play size={16} />}
            </button>
          )}
        </div>
      </div>

      {/* P3 — the deliberate boundary: admin edit mode, vertical defaults
          with forks. The tenant service carries no publish fns → never
          renders on the tenant read. */}
      {editMode && script?.task_scope === "vertical_default" ? (
        <TaskOfferPublishBar taskId={script.task_id} />
      ) : null}

      {/* P3 — the fires strip: THEIR recent runs (tenant read only) */}
      {script?.fires != null ? (
        <PonderFiresStrip
          fires={script.fires}
          isLive={script.is_live}
          canFollowReviews={script.can_follow_reviews}
        />
      ) : null}

      {/* The live-edit confirm — evidence before a live task's settings change */}
      <LiveEditConfirm
        taskName={script?.task_name ?? "this task"}
        pending={pending}
        onSettle={settle}
      />

      {/* Drift honesty — edit mode only (a content bug for the author, not the viewer) */}
      {editMode && script && script.mirror_drift.length > 0 ? (
        <p className="pb-3 text-center text-caption" style={{ color: "var(--accent)" }}>
          ⚠ This walkthrough's mirror has drifted from its runtime workflow — re-run the mirror pass.
        </p>
      ) : null}
    </div>
  )
}
