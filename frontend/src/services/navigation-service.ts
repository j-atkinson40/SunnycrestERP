export interface NavItem {
  label: string;
  href: string;
  icon: string; // lucide icon name
  badge?: number | string;
  permission?: string;
  requiresModule?: string;
  requiresExtension?: string;
  functionalArea?: string; // employee must have this area assigned
  /**
   * The server-enforced AREA this item belongs to — the same vocabulary as
   * `roles.limited_to_areas` and the `area:` router tags, NOT the
   * `functionalArea` above.
   *
   * ⚠️ **THESE ARE TWO DIFFERENT CONCEPTS AND CONFLATING THEM IS THE BUG THIS
   * FIELD EXISTS TO FIX.** `functionalArea` comes from
   * `employee_profiles.functional_areas` and is a soft presentation hint;
   * `area` is the hard rule `enforce_area_limit` refuses by. On 2026-11-06 a
   * payroll-limited user saw Financials, Agents, Production, Resale, Knowledge
   * Base and Settings in her sidebar while the server returned 403 on all 551
   * endpoints behind them, because the sidebar was consulting the soft hint —
   * which was `[]` for her, and which the filter read as "unrestricted".
   *
   * ⚠️ UNTAGGED IS DENIED FOR A LIMITED USER, which mirrors the server: an
   * untagged route gets `reason="untagged"` and a 403. So a new nav item is
   * invisible to a limited user on the day it ships rather than visible until
   * someone notices, and the asymmetry points the safe way.
   */
  area?: string;
  adminOnly?: boolean; // only show for admin role
  requiresMultiLocation?: boolean; // only show when company has >1 location
  children?: NavItem[]; // nested sub-items shown when parent is expanded
  isHub?: boolean; // hub items get a slightly different visual treatment
  isDividerBefore?: boolean; // render a subtle divider line before this item
  isDividerAfter?: boolean; // render a subtle divider line after this item
  settingsGroup?: string; // group label inside the Settings section
  // Command Bar Platform Layer Phase 1: synonyms used by the command
  // bar registry to surface a nav item when the user types shorthand
  // (e.g. "AR" for "AR Aging"). Optional — items without aliases are
  // still discoverable via label + keyword substring match.
  aliases?: string[];
}

export interface NavSection {
  title: string;
  icon?: string;
  collapsible?: boolean;
  defaultCollapsed?: boolean;
  items: NavItem[];
}

export interface NavigationConfig {
  sections: NavSection[];
  mobileTabs: NavItem[];
  commandBarPlaceholder: string;
  quickPrompts: string[];
  presetLabel: string;
  presetAccent: string; // CSS color value
}

// Preset accent colors
const PRESET_ACCENTS: Record<string, string> = {
  manufacturing: "#475569", // slate-600
  funeral_home: "#78716c", // warm gray (stone-500)
  cemetery: "#166534", // green-800
  crematory: "#7f1d1d", // red-900/burgundy
};

const PRESET_LABELS: Record<string, string> = {
  manufacturing: "Manufacturing",
  funeral_home: "Funeral Home",
  cemetery: "Cemetery",
  crematory: "Crematory",
};

/**
 * Keep only the nav a user limited to `limitedToAreas` may actually reach.
 *
 * ⚠️ **ONE SOURCE OF TRUTH: `limitedToAreas` COMES FROM `/auth/me`, WHICH
 * REPORTS `roles.limited_to_areas` — the exact column `enforce_area_limit`
 * refuses by.** The frontend keeps no list of its own. James's ruling of
 * 2026-11-06: the menu is built from the same rule the server uses.
 *
 * ⚠️ `null` IS NOT `[]`. `null` means the role has no area limit — every
 * existing role, and the case that must stay byte-for-byte unchanged. `[]`
 * means limited to nothing, which no admin can configure today but which must
 * not read as unlimited if one ever can. A falsy check would conflate them,
 * and conflating them in the OTHER direction is precisely the bug being fixed:
 * `filterByPermission` read an empty `functional_areas` as "no restriction".
 *
 * ⚠️ UNTAGGED ITEMS ARE DROPPED, deliberately and fail-closed, mirroring the
 * server's treatment of an untagged route. This is applied as a post-pass over
 * the whole built config rather than threaded through the five per-vertical
 * builders, so it holds for funeral_home, cemetery and crematory too — a
 * parameter added to one builder is a rule that applies to one vertical.
 */
