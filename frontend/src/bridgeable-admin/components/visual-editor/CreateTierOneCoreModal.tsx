/**
 * CreateTierOneCoreModal — sub-arc C-2.1.
 *
 * The deliberate-authoring moment when an operator creates a new
 * Tier 1 Focus Core. Less frequent than Tier 2 template creation
 * (Tier 1 cores are added when a new React component lands and
 * needs a canonical chrome default); accordingly the form is
 * weighted toward intentionality rather than speed.
 *
 *   ─ Bind to registered component (filtered to focus-template kind)
 *   ─ core_slug (immutable post-create; lowercase alphanumeric + hyphens)
 *   ─ display_name
 *   ─ description (optional)
 *   ─ default geometry: starting_column / column_span / row_index /
 *     min_column_span / max_column_span
 *
 * Validation:
 *   - slug pattern: ^[a-z0-9][a-z0-9-]*$ (max 96 chars)
 *   - min_column_span ≤ default_column_span ≤ max_column_span
 *   - default_starting_column + default_column_span ≤ 12
 *
 * Posts to /api/platform/admin/focus-template-inheritance/cores.
 * 201 → onCreated(record.id); 422 → field-level inline errors.
 */
import * as React from "react"

import { Button } from "@/components/ui/button"
import {
  focusCoresService,
  type CoreRecord,
} from "@/bridgeable-admin/services/focus-cores-service"
import { getAllRegistered } from "@/lib/visual-editor/registry"

export interface CreateTierOneCoreModalProps {
  open: boolean
  onClose: () => void
  onCreated: (record: CoreRecord) => void
}

interface FormState {
  registered_component_name: string
  core_slug: string
  display_name: string
  description: string
  default_starting_column: number
  default_column_span: number
  default_row_index: number
  min_column_span: number
  max_column_span: number
}

const DEFAULT_FORM: FormState = {
  registered_component_name: "",
  core_slug: "",
  display_name: "",
  description: "",
  default_starting_column: 0,
  default_column_span: 12,
  default_row_index: 0,
  min_column_span: 6,
  max_column_span: 12,
}

const SLUG_PATTERN = /^[a-z0-9][a-z0-9-]*$/

interface FieldErrors {
  registered_component_name?: string
  core_slug?: string
  display_name?: string
  default_starting_column?: string
  default_column_span?: string
  default_row_index?: string
  min_column_span?: string
  max_column_span?: string
  _form?: string
}

function validate(form: FormState): FieldErrors {
  const errs: FieldErrors = {}
  if (!form.registered_component_name.trim()) {
    errs.registered_component_name = "Select a registered component"
  }
  if (!form.core_slug.trim()) {
    errs.core_slug = "Slug is required"
  } else if (!SLUG_PATTERN.test(form.core_slug.trim())) {
    errs.core_slug =
      "Slug must be lowercase alphanumeric + hyphens, starting with letter or digit"
  } else if (form.core_slug.length > 96) {
    errs.core_slug = "Slug must be ≤ 96 characters"
  }
  if (!form.display_name.trim()) {
    errs.display_name = "Display name is required"
  }
  if (form.min_column_span > form.default_column_span) {
    errs.min_column_span = "Must be ≤ default span"
  }
  if (form.default_column_span > form.max_column_span) {
    errs.default_column_span = "Must be ≤ max span"
  }
  if (form.default_starting_column + form.default_column_span > 12) {
    errs.default_starting_column =
      "Starting column + span must be ≤ 12"
  }
  if (form.default_starting_column < 0 || form.default_starting_column > 11) {
    errs.default_starting_column = "Starting column must be 0–11"
  }
  if (form.default_column_span < 1 || form.default_column_span > 12) {
    errs.default_column_span = "Span must be 1–12"
  }
  if (form.min_column_span < 1 || form.min_column_span > 12) {
    errs.min_column_span = "Min span must be 1–12"
  }
  if (form.max_column_span < 1 || form.max_column_span > 12) {
    errs.max_column_span = "Max span must be 1–12"
  }
  return errs
}

