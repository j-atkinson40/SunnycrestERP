import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Breadcrumbs } from "@/components/breadcrumbs";
import {
  Factory, Package, Clipboard, Snowflake, Kanban,
  ArrowRight, ClipboardList, Wrench,
} from "lucide-react";
import apiClient from "@/lib/api-client";
import { useAuth } from "@/contexts/auth-context";

interface ProductionSummary {
  total_products: number;
  low_stock_count: number;
  today_production: number;
  spring_burial_count: number;
}

export default function ProductionHub() {
  const { hasPermission, isAdmin } = useAuth();
  const [summary, setSummary] = useState<ProductionSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiClient.get("/products", { params: { page: 1, page_size: 1 } }).catch(() => ({ data: { total: 0 } })),
      apiClient.get("/inventory/low-stock-count").catch(() => ({ data: { count: 0 } })),
    ])
      .then(([prodRes, stockRes]) => {
        setSummary({
          total_products: prodRes.data.total ?? 0,
          low_stock_count: stockRes.data.count ?? 0,
          today_production: 0,
          spring_burial_count: 0,
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const canInventory = isAdmin || hasPermission("inventory.view");
  const canProducts = isAdmin || hasPermission("products.view");
  const canProdLog = isAdmin || hasPermission("production_log.view");
  const canWorkOrders = isAdmin || hasPermission("work_orders.view");

  return (
    <div className="space-y-6 p-6">
      <Breadcrumbs />
      <div>
        <h1 className="text-2xl font-bold">Production</h1>
        <p className="text-muted-foreground text-sm">
          Production, inventory, and product management.
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          label="Products"
          value={loading ? "—" : String(summary?.total_products ?? 0)}
          icon={Package}
          color="text-blue-600"
        />
        <SummaryCard
          label="Low Stock Items"
          value={loading ? "—" : String(summary?.low_stock_count ?? 0)}
          icon={Package}
          color="text-red-500"
        />
        <SummaryCard
          label="Today's Production"
          value={loading ? "—" : String(summary?.today_production ?? 0)}
          icon={Factory}
          color="text-green-600"
        />
        <SummaryCard
          label="Spring Burials"
          value={loading ? "—" : String(summary?.spring_burial_count ?? 0)}
          icon={Snowflake}
          color="text-cyan-600"
        />
      </div>

      {/* Quick Access Tiles */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {canProdLog && (
          <HubTile
            label="Production Log"
            description="Daily production entries"
            href="/production-log"
            icon={Clipboard}
          />
        )}
        {canInventory && (
          <HubTile
            label="Inventory"
            description="Stock levels & adjustments"
            href="/inventory"
            icon={Package}
          />
        )}
        {canProducts && (
          <HubTile
            label="Products"
            description="Product catalog & pricing"
            href="/products"
            icon={ClipboardList}
          />
        )}
        {canWorkOrders && (
          <>
            <HubTile
              label="Production Board"
              description="Work orders & scheduling"
              href="/production"
              icon={Kanban}
            />
            <HubTile
              label="Work Orders"
              description="Manage work orders"
              href="/work-orders"
              icon={Wrench}
            />
          </>
        )}
        <HubTile
          label="Spring Burials"
          description="Spring burial tracking"
          href="/spring-burials"
          icon={Snowflake}
        />
      </div>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-start gap-3 pt-5">
        <div className={`rounded-lg bg-muted p-2.5 ${color}`}>
          <Icon className="size-5" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-xl font-bold">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function HubTile({
  label,
  description,
  href,
  icon: Icon,
}: {
  label: string;
  description: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <Link to={href}>
      <Card className="group hover:border-primary/30 hover:bg-accent/30 transition-all cursor-pointer h-full">
        <CardContent className="flex items-center gap-3 pt-4 pb-4">
          <div className="rounded-lg bg-muted p-2">
            <Icon className="size-4 text-muted-foreground group-hover:text-primary transition-colors" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium">{label}</p>
            <p className="text-xs text-muted-foreground">{description}</p>
          </div>
          <ArrowRight className="size-4 text-muted-foreground/50 group-hover:text-primary transition-colors" />
        </CardContent>
      </Card>
    </Link>
  );
}
