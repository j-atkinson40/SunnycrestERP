/**
 * CompactPropControl — dense wrapper around PropControlDispatcher
 * for the redesigned right rail.
 *
 * Layout:
 *   ┌────────────────────────────────────────────────┐
 *   │ [info-icon] propLabel  [src]  [reset]           │  ← always
 *   │   description (collapsed by default)            │  ← expandable
 *   │ [PropControlDispatcher]                          │
 *   └────────────────────────────────────────────────┘
 *
 * Source badge is a small icon — Default (registry) / Platform /
 * Vertical / Tenant / Draft. Reset button shows only when the
 * prop is overridden at the active scope.
 */
import { useState } from "react"
import { Info, RotateCcw } from "lucide-react"
import {
  PropControlDispatcher,
  type PropControlDispatcherProps,
} from "@/lib/visual-editor/components/PropControls"
import type { ConfigPropSchema } from "@/lib/visual-editor/registry"


export type PropSource =
  | "registration-default"
  | "class-default"
  | "platform-default"
  | "vertical-default"
  | "tenant-override"
  | "draft"


interface Props {
  /** Prop key — `configurableProps` is keyed by name in
   * `Record<string, ConfigPropSchema>`, so the caller passes the
   * name explicitly rather than reading it off the schema. */
  name: string
  schema: ConfigPropSchema
  value: unknown
  onChange: (next: unknown) => void
  disabled?: boolean
  source: PropSource
  /** When true, show a reset-to-inherited affordance. */
  isOverriddenAtCurrentScope: boolean
  onReset: () => void
}


function SourceBadge({ source }: { source: PropSource }) {
  const labels: Record<PropSource, { letter: string; tone: string; title: string }> = {
    "registration-default": { letter: "D", tone: "text-content-subtle", title: "Default (registration)" },
    "class-default": { letter: "C", tone: "text-content-muted", title: "Inherited from class default" },
    "platform-default": { letter: "P", tone: "text-content-muted", title: "Platform default" },
    "vertical-default": { letter: "V", tone: "text-content-muted", title: "Vertical default" },
    "tenant-override": { letter: "T", tone: "text-accent", title: "Tenant override" },
    draft: { letter: "•", tone: "text-status-warning", title: "Unsaved draft" },
  }
  const { letter, tone, title } = labels[source]
  return (
    <span
      className={`inline-flex h-4 w-4 items-center justify-center rounded-full bg-surface-sunken text-[9px] font-medium ${tone}`}
      title={title}
      data-testid={`source-badge-${source}`}
    >
      {letter}
    </span>
  )
}


export function CompactPropControl({
  name,
  schema,
  value,
  onChange,
  disabled,
  source,
  isOverriddenAtCurrentScope,
  onReset,
}: Props) {
  const [showDescription, setShowDescription] = useState(false)
  const description = schema.description
  const displayLabel = schema.displayLabel ?? name

  const isInlineLayout =
    schema.type === "boolean" ||
    (schema.type === "enum" &&
      Array.isArray(schema.bounds) &&
      (schema.bounds as unknown[]).length <= 4)

  const dispatcherProps: PropControlDispatcherProps = {
    schema,
    value,
    onChange,
    disabled,
    "data-testid": `compact-prop-${name}`,
  }

  return (
    <div
      className="group flex flex-col gap-1.5 rounded-sm px-2 py-1.5 hover:bg-accent-subtle/20"
      data-testid={`compact-prop-row-${name}`}
      data-prop-overridden={isOverriddenAtCurrentScope ? "true" : "false"}
    >
      <div className="flex items-center gap-1.5">
        {description && (
          <button
            type="button"
            onClick={() => setShowDescription((s) => !s)}
            className="text-content-subtle hover:text-content-strong"
            aria-label={showDescription ? "Hide description" : "Show description"}
            data-testid={`compact-prop-info-${name}`}
          >
            <Info size={11} />
          </button>
        )}
        <span className="flex-1 text-caption font-medium text-content-strong">
          {displayLabel}
        </span>
        <SourceBadge source={source} />
        {isOverriddenAtCurrentScope && (
          <button
            type="button"
            onClick={onReset}
            className="rounded-sm p-0.5 text-content-muted opacity-0 hover:bg-accent-subtle/40 hover:text-content-strong group-hover:opacity-100"
            aria-label="Reset to inherited"
            data-testid={`compact-prop-reset-${name}`}
          >
            <RotateCcw size={11} />
          </button>
        )}
        {isInlineLayout && (
          <div className="ml-1 flex-shrink-0">
            <PropControlDispatcher {...dispatcherProps} />
          </div>
        )}
      </div>

      {showDescription && description && (
        <div
          className="pl-5 text-caption text-content-muted"
          data-testid={`compact-prop-desc-${name}`}
        >
          {description}
        </div>
      )}

      {!isInlineLayout && (
        <div className="pl-5">
          <PropControlDispatcher {...dispatcherProps} />
        </div>
      )}
    </div>
  )
}


/** Group-by helper — categorize props for the right rail. */
export function inferPropGroup(propName: string): string {
  const n = propName.toLowerCase()
  if (n.includes("color") || n.includes("token") || n.includes("accent") || n.includes("font") || n.includes("style")) {
    return "Appearance"
  }
  if (n.includes("show") || n.includes("hide") || n.includes("visible") || n.includes("position") || n.includes("alignment") || n.includes("layout") || n.includes("density")) {
    return "Layout"
  }
  if (n.includes("max") || n.includes("min") || n.includes("limit") || n.includes("count") || n.includes("interval") || n.includes("retry") || n.includes("timeout")) {
    return "Behavior"
  }
  return "General"
}
