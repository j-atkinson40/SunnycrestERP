/**
 * PersonalizationStudioTuneModePanel — Workshop Tune mode chrome per
 * Phase 1D + DESIGN_LANGUAGE §14.14.2 visual canon.
 *
 * Operator-facing surface for per-tenant Tune mode configuration
 * within the canonical 4-options vocabulary per §3.26.11.12.19.2:
 *
 * 1. Display label customization — per-canonical-option-type label
 *    override (Wilbert: "Life's Reflections" for vinyl; Sunnycrest:
 *    "Vinyl"; default elsewhere).
 * 2. Emblem catalog selection — subset of canonical-default emblem
 *    catalog.
 * 3. Font catalog selection — subset of canonical-default font catalog.
 * 4. Legacy print catalog selection — subset of canonical-default
 *    Wilbert legacy print catalog.
 *
 * Pattern-establisher discipline: Step 2 (Urn Vault Personalization
 * Studio) reuses this chrome via ``templateType`` prop dispatch; the
 * service-layer registry surfaces per-template Tune mode dimensions
 * + canonical-default catalogs without chrome forks.
 *
 * Anti-pattern guards:
 * - §2.4.4 Anti-pattern 9 — chrome enforces canonical 4-options
 *   vocabulary at display-label dimension; backend service rejects
 *   violations with HTTP 422.
 * - §3.26.11.12.16 Anti-pattern 1 (auto-commit on extraction
 *   confidence rejected) does NOT apply here — Tune mode is
 *   explicit operator authoring, not AI extraction. Operator-decision
 *   discipline ships as Save/Reset buttons.
 */

import { Loader2, RotateCcw, Save } from "lucide-react"
import { useCallback, useEffect, useState } from "react"
import type { ChangeEvent } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import {
  getTenantPersonalizationConfig,
  updateTenantPersonalizationConfig,
} from "@/services/workshop-service"
import type { CanonicalOptionType } from "@/types/personalization-studio"
import { CANONICAL_OPTION_TYPES } from "@/types/personalization-studio"
import type {
  TenantPersonalizationConfig,
  TenantPersonalizationConfigUpdate,
  WorkshopTemplateType,
} from "@/types/workshop"

export interface PersonalizationStudioTuneModePanelProps {
  templateType: WorkshopTemplateType
}