export function restrictNavToAreas(
  nav: NavigationConfig,
  limitedToAreas: string[] | null | undefined,
): NavigationConfig {
  // Not limited — including the `undefined` an older /auth/me payload sends.
  // ⚠️ Returns the SAME OBJECT, so an unlimited user's nav is not merely equal
  // but identical, and no filtering bug can reach them.
  if (limitedToAreas === null || limitedToAreas === undefined) return nav;

  const allowed = new Set(limitedToAreas);
  const keep = (item: NavItem): NavItem | null => {
    if (!item.area || !allowed.has(item.area)) {
      // A parent may be untagged while a child is reachable; keep the parent
      // only if pruning its children leaves something behind.
      const kids = (item.children || []).map(keep).filter((x): x is NavItem => x !== null);
      return kids.length > 0 ? { ...item, children: kids } : null;
    }
    const kids = item.children ? item.children.map(keep).filter((x): x is NavItem => x !== null) : undefined;
    return kids ? { ...item, children: kids } : { ...item };
  };

  return {
    ...nav,
    sections: nav.sections
      .map((sec) => ({
        ...sec,
        items: sec.items.map(keep).filter((x): x is NavItem => x !== null),
      }))
      .filter((sec) => sec.items.length > 0),
  };
}

/**
 * Where an area-limited user should land. `null` for everyone else.
 *
 * James's ruling: "Area-limited users land on their area (Payroll), never on
 * Home, until a payroll-limited home exists." Home's note endpoint is
 * `/briefings/*`, which the server refuses for her — so landing there shows an
 * error page as the first thing she sees after signing in.
 *
 * ⚠️ Derived from the SAME nav the sidebar renders, not from a second
 * area→route table. If her nav is empty there is nowhere to send her and this
 * returns null rather than inventing a route; the caller leaves her on the
 * default and she sees the honest error instead of a redirect loop.
 */
export function landingRouteForAreas(
  nav: NavigationConfig,
  limitedToAreas: string[] | null | undefined,
): string | null {
  if (limitedToAreas === null || limitedToAreas === undefined) return null;
  const restricted = restrictNavToAreas(nav, limitedToAreas);
  for (const sec of restricted.sections) {
    for (const item of sec.items) {
      if (item.href) return item.href;
      const kid = (item.children || []).find((c) => c.href);
      if (kid) return kid.href;
    }
  }
  return null;
}

export function getNavigation(
  vertical: string | null,
  enabledModules: Set<string>,
  permissions: Set<string>,
  tenantSettings?: Record<string, unknown>,
  functionalAreas?: Set<string>,
  isAdmin?: boolean,
  enabledExtensions?: Set<string>,
): NavigationConfig {
  const preset = vertical || "manufacturing";
  const settings = tenantSettings || {};
  const areas = functionalAreas || new Set<string>();
  const admin = isAdmin ?? false;
  const extensions = enabledExtensions || new Set<string>();

  switch (preset) {
    case "manufacturing":
      return getManufacturingNav(enabledModules, permissions, settings, areas, admin, extensions);
    case "funeral_home":
      return getFuneralHomeNav(enabledModules, permissions, admin);
    case "cemetery":
      return getCemeteryNav(enabledModules, permissions, admin);
    case "crematory":
      return getCrematoryNav(enabledModules, permissions, admin);
    default:
      return getManufacturingNav(enabledModules, permissions, settings, areas, admin, extensions);
  }
}

