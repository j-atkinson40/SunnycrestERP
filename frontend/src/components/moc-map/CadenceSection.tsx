/**
 * THE CADENCE SECTION (MAP-4) — one card per rhythm the area actually runs on.
 *
 * MAP-3 derived the grains and put them in the area STORY: four sentences
 * inside one narrative behind a button. Correct content at the wrong altitude —
 * an operator who wants to know what happens at month-end had to read the whole
 * rhythm to find it.
 *
 * THREE LEVELS, EACH ENTERABLE WITHOUT THE ONE ABOVE:
 *   the story    — the whole rhythm, behind its button (MAP-3)
 *   these cards  — one rhythm, on the page, no click
 *   the tasks    — one job, on the page
 * Widest to narrowest. Neither level requires reading the other.
 *
 * DERIVED AND AUTHORED, VISIBLY SPLIT. The label, the times and the job list
 * are read from the tenant's own workflow triggers every render. The sentence
 * is authored (r158) and says what the OPERATOR DOES — the part no schedule can
 * tell you.
 *
 * ⚠️ NO LIVE STATE HERE, DELIBERATELY. A pending count beside "the close stages
 * its anomalies" would say *clear this first* without saying it — the
 * clean-queue claim smuggled in as layout adjacency rather than prose, where
 * nothing could hold it accountable. Nothing enforces that ordering. A count
 * belongs on Books Review's own card, describing its own queue.
 */
import { Link } from "react-router-dom"
import { Clock } from "lucide-react"

import type { CadenceCard } from "@/services/moc-map-service"

export function CadenceSection({
  cards,
  area,
}: {
  cards: CadenceCard[]
  area: string
}) {
  // HONEST ABSENCE. Most areas have no scheduled work at all — measured, only
  // two of the seeded areas produce cadence beats. Rendering an empty "Rhythm"
  // heading on the rest would be scaffolding pretending to be content.
  if (cards.length === 0) return null

  return (
    <section className="mb-8" data-testid="map-cadence-section">
      <h2 className="text-caption font-medium uppercase tracking-wide text-content-subtle">
        Rhythm
      </h2>
      <p className="mt-1 text-body-sm text-content-muted">
        When the {area} work runs, and what you do in each.
      </p>
      <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2">
        {cards.map((c) => (
          <article
            key={c.key}
            data-testid={`map-cadence-card-${c.grain}`}
            className="rounded-xl border border-border-base bg-surface-elevated p-4 shadow-level-1"
          >
            <div className="flex items-baseline justify-between gap-3">
              <h3 className="text-body font-medium text-content-strong">
                {c.label}
              </h3>
              {c.whens.length > 0 ? (
                <span className="inline-flex shrink-0 items-center gap-1 text-caption tabular-nums text-content-muted">
                  <Clock size={12} className="text-content-subtle" />
                  {/* THE TIMES, not the adjective. "Overnight" is the grain; a
                      person deciding when to sit down needs 10:30 PM. */}
                  {c.whens.join(" · ")}
                </span>
              ) : null}
            </div>

            <p className="mt-2 text-body-sm text-content-base">{c.text}</p>

            {c.jobs.length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {c.jobs.map((j) => (
                  // Each chip is the way INTO the task card — the cadence card
                  // answers "what runs together"; the task card answers "what
                  // this one does". Neither duplicates the other.
                  <Link
                    key={j.id}
                    to={`/bridgeable-map/${encodeURIComponent(area)}#job-${j.id}`}
                    className="focus-ring-accent rounded-full border border-border-subtle bg-surface-sunken px-2.5 py-1 text-caption text-content-muted transition-colors duration-quick hover:border-border-base hover:text-content-base"
                  >
                    {j.name}
                  </Link>
                ))}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  )
}
