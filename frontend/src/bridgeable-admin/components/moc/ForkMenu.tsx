/**
 * Fork menu (Focus Variations V-1) — the choice a DEFAULT's pill offers.
 *
 * Clicking a Tier 1 core entry on the platform map's Focuses card opens
 * this menu instead of navigating: "Edit the default" (with the BLAST
 * RADIUS legible at the moment of choice — inherited by N templates across
 * M verticals, from the lineage-aware usage endpoint) vs "Create a
 * variation" (opens the guided flow). The consequence is visible BEFORE
 * the click commits to it.
 *
 * Usage is fetched lazily on first open — the platform map doesn't pay
 * N usage calls to render N pills.
 */

import * as React from "react"
import { useNavigate } from "react-router-dom"
import { GitBranch, Pencil, UploadCloud } from "lucide-react"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  focusCoresService,
  type CoreUsage,
} from "@/bridgeable-admin/services/focus-cores-service"
import type { MoCTypeCardEntry } from "@/bridgeable-admin/components/moc/MoCTypeCards"

export interface ForkMenuProps {
  entry: MoCTypeCardEntry
  onCreateVariation: (entry: MoCTypeCardEntry) => void
  /** V-2: opens the publish dialog (the explicit release boundary). */
  onPublish?: (entry: MoCTypeCardEntry) => void
}

function blastRadius(usage: CoreUsage | null, failed: boolean): string {
  if (failed) return "Edits reach every inheriting template."
  if (usage === null) return "Counting inheritors…"
  const n = usage.templates_count
  if (n === 0) return "No templates inherit this yet — edits are safe."
  const verticals = new Set(
    usage.templates.map((t) => t.vertical ?? "platform"),
  )
  const m = verticals.size
  return `Inherited by ${n} template${n === 1 ? "" : "s"} across ${m} vertical${
    m === 1 ? "" : "s"
  } — edits reach them all.`
}

export function ForkMenu({ entry, onCreateVariation, onPublish }: ForkMenuProps) {
  const navigate = useNavigate()
  const [usage, setUsage] = React.useState<CoreUsage | null>(null)
  const [failed, setFailed] = React.useState(false)
  const fetchedRef = React.useRef(false)

  function handleOpenChange(open: boolean) {
    if (!open || fetchedRef.current || !entry.artifact_id) return
    fetchedRef.current = true
    focusCoresService
      .usage(entry.artifact_id)
      .then(setUsage)
      .catch(() => setFailed(true)) // menu still works; radius line degrades
  }

  return (
    <DropdownMenu onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger
        render={
          <button
            type="button"
            className="focus-ring-accent flex items-center gap-1.5 rounded-sm py-0.5 text-body-sm text-content-base hover:text-accent"
            data-testid={`fork-menu-trigger-${entry.row_id}`}
          >
            {entry.label}
          </button>
        }
      />
      <DropdownMenuContent align="start" className="w-80">
        <DropdownMenuItem
          disabled={entry.href === null}
          onClick={() => {
            if (entry.href) navigate(entry.href)
          }}
          data-testid={`fork-menu-edit-${entry.row_id}`}
        >
          <div className="flex items-start gap-2">
            <Pencil size={14} className="mt-0.5 shrink-0 text-content-muted" />
            <span>
              <span className="block font-medium">Edit the default</span>
              <span
                className="block text-caption text-content-muted"
                data-testid={`fork-menu-radius-${entry.row_id}`}
              >
                {blastRadius(usage, failed)}
              </span>
            </span>
          </div>
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => onCreateVariation(entry)}
          data-testid={`fork-menu-variation-${entry.row_id}`}
        >
          <div className="flex items-start gap-2">
            <GitBranch size={14} className="mt-0.5 shrink-0 text-content-muted" />
            <span>
              <span className="block font-medium">Create a variation</span>
              <span className="block text-caption text-content-muted">
                A new template on this shape, scoped to the verticals you
                choose.
              </span>
            </span>
          </div>
        </DropdownMenuItem>
        {onPublish ? (
          <DropdownMenuItem
            onClick={() => onPublish(entry)}
            data-testid={`fork-menu-publish-${entry.row_id}`}
          >
            <div className="flex items-start gap-2">
              <UploadCloud size={14} className="mt-0.5 shrink-0 text-content-muted" />
              <span>
                <span className="block font-medium">Publish update…</span>
                <span className="block text-caption text-content-muted">
                  Release your edits — inheriting variations get an offer
                  with the patch notes.
                </span>
              </span>
            </div>
          </DropdownMenuItem>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
