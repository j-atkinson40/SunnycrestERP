/**
 * The Ponder motif library (Ponder Polish Set 3) — small animated SVG scenes
 * keyed to BEAT SEMANTICS and parameterized by derived config. Never
 * hand-illustrated per workflow: the server's motif grammar chooses the
 * scene; entity labels arrive from step config. A beat without a motif gets
 * the typographic treatment — a missing visual beats a lying one.
 *
 * DL-NATIVE: the evening stage's palette, terracotta accents, entrances on
 * the settle curve, departures on the gentle curve. Scenes mount per-beat
 * (the overlay renders only the ACTIVE beat, so non-active scenes are
 * unmounted — the 13-beat stress case never animates 13 scenes at once).
 * Reduced motion: scenes render their FINAL frame, static.
 */
import type { PonderMotif } from "@/bridgeable-admin/services/moc-service"

const MUTED = "#A79B8E"
const FAINT = "#6E6459"
const CARD = "rgba(255,251,245,0.07)"
const EDGE = "rgba(234,227,218,0.22)"
const ACCENT = "var(--accent)"

const plural = (s: string) => (s.endsWith("s") ? s : `${s}s`)

/** Shared keyframes — injected once per mounted scene (cheap, idempotent). */
function MotifStyle() {
  return (
    <style>{`
      @keyframes motif-arrive { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
      @keyframes motif-slide-in { from { opacity: 0; transform: translateX(-16px); } to { opacity: 1; transform: none; } }
      @keyframes motif-depart { 0% { opacity: 1; transform: none; } 100% { opacity: 0.25; transform: translateX(52px) scale(0.82); } }
      @keyframes motif-draw { from { stroke-dashoffset: var(--len, 120); } to { stroke-dashoffset: 0; } }
      @keyframes motif-sweep { from { transform: rotate(-240deg); } to { transform: rotate(0deg); } }
      @keyframes motif-pulse { 0% { opacity: 0.9; transform: scale(0.6); } 70% { opacity: 0; transform: scale(1.5); } 100% { opacity: 0; transform: scale(1.5); } }
      @keyframes motif-drop { 0% { opacity: 0; transform: translateY(-26px) rotate(-4deg); } 60% { opacity: 1; transform: translateY(2px) rotate(1deg); } 100% { opacity: 1; transform: none; } }
      @keyframes motif-glow { 0%, 60% { opacity: 0.25; } 100% { opacity: 1; } }
      @keyframes motif-ring { from { opacity: 0; r: 3; } to { opacity: 0.55; r: 14; } }
      .motif-anim [data-anim] { animation-fill-mode: both; animation-timing-function: var(--ease-settle, cubic-bezier(0.2,0,0.1,1)); }
      .motif-static [data-anim] { animation: none !important; }
    `}</style>
  )
}

function Doc({ x, y, w = 34, h = 42, label, delay, accent = false }: {
  x: number; y: number; w?: number; h?: number; label?: string; delay?: number; accent?: boolean
}) {
  return (
    <g data-anim style={{ animationName: "motif-arrive", animationDuration: "500ms", animationDelay: `${delay ?? 0}ms` }}>
      <rect x={x} y={y} width={w} height={h} rx="4"
        fill={CARD} stroke={accent ? ACCENT : EDGE} strokeWidth="1.2" />
      <line x1={x + 7} y1={y + 11} x2={x + w - 7} y2={y + 11} stroke={accent ? ACCENT : FAINT} strokeWidth="1.6" opacity="0.8" />
      <line x1={x + 7} y1={y + 19} x2={x + w - 10} y2={y + 19} stroke={FAINT} strokeWidth="1.2" opacity="0.6" />
      <line x1={x + 7} y1={y + 26} x2={x + w - 13} y2={y + 26} stroke={FAINT} strokeWidth="1.2" opacity="0.5" />
      {label ? (
        <text x={x + w / 2} y={y + h + 15} textAnchor="middle" fontSize="10"
          fill={MUTED} style={{ fontFamily: "var(--font-plex-sans)", textTransform: "capitalize" }}>
          {label}
        </text>
      ) : null}
    </g>
  )
}

function Tray({ x, y, label, w = 76 }: { x: number; y: number; label: string; w?: number }) {
  return (
    <g>
      <path d={`M ${x} ${y} v 20 a 5 5 0 0 0 5 5 h ${w - 10} a 5 5 0 0 0 5 -5 v -20`}
        fill={CARD} stroke={EDGE} strokeWidth="1.4" />
      <text x={x + w / 2} y={y + 42} textAnchor="middle" fontSize="10"
        fill={MUTED} style={{ fontFamily: "var(--font-plex-sans)" }}>
        {label}
      </text>
    </g>
  )
}

