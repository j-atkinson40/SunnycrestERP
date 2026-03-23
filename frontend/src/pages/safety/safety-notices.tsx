import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ShieldAlert, Check, Clock, AlertTriangle, FileText, Trash2, Send, Download, X } from "lucide-react";
import apiClient from "@/lib/api-client";

// ── Types ──

interface SafetyNotice {
  id: string;
  title: string;
  body: string | null;
  priority: "info" | "warning" | "critical";
  safety_category: string | null;
  requires_acknowledgment: boolean;
  is_compliance_relevant: boolean;
  document_url: string | null;
  document_filename: string | null;
  acknowledgment_deadline: string | null;
  is_active: boolean;
  created_at: string;
  created_by_name: string | null;
  acknowledged_count: number;
  total_recipients: number;
}

interface AcknowledgmentEntry {
  employee_id: string;
  first_name: string;
  last_name: string;
  status: "acknowledged" | "pending";
  acknowledged_at: string | null;
  note: string | null;
}

interface NoticeDetail {
  notice_id: string;
  title: string;
  body: string | null;
  priority: "info" | "warning" | "critical";
  safety_category: string | null;
  requires_acknowledgment: boolean;
  is_compliance_relevant: boolean;
  document_url: string | null;
  document_filename: string | null;
  acknowledgment_deadline: string | null;
  is_active: boolean;
  created_at: string;
  created_by_name: string | null;
  employees: AcknowledgmentEntry[];
}

// ── Constants ──

const SAFETY_CATEGORIES = [
  { value: "procedure", label: "New Procedure" },
  { value: "equipment_alert", label: "Equipment Alert" },
  { value: "osha_reminder", label: "OSHA Reminder" },
  { value: "incident_followup", label: "Incident Follow-up" },
  { value: "training_assignment", label: "Training Assignment" },
  { value: "toolbox_talk", label: "Toolbox Talk" },
];

const CATEGORY_LABELS: Record<string, string> = {
  procedure: "New Procedure",
  equipment_alert: "Equipment Alert",
  osha_reminder: "OSHA Reminder",
  incident_followup: "Incident Follow-up",
  training_assignment: "Training Assignment",
  toolbox_talk: "Toolbox Talk",
};

// ── Helpers ──

function deadlineStatus(deadline: string | null): "ok" | "approaching" | "past" | null {
  if (!deadline) return null;
  const now = Date.now();
  const dl = new Date(deadline).getTime();
  if (dl < now) return "past";
  if (dl - now < 24 * 60 * 60 * 1000) return "approaching";
  return "ok";
}

function categoryBadge(category: string | null) {
  const label = category ? CATEGORY_LABELS[category] || category : "General";
  return (
    <span className="inline-flex items-center rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-700">
      {label}
    </span>
  );
}