export function PersonalizationStudioTuneModePanel({
  templateType,
}: PersonalizationStudioTuneModePanelProps) {
  const [config, setConfig] = useState<TenantPersonalizationConfig | null>(null)
  const [draft, setDraft] = useState<TenantPersonalizationConfigUpdate>({})
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadConfig = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const next = await getTenantPersonalizationConfig(templateType)
      setConfig(next)
      setDraft({})
    } catch (err) {
      setError(extractErrorMessage(err) ?? "Failed to load tune mode config")
    } finally {
      setIsLoading(false)
    }
  }, [templateType])

  useEffect(() => {
    void loadConfig()
  }, [loadConfig])

  const handleSave = useCallback(async () => {
    if (Object.keys(draft).length === 0) return
    setIsSaving(true)
    setError(null)
    try {
      const next = await updateTenantPersonalizationConfig(templateType, draft)
      setConfig(next)
      setDraft({})
    } catch (err) {
      setError(extractErrorMessage(err) ?? "Failed to save tune mode config")
    } finally {
      setIsSaving(false)
    }
  }, [draft, templateType])

  const handleResetDraft = useCallback(() => {
    setDraft({})
    setError(null)
  }, [])

  const isDirty = Object.keys(draft).length > 0

  if (isLoading || !config) {
    return (
      <div
        data-slot="tune-mode-panel-loading"
        className="flex items-center gap-2 rounded-md border border-border-subtle bg-surface-elevated p-4 text-body-sm text-content-muted"
      >
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading tune mode configuration…
      </div>
    )
  }

  return (
    <div
      data-slot="personalization-studio-tune-mode-panel"
      data-template-type={templateType}
      data-dirty={isDirty ? "true" : "false"}
      className="flex flex-col gap-4 rounded-md border border-border-subtle bg-surface-elevated p-5 shadow-level-1"
    >
      <header className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-h3 font-plex-serif text-content-strong">
            Tune mode — Burial Vault Personalization Studio
          </h2>
          <p className="text-body-sm text-content-muted">
            Override display labels and select catalog subsets within the
            canonical 4-options vocabulary. Adding new option types or
            catalog entries requires a Workshop template-version bump.
          </p>
        </div>
        {error && (
          <div
            data-slot="tune-mode-panel-error"
            className="rounded-sm bg-status-error-muted px-3 py-1 text-caption text-status-error"
          >
            {error}
          </div>
        )}
      </header>

      <DisplayLabelsSection
        config={config}
        draft={draft}
        onChange={(display_labels) =>
          setDraft((prev) => ({ ...prev, display_labels }))
        }
      />

      <CatalogSection
        title="Emblem catalog"
        description="Emblems available within physical_emblem and vinyl options."
        slot="emblem-catalog"
        canonicalDefault={config.defaults.emblem_catalog}
        currentValue={
          draft.emblem_catalog ?? config.emblem_catalog
        }
        onChange={(emblem_catalog) =>
          setDraft((prev) => ({ ...prev, emblem_catalog }))
        }
      />

      <CatalogSection
        title="Font catalog"
        description="Fonts available within physical_nameplate option."
        slot="font-catalog"
        canonicalDefault={config.defaults.font_catalog}
        currentValue={draft.font_catalog ?? config.font_catalog}
        onChange={(font_catalog) =>
          setDraft((prev) => ({ ...prev, font_catalog }))
        }
      />

      <CatalogSection
        title="Legacy print catalog"
        description="Wilbert legacy prints available within legacy_print option."
        slot="legacy-print-catalog"
        canonicalDefault={config.defaults.legacy_print_catalog}
        currentValue={
          draft.legacy_print_catalog ?? config.legacy_print_catalog
        }
        onChange={(legacy_print_catalog) =>
          setDraft((prev) => ({ ...prev, legacy_print_catalog }))
        }
      />

      <footer className="flex items-center justify-end gap-2 border-t border-border-subtle pt-3">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleResetDraft}
          disabled={!isDirty || isSaving}
          data-slot="tune-mode-panel-reset"
        >
          <RotateCcw className="mr-1 h-3 w-3" />
          Discard changes
        </Button>
        <Button
          type="button"
          variant="default"
          size="sm"
          onClick={handleSave}
          disabled={!isDirty || isSaving}
          data-slot="tune-mode-panel-save"
        >
          {isSaving ? (
            <>
              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
              Saving…
            </>
          ) : (
            <>
              <Save className="mr-1 h-3 w-3" />
              Save changes
            </>
          )}
        </Button>
      </footer>
    </div>
  )
}


// ─────────────────────────────────────────────────────────────────────
// Display labels section — per-canonical-option-type label override
// ─────────────────────────────────────────────────────────────────────


