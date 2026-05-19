/**
 * FocusBuilderInspector — selection-driven inspector (sub-arc F-2).
 *
 * Reads from FocusBuilderSelectionContext + the appropriate Focus draft
 * hook (passed via props as `coreHook` or `templateHook`). Renders one
 * of three states:
 *
 *   selection.kind === 'none'        → empty hint
 *   selection.kind === 'core'        → chrome section
 *   selection.kind === 'background'  → substrate + typography sections
 *                                      (template editing only; for cores
 *                                      we fall through to chrome since
 *                                      cores have no substrate/typography
 *                                      vocabulary)
 *
 * Sections are kept INLINE in this file rather than extracted to
 * sub-component files. Rationale: each section is ~40-60 LOC of straight
 * primitive composition with no shared state across sections, and the
 * top-level conditional rendering keeps the selection-driven logic
 * visible in one place. Sub-components would be a refactor without
 * obvious payoff at F-2 scope. (Surfaced in build report.)
 *
 * Per-row inheritance indicators (template chrome only) consume the
 * resolver's `sources.chrome_sources` provenance per C-2.3 pattern,
 * reused verbatim — no adaptation. Substrate + typography rows always
 * render as explicit (cores are substrate/typography-free by design).
 */
import * as React from "react"
import { ArrowLeftRight, Eye } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  ChromePresetPicker,
  PropertyPanel,
  PropertyRow,
  PropertySection,
  ScrubbableButton,
  SubstratePresetPicker,
  TokenSwatchPicker,
  TypographyPresetPicker,
  type PresetSlug,
  type SubstratePresetSlug,
  type TypographyPresetSlug,
} from "@/bridgeable-admin/components/visual-authoring"
import type { PropertyRowInheritance } from "@/bridgeable-admin/components/visual-authoring/PropertyPanel"
import {
  expandPreset,
  mergeChromeWithOverrides,
  chromeViewFromDraft,
} from "@/bridgeable-admin/lib/visual-editor/chrome-resolver"
import {
  expandSubstratePreset,
  substrateViewFromBlob,
  type SubstratePreset,
} from "@/bridgeable-admin/lib/visual-editor/substrate-resolver"
import {
  expandTypographyPreset,
  typographyViewFromBlob,
  type TypographyPreset,
} from "@/bridgeable-admin/lib/visual-editor/typography-resolver"
import type { CoreRecord } from "@/bridgeable-admin/services/focus-cores-service"
import type { ResolveSources } from "@/bridgeable-admin/services/focus-templates-service"
import type { UseFocusCoreDraftResult } from "@/bridgeable-admin/hooks/useFocusCoreDraft"
import type { UseFocusTemplateDraftResult } from "@/bridgeable-admin/hooks/useFocusTemplateDraft"

import { useFocusBuilderSelection } from "./FocusBuilderSelectionContext"
import {
  WidgetInspectorSection,
  findPlacementById,
} from "./WidgetInspectorSection"

export interface FocusBuilderInspectorProps {
  mode: "core" | "template" | "empty"
  /** Live theme tokens (light mode in F-2). */
  themeTokens: Record<string, string>
  /** Hook result when editing a core. */
  coreHook?: UseFocusCoreDraftResult | null
  /** Hook result when editing a template. */
  templateHook?: UseFocusTemplateDraftResult | null
  /** Inherited core (template editing only — used for cascaded chrome view). */
  inheritedCore?: CoreRecord | null
  /** Per-field provenance from the resolver (template editing only). */
  sources?: ResolveSources | null
  /** "View canonical core" button — opens InheritedCoreInspectorPanel. */
  onOpenInheritedCorePanel?: () => void
}

