/**
 * WidgetInspectorSection — selection-driven widget inspector (sub-arc F-3).
 *
 * Renders when `selection.kind === 'widget'` AND subject is a template
 * (cores have no widgets). Two parts:
 *
 *   1. Widget-specific configurable props (top) — drawn from the
 *      component registry's `configurableProps` for the placement's
 *      widget slug. F-3 ships placeholder widgets with minimal props
 *      (1 prop per widget) to demonstrate the pattern.
 *   2. Class-level chrome section (bottom, collapsible) — placement
 *      chrome overrides via the existing C-1 chrome primitives.
 *
 * "Remove widget" button at the bottom.
 */
import * as React from "react"
import { Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  ChromePresetPicker,
  PropertyPanel,
  PropertyRow,
  PropertySection,
  ScrubbableButton,
  TokenSwatchPicker,
  type PresetSlug,
} from "@/bridgeable-admin/components/visual-authoring"
import { getByName } from "@/lib/visual-editor/registry"
import type {
  ConfigPropSchema,
  RegistryEntry,
} from "@/lib/visual-editor/registry"

import type {
  WidgetPlacement,
  RowsBlob,
} from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

/**
 * Canonical default chrome values for placed widgets. F-3 widget
 * registrations do NOT carry a `defaultChrome` field on
 * `RegistrationMetadata`, so we fall back to these inline defaults
 * (matching the F-3 seed canon: Frosted preset, elevation 50,
 * corner_radius 70, backdrop_blur 44, surface-frosted,
 * border-subtle, space-3). When registrations later add a
 * `defaultChrome` field, swap this constant for a registry lookup.
 */
export const DEFAULT_WIDGET_CHROME = {
  preset: "frosted" as PresetSlug,
  elevation: 50,
  corner_radius: 70,
  backdrop_blur: 44,
  background_token: "surface-frosted",
  border_token: "border-subtle",
  padding_token: "space-3",
} as const

export interface WidgetInspectorSectionProps {
  /** The selected widget placement. */
  placement: WidgetPlacement
  /** Update the widget's chrome blob. */
  onUpdateWidget: (
    widgetId: string,
    partialChrome: Record<string, unknown>,
  ) => void
  /** Remove the widget. */
  onRemoveWidget: (widgetId: string) => void
  /**
   * Live theme tokens (light mode in F-2/F-3). Threaded through to
   * the TokenSwatchPicker controls for background/border/padding.
   * Optional — defaults to an empty record so unit tests can mount
   * without seeding tokens.
   */
  themeTokens?: Record<string, string>
}

export function findPlacementById(
  rows: RowsBlob,
  widgetId: string,
): WidgetPlacement | null {
  for (const r of rows ?? []) {
    for (const p of r.placements ?? []) {
      if (p.id === widgetId) return p
    }
  }
  return null
}

