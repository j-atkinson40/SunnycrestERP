/**
 * MoCFiresCard — recent MoC fires (schedule + event, dry-run/LIVE, with event
 * provenance). Shared by the tenant page (company-scoped, H-1) and the
 * platform home (cross-tenant, H-2 — the "is the platform doing things"
 * pulse). Display-only; the data is the unified fires log.
 */
import type { MoCScheduleRun } from "@/bridgeable-admin/services/moc-service"

export function MoCFiresCard({
  fires, emptyText, "data-testid": testId = "moc-fires-card",
}: {
  fires: MoCScheduleRun[]
  emptyText: string
  "data-testid"?: string
}) {
  return (
    <section className="space-y-2" data-testid={testId}>
      <h2 className="text-h4 font-semibold text-content-strong">Recent fires</h2>
      {fires.length === 0 ? (
        <p className="text-body-sm text-content-subtle">{emptyText}</p>
      ) : (
        <ul className="divide-y divide-border-subtle rounded-md border border-border-subtle">
          {fires.map((f) => (
            <li key={f.run_id} className="flex items-center gap-2 px-3 py-1.5 text-body-sm">
              <span
                className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-caption ${
                  f.is_dry_run
                    ? "bg-surface-sunken text-content-muted"
                    : "bg-accent text-content-on-accent font-semibold"
                }`}
              >
                {f.is_dry_run ? "Dry-run" : "LIVE"}
              </span>
              <span className="text-content-base">{f.task_name ?? "—"}</span>
              <span className="text-content-subtle">
                {f.source === "event" ? `event ${f.event_key ?? ""}` : "schedule"}
              </span>
              <span className="ml-auto text-caption text-content-subtle">
                {f.started_at ? new Date(f.started_at).toLocaleString() : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