export function FocusBuilderInspector(props: FocusBuilderInspectorProps) {
  const {
    mode,
    themeTokens,
    coreHook,
    templateHook,
    inheritedCore,
    sources,
    onOpenInheritedCorePanel,
  } = props
  const { selection } = useFocusBuilderSelection()

  // Empty state ------------------------------------------------------
  if (mode === "empty" || selection.kind === "none") {
    return (
      <div
        data-testid="focus-builder-inspector-empty"
        className="flex h-full items-center justify-center p-6 text-center text-[12px] text-content-muted"
        style={{ fontFamily: "var(--font-plex-sans)" }}
      >
        <span>
          <ArrowLeftRight className="mx-auto mb-2 h-4 w-4" />
          Click background to edit substrate + typography. Click core to
          edit chrome.
        </span>
      </div>
    )
  }

  // For cores, both 'background' and 'core' selections show chrome
  // editing — cores have no substrate/typography vocabulary, so the
  // background-on-a-core selection falls through to chrome (the only
  // editable surface). Documented in build prompt + report.
  const showChrome =
    selection.kind === "core" ||
    (mode === "core" && selection.kind === "background")
  const showSubstrateAndTypography =
    mode === "template" && selection.kind === "background"

  // ── Core editing ─────────────────────────────────────────────────
  if (mode === "core") {
    if (!coreHook) return null
    return (
      <PropertyPanel data-testid="focus-builder-inspector">
        {onOpenInheritedCorePanel && null}
        <ChromeSection
          // Core editing edits the core's chrome blob directly.
          draftSourceFor="core"
          chromeBlob={coreHook.draft}
          onUpdate={(p) => coreHook.updateDraft(p)}
          themeTokens={themeTokens}
        />
      </PropertyPanel>
    )
  }

  // ── Template editing ──────────────────────────────────────────────
  if (mode === "template") {
    if (!templateHook) return null

    // F-3 — widget selection dispatches to WidgetInspectorSection.
    if (selection.kind === "widget") {
      const placement = findPlacementById(templateHook.rowsDraft, selection.id)
      if (!placement) {
        return (
          <div
            data-testid="focus-builder-inspector-widget-missing"
            className="flex h-full items-center justify-center p-6 text-center text-[12px] text-content-muted"
          >
            Widget no longer exists.
          </div>
        )
      }
      return (
        <WidgetInspectorSection
          placement={placement}
          onUpdateWidget={(id, partial) => templateHook.updateWidget(id, partial)}
          onRemoveWidget={(id) => templateHook.removeWidget(id)}
        />
      )
    }

    return (
      <PropertyPanel data-testid="focus-builder-inspector">
        <InspectorHeader onOpenInheritedCorePanel={onOpenInheritedCorePanel} />

        {showChrome && (
          <ChromeSection
            draftSourceFor="template"
            chromeBlob={templateHook.chromeOverridesDraft}
            inheritedCoreChrome={inheritedCore?.chrome ?? null}
            onUpdate={(p) => templateHook.updateChromeOverrides(p)}
            onReset={(field) => templateHook.resetChromeOverridesField(field)}
            sources={sources}
            themeTokens={themeTokens}
          />
        )}

        {showSubstrateAndTypography && (
          <>
            <SubstrateSection
              substrateBlob={templateHook.substrateDraft}
              onUpdate={(p) => templateHook.updateSubstrate(p)}
              onReset={(field) => templateHook.resetSubstrateField(field)}
              themeTokens={themeTokens}
            />
            <TypographySection
              typographyBlob={templateHook.typographyDraft}
              onUpdate={(p) => templateHook.updateTypography(p)}
              onReset={(field) => templateHook.resetTypographyField(field)}
              themeTokens={themeTokens}
            />
          </>
        )}
      </PropertyPanel>
    )
  }

  return null
}

function InspectorHeader({
  onOpenInheritedCorePanel,
}: {
  onOpenInheritedCorePanel?: () => void
}) {
  if (!onOpenInheritedCorePanel) return null
  return (
    <div
      data-testid="focus-builder-inspector-header"
      className="flex items-center justify-end"
    >
      <Button
        type="button"
        variant="ghost"
        size="sm"
        data-testid="view-canonical-core-button"
        onClick={onOpenInheritedCorePanel}
        className="h-7 gap-1 px-2 text-[11px] text-[color:var(--content-muted)] hover:text-[color:var(--accent)]"
      >
        <Eye className="h-3 w-3" />
        View canonical core
      </Button>
    </div>
  )
}

// ── Chrome section (used by both core + template editing) ────────────

interface ChromeSectionProps {
  /**
   * 'core'     — chrome blob IS the core's chrome (no cascade).
   * 'template' — chrome blob is the template's `chrome_overrides`
   *              cascaded with inheritedCoreChrome.
   */
  draftSourceFor: "core" | "template"
  chromeBlob: Record<string, unknown>
  inheritedCoreChrome?: Record<string, unknown> | null
  onUpdate: (partial: Record<string, unknown>) => void
  /** Per-field reset (template only). */
  onReset?: (field: string) => void
  sources?: ResolveSources | null
  themeTokens: Record<string, string>
}

