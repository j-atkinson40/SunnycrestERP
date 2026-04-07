import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { useDevice } from "@/contexts/device-context";
import apiClient from "@/lib/api-client";
import {
  Users,
  GraduationCap,
  ShieldCheck,
  Truck,
  Bell,
  ChevronRight,
  AlertTriangle,
  Clock,
  CheckCircle2,
  XCircle,
  Building2,
  Calendar,
  Route,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RosterEmployee {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  track: string;
  is_driver: boolean;
  position: string | null;
  department: string | null;
  department_id: string | null;
  hire_date: string | null;
  phone: string | null;
}

interface RosterData {
  total: number;
  by_track: Record<string, number>;
  by_department: Record<string, number>;
  employees: RosterEmployee[];
}

interface TrainingData {
  total_requirements: number;
  total_employees: number;
  total_records: number;
  completed: number;
  expired: number;
  expiring_soon: number;
  completion_rate: number;
  expiring_items: Array<{
    employee_id: string;
    training_event_id: string;
    expiry_date: string | null;
    completion_status: string;
  }>;
  expired_items: Array<{
    employee_id: string;
    training_event_id: string;
    expiry_date: string | null;
    completion_status: string;
  }>;
}

interface SafetyCertItem {
  id: string;
  employee_id: string;
  employee_name: string;
  training_event_id: string;
  expiry_date: string | null;
  days_remaining: number;
  is_expired: boolean;
  completion_status: string;
}

interface SafetyCertsData {
  total: number;
  expired_count: number;
  items: SafetyCertItem[];
}

interface DriverPerf {
  driver_id: string;
  employee_id: string;
  name: string;
  license_expiry: string | null;
  routes_total: number;
  routes_completed: number;
  completion_rate: number;
  total_stops: number;
  total_mileage: number;
}

interface DriverPerfData {
  period_days: number;
  total_drivers: number;
  drivers: DriverPerf[];
}

interface AnnouncementItem {
  id: string;
  title: string;
  message: string;
  type: string;
  category: string | null;
  link: string | null;
  is_read: boolean;
  created_at: string | null;
}

interface AnnouncementsData {
  total: number;
  unread: number;
  items: AnnouncementItem[];
}

// ---------------------------------------------------------------------------
// Role-based visibility
// ---------------------------------------------------------------------------

type ViewRole = "owner" | "manager" | "hr" | "employee";

function inferViewRole(isAdmin: boolean, hasEmployeesView: boolean, hasSafetyView: boolean): ViewRole {
  if (isAdmin) return "owner";
  if (hasEmployeesView && hasSafetyView) return "manager";
  if (hasEmployeesView) return "hr";
  return "employee";
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function TeamDashboardPage() {
  const { effectiveDevice } = useDevice();
  const isMobile = effectiveDevice === "mobile" || effectiveDevice === "tablet";

  return isMobile ? <TeamDashboardMobile /> : <TeamDashboardDesktop />;
}

// ---------------------------------------------------------------------------
// Shared Data Hook
// ---------------------------------------------------------------------------

function useTeamData() {
  const { isAdmin, hasPermission } = useAuth();
  const viewRole = inferViewRole(isAdmin, hasPermission("employees.view"), hasPermission("safety.view"));

  const [roster, setRoster] = useState<RosterData | null>(null);
  const [training, setTraining] = useState<TrainingData | null>(null);
  const [safetyCerts, setSafetyCerts] = useState<SafetyCertsData | null>(null);
  const [driverPerf, setDriverPerf] = useState<DriverPerfData | null>(null);
  const [announcements, setAnnouncements] = useState<AnnouncementsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const promises: Promise<void>[] = [];

    if (viewRole !== "employee") {
      promises.push(
        apiClient.get("/api/v1/widget-data/team/roster").then((r) => setRoster(r.data)).catch(() => {}),
        apiClient.get("/api/v1/widget-data/team/training-status").then((r) => setTraining(r.data)).catch(() => {}),
        apiClient.get("/api/v1/widget-data/team/safety-certs-due").then((r) => setSafetyCerts(r.data)).catch(() => {}),
      );
    }

    if (viewRole === "owner" || viewRole === "manager") {
      promises.push(
        apiClient.get("/api/v1/widget-data/team/driver-performance").then((r) => setDriverPerf(r.data)).catch(() => {}),
      );
    }

    promises.push(
      apiClient.get("/api/v1/widget-data/team/announcements").then((r) => setAnnouncements(r.data)).catch(() => {}),
    );

    Promise.all(promises).finally(() => setLoading(false));
  }, [viewRole]);

  return { viewRole, roster, training, safetyCerts, driverPerf, announcements, loading };
}

