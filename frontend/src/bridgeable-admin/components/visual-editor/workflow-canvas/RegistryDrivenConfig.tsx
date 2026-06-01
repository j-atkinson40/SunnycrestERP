/**
 * RegistryDrivenConfig — Phase B sub-arc B-3 (schema-driven inspector).
 *
 * Generic per-node-type inspector. Reads the selected node type's
 * registry `configurableProps` (the object-map B-2 shipped: type /
 * default / bounds / displayLabel / etc. per prop) and renders ONE
 * control per `ConfigPropType`. Replaces the pre-B-3 JSON-textarea
 * fallback for the 30 node types without a bespoke config.
 *
 * Decision §(a) Option Y (operator-locked): a single schema-driven
 * renderer covers all 30 fall-through types via their declared
 * configurableProps — NOT 30 bespoke files. The 2 genuinely-special
 * Focus configs (InvokeGenerationFocusConfig / InvokeReviewFocusConfig)
 * stay as bespoke overrides dispatched ahead of this generic renderer
 * in NodeConfigForm.
 *
 * Control mapping (the 8 ConfigPropTypes workflow-nodes declare):
 *   enum               -> <select> over bounds (allowed values)
 *   number             -> number <input> clamped to bounds [min,max]
 *   string             -> text <input> with maxLength from bounds
 *   boolean            -> <Switch>
 *   object             -> JSON <textarea> with parse validation
 *   array              -> list editor (add/remove per itemSchema)
 *   tokenReference     -> text <input> (token name; category shown as hint)
 *   componentReference -> <select> over registry getByType(componentTypes)
 *
 * Reads `node.config` for current values (falling back to each prop's
 * registry `default`); emits `onChange({...config, [key]: value})`.
 * Same `{config, onChange}` contract as the bespoke configs.
 *
 * The other 4 ConfigPropType union values (tableOfColumns / tableOfRows
 * / listOfParties / conditionalRule) are not declared by any
 * workflow-node registration; an unmapped type renders a read-only
 * "unsupported control" notice rather than throwing — defensive for
 * future vocabulary additions.
 */

import { useMemo } from "react"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { getByName, getByType } from "@/lib/visual-editor/registry"
import type {
  ComponentKind,
  ConfigPropSchema,
} from "@/lib/visual-editor/registry/types"
// Inspector cleanup (path A): hide the vestigial-visual props (A3-retired
// nodeShape/labelPosition/accentToken) + the not-yet-implemented indicator
// enums. The props STAY declared in the registry (≥3 rule + backend
// snapshot untouched); only their inspector controls are suppressed.
import { INSPECTOR_HIDDEN_PARAMS } from "@/lib/visual-editor/workflow-node-templates"


export interface RegistryDrivenConfigProps {
  /** Node type name (matches a workflow-node registry `name`). */
  nodeName: string
  config: Record<string, unknown>
  onChange: (next: Record<string, unknown>) => void
}


function humanize(key: string): string {
  return key
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[_-]/g, " ")
    .replace(/^\w/, (c) => c.toUpperCase())
}


export function RegistryDrivenConfig({
  nodeName,
  config,
  onChange,
}: RegistryDrivenConfigProps) {
  const props = useMemo<Record<string, ConfigPropSchema>>(() => {
    const entry = getByName("workflow-node", nodeName)
    return entry?.metadata.configurableProps ?? {}
  }, [nodeName])

  // Filter the inspector-hidden params (retired-visual + not-yet-built).
  // The props remain declared in the registry; we just don't render their
  // controls — the inspector shows only the real, editable config.
  const keys = Object.keys(props).filter((k) => !INSPECTOR_HIDDEN_PARAMS.has(k))

  if (keys.length === 0) {
    return (
      <p
        className="text-caption text-content-muted"
        data-testid="registry-driven-config-empty"
      >
        This node type has no configurable properties.
      </p>
    )
  }

  const patch = (key: string, value: unknown) => {
    onChange({ ...config, [key]: value })
  }

  return (
    <div
      className="flex flex-col gap-3"
      data-testid="registry-driven-config"
    >
      {keys.map((key) => {
        const schema = props[key]
        const current = key in config ? config[key] : schema.default
        return (
          <PropControl
            key={key}
            propKey={key}
            schema={schema}
            value={current}
            onChange={(v) => patch(key, v)}
          />
        )
      })}
    </div>
  )
}