function getManufacturingNav(
  modules: Set<string>,
  perms: Set<string>,
  settings: Record<string, unknown> = {},
  areas: Set<string> = new Set(),
  isAdmin: boolean = false,
  _extensions: Set<string> = new Set(),
): NavigationConfig {
  const sections: NavSection[] = [];

  // ── Primary ──
  const primaryItems: NavItem[] = [
    { label: "Home", href: "/dashboard", icon: "Home" },
    // The Bridgeable Map (Tenant Ponder-Editor P2) — the map of what the
    // platform does; view for every user, editing gated in-page by role.
    { label: "Bridgeable Map", href: "/bridgeable-map", icon: "Map" },
    {
      label: "Order Station",
      href: "/order-station",
      icon: "Zap",
      permission: "ar.view",
      requiresModule: "sales",
    },
    {
      label: "Operations Board",
      href: "/console/operations",
      icon: "LayoutDashboard",
      permission: "operations_board.view",
      functionalArea: "production_log",
    },
    {
      label: "Scheduling Board",
      href: "/scheduling",
      icon: "Kanban",
      permission: "scheduling_board.view",
      requiresModule: "driver_delivery",
      functionalArea: "funeral_scheduling",
    },
    // Weekly payroll dues review. The permission is the whole gate here: a user
    // on the area-limited `payroll` role sees this item and nothing else in the
    // sidebar, because `filterByPermission` drops every other item she lacks.
    //
    // interim-entrance: remove when Opas can open this page. Opas stays
    // admin-only for now (James, 2026-11-03), so a nav item is this page's only
    // entrance and CLAUDE.md §11 requires the marker rather than silence.
    {
      label: "Payroll",
      href: "/payroll",
      icon: "Receipt",
      permission: "payroll.view",
      // The one tagged item today. Matches the `area:payroll` tag on the
      // payroll-reports router, which is what the server enforces.
      area: "payroll",
      aliases: ["payroll", "dues", "union dues"],
    },
  ];
  sections.push({
    title: "",
    items: filterByPermission(primaryItems, modules, perms, areas, isAdmin),
  });

  // ── Hubs (no section label — dividers handled in sidebar) ──
  const hasSyncError =
    settings.accounting_connection_status === "connected" &&
    settings.last_sync_error;

  const hubItems: NavItem[] = [
    {
      label: "Quoting",
      href: "/quoting",
      icon: "FileText",
      isHub: true,
      isDividerBefore: true,
      permission: "ar.view",
      requiresModule: "sales",
    },
    {
      label: "Financials",
      href: "/financials",
      icon: "BarChart3",
      isHub: true,
      functionalArea: "invoicing_ar",
      ...(hasSyncError ? { badge: "!" } : {}),
    },
    {
      label: "Agents",
      href: "/agents",
      icon: "Bot",
      functionalArea: "invoicing_ar",
    },
    // V-1c: CRM top-level hub removed. CRM is now a registered
    // Vault service — accessed via /vault/crm with its own sidebar
    // entry. Users with `customers.view` still reach it via the
    // Bridgeable Vault entry; legacy /crm paths redirect to
    // /vault/crm.
    {
      label: "Production",
      href: "/production-hub",
      icon: "Factory",
      isHub: true,
      functionalArea: "production_log",
    },
    {
      label: "Resale",
      href: "/resale",
      icon: "Store",
      isHub: true,
      requiresExtension: "urn_sales",
    },
    {
      label: "Compliance",
      href: "/compliance",
      icon: "ShieldCheck",
      isHub: true,
      permission: "safety.view",
      requiresModule: "safety_management",
    },
    // ── V-1a: Bridgeable Vault — cross-cutting platform-infrastructure hub ──
    // Peer to vertical hubs. Documents, Intelligence today; CRM,
    // Notifications, Accounting admin in later V-1 phases. Admin-only
    // gating matches the underlying routes' admin-gating.
    {
      label: "Bridgeable Vault",
      href: "/vault",
      icon: "Vault",
      isHub: true,
      isDividerAfter: true,
      adminOnly: true,
    },
  ];
  const filteredHubs = filterByPermission(hubItems, modules, perms, areas, isAdmin, _extensions);
  if (filteredHubs.length > 0) {
    // Set dividers on first/last of filtered items
    filteredHubs[0].isDividerBefore = true;
    filteredHubs[filteredHubs.length - 1].isDividerAfter = true;
    sections.push({ title: "", items: filteredHubs });
  }

  // ── Tools (Knowledge Base + Legacy Studio collapsible) ──
  const legacyChildren: NavItem[] = filterByPermission(
    [
      {
        label: "Proof Generator",
        href: "/legacy/generator",
        icon: "Wand2",
        permission: "legacy_studio.create",
      },
      {
        label: "Library",
        href: "/legacy/library",
        icon: "Library",
        permission: "legacy_studio.view",
      },
      {
        label: "Settings",
        href: "/legacy/settings",
        icon: "Settings2",
        permission: "legacy_studio.create",
      },
      {
        label: "Template Upload",
        href: "/legacy/templates/upload",
        icon: "Upload",
        permission: "legacy_studio.create",
      },
    ],
    modules,
    perms,
    areas,
    isAdmin,
  );

  // ── Resources (Knowledge Base + Training grouped together) ──
  // Nav cleanup: KB and Training were previously orphaned as their own top-level
  // sections. Consolidating them under one "Resources" label makes the sidebar
  // readable and keeps employees' shared reference material in one place.
  const resourceItems: NavItem[] = [
    {
      label: "Knowledge Base",
      href: "/knowledge-base",
      icon: "BookOpen",
    },
    {
      label: "Training",
      href: "/training",
      icon: "GraduationCap",
      permission: "training.view",
    },
  ];

  if (legacyChildren.length > 0) {
    // Legacy Studio stays nested here (where it already lived) — audit says
    // don't touch it, so we preserve placement.
    resourceItems.push({
      label: "Legacy Studio",
      href: "/legacy/generator",
      icon: "Gem",
      permission: "legacy.view",
      children: legacyChildren,
    });
  }

  sections.push({
    title: "Resources",
    items: filterByPermission(resourceItems, modules, perms, areas, isAdmin),
  });

  // ── Settings (collapsible, grouped sub-sections) ──
  sections.push({
    title: "Settings",
    collapsible: true,
    defaultCollapsed: true,
    items: filterByPermission(
      [
        // Business
        {
          label: "Company Profile",
          href: "/admin/settings",
          icon: "Building2",
          settingsGroup: "Business",
        },
        {
          label: "Branding",
          href: "/settings/branding",
          icon: "Gem",
          settingsGroup: "Business",
        },
        // People
        {
          label: "Team Dashboard",
          href: "/team",
          icon: "Users",
          permission: "users.view",
          settingsGroup: "People",
        },
        {
          label: "Employees",
          href: "/admin/users",
          icon: "UserCircle",
          permission: "users.view",
          settingsGroup: "People",
        },
        {
          label: "Users & Roles",
          href: "/admin/roles",
          icon: "ShieldCheck",
          permission: "settings.users.manage",
          settingsGroup: "People",
        },
        {
          label: "Permissions",
          href: "/admin/permissions",
          icon: "Lock",
          permission: "settings.users.manage",
          settingsGroup: "People",
        },
        // Communication
        {
          label: "Email",
          href: "/settings/email",
          icon: "MessageSquare",
          settingsGroup: "Communication",
        },
        // Integrations
        {
          label: "Call Intelligence",
          href: "/settings/call-intelligence",
          icon: "PhoneCall",
          settingsGroup: "Integrations",
        },
        {
          label: "Accounting",
          href: "/settings/integrations/accounting",
          icon: "Calculator",
          settingsGroup: "Integrations",
          ...(hasSyncError ? { badge: "\u2022" } : {}),
        },
        {
          // Honest label (Suite Session 2): /admin/accounting is the
          // accounting-provider connection page, not API key management.
          label: "Accounting Sync",
          href: "/admin/accounting",
          icon: "Plug",
          settingsGroup: "Integrations",
        },
        // Disinterment
        {
          label: "Disinterment",
          href: "/settings/disinterment",
          icon: "Skull",
          permission: "disinterment_settings.manage",
          requiresExtension: "disinterment_management",
          settingsGroup: "Integrations",
        },
        {
          label: "Union Rotations",
          href: "/settings/union-rotations",
          icon: "RefreshCcw",
          permission: "union_rotations.manage",
          requiresExtension: "disinterment_management",
          settingsGroup: "Integrations",
        },
        // Operations
        {
          // Ledger Posting L-2.1e. The Books Review blocked card tells an
          // operator to configure reconciliation GL; before this entry existed
          // the page was reachable only by URL, so the card named an action and
          // left them hunting. LABEL IS LOAD-BEARING — the card's copy says
          // "Settings → Financial Accounts" verbatim, and a cross-file test
          // (ReconciliationExceptionDisplay.test.tsx) fails if the two drift.
          label: "Financial Accounts",
          href: "/settings/accounts",
          icon: "Landmark",
          settingsGroup: "Operations",
        },
        {
          label: "Bank Categories",
          href: "/settings/bank-categories",
          icon: "Tags",
          settingsGroup: "Operations",
        },
        {
          label: "Programs & Products",
          href: "/settings/programs",
          icon: "Package",
          settingsGroup: "Operations",
        },
        {
          label: "Compliance Config",
          href: "/settings/compliance",
          icon: "ShieldCheck",
          settingsGroup: "Operations",
        },
        {
          label: "Workflows",
          href: "/settings/workflows",
          icon: "Zap",
          settingsGroup: "Operations",
        },
        // Network
        {
          label: "Locations",
          href: "/settings/locations",
          icon: "MapPin",
          adminOnly: true,
          requiresMultiLocation: true,
          settingsGroup: "Network",
        },
        // Platform
        {
          label: "Billing",
          href: "/settings/billing",
          icon: "Receipt",
          adminOnly: true,
          settingsGroup: "Platform",
        },
        {
          label: "Extensions",
          href: "/extensions",
          icon: "Puzzle",
          settingsGroup: "Platform",
        },
        {
          label: "Onboarding",
          // TAX-4: was `/onboarding`, which renders OnboardingFlow. The
          // per-tenant CHECKLIST — the 25 items, their status, the progress
          // — lives at `/onboarding/hub` (App.tsx:1364), one hop further than
          // the nav suggested. Both routes exist, so this was never a broken
          // link; it just pointed past the thing an admin comes here for.
          //
          // It also matters more than it did: the hub lazily calls
          // `initializeChecklist()` when a tenant has none, so opening it is
          // what brings a checklist into existence for tenants that predate
          // the seed-time instantiation.
          href: "/onboarding/hub",
          icon: "Rocket",
          adminOnly: true,
          settingsGroup: "Platform",
        },
        // ── V-1a: Documents + Intelligence admin surfaces moved to
        // Bridgeable Vault (/vault/*). The Settings → Platform subgroup
        // now contains only tenant-management entries (Billing,
        // Extensions, Onboarding).
      ],
      modules,
      perms,
      undefined,
      isAdmin,
      _extensions,
    ),
  });

  return {
    sections,
    mobileTabs: [
      { label: "Home", href: "/dashboard", icon: "Home" },
      { label: "Orders", href: "/order-station", icon: "Zap" },
      { label: "Schedule", href: "/scheduling", icon: "Kanban" },
      { label: "Financials", href: "/financials", icon: "BarChart3" },
      // V-1c: CRM tab → Vault (CRM now lives under /vault/crm).
      { label: "Vault", href: "/vault", icon: "Vault" },
      { label: "More", href: "#more", icon: "MoreHorizontal" },
    ],
    commandBarPlaceholder: "Order, schedule, log production...",
    quickPrompts: ["Log today's production", "New order", "Check inventory"],
    presetLabel: PRESET_LABELS.manufacturing,
    presetAccent: PRESET_ACCENTS.manufacturing,
  };
}

