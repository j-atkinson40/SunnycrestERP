/**
 * Admin Tenant Detail Page
 *
 * Tabbed layout with 6 tabs: Overview, Modules & Extensions, Integration,
 * Billing, Onboarding & Support, Settings.
 */

import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";
import {
  getTenant,
  impersonateTenant,
  updateTenant,
  deleteTenant,
  getTenantModules,
  setTenantModule,
  listModuleDefinitionsFlat,
} from "@/services/platform-service";
import type { TenantDetail, TenantModuleConfig, ModuleDefinition } from "@/types/platform";
import { cn } from "@/lib/utils";
import {
  Factory,
  Heart,
  TreePine,
  Flame,
  UserCheck,
  Pencil,
  MoreHorizontal,
  ChevronLeft,
  CheckCircle2,
  Circle,
  AlertCircle,
  ArrowRight,
  ExternalLink,
  Package,
  Activity,
  CreditCard,
  ClipboardList,
  Settings,
  RotateCcw,
  Trash2,
  Pause,
  MapPin,
  Globe,
  Save,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

// ---------------------------------------------------------------------------
// Preset colors
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

function getPreset(tenant: TenantDetail): string | null {
  const slug = (tenant.plan_name || tenant.slug || "").toLowerCase();
  for (const key of Object.keys(PRESET_COLORS)) {
    if (slug.includes(key)) return key;
  }
  return null;
}

// ---------------------------------------------------------------------------
// US States + Dropdown options
// ---------------------------------------------------------------------------

const US_STATES = [
  { value: "AL", label: "Alabama" }, { value: "AK", label: "Alaska" },
  { value: "AZ", label: "Arizona" }, { value: "AR", label: "Arkansas" },
  { value: "CA", label: "California" }, { value: "CO", label: "Colorado" },
  { value: "CT", label: "Connecticut" }, { value: "DE", label: "Delaware" },
  { value: "FL", label: "Florida" }, { value: "GA", label: "Georgia" },
  { value: "HI", label: "Hawaii" }, { value: "ID", label: "Idaho" },
  { value: "IL", label: "Illinois" }, { value: "IN", label: "Indiana" },
  { value: "IA", label: "Iowa" }, { value: "KS", label: "Kansas" },
  { value: "KY", label: "Kentucky" }, { value: "LA", label: "Louisiana" },
  { value: "ME", label: "Maine" }, { value: "MD", label: "Maryland" },
  { value: "MA", label: "Massachusetts" }, { value: "MI", label: "Michigan" },
  { value: "MN", label: "Minnesota" }, { value: "MS", label: "Mississippi" },
  { value: "MO", label: "Missouri" }, { value: "MT", label: "Montana" },
  { value: "NE", label: "Nebraska" }, { value: "NV", label: "Nevada" },
  { value: "NH", label: "New Hampshire" }, { value: "NJ", label: "New Jersey" },
  { value: "NM", label: "New Mexico" }, { value: "NY", label: "New York" },
  { value: "NC", label: "North Carolina" }, { value: "ND", label: "North Dakota" },
  { value: "OH", label: "Ohio" }, { value: "OK", label: "Oklahoma" },
  { value: "OR", label: "Oregon" }, { value: "PA", label: "Pennsylvania" },
  { value: "RI", label: "Rhode Island" }, { value: "SC", label: "South Carolina" },
  { value: "SD", label: "South Dakota" }, { value: "TN", label: "Tennessee" },
  { value: "TX", label: "Texas" }, { value: "UT", label: "Utah" },
  { value: "VT", label: "Vermont" }, { value: "VA", label: "Virginia" },
  { value: "WA", label: "Washington" }, { value: "WV", label: "West Virginia" },
  { value: "WI", label: "Wisconsin" }, { value: "WY", label: "Wyoming" },
];

const NPCA_OPTIONS = [
  { value: "unknown", label: "Unknown" },
  { value: "certified", label: "Certified" },
  { value: "pursuing", label: "Pursuing certification" },
  { value: "wilbert_only", label: "Wilbert standards only" },
  { value: "not_certified", label: "Not certified" },
];

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------

const TABS = [
  { key: "overview", label: "Overview", icon: Activity },
  { key: "modules", label: "Modules & Extensions", icon: Package },
  { key: "integration", label: "Integration", icon: ArrowRight },
  { key: "billing", label: "Billing", icon: CreditCard },
  { key: "onboarding", label: "Onboarding & Support", icon: ClipboardList },
  { key: "settings", label: "Settings", icon: Settings },
] as const;

type TabKey = (typeof TABS)[number]["key"];

// ---------------------------------------------------------------------------
// Onboarding checklist items (placeholder)
// ---------------------------------------------------------------------------

interface ChecklistItem {
  key: string;
  label: string;
  completed: boolean;
  completedAt?: string;
}

function getPlaceholderChecklist(tenant: TenantDetail): ChecklistItem[] {
  const hasModules = tenant.modules.some((m) => m.enabled);
  const hasUsers = tenant.users.length > 1;
  return [
    { key: "account", label: "Account created", completed: true, completedAt: tenant.created_at },
    { key: "modules", label: "Modules configured", completed: hasModules },
    { key: "users", label: "Team members invited", completed: hasUsers },
    { key: "integration", label: "Accounting integration connected", completed: false },
    { key: "first_order", label: "First order placed", completed: false },
    { key: "training", label: "Training session completed", completed: false },
  ];
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AdminTenantDetail() {
  const { tenantId } = useParams<{ tenantId: string }>();
  const navigate = useNavigate();
  const [tenant, setTenant] = useState<TenantDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [moreMenuOpen, setMoreMenuOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState("");

  // Modules tab state
  const [tenantModules, setTenantModules] = useState<TenantModuleConfig[]>([]);
  const [allModules, setAllModules] = useState<ModuleDefinition[]>([]);
  const [modulesLoading, setModulesLoading] = useState(false);

  useEffect(() => {
    if (!tenantId) return;
    getTenant(tenantId)
      .then(setTenant)
      .catch(() => toast.error("Failed to load tenant"))
      .finally(() => setLoading(false));
  }, [tenantId]);

  const loadModules = useCallback(async () => {
    if (!tenantId) return;
    setModulesLoading(true);
    try {
      const [tm, allDefs] = await Promise.all([
        getTenantModules(tenantId),
        listModuleDefinitionsFlat(),
      ]);
      setTenantModules(tm);
      setAllModules(allDefs);
    } catch {
      toast.error("Failed to load modules");
    } finally {
      setModulesLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    if (activeTab === "modules") {
      loadModules();
    }
  }, [activeTab, loadModules]);

  async function handleImpersonate() {
    if (!tenantId || !tenant) return;
    try {
      const result = await impersonateTenant(tenantId);
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

  async function handleToggleModule(moduleKey: string, enable: boolean) {
    if (!tenantId) return;
    try {
      await setTenantModule(tenantId, moduleKey, enable);
      toast.success(`Module ${enable ? "enabled" : "disabled"}`);
      loadModules();
    } catch {
      toast.error("Failed to update module");
    }
  }

  async function handleSuspend() {
    if (!tenant || !tenantId) return;
    try {
      await updateTenant(tenantId, { is_active: false });
      setTenant({ ...tenant, is_active: false });
      toast.success("Tenant suspended");
    } catch {
      toast.error("Failed to suspend tenant");
    }
  }

  async function handleActivate() {
    if (!tenant || !tenantId) return;
    try {
      await updateTenant(tenantId, { is_active: true });
      setTenant({ ...tenant, is_active: true });
      toast.success("Tenant activated");
    } catch {
      toast.error("Failed to activate tenant");
    }
  }

  async function handleDelete() {
    if (!tenant || !tenantId) return;
    if (deleteConfirm !== tenant.name) {
      toast.error("Type the tenant name exactly to confirm deletion");
      return;
    }
    try {
      await deleteTenant(tenantId);
      toast.success(`Tenant "${tenant.name}" permanently deleted`);
      navigate("/tenants");
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      const detail = axiosErr?.response?.data?.detail || "Unknown error";
      toast.error(`Failed to delete tenant: ${detail}`);
      console.error("Delete tenant error:", err);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600" />
      </div>
    );
  }
  if (!tenant) {
    return <p className="text-muted-foreground">Tenant not found.</p>;
  }

  const preset = getPreset(tenant);
  const presetColor = preset ? PRESET_COLORS[preset] : null;
  const PresetIcon = presetColor?.icon ?? Factory;
  const checklist = getPlaceholderChecklist(tenant);
  const completedCount = checklist.filter((c) => c.completed).length;
  const onboardingPercent = Math.round((completedCount / checklist.length) * 100);

  // Active and available modules
  const activeModules = tenantModules.filter((m) => m.enabled);
  const availableModules = allModules.filter(
    (def) => !tenantModules.some((tm) => tm.key === def.key && tm.enabled)
  );
  const modulesByCategory = availableModules.reduce<Record<string, ModuleDefinition[]>>(
    (acc, mod) => {
      const cat = mod.category || "Other";
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(mod);
      return acc;
    },
    {}
  );

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Breadcrumb + header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link
            to="/tenants"
            className="mb-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <ChevronLeft className="h-3 w-3" />
            Tenants
          </Link>
          <div className="flex items-center gap-3">
            <div
              className={cn(
                "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border",
                presetColor?.bg ?? "bg-slate-50",
                presetColor?.border ?? "border-slate-200"
              )}
            >
              <PresetIcon
                className={cn("h-5 w-5", presetColor?.text ?? "text-slate-400")}
              />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold">{tenant.name}</h1>
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
                <Badge
                  variant="outline"
                  className={cn(
                    "text-[10px]",
                    tenant.is_active
                      ? "bg-green-100 text-green-800 border-green-300"
                      : "bg-red-100 text-red-800 border-red-300"
                  )}
                >
                  {tenant.is_active ? "Active" : "Suspended"}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                {tenant.slug}.yourerp.com
              </p>
            </div>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <Button variant="default" size="sm" onClick={handleImpersonate} className="gap-1.5 bg-indigo-600 hover:bg-indigo-700">
            <UserCheck className="h-3.5 w-3.5" />
            Impersonate
          </Button>
          <Button variant="outline" size="sm" className="gap-1.5">
            <Pencil className="h-3.5 w-3.5" />
            Edit
          </Button>
          <div className="relative">
            <Button
              variant="outline"
              size="icon-sm"
              onClick={() => setMoreMenuOpen(!moreMenuOpen)}
            >
              <MoreHorizontal className="h-4 w-4" />
            </Button>
            {moreMenuOpen && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setMoreMenuOpen(false)}
                />
                <div className="absolute right-0 top-9 z-20 w-48 rounded-lg border bg-white py-1 shadow-lg">
                  <Link
                    to={`/tenants/${tenantId}/modules`}
                    className="flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-slate-50"
                    onClick={() => setMoreMenuOpen(false)}
                  >
                    <Package className="h-3 w-3" />
                    Manage Modules
                  </Link>
                  <button
                    className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-slate-50"
                    onClick={() => setMoreMenuOpen(false)}
                  >
                    <ExternalLink className="h-3 w-3" />
                    View in Stripe
                  </button>
                  <hr className="my-1" />
                  {tenant.is_active ? (
                    <button
                      className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-amber-600 hover:bg-amber-50"
                      onClick={() => {
                        handleSuspend();
                        setMoreMenuOpen(false);
                      }}
                    >
                      <Pause className="h-3 w-3" />
                      Suspend Tenant
                    </button>
                  ) : (
                    <button
                      className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-green-600 hover:bg-green-50"
                      onClick={() => {
                        handleActivate();
                        setMoreMenuOpen(false);
                      }}
                    >
                      <CheckCircle2 className="h-3 w-3" />
                      Activate Tenant
                    </button>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b">
        <nav className="-mb-px flex gap-4 overflow-x-auto">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={cn(
                  "flex shrink-0 items-center gap-1.5 border-b-2 px-1 pb-2 pt-1 text-sm font-medium transition-colors",
                  activeTab === tab.key
                    ? "border-indigo-600 text-indigo-600"
                    : "border-transparent text-muted-foreground hover:border-slate-300 hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === "overview" && (
        <OverviewTab
          tenant={tenant}
          checklist={checklist}
          onboardingPercent={onboardingPercent}
        />
      )}
      {activeTab === "modules" && (
        <ModulesTab
          loading={modulesLoading}
          activeModules={activeModules}
          modulesByCategory={modulesByCategory}
          onToggle={handleToggleModule}
        />
      )}
      {activeTab === "integration" && <IntegrationTab tenant={tenant} />}
      {activeTab === "billing" && <BillingTab tenant={tenant} />}
      {activeTab === "onboarding" && (
        <OnboardingTab tenant={tenant} checklist={checklist} />
      )}
      {activeTab === "settings" && (
        <SettingsTab
          tenant={tenant}
          onSuspend={handleSuspend}
          onActivate={handleActivate}
          onDelete={handleDelete}
          deleteConfirm={deleteConfirm}
          onDeleteConfirmChange={setDeleteConfirm}
        />
      )}
    </div>
  );
}

// ===========================================================================
// Tab 1 — Overview
// ===========================================================================

function OverviewTab({
  tenant,
  checklist,
  onboardingPercent,
}: {
  tenant: TenantDetail;
  checklist: ChecklistItem[];
  onboardingPercent: number;
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      {/* Onboarding checklist */}
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>
            Onboarding Progress ({onboardingPercent}%)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-3 h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-indigo-600 transition-all"
              style={{ width: `${onboardingPercent}%` }}
            />
          </div>
          <div className="space-y-2">
            {checklist.map((item) => (
              <div key={item.key} className="flex items-center gap-2 text-sm">
                {item.completed ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-green-500" />
                ) : (
                  <Circle className="h-4 w-4 shrink-0 text-slate-300" />
                )}
                <span className={item.completed ? "text-muted-foreground line-through" : ""}>
                  {item.label}
                </span>
                {item.completedAt && (
                  <span className="ml-auto text-xs text-muted-foreground">
                    {new Date(item.completedAt).toLocaleDateString()}
                  </span>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Key metrics */}
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Key Metrics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Users</span>
                <span className="font-medium">{tenant.users.length}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Active Modules</span>
                <span className="font-medium">
                  {tenant.modules.filter((m) => m.enabled).length}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Recent Syncs</span>
                <span className="font-medium">{tenant.recent_syncs.length}</span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Created</span>
                <span className="font-medium">
                  {new Date(tenant.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Check-in Call</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-sm">
              <AlertCircle className="h-4 w-4 text-amber-500" />
              <span className="text-muted-foreground">Not scheduled</span>
            </div>
            <Button variant="outline" size="xs" className="mt-2">
              Schedule Call
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Recent activity */}
      <Card className="lg:col-span-3">
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
        </CardHeader>
        <CardContent>
          {tenant.recent_syncs.length > 0 ? (
            <div className="space-y-2">
              {tenant.recent_syncs.slice(0, 8).map((s) => (
                <div key={s.id} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "h-2 w-2 rounded-full",
                        s.status === "success" ? "bg-green-500" : s.status === "error" ? "bg-red-500" : "bg-slate-300"
                      )}
                    />
                    <span>
                      {s.entity_type} {s.direction}
                    </span>
                    {s.records_synced > 0 && (
                      <span className="text-muted-foreground">
                        ({s.records_synced} records)
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {new Date(s.created_at).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No recent activity.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ===========================================================================
// Tab 2 — Modules & Extensions
// ===========================================================================

function ModulesTab({
  loading,
  activeModules,
  modulesByCategory,
  onToggle,
}: {
  loading: boolean;
  activeModules: TenantModuleConfig[];
  modulesByCategory: Record<string, ModuleDefinition[]>;
  onToggle: (key: string, enabled: boolean) => void;
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Active modules */}
      <div>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Active ({activeModules.length})
        </h3>
        {activeModules.length === 0 ? (
          <p className="text-sm text-muted-foreground">No modules enabled.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {activeModules.map((mod) => (
              <Card key={mod.key} className="relative">
                <CardContent className="flex items-center justify-between pt-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 shrink-0 rounded-full bg-green-500" />
                      <span className="truncate font-medium text-sm">{mod.name}</span>
                    </div>
                    {mod.description && (
                      <p className="mt-0.5 truncate text-xs text-muted-foreground">
                        {mod.description}
                      </p>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="xs"
                    className="shrink-0 text-red-500 hover:text-red-700"
                    onClick={() => onToggle(mod.key, false)}
                  >
                    Disable
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Available modules */}
      <div>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Available
        </h3>
        {Object.keys(modulesByCategory).length === 0 ? (
          <p className="text-sm text-muted-foreground">All modules are enabled.</p>
        ) : (
          <div className="space-y-6">
            {Object.entries(modulesByCategory).map(([category, mods]) => (
              <div key={category}>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  {category}
                </h4>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {mods.map((mod) => (
                    <Card key={mod.key} className="border-dashed">
                      <CardContent className="flex items-center justify-between pt-2">
                        <div className="min-w-0">
                          <span className="truncate text-sm font-medium">{mod.name}</span>
                          {mod.description && (
                            <p className="mt-0.5 truncate text-xs text-muted-foreground">
                              {mod.description}
                            </p>
                          )}
                        </div>
                        <Button
                          variant="outline"
                          size="xs"
                          className="shrink-0"
                          onClick={() => onToggle(mod.key, true)}
                        >
                          Enable
                        </Button>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ===========================================================================
// Tab 3 — Integration
// ===========================================================================

function IntegrationTab({ tenant }: { tenant: TenantDetail }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Accounting Integration</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Provider</span>
              <span>{tenant.subscription?.plan_name || "Not configured"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Status</span>
              <Badge
                variant="outline"
                className="bg-amber-100 text-amber-800 border-amber-300 text-[10px]"
              >
                Not connected
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Last Sync</span>
              <span>
                {tenant.recent_syncs.length > 0
                  ? new Date(tenant.recent_syncs[0].created_at).toLocaleString()
                  : "Never"}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Cross-Tenant Relationships</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No cross-tenant relationships configured.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>API Keys</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            API key management coming soon.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Webhooks</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Webhook configuration coming soon.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

// ===========================================================================
// Tab 4 — Billing
// ===========================================================================

function BillingTab({ tenant }: { tenant: TenantDetail }) {
  const sub = tenant.subscription;
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Current Plan</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Plan</span>
              <span className="font-medium">{sub?.plan_name || "Free"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Status</span>
              <Badge
                variant="outline"
                className={cn(
                  "text-[10px]",
                  sub?.status === "active"
                    ? "bg-green-100 text-green-800 border-green-300"
                    : "bg-slate-100 text-slate-600"
                )}
              >
                {sub?.status || "No subscription"}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Billing Interval</span>
              <span>{sub?.billing_interval || "N/A"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">MRR</span>
              <span className="font-semibold">$0.00</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Add-on Costs</span>
              <span>$0.00</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Invoice History</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No invoices yet. Billing integration coming soon.
          </p>
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Plan Changes</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <Button variant="outline" size="sm" disabled>
              Upgrade Plan
            </Button>
            <Button variant="outline" size="sm" disabled>
              Downgrade Plan
            </Button>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Plan changes will be available once billing integration is complete.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

// ===========================================================================
// Tab 5 — Onboarding & Support
// ===========================================================================

function OnboardingTab({
  checklist,
}: {
  tenant: TenantDetail;
  checklist: ChecklistItem[];
}) {
  const [notes, setNotes] = useState("");
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Onboarding Checklist</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {checklist.map((item) => (
              <div key={item.key} className="flex items-center gap-3 text-sm">
                {item.completed ? (
                  <CheckCircle2 className="h-5 w-5 shrink-0 text-green-500" />
                ) : (
                  <Circle className="h-5 w-5 shrink-0 text-slate-300" />
                )}
                <div className="flex-1">
                  <span className={item.completed ? "line-through text-muted-foreground" : ""}>
                    {item.label}
                  </span>
                </div>
                {item.completedAt && (
                  <span className="text-xs text-muted-foreground">
                    {new Date(item.completedAt).toLocaleDateString()}
                  </span>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>White-Glove Import</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Status</span>
              <Badge variant="outline" className="text-[10px]">
                Not requested
              </Badge>
            </div>
            <p className="text-muted-foreground">
              No data import has been requested for this tenant.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Support Notes</CardTitle>
        </CardHeader>
        <CardContent>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add internal notes about this tenant..."
            className="w-full rounded-lg border border-input bg-transparent px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/50"
            rows={4}
          />
          <div className="mt-3 flex items-center gap-3">
            <Button variant="default" size="sm">
              Save Notes
            </Button>
            <Button variant="outline" size="sm" className="gap-1.5 text-amber-600 hover:text-amber-700">
              <RotateCcw className="h-3 w-3" />
              Reset Onboarding
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ===========================================================================
// Tab 6 — Settings
// ===========================================================================

function SettingsTab({
  tenant,
  onSuspend,
  onActivate,
  onDelete,
  deleteConfirm,
  onDeleteConfirmChange,
}: {
  tenant: TenantDetail;
  onSuspend: () => void;
  onActivate: () => void;
  onDelete: () => void;
  deleteConfirm: string;
  onDeleteConfirmChange: (v: string) => void;
}) {
  const [companyForm, setCompanyForm] = useState({
    company_legal_name: tenant.company_legal_name || "",
    facility_address_line1: tenant.facility_address_line1 || "",
    facility_address_line2: tenant.facility_address_line2 || "",
    facility_city: tenant.facility_city || "",
    facility_state: tenant.facility_state || "",
    facility_zip: tenant.facility_zip || "",
    company_phone: tenant.company_phone || "",
  });
  const [companyDirty, setCompanyDirty] = useState(false);
  const [companySaving, setCompanySaving] = useState(false);

  const [intelForm, setIntelForm] = useState({
    website_url: tenant.website_url || "",
    npca_certification_status: tenant.npca_certification_status || "unknown",
    internal_admin_notes: tenant.internal_admin_notes || "",
  });
  const [intelDirty, setIntelDirty] = useState(false);
  const [intelSaving, setIntelSaving] = useState(false);

  function updateCompany(field: string, value: string) {
    setCompanyForm((f) => ({ ...f, [field]: value }));
    setCompanyDirty(true);
  }

  function updateIntel(field: string, value: string) {
    setIntelForm((f) => ({ ...f, [field]: value }));
    setIntelDirty(true);
  }

  async function saveCompanyInfo() {
    setCompanySaving(true);
    try {
      await updateTenant(tenant.id, companyForm);
      toast.success("Company information saved");
      setCompanyDirty(false);
    } catch {
      toast.error("Failed to save company information");
    } finally {
      setCompanySaving(false);
    }
  }

  async function saveIntelInfo() {
    setIntelSaving(true);
    try {
      await updateTenant(tenant.id, intelForm);
      toast.success("Platform intelligence saved");
      setIntelDirty(false);
    } catch {
      toast.error("Failed to save platform intelligence");
    } finally {
      setIntelSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Tenant Information (read-only summary) */}
      <Card>
        <CardHeader>
          <CardTitle>Tenant Information</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Tenant Name
              </label>
              <p className="text-sm font-medium">{tenant.name}</p>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Subdomain
              </label>
              <p className="text-sm font-medium">{tenant.slug}</p>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Preset / Vertical
              </label>
              <p className="text-sm font-medium">{tenant.plan_name || "None"}</p>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Created
              </label>
              <p className="text-sm font-medium">
                {new Date(tenant.created_at).toLocaleString()}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Company Information (editable) */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <MapPin className="h-4 w-4" />
              Company Information
            </CardTitle>
            <Button
              variant="default"
              size="sm"
              disabled={!companyDirty || companySaving}
              onClick={saveCompanyInfo}
              className="gap-1.5"
            >
              <Save className="h-3.5 w-3.5" />
              {companySaving ? "Saving..." : "Save"}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Company Legal Name
              </label>
              <input
                type="text"
                value={companyForm.company_legal_name}
                onChange={(e) => updateCompany("company_legal_name", e.target.value)}
                placeholder="Legal entity name"
                className="w-full rounded-md border px-3 py-1.5 text-sm"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Facility Address Line 1
              </label>
              <input
                type="text"
                value={companyForm.facility_address_line1}
                onChange={(e) => updateCompany("facility_address_line1", e.target.value)}
                placeholder="123 Industrial Blvd"
                className="w-full rounded-md border px-3 py-1.5 text-sm"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Facility Address Line 2
              </label>
              <input
                type="text"
                value={companyForm.facility_address_line2}
                onChange={(e) => updateCompany("facility_address_line2", e.target.value)}
                placeholder="Suite 100"
                className="w-full rounded-md border px-3 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                City
              </label>
              <input
                type="text"
                value={companyForm.facility_city}
                onChange={(e) => updateCompany("facility_city", e.target.value)}
                placeholder="Springfield"
                className="w-full rounded-md border px-3 py-1.5 text-sm"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  State
                </label>
                <select
                  value={companyForm.facility_state}
                  onChange={(e) => updateCompany("facility_state", e.target.value)}
                  className="w-full rounded-md border px-3 py-1.5 text-sm"
                >
                  <option value="">Select</option>
                  {US_STATES.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  Zip Code
                </label>
                <input
                  type="text"
                  value={companyForm.facility_zip}
                  onChange={(e) => updateCompany("facility_zip", e.target.value)}
                  placeholder="12345"
                  className="w-full rounded-md border px-3 py-1.5 text-sm"
                />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Company Phone
              </label>
              <input
                type="tel"
                value={companyForm.company_phone}
                onChange={(e) => updateCompany("company_phone", e.target.value)}
                placeholder="(555) 123-4567"
                className="w-full rounded-md border px-3 py-1.5 text-sm"
              />
            </div>
            <div className="flex items-end">
              <Button variant="outline" size="sm" className="gap-1.5" disabled>
                <MapPin className="h-3 w-3" />
                Re-geocode Address
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Platform Intelligence (editable) */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-4 w-4" />
              Platform Intelligence
            </CardTitle>
            <Button
              variant="default"
              size="sm"
              disabled={!intelDirty || intelSaving}
              onClick={saveIntelInfo}
              className="gap-1.5"
            >
              <Save className="h-3.5 w-3.5" />
              {intelSaving ? "Saving..." : "Save"}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Website URL
              </label>
              <div className="flex gap-2">
                <input
                  type="url"
                  value={intelForm.website_url}
                  onChange={(e) => updateIntel("website_url", e.target.value)}
                  placeholder="https://www.example.com"
                  className="flex-1 rounded-md border px-3 py-1.5 text-sm"
                />
                <Button variant="outline" size="sm" disabled>
                  Re-run Scan
                </Button>
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                NPCA Certification Status
              </label>
              <select
                value={intelForm.npca_certification_status}
                onChange={(e) => updateIntel("npca_certification_status", e.target.value)}
                className="w-full rounded-md border px-3 py-1.5 text-sm"
              >
                {NPCA_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Internal Notes
              </label>
              <textarea
                value={intelForm.internal_admin_notes}
                onChange={(e) => updateIntel("internal_admin_notes", e.target.value)}
                placeholder="Internal notes about this tenant..."
                rows={4}
                className="w-full rounded-md border px-3 py-1.5 text-sm"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Danger zone */}
      <Card className="border-red-200">
        <CardHeader>
          <CardTitle className="text-red-600">Danger Zone</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">
                  {tenant.is_active ? "Suspend Tenant" : "Activate Tenant"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {tenant.is_active
                    ? "Temporarily disable access for all users."
                    : "Re-enable access for all users."}
                </p>
              </div>
              {tenant.is_active ? (
                <Button
                  variant="outline"
                  size="sm"
                  className="border-amber-300 text-amber-600 hover:bg-amber-50"
                  onClick={onSuspend}
                >
                  <Pause className="mr-1.5 h-3 w-3" />
                  Suspend
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  className="border-green-300 text-green-600 hover:bg-green-50"
                  onClick={onActivate}
                >
                  <CheckCircle2 className="mr-1.5 h-3 w-3" />
                  Activate
                </Button>
              )}
            </div>
            <hr />
            <div>
              <div className="mb-3">
                <p className="text-sm font-medium">Delete Tenant</p>
                <p className="text-xs text-muted-foreground">
                  Permanently remove this tenant and all associated data. This
                  action cannot be undone.
                </p>
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="text"
                  value={deleteConfirm}
                  onChange={(e) => onDeleteConfirmChange(e.target.value)}
                  placeholder={`Type "${tenant.name}" to confirm`}
                  className="w-64 rounded-md border border-red-200 px-3 py-1.5 text-sm focus:border-red-400 focus:outline-none focus:ring-1 focus:ring-red-400"
                />
                <Button
                  variant="destructive"
                  size="sm"
                  disabled={deleteConfirm !== tenant.name}
                  onClick={onDelete}
                >
                  <Trash2 className="mr-1.5 h-3 w-3" />
                  Permanently Delete
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
