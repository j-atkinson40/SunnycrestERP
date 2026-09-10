/**
 * ModeDispatcher — resolves a focus id to its registered core mode
 * and renders the matching core stub.
 *
 * Phase A Session 2. Lookup-map pattern (not switch) so TypeScript's
 * exhaustive-record check catches a forgotten entry when new modes
 * land. Open-closed: adding a new mode is one type-union edit + one
 * map entry + a new core component; no existing mode's code changes.
 *
 * Unknown focus id → renders an error state so the app doesn't crash
 * on a stale URL / typo / unregistered id. The error state surfaces
 * the id + dismiss hint; users recover by pressing Esc or clicking
 * outside.
 */

import { useFocusOptional } from "@/contexts/focus-context"
import { getFocusConfig, type CoreMode } from "@/contexts/focus-registry"

import type { CoreProps } from "./cores/_shared"
import { useFocusReadOnly } from "./useFocusReadOnly"
import { EscToDismissHint, ReadOnlyNotice } from "./cores/_shared"
import { KanbanCore } from "./cores/KanbanCore"
import { SingleRecordCore } from "./cores/SingleRecordCore"
import { EditCanvasCore } from "./cores/EditCanvasCore"
import { TriageQueueCore } from "./cores/TriageQueueCore"
import { MatrixCore } from "./cores/MatrixCore"


/**
 * Mode → renderer lookup.
 *
 * TypeScript's `Record<CoreMode, ...>` type enforces exhaustiveness:
 * adding a new mode to the `CoreMode` union without adding a map
 * entry is a compile error, not a runtime-hours-later "why is this
 * focus blank" bug. Keep this map sorted to match the order in the
 * `CoreMode` union for visual diff review.
 */
const MODE_RENDERERS: Record<CoreMode, React.ComponentType<CoreProps>> = {
  kanban: KanbanCore,
  singleRecord: SingleRecordCore,
  editCanvas: EditCanvasCore,
  triageQueue: TriageQueueCore,
  matrix: MatrixCore,
}


export function ModeDispatcher({ focusId }: { focusId: string }) {
  const config = getFocusConfig(focusId)
  // ⚠️ COMPUTED ONCE, HERE. Every core receives the same answer rather than
  // asking for itself — a core that forgot to ask looks exactly like a core
  // whose user happens to hold the permission.
  const readOnly = useFocusReadOnly(config)
  // ⚠️ NULL-SAFE, for the reason §1 learned the hard way: a hook that throws
  // outside its provider makes this component unrenderable in every context
  // that lacks one, and several legitimately do. Unscoped is a real state.
  const focus = useFocusOptional()
  const scope = focus?.currentFocus?.params ?? {}
  if (!config) {
    return <UnknownFocusError focusId={focusId} />
  }
  // Phase B Session 4: specialized renderer takes precedence over the
  // mode-generic stub when a Focus registers a `coreComponent`. Falls
  // back to the mode-generic MODE_RENDERERS entry otherwise. Open-
  // closed: adding a new specialized core doesn't touch this dispatch.
  const Renderer = config.coreComponent ?? MODE_RENDERERS[config.mode]
  // ⚠️ THE NOTICE IS THE LAYER'S, NOT EACH CORE'S. Stated once here so a new
  // core cannot ship read-only without saying so — and so the wording cannot
  // drift between cores, which would make the same condition read as two
  // different states.
  return (
    <div className="flex h-full flex-col">
      {readOnly ? <ReadOnlyNotice permission={config.editPermission} /> : null}
      <div className="min-h-0 flex-1">
        <Renderer
          focusId={focusId}
          config={config}
          readOnly={readOnly}
          scope={scope}
        />
      </div>
    </div>
  )
}


function UnknownFocusError({ focusId }: { focusId: string }) {
  return (
    <div
      data-slot="focus-unknown-error"
      className="flex h-full flex-col gap-4"
    >
      <header className="flex flex-col gap-1">
        <p className="text-micro uppercase tracking-wider text-status-error">
          Unknown focus
        </p>
        <h2 className="text-h2 font-display text-content-strong">
          No Focus registered at this id
        </h2>
      </header>
      <div className="flex-1 rounded-md border border-status-error/30 bg-status-error-muted/40 p-6">
        <p className="text-body-sm text-content-base">
          The id{" "}
          <code className="rounded bg-surface-elevated px-1.5 py-0.5 font-mono text-micro">
            {focusId}
          </code>{" "}
          was not found in the Focus registry. This usually means a
          stale URL, a typo, or a Focus that was retired without its
          link being updated.
        </p>
      </div>
      <EscToDismissHint />
    </div>
  )
}