export function CreateTierOneCoreModal({
  open,
  onClose,
  onCreated,
}: CreateTierOneCoreModalProps) {
  const [form, setForm] = React.useState<FormState>(DEFAULT_FORM)
  const [errors, setErrors] = React.useState<FieldErrors>({})
  const [submitting, setSubmitting] = React.useState(false)

  // Filter registry to focus-template kind (Tier 1 cores bind to
  // a focus-template-kind React component per the inheritance arc
  // architecture). The registry is mutated only at module-load via
  // auto-register's side-effect import; safe to read once per render.
  const registeredComponents = React.useMemo(() => {
    return getAllRegistered()
      .filter((entry) => entry.metadata.type === "focus-template")
      .sort((a, b) => a.metadata.displayName.localeCompare(b.metadata.displayName))
  }, [])

  React.useEffect(() => {
    // Reset form when the modal opens fresh.
    if (open) {
      setForm(DEFAULT_FORM)
      setErrors({})
      setSubmitting(false)
    }
  }, [open])

  React.useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onClose()
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [open, onClose, submitting])

  if (!open) return null

  function updateField<K extends keyof FormState>(
    key: K,
    value: FormState[K],
  ) {
    setForm((prev) => ({ ...prev, [key]: value }))
    if (errors[key as keyof FieldErrors]) {
      setErrors((prev) => {
        const next = { ...prev }
        delete next[key as keyof FieldErrors]
        return next
      })
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const v = validate(form)
    if (Object.keys(v).length > 0) {
      setErrors(v)
      return
    }
    setSubmitting(true)
    setErrors({})
    try {
      const created = await focusCoresService.create({
        core_slug: form.core_slug.trim(),
        display_name: form.display_name.trim(),
        description: form.description.trim() || null,
        registered_component_kind: "focus-template",
        registered_component_name: form.registered_component_name,
        default_starting_column: form.default_starting_column,
        default_column_span: form.default_column_span,
        default_row_index: form.default_row_index,
        min_column_span: form.min_column_span,
        max_column_span: form.max_column_span,
        chrome: {},
      })
      onCreated(created)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to create core"
      // Slug collision sentinel — 409 / 422 typically carries a
      // duplicate-slug message. Surface as a slug-field error.
      if (/slug/i.test(message) || /already/i.test(message)) {
        setErrors({ core_slug: "Slug already exists; choose another" })
      } else {
        setErrors({ _form: message })
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      data-testid="create-tier-one-core-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-tier-one-core-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-[color:var(--shadow-color-strong,rgba(48,32,16,0.40))]"
      onClick={(e) => {
        if (e.target === e.currentTarget && !submitting) onClose()
      }}
    >
      <form
        onSubmit={handleSubmit}
        className="flex w-[480px] max-w-[90vw] flex-col gap-4 rounded-lg border border-[color:var(--border-subtle)] bg-[color:var(--surface-elevated)] p-6 shadow-[var(--shadow-level-2)]"
        style={{ fontFamily: "var(--font-plex-sans)" }}
      >
        <header className="flex flex-col gap-1">
          <h2
            id="create-tier-one-core-title"
            className="text-[16px] font-medium text-[color:var(--content-strong)]"
          >
            New Focus Core (Tier 1)
          </h2>
          <p className="text-[12px] text-[color:var(--content-muted)]">
            Bind a registered React component to a canonical chrome
            default. The slug is permanent once created.
          </p>
        </header>

        {errors._form && (
          <div
            role="alert"
            data-testid="create-tier-one-core-error"
            className="rounded-md border border-[color:var(--status-error)] bg-[color:var(--status-error-muted)] px-3 py-2 text-[12px] text-[color:var(--status-error)]"
          >
            {errors._form}
          </div>
        )}

        <label className="flex flex-col gap-1.5">
          <span className="text-[12px] font-medium text-[color:var(--content-base)]">
            Registered component
          </span>
          <select
            data-testid="registered-component-select"
            value={form.registered_component_name}
            onChange={(e) => updateField("registered_component_name", e.target.value)}
            className="rounded-md border border-[color:var(--border-base)] bg-[color:var(--surface-raised)] px-2 py-1.5 text-[13px] text-[color:var(--content-strong)]"
          >
            <option value="">— select a component —</option>
            {registeredComponents.map((entry) => (
              <option key={entry.metadata.name} value={entry.metadata.name}>
                {entry.metadata.displayName} ({entry.metadata.name})
              </option>
            ))}
          </select>
          {errors.registered_component_name && (
            <span className="text-[11px] text-[color:var(--status-error)]">
              {errors.registered_component_name}
            </span>
          )}
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-[12px] font-medium text-[color:var(--content-base)]">
            Slug
          </span>
          <input
            data-testid="core-slug-input"
            value={form.core_slug}
            onChange={(e) => updateField("core_slug", e.target.value)}
            placeholder="scheduling-kanban-core"
            className="rounded-md border border-[color:var(--border-base)] bg-[color:var(--surface-raised)] px-2 py-1.5 text-[13px] text-[color:var(--content-strong)] font-mono"
          />
          {errors.core_slug && (
            <span
              data-testid="core-slug-error"
              className="text-[11px] text-[color:var(--status-error)]"
            >
              {errors.core_slug}
            </span>
          )}
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-[12px] font-medium text-[color:var(--content-base)]">
            Display name
          </span>
          <input
            data-testid="display-name-input"
            value={form.display_name}
            onChange={(e) => updateField("display_name", e.target.value)}
            placeholder="Scheduling Kanban Core"
            className="rounded-md border border-[color:var(--border-base)] bg-[color:var(--surface-raised)] px-2 py-1.5 text-[13px] text-[color:var(--content-strong)]"
          />
          {errors.display_name && (
            <span className="text-[11px] text-[color:var(--status-error)]">
              {errors.display_name}
            </span>
          )}
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-[12px] font-medium text-[color:var(--content-base)]">
            Description (optional)
          </span>
          <textarea
            data-testid="description-input"
            value={form.description}
            onChange={(e) => updateField("description", e.target.value)}
            rows={2}
            className="resize-none rounded-md border border-[color:var(--border-base)] bg-[color:var(--surface-raised)] px-2 py-1.5 text-[13px] text-[color:var(--content-strong)]"
          />
        </label>

        <fieldset className="grid grid-cols-2 gap-3 rounded-md border border-[color:var(--border-subtle)] p-3">
          <legend className="px-1.5 text-[11px] font-medium uppercase tracking-wide text-[color:var(--content-muted)]">
            Default geometry
          </legend>
          <NumField
            label="Start column"
            testId="start-column-input"
            value={form.default_starting_column}
            onChange={(v) => updateField("default_starting_column", v)}
            error={errors.default_starting_column}
            min={0}
            max={11}
          />
          <NumField
            label="Column span"
            testId="column-span-input"
            value={form.default_column_span}
            onChange={(v) => updateField("default_column_span", v)}
            error={errors.default_column_span}
            min={1}
            max={12}
          />
          <NumField
            label="Row index"
            testId="row-index-input"
            value={form.default_row_index}
            onChange={(v) => updateField("default_row_index", v)}
            error={errors.default_row_index}
            min={0}
            max={50}
          />
          <NumField
            label="Min span"
            testId="min-span-input"
            value={form.min_column_span}
            onChange={(v) => updateField("min_column_span", v)}
            error={errors.min_column_span}
            min={1}
            max={12}
          />
          <NumField
            label="Max span"
            testId="max-span-input"
            value={form.max_column_span}
            onChange={(v) => updateField("max_column_span", v)}
            error={errors.max_column_span}
            min={1}
            max={12}
          />
        </fieldset>

        <footer className="flex justify-end gap-2 pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={submitting}
            data-testid="create-tier-one-core-cancel"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={submitting}
            data-testid="create-tier-one-core-submit"
          >
            {submitting ? "Creating…" : "Create"}
          </Button>
        </footer>
      </form>
    </div>
  )
}

interface NumFieldProps {
  label: string
  value: number
  onChange: (v: number) => void
  error?: string
  testId?: string
  min?: number
  max?: number
}

function NumField({
  label,
  value,
  onChange,
  error,
  testId,
  min,
  max,
}: NumFieldProps) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] font-medium text-[color:var(--content-muted)]">
        {label}
      </span>
      <input
        type="number"
        data-testid={testId}
        value={value}
        min={min}
        max={max}
        onChange={(e) => onChange(Number.parseInt(e.target.value || "0", 10) || 0)}
        className="rounded-md border border-[color:var(--border-base)] bg-[color:var(--surface-raised)] px-2 py-1 text-[13px] tabular-nums text-[color:var(--content-strong)] font-mono"
      />
      {error && (
        <span className="text-[11px] text-[color:var(--status-error)]">
          {error}
        </span>
      )}
    </label>
  )
}

export default CreateTierOneCoreModal
