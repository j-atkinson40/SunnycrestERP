/**
 * The map completes itself (2026-07-18) — the Platform area, the
 * Onboarding journey, the showroom, and per-area tips.
 *
 * THE JOURNEY'S MOOD IS A DELIVERABLE: the whole path visible (done
 * glowing quietly, current gently marked, ahead open — never locked),
 * free movement, calm prose ("3 of 7 walked" — no screaming bars).
 * SLOW IS STILL A FEATURE.
 */
import { useCallback, useEffect, useState } from "react"
import {
  Check, ChevronDown, Lightbulb, LayoutPanelTop, Plug2, Sparkles, Terminal,
} from "lucide-react"

import apiClient from "@/lib/api-client"
import {
  HoldRing, useHoldToPonder,
} from "@/bridgeable-admin/components/moc/MoCTaskTable"

/** The shared ponderable card — the map's one gesture, reused. */
function PonderCard({
  overlayId, title, body, footer, onPonder, accent = false, testid,
}: {
  overlayId: string
  title: React.ReactNode
  body?: string
  footer?: React.ReactNode
  onPonder: (id: string) => void
  accent?: boolean
  testid: string
}) {
  const complete = useCallback(() => onPonder(overlayId), [onPonder, overlayId])
  const { hovered, holding, reduced, hoverProps } = useHoldToPonder(true, complete)
  return (
    <div
      {...hoverProps}
      role="button"
      tabIndex={0}
      onClick={complete}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); complete() }
      }}
      className={
        "group flex min-h-[8rem] cursor-pointer flex-col rounded-md bg-surface-elevated p-4 shadow-level-1 transition-shadow duration-quick ease-settle hover:shadow-level-2 focus-ring-accent" +
        (accent ? " ring-1 ring-accent/40" : "")
      }
      data-testid={testid}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="flex items-center gap-2 text-body font-medium leading-snug text-content-strong">
          {title}
        </p>
        {hovered ? (
          <span className="flex flex-none items-center gap-1.5 whitespace-nowrap text-caption text-content-muted">
            <HoldRing holding={holding} reduced={reduced} />
            Hold <kbd className="rounded-sm border border-border-base px-1 font-plex-mono text-micro">P</kbd>
          </span>
        ) : null}
      </div>
      {body ? (
        <p className="mt-1.5 line-clamp-2 text-body-sm leading-relaxed text-content-muted">
          {body}
        </p>
      ) : null}
      {footer ? <div className="mt-auto flex items-center gap-2 pt-3">{footer}</div> : null}
    </div>
  )
}

// ── The Platform area — three primitive cards ───────────────────────────

const PLATFORM_CARDS = [
  { key: "pulse", title: "Pulse", icon: Sparkles,
    body: "The surfaces that come to you — briefing, boards, badges." },
  { key: "command-bar", title: "The Command Bar", icon: Terminal,
    body: "One keystroke, then say what you want. Navigation is the backup." },
  { key: "focuses", title: "Focuses", icon: LayoutPanelTop,
    body: "Rooms built for one decision — opened, decided, closed." },
]

export function PlatformArea({ onPonder }: { onPonder: (id: string) => void }) {
  return (
    <section data-testid="platform-area">
      <h2 className="text-caption font-medium uppercase tracking-wide text-content-subtle">
        The primitives
      </h2>
      <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {PLATFORM_CARDS.map((c) => (
          <PonderCard
            key={c.key}
            overlayId={`platform:${c.key}`}
            title={<><c.icon size={14} className="flex-none text-accent" /> {c.title}</>}
            body={c.body}
            onPonder={onPonder}
            testid={`platform-card-${c.key}`}
          />
        ))}
      </div>
    </section>
  )
}

// ── The journey (Onboarding & Setup's body) ─────────────────────────────

interface JourneyStep {
  key: string
  title: string
  state: "done" | "current" | "ahead"
  completion: "reality" | "engagement"
  ponder_key: string
}

export function JourneyArea({ onPonder, refreshToken }: {
  onPonder: (id: string) => void
  refreshToken?: unknown
}) {
  const [journey, setJourney] = useState<{
    steps: JourneyStep[]; prose: string
  } | null>(null)

  useEffect(() => {
    apiClient.get("/moc/journey")
      .then((r) => setJourney(r.data))
      .catch(() => setJourney(null))
  }, [refreshToken])

  if (journey === null) return null

  return (
    <section data-testid="journey-area">
      <div className="flex items-baseline gap-3">
        <h2 className="text-caption font-medium uppercase tracking-wide text-content-subtle">
          The path
        </h2>
        <span className="text-body-sm text-content-muted" data-testid="journey-prose">
          {journey.prose}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {journey.steps.map((s) => (
          <PonderCard
            key={s.key}
            overlayId={s.ponder_key}
            accent={s.state === "current"}
            title={<>
              {s.state === "done" ? (
                <Check size={14} className="flex-none text-status-success" />
              ) : null}
              {s.title}
            </>}
            body={
              s.state === "done"
                ? (s.completion === "reality" ? "Done — it exists." : "Walked.")
                : s.state === "current" ? "The gentle next step." : undefined
            }
            footer={
              <span
                className={
                  "rounded-full px-2 py-0.5 text-micro font-medium " +
                  (s.state === "done"
                    ? "bg-status-success-muted text-status-success"
                    : s.state === "current"
                      ? "bg-accent-subtle text-accent"
                      : "bg-surface-sunken text-content-subtle")
                }
                data-testid={`journey-state-${s.key}`}
              >
                {s.state === "done" ? "done" : s.state === "current" ? "up next" : "open"}
              </span>
            }
            onPonder={onPonder}
            testid={`journey-step-${s.key}`}
          />
        ))}
      </div>
    </section>
  )
}

