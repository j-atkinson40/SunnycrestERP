/**
 * LayerInspectorSection — sub-arc FF-5.
 *
 * Inspector-side surface for the four z-order actions
 * (front / forward / backward / back). Mounts inside
 * `WidgetInspectorSection` as a peer of the existing Configuration /
 * Placement / Chrome sections.
 *
 * Per Q-31 (c): both inspector buttons AND the right-click context
 * menu dispatch the same action vocabulary. This component renders the
 * inspector surface; `CanvasContextMenu` renders the right-click
 * surface; both call `hook.setWidgetZIndex(placementId, action)`.
 *
 * Disabled state: when no widget is selected (`placementId === null`)
 * OR the subject is the inherited core (`isCore === true`). The core
 * is structurally anchored per the F-series canon and is not a z-order
 * target (Q-22).
 *
 * Visual: matches WidgetInspectorSection's existing section
 * conventions — `PropertySection` wrapper with title "Layer", a 2x2
 * grid of compact buttons inside, lucide chevron icons. Brass-accent
 * hover. The disabled state dims to content-muted.
 */
import {
  ChevronsUp,
  ChevronUp,
  ChevronDown,
  ChevronsDown,
} from "lucide-react"

import { PropertySection } from "@/bridgeable-admin/components/visual-authoring"
import type { ZIndexAction } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

export interface LayerInspectorSectionProps {
  /** Currently selected placement id; null when no widget selected. */
  placementId: string | null
  /** Dispatched on any of the four button clicks. */
  onAction: (action: ZIndexAction) => void
  /** When true the subject is the inherited core and z-order actions
   * are disabled (core is structurally anchored per Q-22). */
  isCore?: boolean
}

interface ButtonSpec {
  action: ZIndexAction
  label: string
  testId: string
  Icon: typeof ChevronsUp
}

const BUTTONS: ButtonSpec[] = [
  {
    action: "front",
    label: "Bring to front",
    testId: "layer-action-front",
    Icon: ChevronsUp,
  },
  {
    action: "forward",
    label: "Bring forward",
    testId: "layer-action-forward",
    Icon: ChevronUp,
  },
  {
    action: "backward",
    label: "Send backward",
    testId: "layer-action-backward",
    Icon: ChevronDown,
  },
  {
    action: "back",
    label: "Send to back",
    testId: "layer-action-back",
    Icon: ChevronsDown,
  },
]

export function LayerInspectorSection(props: LayerInspectorSectionProps) {
  const { placementId, onAction, isCore = false } = props
  const disabled = placementId === null || isCore

  return (
    <PropertySection
      title="Layer"
      defaultExpanded
      className="data-testid-layer-inspector-section"
    >
      <div
        data-testid="layer-inspector-section"
        className="grid grid-cols-2 gap-1.5 px-1"
      >
        {BUTTONS.map(({ action, label, testId, Icon }) => (
          <button
            key={action}
            type="button"
            data-testid={testId}
            disabled={disabled}
            onClick={() => onAction(action)}
            className={[
              "flex items-center justify-start gap-1.5 rounded-sm px-2 py-1.5",
              "text-[11px] text-left",
              "border border-[color:var(--border-subtle)]",
              "bg-[color:var(--surface-elevated)]",
              "transition-colors duration-100",
              disabled
                ? "cursor-not-allowed opacity-50 text-[color:var(--content-muted)]"
                : "cursor-pointer text-[color:var(--content-base)] hover:border-[color:var(--accent)] hover:text-[color:var(--accent)]",
            ].join(" ")}
            style={{ fontFamily: "var(--font-plex-sans)" }}
          >
            <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
            <span className="truncate">{label}</span>
          </button>
        ))}
      </div>
    </PropertySection>
  )
}

export default LayerInspectorSection