export function WidgetInspectorSection(props: WidgetInspectorSectionProps) {
  const {
    placement,
    onUpdateWidget,
    onRemoveWidget,
    themeTokens = {},
  } = props

  const chromeView = React.useMemo(() => {
    const c = (placement.chrome ?? {}) as Record<string, unknown>
    return {
      preset:
        (c.preset as PresetSlug | undefined) ?? DEFAULT_WIDGET_CHROME.preset,
      elevation:
        typeof c.elevation === "number"
          ? c.elevation
          : DEFAULT_WIDGET_CHROME.elevation,
      corner_radius:
        typeof c.corner_radius === "number"
          ? c.corner_radius
          : DEFAULT_WIDGET_CHROME.corner_radius,
      backdrop_blur:
        typeof c.backdrop_blur === "number"
          ? c.backdrop_blur
          : DEFAULT_WIDGET_CHROME.backdrop_blur,
      background_token:
        typeof c.background_token === "string"
          ? c.background_token
          : DEFAULT_WIDGET_CHROME.background_token,
      border_token:
        typeof c.border_token === "string"
          ? c.border_token
          : DEFAULT_WIDGET_CHROME.border_token,
      padding_token:
        typeof c.padding_token === "string"
          ? c.padding_token
          : DEFAULT_WIDGET_CHROME.padding_token,
    }
  }, [placement.chrome])

  const registryEntry: RegistryEntry | undefined = React.useMemo(
    () => getByName("widget", placement.widget_slug),
    [placement.widget_slug],
  )

  const configurableProps = registryEntry?.metadata.configurableProps ?? {}
  const propEntries = Object.entries(configurableProps) as Array<
    [string, ConfigPropSchema]
  >

  return (
    <PropertyPanel data-testid="widget-inspector-section">
      <header className="flex items-center justify-between px-1">
        <div className="flex min-w-0 flex-col">
          <span
            className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[color:var(--content-muted)]"
            style={{ fontFamily: "var(--font-plex-sans)" }}
          >
            Widget
          </span>
          <span
            className="truncate text-[13px] font-medium text-[color:var(--content-strong)]"
            style={{ fontFamily: "var(--font-plex-sans)" }}
            data-testid="widget-inspector-name"
          >
            {registryEntry?.metadata.displayName ?? placement.widget_slug}
          </span>
        </div>
      </header>

      {propEntries.length > 0 && (
        <PropertySection title="Configuration" defaultExpanded>
          {propEntries.map(([key, schema]) => (
            <PropertyRow key={key} inheritanceSource="explicit">
              <WidgetPropControl
                propKey={key}
                schema={schema}
                value={placement.chrome?.[key]}
                onChange={(v) =>
                  onUpdateWidget(placement.id, { [key]: v })
                }
              />
            </PropertyRow>
          ))}
        </PropertySection>
      )}

      <PropertySection title="Placement" defaultExpanded={false}>
        <PropertyRow inheritanceSource="explicit">
          <ScrubbableButton
            value={placement.column_span ?? 4}
            min={1}
            max={12}
            label="Column span"
            onChange={(v) =>
              onUpdateWidget(placement.id, { _placement_column_span: v })
            }
          />
        </PropertyRow>
      </PropertySection>

      {/* Chrome — per-placement override surface (sub-arc F-3.1b).
          No inheritance indicators: widget chrome is stamped at
          placement creation and edited directly; there is no Tier-1
          cascade for widgets. Each field's onChange flows through
          the hook's updateWidget → adapter → backend prop_overrides
          translation; defaults render when individual chrome fields
          are absent. */}
      <PropertySection title="Chrome" defaultExpanded>
        <PropertyRow inheritanceSource="explicit">
          <ChromePresetPicker
            value={chromeView.preset}
            onChange={(p) =>
              onUpdateWidget(placement.id, { preset: p as PresetSlug | null })
            }
          />
        </PropertyRow>
        <PropertyRow inheritanceSource="explicit">
          <ScrubbableButton
            value={chromeView.elevation}
            min={0}
            max={100}
            label="Elevation"
            onChange={(v) => onUpdateWidget(placement.id, { elevation: v })}
          />
        </PropertyRow>
        <PropertyRow inheritanceSource="explicit">
          <ScrubbableButton
            value={chromeView.corner_radius}
            min={0}
            max={100}
            label="Corner radius"
            onChange={(v) =>
              onUpdateWidget(placement.id, { corner_radius: v })
            }
          />
        </PropertyRow>
        <PropertyRow inheritanceSource="explicit">
          <ScrubbableButton
            value={chromeView.backdrop_blur}
            min={0}
            max={100}
            label="Backdrop blur"
            onChange={(v) =>
              onUpdateWidget(placement.id, { backdrop_blur: v })
            }
          />
        </PropertyRow>
        <PropertyRow inheritanceSource="explicit">
          <TokenSwatchPicker
            value={chromeView.background_token}
            tokenFamily="surface"
            themeTokens={themeTokens}
            onChange={(t) =>
              onUpdateWidget(placement.id, { background_token: t })
            }
            label="Background"
          />
        </PropertyRow>
        <PropertyRow inheritanceSource="explicit">
          <TokenSwatchPicker
            value={chromeView.border_token}
            tokenFamily="border"
            themeTokens={themeTokens}
            onChange={(t) =>
              onUpdateWidget(placement.id, { border_token: t })
            }
            label="Border"
          />
        </PropertyRow>
        <PropertyRow inheritanceSource="explicit">
          <TokenSwatchPicker
            value={chromeView.padding_token}
            tokenFamily="padding"
            themeTokens={themeTokens}
            onChange={(t) =>
              onUpdateWidget(placement.id, { padding_token: t })
            }
            label="Padding"
          />
        </PropertyRow>
      </PropertySection>

      <div className="flex items-center justify-end p-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          data-testid="widget-remove-button"
          onClick={() => onRemoveWidget(placement.id)}
          className="h-7 gap-1 px-2 text-[11px] text-[color:var(--status-error,#a14040)] hover:bg-[color:var(--status-error-muted,rgba(180,60,60,0.08))]"
        >
          <Trash2 className="h-3 w-3" />
          Remove widget
        </Button>
      </div>
    </PropertyPanel>
  )
}

interface WidgetPropControlProps {
  propKey: string
  schema: ConfigPropSchema
  value: unknown
  onChange: (next: unknown) => void
}

/**
 * Minimal control dispatcher for F-3 placeholder widgets. Only the
 * three types the F-3 seeds need are handled inline; richer controls
 * (token references, arrays, etc.) live in the existing
 * PropControlDispatcher and can be wired in a follow-up.
 */
function WidgetPropControl(props: WidgetPropControlProps) {
  const { propKey, schema, value, onChange } = props
  const label = schema.displayLabel ?? propKey

  if (schema.type === "number") {
    const bounds = (schema.bounds ?? [0, 100]) as [number, number]
    const current =
      typeof value === "number" ? value : (schema.default as number) ?? 0
    return (
      <ScrubbableButton
        value={current}
        min={bounds[0]}
        max={bounds[1]}
        label={label}
        onChange={(v) => onChange(v)}
      />
    )
  }
  if (schema.type === "boolean") {
    const current =
      typeof value === "boolean" ? value : (schema.default as boolean) ?? false
    return (
      <label
        className="flex items-center gap-2 text-[12px] text-[color:var(--content-base)]"
        data-testid={`widget-bool-${propKey}`}
      >
        <input
          type="checkbox"
          checked={current}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span>{label}</span>
      </label>
    )
  }
  // Fallback for unhandled types — show value as text.
  return (
    <div
      className="text-[11px] text-content-muted"
      data-testid={`widget-prop-fallback-${propKey}`}
    >
      {label}: {String(value ?? schema.default)}
    </div>
  )
}

export default WidgetInspectorSection
