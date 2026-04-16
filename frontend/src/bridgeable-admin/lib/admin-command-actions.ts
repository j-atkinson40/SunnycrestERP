// Admin command bar action registry — Cmd+K actions.

export type CommandActionType = "COMMAND" | "NAVIGATE" | "RECORD" | "ASK"

export interface CommandAction {
  id: string
  title: string
  subtitle?: string
  keywords: string[]
  type: CommandActionType
  handler: string
  requiresConfirmation?: boolean
  example?: string
}

export const ADMIN_COMMAND_ACTIONS: CommandAction[] = [
  // Tenant lookup & navigation
  {
    id: "find-tenant",
    title: "Find tenant",
    subtitle: "Search by name or vertical",
    keywords: ["find", "open", "tenant", "search"],
    type: "COMMAND",
    handler: "searchTenants",
    example: "find sunnycrest",
  },
  // Impersonation
  {
    id: "impersonate",
    title: "Impersonate tenant user",
    subtitle: "Open tenant platform as admin user",
    keywords: ["impersonate", "login as", "act as", "become"],
    type: "COMMAND",
    handler: "impersonateTenant",
    requiresConfirmation: true,
    example: "impersonate sunnycrest admin",
  },
  // Staging
  {
    id: "open-staging",
    title: "Open tenant staging",
    keywords: ["open staging", "staging for", "test"],
    type: "COMMAND",
    handler: "openTenantStaging",
    example: "open sunnycrest staging",
  },
  // Create staging tenant
  {
    id: "create-staging",
    title: "Create staging tenant",
    subtitle: "Seeded test tenant for any vertical",
    keywords: ["create test", "seed tenant", "new staging", "create staging"],
    type: "COMMAND",
    handler: "createStagingTenant",
    example: "create test funeral home tenant",
  },
  // Audit runner
  {
    id: "run-audit",
    title: "Run audit",
    subtitle: "Playwright E2E test suite",
    keywords: ["run audit", "run tests", "playwright", "audit"],
    type: "NAVIGATE",
    handler: "/bridgeable-admin/audit",
    example: "run audit for sunnycrest",
  },
  // Last audit summary
  {
    id: "last-audit",
    title: "Last audit results",
    subtitle: "Show most recent test run",
    keywords: ["last audit", "audit results", "test results"],
    type: "ASK",
    handler: "askAuditSummary",
  },
  // Migrations
  {
    id: "migrations",
    title: "Run staging migrations",
    subtitle: "alembic upgrade head on staging",
    keywords: ["run migrations", "migrate staging", "alembic", "migrations"],
    type: "NAVIGATE",
    handler: "/bridgeable-admin/migrations",
    requiresConfirmation: true,
  },
  // Feature flags
  {
    id: "feature-flags",
    title: "Feature flags",
    keywords: ["feature flag", "enable feature", "disable", "flag"],
    type: "NAVIGATE",
    handler: "/bridgeable-admin/feature-flags",
    example: "enable funeral home vertical",
  },
  // Deployments
  {
    id: "log-deployment",
    title: "Log deployment",
    subtitle: "Track test coverage of a push",
    keywords: ["log deployment", "new deployment", "deploy"],
    type: "NAVIGATE",
    handler: "/bridgeable-admin/deployments",
  },
  {
    id: "untested-deployments",
    title: "Show untested deployments",
    keywords: ["untested deployments", "deployment status", "untested"],
    type: "NAVIGATE",
    handler: "/bridgeable-admin/deployments?filter=untested",
  },
  // Smoke tests
  {
    id: "smoke-test",
    title: "Run smoke test",
    subtitle: "Production smoke test for a tenant",
    keywords: ["smoke test", "smoke"],
    type: "COMMAND",
    handler: "runSmokeTest",
  },
  // Chat
  {
    id: "ask",
    title: "Ask Bridgeable Assistant",
    keywords: ["ask", "chat", "question"],
    type: "ASK",
    handler: "openChatMode",
  },
  // Saved prompts
  {
    id: "saved-prompts",
    title: "Show saved prompts",
    keywords: ["saved prompts", "my prompts", "build prompts"],
    type: "COMMAND",
    handler: "showSavedPrompts",
  },
  // Refresh context
  {
    id: "refresh-context",
    title: "Refresh context",
    subtitle: "Reload CLAUDE.md and platform state",
    keywords: ["refresh context", "update context"],
    type: "COMMAND",
    handler: "refreshChatContext",
  },
  // Navigation shortcuts
  {
    id: "nav-health",
    title: "Go to health dashboard",
    keywords: ["go to health", "health", "dashboard"],
    type: "NAVIGATE",
    handler: "/bridgeable-admin",
  },
  {
    id: "nav-tenants",
    title: "Go to tenants",
    keywords: ["go to tenants", "tenants", "kanban"],
    type: "NAVIGATE",
    handler: "/bridgeable-admin/tenants",
  },
]

// Question detector: starts with interrogative or contains "help me", "explain", etc.
const QUESTION_STARTERS = [
  "why", "what", "how", "when", "where", "who", "which",
  "can", "could", "should", "is", "are", "does", "did",
]
const QUESTION_CONTAINS = [
  "help me", "explain", "generate", "write",
  "create a prompt", "what was the decision",
]

export function isQuestion(input: string): boolean {
  const lower = input.trim().toLowerCase()
  if (!lower) return false
  for (const starter of QUESTION_STARTERS) {
    if (lower.startsWith(starter + " ") || lower === starter) return true
  }
  for (const phrase of QUESTION_CONTAINS) {
    if (lower.includes(phrase)) return true
  }
  if (lower.endsWith("?")) return true
  return false
}

// Simple fuzzy score: counts matching keyword tokens, higher is better.
export function scoreAction(action: CommandAction, query: string): number {
  if (!query.trim()) return 0
  const q = query.toLowerCase()
  let score = 0
  for (const kw of action.keywords) {
    if (q.includes(kw.toLowerCase())) score += 10
  }
  if (action.title.toLowerCase().includes(q)) score += 5
  // Token-level match
  const qTokens = q.split(/\s+/)
  for (const t of qTokens) {
    if (t.length < 2) continue
    if (action.title.toLowerCase().includes(t)) score += 2
    if (action.keywords.some((k) => k.toLowerCase().includes(t))) score += 1
  }
  return score
}

export function rankActions(query: string, max = 5): CommandAction[] {
  if (!query.trim()) {
    // Return the most useful defaults
    return [
      ADMIN_COMMAND_ACTIONS.find((a) => a.id === "find-tenant")!,
      ADMIN_COMMAND_ACTIONS.find((a) => a.id === "run-audit")!,
      ADMIN_COMMAND_ACTIONS.find((a) => a.id === "log-deployment")!,
      ADMIN_COMMAND_ACTIONS.find((a) => a.id === "feature-flags")!,
      ADMIN_COMMAND_ACTIONS.find((a) => a.id === "ask")!,
    ].filter(Boolean)
  }
  const scored = ADMIN_COMMAND_ACTIONS
    .map((a) => ({ action: a, score: scoreAction(a, query) }))
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, max)
    .map((s) => s.action)
  return scored
}