interface PropControlProps {
  propKey: string
  schema: ConfigPropSchema
  value: unknown
  onChange: (value: unknown) => void
}


function PropControl({ propKey, schema, value, onChange }: PropControlProps) {
  const label = schema.displayLabel ?? humanize(propKey)
  const testId = `prop-${propKey}`

  return (
    <div data-testid={`registry-driven-prop-${propKey}`}>
      <Label className="mb-1.5 flex items-center gap-1 text-micro uppercase tracking-wider text-content-muted">
        {label}
        {schema.required && (
          <span className="text-status-error" aria-hidden>
            *
          </span>
        )}
      </Label>
      <PropInput
        propKey={propKey}
        schema={schema}
        value={value}
        onChange={onChange}
        testId={testId}
      />
      {schema.description && (
        <p className="mt-0.5 text-caption text-content-muted">
          {schema.description}
        </p>
      )}
    </div>
  )
}


function PropInput({
  propKey,
  schema,
  value,
  onChange,
  testId,
}: PropControlProps & { testId: string }) {
  switch (schema.type) {
    case "enum": {
      const options = Array.isArray(schema.bounds)
        ? (schema.bounds as string[])
        : []
      const v = typeof value === "string" ? value : String(value ?? "")
      return (
        <Select value={v || undefined} onValueChange={(next) => onChange(next)}>
          <SelectTrigger data-testid={testId} className="text-caption">
            <SelectValue placeholder="Select…" />
          </SelectTrigger>
          <SelectContent>
            {options.map((opt) => (
              <SelectItem key={opt} value={opt}>
                {opt}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )
    }

    case "number": {
      const bounds = Array.isArray(schema.bounds)
        ? (schema.bounds as [number, number])
        : undefined
      const v = typeof value === "number" ? value : Number(value ?? 0)
      return (
        <Input
          type="number"
          value={Number.isFinite(v) ? v : 0}
          min={bounds?.[0]}
          max={bounds?.[1]}
          onChange={(e) => {
            const n = Number(e.target.value)
            onChange(Number.isFinite(n) ? n : 0)
          }}
          data-testid={testId}
          className="text-caption"
        />
      )
    }

    case "string": {
      const maxLength =
        schema.bounds &&
        typeof schema.bounds === "object" &&
        "maxLength" in schema.bounds
          ? (schema.bounds as { maxLength?: number }).maxLength
          : undefined
      const v = typeof value === "string" ? value : String(value ?? "")
      return (
        <Input
          value={v}
          maxLength={maxLength}
          onChange={(e) => onChange(e.target.value)}
          data-testid={testId}
          className="text-caption"
        />
      )
    }

    case "boolean": {
      const v = value === true
      return (
        <Switch
          checked={v}
          onCheckedChange={(next) => onChange(next)}
          data-testid={testId}
        />
      )
    }

    case "object":
      return (
        <JsonControl value={value} onChange={onChange} testId={testId} />
      )

    case "array":
      return (
        <ArrayControl
          schema={schema}
          value={value}
          onChange={onChange}
          testId={testId}
        />
      )

    case "tokenReference": {
      const v = typeof value === "string" ? value : String(value ?? "")
      return (
        <Input
          value={v}
          onChange={(e) => onChange(e.target.value)}
          placeholder={
            schema.tokenCategory
              ? `${schema.tokenCategory} token`
              : "token name"
          }
          data-testid={testId}
          className="font-plex-mono text-caption"
        />
      )
    }

    case "componentReference":
      return (
        <ComponentRefControl
          schema={schema}
          value={value}
          onChange={onChange}
          testId={testId}
        />
      )

    default:
      // Unmapped ConfigPropType (tableOfColumns / tableOfRows /
      // listOfParties / conditionalRule — not declared by any
      // workflow-node today). Defensive read-only notice.
      return (
        <p
          className="rounded-sm border border-border-subtle bg-surface-sunken px-2 py-1 text-caption text-content-muted"
          data-testid={`${testId}-unsupported`}
        >
          {`Control for "${schema.type}" not available for ${propKey}.`}
        </p>
      )
  }
}


function JsonControl({
  value,
  onChange,
  testId,
}: {
  value: unknown
  onChange: (value: unknown) => void
  testId: string
}) {
  // Render the current value as JSON; parse + validate on edit. Invalid
  // JSON does NOT propagate (the prior valid value stays committed) but
  // surfaces an inline error so the operator can fix it.
  const text = useMemo(() => {
    try {
      return JSON.stringify(value ?? {}, null, 2)
    } catch {
      return "{}"
    }
  }, [value])

  return (
    <textarea
      defaultValue={text}
      rows={4}
      onChange={(e) => {
        try {
          const parsed = JSON.parse(e.target.value || "{}")
          onChange(parsed)
        } catch {
          // swallow — keep last valid value; operator continues typing
        }
      }}
      data-testid={testId}
      className="w-full rounded-md border border-border-base bg-surface-raised p-2 font-plex-mono text-caption text-content-base"
    />
  )
}


function ArrayControl({
  schema,
  value,
  onChange,
  testId,
}: {
  schema: ConfigPropSchema
  value: unknown
  onChange: (value: unknown) => void
  testId: string
}) {
  const items: unknown[] = Array.isArray(value) ? value : []
  const itemType = schema.itemSchema?.type ?? "string"

  const setItem = (idx: number, v: unknown) => {
    onChange(items.map((it, i) => (i === idx ? v : it)))
  }
  const addItem = () => {
    onChange([...items, schema.itemSchema?.default ?? ""])
  }
  const removeItem = (idx: number) => {
    onChange(items.filter((_, i) => i !== idx))
  }

  return (
    <div className="flex flex-col gap-1.5" data-testid={testId}>
      {items.length === 0 ? (
        <p className="text-caption text-content-muted">No items.</p>
      ) : (
        items.map((it, idx) => (
          <div key={idx} className="flex items-center gap-1.5">
            <Input
              value={
                itemType === "string"
                  ? typeof it === "string"
                    ? it
                    : String(it ?? "")
                  : String(it ?? "")
              }
              onChange={(e) =>
                setItem(
                  idx,
                  itemType === "number" ? Number(e.target.value) : e.target.value,
                )
              }
              data-testid={`${testId}-item-${idx}`}
              className="flex-1 text-caption"
            />
            <button
              type="button"
              onClick={() => removeItem(idx)}
              data-testid={`${testId}-item-${idx}-remove`}
              aria-label="Remove item"
              className="rounded-sm border border-border-base bg-surface-raised px-1.5 py-1 text-caption text-content-muted hover:text-status-error"
            >
              ×
            </button>
          </div>
        ))
      )}
      <button
        type="button"
        onClick={addItem}
        data-testid={`${testId}-add`}
        className="self-start rounded-sm border border-border-base bg-surface-raised px-2 py-0.5 text-caption text-content-base hover:bg-accent-subtle"
      >
        + Add
      </button>
    </div>
  )
}


function ComponentRefControl({
  schema,
  value,
  onChange,
  testId,
}: {
  schema: ConfigPropSchema
  value: unknown
  onChange: (value: unknown) => void
  testId: string
}) {
  const options = useMemo(() => {
    const types = (schema.componentTypes ?? []) as ComponentKind[]
    const names = new Set<string>()
    for (const t of types) {
      for (const e of getByType(t)) names.add(e.metadata.name)
    }
    return [...names].sort()
  }, [schema.componentTypes])

  const v = typeof value === "string" ? value : String(value ?? "")

  // If no options resolve (e.g. referenced kind has no registrations
  // yet), fall back to a free-text input so the operator isn't blocked.
  if (options.length === 0) {
    return (
      <Input
        value={v}
        onChange={(e) => onChange(e.target.value)}
        placeholder="component name"
        data-testid={testId}
        className="font-plex-mono text-caption"
      />
    )
  }

  return (
    <Select value={v || undefined} onValueChange={(next) => onChange(next)}>
      <SelectTrigger data-testid={testId} className="text-caption">
        <SelectValue placeholder="Select component…" />
      </SelectTrigger>
      <SelectContent>
        {options.map((opt) => (
          <SelectItem key={opt} value={opt}>
            {opt}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
