/**
 * Derived-diff renderer (Focus Variations V-2) — shared by the publish
 * dialog (read-only preview) and the offer dialog (with the per-field
 * keep-mine / take-new chooser on customized rows).
 *
 * Core→template inheritance is FIELD-granular (placements are never
 * core-inherited), so the chooser is a compact per-field segmented pick —
 * keep-mine (default; the cascade keeps the variation's override winning,
 * zero writes) vs take-new (explicitly drops the override).
 */

import type { UpdateDiffField } from "@/bridgeable-admin/services/moc-service"

function short(v: unknown): string {
  if (v === null || v === undefined) return "—"
  const s = typeof v === "string" ? v : JSON.stringify(v)
  return s.length <= 28 ? s : s.slice(0, 25) + "…"
}

export function UpdateDiffList({
  fields,
  choices,
  onChoice,
}: {
  fields: UpdateDiffField[]
  /** When provided, customized rows render the keep/take chooser. */
  choices?: Record<string, "keep" | "take">
  onChoice?: (field: string, choice: "keep" | "take") => void
}) {
  if (fields.length === 0) {
    return (
      <p className="text-caption text-content-subtle">
        No field changes (component behavior may have changed in code).
      </p>
    )
  }
  return (
    <ul className="space-y-1" data-testid="update-diff-list">
      {fields.map((f) => {
        const customized = f.target_state === "customized"
        const choice = choices?.[f.field] ?? "keep"
        return (
          <li
            key={`${f.family}.${f.field}`}
            className="rounded-md border border-border-subtle bg-surface-elevated px-2.5 py-1.5"
            data-testid={`diff-field-${f.field}`}
          >
            <div className="flex items-center gap-2 text-body-sm">
              <span className="text-caption uppercase tracking-wide text-content-subtle">
                {f.family}
              </span>
              <span className="font-medium text-content-base">{f.field}</span>
              <span className="text-content-muted">
                {short(f.from)} → {short(f.to)}
              </span>
            </div>
            {customized ? (
              <div className="mt-1 flex items-center gap-2 text-caption">
                <span className="text-status-warning">
                  You customized this ({short(f.target_value)})
                </span>
                {onChoice ? (
                  <span className="inline-flex overflow-hidden rounded-sm border border-border-base">
                    <button
                      type="button"
                      onClick={() => onChoice(f.field, "keep")}
                      className={
                        "px-2 py-0.5 " +
                        (choice === "keep"
                          ? "bg-accent-subtle text-content-strong"
                          : "text-content-muted hover:text-content-base")
                      }
                      data-testid={`diff-keep-${f.field}`}
                    >
                      Keep mine
                    </button>
                    <button
                      type="button"
                      onClick={() => onChoice(f.field, "take")}
                      className={
                        "px-2 py-0.5 " +
                        (choice === "take"
                          ? "bg-accent-subtle text-content-strong"
                          : "text-content-muted hover:text-content-base")
                      }
                      data-testid={`diff-take-${f.field}`}
                    >
                      Take new
                    </button>
                  </span>
                ) : null}
              </div>
            ) : null}
          </li>
        )
      })}
    </ul>
  )
}