// ── The showroom (Additional features) ──────────────────────────────────

interface ShowroomCard {
  key: string
  title: string
  description: string
  toggleable: boolean
  ponder_key: string
}

export function ShowroomArea({ onPonder, isAdmin }: {
  onPonder: (id: string) => void
  isAdmin: boolean
}) {
  const [cards, setCards] = useState<ShowroomCard[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)

  const load = useCallback(() => {
    apiClient.get("/moc/showroom")
      .then((r) => setCards(r.data.cards))
      .catch(() => setCards([]))
  }, [])
  useEffect(() => { load() }, [load])

  const enable = (key: string) => {
    setBusy(key)
    apiClient.post(`/moc/showroom/${key}/enable`)
      .then(() => {
        setNote("Enabled — billing per your agreement. Its surfaces are lighting up.")
        load()
      })
      .catch(() => setNote("Couldn't enable — try again."))
      .finally(() => setBusy(null))
  }
  const interest = (key: string) => {
    setBusy(key)
    apiClient.post(`/moc/showroom/${key}/interest`)
      .then(() => setNote("Interest noted — it counts toward when it gets built."))
      .catch(() => {})
      .finally(() => setBusy(null))
  }

  return (
    <section data-testid="showroom-area">
      <h2 className="text-caption font-medium uppercase tracking-wide text-content-subtle">
        Not turned on yet
      </h2>
      {note ? (
        <p className="mt-2 text-body-sm text-content-muted" data-testid="showroom-note">
          {note}
        </p>
      ) : null}
      <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((c) => (
          <PonderCard
            key={c.key}
            overlayId={c.ponder_key}
            title={<><Plug2 size={14} className="flex-none text-accent" /> {c.title}</>}
            body={c.description}
            footer={
              isAdmin ? (
                c.toggleable ? (
                  <button
                    type="button"
                    disabled={busy === c.key}
                    onClick={(e) => { e.stopPropagation(); enable(c.key) }}
                    className="focus-ring-accent rounded-md bg-accent px-2.5 py-1 text-caption font-medium text-content-on-accent disabled:opacity-60"
                    data-testid={`showroom-enable-${c.key}`}
                  >
                    Turn on · billing per your agreement
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={busy === c.key}
                    onClick={(e) => { e.stopPropagation(); interest(c.key) }}
                    className="focus-ring-accent rounded-md border border-border-base px-2.5 py-1 text-caption text-content-muted hover:text-content-base disabled:opacity-60"
                    data-testid={`showroom-interest-${c.key}`}
                  >
                    I'm interested
                  </button>
                )
              ) : (
                <span className="text-caption text-content-subtle">
                  An administrator can turn this on.
                </span>
              )
            }
            onPonder={onPonder}
            testid={`showroom-card-${c.key}`}
          />
        ))}
        {cards.length === 0 ? (
          <p className="text-body-sm text-content-subtle">
            Everything available is already on.
          </p>
        ) : null}
      </div>
    </section>
  )
}

// ── Tips (per business area; collapsed — the engine-room pattern) ───────

export function TipsSection({ area, onPonder }: {
  area: string
  onPonder: (id: string) => void
}) {
  const [tips, setTips] = useState<Array<{ key: string; title: string; ponder_key: string }>>([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    apiClient.get(`/moc/tips/${encodeURIComponent(area)}`)
      .then((r) => setTips(r.data))
      .catch(() => setTips([]))
  }, [area])

  if (tips.length === 0) return null // EMPTY-HONEST

  return (
    <section data-testid="map-tips">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="focus-ring-accent -ml-1 flex items-center gap-1.5 rounded-md px-1 py-0.5"
        data-testid="map-tips-toggle"
      >
        <ChevronDown
          size={14}
          className={
            "text-content-subtle transition-transform duration-quick ease-settle " +
            (open ? "" : "-rotate-90")
          }
        />
        <h2 className="flex items-center gap-1.5 text-caption font-medium uppercase tracking-wide text-content-subtle">
          <Lightbulb size={12} /> Tips & tricks
        </h2>
        <span className="text-caption text-content-subtle">{tips.length}</span>
      </button>
      {open ? (
        <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
          data-testid="map-tips-body">
          {tips.map((t) => (
            <PonderCard
              key={t.key}
              overlayId={t.ponder_key}
              title={t.title}
              onPonder={onPonder}
              testid={`map-tip-${t.key}`}
            />
          ))}
        </div>
      ) : null}
    </section>
  )
}
