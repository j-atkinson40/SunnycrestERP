import { Link, useLocation } from "react-router-dom";
import { ChevronRight, Home } from "lucide-react";
import { cn } from "@/lib/utils";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

// Route → breadcrumb mapping for hub sub-pages
const ROUTE_BREADCRUMBS: Record<string, BreadcrumbItem[]> = {
  // Financials hub sub-pages
  "/billing": [{ label: "Financials", href: "/financials" }, { label: "Billing" }],
  "/ar/invoices/review": [{ label: "Financials", href: "/financials" }, { label: "Invoice Review" }],
  "/ar/invoices": [{ label: "Financials", href: "/financials" }, { label: "Invoices" }],
  "/ar/payments": [{ label: "Financials", href: "/financials" }, { label: "Payments" }],
  "/ar/aging": [{ label: "Financials", href: "/financials" }, { label: "AR Aging" }],
  "/ar/orders": [{ label: "Financials", href: "/financials" }, { label: "Orders" }],
  "/ar/statements": [{ label: "Financials", href: "/financials" }, { label: "Statements" }],
  "/ap/bills": [{ label: "Financials", href: "/financials" }, { label: "Vendors & Bills" }],
  "/ap/purchase-orders": [{ label: "Financials", href: "/financials" }, { label: "Purchase Orders" }],
  "/ap/payments": [{ label: "Financials", href: "/financials" }, { label: "Vendor Payments" }],
  "/ap/aging": [{ label: "Financials", href: "/financials" }, { label: "AP Aging" }],
  "/journal-entries": [{ label: "Financials", href: "/financials" }, { label: "Journal Entries" }],
  "/reports": [{ label: "Financials", href: "/financials" }, { label: "Reports" }],

  // CRM hub sub-pages
  "/vault/crm/companies": [{ label: "CRM", href: "/vault/crm" }, { label: "Companies" }],
  "/vault/crm/funeral-homes": [{ label: "CRM", href: "/vault/crm" }, { label: "Funeral Homes" }],
  "/vault/crm/contractors": [{ label: "CRM", href: "/vault/crm" }, { label: "Contractors" }],
  "/vault/crm/billing-groups": [{ label: "CRM", href: "/vault/crm" }, { label: "Billing Groups" }],
  "/vault/crm/pipeline": [{ label: "CRM", href: "/vault/crm" }, { label: "Pipeline" }],
  "/vault/crm/settings": [{ label: "CRM", href: "/vault/crm" }, { label: "Settings" }],

  // Production hub sub-pages
  "/production-log": [{ label: "Production", href: "/production-hub" }, { label: "Production Log" }],
  "/production-log/summary": [{ label: "Production", href: "/production-hub" }, { label: "Log Summary" }],
  "/inventory": [{ label: "Production", href: "/production-hub" }, { label: "Inventory" }],
  "/products": [{ label: "Production", href: "/production-hub" }, { label: "Products" }],
  "/production": [{ label: "Production", href: "/production-hub" }, { label: "Production Board" }],
  "/spring-burials": [{ label: "Production", href: "/production-hub" }, { label: "Spring Burials" }],

  // Safety sub-pages
  "/safety/training/calendar": [{ label: "Safety & OSHA", href: "/safety" }, { label: "Training Calendar" }],
  "/safety/inspections/new": [{ label: "Safety & OSHA", href: "/safety" }, { label: "Inspections" }],
  "/safety/toolbox-talks": [{ label: "Safety & OSHA", href: "/safety" }, { label: "Toolbox Talks" }],
  "/safety/incidents": [{ label: "Safety & OSHA", href: "/safety" }, { label: "Incidents" }],
  "/safety/notices": [{ label: "Safety & OSHA", href: "/safety" }, { label: "Safety Notices" }],
  "/safety/osha-300": [{ label: "Safety & OSHA", href: "/safety" }, { label: "OSHA 300 Log" }],
  "/safety/chemicals": [{ label: "Safety & OSHA", href: "/safety" }, { label: "SDS / HazCom" }],
  "/safety/loto": [{ label: "Safety & OSHA", href: "/safety" }, { label: "LOTO Procedures" }],
  "/safety/programs": [{ label: "Safety & OSHA", href: "/safety" }, { label: "Programs" }],
};

function findBreadcrumbs(pathname: string): BreadcrumbItem[] | null {
  // Exact match first
  if (ROUTE_BREADCRUMBS[pathname]) return ROUTE_BREADCRUMBS[pathname];

  // Try prefix match for detail pages (e.g., /vault/crm/companies/123)
  for (const [route, crumbs] of Object.entries(ROUTE_BREADCRUMBS)) {
    if (pathname.startsWith(route + "/")) {
      return [...crumbs.slice(0, -1), { ...crumbs[crumbs.length - 1], href: route }, { label: "Details" }];
    }
  }

  return null;
}

export function Breadcrumbs() {
  const location = useLocation();
  const crumbs = findBreadcrumbs(location.pathname);

  if (!crumbs) return null;

  return (
    <nav className="flex items-center gap-1 text-sm text-muted-foreground mb-4">
      <Link
        to="/dashboard"
        className="hover:text-foreground transition-colors"
      >
        <Home className="size-3.5" />
      </Link>
      {crumbs.map((crumb, i) => (
        <span key={i} className="flex items-center gap-1">
          <ChevronRight className="size-3 text-muted-foreground/50" />
          {crumb.href ? (
            <Link
              to={crumb.href}
              className="hover:text-foreground transition-colors"
            >
              {crumb.label}
            </Link>
          ) : (
            <span className={cn(i === crumbs.length - 1 && "text-foreground font-medium")}>
              {crumb.label}
            </span>
          )}
        </span>
      ))}
    </nav>
  );
}
