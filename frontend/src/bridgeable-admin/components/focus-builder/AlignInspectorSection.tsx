/**
 * AlignInspectorSection — sub-arc FF-7.
 *
 * Multi-select inspector section per Q-17 (b) + Q-18 (a). Renders
 * six align affordances arranged as 2 rows × 3 buttons:
 *
 *   Row 1 (X axis):  Left │ Center horizontal │ Right
 *   Row 2 (Y axis):  Top  │ Center vertical   │ Bottom
 *
 * Per Q-18 (a): align is the ONLY multi-select inspector action.
 * Position / Layer / Chrome sections are HIDDEN in multi-select
 * context (see FocusBuilderInspector branching).
 */
import {
  AlignStartHorizontal,
  AlignCenterHorizontal,
  AlignEndHorizontal,
  AlignStartVertical,
  AlignCenterVertical,
  AlignEndVertical,
} from "lucide-react"

import { PropertySection } from "@/bridgeable-admin/components/visual-authoring"
import type {
  AlignAction,
  AlignablePlacement,
} from "./computeAlignTargets"

export interface AlignInspectorSectionProps {
  selectedPlacements: AlignablePlacement[]
  onAlign: (action: AlignAction) => void
}

interface AlignButtonSpec {
  action: AlignAction
  label: string
  Icon: typeof AlignStartHorizontal
}

// Lucide icon naming convention: `AlignStartVertical` is the
// LEFT-align icon (start of horizontal axis = left edge). The
// inspector reads naturally if we stick to the icon as drawn,
// mapping the operator-facing label to the action.
const ALIGN_BUTTONS: AlignButtonSpec[] = [
  { action: "left", label: "Align left", Icon: AlignStartVertical },
  {
    action: "center-horizontal",
    label: "Center horizontal",
    Icon: AlignCenterVertical,
  },
  { action: "right", label: "Align right", Icon: AlignEndVertical },
  { action: "top", label: "Align top", Icon: AlignStartHorizontal },
  {
    action: "center-vertical",
    label: "Center vertical",
    Icon: AlignCenterHorizontal,
  },
  { action: "bottom", label: "Align bottom", Icon: AlignEndHorizontal },
]

export function AlignInspectorSection(props: AlignInspectorSectionProps) {
  const { selectedPlacements, onAlign } = props
  const disabled = selectedPlacements.length < 2

  return (
    <PropertySection title="Align" defaultExpanded>
      <div
        data-testid="align-inspector-section"
        className="grid grid-cols-3 gap-2 px-3 py-2"
      >
        {ALIGN_BUTTONS.map(({ action, label, Icon }) => (
          <button
            key={action}
            type="button"
            data-testid={`align-action-${action}`}
            disabled={disabled}
            aria-label={label}
            title={label}
            onClick={() => onAlign(action)}
            className={[
              "flex h-9 items-center justify-center",
              "rounded-md",
              "border border-[color:var(--border-subtle)]",
              "bg-[color:var(--surface-base)]",
              "text-[color:var(--content-base)]",
              "transition-colors duration-100",
              disabled
                ? "cursor-not-allowed opacity-40"
                : "hover:border-[color:var(--accent)] hover:bg-[color:var(--accent)]/10 hover:text-[color:var(--accent)]",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--accent)]/40",
            ].join(" ")}
          >
            <Icon className="h-4 w-4" aria-hidden />
          </button>
        ))}
      </div>
      <div
        className="px-3 pb-2 text-[11px] text-[color:var(--content-muted)]"
        style={{ fontFamily: "var(--font-plex-sans)" }}
      >
        {selectedPlacements.length} widgets selected
      </div>
    </PropertySection>
  )
}

export default AlignInspectorSection
