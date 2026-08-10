/**
 * FB-1 — the accounting Focus bindings, and the entry points without which they
 * would not be reachable.
 *
 * THE ACCOUNTING SUITE HAD ZERO FOCUSES BEFORE THIS, not one. Books Review was
 * described as a Focus for weeks; it is a purpose-built display component
 * rendering inside a /triage/ page, bound to the Focus primitive nowhere.
 *
 * TWO QUEUES ARE DELIBERATELY NOT BOUND and the absences are asserted, because
 * "we chose not to bind this" is invisible in code and reads as an oversight:
 *
 *   ar_collections_triage   — a WORKLIST, not a bounded decision. The condition
 *                             that stages an item does not resolve when the
 *                             operator sends the drafted email; it resolves when
 *                             the customer pays, elsewhere and later. THE
 *                             QUEUE'S EMPTINESS IS NOT EVIDENCE THE DECISION WAS
 *                             MADE — that is the test it fails.
 *   cash_receipts_matching  — overlaps Books Review from the opposite end (same
 *                             payment pool, same exact-amount ladder) while
 *                             lacking its claimed set and _try_claim. Held
 *                             pending the prior question of whether it should
 *                             still exist.
 *
 * THE REACHABILITY TESTS ARE THE POINT. `decision-triage` has been registered
 * and openable only by typing ?focus= into the URL since it shipped, because
 * nothing surfaced it. A registered Focus with no entry point is not a feature.
 */

import { describe, it, expect } from "vitest"

import { getFocusConfig, listFocusConfigs } from "./focus-registry"
import { triageActions } from "@/services/actions/triage"

const BOUND = [
  { id: "books-review", queueId: "reconciliation_review_triage" },
  { id: "month-end-close", queueId: "month_end_close_triage" },
  { id: "expense-categorization", queueId: "expense_categorization_triage" },
  // FB-2 — moved up from the deliberately-NOT-bound block below.
  { id: "cash-receipts", queueId: "cash_receipts_matching_triage" },
] as const

describe("accounting Focus bindings", () => {
  it.each(BOUND)("$id is registered as a triageQueue on $queueId", ({ id, queueId }) => {
    const config = getFocusConfig(id)
    expect(config).not.toBeNull()
    expect(config?.mode).toBe("triageQueue")
    expect(config?.queueId).toBe(queueId)
  })

  it("every bound accounting Focus carries a queueId", () => {
    // TriageQueueCore renders a deliberate "not bound" empty state when queueId
    // is missing — correct behaviour, and a silent nothing if it ever fires in
    // production. A binding without its queue is the failure this catches.
    for (const { id } of BOUND) {
      expect(getFocusConfig(id)?.queueId, `${id} lost its queueId`).toBeTruthy()
    }
  })
})

describe("the queues deliberately NOT bound", () => {
  it("ar_collections_triage has no Focus — it is a worklist, not a decision", () => {
    const bound = listFocusConfigs().filter(
      (c) => c.queueId === "ar_collections_triage",
    )
    expect(bound).toEqual([])
  })

  // `cash_receipts_matching_triage` USED TO BE ASSERTED HERE, held on the Books
  // Review overlap. FB-2 re-derived that at HEAD and bound it, so the assertion
  // moved to BOUND above rather than being deleted quietly — a test that pins a
  // decision has to move when the decision does, and leaving it would have made
  // the binding look like a regression.
  //
  // The ruling, so the next person does not re-open it from the same starting
  // point: the two queues answer different questions over different objects.
  // Books Review's item is a BANK STATEMENT LINE; cash receipts' item is a
  // CUSTOMER PAYMENT. Resolving either leaves the other open — an applied
  // payment does not reconcile the bank line, and a cleared bank line does not
  // apply the payment. `_try_claim` guards the first link, not the second.
})

describe("reachability — a Focus nobody can open is not shipped", () => {
  it.each(BOUND)("$id has a command-bar entry that opens it", ({ id }) => {
    const entry = triageActions.find((a) => a.route?.includes(`focus=${id}`))
    expect(entry, `no command-bar action opens ?focus=${id}`).toBeDefined()
    expect(entry?.keywords?.length ?? 0).toBeGreaterThan(2)
  })

  it("the entries open the Focus ATOP a route, never over their own queue page", () => {
    // `/triage/<queue>?focus=<id>` would render the standalone page AND the
    // Focus over it — the same queue twice, once behind the other. The backdrop
    // is the financials hub, mirroring the funeral-scheduling action.
    for (const { id } of BOUND) {
      const entry = triageActions.find((a) => a.route?.includes(`focus=${id}`))
      expect(entry?.route).not.toMatch(/^\/triage\//)
      expect(entry?.route).toMatch(/^\/financials\?focus=/)
    }
  })

  it("each entry is permission-gated the way its queue is", () => {
    // The queues all gate on invoice.approve server-side. An action offering an
    // opening the server will refuse is a worse experience than no action.
    for (const { id } of BOUND) {
      const entry = triageActions.find((a) => a.route?.includes(`focus=${id}`))
      expect(entry?.permission).toBe("invoice.approve")
    }
  })
})

describe("every triageQueue Focus is reachable — the generalized guard", () => {
  it("no registered triageQueue Focus is URL-only", () => {
    /**
     * THE TEST THAT WOULD HAVE CAUGHT decision-triage, and did not exist when
     * FB-1 wrote a comment about decision-triage being URL-only.
     *
     * The original reachability test iterated a hardcoded BOUND list — the
     * three Focuses that phase added — so it could not fail for the one it was
     * describing. This iterates the REGISTRY, so the next triageQueue Focus is
     * covered the moment it registers rather than the moment someone remembers.
     *
     * ⚠️ SCOPED TO triageQueue DELIBERATELY. A named command-bar entry is not
     * the only good answer — INTENT ESCALATION is the other, and the better one
     * where it applies: `quote-building` has no "Open Quote Focus" command and
     * must not get one, because it materializes from what the user is already
     * doing (CLAUDE.md's summon-is-intent-shaped rule — "if a command reads
     * 'Open X,' it's wrong"). A blanket assertion over ALL Focuses would score
     * the canonically-correct one as broken and invite someone to "fix" it.
     *
     * A triage queue is a list you go to on purpose, so a named entry is right
     * for this mode and wrong for editCanvas.
     */
    const triageFocuses = listFocusConfigs().filter(
      (c) => c.mode === "triageQueue" && !c.id.startsWith("test-"),
    )
    expect(triageFocuses.length).toBeGreaterThan(0)

    const unreachable = triageFocuses
      .filter((c) => !triageActions.some((a) => a.route?.includes(`focus=${c.id}`)))
      .map((c) => c.id)

    expect(unreachable, `URL-only triageQueue Focus: ${unreachable.join(", ")}`)
      .toEqual([])
  })
})
