import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Breadcrumbs } from "@/components/breadcrumbs";
import {
  Building2, Home, HardHat, Users, Sparkles,
  ClipboardCheck, Settings2, ArrowRight, Building,
  GitBranch,
} from "lucide-react";
import apiClient from "@/lib/api-client";
import { useAuth } from "@/contexts/auth-context";

interface CRMSummary {
  total_companies: number;
  funeral_homes: number;
  cemeteries: number;
  contractors: number;
  recent_activity_count: number;
}

export default function CRMHub() {
  const { isAdmin } = useAuth();
  const [summary, setSummary] = useState<CRMSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .get("/company-entities", { params: { page: 1, page_size: 1 } })
      .then((r) => {
        setSummary({
          total_companies: r.data.total ?? 0,
          funeral_homes: 0,
          cemeteries: 0,
          contractors: 0,
          recent_activity_count: 0,
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6 p-6">
      <Breadcrumbs />
      <div>
        <h1 className="text-2xl font-bold">CRM</h1>
        <p className="text-muted-foreground text-sm">
          Manage customer relationships, companies, and billing groups.
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          label="Total Companies"
          value={loading ? "—" : String(summary?.total_companies ?? 0)}
          icon={Building2}
          color="text-blue-600"
        />
        <SummaryCard
          label="Funeral Homes"
          value={loading ? "—" : String(summary?.funeral_homes ?? "—")}
          icon={Home}
          color="text-purple-600"
        />
        <SummaryCard
          label="Cemeteries"
          value={loading ? "—" : String(summary?.cemeteries ?? "—")}
          icon={Building}
          color="text-green-600"
        />
        <SummaryCard
          label="Contractors"
          value={loading ? "—" : String(summary?.contractors ?? "—")}
          icon={HardHat}
          color="text-amber-600"
        />
      </div>

      {/* Quick Access Tiles */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <HubTile
          label="All Companies"
          description="Browse and search all companies"
          href="/vault/crm/companies"
          icon={Building2}
        />
        <HubTile
          label="Funeral Homes"
          description="Funeral home directory"
          href="/vault/crm/funeral-homes"
          icon={Home}
        />
        <HubTile
          label="Billing Groups"
          description="Manage billing group relationships"
          href="/vault/crm/billing-groups"
          icon={Users}
        />
        <HubTile
          label="Pipeline"
          description="Sales pipeline and opportunities"
          href="/vault/crm/pipeline"
          icon={GitBranch}
        />
        {isAdmin && (
          <>
            <HubTile
              label="Classification"
              description="AI-powered company classification"
              href="/admin/company-classification"
              icon={Sparkles}
            />
            <HubTile
              label="Data Quality"
              description="Duplicate detection & cleanup"
              href="/admin/data-quality"
              icon={ClipboardCheck}
            />
            <HubTile
              label="CRM Settings"
              description="CRM configuration & preferences"
              href="/vault/crm/settings"
              icon={Settings2}
            />
          </>
        )}
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
