export interface NavItem {
  label: string;
  href: string;
  icon: string; // lucide icon name
  badge?: number | string;
  permission?: string;
  requiresModule?: string;
  functionalArea?: string; // employee must have this area assigned
  adminOnly?: boolean; // only show for admin role
  children?: NavItem[]; // nested sub-items shown when parent is expanded
  isHub?: boolean; // hub items get a slightly different visual treatment
  isDividerBefore?: boolean; // render a subtle divider line before this item
  isDividerAfter?: boolean; // render a subtle divider line after this item
  settingsGroup?: string; // group label inside the Settings section
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
      label: "Financials",
      href: "/financials",
      icon: "BarChart3",
      isHub: true,
      isDividerBefore: true,
      functionalArea: "invoicing_ar",
      ...(hasSyncError ? { badge: "!" } : {}),
    },
    {
      label: "CRM",
      href: "/crm",
      icon: "Building2",
      isHub: true,
      permission: "customers.view",
    },
    {
      label: "Production",
      href: "/production-hub",
      icon: "Factory",
      isHub: true,
      isDividerAfter: true,
      functionalArea: "production_log",
    },
  ];
  const filteredHubs = filterByPermission(hubItems, modules, perms, areas, isAdmin);
  if (filteredHubs.length > 0) {
    // Set dividers on first/last of filtered items
    filteredHubs[0].isDividerBefore = true;
    filteredHubs[filteredHubs.length - 1].isDividerAfter = true;
    sections.push({ title: "", items: filteredHubs });
  }

  // ── Disinterment (module-gated) ──
  const disintermentItems: NavItem[] = filterByPermission(
    [
      {
        label: "Disinterments",
        href: "/disinterments",
        icon: "Skull",
        permission: "disinterments.view",
        requiresModule: "disinterment_management",
        isDividerBefore: true,
      },
    ],
    modules,
    perms,
    areas,
    isAdmin,
  );
  if (disintermentItems.length > 0) {
    sections.push({ title: "", items: disintermentItems });
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

  const toolItems: NavItem[] = [
    {
      label: "Knowledge Base",
      href: "/knowledge-base",
      icon: "BookOpen",
    },
  ];

  if (legacyChildren.length > 0) {
    toolItems.push({
      label: "Legacy Studio",
      href: "/legacy/generator",
      icon: "Gem",
      permission: "legacy.view",
      children: legacyChildren,
    });
  }

  sections.push({
    title: "Tools",
    items: filterByPermission(toolItems, modules, perms, areas, isAdmin),
  });

  // ── Training (single hub item) ──
  sections.push({
    title: "Training",
    items: filterByPermission(
      [
        {
          label: "Training",
          href: "/training",
          icon: "GraduationCap",
          permission: "training.view",
        },
      ],
      modules,
      perms,
      areas,
      isAdmin,
    ),
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
          label: "API Keys",
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
          requiresModule: "disinterment_management",
          settingsGroup: "Integrations",
        },
        {
          label: "Union Rotations",
          href: "/settings/union-rotations",
          icon: "RefreshCcw",
          permission: "union_rotations.manage",
          requiresModule: "union_rotation",
          settingsGroup: "Integrations",
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
          href: "/onboarding",
          icon: "Rocket",
          adminOnly: true,
          settingsGroup: "Platform",
        },
      ],
      modules,
      perms,
      undefined,
      isAdmin,
    ),
  });

  return {
    sections,
    mobileTabs: [
      { label: "Home", href: "/dashboard", icon: "Home" },
      { label: "Orders", href: "/order-station", icon: "Zap" },
      { label: "Schedule", href: "/scheduling", icon: "Kanban" },
      { label: "Financials", href: "/financials", icon: "BarChart3" },
      { label: "CRM", href: "/crm", icon: "Building2" },
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
    {
      label: "Active Cases",
      href: "/cases",
      icon: "FolderOpen",
      permission: "fh_cases.view",
    },
    {
      label: "New Case",
      href: "/cases/new",
      icon: "Plus",
      permission: "fh_cases.create",
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
  const hubItems: NavItem[] = [
    { label: "Financials", href: "/financials", icon: "BarChart3", isHub: true, isDividerBefore: true },
    { label: "CRM", href: "/crm", icon: "Building2", isHub: true, permission: "customers.view", isDividerAfter: true },
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
        { label: "Notifications", href: "/notifications", icon: "Bell" },
      ],
      modules,
      perms,
    ),
  });

  return {
    sections,
    mobileTabs: [
      { label: "Home", href: "/dashboard", icon: "Home" },
      { label: "Cases", href: "/cases", icon: "FolderOpen" },
      { label: "Financials", href: "/financials", icon: "BarChart3" },
      { label: "CRM", href: "/crm", icon: "Building2" },
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

  // Hubs
  const hubItems: NavItem[] = [
    { label: "Financials", href: "/financials", icon: "BarChart3", isHub: true, isDividerBefore: true, isDividerAfter: true },
  ];
  sections.push({ title: "", items: hubItems });

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

  // Hubs
  const hubItems: NavItem[] = [
    { label: "Financials", href: "/financials", icon: "BarChart3", isHub: true, isDividerBefore: true, isDividerAfter: true },
  ];
  sections.push({ title: "", items: hubItems });

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
): NavItem[] {
  return items.filter((item) => {
    // Admin-only items
    if (item.adminOnly && !isAdmin) return false;
    // Module gating
    if (item.requiresModule && !modules.has(item.requiresModule)) return false;
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
