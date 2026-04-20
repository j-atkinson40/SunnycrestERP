/**
 * Phase 5 — Funeral-home vertical actions.
 *
 * Migrated verbatim from the pre-Phase-5 `core/actionRegistry.ts`
 * `funeralHomeActions` array. Case creation (`fh_new_arrangement`)
 * stays in this vertical — it's the FH director's primary intent
 * surface and is coupled to the FH-specific Story workflow. Task +
 * event + contact creates live in `shared.ts`.
 */

import type { ActionRegistryEntry } from "./types";

export const funeralHomeActions: ActionRegistryEntry[] = [
  {
    id: "fh_new_arrangement",
    title: "New Arrangement",
    subtitle: "Create a new funeral case",
    icon: "plus-circle",
    kind: "create",
    keywords: [
      "new arrangement",
      "new case",
      "first call",
      "create case",
      "start arrangement",
    ],
    nl_aliases: ["case", "arrangement", "file"],
    supports_nl_creation: true,
    roles: ["admin", "director"],
    vertical: "funeral_home",
    route: "/fh/cases",
  },
  {
    id: "fh_nav_cases",
    title: "Cases",
    icon: "folder",
    kind: "navigate",
    keywords: ["cases", "all cases", "case list", "active cases"],
    roles: ["admin", "director", "office"],
    vertical: "funeral_home",
    route: "/fh/cases",
  },
  {
    id: "fh_nav_home",
    title: "Funeral Direction Hub",
    icon: "home",
    kind: "navigate",
    keywords: ["home", "direction hub", "go home", "dashboard"],
    roles: ["admin", "director", "office"],
    vertical: "funeral_home",
    route: "/fh",
  },
  {
    id: "fh_add_case_note",
    title: "Add case note",
    subtitle: "Jot a note on the current case",
    icon: "file-text",
    kind: "action",
    keywords: ["add note", "case note", "log note", "add to case"],
    handler: "addNoteToCurrentCase",
    roles: ["admin", "director"],
    vertical: "funeral_home",
  },
  {
    id: "fh_start_scribe",
    title: "Start Scribe recording",
    subtitle: "Capture an arrangement conference",
    icon: "mic",
    kind: "action",
    keywords: [
      "scribe",
      "start scribe",
      "record arrangement",
      "start recording",
    ],
    handler: "openScribeForCurrentCase",
    roles: ["admin", "director"],
    vertical: "funeral_home",
  },
  {
    id: "fh_nav_services",
    title: "Services this week",
    icon: "calendar",
    kind: "navigate",
    keywords: ["services", "this week", "upcoming services", "schedule"],
    roles: ["admin", "director", "office"],
    vertical: "funeral_home",
    route: "/fh",
  },
  {
    id: "fh_find_case",
    title: "Find case",
    icon: "search",
    kind: "action",
    keywords: ["find case", "search case", "open case", "find family"],
    roles: ["admin", "director", "office"],
    vertical: "funeral_home",
    route: "/fh/cases",
  },
  {
    id: "fh_network",
    title: "Network",
    subtitle: "Connected cemeteries, manufacturers, crematories",
    icon: "link",
    kind: "navigate",
    keywords: [
      "network",
      "connections",
      "cemetery",
      "manufacturer",
      "crematory",
      "partners",
    ],
    roles: ["admin", "director"],
    vertical: "funeral_home",
    route: "/fh/settings/network",
  },
  {
    id: "fh_approve_all",
    title: "Approve all (Story step)",
    subtitle: "Finalize and send all orders",
    icon: "check-square",
    kind: "action",
    keywords: [
      "approve all",
      "story",
      "finalize",
      "finish arrangement",
    ],
    handler: "openStoryForCurrentCase",
    roles: ["admin", "director"],
    vertical: "funeral_home",
  },
];
