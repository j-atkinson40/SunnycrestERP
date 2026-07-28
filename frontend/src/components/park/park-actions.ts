/**
 * Park summon actions (S-5) — intent-shaped command-bar entries.
 *
 * Summon is FROM the command bar, never an app-launcher menu (spec). Each
 * entry's `handler` is a `park:summon:<act-type>` string; CommandBar's
 * executeAction dispatches it to `summonParkAct`, which drops a tablet
 * into the park working set. Park coexists with the bar (no `?focus=`),
 * so summoning doesn't close it.
 */

import type { ActionRegistryEntry } from "@/services/actions/types"

export const parkSummonActions: ActionRegistryEntry[] = [
  {
    id: "park_summon_reply_dm",
    title: "Reply in park",
    subtitle: "Open a reply beside your other work",
    icon: "message-square",
    kind: "action",
    keywords: ["reply", "reply dm", "respond", "reply to sender"],
    roles: [],
    vertical: "cross",
    handler: "park:summon:reply-dm",
  },
  {
    id: "park_summon_add_note",
    title: "Add a note in park",
    subtitle: "Jot a note to a record beside your other work",
    icon: "file-text",
    kind: "action",
    keywords: ["note", "add note", "log note", "jot a note"],
    roles: [],
    vertical: "cross",
    handler: "park:summon:add-note",
  },
  {
    id: "park_summon_start_quote",
    title: "Start a quote in park",
    subtitle: "Begin a quote beside your other work",
    icon: "file-question",
    kind: "action",
    keywords: ["quote in park", "start a quote", "park quote", "new quote here"],
    roles: [],
    vertical: "cross",
    handler: "park:summon:start-quote",
  },
]