function DisplayLabelsSection({
  config,
  draft,
  onChange,
}: {
  config: TenantPersonalizationConfig
  draft: TenantPersonalizationConfigUpdate
  onChange: (
    next: Partial<Record<CanonicalOptionType, string>>,
  ) => void
}) {
  const overrides = draft.display_labels ?? {}
  const handleFieldChange = (
    optionType: CanonicalOptionType,
    value: string,
  ) => {
    const next: Partial<Record<CanonicalOptionType, string>> = {
      ...overrides,
    }
    if (value === "" || value === config.defaults.display_labels[optionType]) {
      delete next[optionType]
    } else {
      next[optionType] = value
    }
    onChange(next)
  }

  return (
    <section
      data-slot="tune-mode-section"
      data-section="display-labels"
      className="flex flex-col gap-2"
    >
      <header>
        <h3 className="text-caption font-medium uppercase tracking-wider text-content-muted">
          Display labels
        </h3>
        <p className="text-body-sm text-content-muted">
          Override how each canonical option type displays in operator
          chrome. The canonical substrate value never changes — only
          the rendered label.
        </p>
      </header>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {CANONICAL_OPTION_TYPES.map((optionType) => {
          const defaultLabel = config.defaults.display_labels[optionType]
          const current =
            overrides[optionType] ??
            config.display_labels[optionType] ??
            defaultLabel
          const isOverridden = current !== defaultLabel
          return (
            <label
              key={optionType}
              data-slot="display-label-field"
              data-option-type={optionType}
              data-overridden={isOverridden ? "true" : "false"}
              className="flex flex-col gap-1"
            >
              <span className="text-caption font-plex-mono text-content-muted">
                {optionType}
                {isOverridden && (
                  <span className="ml-2 rounded-sm bg-accent-subtle px-1.5 py-0.5 text-caption text-accent">
                    custom
                  </span>
                )}
              </span>
              <Input
                value={current}
                placeholder={defaultLabel}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  handleFieldChange(optionType, e.target.value)
                }
                data-slot="display-label-input"
              />
            </label>
          )
        })}
      </div>
    </section>
  )
}


// ─────────────────────────────────────────────────────────────────────
// Catalog section — emblem / font / legacy_print subset selection
// ─────────────────────────────────────────────────────────────────────


function CatalogSection({
  title,
  description,
  slot,
  canonicalDefault,
  currentValue,
  onChange,
}: {
  title: string
  description: string
  slot: string
  canonicalDefault: string[]
  currentValue: string[]
  onChange: (next: string[]) => void
}) {
  const selected = new Set(currentValue)

  const toggleEntry = (entry: string) => {
    const next = selected.has(entry)
      ? currentValue.filter((v) => v !== entry)
      : [...currentValue, entry]
    onChange(next)
  }

  const selectAll = () => onChange([...canonicalDefault])
  const selectNone = () => onChange([])

  return (
    <section
      data-slot="tune-mode-section"
      data-section={slot}
      className="flex flex-col gap-2"
    >
      <header className="flex items-baseline justify-between gap-2">
        <div>
          <h3 className="text-caption font-medium uppercase tracking-wider text-content-muted">
            {title}
          </h3>
          <p className="text-body-sm text-content-muted">{description}</p>
        </div>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={selectAll}
            data-slot={`${slot}-select-all`}
          >
            Select all
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={selectNone}
            data-slot={`${slot}-select-none`}
          >
            Select none
          </Button>
        </div>
      </header>
      <div
        data-slot={`${slot}-options`}
        className="flex flex-wrap gap-1.5 rounded-sm border border-border-subtle bg-surface-base p-3"
      >
        {canonicalDefault.map((entry) => {
          const active = selected.has(entry)
          return (
            <button
              key={entry}
              type="button"
              onClick={() => toggleEntry(entry)}
              data-slot={`${slot}-entry`}
              data-entry-key={entry}
              data-active={active ? "true" : "false"}
              className={cn(
                "rounded-sm px-2 py-1 text-caption transition-colors",
                active
                  ? "bg-accent-subtle text-content-strong border border-accent"
                  : "border border-border-base bg-surface-elevated text-content-muted hover:bg-surface-raised",
              )}
            >
              {entry}
            </button>
          )
        })}
      </div>
      <div
        className="text-caption text-content-muted"
        data-slot={`${slot}-summary`}
      >
        {currentValue.length} of {canonicalDefault.length} selected
        {currentValue.length === 0 && (
          <span className="ml-1 italic">
            (resets to canonical default at read time)
          </span>
        )}
      </div>
    </section>
  )
}


function extractErrorMessage(err: unknown): string | null {
  if (typeof err === "object" && err !== null) {
    const e = err as { response?: { data?: { detail?: string } }; message?: string }
    return e.response?.data?.detail ?? e.message ?? null
  }
  return null
}
