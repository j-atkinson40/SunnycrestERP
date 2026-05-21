/**
 * AtomInspectorDispatch — WB-4b per-atom inspector dispatch.
 *
 * Reads the selected atom_id (null = canvas root) + the current
 * draft `CompositionBlob` + a `setConfig(atom_id, next_config)`
 * mutator from the parent.
 *
 * For each of the 9 Phase 1 atom kinds, a small inspector component
 * renders the right-rail controls per the WB-4b investigation
 * Area 4 enumeration. `CanvasRootInspector` renders when no atom is
 * selected (direction + spacing + alignment of the synthetic root
 * conditional_container).
 *
 * The dispatch is composition only; each per-atom inspector is small
 * enough that inlining all 9 within this file keeps the substrate
 * readable while staying under the LOC budget.
 */
import { useCallback } from "react"

import type {
  AtomNode,
  AtomType,
  CompositionBlob,
} from "@/lib/widget-builder/types/composition-blob"

import {
  BindingPlaceholderField,
  InspectorField,
  InspectorSection,
  SelectField,
  TextFieldUncontrolled,
} from "./inspector-primitives"


// ── Vocabulary tables (shared with runtime renderers) ───────────────

const TYPOGRAPHY_OPTIONS = [
  { value: "body", label: "Body" },
  { value: "body-sm", label: "Body small" },
  { value: "caption", label: "Caption" },
  { value: "label", label: "Label" },
  { value: "heading-1", label: "Heading 1" },
  { value: "heading-2", label: "Heading 2" },
  { value: "heading-3", label: "Heading 3" },
  { value: "mono", label: "Mono" },
  { value: "serif", label: "Serif" },
] as const

const ALIGN_OPTIONS = [
  { value: "start", label: "Start" },
  { value: "center", label: "Center" },
  { value: "end", label: "End" },
] as const

const ALIGN_FOUR_OPTIONS = [
  { value: "start", label: "Start" },
  { value: "center", label: "Center" },
  { value: "end", label: "End" },
  { value: "stretch", label: "Stretch" },
] as const

const COLOR_OPTIONS = [
  { value: "default", label: "Default" },
  { value: "muted", label: "Muted" },
  { value: "subtle", label: "Subtle" },
  { value: "accent", label: "Accent" },
  { value: "success", label: "Success" },
  { value: "warning", label: "Warning" },
  { value: "danger", label: "Danger" },
] as const

const ICON_SIZE_OPTIONS = [
  { value: "xs", label: "XS" },
  { value: "sm", label: "Small" },
  { value: "md", label: "Medium" },
  { value: "lg", label: "Large" },
  { value: "xl", label: "XL" },
] as const

const STATUS_BADGE_VARIANT_OPTIONS = [
  { value: "neutral", label: "Neutral" },
  { value: "success", label: "Success" },
  { value: "warning", label: "Warning" },
  { value: "danger", label: "Danger" },
  { value: "info", label: "Info" },
] as const

const DIVIDER_ORIENTATION_OPTIONS = [
  { value: "horizontal", label: "Horizontal" },
  { value: "vertical", label: "Vertical" },
] as const

const DIVIDER_SPACING_OPTIONS = [
  { value: "compact", label: "Compact" },
  { value: "normal", label: "Normal" },
  { value: "loose", label: "Loose" },
] as const

const DIVIDER_COLOR_OPTIONS = [
  { value: "subtle", label: "Subtle" },
  { value: "normal", label: "Normal" },
] as const

const BUTTON_VARIANT_OPTIONS = [
  { value: "primary", label: "Primary" },
  { value: "secondary", label: "Secondary" },
  { value: "ghost", label: "Ghost" },
  { value: "destructive", label: "Destructive" },
] as const

const BUTTON_SIZE_OPTIONS = [
  { value: "sm", label: "Small" },
  { value: "md", label: "Medium" },
  { value: "lg", label: "Large" },
] as const

