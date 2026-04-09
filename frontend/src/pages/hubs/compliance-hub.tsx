import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Breadcrumbs } from "@/components/breadcrumbs";
import {
  Shield,
  FileCheck,
  ClipboardCheck,
  AlertTriangle,
  BookOpen,
  FileText,
  Beaker,
  Lock,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import apiClient from "@/lib/api-client";
import { useAuth } from "@/contexts/auth-context";

interface ComplianceSummary {
  pending_reviews: number;
  compliance_score: number | null;
  overdue_inspections: number;
  open_incidents: number;
}

export default function ComplianceHub() {
  const { hasPermission, hasModule, isAdmin } = useAuth();
  const [summary, setSummary] = useState<ComplianceSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const canSafety = isAdmin || hasPermission("safety.view");
  const canTrainer = isAdmin || hasPermission("safety.trainer.view");
  const hasNpca = hasModule("npca_audit_prep");

  useEffect(() => {
    Promise.all([
      apiClient.get("/safety/compliance-score").catch(() => ({ data: { overall_score: null } })),
      apiClient.get("/safety/overdue-inspections").catch(() => ({ data: [] })),
      apiClient.get("/safety/incidents", { params: { status: "open", limit: 1 } }).catch(() => ({ data: [] })),
      canTrainer
        ? apiClient.get("/safety/programs/generations", { params: { limit: 50 } }).catch(() => ({ data: [] }))
        : Promise.resolve({ data: [] }),
    ])
      .then(([scoreRes, overdueRes, incidentsRes, gensRes]) => {
        const gens = Array.isArray(gensRes.data) ? gensRes.data : [];
        const pendingReviews = gens.filter(
          (g: Record<string, unknown>) => g.status === "pending_review"
        ).length;
        setSummary({
          compliance_score: scoreRes.data?.overall_score ?? null,
          overdue_inspections: Array.isArray(overdueRes.data) ? overdueRes.data.length : 0,
          open_incidents: Array.isArray(incidentsRes.data) ? incidentsRes.data.length : 0,
          pending_reviews: pendingReviews,
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [canTrainer]);

  return (
    <div className="space-y-6 p-6">
      <Breadcrumbs />
      <div>
        <h1 className="text-2xl font-bold">Compliance</h1>
        <p className="text-muted-foreground text-sm">
          Safety programs, regulatory compliance, inspections, and audit readiness.
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          label="Compliance Score"
          value={
            loading
              ? "\u2014"
              : summary?.compliance_score != null
                ? `${summary.compliance_score}%`
                : "N/A"
          }
          icon={Shield}
          color={
            summary?.compliance_score != null
              ? summary.compliance_score >= 90
                ? "text-green-600"
                : summary.compliance_score >= 75
                  ? "text-amber-500"
                  : "text-red-500"
              : "text-muted-foreground"
          }
        />
        <SummaryCard
          label="Pending Reviews"
          value={loading ? "\u2014" : String(summary?.pending_reviews ?? 0)}
          icon={FileCheck}
          color={
            (summary?.pending_reviews ?? 0) > 0
              ? "text-amber-500"
              : "text-green-600"
          }
        />
        <SummaryCard
          label="Overdue Inspections"
          value={loading ? "\u2014" : String(summary?.overdue_inspections ?? 0)}
          icon={ClipboardCheck}
          color={
            (summary?.overdue_inspections ?? 0) > 0
              ? "text-red-500"
              : "text-green-600"
          }
        />
        <SummaryCard
          label="Open Incidents"
          value={loading ? "\u2014" : String(summary?.open_incidents ?? 0)}
          icon={AlertTriangle}
          color={
            (summary?.open_incidents ?? 0) > 0
              ? "text-red-500"
              : "text-green-600"
          }
        />
      </div>

      {/* Hub Tiles */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {canTrainer && (
          <HubTile
            label="Safety Programs"
            description="AI-generated monthly safety programs with OSHA standards"
            href="/safety/programs"
            icon={Sparkles}
            badge={
              (summary?.pending_reviews ?? 0) > 0
                ? `${summary!.pending_reviews} pending`
                : undefined
            }
          />
        )}
        {canSafety && (
          <>
            <HubTile
              label="Safety Dashboard"
              description="Compliance score, alerts, and safety overview"
              href="/safety"
              icon={Shield}
            />
            <HubTile
              label="Inspections"
              description="Equipment inspections and compliance checks"
              href="/safety/inspections/new"
              icon={ClipboardCheck}
              badge={
                (summary?.overdue_inspections ?? 0) > 0
                  ? `${summary!.overdue_inspections} overdue`
                  : undefined
              }
            />
            <HubTile
              label="OSHA 300 Log"
              description="Recordable injury and illness tracking"
              href="/safety/osha-300"
              icon={FileText}
            />
            <HubTile
              label="Incidents"
              description="Incident reporting and investigation"
              href="/safety/incidents"
              icon={AlertTriangle}
            />
            <HubTile
              label="Toolbox Talks"
              description="Weekly safety discussions and topics"
              href="/safety/toolbox-talks"
              icon={BookOpen}
            />
            <HubTile
              label="Chemical Inventory"
              description="SDS management and chemical tracking"
              href="/safety/chemicals"
              icon={Beaker}
            />
            <HubTile
              label="LOTO Procedures"
              description="Lockout/tagout procedures and assignments"
              href="/safety/loto"
              icon={Lock}
            />
            <HubTile
              label="Compliance Notices"
              description="Regulatory notices and acknowledgments"
              href="/safety/notices"
              icon={FileCheck}
            />
          </>
        )}
        <HubTile
          label="SS Certificates"
          description="Social Service certificate generation and tracking"
          href="/social-service-certificates"
          icon={FileCheck}
        />
        {hasNpca && (
          <HubTile
            label="NPCA Audit Prep"
            description="Audit readiness and certification compliance"
            href="/npca"
            icon={ClipboardCheck}
          />
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
  badge,
}: {
  label: string;
  description: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}) {
  return (
    <Link to={href}>
      <Card className="group hover:border-primary/30 hover:bg-accent/30 transition-all cursor-pointer h-full">
        <CardContent className="flex items-center gap-3 pt-4 pb-4">
          <div className="rounded-lg bg-muted p-2">
            <Icon className="size-4 text-muted-foreground group-hover:text-primary transition-colors" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium">{label}</p>
              {badge && (
                <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200 text-xs">
                  {badge}
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground">{description}</p>
          </div>
          <ArrowRight className="size-4 text-muted-foreground/50 group-hover:text-primary transition-colors" />
        </CardContent>
      </Card>
    </Link>
  );
}