// ── The scenes ───────────────────────────────────────────────────────────────

function ClockScene() {
  return (
    <svg width="150" height="96" viewBox="0 0 150 96" aria-hidden>
      <circle cx="75" cy="46" r="30" fill={CARD} stroke={EDGE} strokeWidth="1.4" />
      {[0, 90, 180, 270].map((a) => (
        <line key={a} x1="75" y1="19" x2="75" y2="23" stroke={FAINT} strokeWidth="1.5"
          transform={`rotate(${a} 75 46)`} />
      ))}
      <g data-anim style={{ animationName: "motif-sweep", animationDuration: "1400ms", transformOrigin: "75px 46px" }}>
        <line x1="75" y1="46" x2="75" y2="26" stroke={ACCENT} strokeWidth="2.2" strokeLinecap="round" />
      </g>
      <line x1="75" y1="46" x2="88" y2="52" stroke={MUTED} strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="75" cy="46" r="2.4" fill={ACCENT} />
      <circle data-anim cx="75" cy="46" fill="none" stroke={ACCENT} strokeWidth="1.5"
        style={{ animationName: "motif-ring", animationDuration: "900ms", animationDelay: "1350ms" }} />
    </svg>
  )
}

function SignalScene() {
  return (
    <svg width="150" height="96" viewBox="0 0 150 96" aria-hidden>
      <circle cx="75" cy="48" r="5" fill={ACCENT} />
      {[0, 350, 700].map((d, i) => (
        <circle key={d} data-anim cx="75" cy="48" fill="none" stroke={ACCENT} strokeWidth={1.8 - i * 0.4}
          style={{ animationName: "motif-ring", animationDuration: "1200ms", animationDelay: `${d}ms`, animationIterationCount: "2" }} />
      ))}
    </svg>
  )
}

function CreateScene({ entity }: { entity?: string | null }) {
  const label = entity ? plural(entity) : "records"
  return (
    <svg width="200" height="110" viewBox="0 0 200 110" aria-hidden>
      <Doc x={58} y={16} delay={0} />
      <Doc x={83} y={12} delay={220} />
      <Doc x={108} y={16} delay={440} accent label={label} />
    </svg>
  )
}

function TransformScene({ from, to }: { from?: string | null; to?: string | null }) {
  return (
    <svg width="240" height="110" viewBox="0 0 240 110" aria-hidden>
      <Doc x={26} y={16} label={from ? plural(from) : undefined} delay={0} />
      <g data-anim style={{ animationName: "motif-arrive", animationDuration: "400ms", animationDelay: "350ms" }}>
        <path d="M 74 37 H 148" fill="none" stroke={MUTED} strokeWidth="1.6"
          strokeDasharray="80" data-anim
          style={{ animationName: "motif-draw", animationDuration: "600ms", animationDelay: "380ms", ["--len" as string]: "80" }} />
        <path d="M 142 31 L 152 37 L 142 43" fill="none" stroke={MUTED} strokeWidth="1.6"
          strokeLinecap="round" strokeLinejoin="round" data-anim
          style={{ animationName: "motif-arrive", animationDuration: "300ms", animationDelay: "820ms" }} />
      </g>
      <Doc x={166} y={16} label={to ? plural(to) : undefined} delay={950} accent />
    </svg>
  )
}

function SendScene({ entity }: { entity?: string | null }) {
  return (
    <svg width="220" height="110" viewBox="0 0 220 110" aria-hidden>
      <g data-anim style={{
        animationName: "motif-depart", animationDuration: "1100ms", animationDelay: "500ms",
        animationTimingFunction: "var(--ease-gentle, cubic-bezier(0.4,0,0.4,1))",
      }}>
        <Doc x={42} y={16} label={entity ? plural(entity) : undefined} delay={0} />
      </g>
      <circle cx="168" cy="37" r="14" fill={CARD} stroke={EDGE} strokeWidth="1.4" />
      <path d="M 161 37 l 5 5 l 9 -10" fill="none" stroke={ACCENT} strokeWidth="1.8"
        strokeLinecap="round" strokeLinejoin="round" data-anim
        style={{ animationName: "motif-glow", animationDuration: "1700ms" }} />
    </svg>
  )
}

