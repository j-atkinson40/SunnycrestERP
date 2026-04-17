export interface CommandAction {
  id: string;
  keywords: string[];
  title: string;
  subtitle?: string;
  icon: string;
  type: "ACTION" | "NAV" | "VIEW" | "RECORD" | "ASK" | "WORKFLOW" | "ANSWER" | "DOCUMENT" | "ASK_AI";
  route?: string;
  prefillSchema?: Record<string, unknown>;
  // Either a named handler string (resolved in CommandBar dispatch) or an inline callback.
  handler?: string | (() => void);
  roles: string[];
  vertical: string;
  // WORKFLOW-only: the workflow id the engine should run
  workflowId?: string;
  // WORKFLOW-only: preview of the first step ("Ask: Which funeral home?")
  firstStepPreview?: string;
  // ANSWER/DOCUMENT-only: where the content lives, for preview + navigation
  contentSource?: string; // 'vault_document' | 'kb_article' | 'safety_program' | ...
  sourceId?: string;
  chunkId?: string;
  sourceSection?: string | null;
  excerpt?: string;
  confidence?: number;
}

export interface RecentAction {
  id: string;
  title: string;
  subtitle?: string;
  icon: string;
  type: string;
  action: Record<string, unknown>;
  timestamp: number;
}

const RECENT_ACTIONS_KEY = "bridgeable_recent_actions";
const MAX_RECENT = 10;

