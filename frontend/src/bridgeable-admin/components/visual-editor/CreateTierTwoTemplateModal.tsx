/**
 * CreateTierTwoTemplateModal — sub-arc C-2.2c.
 *
 * The deliberate-authoring moment when an operator creates a new
 * Tier 2 Focus Template by selecting a Tier 1 core to inherit from.
 * Mirrors the structure of CreateTierOneCoreModal — the modal is
 * weighted toward intentionality (slug is permanent, vertical scope
 * is a deliberate choice) rather than speed.
 *
 *   ─ Inherit from core (dropdown of active Tier 1 cores; required)
 *   ─ template_slug (immutable post-create; lowercase alphanumeric + hyphens)
 *   ─ display_name
 *   ─ description (optional)
 *   ─ Scope: Platform default | Vertical default
 *   ─ Vertical dropdown (shown only when scope=vertical_default;
 *     defaults to Studio's current vertical if provided)
 *
 * Validation:
 *   - slug pattern: ^[a-z0-9][a-z0-9-]*$ (max 96 chars)
 *   - core must be selected
 *   - display_name required
 *   - when scope=vertical_default, vertical must be selected
 *
 * Posts to /api/platform/admin/focus-template-inheritance/templates.
 * On 201 → onCreated(record); modal closes, parent updates URL
 * (?tier=2&template=<id>). On 422 slug collision → field-level
 * inline error. On other 5xx → form-level error banner; preserve
 * form state so the operator can retry.
 */
import * as React from "react"

import { Button } from "@/components/ui/button"
import {
  focusTemplatesService,
  type TemplateRecord,
  type TemplateScope,
} from "@/bridgeable-admin/services/focus-templates-service"
import {
  focusCoresService,
  type CoreRecord,
} from "@/bridgeable-admin/services/focus-cores-service"
import {
  verticalsService,
  type Vertical,
} from "@/bridgeable-admin/services/verticals-service"

export interface CreateTierTwoTemplateModalProps {
  open: boolean
  onClose: () => void
  onCreated: (record: TemplateRecord) => void
  /**
   * Studio's currently-active vertical slug, if any. When provided +
   * scope=vertical_default, the vertical dropdown pre-selects this
   * value. Operator may still override. Null = no Studio scope hint
   * (Platform default is the natural starting choice).
   */
  defaultVertical?: string | null
}

interface FormState {
  inherits_from_core_id: string
  template_slug: string
  display_name: string
  description: string
  scope: TemplateScope
  vertical: string
}

const SLUG_PATTERN = /^[a-z0-9][a-z0-9-]*$/

interface FieldErrors {
  inherits_from_core_id?: string
  template_slug?: string
  display_name?: string
  vertical?: string
  _form?: string
}

function buildDefaultForm(defaultVertical: string | null | undefined): FormState {
  // If the Studio scope is a real vertical, default to vertical_default
  // + that vertical pre-selected. Otherwise default to platform_default.
  const hasVertical = !!defaultVertical && defaultVertical.length > 0
  return {
    inherits_from_core_id: "",
    template_slug: "",
    display_name: "",
    description: "",
    scope: hasVertical ? "vertical_default" : "platform_default",
    vertical: hasVertical ? (defaultVertical as string) : "",
  }
}

function validate(form: FormState): FieldErrors {
  const errs: FieldErrors = {}
  if (!form.inherits_from_core_id.trim()) {
    errs.inherits_from_core_id = "Select a Tier 1 core to inherit from"
  }
  if (!form.template_slug.trim()) {
    errs.template_slug = "Slug is required"
  } else if (!SLUG_PATTERN.test(form.template_slug.trim())) {
    errs.template_slug =
      "Slug must be lowercase alphanumeric + hyphens, starting with letter or digit"
  } else if (form.template_slug.length > 96) {
    errs.template_slug = "Slug must be ≤ 96 characters"
  }
  if (!form.display_name.trim()) {
    errs.display_name = "Display name is required"
  }
  if (form.scope === "vertical_default" && !form.vertical.trim()) {
    errs.vertical = "Select a vertical"
  }
  return errs
}