function getFuneralHomeNav(
  modules: Set<string>,
  perms: Set<string>,
  isAdmin: boolean = false,
): NavigationConfig {
  const sections: NavSection[] = [];

  // Primary
  const caseItems: NavItem[] = [
    { label: "Home", href: "/dashboard", icon: "Home" },
    // fh-case-table-split fix (2026-07): the FH sidebar now wires up
    // the canonical FH-1 list (/fh/cases → funeral_cases). Previously
    // it pointed at the legacy /cases surface (superseded fh_cases
    // table, 0 rows post-repoint) and the canonical route had ZERO
    // nav references — directors could only reach real cases via the
    // command bar. "New Case" is dropped: there is no canonical
    // standalone create route (create lives on the /fh/cases list; NL
    // creation via the command bar is the primary path).
    {
      label: "Active Cases",
      href: "/fh/cases",
      icon: "FolderOpen",
      permission: "fh_cases.view",
    },
  ];
  if (modules.has("ai_obituary_builder")) {
    caseItems.push({
      label: "Obituaries",
      href: "/funeral-home/obituaries",
      icon: "FileText",
    });
  }
  sections.push({
    title: "Cases",
    items: filterByPermission(caseItems, modules, perms, undefined, isAdmin),
  });

  // Hubs
  // V-1c: CRM top-level hub removed. CRM accessed via /vault/crm
  // (Vault Hub sidebar). Permission gate preserved on the Vault
  // service descriptor.
  const hubItems: NavItem[] = [
    { label: "Financials", href: "/financials", icon: "BarChart3", isHub: true, isDividerBefore: true },
    // V-1a: Bridgeable Vault — cross-cutting platform-infrastructure hub.
    { label: "Bridgeable Vault", href: "/vault", icon: "Vault", isHub: true, adminOnly: true, isDividerAfter: true },
  ];
  const filteredHubs = filterByPermission(hubItems, modules, perms, undefined, isAdmin);
  if (filteredHubs.length > 0) {
    filteredHubs[0].isDividerBefore = true;
    filteredHubs[filteredHubs.length - 1].isDividerAfter = true;
    sections.push({ title: "", items: filteredHubs });
  }

  // Compliance
  const complianceItems = filterByPermission(
    [
      {
        label: "FTC Compliance",
        href: "/funeral-home/compliance",
        icon: "Scale",
        permission: "fh_compliance.view",
      },
    ],
    modules,
    perms,
  );
  if (complianceItems.length > 0) {
    sections.push({ title: "Compliance", items: complianceItems });
  }

  // Team
  const teamItems = filterByPermission(
    [
      {
        label: "Directors & Staff",
        href: "/admin/users",
        icon: "UserCircle",
        permission: "users.view",
      },
    ],
    modules,
    perms,
  );
  if (teamItems.length > 0) {
    sections.push({ title: "Team", items: teamItems });
  }

  // Settings
  sections.push({
    title: "Settings",
    collapsible: true,
    defaultCollapsed: true,
    items: filterByPermission(
      [
        { label: "Company Profile", href: "/admin/settings", icon: "Building2" },
        {
          label: "Price List",
          href: "/funeral-home/price-list",
          icon: "ListOrdered",
          permission: "fh_price_list.view",
        },
        { label: "Integrations", href: "/admin/accounting", icon: "Plug" },
        { label: "Extensions", href: "/extensions", icon: "Puzzle" },
        // V-1d: Notifications moved to /vault/notifications (full
        // Vault service). Reachable through the Vault hub sidebar,
        // the bell icon dropdown, and the vault_notifications widget
        // on the Vault Overview — no longer a top-level nav entry.
      ],
      modules,
      perms,
    ),
  });

  return {
    sections,
    mobileTabs: [
      { label: "Home", href: "/dashboard", icon: "Home" },
      // fh-case-table-split fix (2026-07): canonical FH-1 list.
      { label: "Cases", href: "/fh/cases", icon: "FolderOpen" },
      { label: "Financials", href: "/financials", icon: "BarChart3" },
      // V-1c: CRM tab → Vault (CRM now lives under /vault/crm).
      { label: "Vault", href: "/vault", icon: "Vault" },
      { label: "More", href: "#more", icon: "MoreHorizontal" },
    ],
    commandBarPlaceholder: "First call, order vault, record payment...",
    quickPrompts: [
      "First call from the Johnson family...",
      "Order vault for the Johnson case",
      "Record payment from the Johnson family",
    ],
    presetLabel: PRESET_LABELS.funeral_home,
    presetAccent: PRESET_ACCENTS.funeral_home,
  };
}