const VALUE_FORMAT_OPTIONS = [
  { value: "text", label: "Text" },
  { value: "number", label: "Number" },
  { value: "currency", label: "Currency" },
  { value: "percent", label: "Percent" },
  { value: "date", label: "Date" },
  { value: "duration", label: "Duration" },
  { value: "relative-time", label: "Relative time" },
] as const

const IMAGE_ASPECT_OPTIONS = [
  { value: "auto", label: "Auto" },
  { value: "square", label: "Square" },
  { value: "video", label: "16:9" },
  { value: "portrait", label: "3:4" },
] as const

const IMAGE_FIT_OPTIONS = [
  { value: "cover", label: "Cover" },
  { value: "contain", label: "Contain" },
] as const

const CONTAINER_DIRECTION_OPTIONS = [
  { value: "column", label: "Column" },
  { value: "row", label: "Row" },
] as const

const CONTAINER_SPACING_OPTIONS = [
  { value: "compact", label: "Compact" },
  { value: "normal", label: "Normal" },
  { value: "loose", label: "Loose" },
] as const


// ── Helpers ─────────────────────────────────────────────────────────

type ConfigDict = Record<string, unknown>

function get<T extends string>(
  config: ConfigDict | undefined,
  key: string,
): T | undefined {
  if (!config) return undefined
  const v = config[key]
  return typeof v === "string" ? (v as T) : undefined
}

function getStr(config: ConfigDict | undefined, key: string): string {
  const v = config?.[key]
  return typeof v === "string" ? v : ""
}

function getNum(config: ConfigDict | undefined, key: string): number | "" {
  const v = config?.[key]
  return typeof v === "number" ? v : ""
}


export interface AtomInspectorDispatchProps {
  blob: CompositionBlob
  selectedAtomId: string | null
  /** Caller mutates draft config for an atom (or root). */
  onUpdateConfig: (atomId: string, nextConfig: ConfigDict) => void
  /** Per-atom validation errors keyed on atom_id. */
  errors?: Record<string, string[]>
}


export function AtomInspectorDispatch(props: AtomInspectorDispatchProps) {
  const { blob, selectedAtomId, onUpdateConfig, errors } = props

  const selectedNode: AtomNode | null = selectedAtomId
    ? (blob.atom_tree[selectedAtomId] ?? null)
    : null

  // No atom → render canvas root inspector.
  if (!selectedNode) {
    const root = blob.atom_tree[blob.root_atom_id]
    if (!root) return null
    return (
      <CanvasRootInspector
        node={root}
        onChange={(next) => onUpdateConfig(root.atom_id, next)}
      />
    )
  }

  const rowErrors = errors?.[selectedNode.atom_id] ?? []
  const onChange = (next: ConfigDict) =>
    onUpdateConfig(selectedNode.atom_id, next)

  switch (selectedNode.atom_type) {
    case "text_label":
      return (
        <TextLabelInspector
          node={selectedNode}
          onChange={onChange}
          errors={rowErrors}
        />
      )
    case "value_display":
      return (
        <ValueDisplayInspector
          node={selectedNode}
          onChange={onChange}
          errors={rowErrors}
        />
      )
    case "icon":
      return (
        <IconInspector node={selectedNode} onChange={onChange} errors={rowErrors} />
      )
    case "status_badge":
      return (
        <StatusBadgeInspector
          node={selectedNode}
          onChange={onChange}
          errors={rowErrors}
        />
      )
    case "divider":
      return (
        <DividerInspector
          node={selectedNode}
          onChange={onChange}
          errors={rowErrors}
        />
      )
    case "button":
      return (
        <ButtonInspector
          node={selectedNode}
          onChange={onChange}
          errors={rowErrors}
        />
      )
    case "image":
      return (
        <ImageInspector
          node={selectedNode}
          onChange={onChange}
          errors={rowErrors}
        />
      )
    case "conditional_container":
      return (
        <ConditionalContainerInspector
          node={selectedNode}
          onChange={onChange}
          errors={rowErrors}
        />
      )
    case "repeater_atom":
      return (
        <RepeaterAtomInspector
          node={selectedNode}
          onChange={onChange}
          errors={rowErrors}
        />
      )
    default: {
      const _exhaustive: never = selectedNode.atom_type
      void _exhaustive
      return null
    }
  }
}


