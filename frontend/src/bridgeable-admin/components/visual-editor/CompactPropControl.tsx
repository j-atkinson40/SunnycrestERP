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
// Arc 4d — tenth canonical primitive promotion. Inline SourceBadge
// retired in favor of canonical SourceBadge with `variant="letter"`.
// 3-way pattern drift closed (ThemeTab inline + per-tab + canonical).
import {
  SourceBadge,
  ScopeDiffPopover,
  type SourceValue,
  type ResolutionSourceEntry,
} from "@/lib/visual-editor/source-badge"


export type PropSource =
  | "registration-default"
  | "class-default"
  | "platform-default"
  | "vertical-default"
  | "tenant-override"
  | "draft"


/**
 * Arc 4d — map historical PropSource vocabulary onto canonical
 * SourceValue. CompactPropControl callers continue to pass the
 * historical strings; the primitive accepts only canonical values.
 */
function toSourceValue(s: PropSource): SourceValue {
  switch (s) {
    case "registration-default":
      return "default"
    case "class-default":
      return "class-default"
    case "platform-default":
      return "platform"
    case "vertical-default":
      return "vertical"
    case "tenant-override":
      return "tenant"
    case "draft":
      return "draft"
  }
}


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
  /**
   * Arc 4d — optional resolution chain for hover-reveal scope diff.
   * When provided + non-empty, wraps the SourceBadge in
   * ScopeDiffPopover so the operator can see up-the-chain values.
   * Empty / undefined → bare badge with title tooltip only.
   */
  scopeSources?: ResolutionSourceEntry[]
  /** Optional fieldLabel for ScopeDiffPopover header (e.g. "accent token"). */
  scopeFieldLabel?: string
}


/**
 * Arc 4d — `SourceBadge` previously declared inline here. Promoted
 * to canonical primitive at `@/lib/visual-editor/source-badge`. The
 * letter-variant chrome matches the pre-Arc-4d treatment verbatim;
 * consumers (Class/Props tabs via this wrapper) pass `variant="letter"`.
 */
export function CompactPropControl({
  name,
  schema,
  value,
  onChange,
  disabled,
  source,
  isOverriddenAtCurrentScope,
  onReset,
  scopeSources,
  scopeFieldLabel,
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
        {/* Arc 4d — canonical SourceBadge (letter variant) optionally
            wrapped in ScopeDiffPopover for hover-reveal cascade diff. */}
        {scopeSources && scopeSources.length > 0 ? (
          <ScopeDiffPopover
            sources={scopeSources}
            currentValue={value}
            fieldLabel={scopeFieldLabel ?? displayLabel}
            data-testid={`scope-diff-${name}`}
          >
            <SourceBadge
              source={toSourceValue(source)}
              variant="letter"
              data-testid={`source-badge-${source}`}
            />
          </ScopeDiffPopover>
        ) : (
          <SourceBadge
            source={toSourceValue(source)}
            variant="letter"
            data-testid={`source-badge-${source}`}
          />
        )}
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
