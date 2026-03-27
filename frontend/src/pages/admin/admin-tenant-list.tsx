/**
 * Admin Tenant List Page
 *
 * Redesigned tenant list with preset filtering, rich status indicators,
 * and card-like tenant rows with onboarding progress and impersonation.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import {
  listTenants,
  impersonateTenant,
} from "@/services/platform-service";
import type { TenantOverview } from "@/types/platform";
import {
  Search,
  Plus,
  Factory,
  Heart,
  TreePine,
  Flame,
  Eye,
  UserCheck,
  MoreHorizontal,
  ChevronDown,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Preset color system
// ---------------------------------------------------------------------------

const PRESET_COLORS: Record<
  string,
  { bg: string; text: string; border: string; icon: LucideIcon }
> = {
  manufacturing: { bg: "bg-slate-100", text: "text-slate-700", border: "border-slate-300", icon: Factory },
  funeral_home: { bg: "bg-stone-100", text: "text-stone-700", border: "border-stone-300", icon: Heart },
  cemetery: { bg: "bg-green-100", text: "text-green-800", border: "border-green-300", icon: TreePine },
  crematory: { bg: "bg-red-100", text: "text-red-900", border: "border-red-300", icon: Flame },
};

const PRESET_LABELS: Record<string, string> = {
  manufacturing: "Manufacturing",
  funeral_home: "Funeral Home",
  cemetery: "Cemetery",
  crematory: "Crematory",
};

function getPreset(tenant: TenantOverview): string | null {
  // Try to derive preset from plan name or slug — adjust to match your data
  const slug = (tenant.plan_name || tenant.slug || "").toLowerCase();
  for (const key of Object.keys(PRESET_COLORS)) {
    if (slug.includes(key)) return key;
  }
  return null;
}

// ---------------------------------------------------------------------------
// SVG progress ring
// ---------------------------------------------------------------------------

function ProgressRing({
  percent,
  size = 36,
  stroke = 3,
}: {
  percent: number;
  size?: number;
  stroke?: number;
}) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;

  return (
    <svg width={size} height={size} className="shrink-0">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="currentColor"
        strokeWidth={stroke}
        className="text-slate-200"
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="currentColor"
        strokeWidth={stroke}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        className={cn(
          "transition-all duration-300",
          percent >= 100
            ? "text-green-500"
            : percent >= 50
              ? "text-blue-500"
              : "text-amber-500"
        )}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text
        x="50%"
        y="50%"
        dominantBaseline="central"
        textAnchor="middle"
        className="fill-current text-[9px] font-semibold text-slate-600"
      >
        {Math.round(percent)}%
      </text>
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Status helpers
// ---------------------------------------------------------------------------

type TenantStatus = "active" | "trial" | "suspended" | "inactive";

function deriveTenantStatus(t: TenantOverview): TenantStatus {
  if (!t.is_active) return "suspended";
  const sub = (t.subscription_status || "").toLowerCase();
  if (sub === "trial" || sub === "trialing") return "trial";
  if (sub === "suspended" || sub === "past_due") return "suspended";
  return "active";
}

const STATUS_STYLES: Record<TenantStatus, string> = {
  active: "bg-green-100 text-green-800",
  trial: "bg-amber-100 text-amber-800",
  suspended: "bg-red-100 text-red-800",
  inactive: "bg-gray-100 text-gray-600",
};

// ---------------------------------------------------------------------------
// Dropdown component
// ---------------------------------------------------------------------------

function SimpleSelect({
  value,
  onChange,
  options,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  placeholder: string;
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 appearance-none rounded-lg border border-input bg-transparent px-2.5 pr-7 text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/50"
      >
        <option value="">{placeholder}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AdminTenantList() {
  const [tenants, setTenants] = useState<TenantOverview[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [presetFilter, setPresetFilter] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [menuOpen, setMenuOpen] = useState<string | null>(null);

  const fetchTenants = useCallback(async () => {
    try {
      setLoading(true);
      const data = await listTenants({
        search: search || undefined,
        limit: 200,
      });
      setTenants(data.items);
      setTotal(data.total);
    } catch {
      toast.error("Failed to load tenants");
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    fetchTenants();
  }, [fetchTenants]);

  // Derive counts per preset
  const presetCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const t of tenants) {
      const p = getPreset(t);
      if (p) counts[p] = (counts[p] || 0) + 1;
    }
    return counts;
  }, [tenants]);

  // Filter tenants
  const filtered = useMemo(() => {
    let list = tenants;
    if (presetFilter) {
      list = list.filter((t) => getPreset(t) === presetFilter);
    }
    if (statusFilter) {
      list = list.filter((t) => deriveTenantStatus(t) === statusFilter);
    }
    return list;
  }, [tenants, presetFilter, statusFilter]);

  async function handleImpersonate(tenant: TenantOverview) {
    try {
      const result = await impersonateTenant(tenant.id);
      localStorage.setItem(
        "impersonation_info",
        JSON.stringify({
          session_id: result.session_id,
          tenant_name: result.tenant_name,
          user_name: result.impersonated_user_name,
          expires_at: Date.now() + result.expires_in_minutes * 60 * 1000,
        })
      );
      localStorage.setItem("access_token", result.access_token);
      localStorage.setItem("company_slug", result.tenant_slug);
      localStorage.removeItem("platform_mode");
      window.location.href = "/dashboard";
    } catch {
      toast.error("Failed to start impersonation");
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Tenants</h1>
          <p className="text-sm text-muted-foreground">{total} total tenants</p>
        </div>
        <Link
          to="/tenants/new"
          className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-indigo-600 px-3 text-sm font-medium text-white transition-colors hover:bg-indigo-700"
        >
          <Plus className="h-4 w-4" />
          Add Tenant
        </Link>
      </div>

      {/* Preset filter pills */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setPresetFilter(null)}
          className={cn(
            "rounded-full px-3 py-1 text-xs font-medium transition-colors",
            presetFilter === null
              ? "bg-indigo-600 text-white"
              : "bg-slate-100 text-slate-600 hover:bg-slate-200"
          )}
        >
          All ({total})
        </button>
        {Object.entries(PRESET_COLORS).map(([key, colors]) => {
          const Icon = colors.icon;
          const count = presetCounts[key] || 0;
          return (
            <button
              key={key}
              onClick={() => setPresetFilter(presetFilter === key ? null : key)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                presetFilter === key
                  ? `${colors.bg} ${colors.text} ${colors.border}`
                  : "border-transparent bg-slate-100 text-slate-600 hover:bg-slate-200"
              )}
            >
              <Icon className="h-3 w-3" />
              {PRESET_LABELS[key]} ({count})
            </button>
          );
        })}
      </div>

      {/* Search + secondary filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search tenants..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>
        <SimpleSelect
          value={statusFilter}
          onChange={setStatusFilter}
          placeholder="All Statuses"
          options={[
            { value: "active", label: "Active" },
            { value: "trial", label: "Trial" },
            { value: "suspended", label: "Suspended" },
          ]}
        />
      </div>

      {/* Tenant list */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="py-16 text-center text-sm text-muted-foreground">
          No tenants match your filters.
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((tenant) => {
            const preset = getPreset(tenant);
            const presetColor = preset ? PRESET_COLORS[preset] : null;
            const PresetIcon = presetColor?.icon;
            const status = deriveTenantStatus(tenant);
            // Placeholder onboarding progress — use real data when available
            const onboardingPercent = tenant.is_active ? 100 : 40;
            const daysSinceCreated = Math.floor(
              (Date.now() - new Date(tenant.created_at).getTime()) / 86400000
            );

            return (
              <div
                key={tenant.id}
                className="group relative flex items-center gap-4 rounded-xl border bg-card p-4 ring-1 ring-foreground/5 transition-shadow hover:shadow-md"
              >
                {/* Left: Preset icon + name */}
                <div className="flex min-w-0 flex-1 items-center gap-3">
                  {PresetIcon ? (
                    <div
                      className={cn(
                        "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border",
                        presetColor?.bg,
                        presetColor?.border
                      )}
                    >
                      <PresetIcon className={cn("h-5 w-5", presetColor?.text)} />
                    </div>
                  ) : (
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border bg-slate-50 border-slate-200">
                      <Factory className="h-5 w-5 text-slate-400" />
                    </div>
                  )}
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Link
                        to={`/tenants/${tenant.id}`}
                        className="truncate font-semibold hover:underline"
                      >
                        {tenant.name}
                      </Link>
                      <Badge
                        variant="outline"
                        className={cn("text-[10px] font-semibold", STATUS_STYLES[status])}
                      >
                        {status}
                      </Badge>
                      {preset && (
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-[10px]",
                            presetColor?.bg,
                            presetColor?.text,
                            presetColor?.border
                          )}
                        >
                          {PRESET_LABELS[preset]}
                        </Badge>
                      )}
                    </div>
                    <p className="truncate text-xs text-muted-foreground">
                      {tenant.slug}.{import.meta.env.VITE_APP_DOMAIN || "getbridgeable.com"}
                    </p>
                    {(tenant.facility_city || tenant.facility_state) && (
                      <p className="text-xs text-muted-foreground">
                        {tenant.facility_city && tenant.facility_state
                          ? `${tenant.facility_city}, ${tenant.facility_state}`
                          : tenant.facility_state || ""}
                      </p>
                    )}
                  </div>
                </div>

                {/* Middle: Contact info */}
                <div className="hidden flex-col gap-0.5 text-xs text-muted-foreground lg:flex lg:min-w-[180px]">
                  <span>{tenant.user_count} user{tenant.user_count !== 1 ? "s" : ""}</span>
                  <span>
                    Tenant since {new Date(tenant.created_at).toLocaleDateString()}
                  </span>
                  <span>{daysSinceCreated}d ago</span>
                </div>

                {/* Right: Onboarding ring + integration dot */}
                <div className="hidden items-center gap-4 md:flex">
                  <div className="flex flex-col items-center">
                    <ProgressRing percent={onboardingPercent} />
                    <span className="mt-0.5 text-[10px] text-muted-foreground">
                      Onboarding
                    </span>
                  </div>
                  <div className="flex flex-col items-center gap-1">
                    <span
                      className={cn(
                        "h-2.5 w-2.5 rounded-full",
                        tenant.is_active ? "bg-green-500" : "bg-gray-300"
                      )}
                    />
                    <span className="text-[10px] text-muted-foreground">
                      {tenant.is_active ? "Connected" : "Offline"}
                    </span>
                  </div>
                </div>

                {/* Far right: Actions */}
                <div className="flex shrink-0 items-center gap-1.5">
                  <Link
                    to={`/tenants/${tenant.id}`}
                    className="inline-flex h-7 items-center gap-1 rounded-md border px-2.5 text-xs font-medium transition-colors hover:bg-slate-50"
                  >
                    <Eye className="h-3 w-3" />
                    View
                  </Link>
                  <Button
                    variant="outline"
                    size="xs"
                    onClick={() => handleImpersonate(tenant)}
                    className="gap-1"
                  >
                    <UserCheck className="h-3 w-3" />
                    Impersonate
                  </Button>
                  <div className="relative">
                    <button
                      onClick={() =>
                        setMenuOpen(menuOpen === tenant.id ? null : tenant.id)
                      }
                      className="inline-flex h-7 w-7 items-center justify-center rounded-md border transition-colors hover:bg-slate-50"
                    >
                      <MoreHorizontal className="h-3.5 w-3.5" />
                    </button>
                    {menuOpen === tenant.id && (
                      <>
                        <div
                          className="fixed inset-0 z-10"
                          onClick={() => setMenuOpen(null)}
                        />
                        <div className="absolute right-0 top-8 z-20 w-40 rounded-lg border bg-white py-1 shadow-lg">
                          <Link
                            to={`/tenants/${tenant.id}/modules`}
                            className="block px-3 py-1.5 text-xs hover:bg-slate-50"
                            onClick={() => setMenuOpen(null)}
                          >
                            Manage Modules
                          </Link>
                          <button
                            className="block w-full px-3 py-1.5 text-left text-xs hover:bg-slate-50"
                            onClick={() => setMenuOpen(null)}
                          >
                            Edit Tenant
                          </button>
                          <button
                            className="block w-full px-3 py-1.5 text-left text-xs text-red-600 hover:bg-red-50"
                            onClick={() => setMenuOpen(null)}
                          >
                            Suspend Tenant
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
