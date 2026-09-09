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
  prose: ProseFragment[];
  withheld?: {
    fragment_id: string;
    instance_key: string;
    gate: string;
    deferred_until: string | null;
    deferred_count: number;
  }[];
}

/**
 * One run of prose in exactly one of the three text states.
 *
 * ⚠️ THE SERVER SENDS SPANS, NOT A STRING PLUS SUBSTRINGS TO MARK. Marking by
 * substring puts the mark in the wrong place whenever a label occurs twice, and
 * the output looks correct. Nothing here searches for anything.
 */
interface ProseSpan {
  text: string;
  state: "measured" | "inferred" | "plain";
  href: string | null;
  entity_id: string | null;
}

interface ProseFragment {
  fragment_id: string;
  instance_key: string;
  kind: "prompt" | "non_prompt";
  title: string;
  text: string;
  spans: ProseSpan[];
  target_surface: string;
  target_key: string;
  openable: boolean;
  gate: string;
  /** Prompts defer; non-prompts dismiss. Sent explicitly rather than inferred
   *  from `kind`, so a third kind does not silently get the wrong affordance. */
  deferrable: boolean;
  /** Every deferral of this prompt by this reader, ever — including ones that
   *  lapsed or were woken. Stated plainly, never escalated. */
  deferred_count: number;
}

/** The affordances the server accepts. `date` opens the picker. */
const DEFER_PRESETS: { preset: string; label: string }[] = [
  { preset: "tomorrow", label: "Tomorrow" },
  { preset: "next_week", label: "Next week" },
  { preset: "next_month", label: "Next month" },
];