function getCemeteryNav(
  modules: Set<string>,
  perms: Set<string>,
  _isAdmin: boolean = false,
): NavigationConfig {
  const sections: NavSection[] = [];

  sections.push({
    title: "Operations",
    items: filterByPermission(
      [
        { label: "Home", href: "/dashboard", icon: "Home" },
        { label: "Interments", href: "/interments", icon: "MapPin" },
        { label: "Plot Map", href: "/plots", icon: "Map" },
        { label: "Deeds", href: "/deeds", icon: "FileText" },
      ],
      modules,
      perms,
    ),
  });

  // Hubs — Cemetery + V-1a Bridgeable Vault
  const hubItems: NavItem[] = [
    { label: "Financials", href: "/financials", icon: "BarChart3", isHub: true, isDividerBefore: true },
    { label: "Bridgeable Vault", href: "/vault", icon: "Vault", isHub: true, adminOnly: true, isDividerAfter: true },
  ];
  const filteredCemHubs = filterByPermission(hubItems, modules, perms, undefined, _isAdmin);
  if (filteredCemHubs.length > 0) {
    filteredCemHubs[0].isDividerBefore = true;
    filteredCemHubs[filteredCemHubs.length - 1].isDividerAfter = true;
    sections.push({ title: "", items: filteredCemHubs });
  }

  sections.push({
    title: "Settings",
    collapsible: true,
    defaultCollapsed: true,
    items: filterByPermission(
      [
        { label: "Company Profile", href: "/admin/settings", icon: "Building2" },
        { label: "Extensions", href: "/extensions", icon: "Puzzle" },
      ],
      modules,
      perms,
    ),
  });

  return {
    sections,
    mobileTabs: [
      { label: "Home", href: "/dashboard", icon: "Home" },
      { label: "Interments", href: "/interments", icon: "MapPin" },
      { label: "Plots", href: "/plots", icon: "Map" },
      { label: "Financials", href: "/financials", icon: "BarChart3" },
      { label: "More", href: "#more", icon: "MoreHorizontal" },
    ],
    commandBarPlaceholder:
      "Schedule interment, update plot, record payment...",
    quickPrompts: ["Schedule interment", "Update plot", "Record payment"],
    presetLabel: PRESET_LABELS.cemetery,
    presetAccent: PRESET_ACCENTS.cemetery,
  };
}

