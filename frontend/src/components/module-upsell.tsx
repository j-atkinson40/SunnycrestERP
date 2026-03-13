import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ModuleUpsellProps {
  moduleLabel: string;
  moduleDescription: string;
}

const MODULE_META: Record<string, { label: string; description: string }> = {
  products: {
    label: "Product Catalog",
    description:
      "Product database with categories, pricing tiers, and bulk import capabilities.",
  },
  inventory: {
    label: "Inventory Management",
    description:
      "Track stock levels, record transactions, set reorder points, and manage warehouse locations.",
  },
  hr_time: {
    label: "HR & Time Tracking",
    description:
      "Flexible time and attendance, early release model, PTO management, employee records, and payroll export.",
  },
  driver_delivery: {
    label: "Driver & Delivery",
    description:
      "Route scheduling, mobile delivery confirmation, mileage logging, and stop management.",
  },
  pos: {
    label: "Point of Sale",
    description:
      "Counter sales screen, barcode scanning, cash and card payments, thermal receipts, and end-of-day reconciliation.",
  },
  project_mgmt: {
    label: "Project Management",
    description:
      "Job creation, task assignment, timelines, resource allocation, and status reporting.",
  },
  analytics: {
    label: "Advanced Analytics",
    description:
      "Custom dashboard builder, trend analysis, forecasting, and scheduled report delivery.",
  },
};

export function ModuleUpsell({ moduleLabel, moduleDescription }: ModuleUpsellProps) {
  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <Card className="max-w-lg w-full text-center">
        <CardHeader>
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-8 w-8 text-muted-foreground"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
              />
            </svg>
          </div>
          <CardTitle className="text-xl">{moduleLabel}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">{moduleDescription}</p>
          <div className="rounded-lg border border-dashed p-4">
            <p className="text-sm text-muted-foreground">
              This module is not currently enabled for your company. Please
              contact your administrator to enable it.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function getModuleMeta(moduleKey: string) {
  return MODULE_META[moduleKey] ?? { label: moduleKey, description: "" };
}
