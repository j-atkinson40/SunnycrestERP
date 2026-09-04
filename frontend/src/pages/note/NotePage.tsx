/**
 * The note surface — session 1 shell.
 *
 * ⚠️ THIS IS NOT /home. Pulse still serves /home until session 5 retires it.
 * The note lives at its own route so the two coexist without either pretending
 * to be the other, and so the supersession markers on CLAUDE.md §1a and
 * PLATFORM_ARCHITECTURE §3 stay honest: they say Pulse is what ships, and it is.
 *
 * What this renders: the standing set, and an empty prose region.
 *
 * What it deliberately does NOT do:
 *  • Standing lines do not open. Opening is peek behaviour and peek is session
 *    3. A placeholder click would have to be removed later, and removing an
 *    interaction users have learned is worse than never shipping it.
 *  • No badges. Counts render as plain text — no colour escalation, no growth
 *    to catch the eye, no red. Per DECISIONS 2026-09-04: a count is a fact the
 *    user reads; a badge is a demand.
 *  • No reordering, ever. Entries render in declared order. Positional
 *    stability is the register's entire value — a user who has stopped reading
 *    the labels and hits the third line is relying on it.
 */

import { useEffect, useState } from "react";

import apiClient from "@/lib/api-client";

interface StandingEntry {
  entry_id: string;
  label: string;
  target_surface: string;
  target_key: string;
  /** null means NO count — never rendered as zero, because zero is a claim. */
  count: number | null;
  /** "absent" = no count declared · "ok" = resolved · "unavailable" = it broke.
   *  Both non-ok states render without a number; they are distinguished so a
   *  reviewer can tell a deliberate blank from a silent failure. */
  count_state: "absent" | "ok" | "unavailable";
  tier: string;
  openable: boolean;
}

interface TodayNote {
  note_id: string;
  note_date: string;
  subject_id: string;
  settled_at: string | null;
  standing_set: StandingEntry[];
  prose: unknown[];
}

export default function NotePage() {
  const [note, setNote] = useState<TodayNote | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    apiClient
      .get<TodayNote>("/note/today")
      .then((r) => {
        if (alive) setNote(r.data);
      })
      .catch(() => {
        // Unknown is not empty. An error must not render as a quiet day.
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
    };
  }, []);

  if (failed) {
    return (
      <div className="p-6">
        <p className="text-status-error">
          The note could not be loaded. This is an error, not an empty day.
        </p>
      </div>
    );
  }

  if (!note) {
    return <div className="p-6 text-content-muted">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-reading space-y-8 p-6">
      <header className="space-y-1">
        <h1 className="text-h2 text-content-strong">Today</h1>
        <p className="text-body-sm text-content-muted">{note.note_date}</p>
      </header>

      {/* The standing set — configured, never composed. */}
      <section aria-label="Standing set" className="space-y-1">
        {note.standing_set.map((e) => (
          <div
            key={e.entry_id}
            data-testid={`standing-${e.entry_id}`}
            data-tier={e.tier}
            className="flex items-baseline justify-between border-b border-border-subtle py-2"
          >
            <span className="text-body text-content-base">{e.label}</span>
            {/* Plain text. No badge, no colour, no shape. `data-count-state`
                carries the distinction to the DOM so a reviewer (and a test)
                can tell "no count" from "count broke" without either becoming
                a number. Never renders zero on failure — zero is a claim. */}
            <span
              data-testid={`count-${e.entry_id}`}
              data-count-state={e.count_state}
              className="text-body-sm tabular-nums text-content-muted"
            >
              {e.count_state === "ok" ? e.count : ""}
            </span>
          </div>
        ))}
      </section>

      {/* Prose region — session 2. Empty is a real state, not a gap. */}
      <section aria-label="Prose" data-testid="prose-region">
        {note.prose.length === 0 && (
          <p className="text-body text-content-muted">
            Nothing needs saying today.
          </p>
        )}
      </section>
    </div>
  );
}