function ChromeSection({
  draftSourceFor,
  chromeBlob,
  inheritedCoreChrome,
  onUpdate,
  onReset,
  sources,
  themeTokens,
}: ChromeSectionProps) {
  // For core editing, the chrome view is the live core chrome draft
  // (no cascade). For template editing, the chrome view is the
  // cascaded merge of inherited core chrome + template overrides.
  const chromeView = React.useMemo(() => {
    if (draftSourceFor === "core") {
      return expandPreset(chromeViewFromDraft(chromeBlob))
    }
    return expandPreset(
      mergeChromeWithOverrides(inheritedCoreChrome ?? null, chromeBlob),
    )
  }, [draftSourceFor, chromeBlob, inheritedCoreChrome])

  const chromeInheritanceFor = React.useCallback(
    (field: string): PropertyRowInheritance => {
      if (draftSourceFor !== "template") return null
      const tier = sources?.chrome_sources?.[field]
      if (tier === "tier1") return { tier: "Tier 1 core" }
      if (tier === "tier2" || tier === "tier3") return "explicit"
      return null
    },
    [draftSourceFor, sources],
  )

  const reset = React.useCallback(
    (field: string) => onReset?.(field),
    [onReset],
  )

  return (
    <PropertySection title="Chrome" defaultExpanded>
      <PropertyRow
        inheritanceSource={chromeInheritanceFor("preset")}
        onReset={onReset ? () => reset("preset") : undefined}
      >
        <ChromePresetPicker
          value={(chromeView.preset ?? null) as PresetSlug | null}
          onChange={(p) => onUpdate({ preset: p as PresetSlug | null })}
        />
      </PropertyRow>
      <PropertyRow
        inheritanceSource={chromeInheritanceFor("elevation")}
        onReset={onReset ? () => reset("elevation") : undefined}
      >
        <ScrubbableButton
          value={chromeView.elevation ?? 0}
          min={0}
          max={100}
          label="Elevation"
          onChange={(v) => onUpdate({ elevation: v })}
        />
      </PropertyRow>
      <PropertyRow
        inheritanceSource={chromeInheritanceFor("corner_radius")}
        onReset={onReset ? () => reset("corner_radius") : undefined}
      >
        <ScrubbableButton
          value={chromeView.corner_radius ?? 0}
          min={0}
          max={100}
          label="Corner radius"
          onChange={(v) => onUpdate({ corner_radius: v })}
        />
      </PropertyRow>
      <PropertyRow
        inheritanceSource={chromeInheritanceFor("backdrop_blur")}
        onReset={onReset ? () => reset("backdrop_blur") : undefined}
      >
        <ScrubbableButton
          value={chromeView.backdrop_blur ?? 0}
          min={0}
          max={100}
          label="Backdrop blur"
          onChange={(v) => onUpdate({ backdrop_blur: v })}
        />
      </PropertyRow>
      <PropertyRow
        inheritanceSource={chromeInheritanceFor("background_token")}
        onReset={onReset ? () => reset("background_token") : undefined}
      >
        <TokenSwatchPicker
          value={chromeView.background_token ?? null}
          tokenFamily="surface"
          themeTokens={themeTokens}
          onChange={(t) => onUpdate({ background_token: t })}
          label="Background"
        />
      </PropertyRow>
      <PropertyRow
        inheritanceSource={chromeInheritanceFor("border_token")}
        onReset={onReset ? () => reset("border_token") : undefined}
      >
        <TokenSwatchPicker
          value={chromeView.border_token ?? null}
          tokenFamily="border"
          themeTokens={themeTokens}
          onChange={(t) => onUpdate({ border_token: t })}
          label="Border"
        />
      </PropertyRow>
      <PropertyRow
        inheritanceSource={chromeInheritanceFor("padding_token")}
        onReset={onReset ? () => reset("padding_token") : undefined}
      >
        <TokenSwatchPicker
          value={chromeView.padding_token ?? null}
          tokenFamily="padding"
          themeTokens={themeTokens}
          onChange={(t) => onUpdate({ padding_token: t })}
          label="Padding"
        />
      </PropertyRow>
    </PropertySection>
  )
}

// ── Substrate section (template editing only) ────────────────────────

interface SubstrateSectionProps {
  substrateBlob: Record<string, unknown>
  onUpdate: (partial: Record<string, unknown>) => void
  onReset: (field: string) => void
  themeTokens: Record<string, string>
}