// ── Common identity card ────────────────────────────────────────────

function AtomIdentityCard({
  node,
  label,
}: {
  node: AtomNode
  label: string
}) {
  return (
    <div
      data-testid="atom-inspector-identity"
      className="mb-3 rounded-md border border-border-subtle bg-surface-raised p-2 text-caption text-content-muted"
    >
      <div className="font-medium text-content-base">{label}</div>
      <div className="font-plex-mono text-content-subtle">
        {node.atom_id.slice(0, 8)}…
      </div>
    </div>
  )
}


function findError(errors: string[], substr: string): string | undefined {
  return errors.find((e) => e.toLowerCase().includes(substr.toLowerCase()))
}


// ── Per-atom inspectors ─────────────────────────────────────────────

function TextLabelInspector({
  node,
  onChange,
  errors,
}: {
  node: AtomNode
  onChange: (next: ConfigDict) => void
  errors: string[]
}) {
  const cfg = node.config ?? {}
  const textError = findError(errors, "text")
  return (
    <div data-testid="atom-inspector-text_label">
      <AtomIdentityCard node={node} label="Text label" />
      <InspectorSection title="Content">
        <InspectorField label="Text" error={textError}>
          <TextFieldUncontrolled
            testId="atom-inspector-text"
            value={getStr(cfg, "text")}
            placeholder="Static text"
            error={textError}
            onCommit={(v) => onChange({ ...cfg, text: v })}
          />
        </InspectorField>
      </InspectorSection>
      <InspectorSection title="Appearance">
        <InspectorField label="Variant">
          <SelectField
            testId="atom-inspector-variant"
            value={get(cfg, "variant") ?? "body"}
            onChange={(v) => onChange({ ...cfg, variant: v })}
            options={TYPOGRAPHY_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Alignment">
          <SelectField
            testId="atom-inspector-alignment"
            value={get(cfg, "alignment") ?? "start"}
            onChange={(v) => onChange({ ...cfg, alignment: v })}
            options={ALIGN_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Color">
          <SelectField
            testId="atom-inspector-color"
            value={get(cfg, "color") ?? "default"}
            onChange={(v) => onChange({ ...cfg, color: v })}
            options={COLOR_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Max lines">
          <TextFieldUncontrolled
            testId="atom-inspector-max-lines"
            value={String(getNum(cfg, "max_lines") || "")}
            placeholder="Optional"
            onCommit={(v) => {
              const n = parseInt(v, 10)
              const next = { ...cfg }
              if (Number.isFinite(n) && n > 0) next.max_lines = n
              else delete next.max_lines
              onChange(next)
            }}
          />
        </InspectorField>
      </InspectorSection>
    </div>
  )
}


function ValueDisplayInspector({
  node,
  onChange,
  errors,
}: {
  node: AtomNode
  onChange: (next: ConfigDict) => void
  errors: string[]
}) {
  const cfg = node.config ?? {}
  const bindError = findError(errors, "binding")
  const format = (get(cfg, "format") as string | undefined) ?? "number"
  return (
    <div data-testid="atom-inspector-value_display">
      <AtomIdentityCard node={node} label="Value" />
      <InspectorSection title="Source">
        <BindingPlaceholderField
          label="Bound value"
          activatedIn="WB-6"
          testId="atom-inspector-binding-placeholder"
        />
        {bindError ? (
          <div className="text-caption text-status-error">{bindError}</div>
        ) : null}
      </InspectorSection>
      <InspectorSection title="Format">
        <InspectorField label="Format">
          <SelectField
            testId="atom-inspector-format"
            value={format}
            onChange={(v) => onChange({ ...cfg, format: v })}
            options={VALUE_FORMAT_OPTIONS}
          />
        </InspectorField>
        {format === "currency" ? (
          <InspectorField label="Currency code">
            <TextFieldUncontrolled
              testId="atom-inspector-currency-code"
              value={getStr(
                (cfg.format_config as ConfigDict | undefined) ?? {},
                "currency_code",
              )}
              placeholder="USD"
              onCommit={(v) => {
                const fc: ConfigDict = {
                  ...((cfg.format_config as ConfigDict) ?? {}),
                  currency_code: v || "USD",
                }
                onChange({ ...cfg, format_config: fc })
              }}
            />
          </InspectorField>
        ) : null}
        {format === "date" ? (
          <InspectorField label="Date format">
            <TextFieldUncontrolled
              testId="atom-inspector-date-format"
              value={getStr(
                (cfg.format_config as ConfigDict | undefined) ?? {},
                "date_format",
              )}
              placeholder="medium"
              onCommit={(v) => {
                const fc: ConfigDict = {
                  ...((cfg.format_config as ConfigDict) ?? {}),
                  date_format: v,
                }
                onChange({ ...cfg, format_config: fc })
              }}
            />
          </InspectorField>
        ) : null}
        <InspectorField label="Placeholder">
          <TextFieldUncontrolled
            testId="atom-inspector-placeholder"
            value={getStr(cfg, "placeholder")}
            placeholder="—"
            onCommit={(v) => onChange({ ...cfg, placeholder: v })}
          />
        </InspectorField>
      </InspectorSection>
      <InspectorSection title="Appearance">
        <InspectorField label="Variant">
          <SelectField
            testId="atom-inspector-variant"
            value={get(cfg, "variant") ?? "body"}
            onChange={(v) => onChange({ ...cfg, variant: v })}
            options={TYPOGRAPHY_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Alignment">
          <SelectField
            testId="atom-inspector-alignment"
            value={get(cfg, "alignment") ?? "start"}
            onChange={(v) => onChange({ ...cfg, alignment: v })}
            options={ALIGN_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Color">
          <SelectField
            testId="atom-inspector-color"
            value={get(cfg, "color") ?? "default"}
            onChange={(v) => onChange({ ...cfg, color: v })}
            options={COLOR_OPTIONS}
          />
        </InspectorField>
      </InspectorSection>
    </div>
  )
}


function IconInspector({
  node,
  onChange,
  errors,
}: {
  node: AtomNode
  onChange: (next: ConfigDict) => void
  errors: string[]
}) {
  const cfg = node.config ?? {}
  const iconError = findError(errors, "icon_name")
  return (
    <div data-testid="atom-inspector-icon">
      <AtomIdentityCard node={node} label="Icon" />
      <InspectorSection title="Identity">
        <InspectorField label="Icon name" error={iconError}>
          <TextFieldUncontrolled
            testId="atom-inspector-icon-name"
            value={getStr(cfg, "icon_name")}
            placeholder="check"
            error={iconError}
            onCommit={(v) => onChange({ ...cfg, icon_name: v })}
          />
        </InspectorField>
      </InspectorSection>
      <InspectorSection title="Appearance">
        <InspectorField label="Size">
          <SelectField
            testId="atom-inspector-size"
            value={get(cfg, "size_token") ?? "md"}
            onChange={(v) => onChange({ ...cfg, size_token: v })}
            options={ICON_SIZE_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Color">
          <SelectField
            testId="atom-inspector-color"
            value={get(cfg, "color") ?? "default"}
            onChange={(v) => onChange({ ...cfg, color: v })}
            options={COLOR_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Stroke width">
          <TextFieldUncontrolled
            testId="atom-inspector-stroke-width"
            value={String(getNum(cfg, "stroke_width") || 2)}
            placeholder="2"
            onCommit={(v) => {
              const n = parseFloat(v)
              onChange({
                ...cfg,
                stroke_width: Number.isFinite(n) ? n : 2,
              })
            }}
          />
        </InspectorField>
      </InspectorSection>
    </div>
  )
}


function StatusBadgeInspector({
  node,
  onChange,
  errors,
}: {
  node: AtomNode
  onChange: (next: ConfigDict) => void
  errors: string[]
}) {
  const cfg = node.config ?? {}
  const labelError = findError(errors, "label")
  return (
    <div data-testid="atom-inspector-status_badge">
      <AtomIdentityCard node={node} label="Status badge" />
      <InspectorSection title="Content">
        <InspectorField label="Label" error={labelError}>
          <TextFieldUncontrolled
            testId="atom-inspector-label"
            value={getStr(cfg, "label")}
            placeholder="Active"
            error={labelError}
            onCommit={(v) => onChange({ ...cfg, label: v })}
          />
        </InspectorField>
      </InspectorSection>
      <InspectorSection title="Appearance">
        <InspectorField label="Variant">
          <SelectField
            testId="atom-inspector-variant"
            value={get(cfg, "variant") ?? "neutral"}
            onChange={(v) => onChange({ ...cfg, variant: v })}
            options={STATUS_BADGE_VARIANT_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Icon name (optional)">
          <TextFieldUncontrolled
            testId="atom-inspector-icon-name"
            value={getStr(cfg, "icon_name")}
            placeholder="check"
            onCommit={(v) => onChange({ ...cfg, icon_name: v })}
          />
        </InspectorField>
      </InspectorSection>
    </div>
  )
}


function DividerInspector({
  node,
  onChange,
}: {
  node: AtomNode
  onChange: (next: ConfigDict) => void
  errors: string[]
}) {
  const cfg = node.config ?? {}
  return (
    <div data-testid="atom-inspector-divider">
      <AtomIdentityCard node={node} label="Divider" />
      <InspectorSection title="Layout">
        <InspectorField label="Orientation">
          <SelectField
            testId="atom-inspector-orientation"
            value={get(cfg, "orientation") ?? "horizontal"}
            onChange={(v) => onChange({ ...cfg, orientation: v })}
            options={DIVIDER_ORIENTATION_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Spacing">
          <SelectField
            testId="atom-inspector-spacing"
            value={get(cfg, "spacing") ?? "normal"}
            onChange={(v) => onChange({ ...cfg, spacing: v })}
            options={DIVIDER_SPACING_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Color">
          <SelectField
            testId="atom-inspector-color"
            value={get(cfg, "color") ?? "subtle"}
            onChange={(v) => onChange({ ...cfg, color: v })}
            options={DIVIDER_COLOR_OPTIONS}
          />
        </InspectorField>
      </InspectorSection>
    </div>
  )
}


function ButtonInspector({
  node,
  onChange,
  errors,
}: {
  node: AtomNode
  onChange: (next: ConfigDict) => void
  errors: string[]
}) {
  const cfg = node.config ?? {}
  const labelError = findError(errors, "label")
  return (
    <div data-testid="atom-inspector-button">
      <AtomIdentityCard node={node} label="Button" />
      <InspectorSection title="Content">
        <InspectorField label="Label" error={labelError}>
          <TextFieldUncontrolled
            testId="atom-inspector-label"
            value={getStr(cfg, "label")}
            placeholder="Go"
            error={labelError}
            onCommit={(v) => onChange({ ...cfg, label: v })}
          />
        </InspectorField>
        <InspectorField label="Icon name (optional)">
          <TextFieldUncontrolled
            testId="atom-inspector-icon-name"
            value={getStr(cfg, "icon_name")}
            placeholder="chevron-right"
            onCommit={(v) => onChange({ ...cfg, icon_name: v })}
          />
        </InspectorField>
      </InspectorSection>
      <InspectorSection title="Appearance">
        <InspectorField label="Variant">
          <SelectField
            testId="atom-inspector-variant"
            value={get(cfg, "variant") ?? "secondary"}
            onChange={(v) => onChange({ ...cfg, variant: v })}
            options={BUTTON_VARIANT_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Size">
          <SelectField
            testId="atom-inspector-size"
            value={get(cfg, "size") ?? "md"}
            onChange={(v) => onChange({ ...cfg, size: v })}
            options={BUTTON_SIZE_OPTIONS}
          />
        </InspectorField>
      </InspectorSection>
      <InspectorSection title="Action">
        <BindingPlaceholderField
          label="Action"
          activatedIn="WB-7"
          testId="atom-inspector-action-placeholder"
        />
      </InspectorSection>
    </div>
  )
}


function ImageInspector({
  node,
  onChange,
  errors,
}: {
  node: AtomNode
  onChange: (next: ConfigDict) => void
  errors: string[]
}) {
  const cfg = node.config ?? {}
  const altError = findError(errors, "alt")
  return (
    <div data-testid="atom-inspector-image">
      <AtomIdentityCard node={node} label="Image" />
      <InspectorSection title="Source">
        <BindingPlaceholderField
          label="Bound src"
          activatedIn="WB-6"
          testId="atom-inspector-src-placeholder"
        />
        <InspectorField label="Static src (URL)">
          <TextFieldUncontrolled
            testId="atom-inspector-src"
            value={getStr(cfg, "src")}
            placeholder="https://…"
            onCommit={(v) => onChange({ ...cfg, src: v })}
          />
        </InspectorField>
        <InspectorField label="Alt (required)" error={altError}>
          <TextFieldUncontrolled
            testId="atom-inspector-alt"
            value={getStr(cfg, "alt")}
            placeholder="Logo"
            error={altError}
            onCommit={(v) => onChange({ ...cfg, alt: v })}
          />
        </InspectorField>
      </InspectorSection>
      <InspectorSection title="Appearance">
        <InspectorField label="Aspect ratio">
          <SelectField
            testId="atom-inspector-aspect"
            value={get(cfg, "aspect_ratio_token") ?? "auto"}
            onChange={(v) => onChange({ ...cfg, aspect_ratio_token: v })}
            options={IMAGE_ASPECT_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Object fit">
          <SelectField
            testId="atom-inspector-fit"
            value={get(cfg, "object_fit") ?? "cover"}
            onChange={(v) => onChange({ ...cfg, object_fit: v })}
            options={IMAGE_FIT_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Fallback icon name">
          <TextFieldUncontrolled
            testId="atom-inspector-fallback-icon"
            value={getStr(cfg, "fallback_icon_name")}
            placeholder="image"
            onCommit={(v) => onChange({ ...cfg, fallback_icon_name: v })}
          />
        </InspectorField>
      </InspectorSection>
    </div>
  )
}


function ConditionalContainerInspector({
  node,
  onChange,
}: {
  node: AtomNode
  onChange: (next: ConfigDict) => void
  errors: string[]
}) {
  const cfg = node.config ?? {}
  return (
    <div data-testid="atom-inspector-conditional_container">
      <AtomIdentityCard node={node} label="Conditional container" />
      <InspectorSection title="Layout">
        <InspectorField label="Direction">
          <SelectField
            testId="atom-inspector-direction"
            value={get(cfg, "direction") ?? "column"}
            onChange={(v) => onChange({ ...cfg, direction: v })}
            options={CONTAINER_DIRECTION_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Spacing">
          <SelectField
            testId="atom-inspector-spacing"
            value={get(cfg, "spacing") ?? "normal"}
            onChange={(v) => onChange({ ...cfg, spacing: v })}
            options={CONTAINER_SPACING_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Alignment">
          <SelectField
            testId="atom-inspector-alignment"
            value={get(cfg, "alignment") ?? "start"}
            onChange={(v) => onChange({ ...cfg, alignment: v })}
            options={ALIGN_FOUR_OPTIONS}
          />
        </InspectorField>
      </InspectorSection>
      <InspectorSection title="Condition">
        <BindingPlaceholderField
          label="Condition binding"
          activatedIn="WB-7"
          testId="atom-inspector-condition-placeholder"
        />
      </InspectorSection>
      <InspectorSection title="Children">
        <p className="text-caption text-content-muted">
          Add children by dragging atoms onto the canvas. Children are
          managed in the canvas, not in the inspector.
        </p>
      </InspectorSection>
    </div>
  )
}


function RepeaterAtomInspector({
  node,
  onChange,
}: {
  node: AtomNode
  onChange: (next: ConfigDict) => void
  errors: string[]
}) {
  const cfg = node.config ?? {}
  return (
    <div data-testid="atom-inspector-repeater_atom">
      <AtomIdentityCard node={node} label="Repeater" />
      <InspectorSection title="Source">
        <BindingPlaceholderField
          label="Row binding"
          activatedIn="WB-6"
          testId="atom-inspector-row-binding-placeholder"
        />
      </InspectorSection>
      <InspectorSection title="Layout">
        <InspectorField label="Direction">
          <SelectField
            testId="atom-inspector-direction"
            value={get(cfg, "direction") ?? "column"}
            onChange={(v) => onChange({ ...cfg, direction: v })}
            options={CONTAINER_DIRECTION_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Spacing">
          <SelectField
            testId="atom-inspector-spacing"
            value={get(cfg, "spacing") ?? "normal"}
            onChange={(v) => onChange({ ...cfg, spacing: v })}
            options={CONTAINER_SPACING_OPTIONS}
          />
        </InspectorField>
      </InspectorSection>
      <InspectorSection title="Behavior">
        <InspectorField label="Empty state">
          <TextFieldUncontrolled
            testId="atom-inspector-empty-state"
            value={getStr(cfg, "empty_state")}
            placeholder="No items"
            onCommit={(v) => onChange({ ...cfg, empty_state: v })}
          />
        </InspectorField>
        <InspectorField label="Max rows">
          <TextFieldUncontrolled
            testId="atom-inspector-max-rows"
            value={String(getNum(cfg, "max_rows") || "")}
            placeholder="Optional"
            onCommit={(v) => {
              const n = parseInt(v, 10)
              const next = { ...cfg }
              if (Number.isFinite(n) && n > 0) next.max_rows = n
              else delete next.max_rows
              onChange(next)
            }}
          />
        </InspectorField>
      </InspectorSection>
      <InspectorSection title="Children">
        <p className="text-caption text-content-muted">
          Per-row children are managed via canvas drag-drop.
        </p>
      </InspectorSection>
    </div>
  )
}


function CanvasRootInspector({
  node,
  onChange,
}: {
  node: AtomNode
  onChange: (next: ConfigDict) => void
}) {
  const cfg = node.config ?? {}
  return (
    <div data-testid="atom-inspector-canvas-root">
      <div className="mb-3 text-caption text-content-muted">
        Canvas root — select an atom to configure it, or edit the canvas
        defaults below.
      </div>
      <InspectorSection title="Canvas">
        <InspectorField label="Direction">
          <SelectField
            testId="canvas-root-inspector-direction"
            value={get(cfg, "direction") ?? "column"}
            onChange={(v) => onChange({ ...cfg, direction: v })}
            options={CONTAINER_DIRECTION_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Spacing">
          <SelectField
            testId="canvas-root-inspector-spacing"
            value={
              (get(cfg, "spacing") as string | undefined) ??
              (get(cfg, "gap_token") as string | undefined) ??
              "normal"
            }
            onChange={(v) => onChange({ ...cfg, spacing: v, gap_token: v })}
            options={CONTAINER_SPACING_OPTIONS}
          />
        </InspectorField>
        <InspectorField label="Alignment">
          <SelectField
            testId="canvas-root-inspector-alignment"
            value={get(cfg, "alignment") ?? "start"}
            onChange={(v) => onChange({ ...cfg, alignment: v })}
            options={ALIGN_FOUR_OPTIONS}
          />
        </InspectorField>
      </InspectorSection>
    </div>
  )
}


// ── Convenience hook for the page-level mutator ─────────────────────

export function useAtomConfigUpdater(
  blob: CompositionBlob | null,
  setDraft: (next: CompositionBlob) => void,
) {
  return useCallback(
    (atomId: string, nextConfig: ConfigDict) => {
      if (!blob) return
      const node = blob.atom_tree[atomId]
      if (!node) return
      const nextNode: AtomNode = { ...node, config: nextConfig }
      setDraft({
        ...blob,
        atom_tree: { ...blob.atom_tree, [atomId]: nextNode },
      })
    },
    [blob, setDraft],
  )
}


// Re-exports for tests + page-level usage.
export type AtomKind = AtomType
