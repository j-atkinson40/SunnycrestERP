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
];