function SubstrateSection({
  substrateBlob,
  onUpdate,
  onReset,
  themeTokens,
}: SubstrateSectionProps) {
  const substrateView = React.useMemo(
    () => expandSubstratePreset(substrateViewFromBlob(substrateBlob)),
    [substrateBlob],
  )
  return (
    <PropertySection title="Substrate" defaultExpanded>
      <PropertyRow
        inheritanceSource="explicit"
        onReset={() => onReset("preset")}
      >
        <SubstratePresetPicker
          value={
            (substrateView.preset ?? null) as SubstratePresetSlug | null
          }
          onChange={(p) =>
            onUpdate({ preset: p as SubstratePreset | null })
          }
        />
      </PropertyRow>
      <PropertyRow
        inheritanceSource="explicit"
        onReset={() => onReset("intensity")}
      >
        <ScrubbableButton
          value={substrateView.intensity ?? 0}
          min={0}
          max={100}
          label="Intensity"
          onChange={(v) => onUpdate({ intensity: v })}
        />
      </PropertyRow>
      <PropertyRow
        inheritanceSource="explicit"
        onReset={() => onReset("base_token")}
      >
        <TokenSwatchPicker
          value={substrateView.base_token ?? null}
          tokenFamily="surface"
          themeTokens={themeTokens}
          onChange={(t) => onUpdate({ base_token: t })}
          label="Base"
        />
      </PropertyRow>
      <PropertyRow
        inheritanceSource="explicit"
        onReset={() => onReset("accent_token_1")}
      >
        <TokenSwatchPicker
          value={substrateView.accent_token_1 ?? null}
          tokenFamily="surface"
          themeTokens={themeTokens}
          onChange={(t) => onUpdate({ accent_token_1: t })}
          label="Accent 1"
        />
      </PropertyRow>
      <PropertyRow
        inheritanceSource="explicit"
        onReset={() => onReset("accent_token_2")}
      >
        <TokenSwatchPicker
          value={substrateView.accent_token_2 ?? null}
          tokenFamily="surface"
          themeTokens={themeTokens}
          onChange={(t) => onUpdate({ accent_token_2: t })}
          label="Accent 2"
        />
      </PropertyRow>
    </PropertySection>
  )
}

// ── Typography section (template editing only) ───────────────────────

interface TypographySectionProps {
  typographyBlob: Record<string, unknown>
  onUpdate: (partial: Record<string, unknown>) => void
  onReset: (field: string) => void
  themeTokens: Record<string, string>
}

function TypographySection({
  typographyBlob,
  onUpdate,
  onReset,
  themeTokens,
}: TypographySectionProps) {
  const view = React.useMemo(
    () => expandTypographyPreset(typographyViewFromBlob(typographyBlob)),
    [typographyBlob],
  )
  return (
    <PropertySection title="Typography" defaultExpanded>
      <PropertyRow
        inheritanceSource="explicit"
        onReset={() => onReset("preset")}
      >
        <TypographyPresetPicker
          value={(view.preset ?? null) as TypographyPresetSlug | null}
          onChange={(p) =>
            onUpdate({ preset: p as TypographyPreset | null })
          }
        />
      </PropertyRow>
      <PropertyRow
        inheritanceSource="explicit"
        onReset={() => onReset("heading_weight")}
      >
        <ScrubbableButton
          value={view.heading_weight ?? 400}
          min={400}
          max={900}
          label="Heading weight"
          onChange={(v) => onUpdate({ heading_weight: v })}
        />
      </PropertyRow>
      <PropertyRow
        inheritanceSource="explicit"
        onReset={() => onReset("body_weight")}
      >
        <ScrubbableButton
          value={view.body_weight ?? 400}
          min={400}
          max={900}
          label="Body weight"
          onChange={(v) => onUpdate({ body_weight: v })}
        />
      </PropertyRow>
      <PropertyRow
        inheritanceSource="explicit"
        onReset={() => onReset("heading_color_token")}
      >
        <TokenSwatchPicker
          value={view.heading_color_token ?? null}
          tokenFamily="surface"
          themeTokens={themeTokens}
          onChange={(t) => onUpdate({ heading_color_token: t })}
          label="Heading color"
        />
      </PropertyRow>
      <PropertyRow
        inheritanceSource="explicit"
        onReset={() => onReset("body_color_token")}
      >
        <TokenSwatchPicker
          value={view.body_color_token ?? null}
          tokenFamily="surface"
          themeTokens={themeTokens}
          onChange={(t) => onUpdate({ body_color_token: t })}
          label="Body color"
        />
      </PropertyRow>
    </PropertySection>
  )
}

export default FocusBuilderInspector
