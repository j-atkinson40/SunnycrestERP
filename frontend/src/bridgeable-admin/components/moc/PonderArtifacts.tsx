/**
 * Ponder Enrichment — artifact previews on the stage.
 *
 * DOCUMENT: the template's REAL face, lazy-fetched at beat mount (live-
 * resolved server-side — a Studio edit reflects on the next open), scaled
 * into a clipped card via a sandboxed iframe. The name line carries the
 * resolved identity ("using: Statement · Professional v3") + a Studio
 * deep-link.
 *
 * FOCUS: a static miniature SCHEMATIC derived from the task's RESOLVED
 * composition (pin-honoring rows/placements + chrome title) — never a
 * generic picture. Labeled with the lineage ("Cemetery Triage · from
 * decision-triage core v3") + the family icon.
 *
 * A payload the renderer can't place renders NOTHING — a missing preview
 * beats a lying one.
 */
import { useEffect, useState } from "react"
import { ArrowUpRight, FileText } from "lucide-react"

import { adminPath } from "@/bridgeable-admin/lib/admin-routes"
import { FocusFamilyGlyph } from "@/bridgeable-admin/components/moc/MoCTypeCards"
import {
  type PonderArtifact,
} from "@/bridgeable-admin/services/moc-service"
import { usePonderService } from "./ponder-service-context"

const MUTED = "#A79B8E"
const FAINT = "#6E6459"
const CARD = "rgba(255,251,245,0.055)"
const EDGE = "rgba(234,227,218,0.16)"

export function ArtifactPreview({ artifact }: { artifact?: PonderArtifact | null }) {
  if (!artifact) return null
  if (artifact.type === "document") return <DocumentPreview artifact={artifact} />
  if (artifact.type === "focus") return <FocusMiniature artifact={artifact} />
  if (artifact.type === "bank_accounts") return <BankAccountsList artifact={artifact} />
  return null // unknown artifact types render nothing — never a wrong preview
}

function DocumentPreview({ artifact }: { artifact: PonderArtifact }) {
  const svc = usePonderService()
  const [html, setHtml] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    if (!artifact.template_key) return
    svc.getPonderDocumentPreview(artifact.template_key)
      .then((r) => { if (live) setHtml(r.html) })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [artifact.template_key])

  if (failed) return null // degrade typographic — never a lying preview

  return (
    <div className="mt-3" data-testid="ponder-artifact-document">
      <p className="mb-1.5 flex items-center gap-1.5 text-caption" style={{ color: FAINT }}>
        <FileText size={11} />
        using:{" "}
        <span style={{ color: MUTED }}>
          {artifact.label}{artifact.version ? ` v${artifact.version}` : ""}
        </span>
        {svc.studioLinks ? (
          <a
            href={adminPath("visual-editor/documents")}
            className="focus-ring-accent inline-flex items-center gap-0.5 rounded-sm hover:text-white"
            style={{ color: FAINT }}
            title="Open in Studio"
          >
            Studio <ArrowUpRight size={10} />
          </a>
        ) : null}
      </p>
      {/* A document looks like a document: a full portrait page, whole and
          legible-at-a-glance (US-letter aspect, scaled). */}
      <div
        className="overflow-hidden rounded-md shadow-level-2"
        style={{
          border: `1px solid ${EDGE}`, background: "#F5F1EA",
          width: 320, height: 414,
        }}
      >
        {html ? (
          <iframe
            title={`${artifact.label} preview`}
            sandbox=""
            srcDoc={html}
            scrolling="no"
            style={{
              width: 800, height: 1035, border: 0,
              transform: "scale(0.4)", transformOrigin: "top left",
              pointerEvents: "none",
            }}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-caption" style={{ color: "#8a8178" }}>
            rendering…
          </div>
        )}
      </div>
    </div>
  )
}

/** Schematic content lines — generic structure, never fake specifics. */
function ContentLines({ n = 3 }: { n?: number }) {
  return (
    <div className="mt-1.5 space-y-1.5">
      {Array.from({ length: n }, (_, i) => (
        <div
          key={i}
          className="rounded-full"
          style={{
            height: 4,
            width: `${88 - i * 16}%`,
            background: "rgba(234,227,218,0.10)",
          }}
        />
      ))}
    </div>
  )
}

