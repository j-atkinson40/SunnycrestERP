export interface NavItem {
  label: string;
  href: string;
  icon: string; // lucide icon name
  badge?: number | string;
  permission?: string;
  requiresModule?: string;
  functionalArea?: string; // employee must have this area assigned
  children?: NavItem[]; // nested sub-items shown when parent is expanded
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
): NavigationConfig {
  const preset = vertical || "manufacturing";
  const settings = tenantSettings || {};
  const areas = functionalAreas || new Set<string>();

  switch (preset) {
    case "manufacturing":
      return getManufacturingNav(enabledModules, permissions, settings, areas);
    case "funeral_home":
      return getFuneralHomeNav(enabledModules, permissions);
    case "cemetery":
      return getCemeteryNav(enabledModules, permissions);
    case "crematory":
      return getCrematoryNav(enabledModules, permissions);
    default:
      return getManufacturingNav(enabledModules, permissions, settings, areas);
  }
}

function getManufacturingNav(
  modules: Set<string>,
  perms: Set<string>,
  settings: Record<string, unknown> = {},
  areas: Set<string> = new Set(),
): NavigationConfig {
  const sections: NavSection[] = [];

  // Operations
  const opsItems: NavItem[] = [
    { label: "Dashboard", href: "/dashboard", icon: "LayoutDashboard" },
    {
      label: "Announcements",
      href: "/announcements",
      icon: "Megaphone",
    },
    {
      label: "Order Station",
      href: "/order-station",
      icon: "Zap",
      permission: "ar.view",
      requiresModule: "sales",
    },
    {
      label: "Orders",
      href: "/ar/orders",
      icon: "ClipboardList",
      permission: "orders.view",
    },
    {
      label: "Customers",
      href: "/customers",
      icon: "Users",
      permission: "customers.view",
      functionalArea: "customer_management",
    },
    {
      label: "Products",
      href: "/products",
      icon: "Package",
      permission: "products.view",
    },
    {
      label: "Scheduling Board",
      href: "/scheduling",
      icon: "Kanban",
      permission: "deliveries.view",
      requiresModule: "driver_delivery",
      functionalArea: "funeral_scheduling",
    },
    {
      label: "Inventory",
      href: "/inventory",
      icon: "Package",
      permission: "inventory.view",
      functionalArea: "production_log",
    },
    {
      label: "Production Log",
      href: "/production-log",
      icon: "Factory",
      permission: "production_log.view",
      requiresModule: "daily_production_log",
      functionalArea: "production_log",
    },
    {
      label: "Operations Board",
      href: "/console/operations",
      icon: "LayoutDashboard",
      functionalArea: "production_log",
    },
    // Transfers moved to Orders page tab — no standalone nav item
  ];

  // Extension-added items
  if (modules.has("work_orders")) {
    opsItems.push({
      label: "Work Orders",
      href: "/work-orders",
      icon: "Wrench",
      permission: "work_orders.view",
    });
    opsItems.push({
      label: "Production Board",
      href: "/production",
      icon: "Kanban",
      permission: "work_orders.view",
    });
  }

  sections.push({
    title: "Operations",
    items: filterByPermission(opsItems, modules, perms, areas),
  });

  // Compliance
  const complianceItems: NavItem[] = [
    {
      label: "Safety & OSHA",
      href: "/safety",
      icon: "ShieldCheck",
      permission: "safety.view",
      requiresModule: "safety_management",
      functionalArea: "safety_compliance",
      children: [
        { label: "Dashboard", href: "/safety", icon: "LayoutDashboard" },
        { label: "Training Calendar", href: "/safety/training/calendar", icon: "CalendarDays" },
        { label: "Inspections", href: "/safety/inspections/new", icon: "ClipboardCheck" },
        { label: "Toolbox Talks", href: "/safety/toolbox-talks", icon: "MessageSquare" },
        { label: "Incidents", href: "/safety/incidents", icon: "AlertTriangle" },
        { label: "Safety Notices", href: "/safety/notices", icon: "ShieldAlert" },
        { label: "OSHA 300 Log", href: "/safety/osha-300", icon: "FileText" },
        { label: "SDS / HazCom", href: "/safety/chemicals", icon: "FlaskConical" },
        { label: "LOTO Procedures", href: "/safety/loto", icon: "Lock" },
        { label: "Programs", href: "/safety/programs", icon: "BookOpen" },
      ],
    },
  ];
  if (modules.has("npca_audit_prep")) {
    complianceItems.push({
      label: "NPCA Audit Prep",
      href: "/npca",
      icon: "Award",
      permission: "npca.view",
      requiresModule: "npca_audit_prep",
    });
  }
  const filteredCompliance = filterByPermission(
    complianceItems,
    modules,
    perms,
    areas,
  );
  if (filteredCompliance.length > 0) {
    sections.push({ title: "Compliance", items: filteredCompliance });
  }

  // Training
  sections.push({
    title: "Training",
    items: [
      {
        label: "Procedure Library",
        href: "/training/procedures",
        icon: "BookOpen",
      },
    ],
  });

  // Finance
  const hasSyncError =
    settings.accounting_connection_status === "connected" &&
    settings.last_sync_error;
  const financeItems = filterByPermission(
    [
      {
        label: "Financials Board",
        href: "/financials",
        icon: "BarChart3",
        functionalArea: "invoicing_ar",
      },
      {
        label: "Billing",
        href: "/billing",
        icon: "Receipt",
        permission: "invoices.view",
        functionalArea: "invoicing_ar",
        ...(hasSyncError ? { badge: "!" } : {}),
      },
      {
        label: "Invoice Review",
        href: "/ar/invoices/review",
        icon: "ClipboardCheck",
        permission: "ar.create_invoice",
        functionalArea: "invoicing_ar",
      },
      {
        label: "Vendors & Bills",
        href: "/ap/bills",
        icon: "Receipt",
        permission: "ap.view",
        functionalArea: "invoicing_ar",
      },
      {
        label: "Journal Entries",
        href: "/journal-entries",
        icon: "BookOpen",
        functionalArea: "invoicing_ar",
      },
      {
        label: "Reports",
        href: "/reports",
        icon: "PieChart",
        functionalArea: "invoicing_ar",
      },
    ],
    modules,
    perms,
    areas,
  );
  if (financeItems.length > 0) {
    sections.push({ title: "Finance", items: financeItems });
  }

  // Team
  const teamItems = filterByPermission(
    [
      {
        label: "Employees",
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
        {
          label: "Team Intelligence",
          href: "/settings/team-intelligence",
          icon: "BrainCircuit",
        },
        {
          label: "Company Profile",
          href: "/admin/settings",
          icon: "Building2",
        },
        {
          label: "Integrations",
          href: "/admin/accounting",
          icon: "Plug",
        },
        {
          label: "Accounting",
          href: "/settings/integrations/accounting",
          icon: "Calculator",
          ...(hasSyncError ? { badge: "\u2022" } : {}),
        },
        {
          label: "Charge Library",
          href: "/settings/charges",
          icon: "CircleDollarSign",
          permission: "products.view",
        },
        {
          label: "Tax Configuration",
          href: "/settings/tax",
          icon: "Percent",
          functionalArea: "invoicing_ar",
        },
        {
          label: "Financial Accounts",
          href: "/settings/accounts",
          icon: "Landmark",
          functionalArea: "invoicing_ar",
        },
        { label: "Extensions", href: "/extensions", icon: "Puzzle" },
        {
          label: "Network Preferences",
          href: "/settings/network/preferences",
          icon: "Link",
        },
        {
          label: "Notifications",
          href: "/notifications",
          icon: "Bell",
        },
      ],
      modules,
      perms,
    ),
  });

  return {
    sections,
    mobileTabs: [
      { label: "Orders", href: "/ar/orders", icon: "ClipboardList" },
      { label: "Schedule", href: "/scheduling", icon: "Kanban" },
      { label: "Inventory", href: "/inventory", icon: "Package" },
      { label: "Production", href: "/production-log", icon: "Factory" },
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
): NavigationConfig {
  const sections: NavSection[] = [];

  // Cases
  const caseItems: NavItem[] = [
    { label: "Dashboard", href: "/dashboard", icon: "LayoutDashboard" },
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
    items: filterByPermission(caseItems, modules, perms),
  });

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

  // Finance
  const financeItems = filterByPermission(
    [
      { label: "Financials Board", href: "/financials", icon: "BarChart3" },
      {
        label: "Billing",
        href: "/billing",
        icon: "Receipt",
        permission: "fh_invoices.view",
      },
      {
        label: "Vendors & Bills",
        href: "/ap/bills",
        icon: "Receipt",
        permission: "ap.view",
      },
    ],
    modules,
    perms,
  );
  if (financeItems.length > 0) {
    sections.push({ title: "Finance", items: financeItems });
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
        {
          label: "Company Profile",
          href: "/admin/settings",
          icon: "Building2",
        },
        {
          label: "Price List",
          href: "/funeral-home/price-list",
          icon: "ListOrdered",
          permission: "fh_price_list.view",
        },
        {
          label: "Integrations",
          href: "/admin/accounting",
          icon: "Plug",
        },
        { label: "Extensions", href: "/extensions", icon: "Puzzle" },
        {
          label: "Notifications",
          href: "/notifications",
          icon: "Bell",
        },
      ],
      modules,
      perms,
    ),
  });

  return {
    sections,
    mobileTabs: [
      { label: "Cases", href: "/cases", icon: "FolderOpen" },
      { label: "New Case", href: "/cases/new", icon: "Plus" },
      { label: "FTC", href: "/funeral-home/compliance", icon: "Scale" },
      { label: "Billing", href: "/billing", icon: "Receipt" },
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
): NavigationConfig {
  const sections: NavSection[] = [];

  sections.push({
    title: "Operations",
    items: filterByPermission(
      [
        { label: "Dashboard", href: "/dashboard", icon: "LayoutDashboard" },
        { label: "Interments", href: "/interments", icon: "MapPin" },
        { label: "Plot Map", href: "/plots", icon: "Map" },
        { label: "Deeds", href: "/deeds", icon: "FileText" },
      ],
      modules,
      perms,
    ),
  });

  const financeItems = filterByPermission(
    [
      { label: "Financials Board", href: "/financials", icon: "BarChart3" },
      { label: "Billing", href: "/billing", icon: "Receipt" },
      {
        label: "Vendors & Bills",
        href: "/ap/bills",
        icon: "Receipt",
        permission: "ap.view",
      },
    ],
    modules,
    perms,
  );
  if (financeItems.length > 0) {
    sections.push({ title: "Finance", items: financeItems });
  }

  sections.push({
    title: "Settings",
    collapsible: true,
    defaultCollapsed: true,
    items: filterByPermission(
      [
        {
          label: "Company Profile",
          href: "/admin/settings",
          icon: "Building2",
        },
        { label: "Extensions", href: "/extensions", icon: "Puzzle" },
      ],
      modules,
      perms,
    ),
  });

  return {
    sections,
    mobileTabs: [
      { label: "Interments", href: "/interments", icon: "MapPin" },
      { label: "Plots", href: "/plots", icon: "Map" },
      { label: "Deeds", href: "/deeds", icon: "FileText" },
      { label: "Billing", href: "/billing", icon: "Receipt" },
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
): NavigationConfig {
  const sections: NavSection[] = [];

  sections.push({
    title: "Operations",
    items: filterByPermission(
      [
        { label: "Dashboard", href: "/dashboard", icon: "LayoutDashboard" },
        {
          label: "Cases",
          href: "/crematory/cases",
          icon: "FolderOpen",
        },
        {
          label: "Schedule",
          href: "/crematory/schedule",
          icon: "Calendar",
        },
      ],
      modules,
      perms,
    ),
  });

  const complianceItems = filterByPermission(
    [
      {
        label: "Chain of Custody",
        href: "/crematory/custody",
        icon: "Link",
      },
    ],
    modules,
    perms,
  );
  if (complianceItems.length > 0) {
    sections.push({ title: "Compliance", items: complianceItems });
  }

  const financeItems = filterByPermission(
    [
      { label: "Financials Board", href: "/financials", icon: "BarChart3" },
      { label: "Billing", href: "/billing", icon: "Receipt" },
      {
        label: "Vendors & Bills",
        href: "/ap/bills",
        icon: "Receipt",
        permission: "ap.view",
      },
    ],
    modules,
    perms,
  );
  if (financeItems.length > 0) {
    sections.push({ title: "Finance", items: financeItems });
  }

  sections.push({
    title: "Settings",
    collapsible: true,
    defaultCollapsed: true,
    items: filterByPermission(
      [
        {
          label: "Company Profile",
          href: "/admin/settings",
          icon: "Building2",
        },
        { label: "Extensions", href: "/extensions", icon: "Puzzle" },
      ],
      modules,
      perms,
    ),
  });

  return {
    sections,
    mobileTabs: [
      { label: "Cases", href: "/crematory/cases", icon: "FolderOpen" },
      { label: "Schedule", href: "/crematory/schedule", icon: "Calendar" },
      { label: "Custody", href: "/crematory/custody", icon: "Link" },
      { label: "Billing", href: "/billing", icon: "Receipt" },
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
  _perms: Set<string>,
  areas?: Set<string>,
): NavItem[] {
  return items.filter((item) => {
    if (item.requiresModule && !modules.has(item.requiresModule)) return false;
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