export function CreateTierTwoTemplateModal({
  open,
  onClose,
  onCreated,
  defaultVertical,
}: CreateTierTwoTemplateModalProps) {
  const [form, setForm] = React.useState<FormState>(() =>
    buildDefaultForm(defaultVertical),
  )
  const [errors, setErrors] = React.useState<FieldErrors>({})
  const [submitting, setSubmitting] = React.useState(false)

  const [cores, setCores] = React.useState<CoreRecord[]>([])
  const [verticals, setVerticals] = React.useState<Vertical[]>([])

  // Reset form + reload registries when the modal opens.
  React.useEffect(() => {
    if (!open) return
    setForm(buildDefaultForm(defaultVertical))
    setErrors({})
    setSubmitting(false)
    let cancelled = false

    // Fetch active Tier 1 cores. The list endpoint returns active
    // rows by default per backend spec.
    focusCoresService
      .list()
      .then((rows) => {
        if (cancelled) return
        setCores(
          rows
            .filter((c) => c.is_active !== false)
            .sort((a, b) =>
              a.display_name.localeCompare(b.display_name),
            ),
        )
      })
      .catch(() => {
        if (!cancelled) setCores([])
      })

    // Fetch published verticals for the dropdown.
    verticalsService
      .list()
      .then((rows) => {
        if (cancelled) return
        setVerticals(
          rows
            .filter((v) => v.status === "published")
            .sort((a, b) =>
              a.display_name.localeCompare(b.display_name),
            ),
        )
      })
      .catch(() => {
        if (!cancelled) setVerticals([])
      })

    return () => {
      cancelled = true
    }
  }, [open, defaultVertical])

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
      const created = await focusTemplatesService.create({
        scope: form.scope,
        vertical: form.scope === "vertical_default" ? form.vertical : null,
        template_slug: form.template_slug.trim(),
        display_name: form.display_name.trim(),
        description: form.description.trim() || null,
        inherits_from_core_id: form.inherits_from_core_id,
        // Explicit empty defaults — backend accepts them and they
        // make the cascade-from-core intent visible at create time.
        chrome_overrides: {},
        substrate: {},
        typography: {},
      })
      onCreated(created)
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to create template"
      if (/slug/i.test(message) || /already/i.test(message)) {
        setErrors({
          template_slug: "Slug already exists; choose another",
        })
      } else {
        setErrors({ _form: message })
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      data-testid="create-tier-two-template-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-tier-two-template-title"
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
            id="create-tier-two-template-title"
            className="text-[16px] font-medium text-[color:var(--content-strong)]"
          >
            New Focus Template (Tier 2)
          </h2>
          <p className="text-[12px] text-[color:var(--content-muted)]">
            Pick a Tier 1 core to inherit chrome from. Substrate +
            typography start empty (cascade-from-core); customize them
            once the template opens.
          </p>
        </header>

        {errors._form && (
          <div
            role="alert"
            data-testid="create-tier-two-template-error"
            className="rounded-md border border-[color:var(--status-error)] bg-[color:var(--status-error-muted)] px-3 py-2 text-[12px] text-[color:var(--status-error)]"
          >
            {errors._form}
          </div>
        )}

        <label className="flex flex-col gap-1.5">
          <span className="text-[12px] font-medium text-[color:var(--content-base)]">
            Inherit from core
          </span>
          <select
            data-testid="inherits-from-core-select"
            value={form.inherits_from_core_id}
            onChange={(e) =>
              updateField("inherits_from_core_id", e.target.value)
            }
            className="rounded-md border border-[color:var(--border-base)] bg-[color:var(--surface-raised)] px-2 py-1.5 text-[13px] text-[color:var(--content-strong)]"
          >
            <option value="">— select a Tier 1 core —</option>
            {cores.map((core) => (
              <option key={core.id} value={core.id}>
                {core.display_name} ({core.core_slug}) v{core.version}
              </option>
            ))}
          </select>
          {errors.inherits_from_core_id && (
            <span
              data-testid="inherits-from-core-error"
              className="text-[11px] text-[color:var(--status-error)]"
            >
              {errors.inherits_from_core_id}
            </span>
          )}
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-[12px] font-medium text-[color:var(--content-base)]">
            Slug
          </span>
          <input
            data-testid="template-slug-input"
            value={form.template_slug}
            onChange={(e) => updateField("template_slug", e.target.value)}
            placeholder="frosted-scribe"
            className="rounded-md border border-[color:var(--border-base)] bg-[color:var(--surface-raised)] px-2 py-1.5 text-[13px] text-[color:var(--content-strong)] font-mono"
          />
          {errors.template_slug && (
            <span
              data-testid="template-slug-error"
              className="text-[11px] text-[color:var(--status-error)]"
            >
              {errors.template_slug}
            </span>
          )}
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-[12px] font-medium text-[color:var(--content-base)]">
            Display name
          </span>
          <input
            data-testid="template-display-name-input"
            value={form.display_name}
            onChange={(e) => updateField("display_name", e.target.value)}
            placeholder="Frosted Scribe"
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
            data-testid="template-description-input"
            value={form.description}
            onChange={(e) => updateField("description", e.target.value)}
            rows={2}
            className="resize-none rounded-md border border-[color:var(--border-base)] bg-[color:var(--surface-raised)] px-2 py-1.5 text-[13px] text-[color:var(--content-strong)]"
          />
        </label>

        <fieldset
          className="flex flex-col gap-2 rounded-md border border-[color:var(--border-subtle)] p-3"
          data-testid="template-scope-fieldset"
        >
          <legend className="px-1.5 text-[11px] font-medium uppercase tracking-wide text-[color:var(--content-muted)]">
            Scope
          </legend>
          <label className="flex items-center gap-2 text-[12px] text-[color:var(--content-base)]">
            <input
              type="radio"
              data-testid="scope-platform-default"
              name="scope"
              value="platform_default"
              checked={form.scope === "platform_default"}
              onChange={() => updateField("scope", "platform_default")}
            />
            Platform default
          </label>
          <label className="flex items-center gap-2 text-[12px] text-[color:var(--content-base)]">
            <input
              type="radio"
              data-testid="scope-vertical-default"
              name="scope"
              value="vertical_default"
              checked={form.scope === "vertical_default"}
              onChange={() => updateField("scope", "vertical_default")}
            />
            Vertical default
          </label>
          {form.scope === "vertical_default" && (
            <label className="mt-1 flex flex-col gap-1">
              <span className="text-[11px] font-medium text-[color:var(--content-muted)]">
                Vertical
              </span>
              <select
                data-testid="template-vertical-select"
                value={form.vertical}
                onChange={(e) => updateField("vertical", e.target.value)}
                className="rounded-md border border-[color:var(--border-base)] bg-[color:var(--surface-raised)] px-2 py-1 text-[12px] text-[color:var(--content-strong)]"
              >
                <option value="">— select a vertical —</option>
                {verticals.map((v) => (
                  <option key={v.slug} value={v.slug}>
                    {v.display_name} ({v.slug})
                  </option>
                ))}
              </select>
              {errors.vertical && (
                <span
                  data-testid="template-vertical-error"
                  className="text-[11px] text-[color:var(--status-error)]"
                >
                  {errors.vertical}
                </span>
              )}
            </label>
          )}
        </fieldset>

        <footer className="flex justify-end gap-2 pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={onClose}
            disabled={submitting}
            data-testid="create-tier-two-template-cancel"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={submitting}
            data-testid="create-tier-two-template-submit"
          >
            {submitting ? "Creating…" : "Create"}
          </Button>
        </footer>
      </form>
    </div>
  )
}

export default CreateTierTwoTemplateModal
