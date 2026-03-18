/**
 * Admin Dashboard — Operational command center for the platform.
 *
 * Shows stat cards, preset distribution, attention-required items,
 * recent activity, and extension demand signals.
 */

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  getSystemHealth,
  listTenants,
} from "@/services/platform-service";
import platformClient from "@/lib/platform-api-client";
import type { SystemHealth, TenantOverview } from "@/types/platform";
import type { DemandSignalItem } from "@/types/extension";
import { cn } from "@/lib/utils";
import {
  Building2,
  DollarSign,
  Clock,
  Target,
  TrendingUp,
  Factory,
  Heart,
  TreePine,
  Flame,
  AlertTriangle,
  Bell,
  ArrowRight,
  Rocket,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

// ---------------------------------------------------------------------------
// Preset config
// ---------------------------------------------------------------------------

const PRESET_COLORS: Record<
  string,
  { bg: string; text: string; border: string; icon: LucideIcon; barColor: string }
> = {
  manufacturing: { bg: "bg-slate-100", text: "text-slate-700", border: "border-slate-300", icon: Factory, barColor: "bg-slate-500" },
  funeral_home: { bg: "bg-stone-100", text: "text-stone-700", border: "border-stone-300", icon: Heart, barColor: "bg-stone-500" },
  cemetery: { bg: "bg-green-100", text: "text-green-800", border: "border-green-300", icon: TreePine, barColor: "bg-green-500" },
  crematory: { bg: "bg-red-100", text: "text-red-900", border: "border-red-300", icon: Flame, barColor: "bg-red-500" },
};

const PRESET_LABELS: Record<string, string> = {
  manufacturing: "Manufacturing",
  funeral_home: "Funeral Home",
  cemetery: "Cemetery",
  crematory: "Crematory",
};

function getPreset(t: TenantOverview): string | null {
  const slug = (t.plan_name || t.slug || "").toLowerCase();
  for (const key of Object.keys(PRESET_COLORS)) {
    if (slug.includes(key)) return key;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Attention item types
// ---------------------------------------------------------------------------

interface AttentionItem {
  category: string;
  categoryColor: string;
  label: string;
  tenantId: string;
  tenantName: string;
}

function deriveAttentionItems(tenants: TenantOverview[]): AttentionItem[] {
  const items: AttentionItem[] = [];
  for (const t of tenants) {
    const sub = (t.subscription_status || "").toLowerCase();
    if (sub === "trial" || sub === "trialing") {
      items.push({
        category: "Trial Expiring",
        categoryColor: "bg-amber-500",
        label: `${t.name} is on trial`,
        tenantId: t.id,
        tenantName: t.name,
      });
    }
    if (!t.is_active) {
      items.push({
        category: "Suspended",
        categoryColor: "bg-red-500",
        label: `${t.name} is suspended`,
        tenantId: t.id,
        tenantName: t.name,
      });
    }
  }
  return items;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AdminDashboard() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [tenants, setTenants] = useState<TenantOverview[]>([]);
  const [demandItems, setDemandItems] = useState<DemandSignalItem[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [h, t] = await Promise.all([
        getSystemHealth(),
        listTenants({ limit: 500 }),
      ]);
      setHealth(h);
      setTenants(t.items);
    } catch {
      toast.error("Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Load demand signals separately (may fail if no extensions)
  useEffect(() => {
    platformClient
      .get<DemandSignalItem[]>("/extensions/notify-requests/demand")
      .then(({ data }) => setDemandItems(data))
      .catch(() => {
        // Silently ignore — demand signals may not exist
      });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600" />
      </div>
    );
  }

  if (!health) return null;

  // Derive preset counts
  const presetCounts: Record<string, number> = {};
  let otherCount = 0;
  for (const t of tenants) {
    const p = getPreset(t);
    if (p) presetCounts[p] = (presetCounts[p] || 0) + 1;
    else otherCount++;
  }
  const maxPresetCount = Math.max(...Object.values(presetCounts), otherCount, 1);

  const trialCount = tenants.filter(
    (t) =>
      (t.subscription_status || "").toLowerCase() === "trial" ||
      (t.subscription_status || "").toLowerCase() === "trialing"
  ).length;

  // Onboarding completion rate (placeholder: active = completed)
  const activeCount = tenants.filter((t) => t.is_active).length;
  const onboardingRate = tenants.length > 0 ? Math.round((activeCount / tenants.length) * 100) : 0;

  // Attention items
  const attentionItems = deriveAttentionItems(tenants);

  // Stat cards
  const stats = [
    {
      label: "Total Active Tenants",
      value: health.active_tenants,
      icon: Building2,
      color: "text-indigo-600",
      bgColor: "bg-indigo-50",
    },
    {
      label: "Total MRR",
      value: "$0",
      icon: DollarSign,
      color: "text-green-600",
      bgColor: "bg-green-50",
    },
    {
      label: "Tenants in Trial",
      value: trialCount,
      icon: Clock,
      color: "text-amber-600",
      bgColor: "bg-amber-50",
    },
    {
      label: "Onboarding Completion",
      value: `${onboardingRate}%`,
      icon: Target,
      color: "text-blue-600",
      bgColor: "bg-blue-50",
    },
    {
      label: "Avg Time to First Value",
      value: "N/A",
      icon: TrendingUp,
      color: "text-purple-600",
      bgColor: "bg-purple-50",
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-sm text-muted-foreground">Platform operations overview</p>
      </div>

      {/* Stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {stats.map((s) => {
          const Icon = s.icon;
          return (
            <Card key={s.label}>
              <CardContent className="pt-2">
                <div className="flex items-center gap-3">
                  <div
                    className={cn(
                      "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
                      s.bgColor
                    )}
                  >
                    <Icon className={cn("h-5 w-5", s.color)} />
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">{s.label}</p>
                    <p className="text-xl font-bold">{s.value}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Preset distribution */}
        <Card>
          <CardHeader>
            <CardTitle>Tenant Distribution by Preset</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(PRESET_COLORS).map(([key, colors]) => {
                const count = presetCounts[key] || 0;
                const Icon = colors.icon;
                const pct = maxPresetCount > 0 ? (count / maxPresetCount) * 100 : 0;
                return (
                  <div key={key} className="flex items-center gap-3">
                    <div className="flex w-28 items-center gap-2">
                      <Icon className={cn("h-4 w-4 shrink-0", colors.text)} />
                      <span className="truncate text-sm">{PRESET_LABELS[key]}</span>
                    </div>
                    <div className="flex-1">
                      <div className="h-5 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all",
                            colors.barColor
                          )}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                    <span className="w-8 text-right text-sm font-semibold">{count}</span>
                  </div>
                );
              })}
              {otherCount > 0 && (
                <div className="flex items-center gap-3">
                  <div className="flex w-28 items-center gap-2">
                    <Building2 className="h-4 w-4 shrink-0 text-slate-400" />
                    <span className="truncate text-sm">Other</span>
                  </div>
                  <div className="flex-1">
                    <div className="h-5 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-slate-400 transition-all"
                        style={{
                          width: `${(otherCount / maxPresetCount) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                  <span className="w-8 text-right text-sm font-semibold">{otherCount}</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Attention Required */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              <CardTitle>Attention Required</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            {attentionItems.length === 0 ? (
              <div className="flex flex-col items-center py-6 text-center">
                <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-green-50">
                  <Bell className="h-5 w-5 text-green-500" />
                </div>
                <p className="text-sm text-muted-foreground">
                  All clear — no items need attention.
                </p>
              </div>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {attentionItems.slice(0, 15).map((item, i) => (
                  <Link
                    key={i}
                    to={`/tenants/${item.tenantId}`}
                    className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-slate-50"
                  >
                    <span
                      className={cn("h-2 w-2 shrink-0 rounded-full", item.categoryColor)}
                    />
                    <span className="flex-1 truncate">{item.label}</span>
                    <Badge variant="outline" className="text-[10px] shrink-0">
                      {item.category}
                    </Badge>
                    <ArrowRight className="h-3 w-3 shrink-0 text-muted-foreground" />
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            {tenants.length === 0 ? (
              <p className="text-sm text-muted-foreground">No recent activity.</p>
            ) : (
              <div className="space-y-2">
                {tenants.slice(0, 10).map((t) => {
                  const preset = getPreset(t);
                  const presetColor = preset ? PRESET_COLORS[preset] : null;
                  return (
                    <div key={t.id} className="flex items-center gap-2 text-sm">
                      <span
                        className={cn(
                          "h-2 w-2 shrink-0 rounded-full",
                          t.is_active ? "bg-green-500" : "bg-gray-300"
                        )}
                      />
                      <Link
                        to={`/tenants/${t.id}`}
                        className="truncate font-medium hover:underline"
                      >
                        {t.name}
                      </Link>
                      {preset && presetColor && (
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-[10px]",
                            presetColor.bg,
                            presetColor.text,
                            presetColor.border
                          )}
                        >
                          {PRESET_LABELS[preset]}
                        </Badge>
                      )}
                      <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                        {new Date(t.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Extension Demand Signals */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Rocket className="h-4 w-4 text-purple-500" />
                <CardTitle>Extension Demand Signals</CardTitle>
              </div>
              <Link
                to="/extensions/demand"
                className="text-xs text-indigo-600 hover:underline"
              >
                View all
              </Link>
            </div>
          </CardHeader>
          <CardContent>
            {demandItems.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No demand signals yet.
              </p>
            ) : (
              <div className="space-y-3">
                {demandItems.slice(0, 5).map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{item.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {item.notify_me_count} request{item.notify_me_count !== 1 ? "s" : ""}
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="xs"
                      className="shrink-0 gap-1"
                      onClick={async () => {
                        try {
                          await platformClient.put(`/extensions/${item.id}`, {
                            status: "beta",
                          });
                          toast.success(`${item.name} marked as in development`);
                        } catch {
                          toast.error("Failed to update");
                        }
                      }}
                    >
                      <Wrench className="h-3 w-3" />
                      In Dev
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
