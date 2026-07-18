/**
 * SuggestionsRail — rule-based v1, honesty visible (The Map Home campaign).
 *
 * THE RESTRAINT PINS (the observe-and-offer canon): at most a handful of
 * cards, never a feed; the WHY-LINE is LOAD-BEARING — every card states
 * the honest reason it exists; dismissal is respected (one X, recorded,
 * no resurrection); when no rule genuinely fires the rail renders NOTHING
 * (an empty rail beats a stretched one — the home reads whole without it).
 *
 * The rail AUGMENTS the home — it never reorders or hides the stable
 * spine beneath it (the navigation guarantee).
 */
import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Lightbulb, X } from "lucide-react"

import {
  getSuggestions, recordEngagement, type MapSuggestion,
} from "@/services/moc-map-service"

export function SuggestionsRail({
  onOpen, refreshToken,
}: {
  /** Opens the suggestion's ponder (the page maps ponder_key → overlay). */
  onOpen: (s: MapSuggestion) => void
  /** Refetch when this changes — the page passes its reload cycle so the
   * rail advances/retires the moment a ponder closes. */
  refreshToken?: unknown
}) {
  const [cards, setCards] = useState<MapSuggestion[]>([])
  const navigate = useNavigate()

  const load = useCallback(() => {
    getSuggestions().then(setCards).catch(() => setCards([]))
  }, [])

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load() }, [load, refreshToken])

  const dismiss = useCallback((s: MapSuggestion) => {
    recordEngagement(s.ponder_key, "dismissed")
    // Optimistic — the dismissal is final server-side too (no resurrection).
    setCards((prev) => prev.filter((c) => c.id !== s.id))
  }, [])

  // B-3 — the NAV-CAPABLE variant: an href card navigates (the setup
  // suggestion); ponder cards keep the page-supplied opener. RETIRE-BY-
  // REALITY lives server-side — the rule re-checks the live state each
  // build; the card vanishes on connection, never by click.
  const activate = (s: MapSuggestion) => {
    if (s.href) {
      recordEngagement(s.ponder_key, "viewed")
      navigate(s.href)
    } else {
      onOpen(s)
    }
  }

  if (cards.length === 0) return null // EMPTY-HONEST — nothing to stretch

  return (
    <section data-testid="map-suggestions-rail">
      <h2 className="flex items-center gap-1.5 text-caption font-medium uppercase tracking-wide text-content-subtle">
        <Lightbulb size={12} /> For you
      </h2>
      <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((s) => (
          <div
            key={s.id}
            role="button"
            tabIndex={0}
            onClick={() => activate(s)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault()
                activate(s)
              }
            }}
            className="group relative cursor-pointer rounded-md bg-surface-elevated p-4 shadow-level-1 transition-shadow duration-quick ease-settle hover:shadow-level-2 focus-ring-accent"
            data-testid={`map-suggestion-${s.rule}`}
          >
            <button
              type="button"
              aria-label={`Dismiss "${s.title}"`}
              onClick={(e) => { e.stopPropagation(); dismiss(s) }}
              className="focus-ring-accent absolute right-2 top-2 rounded-md p-1 text-content-subtle opacity-0 transition-opacity duration-quick hover:text-content-muted focus-visible:opacity-100 group-hover:opacity-100"
              data-testid={`map-suggestion-dismiss-${s.rule}`}
            >
              <X size={13} />
            </button>
            <p className="pr-6 text-body font-medium text-content-strong">
              {s.title}
            </p>
            {/* THE WHY — load-bearing; never omitted. */}
            <p
              className="mt-1 text-body-sm text-content-muted"
              data-testid={`map-suggestion-why-${s.rule}`}
            >
              {s.why}
            </p>
          </div>
        ))}
      </div>
    </section>
  )
}