export function getRecentActions(): RecentAction[] {
  try {
    const raw = localStorage.getItem(RECENT_ACTIONS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function addRecentAction(action: RecentAction): void {
  const recent = getRecentActions().filter((a) => a.id !== action.id);
  recent.unshift({ ...action, timestamp: Date.now() });
  localStorage.setItem(
    RECENT_ACTIONS_KEY,
    JSON.stringify(recent.slice(0, MAX_RECENT))
  );
}

// Manufacturing preset actions
export const manufacturingActions: CommandAction[] = [
  // Note: create_order / create_disinterment / create_urn_order
  // are covered by the universal wf_create_order workflow with
  // natural-language extraction. Keeping separate ACTION entries
  // would duplicate the workflow row in the command bar.
  {
    id: "schedule_delivery",
    keywords: ["schedule delivery", "new delivery", "delivery for"],
    title: "Schedule delivery",
    subtitle: "Open delivery scheduling",
    icon: "truck",
    type: "ACTION",
    route: "/scheduling/new",
    roles: ["admin", "office", "driver"],
    vertical: "manufacturing",
  },
  {
    id: "log_pour",
    keywords: ["log pour", "pour mold", "production pour", "poured"],
    title: "Log production pour",
    subtitle: "Record mold pour event",
    icon: "layers",
    type: "ACTION",
    route: "/production/log-pour",
    roles: ["admin", "production"],
    vertical: "manufacturing",
  },
  {
    id: "log_strip",
    keywords: ["log strip", "strip mold", "stripped"],
    title: "Log mold strip",
    subtitle: "Record strip event",
    icon: "check-square",
    type: "ACTION",
    route: "/production/log-strip",
    roles: ["admin", "production"],
    vertical: "manufacturing",
  },
  {
    id: "view_deliveries_today",
    keywords: ["deliveries today", "todays deliveries", "today delivery"],
    title: "Deliveries today",
    subtitle: "",
    icon: "calendar",
    type: "NAV",
    route: "/scheduling?filter=today",
    roles: ["admin", "office", "driver"],
    vertical: "manufacturing",
  },
  {
    id: "view_compliance_overdue",
    keywords: ["overdue compliance", "compliance overdue", "whats overdue"],
    title: "Overdue compliance items",
    subtitle: "",
    icon: "alert-triangle",
    type: "NAV",
    route: "/compliance?filter=overdue",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },
  {
    id: "open_morning_briefing",
    keywords: ["morning briefing", "briefing", "whats happening today"],
    title: "Morning briefing",
    subtitle: "Today's operational overview",
    icon: "sun",
    type: "NAV",
    route: "/",
    roles: ["admin", "office", "production", "driver"],
    vertical: "manufacturing",
  },
  {
    id: "call_customer",
    keywords: ["call", "phone", "contact"],
    title: "Call customer",
    subtitle: "Open phone",
    icon: "phone",
    type: "ACTION",
    roles: ["admin", "office", "driver"],
    vertical: "manufacturing",
  },
  {
    id: "nav_orders",
    keywords: ["go to orders", "open orders", "order station"],
    title: "Order Station",
    icon: "zap",
    type: "NAV",
    route: "/orders",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },
  {
    id: "nav_scheduling",
    keywords: ["go to scheduling", "scheduling board", "open scheduling"],
    title: "Scheduling Board",
    icon: "calendar",
    type: "NAV",
    route: "/scheduling",
    roles: ["admin", "office", "driver"],
    vertical: "manufacturing",
  },
  {
    id: "nav_compliance",
    keywords: ["go to compliance", "open compliance", "compliance hub"],
    title: "Compliance Hub",
    icon: "shield",
    type: "NAV",
    route: "/compliance",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },
  {
    id: "nav_production",
    keywords: ["go to production", "production board", "open production"],
    title: "Production Board",
    icon: "layers",
    type: "NAV",
    route: "/production",
    roles: ["admin", "production"],
    vertical: "manufacturing",
  },
  {
    id: "nav_crm",
    keywords: ["go to crm", "open crm", "customers", "funeral homes"],
    title: "CRM",
    icon: "users",
    type: "NAV",
    route: "/crm",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },

  // ──────────────────────────────────────────────────────────────
  // DISINTERMENTS
  // ──────────────────────────────────────────────────────────────
  {
    id: "nav_disinterments",
    keywords: [
      "disinterment",
      "disinterments",
      "exhumation",
      "open disinterment",
      "disinterment order",
    ],
    title: "Disinterments",
    subtitle: "View and manage disinterment orders",
    icon: "clipboard-list",
    type: "NAV",
    route: "/compliance/disinterments",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },
  // create_disinterment removed — covered by wf_create_order.

  // ──────────────────────────────────────────────────────────────
  // FINANCIAL REPORTS (admin only)
  // ──────────────────────────────────────────────────────────────
  {
    id: "report_ar_aging",
    keywords: [
      "ar aging",
      "accounts receivable",
      "aging report",
      "outstanding invoices",
      "overdue",
    ],
    title: "AR Aging Report",
    subtitle: "Accounts receivable by age",
    icon: "bar-chart",
    type: "NAV",
    route: "/ar/aging",
    roles: ["admin"],
    vertical: "manufacturing",
  },
  {
    id: "report_ap_aging",
    keywords: ["ap aging", "accounts payable", "bills aging"],
    title: "AP Aging Report",
    subtitle: "Accounts payable by age",
    icon: "bar-chart",
    type: "NAV",
    route: "/ap/aging",
    roles: ["admin"],
    vertical: "manufacturing",
  },
  {
    id: "report_revenue",
    keywords: [
      "revenue report",
      "sales report",
      "revenue by product",
      "revenue by customer",
      "monthly revenue",
    ],
    title: "Revenue Report",
    icon: "trending-up",
    type: "NAV",
    route: "/reports",
    roles: ["admin"],
    vertical: "manufacturing",
  },
  {
    id: "run_statements",
    keywords: [
      "run statements",
      "monthly statements",
      "statements",
      "ar statements",
      "customer statements",
    ],
    title: "Run Monthly Statements",
    icon: "file-text",
    type: "ACTION",
    route: "/ar/statements",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },

  // ──────────────────────────────────────────────────────────────
  // COMPLIANCE SUBMODULES
  // ──────────────────────────────────────────────────────────────
  {
    id: "nav_safety",
    keywords: [
      "safety",
      "osha",
      "safety programs",
      "written programs",
      "training matrix",
    ],
    title: "Safety & OSHA",
    icon: "shield",
    type: "NAV",
    route: "/safety",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },
  {
    id: "nav_vehicles",
    keywords: [
      "vehicles",
      "dot",
      "fleet",
      "vehicle registry",
      "hut",
      "dot registration",
    ],
    title: "Vehicle & DOT",
    icon: "truck",
    type: "NAV",
    route: "/compliance",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },
  {
    id: "nav_npca",
    keywords: [
      "npca",
      "plant certification",
      "npca audit",
      "concrete certification",
    ],
    title: "NPCA Certification",
    icon: "award",
    type: "NAV",
    route: "/compliance",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },
  {
    id: "audit_prep",
    keywords: [
      "audit prep",
      "run audit prep",
      "compliance audit",
      "generate audit package",
      "audit report",
    ],
    title: "Run Audit Prep",
    subtitle: "Generate compliance audit package",
    icon: "file-search",
    type: "ACTION",
    route: "/compliance",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },
  {
    id: "nav_incidents",
    keywords: ["incidents", "safety incident", "incident report", "osha 300"],
    title: "Safety Incidents",
    icon: "alert-triangle",
    type: "NAV",
    route: "/safety/incidents",
    roles: ["admin", "office", "production"],
    vertical: "manufacturing",
  },
  {
    id: "create_incident",
    keywords: ["log incident", "new incident", "report incident"],
    title: "Log safety incident",
    icon: "plus-circle",
    type: "ACTION",
    route: "/safety/incidents/new",
    roles: ["admin", "office", "production"],
    vertical: "manufacturing",
  },
  {
    id: "nav_training",
    keywords: ["training", "safety training", "osha training", "toolbox talks"],
    title: "Safety Training",
    icon: "book-open",
    type: "NAV",
    route: "/safety/training",
    roles: ["admin", "office", "production"],
    vertical: "manufacturing",
  },

  // ──────────────────────────────────────────────────────────────
  // SOCIAL SERVICE CERTIFICATES
  // ──────────────────────────────────────────────────────────────
  {
    id: "nav_ss_certs",
    keywords: [
      "social service",
      "ss certificate",
      "social service certificate",
      "ss cert",
    ],
    title: "Social Service Certificates",
    icon: "file-check",
    type: "NAV",
    route: "/social-service-certificates",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },

  // ──────────────────────────────────────────────────────────────
  // SETTINGS
  // ──────────────────────────────────────────────────────────────
  {
    id: "settings_programs",
    keywords: [
      "programs",
      "wilbert programs",
      "program settings",
      "vault program",
      "urn program",
      "casket program",
    ],
    title: "Program Settings",
    icon: "settings",
    type: "NAV",
    route: "/settings/programs",
    roles: ["admin"],
    vertical: "manufacturing",
  },
  {
    id: "settings_locations",
    keywords: [
      "locations",
      "location settings",
      "manage locations",
      "add location",
      "plants",
    ],
    title: "Location Settings",
    icon: "map-pin",
    type: "NAV",
    route: "/settings/locations",
    roles: ["admin"],
    vertical: "manufacturing",
  },
  {
    id: "settings_team",
    keywords: [
      "team",
      "users",
      "invite user",
      "manage team",
      "add user",
      "team settings",
    ],
    title: "Team Settings",
    icon: "users",
    type: "NAV",
    route: "/team",
    roles: ["admin"],
    vertical: "manufacturing",
  },
  {
    id: "settings_product_lines",
    keywords: [
      "product lines",
      "extensions",
      "redi-rock",
      "wastewater",
      "activate product line",
    ],
    title: "Product Lines",
    icon: "package",
    type: "NAV",
    route: "/settings/product-lines",
    roles: ["admin"],
    vertical: "manufacturing",
  },
  {
    id: "settings_tax",
    keywords: ["tax settings", "tax rates", "sales tax", "tax jurisdictions"],
    title: "Tax Settings",
    icon: "percent",
    type: "NAV",
    route: "/settings/tax",
    roles: ["admin"],
    vertical: "manufacturing",
  },
  {
    id: "settings_invoice",
    keywords: ["invoice settings", "invoice template", "invoice design"],
    title: "Invoice Settings",
    icon: "file-text",
    type: "NAV",
    route: "/settings/invoice",
    roles: ["admin"],
    vertical: "manufacturing",
  },
  {
    id: "settings_email",
    keywords: ["email settings", "email config", "smtp", "platform email"],
    title: "Email Settings",
    icon: "mail",
    type: "NAV",
    route: "/settings/email",
    roles: ["admin"],
    vertical: "manufacturing",
  },
  {
    id: "settings_call_intelligence",
    keywords: ["call intelligence", "ringcentral", "phone integration"],
    title: "Call Intelligence Settings",
    icon: "phone",
    type: "NAV",
    route: "/settings/call-intelligence",
    roles: ["admin"],
    vertical: "manufacturing",
  },

  // ──────────────────────────────────────────────────────────────
  // INVOICES
  // ──────────────────────────────────────────────────────────────
  {
    id: "nav_invoices",
    keywords: ["invoices", "ar invoices", "open invoice", "invoice list"],
    title: "Invoices",
    icon: "file-text",
    type: "NAV",
    route: "/ar/invoices",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },
  {
    id: "review_invoices",
    keywords: ["review invoices", "draft invoices", "invoice review queue"],
    title: "Review Invoices",
    subtitle: "Pending invoice approvals",
    icon: "check-square",
    type: "NAV",
    route: "/ar/invoices/review",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },
  {
    id: "nav_payments",
    keywords: ["payments", "customer payments", "ar payments"],
    title: "Customer Payments",
    icon: "dollar-sign",
    type: "NAV",
    route: "/ar/payments",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },
  {
    id: "nav_quotes",
    keywords: ["quotes", "estimates"],
    title: "Quotes",
    icon: "file-text",
    type: "NAV",
    route: "/ar/quotes",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },

  // ──────────────────────────────────────────────────────────────
  // AP (bills + vendor payments)
  // ──────────────────────────────────────────────────────────────
  {
    id: "nav_bills",
    keywords: ["bills", "vendor bills", "ap bills"],
    title: "Vendor Bills",
    icon: "file-text",
    type: "NAV",
    route: "/ap/bills",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },
  {
    id: "nav_purchase_orders",
    keywords: ["purchase orders", "po", "pos"],
    title: "Purchase Orders",
    icon: "shopping-cart",
    type: "NAV",
    route: "/ap/purchase-orders",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },
  {
    id: "nav_vendor_payments",
    keywords: ["vendor payments", "ap payments", "pay vendor"],
    title: "Vendor Payments",
    icon: "dollar-sign",
    type: "NAV",
    route: "/ap/payments",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },

  // ──────────────────────────────────────────────────────────────
  // PRODUCTS
  // ──────────────────────────────────────────────────────────────
  {
    id: "nav_products",
    keywords: ["products", "product catalog", "catalog", "skus", "price list"],
    title: "Product Catalog",
    icon: "package",
    type: "NAV",
    route: "/products",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },

  // ──────────────────────────────────────────────────────────────
  // KNOWLEDGE BASE
  // ──────────────────────────────────────────────────────────────
  {
    id: "nav_knowledge_base",
    keywords: [
      "knowledge base",
      "knowledge",
      "docs",
      "documentation",
      "kb",
    ],
    title: "Knowledge Base",
    icon: "book-open",
    type: "NAV",
    route: "/knowledge-base",
    roles: ["admin", "office", "production", "driver"],
    vertical: "manufacturing",
  },

  // ──────────────────────────────────────────────────────────────
  // URNS (Resale)
  // ──────────────────────────────────────────────────────────────
  // create_urn_order removed — covered by wf_create_order.
  {
    id: "nav_urns",
    keywords: ["urns", "urn catalog", "urn orders", "resale"],
    title: "Urn Catalog",
    icon: "package",
    type: "NAV",
    route: "/urns/catalog",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },

  // ──────────────────────────────────────────────────────────────
  // EMPLOYEES / TEAM
  // ──────────────────────────────────────────────────────────────
  {
    id: "nav_team",
    keywords: ["team", "employees", "staff", "team members", "personnel"],
    title: "Team",
    icon: "users",
    type: "NAV",
    route: "/team",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },

  // ──────────────────────────────────────────────────────────────
  // SPRING BURIALS
  // ──────────────────────────────────────────────────────────────
  {
    id: "nav_spring_burials",
    keywords: ["spring burials", "spring burial list", "seasonal burials"],
    title: "Spring Burials",
    icon: "calendar",
    type: "NAV",
    route: "/spring-burials",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },

  // ──────────────────────────────────────────────────────────────
  // TRANSFERS (Cross-licensee)
  // ──────────────────────────────────────────────────────────────
  {
    id: "nav_transfers",
    keywords: ["transfers", "cross licensee", "licensee transfer"],
    title: "Transfers",
    icon: "repeat",
    type: "NAV",
    route: "/transfers",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },

  // ──────────────────────────────────────────────────────────────
  // CALLS
  // ──────────────────────────────────────────────────────────────
  {
    id: "nav_call_log",
    keywords: ["call log", "calls", "recent calls", "phone history"],
    title: "Call Log",
    icon: "phone",
    type: "NAV",
    route: "/calls",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },

  // ──────────────────────────────────────────────────────────────
  // AGENTS
  // ──────────────────────────────────────────────────────────────
  {
    id: "nav_agents",
    keywords: ["agents", "ai agents", "accounting agents"],
    title: "Accounting Agents",
    icon: "bot",
    type: "NAV",
    route: "/agents",
    roles: ["admin"],
    vertical: "manufacturing",
  },
];

// ──────────────────────────────────────────────────────────────────────
// Funeral Home vertical actions (FH-1a)
// ──────────────────────────────────────────────────────────────────────
export const funeralHomeActions: CommandAction[] = [
  {
    id: "fh_new_arrangement",
    keywords: ["new arrangement", "new case", "first call", "create case", "start arrangement"],
    title: "New Arrangement",
    subtitle: "Create a new funeral case",
    icon: "plus-circle",
    type: "ACTION",
    route: "/fh/cases",
    roles: ["admin", "director"],
    vertical: "funeral_home",
  },
  {
    id: "fh_nav_cases",
    keywords: ["cases", "all cases", "case list", "active cases"],
    title: "Cases",
    icon: "folder",
    type: "NAV",
    route: "/fh/cases",
    roles: ["admin", "director", "office"],
    vertical: "funeral_home",
  },
  {
    id: "fh_nav_home",
    keywords: ["home", "direction hub", "go home", "dashboard"],
    title: "Funeral Direction Hub",
    icon: "home",
    type: "NAV",
    route: "/fh",
    roles: ["admin", "director", "office"],
    vertical: "funeral_home",
  },
  {
    id: "fh_add_case_note",
    keywords: ["add note", "case note", "log note", "add to case"],
    title: "Add case note",
    subtitle: "Jot a note on the current case",
    icon: "file-text",
    type: "ACTION",
    handler: "addNoteToCurrentCase",
    roles: ["admin", "director"],
    vertical: "funeral_home",
  },
  {
    id: "fh_start_scribe",
    keywords: ["scribe", "start scribe", "record arrangement", "start recording"],
    title: "Start Scribe recording",
    subtitle: "Capture an arrangement conference",
    icon: "mic",
    type: "ACTION",
    handler: "openScribeForCurrentCase",
    roles: ["admin", "director"],
    vertical: "funeral_home",
  },
  {
    id: "fh_nav_services",
    keywords: ["services", "this week", "upcoming services", "schedule"],
    title: "Services this week",
    icon: "calendar",
    type: "NAV",
    route: "/fh",
    roles: ["admin", "director", "office"],
    vertical: "funeral_home",
  },
  {
    id: "fh_find_case",
    keywords: ["find case", "search case", "open case", "find family"],
    title: "Find case",
    icon: "search",
    type: "ACTION",
    route: "/fh/cases",
    roles: ["admin", "director", "office"],
    vertical: "funeral_home",
  },
  {
    id: "fh_network",
    keywords: ["network", "connections", "cemetery", "manufacturer", "crematory", "partners"],
    title: "Network",
    subtitle: "Connected cemeteries, manufacturers, crematories",
    icon: "link",
    type: "NAV",
    route: "/fh/settings/network",
    roles: ["admin", "director"],
    vertical: "funeral_home",
  },
  {
    id: "fh_approve_all",
    keywords: ["approve all", "story", "finalize", "finish arrangement"],
    title: "Approve all (Story step)",
    subtitle: "Finalize and send all orders",
    icon: "check-square",
    type: "ACTION",
    handler: "openStoryForCurrentCase",
    roles: ["admin", "director"],
    vertical: "funeral_home",
  },
]

/**
 * Filter actions by the current user's role.
 * Actions with no `roles` or empty `roles` array are visible to everyone.
 */
export function filterActionsByRole(
  actions: CommandAction[],
  userRole: string | undefined | null
): CommandAction[] {
  if (!userRole) return actions.filter((a) => !a.roles || a.roles.length === 0);
  return actions.filter((a) => {
    if (!a.roles || a.roles.length === 0) return true;
    return a.roles.includes(userRole);
  });
}

/**
 * Pick the right action registry for the current tenant's vertical.
 * FH tenants see ONLY funeral_home actions; manufacturer tenants see
 * manufacturing actions. Never mix the two.
 */
export function getActionsForVertical(vertical: string | null | undefined): CommandAction[] {
  const v = (vertical || "manufacturing").toLowerCase()
  if (v === "funeral_home" || v === "funeralhome") return funeralHomeActions;
  return manufacturingActions;
}

/** Fuzzy local match against registered actions */
export function matchLocalActions(
  input: string,
  actions: CommandAction[],
  maxResults = 5
): CommandAction[] {
  const lower = input.toLowerCase().trim();
  if (!lower) return [];

  const scored = actions
    .map((action) => {
      let score = 0;
      // Exact keyword match
      for (const kw of action.keywords) {
        if (lower === kw) {
          score = 100;
          break;
        }
        if (kw.includes(lower) || lower.includes(kw)) {
          score = Math.max(score, 70);
        }
        // Word overlap
        const kwWords = kw.split(" ");
        const inputWords = lower.split(" ");
        const overlap = inputWords.filter((w) =>
          kwWords.some((kw2) => kw2.includes(w) || w.includes(kw2))
        ).length;
        if (overlap > 0) {
          score = Math.max(score, (overlap / inputWords.length) * 60);
        }
      }
      // Title match
      if (action.title.toLowerCase().includes(lower)) {
        score = Math.max(score, 50);
      }
      return { action, score };
    })
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score);

  return scored.slice(0, maxResults).map((s) => s.action);
}
