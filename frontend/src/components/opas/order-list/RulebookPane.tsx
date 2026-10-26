/**
 * The rulebook. Sentences the office wrote, and where each came from.
 *
 * James's dispatch of 2026-10-26, clause 4: "'the rulebook' / 'rules' in the bar opens a
 * pane listing active rules (sentence, who, when, the change it came from, linking to
 * that order). Each rule can be edited or switched off."
 *
 * ⚠️ THE FOOTER IS THE MOST IMPORTANT LINE ON THIS PANE AND IT COMES FROM THE SERVER.
 * "nothing uses the rulebook in this slice. It records and shows, and the model starts
 * reading it in the next step" (James). A reader who sees a rule they confirmed would
 * otherwise reasonably assume it is in force — so the pane says, in its own words, that
 * it is not. One place composes it, as with every other sentence on every other pane.
 *
 * ⚠️ THERE IS NO PROTOTYPE FOR THIS PANE. The 2026-10-03 artifact covers Contact,
 * Cemetery and Invoice; the rulebook is new with this dispatch and the design is the
 * dispatch's own four clauses. So the glass, the density and the section header are
 * taken from `CustomerPane` and `CemeteryPane` rather than quoted from a prototype —
 * stated because every other pane's docstring quotes its source and a reader should know
 * this one has none to quote.
 */
import { useCallback, useEffect, useRef, useState } from "react"

import {
  getRulebook,
  updateRule,
  type RulebookDetail,
} from "@/services/order-list-service"

const HAIRLINE = "1px solid rgba(255,255,255,.08)"
const SERIF = '"IBM Plex Serif", ui-serif, Georgia, serif'
/** `.sech{…letter-spacing:.14em;text-transform:uppercase;color:var(--fg-3)}` */
const SECH = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "baseline",
  fontSize: 11,
  letterSpacing: ".14em",
  textTransform: "uppercase",
  color: "#5e5e5e",
  padding: "0 0 6px",
  margin: "14px 0 0",
} as const
const LNK = {
  background: "none",
  border: 0,
  padding: 0,
  color: "#9a9a9a",
  font: "inherit",
  fontSize: 12,
  cursor: "pointer",
  textDecoration: "underline",
  textDecorationColor: "rgba(255,255,255,.16)",
  textUnderlineOffset: 3,
} as const
const TERRA = "#cc7452"

export interface RulebookPaneProps {
  /** Opens the order a rule came from. Absent while nothing can resolve a decision. */
  readonly onOpenDecision?: (decisionId: string) => void
  /** Bumped by the host when a rule has just been added, so the pane re-reads. */
  readonly refresh?: number
}

