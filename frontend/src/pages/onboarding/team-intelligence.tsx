/**
 * Team Intelligence — Morning Briefings & Announcements configuration.
 *
 * Two contexts:
 *   /onboarding/team-intelligence → onboarding wizard with Back/Continue footer
 *   /settings/team-intelligence   → settings page with Save, history, management
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { useLocation, useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft,
  ArrowRight,
  RefreshCw,
  Check,
  Pin,
  Megaphone,
  Truck,
  Factory,
  X,
  Eye,
  Trash2,
  Clock,
  AlertTriangle,
  Info,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/auth-context";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import apiClient from "@/lib/api-client";
import { completeChecklistItem } from "@/services/onboarding-service";

// ── Types ─────────────────────────────────────────────────────────────────────

interface EmployeeConfig {
  user_id: string;
  first_name: string;
  last_name: string;
  display_title: string | null;
  track: string;
  functional_areas: string[];
  primary_area: string | null;
  primary_area_override: string | null;
  briefing_enabled: boolean;
  can_create_announcements: boolean;
}

interface TenantSettings {
  team_intelligence_configured: boolean;
  briefings_enabled_tenant_wide: boolean;
  briefing_delivery_time: string;
}

interface BriefingPreview {
  content: string | null;
  items: Array<{ number: number; text: string; priority: string }>;
  tier: string | null;
  primary_area: string | null;
  was_cached: boolean;
  generated_at: string;
  reason?: string;
}

interface BriefingHistoryEntry {
  user_id: string;
  first_name: string;
  last_name: string;
  briefing_date: string;
  primary_area: string | null;
  tier: string | null;
  generated_content: string | null;
  items: Array<{ number: number; text: string; priority: string }>;
  created_at: string | null;
}

interface AnnouncementEntry {
  id: string;
  title: string;
  body: string | null;
  priority: string;
  target_type: string;
  is_active: boolean;
  created_at: string | null;
  created_by_name: string | null;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const EXAMPLE_BRIEFINGS = {
  dispatcher: {
    title: "Dispatcher",
    items: [
      {
        number: 1,
        text: "Smith Chapel delivery 2pm — vault not confirmed in yard. Assign driver.",
        priority: "critical",
      },
      {
        number: 2,
        text: "3 orders this week have no driver assigned.",
        priority: "warning",
      },
      {
        number: 3,
        text: "Spring burial season — Riverside Memorial opens in 8 days.",
        priority: "info",
      },
    ],
  },
  office_manager: {
    title: "Office Manager",
    items: [
      {
        number: 1,
        text: "Johnson FH — $2,100 past due 45 days. Follow up.",
        priority: "critical",
      },
      {
        number: 2,
        text: "QB sync error — 2 invoices not pushed since Monday.",
        priority: "warning",
      },
      {
        number: 3,
        text: "2 completed orders with no invoice sent.",
        priority: "info",
      },
    ],
  },
  driver: {
    title: "Driver",
    content:
      "3 deliveries today: Johnson FH → Riverside 10am. Smith → Green Lawn 1pm. Davis → Forest Hills 3pm ⚠ vault not confirmed.",
  },
};

const AREA_LABELS: Record<string, string> = {
  funeral_scheduling: "Funeral Scheduling",
  invoicing_ar: "Invoicing / AR",
  safety_compliance: "Safety & Compliance",
  production_log: "Production Log",
  customer_management: "Customer Management",
  full_admin: "Full Admin",
  precast_scheduling: "Precast Scheduling",
};

const TIME_OPTIONS = [
  { value: "06:00", label: "6:00 AM" },
  { value: "06:30", label: "6:30 AM" },
  { value: "07:00", label: "7:00 AM" },
  { value: "07:30", label: "7:30 AM" },
  { value: "08:00", label: "8:00 AM" },
  { value: "08:30", label: "8:30 AM" },
  { value: "09:00", label: "9:00 AM" },
  { value: "09:30", label: "9:30 AM" },
  { value: "10:00", label: "10:00 AM" },
  { value: "10:30", label: "10:30 AM" },
  { value: "11:00", label: "11:00 AM" },
  { value: "11:30", label: "11:30 AM" },
  { value: "12:00", label: "12:00 PM" },
];

const PRIORITY_COLORS: Record<string, string> = {
  critical: "text-red-600 bg-red-50 border-red-200",
  warning: "text-amber-600 bg-amber-50 border-amber-200",
  info: "text-blue-600 bg-blue-50 border-blue-200",
};

const PRIORITY_ICONS: Record<string, React.ReactNode> = {
  critical: <AlertTriangle className="size-4 text-red-500" />,
  warning: <Clock className="size-4 text-amber-500" />,
  info: <Info className="size-4 text-blue-500" />,
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function areaLabel(key: string | null): string {
  if (!key) return "Auto-detect";
  return AREA_LABELS[key] ?? key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function TeamIntelligencePage() {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const isOnboarding = location.pathname.startsWith("/onboarding");

  // ── Tab state ───────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<"briefings" | "announcements">("briefings");
  const [briefingsTabVisited, setBriefingsTabVisited] = useState(true);
  const [announcementsTabVisited, setAnnouncementsTabVisited] = useState(false);

  // ── Data state ──────────────────────────────────────────────────────────────
  const [employees, setEmployees] = useState<EmployeeConfig[]>([]);
  const [tenantSettings, setTenantSettings] = useState<TenantSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // ── Tab 1 — Briefings state ─────────────────────────────────────────────────
  const [briefingsEnabled, setBriefingsEnabled] = useState(true);
  const [briefingTime, setBriefingTime] = useState("08:00");
  const [preview, setPreview] = useState<BriefingPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [testSent, setTestSent] = useState(false);
  const [testConfirmed, setTestConfirmed] = useState(false);
  const [employeeFilter, setEmployeeFilter] = useState<"all" | "office" | "drivers">("all");

  // ── Tab 2 — Announcements state ─────────────────────────────────────────────
  const [announcementTitle, setAnnouncementTitle] = useState("");
  const [announcementBody, setAnnouncementBody] = useState("");
  const [announcementPriority, setAnnouncementPriority] = useState("info");
  const [announcementTarget, setAnnouncementTarget] = useState("everyone");
  const [announcementPosted, setAnnouncementPosted] = useState(false);
  const [announcementSkipped, setAnnouncementSkipped] = useState(false);

  // ── Settings-page only state ────────────────────────────────────────────────
  const [history, setHistory] = useState<BriefingHistoryEntry[]>([]);
  const [managedAnnouncements, setManagedAnnouncements] = useState<AnnouncementEntry[]>([]);
  const [historyModal, setHistoryModal] = useState<BriefingHistoryEntry | null>(null);

  // ── Auto-save indicator ─────────────────────────────────────────────────────
  const [saved, setSaved] = useState(false);
  const savedTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  // ── Flash saved indicator ───────────────────────────────────────────────────
  const flashSaved = useCallback(() => {
    setSaved(true);
    if (savedTimer.current) clearTimeout(savedTimer.current);
    savedTimer.current = setTimeout(() => setSaved(false), 1500);
  }, []);

  // ── Data fetching ───────────────────────────────────────────────────────────

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [teamRes, settingsRes] = await Promise.all([
        apiClient.get("/briefings/team-config"),
        apiClient.get("/briefings/tenant-settings"),
      ]);
      setEmployees(teamRes.data);
      setTenantSettings(settingsRes.data);
      setBriefingsEnabled(settingsRes.data.briefings_enabled_tenant_wide);
      setBriefingTime(settingsRes.data.briefing_delivery_time ?? "08:00");

      // Settings page: also fetch history & managed announcements
      if (!isOnboarding) {
        const [historyRes, announcementsRes] = await Promise.all([
          apiClient.get("/briefings/history").catch(() => ({ data: [] })),
          apiClient.get("/announcements/").catch(() => ({ data: [] })),
        ]);
        setHistory(historyRes.data);
        setManagedAnnouncements(announcementsRes.data);
      }
    } catch (err) {
      console.error("Failed to load team intelligence config", err);
      toast.error("Failed to load configuration");
    } finally {
      setLoading(false);
    }
  }, [isOnboarding]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ── Employee PATCH helper ───────────────────────────────────────────────────

  const patchEmployee = useCallback(
    async (userId: string, updates: Partial<EmployeeConfig>) => {
      try {
        await apiClient.patch(`/briefings/team-config/${userId}`, updates);
        setEmployees((prev) =>
          prev.map((e) => (e.user_id === userId ? { ...e, ...updates } : e))
        );
        flashSaved();
      } catch {
        toast.error("Failed to save change");
      }
    },
    [flashSaved]
  );

  // ── Tenant settings save ────────────────────────────────────────────────────

  const saveTenantSettings = useCallback(
    async (updates: Partial<TenantSettings>) => {
      try {
        await apiClient.put("/briefings/tenant-settings", {
          ...tenantSettings,
          ...updates,
        });
        setTenantSettings((prev) => (prev ? { ...prev, ...updates } : prev));
        flashSaved();
      } catch {
        toast.error("Failed to save settings");
      }
    },
    [tenantSettings, flashSaved]
  );

  // ── Preview ─────────────────────────────────────────────────────────────────

  const fetchPreview = useCallback(async () => {
    setPreviewLoading(true);
    try {
      const { data } = await apiClient.get("/briefings/briefing");
      setPreview(data);
    } catch {
      toast.error("Failed to load preview");
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  const refreshPreview = useCallback(async () => {
    setPreviewLoading(true);
    try {
      await apiClient.post("/briefings/briefing/refresh");
      const { data } = await apiClient.get("/briefings/briefing");
      setPreview(data);
      toast.success("Preview refreshed");
    } catch {
      toast.error("Failed to refresh preview");
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  // ── Test send ───────────────────────────────────────────────────────────────

  const handleTestSend = useCallback(async () => {
    setPreviewLoading(true);
    try {
      await apiClient.post("/briefings/briefing/refresh");
      const { data } = await apiClient.get("/briefings/briefing");
      setPreview(data);
      setTestSent(true);
      toast.success("Test briefing generated");
    } catch {
      toast.error("Failed to generate test briefing");
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  // ── Post first announcement ─────────────────────────────────────────────────

  const handlePostAnnouncement = useCallback(async () => {
    if (!announcementTitle.trim()) {
      toast.error("Title is required");
      return;
    }
    setSaving(true);
    try {
      await apiClient.post("/announcements", {
        title: announcementTitle.trim(),
        body: announcementBody.trim() || null,
        priority: announcementPriority,
        target_type: announcementTarget,
      });
      setAnnouncementPosted(true);
      toast.success("Announcement posted");
    } catch {
      toast.error("Failed to post announcement");
    } finally {
      setSaving(false);
    }
  }, [announcementTitle, announcementBody, announcementPriority, announcementTarget]);

  // ── Delete announcement (settings only) ─────────────────────────────────────

  const handleDeleteAnnouncement = useCallback(
    async (id: string) => {
      try {
        await apiClient.delete(`/announcements/${id}`);
        setManagedAnnouncements((prev) => prev.filter((a) => a.id !== id));
        toast.success("Announcement deleted");
      } catch {
        toast.error("Failed to delete announcement");
      }
    },
    []
  );

  // ── Complete setup (onboarding) ─────────────────────────────────────────────

  const handleComplete = useCallback(async () => {
    setSaving(true);
    try {
      await apiClient.post("/briefings/team-config/complete-setup");
      await completeChecklistItem("setup_team_intelligence");
      toast.success("Team intelligence configured");
      navigate("/onboarding");
    } catch {
      toast.error("Failed to complete setup");
    } finally {
      setSaving(false);
    }
  }, [navigate]);

  // ── Tab switching ───────────────────────────────────────────────────────────

  const switchTab = useCallback(
    (tab: "briefings" | "announcements") => {
      setActiveTab(tab);
      if (tab === "briefings") setBriefingsTabVisited(true);
      if (tab === "announcements") setAnnouncementsTabVisited(true);
    },
    []
  );

  // ── Filtered employees ──────────────────────────────────────────────────────

  const filteredEmployees = employees.filter((e) => {
    if (employeeFilter === "office") return e.track === "office_management";
    if (employeeFilter === "drivers") return e.track === "production_delivery";
    return true;
  });

  // ── Bulk toggles ────────────────────────────────────────────────────────────

  const bulkToggleBriefings = useCallback(
    async (enabled: boolean) => {
      const targets = filteredEmployees.filter((e) => e.briefing_enabled !== enabled);
      for (const emp of targets) {
        await patchEmployee(emp.user_id, { briefing_enabled: enabled });
      }
    },
    [filteredEmployees, patchEmployee]
  );

  // ── Loading state ───────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <RefreshCw className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════════════════════════════

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-8">
      {/* ── Page header ──────────────────────────────────────────────────────── */}
      <div>
        {isOnboarding && (
          <Link
            to="/onboarding"
            className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Back to onboarding
          </Link>
        )}
        <h1 className="text-2xl font-semibold tracking-tight">Team Intelligence</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Configure morning briefings and announcements for your team.
        </p>
      </div>

      {/* ── Saved indicator ──────────────────────────────────────────────────── */}
      <div
        className={cn(
          "fixed right-6 top-6 z-50 flex items-center gap-2 rounded-lg bg-green-600 px-3 py-2 text-sm font-medium text-white shadow-lg transition-all duration-300",
          saved ? "translate-y-0 opacity-100" : "-translate-y-4 opacity-0 pointer-events-none"
        )}
      >
        <Check className="size-4" />
        Saved
      </div>

      {/* ── Tab bar ──────────────────────────────────────────────────────────── */}
      <div className="flex gap-1 rounded-lg bg-muted p-1">
        <button
          onClick={() => switchTab("briefings")}
          className={cn(
            "flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors",
            activeTab === "briefings"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          <Clock className="mr-2 inline size-4" />
          Morning Briefings
        </button>
        <button
          onClick={() => switchTab("announcements")}
          className={cn(
            "flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors",
            activeTab === "announcements"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          <Megaphone className="mr-2 inline size-4" />
          Announcements
        </button>
      </div>

      {/* ═════════════════════════════════════════════════════════════════════════
          TAB 1 — Morning Briefings
          ═════════════════════════════════════════════════════════════════════════ */}
      {activeTab === "briefings" && (
        <div className="space-y-6">
          {/* ── Section A: Master Switch ────────────────────────────────────── */}
          <Card>
            <CardHeader>
              <CardTitle>Briefing Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Enable / Disable */}
              <div className="space-y-2">
                <p className="text-sm font-medium">Morning briefings</p>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="radio"
                      name="briefings-enabled"
                      checked={briefingsEnabled}
                      onChange={() => {
                        setBriefingsEnabled(true);
                        saveTenantSettings({ briefings_enabled_tenant_wide: true });
                      }}
                      className="accent-primary"
                    />
                    Enabled for this company
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="radio"
                      name="briefings-enabled"
                      checked={!briefingsEnabled}
                      onChange={() => {
                        setBriefingsEnabled(false);
                        saveTenantSettings({ briefings_enabled_tenant_wide: false });
                      }}
                      className="accent-primary"
                    />
                    Disabled
                  </label>
                </div>
              </div>

              {/* Delivery time */}
              {briefingsEnabled && (
                <div className="space-y-1">
                  <label className="text-sm font-medium" htmlFor="briefing-time">
                    Delivery time
                  </label>
                  <select
                    id="briefing-time"
                    value={briefingTime}
                    onChange={(e) => {
                      setBriefingTime(e.target.value);
                      saveTenantSettings({ briefing_delivery_time: e.target.value });
                    }}
                    className="block w-48 rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    {TIME_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-muted-foreground">
                    Each team member receives their briefing at this time.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Remaining sections only when enabled */}
          {briefingsEnabled && (
            <>
              {/* ── Section B: Employee Table ──────────────────────────────── */}
              <Card>
                <CardHeader>
                  <CardTitle>Team Members</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Filter bar */}
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium text-muted-foreground">Show:</span>
                    {(["all", "office", "drivers"] as const).map((f) => (
                      <button
                        key={f}
                        onClick={() => setEmployeeFilter(f)}
                        className={cn(
                          "rounded-md px-3 py-1 text-sm transition-colors",
                          employeeFilter === f
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted text-muted-foreground hover:text-foreground"
                        )}
                      >
                        {f === "all" && "All"}
                        {f === "office" && (
                          <>
                            <Factory className="mr-1 inline size-3.5" />
                            Office
                          </>
                        )}
                        {f === "drivers" && (
                          <>
                            <Truck className="mr-1 inline size-3.5" />
                            Drivers
                          </>
                        )}
                      </button>
                    ))}

                    {/* Bulk toggles */}
                    <div className="ml-auto flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => bulkToggleBriefings(true)}
                      >
                        Enable all shown
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => bulkToggleBriefings(false)}
                      >
                        Disable all shown
                      </Button>
                    </div>
                  </div>

                  {/* Table */}
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-muted-foreground">
                          <th className="pb-2 font-medium">Employee</th>
                          <th className="pb-2 font-medium">Primary Focus</th>
                          <th className="pb-2 text-center font-medium">Briefing</th>
                          <th className="pb-2 text-center font-medium">Preview</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {filteredEmployees.length === 0 && (
                          <tr>
                            <td
                              colSpan={4}
                              className="py-6 text-center text-muted-foreground"
                            >
                              No employees match this filter.
                            </td>
                          </tr>
                        )}
                        {filteredEmployees.map((emp) => (
                          <tr key={emp.user_id} className="group">
                            {/* Name + title */}
                            <td className="py-3 pr-4">
                              <div className="font-medium">
                                {emp.first_name} {emp.last_name}
                              </div>
                              {emp.display_title && (
                                <div className="text-xs text-muted-foreground">
                                  {emp.display_title}
                                </div>
                              )}
                              <div className="mt-0.5 text-xs text-muted-foreground">
                                {emp.track === "office_management" ? (
                                  <span className="inline-flex items-center gap-1">
                                    <Factory className="size-3" /> Office
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1">
                                    <Truck className="size-3" /> Driver
                                  </span>
                                )}
                              </div>
                            </td>

                            {/* Primary focus (auto-detect + override) */}
                            <td className="py-3 pr-4">
                              <div className="flex items-center gap-2">
                                <span className="text-xs text-muted-foreground">
                                  Auto: {areaLabel(emp.primary_area)}
                                </span>
                              </div>
                              <select
                                value={emp.primary_area_override ?? ""}
                                onChange={(e) =>
                                  patchEmployee(emp.user_id, {
                                    primary_area_override: e.target.value || null,
                                  })
                                }
                                className="mt-1 block w-full max-w-[200px] rounded-md border border-input bg-background px-2 py-1 text-xs shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                              >
                                <option value="">Use auto-detect</option>
                                {Object.entries(AREA_LABELS).map(([key, label]) => (
                                  <option key={key} value={key}>
                                    {label}
                                  </option>
                                ))}
                              </select>
                            </td>

                            {/* Briefing toggle */}
                            <td className="py-3 text-center">
                              <button
                                onClick={() =>
                                  patchEmployee(emp.user_id, {
                                    briefing_enabled: !emp.briefing_enabled,
                                  })
                                }
                                className={cn(
                                  "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
                                  emp.briefing_enabled ? "bg-primary" : "bg-muted"
                                )}
                              >
                                <span
                                  className={cn(
                                    "pointer-events-none inline-block size-5 rounded-full bg-white shadow ring-0 transition-transform",
                                    emp.briefing_enabled
                                      ? "translate-x-5"
                                      : "translate-x-0"
                                  )}
                                />
                              </button>
                            </td>

                            {/* Preview link */}
                            <td className="py-3 text-center">
                              <button
                                onClick={() => {
                                  fetchPreview();
                                }}
                                className="text-primary hover:underline"
                              >
                                <Eye className="inline size-4" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>

              {/* ── Settings page: Briefing History ────────────────────────── */}
              {!isOnboarding && history.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Briefing History</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-left text-muted-foreground">
                            <th className="pb-2 font-medium">Employee</th>
                            <th className="pb-2 font-medium">Date</th>
                            <th className="pb-2 font-medium">Focus Area</th>
                            <th className="pb-2 font-medium">Tier</th>
                            <th className="pb-2 text-center font-medium">View</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y">
                          {history.map((entry, idx) => (
                            <tr key={`${entry.user_id}-${entry.briefing_date}-${idx}`}>
                              <td className="py-2 pr-4 font-medium">
                                {entry.first_name} {entry.last_name}
                              </td>
                              <td className="py-2 pr-4">
                                {formatDate(entry.briefing_date)}
                              </td>
                              <td className="py-2 pr-4">
                                {areaLabel(entry.primary_area)}
                              </td>
                              <td className="py-2 pr-4 capitalize">
                                {entry.tier ?? "—"}
                              </td>
                              <td className="py-2 text-center">
                                <button
                                  onClick={() => setHistoryModal(entry)}
                                  className="text-primary hover:underline"
                                >
                                  <Eye className="inline size-4" />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* ── History modal ──────────────────────────────────────────── */}
              {historyModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
                  <div className="w-full max-w-lg rounded-xl bg-background p-6 shadow-xl">
                    <div className="mb-4 flex items-start justify-between">
                      <div>
                        <h3 className="text-lg font-semibold">
                          {historyModal.first_name} {historyModal.last_name}
                        </h3>
                        <p className="text-sm text-muted-foreground">
                          {formatDate(historyModal.briefing_date)} &middot;{" "}
                          {areaLabel(historyModal.primary_area)}
                        </p>
                      </div>
                      <button
                        onClick={() => setHistoryModal(null)}
                        className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                      >
                        <X className="size-5" />
                      </button>
                    </div>

                    {/* Items */}
                    {historyModal.items && historyModal.items.length > 0 ? (
                      <ul className="space-y-2">
                        {historyModal.items.map((item) => (
                          <li
                            key={item.number}
                            className={cn(
                              "flex items-start gap-3 rounded-lg border p-3",
                              PRIORITY_COLORS[item.priority] ?? PRIORITY_COLORS.info
                            )}
                          >
                            <span className="mt-0.5">
                              {PRIORITY_ICONS[item.priority] ?? PRIORITY_ICONS.info}
                            </span>
                            <span className="text-sm">{item.text}</span>
                          </li>
                        ))}
                      </ul>
                    ) : historyModal.generated_content ? (
                      <p className="rounded-lg bg-muted p-4 text-sm whitespace-pre-wrap">
                        {historyModal.generated_content}
                      </p>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No briefing content available.
                      </p>
                    )}

                    <div className="mt-4 flex justify-end">
                      <Button variant="outline" onClick={() => setHistoryModal(null)}>
                        Close
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {/* ── Section C: Preview ─────────────────────────────────────── */}
              <Card>
                <CardHeader>
                  <CardTitle>Preview</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* C1: Live preview */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-medium">Your live preview</h4>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={preview ? refreshPreview : fetchPreview}
                        disabled={previewLoading}
                      >
                        <RefreshCw
                          className={cn(
                            "mr-1.5 size-3.5",
                            previewLoading && "animate-spin"
                          )}
                        />
                        {preview ? "Refresh" : "Load preview"}
                      </Button>
                    </div>

                    {preview ? (
                      <div className="rounded-lg border bg-muted/30 p-4">
                        <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                          <span>
                            Focus: {areaLabel(preview.primary_area)} &middot; Tier:{" "}
                            {preview.tier ?? "—"}
                          </span>
                          {preview.was_cached && (
                            <span className="rounded bg-muted px-1.5 py-0.5 text-xs">
                              cached
                            </span>
                          )}
                        </div>
                        {preview.items && preview.items.length > 0 ? (
                          <ul className="space-y-2">
                            {preview.items.map((item) => (
                              <li
                                key={item.number}
                                className={cn(
                                  "flex items-start gap-3 rounded-lg border p-3",
                                  PRIORITY_COLORS[item.priority] ?? PRIORITY_COLORS.info
                                )}
                              >
                                <span className="mt-0.5">
                                  {PRIORITY_ICONS[item.priority] ?? PRIORITY_ICONS.info}
                                </span>
                                <span className="text-sm">{item.text}</span>
                              </li>
                            ))}
                          </ul>
                        ) : preview.content ? (
                          <p className="text-sm whitespace-pre-wrap">{preview.content}</p>
                        ) : (
                          <p className="text-sm text-muted-foreground">
                            {preview.reason ?? "No briefing content generated yet."}
                          </p>
                        )}
                        <p className="mt-2 text-xs text-muted-foreground">
                          Generated {formatDateTime(preview.generated_at)}
                        </p>
                      </div>
                    ) : (
                      <div className="flex h-24 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
                        Click "Load preview" to see your briefing
                      </div>
                    )}
                  </div>

                  {/* C2: Example briefings */}
                  <div className="space-y-3">
                    <h4 className="text-sm font-medium">
                      Example briefings by role
                    </h4>
                    <div className="grid gap-4 sm:grid-cols-3">
                      {/* Dispatcher example */}
                      <div className="rounded-lg border p-4">
                        <h5 className="mb-2 text-sm font-semibold">
                          {EXAMPLE_BRIEFINGS.dispatcher.title}
                        </h5>
                        <ul className="space-y-1.5">
                          {EXAMPLE_BRIEFINGS.dispatcher.items.map((item) => (
                            <li
                              key={item.number}
                              className={cn(
                                "flex items-start gap-2 rounded border p-2 text-xs",
                                PRIORITY_COLORS[item.priority]
                              )}
                            >
                              <span className="mt-0.5 shrink-0">
                                {PRIORITY_ICONS[item.priority]}
                              </span>
                              <span>{item.text}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* Office Manager example */}
                      <div className="rounded-lg border p-4">
                        <h5 className="mb-2 text-sm font-semibold">
                          {EXAMPLE_BRIEFINGS.office_manager.title}
                        </h5>
                        <ul className="space-y-1.5">
                          {EXAMPLE_BRIEFINGS.office_manager.items.map((item) => (
                            <li
                              key={item.number}
                              className={cn(
                                "flex items-start gap-2 rounded border p-2 text-xs",
                                PRIORITY_COLORS[item.priority]
                              )}
                            >
                              <span className="mt-0.5 shrink-0">
                                {PRIORITY_ICONS[item.priority]}
                              </span>
                              <span>{item.text}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* Driver example */}
                      <div className="rounded-lg border p-4">
                        <h5 className="mb-2 text-sm font-semibold">
                          {EXAMPLE_BRIEFINGS.driver.title}
                        </h5>
                        <p className="text-xs leading-relaxed">
                          {EXAMPLE_BRIEFINGS.driver.content}
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* ── Section D: Test Send ────────────────────────────────────── */}
              <Card>
                <CardHeader>
                  <CardTitle>Test Your Briefing</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {!testSent ? (
                    <>
                      <p className="text-sm text-muted-foreground">
                        Generate a test briefing for your account to see how it
                        looks. This won't be sent to anyone else.
                      </p>
                      <Button onClick={handleTestSend} disabled={previewLoading}>
                        {previewLoading ? (
                          <>
                            <RefreshCw className="mr-2 size-4 animate-spin" />
                            Generating...
                          </>
                        ) : (
                          <>Generate test briefing</>
                        )}
                      </Button>
                    </>
                  ) : !testConfirmed ? (
                    <div className="space-y-4">
                      <div className="rounded-lg border border-green-200 bg-green-50 p-4">
                        <div className="mb-2 flex items-center gap-2 text-sm font-medium text-green-700">
                          <Check className="size-4" />
                          Test briefing generated
                        </div>
                        {preview && preview.items && preview.items.length > 0 ? (
                          <ul className="space-y-1.5">
                            {preview.items.map((item) => (
                              <li
                                key={item.number}
                                className={cn(
                                  "flex items-start gap-2 rounded border p-2 text-xs",
                                  PRIORITY_COLORS[item.priority]
                                )}
                              >
                                <span className="mt-0.5 shrink-0">
                                  {PRIORITY_ICONS[item.priority]}
                                </span>
                                <span>{item.text}</span>
                              </li>
                            ))}
                          </ul>
                        ) : preview?.content ? (
                          <p className="text-sm">{preview.content}</p>
                        ) : (
                          <p className="text-sm text-muted-foreground">
                            No items generated — this may happen when the system
                            has no data to brief on yet.
                          </p>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <Button onClick={() => setTestConfirmed(true)}>
                          <Check className="mr-2 size-4" />
                          Looks good
                        </Button>
                        <Button variant="outline" onClick={handleTestSend}>
                          <RefreshCw className="mr-2 size-4" />
                          Regenerate
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 p-4 text-sm font-medium text-green-700">
                      <Check className="size-4" />
                      Briefing confirmed — looking good!
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════════
          TAB 2 — Announcements
          ═════════════════════════════════════════════════════════════════════════ */}
      {activeTab === "announcements" && (
        <div className="space-y-6">
          {/* ── Section A: Overview ─────────────────────────────────────────── */}
          <Card>
            <CardHeader>
              <CardTitle>Announcements</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <p className="text-sm text-muted-foreground">
                Announcements appear at the top of every team member's briefing.
                They're great for company-wide messages, policy reminders, or
                seasonal updates.
              </p>
              <div className="flex items-center gap-3 rounded-lg border bg-muted/30 p-3">
                <Pin className="size-5 text-primary" />
                <div className="text-sm">
                  <span className="font-medium">Pinned announcements</span> appear
                  in every briefing until unpinned. Regular announcements show once.
                </div>
              </div>
            </CardContent>
          </Card>

          {/* ── Section B: Permission Checklist ─────────────────────────────── */}
          <Card>
            <CardHeader>
              <CardTitle>Who can create announcements?</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="mb-3 text-sm text-muted-foreground">
                Select which team members can post announcements.
              </p>
              <div className="divide-y">
                {employees
                  .filter((e) => e.track === "office_management")
                  .map((emp) => {
                    const isOwner = emp.user_id === user?.id;
                    return (
                      <label
                        key={emp.user_id}
                        className={cn(
                          "flex items-center gap-3 py-3",
                          isOwner
                            ? "cursor-default opacity-75"
                            : "cursor-pointer hover:bg-muted/30"
                        )}
                      >
                        <input
                          type="checkbox"
                          checked={emp.can_create_announcements}
                          disabled={isOwner}
                          onChange={() =>
                            patchEmployee(emp.user_id, {
                              can_create_announcements: !emp.can_create_announcements,
                            })
                          }
                          className="size-4 accent-primary"
                        />
                        <div>
                          <span className="text-sm font-medium">
                            {emp.first_name} {emp.last_name}
                          </span>
                          {isOwner && (
                            <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                              Owner — always enabled
                            </span>
                          )}
                          {emp.display_title && (
                            <div className="text-xs text-muted-foreground">
                              {emp.display_title}
                            </div>
                          )}
                        </div>
                      </label>
                    );
                  })}
              </div>
            </CardContent>
          </Card>

          {/* ── Settings page: Announcement Management ─────────────────────── */}
          {!isOnboarding && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Manage Announcements</CardTitle>
                <Button
                  size="sm"
                  onClick={() => {
                    setAnnouncementPosted(false);
                    setAnnouncementSkipped(false);
                    setAnnouncementTitle("");
                    setAnnouncementBody("");
                    setAnnouncementPriority("info");
                    setAnnouncementTarget("everyone");
                  }}
                >
                  + New Announcement
                </Button>
              </CardHeader>
              <CardContent>
                {managedAnnouncements.length === 0 ? (
                  <p className="py-4 text-center text-sm text-muted-foreground">
                    No announcements yet.
                  </p>
                ) : (
                  <div className="divide-y">
                    {managedAnnouncements.map((ann) => (
                      <div
                        key={ann.id}
                        className="flex items-start justify-between gap-3 py-3"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium">{ann.title}</span>
                            <span
                              className={cn(
                                "rounded px-1.5 py-0.5 text-xs font-medium",
                                ann.priority === "critical"
                                  ? "bg-red-100 text-red-700"
                                  : ann.priority === "warning"
                                    ? "bg-amber-100 text-amber-700"
                                    : "bg-blue-100 text-blue-700"
                              )}
                            >
                              {ann.priority}
                            </span>
                            {!ann.is_active && (
                              <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                                inactive
                              </span>
                            )}
                          </div>
                          {ann.body && (
                            <p className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
                              {ann.body}
                            </p>
                          )}
                          <div className="mt-1 flex gap-3 text-xs text-muted-foreground">
                            <span>Target: {ann.target_type}</span>
                            <span>By: {ann.created_by_name ?? "—"}</span>
                            <span>{formatDateTime(ann.created_at)}</span>
                          </div>
                        </div>
                        <button
                          onClick={() => handleDeleteAnnouncement(ann.id)}
                          className="shrink-0 rounded-md p-1.5 text-muted-foreground hover:bg-red-50 hover:text-red-600"
                          title="Delete announcement"
                        >
                          <Trash2 className="size-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* ── Section C: First Announcement (or new announcement form) ──── */}
          {!announcementPosted && !announcementSkipped && (
            <Card>
              <CardHeader>
                <CardTitle>
                  {isOnboarding
                    ? "Post your first announcement"
                    : "New Announcement"}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {isOnboarding && (
                  <p className="text-sm text-muted-foreground">
                    Get started with a welcome message or seasonal reminder. You
                    can always edit or delete this later.
                  </p>
                )}

                {/* Title */}
                <div className="space-y-1">
                  <label
                    htmlFor="ann-title"
                    className="text-sm font-medium"
                  >
                    Title
                  </label>
                  <input
                    id="ann-title"
                    type="text"
                    placeholder="e.g. Spring burial season reminder"
                    value={announcementTitle}
                    onChange={(e) => setAnnouncementTitle(e.target.value)}
                    maxLength={120}
                    className="block w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>

                {/* Body */}
                <div className="space-y-1">
                  <label
                    htmlFor="ann-body"
                    className="text-sm font-medium"
                  >
                    Body{" "}
                    <span className="font-normal text-muted-foreground">
                      (optional)
                    </span>
                  </label>
                  <textarea
                    id="ann-body"
                    rows={3}
                    placeholder="Add more details..."
                    value={announcementBody}
                    onChange={(e) => setAnnouncementBody(e.target.value)}
                    maxLength={500}
                    className="block w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <p className="text-right text-xs text-muted-foreground">
                    {announcementBody.length}/500
                  </p>
                </div>

                {/* Target */}
                <div className="space-y-1">
                  <p className="text-sm font-medium">Target audience</p>
                  <div className="flex flex-wrap gap-3">
                    {[
                      { value: "everyone", label: "Everyone" },
                      { value: "office", label: "Office only" },
                      { value: "drivers", label: "Drivers only" },
                    ].map((opt) => (
                      <label
                        key={opt.value}
                        className="flex items-center gap-2 text-sm"
                      >
                        <input
                          type="radio"
                          name="ann-target"
                          value={opt.value}
                          checked={announcementTarget === opt.value}
                          onChange={() => setAnnouncementTarget(opt.value)}
                          className="accent-primary"
                        />
                        {opt.label}
                      </label>
                    ))}
                  </div>
                </div>

                {/* Priority */}
                <div className="space-y-1">
                  <p className="text-sm font-medium">Priority</p>
                  <div className="flex flex-wrap gap-3">
                    {[
                      { value: "info", label: "Info", icon: <Info className="size-3.5 text-blue-500" /> },
                      { value: "warning", label: "Warning", icon: <Clock className="size-3.5 text-amber-500" /> },
                      { value: "critical", label: "Critical", icon: <AlertTriangle className="size-3.5 text-red-500" /> },
                    ].map((opt) => (
                      <label
                        key={opt.value}
                        className={cn(
                          "flex cursor-pointer items-center gap-2 rounded-md border px-3 py-1.5 text-sm transition-colors",
                          announcementPriority === opt.value
                            ? "border-primary bg-primary/5 font-medium"
                            : "border-input hover:border-primary/50"
                        )}
                      >
                        <input
                          type="radio"
                          name="ann-priority"
                          value={opt.value}
                          checked={announcementPriority === opt.value}
                          onChange={() => setAnnouncementPriority(opt.value)}
                          className="sr-only"
                        />
                        {opt.icon}
                        {opt.label}
                      </label>
                    ))}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-3 pt-2">
                  <Button
                    onClick={handlePostAnnouncement}
                    disabled={saving || !announcementTitle.trim()}
                  >
                    {saving ? (
                      <>
                        <RefreshCw className="mr-2 size-4 animate-spin" />
                        Posting...
                      </>
                    ) : (
                      <>
                        <Megaphone className="mr-2 size-4" />
                        Post announcement
                      </>
                    )}
                  </Button>
                  {isOnboarding && (
                    <button
                      onClick={() => setAnnouncementSkipped(true)}
                      className="text-sm text-muted-foreground hover:text-foreground"
                    >
                      Skip for now
                    </button>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Posted confirmation */}
          {announcementPosted && (
            <Card>
              <CardContent className="py-6">
                <div className="flex items-center gap-3 text-green-700">
                  <div className="flex size-8 items-center justify-center rounded-full bg-green-100">
                    <Check className="size-5" />
                  </div>
                  <div>
                    <p className="font-medium">Announcement posted!</p>
                    <p className="text-sm text-muted-foreground">
                      "{announcementTitle}" will appear in your team's next
                      briefing.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Skipped confirmation */}
          {announcementSkipped && !announcementPosted && (
            <Card>
              <CardContent className="py-6">
                <p className="text-sm text-muted-foreground">
                  No problem — you can create announcements anytime from the Team
                  Intelligence settings page.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════════
          FOOTER — Onboarding only
          ═════════════════════════════════════════════════════════════════════════ */}
      {isOnboarding && (
        <div className="sticky bottom-0 -mx-4 flex items-center justify-between border-t bg-background/95 px-4 py-4 backdrop-blur-sm">
          {/* Left: Back */}
          <Link
            to="/onboarding"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Back
          </Link>

          {/* Center: Completion indicators */}
          <div className="hidden text-sm text-muted-foreground sm:flex sm:items-center sm:gap-3">
            <span
              className={cn(
                "inline-flex items-center gap-1",
                briefingsTabVisited ? "text-green-600" : ""
              )}
            >
              Morning Briefings
              {briefingsTabVisited && <Check className="size-3.5" />}
            </span>
            <span className="text-muted-foreground/50">&middot;</span>
            <span
              className={cn(
                "inline-flex items-center gap-1",
                announcementsTabVisited ? "text-green-600" : ""
              )}
            >
              Announcements
              {announcementsTabVisited && <Check className="size-3.5" />}
            </span>
          </div>

          {/* Right: Continue */}
          <Button
            onClick={handleComplete}
            disabled={saving || !(briefingsTabVisited && announcementsTabVisited)}
          >
            {saving ? (
              <>
                <RefreshCw className="mr-2 size-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                Save and continue
                <ArrowRight className="ml-2 size-4" />
              </>
            )}
          </Button>
        </div>
      )}

      {/* ═════════════════════════════════════════════════════════════════════════
          SAVE BUTTON — Settings page only
          ═════════════════════════════════════════════════════════════════════════ */}
      {!isOnboarding && (
        <div className="flex justify-end">
          <Button
            onClick={() => {
              saveTenantSettings({
                briefings_enabled_tenant_wide: briefingsEnabled,
                briefing_delivery_time: briefingTime,
              });
              toast.success("Settings saved");
            }}
          >
            <Check className="mr-2 size-4" />
            Save settings
          </Button>
        </div>
      )}
    </div>
  );
}
