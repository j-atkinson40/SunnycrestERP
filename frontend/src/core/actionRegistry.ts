export interface CommandAction {
  id: string;
  keywords: string[];
  title: string;
  subtitle?: string;
  icon: string;
  type: "ACTION" | "NAV" | "VIEW" | "RECORD" | "ASK";
  route?: string;
  prefillSchema?: Record<string, unknown>;
  handler?: () => void;
  roles: string[];
  vertical: string;
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
  {
    id: "create_order",
    keywords: ["create order", "new order", "add order", "order for"],
    title: "Create new order",
    subtitle: "Open order creation form",
    icon: "plus-circle",
    type: "ACTION",
    route: "/orders/new",
    roles: ["admin", "office"],
    vertical: "manufacturing",
  },
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
];

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