function exportAcknowledgmentLog(detail: NoticeDetail) {
  const rows = [["Notice Title", "Employee Name", "Status", "Acknowledged At", "Note"]];
  for (const emp of detail.employees) {
    rows.push([
      detail.title,
      `${emp.first_name} ${emp.last_name}`,
      emp.status === "acknowledged" ? "Acknowledged" : "Not acknowledged",
      emp.acknowledged_at || "\u2014",
      emp.note || "",
    ]);
  }
  const csv = rows.map(r => r.map(c => `"${c}"`).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `acknowledgment-log-${detail.notice_id}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Component ──

export default function SafetyNoticesPage() {
  const [notices, setNotices] = useState<SafetyNotice[]>([]);
  const [loading, setLoading] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedNoticeId, setSelectedNoticeId] = useState<string | null>(null);
  const [detail, setDetail] = useState<NoticeDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [sendingReminder, setSendingReminder] = useState(false);

  const fetchNotices = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (categoryFilter !== "all") params.set("category", categoryFilter);
      if (statusFilter !== "all") params.set("status", statusFilter);
      const res = await apiClient.get<SafetyNotice[]>(`/safety/notices?${params.toString()}`);
      setNotices(res.data);
    } catch {
      toast.error("Failed to load safety notices");
    } finally {
      setLoading(false);
    }
  }, [categoryFilter, statusFilter]);

  useEffect(() => {
    setLoading(true);
    fetchNotices();
  }, [fetchNotices]);

  const fetchDetail = useCallback(async (noticeId: string) => {
    setDetailLoading(true);
    try {
      const res = await apiClient.get<NoticeDetail>(`/safety/notices/${noticeId}`);
      setDetail(res.data);
    } catch {
      toast.error("Failed to load notice details");
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const handleViewDetails = (noticeId: string) => {
    setSelectedNoticeId(noticeId);
    fetchDetail(noticeId);
  };

  const handleCloseDetail = () => {
    setSelectedNoticeId(null);
    setDetail(null);
  };

  const handleSendReminder = async (noticeId: string) => {
    setSendingReminder(true);
    try {
      await apiClient.post(`/safety/notices/${noticeId}/remind`);
      toast.success("Reminder sent to pending employees");
    } catch {
      toast.error("Failed to send reminder");
    } finally {
      setSendingReminder(false);
    }
  };

  const handleDeactivate = async (noticeId: string) => {
    try {
      await apiClient.patch(`/safety/notices/${noticeId}`, { is_active: false });
      toast.success("Notice deactivated");
      fetchNotices();
      if (selectedNoticeId === noticeId) {
        handleCloseDetail();
      }
    } catch {
      toast.error("Failed to deactivate notice");
    }
  };

  const filteredNotices = notices;

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <ShieldAlert className="h-6 w-6 text-orange-600" />
            Safety Notices
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage safety notices, track acknowledgments, and maintain compliance records.
          </p>
        </div>
        <Link to="/announcements">
          <Button>+ New Safety Notice</Button>
        </Link>
      </div>

      {/* Filter Bar */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-4 flex-wrap">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                Category
              </label>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="all">All Categories</option>
                {SAFETY_CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                Status
              </label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="all">All</option>
                <option value="active">Active</option>
                <option value="requires_acknowledgment">Requires Acknowledgment</option>
                <option value="compliance_relevant">Compliance-Relevant</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Detail view */}
      {selectedNoticeId && (
        <Card className="border-orange-200">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Notice Details</CardTitle>
            <button
              onClick={handleCloseDetail}
              className="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
              aria-label="Close details"
            >
              <X className="h-4 w-4" />
            </button>
          </CardHeader>
          <CardContent>
            {detailLoading ? (
              <div className="space-y-3">
                <div className="h-5 w-64 bg-gray-200 rounded animate-pulse" />
                <div className="h-4 w-full bg-gray-200 rounded animate-pulse" />
                <div className="h-4 w-3/4 bg-gray-200 rounded animate-pulse" />
              </div>
            ) : detail ? (
              <div className="space-y-5">
                {/* Notice content */}
                <div>
                  <div className="flex items-center gap-2 flex-wrap mb-2">
                    <h3 className="text-lg font-semibold text-gray-900">{detail.title}</h3>
                    {categoryBadge(detail.safety_category)}
                    {detail.is_compliance_relevant && (
                      <span className="inline-flex items-center rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700">
                        Compliance
                      </span>
                    )}
                  </div>
                  {detail.body && (
                    <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                      {detail.body}
                    </p>
                  )}
                  {detail.document_url && (
                    <a
                      href={detail.document_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800 mt-2"
                    >
                      <FileText className="h-4 w-4" />
                      {detail.document_filename || "View attached document"}
                    </a>
                  )}
                  <p className="text-xs text-gray-500 mt-2">
                    Posted by {detail.created_by_name || "Unknown"} on{" "}
                    {new Date(detail.created_at).toLocaleDateString()}
                    {detail.acknowledgment_deadline && (
                      <> &middot; Deadline: {new Date(detail.acknowledgment_deadline).toLocaleDateString()}</>
                    )}
                  </p>
                </div>

                {/* Acknowledgment table */}
                {detail.requires_acknowledgment && detail.employees.length > 0 && (
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="text-sm font-semibold text-gray-900">
                        Acknowledgments ({detail.employees.filter(e => e.status === "acknowledged").length} of {detail.employees.length})
                      </h4>
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 text-xs gap-1.5"
                          onClick={() => handleSendReminder(detail.notice_id)}
                          disabled={sendingReminder}
                        >
                          <Send className="h-3 w-3" />
                          {sendingReminder ? "Sending..." : "Send Reminder"}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 text-xs gap-1.5"
                          onClick={() => exportAcknowledgmentLog(detail)}
                        >
                          <Download className="h-3 w-3" />
                          Export CSV
                        </Button>
                      </div>
                    </div>
                    <div className="border border-gray-200 rounded-md overflow-hidden">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-gray-50">
                            <th className="text-left px-3 py-2 font-medium text-gray-600">Employee</th>
                            <th className="text-left px-3 py-2 font-medium text-gray-600">Status</th>
                            <th className="text-left px-3 py-2 font-medium text-gray-600">Date</th>
                            <th className="text-left px-3 py-2 font-medium text-gray-600">Note</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {detail.employees.map((emp) => (
                            <tr key={emp.employee_id}>
                              <td className="px-3 py-2 text-gray-900">
                                {emp.first_name} {emp.last_name}
                              </td>
                              <td className="px-3 py-2">
                                {emp.status === "acknowledged" ? (
                                  <span className="inline-flex items-center gap-1 text-green-700">
                                    <Check className="h-3.5 w-3.5" />
                                    Acknowledged
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1 text-amber-600">
                                    <Clock className="h-3.5 w-3.5" />
                                    Pending
                                  </span>
                                )}
                              </td>
                              <td className="px-3 py-2 text-gray-500">
                                {emp.acknowledged_at
                                  ? new Date(emp.acknowledged_at).toLocaleDateString()
                                  : "\u2014"}
                              </td>
                              <td className="px-3 py-2 text-gray-500 max-w-[200px] truncate">
                                {emp.note || "\u2014"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}

      {/* Notice list */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {loading ? "Loading..." : `${filteredNotices.length} Notice${filteredNotices.length === 1 ? "" : "s"}`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-20 bg-gray-100 rounded animate-pulse" />
              ))}
            </div>
          ) : filteredNotices.length === 0 ? (
            <div className="text-center py-8">
              <ShieldAlert className="h-10 w-10 text-gray-300 mx-auto mb-3" />
              <p className="text-sm text-gray-500">No safety notices found.</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {filteredNotices.map((notice) => {
                const dlStatus = deadlineStatus(notice.acknowledgment_deadline);
                const ackPercent = notice.total_recipients > 0
                  ? Math.round((notice.acknowledged_count / notice.total_recipients) * 100)
                  : 0;

                return (
                  <div key={notice.id} className="py-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <ShieldAlert className="h-4 w-4 text-orange-600 shrink-0" />
                          <span className="text-sm font-semibold text-gray-900">
                            {notice.title}
                          </span>
                          {categoryBadge(notice.safety_category)}
                          {notice.is_compliance_relevant && (
                            <span className="inline-flex items-center rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700">
                              Compliance
                            </span>
                          )}
                          {!notice.is_active && (
                            <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">
                              Inactive
                            </span>
                          )}
                        </div>

                        {notice.body && (
                          <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                            {notice.body}
                          </p>
                        )}

                        <div className="flex items-center gap-3 mt-2 flex-wrap">
                          <p className="text-xs text-gray-500">
                            {notice.created_by_name && <>by {notice.created_by_name} &middot; </>}
                            {new Date(notice.created_at).toLocaleDateString()}
                          </p>

                          {notice.requires_acknowledgment && (
                            <span className="text-xs text-gray-600">
                              {notice.acknowledged_count} of {notice.total_recipients} acknowledged ({ackPercent}%)
                            </span>
                          )}

                          {notice.acknowledgment_deadline && (
                            <span
                              className={`text-xs font-medium flex items-center gap-1 ${
                                dlStatus === "past"
                                  ? "text-red-600"
                                  : dlStatus === "approaching"
                                    ? "text-amber-600"
                                    : "text-gray-500"
                              }`}
                            >
                              {dlStatus === "past" ? (
                                <AlertTriangle className="h-3 w-3" />
                              ) : (
                                <Clock className="h-3 w-3" />
                              )}
                              {dlStatus === "past"
                                ? "Overdue"
                                : `Due ${new Date(notice.acknowledgment_deadline).toLocaleDateString()}`}
                            </span>
                          )}
                        </div>

                        {/* Acknowledgment progress bar */}
                        {notice.requires_acknowledgment && notice.total_recipients > 0 && (
                          <div className="mt-2 w-48">
                            <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all ${
                                  ackPercent === 100
                                    ? "bg-green-500"
                                    : ackPercent >= 50
                                      ? "bg-amber-500"
                                      : "bg-red-500"
                                }`}
                                style={{ width: `${ackPercent}%` }}
                              />
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1 shrink-0">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 text-xs"
                          onClick={() => handleViewDetails(notice.id)}
                        >
                          View details
                        </Button>
                        {notice.requires_acknowledgment && notice.is_active && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 text-xs gap-1"
                            onClick={() => handleSendReminder(notice.id)}
                            disabled={sendingReminder}
                          >
                            <Send className="h-3 w-3" />
                            Remind
                          </Button>
                        )}
                        {notice.is_active && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 text-xs text-red-600 hover:text-red-700 hover:bg-red-50 gap-1"
                            onClick={() => handleDeactivate(notice.id)}
                          >
                            <Trash2 className="h-3 w-3" />
                            Deactivate
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
