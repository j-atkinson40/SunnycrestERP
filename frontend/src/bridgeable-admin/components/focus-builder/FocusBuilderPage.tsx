/**
 * FocusBuilderPage — top-level Focus Builder surface (sub-arc F-1).
 *
 * Mounts at /studio/builder/focuses (path registered inside
 * StudioShell). Three-region layout:
 *   - LEFT  (280px): FocusBuilderTree (vertical-grouped tree).
 *   - CENTER (flex-1): FocusBuilderCanvasPlaceholder.
 *   - RIGHT (320px): FocusBuilderRightRailPlaceholder.
 *
 * URL contract per investigation Q-40 LOCKED (b):
 *   `?subject=core:<id>` OR `?subject=template:<id>`
 *   `?return_to=` preserved for the back-link contract.
 *
 * F-1 is READ-ONLY. The FocusBuilderSelectionProvider is mounted so
 * F-2's editing wires drop in without restructuring; selection stays
 * at `{ kind: 'none' }` throughout F-1.
 */
import * as React from "react"
import { useLocation, useNavigate, useSearchParams } from "react-router-dom"

import { parseStudioPath } from "@/bridgeable-admin/lib/studio-routes"

import FocusBuilderTree, {
  type FocusBuilderSubject,
} from "./FocusBuilderTree"
import FocusBuilderCanvasPlaceholder from "./FocusBuilderCanvasPlaceholder"
import FocusBuilderRightRailPlaceholder from "./FocusBuilderRightRailPlaceholder"
import { FocusBuilderSelectionProvider } from "./FocusBuilderSelectionContext"


function parseSubjectParam(raw: string | null): FocusBuilderSubject | null {
  if (!raw) return null
  const colon = raw.indexOf(":")
  if (colon <= 0) return null
  const kind = raw.slice(0, colon)
  const id = raw.slice(colon + 1)
  if (!id) return null
  if (kind === "core") return { kind: "core", id }
  if (kind === "template") return { kind: "template", id }
  return null
}


function subjectToParam(subject: FocusBuilderSubject): string {
  return `${subject.kind}:${subject.id}`
}


export function FocusBuilderPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const location = useLocation()

  const subject = React.useMemo(
    () => parseSubjectParam(searchParams.get("subject")),
    [searchParams],
  )

  const studioActiveVertical = React.useMemo(() => {
    // The /studio/builder/focuses route doesn't carry a vertical
    // path segment by design — parseStudioPath returns vertical=null.
    // FocusBuilderTree falls back to readLastVertical() in that case.
    return parseStudioPath(
      location.pathname.replace(/^\/bridgeable-admin/, ""),
    ).vertical
  }, [location.pathname])

  const handleSelectSubject = React.useCallback(
    (next: FocusBuilderSubject) => {
      const params = new URLSearchParams(searchParams)
      params.set("subject", subjectToParam(next))
      // Preserve ?return_to= if present.
      setSearchParams(params, { replace: false })
    },
    [searchParams, setSearchParams],
  )

  // Suppress unused-warning for navigate during F-1 (reserved for
  // F-5 breadcrumb back-link wiring).
  void navigate

  return (
    <FocusBuilderSelectionProvider>
      <div
        className="flex h-[calc(100vh-3rem)] min-h-[600px] flex-col bg-surface-base"
        data-testid="focus-builder-page"
      >
        <header
          className="flex h-10 shrink-0 items-center border-b border-[color:var(--border-subtle)] bg-surface-sunken px-4 text-[12px] text-content-muted"
          data-testid="focus-builder-topbar"
        >
          <span className="font-plex-mono uppercase tracking-wider">
            Bridgeable Studio · Focus Builder
          </span>
        </header>

        <div className="flex min-h-0 flex-1">
          <aside
            className="flex w-[280px] shrink-0 flex-col overflow-y-auto border-r border-[color:var(--border-subtle)] bg-surface-sunken py-2"
            data-testid="focus-builder-tree-region"
          >
            <FocusBuilderTree
              selectedSubject={subject}
              onSelectSubject={handleSelectSubject}
              studioActiveVertical={studioActiveVertical}
            />
          </aside>

          <section
            className="min-w-0 flex-1 overflow-y-auto"
            data-testid="focus-builder-canvas-region"
          >
            <FocusBuilderCanvasPlaceholder subject={subject} />
          </section>

          <aside
            className="w-[320px] shrink-0 overflow-y-auto border-l border-[color:var(--border-subtle)] bg-surface-sunken"
            data-testid="focus-builder-right-rail-region"
          >
            <FocusBuilderRightRailPlaceholder />
          </aside>
        </div>
      </div>
    </FocusBuilderSelectionProvider>
  )
}

export default FocusBuilderPage