export function RulebookPane({ onOpenDecision, refresh }: RulebookPaneProps) {
  const [book, setBook] = useState<RulebookDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const read = useCallback(() => {
    getRulebook()
      .then((b) => {
        if (!mounted.current) return
        setBook(b)
        setError(null)
      })
      .catch(() => {
        if (!mounted.current) return
        setError("Could not read the rulebook")
      })
  }, [])

  // ⚠️ `refresh` IS IN THE DEPENDENCIES ON PURPOSE. Confirming a rule happens in the
  // BAR, not in this pane, so without it a pane already open would keep showing the
  // book as it was before the rule the person just wrote.
  useEffect(() => {
    read()
  }, [read, refresh])

  const save = useCallback(
    async (ruleId: string, text: string) => {
      try {
        await updateRule(ruleId, { text })
      } finally {
        setEditing(null)
        read()
      }
    },
    [read],
  )

  const switchOff = useCallback(
    async (ruleId: string) => {
      try {
        await updateRule(ruleId, { is_active: false })
      } finally {
        read()
      }
    },
    [read],
  )

  if (error !== null) {
    return (
      <p data-testid="opas-rulebook-error" style={{ margin: 0, fontSize: 13, color: TERRA }}>
        {error}
      </p>
    )
  }
  if (book === null) {
    return (
      <p data-testid="opas-rulebook-loading" style={{ margin: 0, fontSize: 13, color: "#5e5e5e" }}>
        Reading…
      </p>
    )
  }

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div data-testid="opas-rulebook-title" style={{ fontSize: 23, fontWeight: 300, letterSpacing: "-.012em", lineHeight: 1.2, fontFamily: SERIF }}>
        The rulebook
      </div>

      <div style={SECH}>
        <span>Rules</span>
        <span style={{ letterSpacing: 0, textTransform: "none", fontSize: 13 }}>
          {book.rules.length > 0 ? book.rules.length : ""}
        </span>
      </div>

      {book.rules.length === 0 ? (
        <p data-testid="opas-rulebook-empty" style={{ margin: 0, fontSize: 13, color: "#5e5e5e" }}>
          {book.empty}
        </p>
      ) : (
        book.rules.map((rule) => (
          <div
            key={rule.id}
            data-testid={`opas-rule-${rule.id}`}
            style={{ borderTop: HAIRLINE, padding: "9px 0" }}
          >
            {editing === rule.id ? (
              <>
                {/* ⚠️ A TEXTAREA RATHER THAN THE BAR. The bar is the only input for
                    CAPTURE, by ruling; editing a stored rule is a row-level edit inside
                    a pane, like Undo confirm, and routing it through the bar would make
                    an edit indistinguishable from a new request. */}
                <textarea
                  data-testid={`opas-rule-edit-${rule.id}`}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  rows={2}
                  style={{
                    width: "100%",
                    background: "rgba(255,255,255,.05)",
                    border: "1px solid rgba(255,255,255,.14)",
                    borderRadius: 6,
                    color: "#f2f2f2",
                    font: "inherit",
                    fontSize: 14,
                    padding: "6px 8px",
                    resize: "vertical",
                  }}
                />
                <div style={{ display: "flex", gap: 12, marginTop: 6 }}>
                  <button
                    type="button"
                    data-testid={`opas-rule-save-${rule.id}`}
                    style={LNK}
                    onClick={() => void save(rule.id, draft)}
                  >
                    Save
                  </button>
                  <button type="button" style={LNK} onClick={() => setEditing(null)}>
                    Cancel
                  </button>
                </div>
              </>
            ) : (
              <>
                <div style={{ fontSize: 14, color: "#f2f2f2" }}>{rule.text}</div>
                <div style={{ fontSize: 12, color: "#9a9a9a", marginTop: 2 }}>
                  {[rule.who, shortDate(rule.created_at)].filter(Boolean).join(" · ")}
                </div>
                {rule.change !== undefined && (
                  <div style={{ fontSize: 12, color: "#5e5e5e", marginTop: 2 }}>
                    {/* The change it came from, and the order it was on. */}
                    {rule.decision_id !== undefined && onOpenDecision !== undefined ? (
                      <button
                        type="button"
                        data-testid={`opas-rule-source-${rule.id}`}
                        style={{ ...LNK, color: "#5e5e5e" }}
                        onClick={() => onOpenDecision(rule.decision_id!)}
                      >
                        {rule.change}
                      </button>
                    ) : (
                      rule.change
                    )}
                  </div>
                )}
                {rule.reason !== undefined && (
                  <div style={{ fontSize: 12, color: "#5e5e5e", marginTop: 2, fontStyle: "italic" }}>
                    “{rule.reason}”
                  </div>
                )}
                <div style={{ display: "flex", gap: 12, marginTop: 5 }}>
                  <button
                    type="button"
                    data-testid={`opas-rule-edit-open-${rule.id}`}
                    style={LNK}
                    onClick={() => {
                      setEditing(rule.id)
                      setDraft(rule.text)
                    }}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    data-testid={`opas-rule-off-${rule.id}`}
                    style={LNK}
                    onClick={() => void switchOff(rule.id)}
                  >
                    Switch off
                  </button>
                </div>
              </>
            )}
          </div>
        ))
      )}

      {/* ⚠️ ALWAYS SHOWN, EVEN WITH NO RULES. An empty rulebook is the most likely moment
          for somebody to wonder what it would do if it had any. */}
      <p
        data-testid="opas-rulebook-footer"
        style={{ margin: "14px 0 0", fontSize: 12, color: "#5e5e5e", borderTop: HAIRLINE, paddingTop: 8 }}
      >
        {book.footer}
      </p>
    </div>
  )
}

/** `"2026-10-26T13:22:53+00:00"` -> `"Oct 26"`. Falls back to the raw value. */
export function shortDate(iso: string | undefined): string {
  if (iso === undefined) return ""
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" })
}
