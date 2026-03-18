export interface NavItem {
  label: string;
  href: string;
  icon: string; // lucide icon name
  badge?: number | string;
  permission?: string;
  requiresModule?: string;
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
): NavigationConfig {
  const preset = vertical || "manufacturing";
  const settings = tenantSettings || {};

  switch (preset) {
    case "manufacturing":
      return getManufacturingNav(enabledModules, permissions, settings);
    case "funeral_home":
      return getFuneralHomeNav(enabledModules, permissions);
    case "cemetery":
      return getCemeteryNav(enabledModules, permissions);
    case "crematory":
      return getCrematoryNav(enabledModules, permissions);
    default:
      return getManufacturingNav(enabledModules, permissions);
  }
}

function getManufacturingNav(
  modules: Set<string>,
  perms: Set<string>,
  settings: Record<string, unknown> = {},
): NavigationConfig {
  const sections: NavSection[] = [];

  // Operations
  const opsItems: NavItem[] = [
    { label: "Dashboard", href: "/dashboard", icon: "LayoutDashboard" },
    {
      label: "Orders",
      href: "/orders",
      icon: "ClipboardList",
      permission: "orders.view",
    },
    {
      label: "Customers",
      href: "/customers",
      icon: "Users",
      permission: "customers.view",
    },
    {
      label: "Delivery Schedule",
      href: "/delivery",
      icon: "Truck",
      permission: "deliveries.view",
      requiresModule: "driver_delivery",
    },
    {
      label: "Inventory",
      href: "/inventory",
      icon: "Package",
      permission: "inventory.view",
    },
    {
      label: "Production Log",
      href: "/production-log",
      icon: "Factory",
      permission: "production_log.view",
      requiresModule: "daily_production_log",
    },
  ];

  // Spring Burials — only if enabled in tenant settings
  if (settings.spring_burials_enabled) {
    opsItems.push({
      label: "Spring Burials",
      href: "/spring-burials",
      icon: "Snowflake",
    });
  }

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
    items: filterByPermission(opsItems, modules, perms),
  });

  // Compliance
  const complianceItems: NavItem[] = [
    {
      label: "Safety & OSHA",
      href: "/safety",
      icon: "ShieldCheck",
      permission: "safety.view",
      requiresModule: "safety_management",
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
  );
  if (filteredCompliance.length > 0) {
    sections.push({ title: "Compliance", items: filteredCompliance });
  }

  // Finance
  const financeItems = filterByPermission(
    [
      {
        label: "Invoices",
        href: "/invoices",
        icon: "Receipt",
        permission: "invoices.view",
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
          label: "Company Profile",
          href: "/admin/settings",
          icon: "Building2",
        },
        {
          label: "Integrations",
          href: "/admin/settings/integrations",
          icon: "Plug",
        },
        { label: "Extensions", href: "/extensions", icon: "Puzzle" },
        {
          label: "Notifications",
          href: "/admin/settings/notifications",
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
      { label: "Orders", href: "/orders", icon: "ClipboardList" },
      { label: "Schedule", href: "/delivery", icon: "Truck" },
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
      href: "/funeral-home/cases",
      icon: "FolderOpen",
      permission: "fh_cases.view",
    },
    {
      label: "New Case",
      href: "/funeral-home/first-call",
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
      {
        label: "Invoices",
        href: "/invoices",
        icon: "Receipt",
        permission: "fh_invoices.view",
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
          href: "/admin/settings/integrations",
          icon: "Plug",
        },
        { label: "Extensions", href: "/extensions", icon: "Puzzle" },
        {
          label: "Notifications",
          href: "/admin/settings/notifications",
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
      { label: "Cases", href: "/funeral-home/cases", icon: "FolderOpen" },
      { label: "New Case", href: "/funeral-home/first-call", icon: "Plus" },
      { label: "FTC", href: "/funeral-home/compliance", icon: "Scale" },
      { label: "Invoices", href: "/invoices", icon: "Receipt" },
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
    [{ label: "Invoices", href: "/invoices", icon: "Receipt" }],
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
      { label: "Invoices", href: "/invoices", icon: "Receipt" },
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
    [{ label: "Invoices", href: "/invoices", icon: "Receipt" }],
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
      { label: "Invoices", href: "/invoices", icon: "Receipt" },
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
): NavItem[] {
  return items.filter((item) => {
    if (item.requiresModule && !modules.has(item.requiresModule)) return false;
    // Permission checking happens at route level; nav shows all items
    // that pass module gating for simplicity
    return true;
  });
}