function FocusMiniature({ artifact }: { artifact: PonderArtifact }) {
  const rows = artifact.rows ?? []
  return (
    <div data-testid="ponder-artifact-focus">
      {/* A focus looks like a focus: a landscape screen — chrome bar on top,
          the resolved rows/widgets filling the surface. */}
      <div
        className="flex flex-col overflow-hidden rounded-lg shadow-level-2"
        style={{
          border: `1px solid ${EDGE}`,
          background: "rgba(255,251,245,0.035)",
          width: 560, height: 330,
        }}
      >
        {/* chrome bar */}
        <div
          className="flex items-center gap-2 border-b px-3 py-2"
          style={{ borderColor: EDGE, background: CARD }}
        >
          <span style={{ color: "var(--accent)" }}>
            <FocusFamilyGlyph icon={artifact.icon ?? null} />
          </span>
          <span className="text-body-sm font-medium" style={{ color: MUTED }}>
            {artifact.chrome_title || artifact.display_name}
          </span>
        </div>
        {/* the resolved composition */}
        <div className="flex min-h-0 flex-1 flex-col gap-2 p-3">
          {rows.length === 0 ? (
            <div
              className="flex flex-1 flex-col justify-center rounded-md px-4"
              style={{ background: "rgba(255,251,245,0.03)", border: `1px solid ${EDGE}` }}
            >
              <span className="text-caption" style={{ color: FAINT }}>the core surface</span>
              <ContentLines n={4} />
            </div>
          ) : (
            rows.map((row, i) => (
              <div key={i} className="flex min-h-0 flex-1 gap-2">
                {(row.placements?.length ? row.placements : [{ label: "…" }]).map((p, j) => (
                  <div
                    key={j}
                    className="flex min-w-0 flex-1 flex-col rounded-md px-3 py-2"
                    style={{
                      background: "rgba(255,251,245,0.04)",
                      border: `1px solid ${EDGE}`,
                    }}
                  >
                    <span className="truncate text-caption font-medium" style={{ color: MUTED }}>
                      {p.label ?? "widget"}
                    </span>
                    <ContentLines n={rows.length > 2 ? 2 : 4} />
                  </div>
                ))}
              </div>
            ))
          )}
        </div>
      </div>
      <p className="mt-1.5 text-center text-caption" style={{ color: FAINT }} data-testid="ponder-focus-lineage">
        {artifact.display_name}
        {artifact.core_slug ? (
          <span> · from {artifact.core_slug.replace(/-/g, " ").replace(/ ?core$/, "")} core v{artifact.core_version}</span>
        ) : null}
      </p>
    </div>
  )
}

export function AudienceLine({ audience }: {
  audience?: { text: string; count?: number; count_capped?: boolean } | null
}) {
  if (!audience) return null // not derivable → no line, never a guess
  return (
    <p
      className="mt-2 inline-flex flex-wrap items-center gap-1.5 text-body-sm"
      style={{ color: MUTED }}
      data-testid="ponder-audience"
    >
      <span style={{ color: FAINT }}>→</span>
      {audience.text}
      {typeof audience.count === "number" && audience.count > 0 ? (
        <span
          className="rounded-full px-1.5 py-0.5 text-micro"
          style={{ background: CARD, border: `1px solid ${EDGE}`, color: FAINT }}
        >
          {audience.count_capped ? `${audience.count}+` : audience.count}{" "}
          {audience.count === 1 && !audience.count_capped ? "user" : "users"} today
        </span>
      ) : null}
    </p>
  )
}


/** Plaid B-3 follow-up — the connections beat's account list. Colored
 * pills carry type + linkage so the name and mask read clean. Evening-
 * stage palette (the overlay's committed look). */
function BankAccountsList({ artifact }: { artifact: PonderArtifact }) {
  const conns = (artifact as unknown as {
    connections?: Array<{
      institution: string
      face: string
      accounts: Array<{
        name: string; mask: string | null; subtype: string
        is_credit: boolean; linked: boolean
        balance?: number | null; balance_as_of?: string | null
      }>
    }>
  }).connections
  if (!conns?.length) return null
  return (
    <div className="mx-auto w-full max-w-md space-y-3" data-testid="ponder-bank-accounts">
      {conns.map((c) => (
        <ul key={c.institution} className="space-y-1.5">
          {c.accounts.map((a) => (
            <li
              key={`${a.name}-${a.mask}`}
              className="flex items-center gap-2 rounded-md px-3 py-1.5 text-left"
              style={{ background: "rgba(255,251,245,0.055)" }}
            >
              <span className="text-sm" style={{ color: "#EAE3DA" }}>
                {a.name}
              </span>
              {a.mask ? (
                <span className="font-plex-mono text-xs" style={{ color: "#A79B8E" }}>
                  ····{a.mask}
                </span>
              ) : null}
              {a.balance !== null && a.balance !== undefined ? (
                <span
                  className="font-plex-mono text-xs"
                  style={{ color: a.is_credit ? "#E0B380" : "#EAE3DA" }}
                  title={a.balance_as_of ? `as of ${new Date(a.balance_as_of).toLocaleString()}` : undefined}
                >
                  {a.is_credit ? "owes −" : ""}${Math.abs(a.balance).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>
              ) : null}
              <span className="ml-auto flex flex-none items-center gap-1.5">
                <span
                  className="rounded-full px-2 py-0.5 text-[10px] font-medium"
                  style={a.is_credit
                    ? { background: "rgba(224,159,98,0.16)", color: "#E0B380" }
                    : { background: "rgba(234,227,218,0.10)", color: "#A79B8E" }}
                >
                  {a.subtype}
                </span>
                {a.linked ? (
                  <span
                    className="rounded-full px-2 py-0.5 text-[10px] font-medium"
                    style={{ background: "rgba(156,86,64,0.28)", color: "#E8A18C" }}
                  >
                    feeds reconciliation
                  </span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      ))}
    </div>
  )
}