// ---------------------------------------------------------------------------
// Desktop Layout
// ---------------------------------------------------------------------------

function TeamDashboardDesktop() {
  const navigate = useNavigate();
  const { viewRole, roster, training, safetyCerts, driverPerf, announcements, loading } = useTeamData();

  if (loading) {
    return (
      <div className="space-y-6 p-6">
        <div className="h-8 w-48 animate-pulse rounded bg-gray-200" />
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-32 animate-pulse rounded-lg border bg-gray-50" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Team Dashboard</h1>
        <p className="text-sm text-gray-500">
          {viewRole === "owner" && "Complete team overview"}
          {viewRole === "manager" && "Team management view"}
          {viewRole === "hr" && "HR & personnel view"}
          {viewRole === "employee" && "Team updates"}
        </p>
      </div>

      {/* Summary Cards Row */}
      {viewRole !== "employee" && roster && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            icon={<Users className="h-5 w-5 text-blue-600" />}
            label="Team Members"
            value={roster.total}
            sub={`${roster.by_track["production_delivery"] || 0} production · ${roster.by_track["office_management"] || 0} office`}
          />
          <StatCard
            icon={<GraduationCap className="h-5 w-5 text-emerald-600" />}
            label="Training Completion"
            value={training ? `${training.completion_rate}%` : "--"}
            sub={training ? `${training.expired} expired · ${training.expiring_soon} due soon` : ""}
            alert={(training?.expired ?? 0) > 0}
          />
          <StatCard
            icon={<ShieldCheck className="h-5 w-5 text-amber-600" />}
            label="Safety Certs Due"
            value={safetyCerts?.total ?? 0}
            sub={safetyCerts ? `${safetyCerts.expired_count} expired` : ""}
            alert={(safetyCerts?.expired_count ?? 0) > 0}
          />
          <StatCard
            icon={<Truck className="h-5 w-5 text-purple-600" />}
            label="Active Drivers"
            value={driverPerf?.total_drivers ?? roster.employees.filter((e) => e.is_driver).length}
            sub={driverPerf ? `${driverPerf.period_days}-day period` : ""}
          />
        </div>
      )}

      {/* Main Grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Column — 2/3 width */}
        <div className="space-y-6 lg:col-span-2">
          {/* Team Roster */}
          {viewRole !== "employee" && roster && (
            <WidgetCard title="Team Roster" icon={<Users className="h-4 w-4" />} action={{ label: "Manage", onClick: () => navigate("/admin/users") }}>
              <div className="divide-y">
                {Object.entries(roster.by_department).map(([dept, count]) => (
                  <div key={dept} className="flex items-center justify-between py-2.5">
                    <div className="flex items-center gap-2">
                      <Building2 className="h-4 w-4 text-gray-400" />
                      <span className="text-sm font-medium text-gray-700">{dept}</span>
                    </div>
                    <span className="text-sm tabular-nums text-gray-500">{count} members</span>
                  </div>
                ))}
              </div>
              {/* Recent hires */}
              {roster.employees.filter((e) => e.hire_date).length > 0 && (
                <div className="mt-4 border-t pt-4">
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">Recent Hires</p>
                  <div className="space-y-2">
                    {roster.employees
                      .filter((e) => e.hire_date)
                      .sort((a, b) => (b.hire_date ?? "").localeCompare(a.hire_date ?? ""))
                      .slice(0, 3)
                      .map((e) => (
                        <div key={e.id} className="flex items-center justify-between text-sm">
                          <span className="font-medium text-gray-700">
                            {e.first_name} {e.last_name}
                          </span>
                          <span className="text-gray-400">
                            {e.position || e.track} · {e.hire_date}
                          </span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </WidgetCard>
          )}

          {/* Driver Performance — owner/manager only */}
          {(viewRole === "owner" || viewRole === "manager") && driverPerf && driverPerf.drivers.length > 0 && (
            <WidgetCard title="Driver Performance" icon={<Route className="h-4 w-4" />} subtitle={`Last ${driverPerf.period_days} days`}>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs font-medium uppercase tracking-wide text-gray-400">
                      <th className="pb-2">Driver</th>
                      <th className="pb-2 text-right">Routes</th>
                      <th className="pb-2 text-right">Stops</th>
                      <th className="pb-2 text-right">Miles</th>
                      <th className="pb-2 text-right">Rate</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {driverPerf.drivers.map((d) => (
                      <tr key={d.driver_id}>
                        <td className="py-2.5">
                          <div className="font-medium text-gray-700">{d.name}</div>
                          {d.license_expiry && (
                            <div className="text-xs text-gray-400">License exp: {d.license_expiry}</div>
                          )}
                        </td>
                        <td className="py-2.5 text-right tabular-nums text-gray-600">
                          {d.routes_completed}/{d.routes_total}
                        </td>
                        <td className="py-2.5 text-right tabular-nums text-gray-600">{d.total_stops}</td>
                        <td className="py-2.5 text-right tabular-nums text-gray-600">{d.total_mileage}</td>
                        <td className="py-2.5 text-right">
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                              d.completion_rate >= 90
                                ? "bg-emerald-50 text-emerald-700"
                                : d.completion_rate >= 70
                                  ? "bg-amber-50 text-amber-700"
                                  : "bg-red-50 text-red-700"
                            }`}
                          >
                            {d.completion_rate}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </WidgetCard>
          )}

          {/* Training Status */}
          {viewRole !== "employee" && training && (
            <WidgetCard title="Training Status" icon={<GraduationCap className="h-4 w-4" />}>
              <div className="grid gap-4 sm:grid-cols-3">
                <MiniStat label="Total Records" value={training.total_records} />
                <MiniStat label="Completed" value={training.completed} color="emerald" />
                <MiniStat label="Expired" value={training.expired} color={training.expired > 0 ? "red" : "gray"} />
              </div>
              {training.completion_rate < 100 && (
                <div className="mt-4">
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="text-gray-500">Overall Completion</span>
                    <span className="font-medium text-gray-700">{training.completion_rate}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-gray-100">
                    <div
                      className="h-full rounded-full bg-emerald-500 transition-all"
                      style={{ width: `${training.completion_rate}%` }}
                    />
                  </div>
                </div>
              )}
            </WidgetCard>
          )}
        </div>

        {/* Right Column — 1/3 width */}
        <div className="space-y-6">
          {/* Safety Certs Due */}
          {viewRole !== "employee" && safetyCerts && safetyCerts.items.length > 0 && (
            <WidgetCard title="Certs Due Soon" icon={<ShieldCheck className="h-4 w-4" />}>
              <div className="space-y-3">
                {safetyCerts.items.slice(0, 6).map((item) => (
                  <div key={item.id} className="flex items-start gap-3">
                    <div
                      className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
                        item.is_expired ? "bg-red-100" : "bg-amber-100"
                      }`}
                    >
                      {item.is_expired ? (
                        <XCircle className="h-3.5 w-3.5 text-red-600" />
                      ) : (
                        <Clock className="h-3.5 w-3.5 text-amber-600" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-700 truncate">{item.employee_name}</p>
                      <p className="text-xs text-gray-400">
                        {item.is_expired
                          ? "Expired"
                          : `${item.days_remaining} days remaining`}
                        {item.expiry_date && ` · ${item.expiry_date}`}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </WidgetCard>
          )}

          {/* Announcements */}
          {announcements && announcements.items.length > 0 && (
            <WidgetCard
              title="Announcements"
              icon={<Bell className="h-4 w-4" />}
              action={{ label: "View all", onClick: () => {} }}
            >
              <div className="space-y-3">
                {announcements.items.slice(0, 5).map((a) => (
                  <div
                    key={a.id}
                    className={`rounded-lg border p-3 ${
                      !a.is_read ? "border-blue-200 bg-blue-50/50" : "border-gray-100 bg-gray-50/50"
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      {!a.is_read && <div className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-blue-500" />}
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-gray-700">{a.title}</p>
                        <p className="mt-0.5 text-xs text-gray-500 line-clamp-2">{a.message}</p>
                        {a.created_at && (
                          <p className="mt-1 text-xs text-gray-400">
                            {new Date(a.created_at).toLocaleDateString()}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </WidgetCard>
          )}

          {/* Time Clock placeholder */}
          <WidgetCard title="Time Clock" icon={<Clock className="h-4 w-4" />}>
            <div className="flex flex-col items-center py-6 text-center">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-gray-100">
                <Clock className="h-6 w-6 text-gray-400" />
              </div>
              <p className="text-sm font-medium text-gray-500">Coming Soon</p>
              <p className="mt-1 text-xs text-gray-400">
                Time clock and attendance tracking will appear here.
              </p>
            </div>
          </WidgetCard>

          {/* Time Off placeholder */}
          <WidgetCard title="Time Off Requests" icon={<Calendar className="h-4 w-4" />}>
            <div className="flex flex-col items-center py-6 text-center">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-gray-100">
                <Calendar className="h-6 w-6 text-gray-400" />
              </div>
              <p className="text-sm font-medium text-gray-500">Coming Soon</p>
              <p className="mt-1 text-xs text-gray-400">
                PTO requests and approvals will appear here.
              </p>
            </div>
          </WidgetCard>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mobile Layout
// ---------------------------------------------------------------------------

function TeamDashboardMobile() {
  const navigate = useNavigate();
  const { viewRole, roster, training, safetyCerts, driverPerf, announcements, loading } = useTeamData();
  const [activeSection, setActiveSection] = useState<string>("overview");

  if (loading) {
    return (
      <div className="fixed inset-0 z-40 bg-gray-50">
        <div className="flex h-full items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
        </div>
      </div>
    );
  }

  const sections = useMemo(() => {
    const s: Array<{ key: string; label: string; icon: React.ReactNode }> = [];
    s.push({ key: "overview", label: "Overview", icon: <Users className="h-4 w-4" /> });
    if (viewRole !== "employee" && training) {
      s.push({ key: "training", label: "Training", icon: <GraduationCap className="h-4 w-4" /> });
    }
    if (viewRole !== "employee" && safetyCerts && safetyCerts.items.length > 0) {
      s.push({ key: "safety", label: "Safety", icon: <ShieldCheck className="h-4 w-4" /> });
    }
    if ((viewRole === "owner" || viewRole === "manager") && driverPerf && driverPerf.drivers.length > 0) {
      s.push({ key: "drivers", label: "Drivers", icon: <Truck className="h-4 w-4" /> });
    }
    if (announcements && announcements.items.length > 0) {
      s.push({ key: "updates", label: "Updates", icon: <Bell className="h-4 w-4" /> });
    }
    return s;
  }, [viewRole, training, safetyCerts, driverPerf, announcements]);

  return (
    <div className="fixed inset-0 z-40 bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b px-4 pt-[env(safe-area-inset-top)] pb-3">
        <div className="pt-3">
          <h1 className="text-lg font-bold text-gray-900">Team</h1>
          <p className="text-xs text-gray-500">
            {roster ? `${roster.total} team members` : "Team overview"}
          </p>
        </div>
        {/* Section Tabs */}
        <div className="mt-3 flex gap-1 overflow-x-auto pb-1 -mx-4 px-4 scrollbar-hide">
          {sections.map((s) => (
            <button
              key={s.key}
              onClick={() => setActiveSection(s.key)}
              className={`flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                activeSection === s.key
                  ? "bg-gray-900 text-white"
                  : "bg-gray-100 text-gray-600"
              }`}
            >
              {s.icon}
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-4 pb-[env(safe-area-inset-bottom)] space-y-4">
        {activeSection === "overview" && (
          <MobileOverview
            viewRole={viewRole}
            roster={roster}
            training={training}
            safetyCerts={safetyCerts}
            driverPerf={driverPerf}
            announcements={announcements}
            navigate={navigate}
          />
        )}
        {activeSection === "training" && training && (
          <MobileTraining training={training} roster={roster} />
        )}
        {activeSection === "safety" && safetyCerts && (
          <MobileSafetyCerts safetyCerts={safetyCerts} />
        )}
        {activeSection === "drivers" && driverPerf && (
          <MobileDriverPerf driverPerf={driverPerf} />
        )}
        {activeSection === "updates" && announcements && (
          <MobileAnnouncements announcements={announcements} />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mobile Sub-sections
// ---------------------------------------------------------------------------

function MobileOverview({
  viewRole,
  roster,
  training,
  safetyCerts,
  driverPerf,
  announcements,
  navigate,
}: {
  viewRole: ViewRole;
  roster: RosterData | null;
  training: TrainingData | null;
  safetyCerts: SafetyCertsData | null;
  driverPerf: DriverPerfData | null;
  announcements: AnnouncementsData | null;
  navigate: (path: string) => void;
}) {
  return (
    <>
      {/* Quick Stats */}
      {viewRole !== "employee" && roster && (
        <div className="grid grid-cols-2 gap-3">
          <MobileStatCard
            icon={<Users className="h-4 w-4 text-blue-600" />}
            label="Team Size"
            value={roster.total}
          />
          <MobileStatCard
            icon={<GraduationCap className="h-4 w-4 text-emerald-600" />}
            label="Training"
            value={training ? `${training.completion_rate}%` : "--"}
          />
          <MobileStatCard
            icon={<ShieldCheck className="h-4 w-4 text-amber-600" />}
            label="Certs Due"
            value={safetyCerts?.total ?? 0}
            alert={(safetyCerts?.expired_count ?? 0) > 0}
          />
          <MobileStatCard
            icon={<Truck className="h-4 w-4 text-purple-600" />}
            label="Drivers"
            value={driverPerf?.total_drivers ?? 0}
          />
        </div>
      )}

      {/* Department Breakdown */}
      {viewRole !== "employee" && roster && (
        <div className="rounded-xl bg-white border p-4">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">By Department</h3>
          <div className="space-y-2.5">
            {Object.entries(roster.by_department).map(([dept, count]) => (
              <div key={dept} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-gray-400" />
                  <span className="text-sm text-gray-700">{dept}</span>
                </div>
                <span className="text-sm font-medium tabular-nums text-gray-500">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Team List Preview */}
      {viewRole !== "employee" && roster && (
        <div className="rounded-xl bg-white border p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-900">Team Members</h3>
            <button
              onClick={() => navigate("/admin/users")}
              className="flex items-center gap-1 text-xs font-medium text-blue-600"
            >
              View all
              <ChevronRight className="h-3 w-3" />
            </button>
          </div>
          <div className="space-y-3">
            {roster.employees.slice(0, 5).map((e) => (
              <div key={e.id} className="flex items-center gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-bold text-gray-500">
                  {e.first_name[0]}
                  {e.last_name[0]}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-gray-800 truncate">
                    {e.first_name} {e.last_name}
                  </p>
                  <p className="text-xs text-gray-400 truncate">
                    {e.position || e.track}
                    {e.department ? ` · ${e.department}` : ""}
                  </p>
                </div>
                {e.is_driver && (
                  <Truck className="h-4 w-4 shrink-0 text-purple-400" />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Announcements preview */}
      {announcements && announcements.unread > 0 && (
        <div className="rounded-xl bg-blue-50 border border-blue-200 p-4">
          <div className="flex items-center gap-2">
            <Bell className="h-4 w-4 text-blue-600" />
            <span className="text-sm font-medium text-blue-800">
              {announcements.unread} unread notification{announcements.unread !== 1 ? "s" : ""}
            </span>
          </div>
        </div>
      )}
    </>
  );
}

function MobileTraining({ training, roster }: { training: TrainingData; roster: RosterData | null }) {
  return (
    <>
      {/* Progress */}
      <div className="rounded-xl bg-white border p-4">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Completion Rate</h3>
        <div className="flex items-end gap-3">
          <span className="text-3xl font-bold text-gray-900">{training.completion_rate}%</span>
          <span className="mb-1 text-xs text-gray-400">
            {training.completed} of {training.total_records} records completed
          </span>
        </div>
        <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-gray-100">
          <div
            className="h-full rounded-full bg-emerald-500 transition-all"
            style={{ width: `${training.completion_rate}%` }}
          />
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-3">
        <MobileStatCard icon={<CheckCircle2 className="h-4 w-4 text-emerald-600" />} label="Completed" value={training.completed} />
        <MobileStatCard
          icon={<AlertTriangle className="h-4 w-4 text-amber-600" />}
          label="Expiring"
          value={training.expiring_soon}
        />
        <MobileStatCard
          icon={<XCircle className="h-4 w-4 text-red-600" />}
          label="Expired"
          value={training.expired}
          alert={training.expired > 0}
        />
      </div>

      {/* Expiring Items */}
      {training.expiring_items.length > 0 && (
        <div className="rounded-xl bg-white border p-4">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">Expiring Soon</h3>
          <div className="space-y-3">
            {training.expiring_items.map((item, idx) => {
              const emp = roster?.employees.find((e) => e.id === item.employee_id);
              return (
                <div key={idx} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-amber-500" />
                    <span className="text-sm text-gray-700">
                      {emp ? `${emp.first_name} ${emp.last_name}` : "Employee"}
                    </span>
                  </div>
                  <span className="text-xs text-gray-400">{item.expiry_date}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}

function MobileSafetyCerts({ safetyCerts }: { safetyCerts: SafetyCertsData }) {
  return (
    <>
      <div className="grid grid-cols-2 gap-3">
        <MobileStatCard
          icon={<AlertTriangle className="h-4 w-4 text-amber-600" />}
          label="Due Soon"
          value={safetyCerts.total - safetyCerts.expired_count}
        />
        <MobileStatCard
          icon={<XCircle className="h-4 w-4 text-red-600" />}
          label="Expired"
          value={safetyCerts.expired_count}
          alert={safetyCerts.expired_count > 0}
        />
      </div>
      <div className="rounded-xl bg-white border p-4">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">Certifications</h3>
        <div className="space-y-3">
          {safetyCerts.items.map((item) => (
            <div key={item.id} className="flex items-start gap-3">
              <div
                className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${
                  item.is_expired ? "bg-red-100" : "bg-amber-100"
                }`}
              >
                {item.is_expired ? (
                  <XCircle className="h-4 w-4 text-red-600" />
                ) : (
                  <Clock className="h-4 w-4 text-amber-600" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-700">{item.employee_name}</p>
                <p className="text-xs text-gray-400">
                  {item.is_expired ? "Expired" : `${item.days_remaining} days left`}
                  {item.expiry_date ? ` · ${item.expiry_date}` : ""}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function MobileDriverPerf({ driverPerf }: { driverPerf: DriverPerfData }) {
  return (
    <>
      <div className="rounded-xl bg-white border p-4">
        <h3 className="text-sm font-semibold text-gray-900 mb-1">
          Driver Performance
        </h3>
        <p className="text-xs text-gray-400 mb-4">Last {driverPerf.period_days} days</p>
        <div className="space-y-4">
          {driverPerf.drivers.map((d) => (
            <div key={d.driver_id} className="border-b last:border-0 pb-3 last:pb-0">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-gray-800">{d.name}</span>
                <span
                  className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                    d.completion_rate >= 90
                      ? "bg-emerald-50 text-emerald-700"
                      : d.completion_rate >= 70
                        ? "bg-amber-50 text-amber-700"
                        : "bg-red-50 text-red-700"
                  }`}
                >
                  {d.completion_rate}%
                </span>
              </div>
              <div className="flex gap-4 text-xs text-gray-400">
                <span>{d.routes_completed}/{d.routes_total} routes</span>
                <span>{d.total_stops} stops</span>
                <span>{d.total_mileage} mi</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function MobileAnnouncements({ announcements }: { announcements: AnnouncementsData }) {
  return (
    <>
      <div className="rounded-xl bg-white border p-4">
        <h3 className="text-sm font-semibold text-gray-900 mb-3">
          Notifications
          {announcements.unread > 0 && (
            <span className="ml-2 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-blue-100 px-1.5 text-xs font-medium text-blue-700">
              {announcements.unread}
            </span>
          )}
        </h3>
        <div className="space-y-3">
          {announcements.items.map((a) => (
            <div
              key={a.id}
              className={`rounded-lg border p-3 ${
                !a.is_read ? "border-blue-200 bg-blue-50/50" : "border-gray-100"
              }`}
            >
              <div className="flex items-start gap-2">
                {!a.is_read && (
                  <div className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-blue-500" />
                )}
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-gray-700">{a.title}</p>
                  <p className="mt-0.5 text-xs text-gray-500 line-clamp-2">{a.message}</p>
                  {a.created_at && (
                    <p className="mt-1 text-xs text-gray-400">
                      {new Date(a.created_at).toLocaleDateString()}
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Shared Widgets
// ---------------------------------------------------------------------------

function StatCard({
  icon,
  label,
  value,
  sub,
  alert,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  sub?: string;
  alert?: boolean;
}) {
  return (
    <div className={`rounded-lg border bg-white p-4 ${alert ? "border-red-200" : ""}`}>
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</span>
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      {sub && <p className="mt-1 text-xs text-gray-400">{sub}</p>}
    </div>
  );
}

function MobileStatCard({
  icon,
  label,
  value,
  alert,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  alert?: boolean;
}) {
  return (
    <div className={`rounded-xl bg-white border p-3 ${alert ? "border-red-200" : ""}`}>
      <div className="flex items-center gap-1.5 mb-1">
        {icon}
        <span className="text-xs text-gray-500">{label}</span>
      </div>
      <p className="text-xl font-bold text-gray-900">{value}</p>
    </div>
  );
}

function WidgetCard({
  title,
  icon,
  subtitle,
  action,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  subtitle?: string;
  action?: { label: string; onClick: () => void };
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border bg-white p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon && <span className="text-gray-400">{icon}</span>}
          <div>
            <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
            {subtitle && <p className="text-xs text-gray-400">{subtitle}</p>}
          </div>
        </div>
        {action && (
          <button
            onClick={action.onClick}
            className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-700"
          >
            {action.label}
            <ChevronRight className="h-3 w-3" />
          </button>
        )}
      </div>
      {children}
    </div>
  );
}

function MiniStat({
  label,
  value,
  color = "gray",
}: {
  label: string;
  value: number | string;
  color?: "gray" | "emerald" | "red" | "amber";
}) {
  const colors = {
    gray: "text-gray-900",
    emerald: "text-emerald-600",
    red: "text-red-600",
    amber: "text-amber-600",
  };
  return (
    <div className="rounded-lg bg-gray-50 p-3 text-center">
      <p className={`text-xl font-bold ${colors[color]}`}>{value}</p>
      <p className="text-xs text-gray-500">{label}</p>
    </div>
  );
}