function BranchScene() {
  return (
    <svg width="200" height="110" viewBox="0 0 200 110" aria-hidden>
      <path d="M 30 55 H 92" fill="none" stroke={MUTED} strokeWidth="1.8"
        strokeDasharray="62" data-anim
        style={{ animationName: "motif-draw", animationDuration: "450ms", ["--len" as string]: "62" }} />
      <path d="M 92 55 C 116 55 120 30 150 28" fill="none" stroke={ACCENT} strokeWidth="2"
        strokeDasharray="70" data-anim
        style={{ animationName: "motif-draw", animationDuration: "600ms", animationDelay: "430ms", ["--len" as string]: "70" }} />
      <path d="M 92 55 C 116 55 120 80 150 82" fill="none" stroke={FAINT} strokeWidth="1.5"
        strokeDasharray="70" data-anim
        style={{ animationName: "motif-draw", animationDuration: "600ms", animationDelay: "430ms", ["--len" as string]: "70" }} />
      <circle cx="155" cy="28" r="4" fill={ACCENT} data-anim
        style={{ animationName: "motif-arrive", animationDuration: "300ms", animationDelay: "1000ms" }} />
      <circle cx="155" cy="82" r="3.4" fill="none" stroke={FAINT} strokeWidth="1.4" />
    </svg>
  )
}

function QueueScene({ label }: { label?: string | null }) {
  return (
    <svg width="220" height="120" viewBox="0 0 220 120" aria-hidden>
      <g data-anim style={{ animationName: "motif-drop", animationDuration: "800ms", animationDelay: "250ms" }}>
        <rect x="88" y="18" width="44" height="30" rx="4" fill={CARD} stroke={ACCENT} strokeWidth="1.3" />
        <line x1="96" y1="29" x2="124" y2="29" stroke={ACCENT} strokeWidth="1.5" opacity="0.8" />
        <line x1="96" y1="37" x2="118" y2="37" stroke={FAINT} strokeWidth="1.2" opacity="0.6" />
      </g>
      <Tray x={72} y={56} label={label ?? "review queue"} />
    </svg>
  )
}

function FailureScene({ label }: { label?: string | null }) {
  return (
    <svg width="260" height="120" viewBox="0 0 260 120" aria-hidden>
      <g data-anim style={{ animationName: "motif-drop", animationDuration: "800ms", animationDelay: "250ms" }}>
        <rect x="66" y="16" width="44" height="30" rx="4" fill={CARD} stroke={ACCENT} strokeWidth="1.3" />
        <path d="M 82 24 l 12 12 M 94 24 l -12 12" stroke={ACCENT} strokeWidth="1.6" strokeLinecap="round" />
      </g>
      <Tray x={50} y={56} label={label ?? "Decision Triage"} />
      {/* the morning-briefing echo — the H1 story, drawn */}
      <g data-anim style={{ animationName: "motif-glow", animationDuration: "2100ms" }}>
        <circle cx="196" cy="42" r="11" fill="none" stroke={MUTED} strokeWidth="1.4" />
        {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
          <line key={a} x1="196" y1="26" x2="196" y2="29" stroke={MUTED} strokeWidth="1.2"
            transform={`rotate(${a} 196 42)`} />
        ))}
        <text x="196" y="72" textAnchor="middle" fontSize="9" fill={FAINT}
          style={{ fontFamily: "var(--font-plex-sans)" }}>
          morning briefing
        </text>
      </g>
    </svg>
  )
}

// ── The dispatcher ───────────────────────────────────────────────────────────

export function MotifScene({ motif, reduced }: { motif?: PonderMotif | null; reduced: boolean }) {
  if (!motif) return null
  let scene: React.ReactNode = null
  switch (motif.kind) {
    case "clock": scene = <ClockScene />; break
    case "signal": scene = <SignalScene />; break
    case "create": scene = <CreateScene entity={motif.entity} />; break
    case "transform": scene = <TransformScene from={motif.from} to={motif.to} />; break
    case "send": scene = <SendScene entity={motif.entity} />; break
    case "branch": scene = <BranchScene />; break
    case "queue": scene = <QueueScene label={motif.label} />; break
    case "failure": scene = <FailureScene label={motif.label} />; break
    default: return null // an unknown kind renders NOTHING — never a wrong scene
  }
  return (
    <div
      className={reduced ? "motif-static" : "motif-anim"}
      data-testid={`ponder-motif-${motif.kind}`}
    >
      <MotifStyle />
      {scene}
    </div>
  )
}