function getCrematoryNav(
  modules: Set<string>,
  perms: Set<string>,
  _isAdmin: boolean = false,
): NavigationConfig {
  const sections: NavSection[] = [];

  sections.push({
    title: "Operations",
    items: filterByPermission(
      [
        { label: "Home", href: "/dashboard", icon: "Home" },
        { label: "Cases", href: "/crematory/cases", icon: "FolderOpen" },
        { label: "Schedule", href: "/crematory/schedule", icon: "Calendar" },
      ],
      modules,
      perms,
    ),
  });

  const complianceItems = filterByPermission(
    [
      { label: "Chain of Custody", href: "/crematory/custody", icon: "Link" },
    ],
    modules,
    perms,
  );
  if (complianceItems.length > 0) {
    sections.push({ title: "Compliance", items: complianceItems });
  }

  // Hubs — Crematory + V-1a Bridgeable Vault
  const hubItems: NavItem[] = [
    { label: "Financials", href: "/financials", icon: "BarChart3", isHub: true, isDividerBefore: true },
    { label: "Bridgeable Vault", href: "/vault", icon: "Vault", isHub: true, adminOnly: true, isDividerAfter: true },
  ];
  const filteredCremHubs = filterByPermission(hubItems, modules, perms, undefined, _isAdmin);
  if (filteredCremHubs.length > 0) {
    filteredCremHubs[0].isDividerBefore = true;
    filteredCremHubs[filteredCremHubs.length - 1].isDividerAfter = true;
    sections.push({ title: "", items: filteredCremHubs });
  }

  sections.push({
    title: "Settings",
    collapsible: true,
    defaultCollapsed: true,
    items: filterByPermission(
      [
        { label: "Company Profile", href: "/admin/settings", icon: "Building2" },
        { label: "Extensions", href: "/extensions", icon: "Puzzle" },
      ],
      modules,
      perms,
    ),
  });

  return {
    sections,
    mobileTabs: [
      { label: "Home", href: "/dashboard", icon: "Home" },
      { label: "Cases", href: "/crematory/cases", icon: "FolderOpen" },
      { label: "Schedule", href: "/crematory/schedule", icon: "Calendar" },
      { label: "Financials", href: "/financials", icon: "BarChart3" },
      { label: "More", href: "#more", icon: "MoreHorizontal" },
    ],
    commandBarPlaceholder: "New case, update status, schedule cremation...",
    quickPrompts: ["New case", "Update status", "Schedule cremation"],
    presetLabel: PRESET_LABELS.crematory,
    presetAccent: PRESET_ACCENTS.crematory,
  };
}

