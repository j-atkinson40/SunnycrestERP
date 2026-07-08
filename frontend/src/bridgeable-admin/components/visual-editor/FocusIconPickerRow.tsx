/**
 * Focus family icon picker (r122) — the Tier 1 core's Identity control.
 *
 * IMMEDIATE-COMMIT (separate from the chrome draft's debounced auto-save):
 * the icon is family identity, not versioned content — a click saves and
 * the change reaches every variation everywhere at once, deliberately.
 * A save without a session token version-bumps (new row id); the caller
 * follows the id via onSaved.
 *
 * DISTINCTNESS GUARD: choosing an icon another active core already wears
 * WARNS (never blocks) — the whole point is at-a-glance family
 * distinction, but the operator stays in charge.
 */

import * as React from "react"
import { toast } from "sonner"

import {
  FOCUS_ICON_NAMES,
  focusIcon,
} from "@/bridgeable-admin/lib/focus-icons"
import {
  focusCoresService,
  type CoreRecord,
} from "@/bridgeable-admin/services/focus-cores-service"

export function FocusIconPickerRow({
  coreId,
  cores,
  currentIcon,
  onSaved,
}: {
  coreId: string | null
  /** The list pane's cores — the distinctness check reads it (no refetch). */
  cores: CoreRecord[]
  currentIcon: string | null
  onSaved: (updated: CoreRecord) => void
}) {
  const [saving, setSaving] = React.useState<string | null>(null)
  const [warn, setWarn] = React.useState<string | null>(null)

  const usedByOthers = React.useMemo(() => {
    const m = new Map<string, string>()
    for (const c of cores) {
      if (c.id !== coreId && c.is_active && c.icon) {
        m.set(c.icon, c.display_name)
      }
    }
    return m
  }, [cores, coreId])

  async function pick(name: string) {
    if (!coreId || saving) return
    const holder = usedByOthers.get(name)
    setWarn(
      holder
        ? `"${name}" is already ${holder}'s icon — two families sharing a mark defeats at-a-glance distinction.`
        : null,
    )
    setSaving(name)
    try {
      const updated = await focusCoresService.update(coreId, { icon: name })
      onSaved(updated)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Icon save failed")
    } finally {
      setSaving(null)
    }
  }

  return (
    <div className="space-y-1.5" data-testid="focus-icon-picker">
      <div
        className="text-[11px] uppercase tracking-wide"
        style={{ color: "var(--content-muted)", fontFamily: "var(--font-plex-sans)" }}
      >
        Family icon
      </div>
      <div className="grid grid-cols-8 gap-1">
        {FOCUS_ICON_NAMES.map((name) => {
          const Glyph = focusIcon(name)
          const active = currentIcon === name
          const taken = usedByOthers.has(name)
          return (
            <button
              key={name}
              type="button"
              title={
                taken
                  ? `${name} — in use by ${usedByOthers.get(name)}`
                  : name
              }
              onClick={() => void pick(name)}
              disabled={saving !== null}
              className={
                "focus-ring-accent flex h-7 w-7 items-center justify-center rounded-md border transition-colors " +
                (active
                  ? "border-accent bg-accent-subtle text-accent"
                  : "border-border-subtle text-content-muted hover:border-border-strong hover:text-content-base")
              }
              data-testid={`focus-icon-choice-${name}`}
              data-taken={taken}
            >
              <Glyph size={14} />
            </button>
          )
        })}
      </div>
      {warn ? (
        <p
          className="text-caption text-status-warning"
          data-testid="focus-icon-distinctness-warn"
        >
          {warn}
        </p>
      ) : (
        <p className="text-caption text-content-subtle">
          Every variation of this core wears this mark — it identifies the
          family, everywhere, immediately.
        </p>
      )}
    </div>
  )
}
