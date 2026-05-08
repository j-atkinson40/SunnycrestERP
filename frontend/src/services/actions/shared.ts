/**
 * Phase 5 — Cross-vertical create actions.
 *
 * These entries surface in every vertical (`vertical: "cross"`). The
 * `supports_nl_creation` flag + `nl_aliases` list is the authoritative
 * source for `detectNLIntent.ts` — the Phase 4 NL overlay reads this
 * list rather than maintaining its own duplicated pattern table.
 *
 * Backend parity:
 *   - `create.quote` / `create.invoice` / `create.contact` /
 *     `create.product` / `create.task` match the seeds in
 *     `backend/app/services/command_bar/registry.py`.
 *   - Case creation (`fh_new_arrangement`) lives in
 *     `funeral_home.ts` — FH-preset-only.
 *   - Sales-order creation is covered by the `wf_create_order`
 *     workflow registered elsewhere; no entry here.
 */

import type { ActionRegistryEntry } from "./types";

export const sharedActions: ActionRegistryEntry[] = [
  {
    id: "create_quote",
    title: "New quote",
    subtitle: "Open quote creation",
    icon: "file-question",
    kind: "create",
    keywords: ["new quote", "create quote", "estimate", "bid", "new estimate"],
    nl_aliases: ["quote", "estimate", "bid"],
    supports_nl_creation: false,
    roles: ["admin", "office"],
    vertical: "cross",
    route: "/quoting/new",
  },
  {
    id: "create_invoice",
    title: "New invoice",
    subtitle: "Open invoice creation",
    icon: "receipt",
    kind: "create",
    keywords: ["new invoice", "create invoice", "bill", "new bill"],
    nl_aliases: ["invoice", "bill"],
    supports_nl_creation: false,
    roles: ["admin", "office"],
    vertical: "cross",
    route: "/ar/invoices/new",
  },
  {
    id: "create_contact",
    title: "New contact",
    subtitle: "Add a CRM contact",
    icon: "user-plus",
    kind: "create",
    keywords: ["new contact", "add contact", "new person"],
    nl_aliases: ["contact", "person"],
    // Phase 4 — registered in the NL entity registry.
    supports_nl_creation: true,
    roles: ["admin", "office"],
    vertical: "cross",
    route: "/vault/crm/contacts/new",
  },
  {
    id: "create_product",
    title: "New product",
    subtitle: "Open product creation",
    icon: "package",
    kind: "create",
    keywords: ["new product", "add product", "new SKU"],
    nl_aliases: ["product", "SKU"],
    supports_nl_creation: false,
    roles: ["admin", "office"],
    vertical: "cross",
    route: "/products/new",
  },
  // ── Phase 5 NEW — Task creation ────────────────────────────────
  {
    id: "create_task",
    title: "New task",
    subtitle: "Add a task",
    icon: "check-circle",
    kind: "create",
    keywords: ["new task", "add task", "create task", "todo", "new todo"],
    nl_aliases: ["task", "todo"],
    supports_nl_creation: true,
    roles: ["admin", "office", "production", "director", "driver"],
    vertical: "cross",
    route: "/tasks/new",
  },
  // ── Phase 4 NL overlay — calendar event (cross-vertical) ───────
  {
    id: "create_event",
    title: "Schedule event",
    subtitle: "Add a calendar event",
    icon: "calendar-plus",
    kind: "create",
    keywords: ["schedule event", "new event", "create event", "meeting"],
    nl_aliases: ["event", "meeting", "calendar event"],
    supports_nl_creation: true,
    roles: ["admin", "office", "director"],
    vertical: "cross",
    route: "/vault/calendar",
  },
  // ── Phase 6 briefings (cross-vertical) ─────────────────────────
  {
    id: "navigate_briefing_latest",
    title: "Open briefing",
    subtitle: "Today's morning or evening summary",
    icon: "sunrise",
    kind: "navigate",
    keywords: [
      "briefing",
      "morning briefing",
      "evening briefing",
      "daily briefing",
      "todays briefing",
    ],
    roles: [],
    vertical: "cross",
    route: "/briefing",
  },
  {
    id: "navigate_briefing_preferences",
    title: "Briefing preferences",
    subtitle: "Configure delivery + sections",
    icon: "settings",
    kind: "navigate",
    keywords: [
      "briefing settings",
      "briefing preferences",
      "configure briefing",
    ],
    roles: [],
    vertical: "cross",
    route: "/settings/briefings",
  },
  // ── R-5.1 — edge panel customization (cross-vertical) ──────────
  {
    id: "navigate_settings_edge_panel",
    title: "Customize edge panel",
    subtitle: "Personalize your edge panel for this tenant",
    icon: "settings",
    kind: "navigate",
    keywords: [
      "edge panel",
      "edge panel settings",
      "customize edge panel",
      "edge panel preferences",
      "panel preferences",
    ],
    roles: [],
    vertical: "cross",
    route: "/settings/edge-panel",
  },
];