export default function NotePage() {
  const [note, setNote] = useState<TodayNote | null>(null);
  const [failed, setFailed] = useState(false);
  /** instance_key of the prompt currently being deferred, so its controls
   *  disable rather than accepting a second click into an in-flight request. */
  const [deferring, setDeferring] = useState<string | null>(null);

  /**
   * ⚠️ REFETCH RATHER THAN PATCH LOCAL STATE. Deferring changes what the GATE
   * says, and the gate is the server's. Removing the fragment client-side would
   * be the client deciding what the note contains — and would be WRONG the
   * moment a deferral wakes on divergence instead of suppressing.
   */
  async function onDefer(
    f: ProseFragment,
    preset: string,
    deferredUntil?: string,
  ) {
    setDeferring(f.instance_key);
    try {
      await apiClient.post("/note/defer", {
        fragment_id: f.fragment_id,
        instance_key: f.instance_key,
        preset,
        deferred_until: deferredUntil ?? null,
      });
      const r = await apiClient.get<TodayNote>("/note/today");
      setNote(r.data);
    } catch {
      // Unknown is not empty, here too: a failed deferral leaves the prompt
      // exactly where it was rather than hiding it optimistically.
      setFailed(true);
    } finally {
      setDeferring(null);
    }
  }

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
      <section aria-label="Prose" data-testid="prose-region" className="space-y-4">
        {note.prose.length === 0 && (
          <p className="text-body text-content-muted">
            Nothing needs saying today.
          </p>
        )}

        {note.prose.map((f) => (
          <div key={f.instance_key} className="space-y-1">
          <p
            data-testid={`prose-${f.fragment_id}`}
            data-kind={f.kind}
            className="text-body text-content-base"
          >
            {f.spans.map((sp, i) => {
              /*
               * ⚠️ THREE STATES, DISTINGUISHED WITHOUT COLOUR. Functional colour
               * is reserved for meaning per DESIGN_LANGUAGE, so a reader who
               * cannot separate red from green must still tell a measurement
               * from an inference.
               *
               * MEASURED — a link. THE LINK IS THE PROVENANCE MARK; there is no
               * separate badge saying "this is real".
               */
              if (sp.state === "measured") {
                /*
                 * ⚠️ MEASURED-AND-UNLINKED IS A REAL STATE, not a missing href.
                 * A measured span always carries its provenance in the payload;
                 * whether that provenance is REACHABLE is a separate fact. The
                 * collections amount is measured and deliberately unlinked
                 * (operator review, 2026-09-09) because linked it pulled the eye
                 * harder than the customer name -- the badge question arriving
                 * in prose. Rendering an <a> with no href would keep the link
                 * styling and defeat the experiment.
                 */
                if (!sp.href) {
                  return (
                    <span key={i} data-state="measured" data-linked="false">
                      {sp.text}
                    </span>
                  );
                }
                return (
                  <a
                    key={i}
                    href={sp.href}
                    data-state="measured"
                    data-linked="true"
                    className="underline underline-offset-2 decoration-border-strong hover:decoration-content-base"
                  >
                    {sp.text}
                  </a>
                );
              }
              /*
               * INFERRED — unlinked, marked. Dotted underline is the DOCUMENTED
               * PLACEHOLDER: the exact treatment belongs to the aesthetics arc
               * and must survive the chrome/steel language. It is recorded as a
               * placeholder so it gets revisited rather than inherited.
               */
              if (sp.state === "inferred") {
                return (
                  <span
                    key={i}
                    data-state="inferred"
                    className="underline decoration-dotted underline-offset-2 decoration-content-subtle"
                  >
                    {sp.text}
                  </span>
                );
              }
              /* CONNECTIVE TISSUE — plain. The words making the other two a sentence. */
              return (
                <span key={i} data-state="plain">
                  {sp.text}
                </span>
              );
            })}
          </p>

          {/* ⚠️ PROMPTS DEFER. NON-PROMPTS DISMISS, and that path is not here.
              A prompt has no "make this go away" — it leaves by its end
              transition occurring or by the reader naming a date. */}
          {f.deferrable && (
            <div
              data-testid={`defer-${f.fragment_id}`}
              className="flex flex-wrap items-baseline gap-2 text-body-sm text-content-muted"
            >
              <span>See again</span>
              {DEFER_PRESETS.map((p) => (
                <button
                  key={p.preset}
                  type="button"
                  disabled={deferring === f.instance_key}
                  data-testid={`defer-${f.fragment_id}-${p.preset}`}
                  onClick={() => onDefer(f, p.preset)}
                  className="underline underline-offset-2 decoration-border-strong hover:decoration-content-base disabled:opacity-50"
                >
                  {p.label}
                </button>
              ))}
              <input
                type="date"
                aria-label="Defer to a specific date"
                data-testid={`defer-${f.fragment_id}-date`}
                disabled={deferring === f.instance_key}
                onChange={(e) =>
                  e.target.value && onDefer(f, "date", e.target.value)
                }
                className="bg-transparent text-body-sm text-content-muted underline underline-offset-2 decoration-border-strong disabled:opacity-50"
              />

              {/* ⚠️ STATED, NEVER ESCALATED. No colour, no icon, no urgency.
                  Someone pushing the same thing repeatedly is usually blocked
                  on something else — that is worth seeing, and colouring it
                  would state a judgement the surface has not earned. */}
              {f.deferred_count > 0 && (
                <span data-testid={`defer-count-${f.fragment_id}`}>
                  · deferred {f.deferred_count}{" "}
                  {f.deferred_count === 1 ? "time" : "times"}
                </span>
              )}
            </div>
          )}
          </div>
        ))}

        {/* A deferred prompt says WHEN it comes back. Without this line,
            "withheld" and "gone" look identical to the reader who deferred it. */}
        {(note.withheld ?? [])
          .filter((w) => w.gate === "withheld:deferred")
          .map((w) => (
            <p
              key={w.instance_key}
              data-testid={`deferred-${w.fragment_id}`}
              className="text-body-sm text-content-muted"
            >
              Deferred until {w.deferred_until}
              {w.deferred_count > 1
                ? ` · deferred ${w.deferred_count} times`
                : ""}
            </p>
          ))}
      </section>
    </div>
  );
}