function filterByPermission(
  items: NavItem[],
  modules: Set<string>,
  perms: Set<string>,
  areas?: Set<string>,
  isAdmin?: boolean,
  extensions?: Set<string>,
): NavItem[] {
  return items.filter((item) => {
    // Admin-only items
    if (item.adminOnly && !isAdmin) return false;
    // Module gating
    if (item.requiresModule && !modules.has(item.requiresModule)) return false;
    // Extension gating
    if (item.requiresExtension && !(extensions || new Set<string>()).has(item.requiresExtension)) return false;
    // Permission gating (admins bypass)
    if (item.permission && !isAdmin && !perms.has(item.permission)) return false;
    // Functional area filtering — only applied when areas are configured
    if (item.functionalArea && areas && areas.size > 0) {
      // full_admin bypasses area restrictions
      if (!areas.has("full_admin") && !areas.has(item.functionalArea)) {
        return false;
      }
    }
    return true;
  });
}


// ── Command Bar Platform Layer Phase 1 — flat iteration ──────────────
//
// The backend registry (`backend/app/services/command_bar/registry.py`)
// hardcodes its own navigate actions today. This helper exists for two
// reasons:
//
//   1. Client-side fallback matching when the backend is reachable
//      but the user's tenant / role filters would hide the target in
//      the server response. The command bar can still suggest it as
//      a nav target (subject to frontend permission check).
//   2. Future Phase 2/3 work that needs to enumerate every route the
//      current user can see without a round-trip — e.g. pre-warming
//      a search index in the browser.
//
// This is a pure iteration — it flattens `sections[].items[]` + any
// `children[]` into a single list. Callers apply their own filtering.

export function getAllNavItemsFlat(nav: NavigationConfig): NavItem[] {
  const out: NavItem[] = [];
  const walk = (items: NavItem[]) => {
    for (const item of items) {
      out.push(item);
      if (item.children && item.children.length > 0) {
        walk(item.children);
      }
    }
  };
  for (const section of nav.sections) {
    walk(section.items);
  }
  return out;
}
