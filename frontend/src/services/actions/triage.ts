/**
 * Phase 5 — Triage Workspace nav entries.
 *
 * Two platform-default queues ship in Phase 5 (seeded in
 * `backend/app/services/triage/platform_defaults.py`):
 *   - `task_triage` (any tenant, any role)
 *   - `ss_cert_triage` (manufacturing vertical, `invoice.approve`)
 *
 * Per-tenant queues live as VaultItems (item_type=triage_queue_config)
 * and are surfaced via the backend `/triage/queues` endpoint — they do
 * not have static entries in this file.
 */

import type { ActionRegistryEntry } from "./types";

export const triageActions: ActionRegistryEntry[] = [
  {
    id: "triage_workspace_index",
    title: "Triage Workspace",
    subtitle: "Process pending items one at a time",
    icon: "list-checks",
    kind: "triage",
    keywords: ["triage", "process queue", "work queue", "inbox zero"],
    roles: ["admin", "office", "production", "director", "driver"],
    vertical: "cross",
    route: "/triage",
  },
  {
    id: "triage_task_queue",
    title: "Triage my tasks",
    subtitle: "Complete, reassign, or defer your open tasks",
    icon: "check-square",
    kind: "triage",
    keywords: [
      "triage tasks",
      "task triage",
      "process tasks",
      "my tasks",
      "open tasks",
    ],
    roles: ["admin", "office", "production", "director", "driver"],
    vertical: "cross",
    route: "/triage/task_triage",
  },
  {
    id: "triage_ss_cert_queue",
    title: "Triage social service certificates",
    subtitle: "Approve or void pending certificates",
    icon: "file-check",
    kind: "triage",
    keywords: [
      "triage ss certs",
      "triage social service",
      "ss cert triage",
      "approve ss cert",
      "social service triage",
    ],
    roles: ["admin", "office"],
    permission: "invoice.approve",
    vertical: "manufacturing",
    route: "/triage/ss_cert_triage",
  },

  // ── Decision Triage (affordance audit, 2026-08-06) ───────────────────────
  //
  // THE ENTRY FB-1 NAMED AND DID NOT ADD. FB-1's comment below says
  // decision-triage "has been reachable ONLY by typing ?focus=decision-triage
  // into the address bar since it shipped" — and then added entries for the
  // three new Focuses while leaving the one it was describing exactly as it
  // found it. Diagnosed, cited as the motivating example, not fixed.
  //
  // IT ALSO UNBURIES workflow_review_triage. That queue's richest surface is
  // this Focus, so the plainer /triage index worked while the better door did
  // not — the Legacy Order workflow stages its proof for approval here.
  //
  // Backdrop is /financials for the same reason as the three below: the Focus
  // opens ATOP a route rather than over its own queue page.
  {
    id: "open_decision_triage_focus",
    title: "Open Decision Triage",
    subtitle: "Approve the proofs waiting on you",
    icon: "check-square",
    kind: "navigate",
    keywords: [
      "decision triage",
      "review decisions",
      "approve proof",
      "workflow review",
      "pending approvals",
      "decide",
    ],
    roles: ["admin", "office"],
    permission: "invoice.approve",
    vertical: "cross",
    route: "/financials?focus=decision-triage",
  },

  // ── Accounting Focuses (FB-1) ────────────────────────────────────────────
  //
  // THESE ARE THE WAY IN, and they are the point of the phase rather than a
  // convenience on top of it. `decision-triage` — the only triageQueue Focus
  // before this — has been reachable ONLY by typing `?focus=decision-triage`
  // into the address bar since it shipped, because nothing surfaced it. Three
  // more registry entries with no entry point would have been three more
  // surfaces nobody could open, which is the `accounting_gl` gap in a different
  // layer: shipped, correct, and unreachable.
  //
  // ROUTE SHAPE: `/financials?focus=<id>`, mirroring the funeral-scheduling
  // action verbatim (`/dispatch/funeral-schedule?focus=funeral-scheduling`).
  // The FocusProvider's URL-reconcile effect sees `?focus=` and opens the Focus
  // ATOP the route beneath — Monitor underneath, Decide on top. Deliberately NOT
  // `/triage/<queue>?focus=<id>`, which would render the standalone page and the
  // Focus over it: the same queue twice, once behind the other.
  //
  // The `/triage/<queue>` pages stay exactly where they are. A Focus is the
  // bounded-decision surface; the page remains for anyone who wants the list.
  {
    id: "open_books_review_focus",
    title: "Open Books Review",
    subtitle: "Clear the unreconciled bank lines",
    icon: "book-check",
    kind: "navigate",
    keywords: [
      "books review",
      "open books review",
      "reconcile",
      "reconciliation",
      "unmatched transactions",
      "bank review",
      "clear exceptions",
    ],
    roles: ["admin", "office"],
    permission: "invoice.approve",
    vertical: "cross",
    route: "/financials?focus=books-review",
  },
  {
    id: "open_month_end_close_focus",
    title: "Open Month-End Close",
    subtitle: "Close the period or name the blockers",
    icon: "calendar-check",
    kind: "navigate",
    keywords: [
      "month end close",
      "close the month",
      "close period",
      "month end",
      "period close",
      "approve close",
    ],
    roles: ["admin"],
    permission: "invoice.approve",
    vertical: "cross",
    route: "/financials?focus=month-end-close",
  },
  {
    id: "open_expense_categorization_focus",
    title: "Open Expense Categorization",
    subtitle: "Code the uncategorized expense lines",
    icon: "receipt",
    kind: "navigate",
    keywords: [
      "expense categorization",
      "categorize expenses",
      "code expenses",
      "uncategorized expenses",
      "expense coding",
    ],
    roles: ["admin", "office"],
    permission: "invoice.approve",
    vertical: "cross",
    route: "/financials?focus=expense-categorization",
  },
];
