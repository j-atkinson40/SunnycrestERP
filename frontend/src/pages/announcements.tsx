import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import apiClient from "@/lib/api-client";
import { Trash2, Megaphone, ShieldAlert } from "lucide-react";

interface Permissions {
  can_create: boolean;
  can_mark_compliance?: boolean;
}

interface Announcement {
  id: string;
  title: string;
  body: string | null;
  priority: "info" | "warning" | "critical";
  content_type: string; // "announcement" | "note" | "safety_notice"
  target_type: "everyone" | "functional_area" | "employee_type" | "specific_employees";
  target_value: string | null;
  pin_to_top: boolean;
  expires_at: string | null;
  is_active: boolean;
  created_at: string;
  created_by_name: string | null;
  // Safety notice fields
  safety_category: string | null;
  requires_acknowledgment: boolean;
  is_compliance_relevant: boolean;
  document_url: string | null;
  acknowledgment_deadline: string | null;
}

const FUNCTIONAL_AREAS = [
  { value: "full_admin", label: "Full Admin" },
  { value: "funeral_scheduling", label: "Funeral Scheduling" },
  { value: "invoicing_ar", label: "Invoicing / AR" },
  { value: "production_log", label: "Production Log" },
  { value: "customer_management", label: "Customer Management" },
  { value: "safety_compliance", label: "Safety & Compliance" },
];

const EMPLOYEE_TYPES = [
  { value: "office_management", label: "Office / Management" },
  { value: "production_delivery", label: "Production / Delivery" },
];

const SAFETY_CATEGORIES = [
  { value: "procedure", label: "New Procedure" },
  { value: "equipment_alert", label: "Equipment Alert" },
  { value: "osha_reminder", label: "OSHA Reminder" },
  { value: "incident_followup", label: "Incident Follow-up" },
  { value: "training_assignment", label: "Training Assignment" },
  { value: "toolbox_talk", label: "Toolbox Talk" },
];

function priorityBadge(priority: string) {
  switch (priority) {
    case "critical":
      return (
        <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
          Critical
        </span>
      );
    case "warning":
      return (
        <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
          Warning
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
          Info
        </span>
      );
  }
}

function contentTypeBadge(contentType: string) {
  switch (contentType) {
    case "safety_notice":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-700">
          <ShieldAlert className="h-3 w-3" />
          Safety
        </span>
      );
    case "note":
      return (
        <span className="inline-flex items-center rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700">
          Note
        </span>
      );
    default:
      return null;
  }
}

function targetLabel(a: Announcement): string {
  switch (a.target_type) {
    case "everyone":
      return "Everyone";
    case "functional_area":
      return `Area: ${FUNCTIONAL_AREAS.find((f) => f.value === a.target_value)?.label ?? a.target_value}`;
    case "employee_type":
      return `Type: ${EMPLOYEE_TYPES.find((e) => e.value === a.target_value)?.label ?? a.target_value}`;
    case "specific_employees":
      return "Specific employees";
    default:
      return a.target_type;
  }
}

export default function AnnouncementsPage() {
  const [permissions, setPermissions] = useState<Permissions | null>(null);
  const [permLoading, setPermLoading] = useState(true);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Form state
  const [contentType, setContentType] = useState<"announcement" | "note" | "safety_notice">("announcement");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [priority, setPriority] = useState<"info" | "warning" | "critical">("info");
  const [targetType, setTargetType] = useState<"everyone" | "functional_area" | "employee_type" | "specific_employees">("everyone");
  const [targetValue, setTargetValue] = useState("");
  const [pinToTop, setPinToTop] = useState(false);
  const [expiresAt, setExpiresAt] = useState("");

  // Safety notice form state
  const [safetyCategory, setSafetyCategory] = useState("");
  const [requiresAcknowledgment, setRequiresAcknowledgment] = useState(false);
  const [acknowledgmentDeadline, setAcknowledgmentDeadline] = useState("");
  const [isComplianceRelevant, setIsComplianceRelevant] = useState(false);
  const [documentUrl, setDocumentUrl] = useState("");

  const bodyMaxChars = contentType === "safety_notice" ? 1000 : 500;

  const fetchPermissions = useCallback(async () => {
    try {
      const res = await apiClient.get<Permissions>("/announcements/permissions");
      setPermissions(res.data);
    } catch {
      setPermissions({ can_create: false });
    } finally {
      setPermLoading(false);
    }
  }, []);

  const fetchAnnouncements = useCallback(async () => {
    try {
      const res = await apiClient.get<Announcement[]>("/announcements/");
      setAnnouncements(res.data);
    } catch {
      // fail silently
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPermissions();
    fetchAnnouncements();
  }, [fetchPermissions, fetchAnnouncements]);

  const resetForm = () => {
    setContentType("announcement");
    setTitle("");
    setBody("");
    setPriority("info");
    setTargetType("everyone");
    setTargetValue("");
    setPinToTop(false);
    setExpiresAt("");
    setSafetyCategory("");
    setRequiresAcknowledgment(false);
    setAcknowledgmentDeadline("");
    setIsComplianceRelevant(false);
    setDocumentUrl("");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      toast.error("Title is required");
      return;
    }
    setSubmitting(true);
    try {
      await apiClient.post("/announcements/", {
        title: title.trim(),
        body: body.trim() || null,
        priority,
        content_type: contentType,
        target_type: targetType,
        target_value: targetType === "everyone" ? null : targetValue || null,
        pin_to_top: pinToTop,
        expires_at: expiresAt || null,
        // Safety notice fields
        ...(contentType === "safety_notice" && {
          safety_category: safetyCategory || null,
          requires_acknowledgment: requiresAcknowledgment,
          acknowledgment_deadline: requiresAcknowledgment && acknowledgmentDeadline ? acknowledgmentDeadline : null,
          is_compliance_relevant: isComplianceRelevant,
          document_url: documentUrl.trim() || null,
        }),
      });
      toast.success(
        contentType === "safety_notice"
          ? "Safety notice posted"
          : "Announcement posted"
      );
      resetForm();
      fetchAnnouncements();
    } catch {
      toast.error("Failed to post announcement");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await apiClient.delete(`/announcements/${id}`);
      setAnnouncements((prev) => prev.filter((a) => a.id !== id));
      toast.success("Announcement deleted");
    } catch {
      toast.error("Failed to delete announcement");
    }
  };

  if (permLoading) {
    return (
      <div className="max-w-3xl mx-auto py-8 px-4">
        <div className="h-8 w-48 bg-gray-200 rounded animate-pulse mb-6" />
        <div className="h-64 bg-gray-200 rounded animate-pulse" />
      </div>
    );
  }

  if (!permissions?.can_create) {
    return (
      <div className="max-w-3xl mx-auto py-8 px-4">
        <Card>
          <CardContent className="p-8 text-center">
            <Megaphone className="h-10 w-10 text-gray-300 mx-auto mb-3" />
            <h2 className="text-lg font-semibold text-gray-900 mb-1">No Permission</h2>
            <p className="text-sm text-gray-500">
              You do not have permission to manage announcements.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const isExpired = (a: Announcement) =>
    a.expires_at && new Date(a.expires_at) < new Date();

  return (
    <div className="max-w-3xl mx-auto py-8 px-4 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Announcements</h1>
        <p className="text-sm text-gray-500 mt-1">
          Post announcements visible to your team on their dashboard.
        </p>
      </div>

      {/* Create Form */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Post New Announcement</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Content Type Selector */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Type
              </label>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-1.5 text-sm text-gray-700 cursor-pointer">
                  <input
                    type="radio"
                    name="content_type"
                    value="announcement"
                    checked={contentType === "announcement"}
                    onChange={() => setContentType("announcement")}
                    className="h-4 w-4 border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  Company announcement
                </label>
                <label className="flex items-center gap-1.5 text-sm text-gray-700 cursor-pointer">
                  <input
                    type="radio"
                    name="content_type"
                    value="note"
                    checked={contentType === "note"}
                    onChange={() => setContentType("note")}
                    className="h-4 w-4 border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  Note for a specific person
                </label>
                <label className="flex items-center gap-1.5 text-sm text-gray-700 cursor-pointer">
                  <input
                    type="radio"
                    name="content_type"
                    value="safety_notice"
                    checked={contentType === "safety_notice"}
                    onChange={() => setContentType("safety_notice")}
                    className="h-4 w-4 border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  Safety notice
                </label>
              </div>
            </div>

            {/* Title */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Title <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder={
                  contentType === "safety_notice"
                    ? "Safety notice title"
                    : "Announcement title"
                }
                required
              />
            </div>

            {/* Body */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Body
              </label>
              <textarea
                value={body}
                onChange={(e) => {
                  if (e.target.value.length <= bodyMaxChars) {
                    setBody(e.target.value);
                  }
                }}
                rows={contentType === "safety_notice" ? 5 : 3}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Optional details..."
              />
              <p className="text-xs text-gray-400 mt-0.5 text-right">
                {body.length}/{bodyMaxChars}
              </p>
            </div>

            {/* Safety notice fields */}
            {contentType === "safety_notice" && (
              <div className="space-y-4 rounded-md border border-orange-200 bg-orange-50/50 p-4">
                <h4 className="text-sm font-semibold text-orange-800 flex items-center gap-1.5">
                  <ShieldAlert className="h-4 w-4" />
                  Safety Notice Options
                </h4>

                {/* Safety category */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Safety Category
                  </label>
                  <select
                    value={safetyCategory}
                    onChange={(e) => setSafetyCategory(e.target.value)}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="">Select category...</option>
                    {SAFETY_CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Requires acknowledgment */}
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="requires-ack"
                    checked={requiresAcknowledgment}
                    onChange={(e) => setRequiresAcknowledgment(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <label htmlFor="requires-ack" className="text-sm text-gray-700">
                    Requires acknowledgment from all recipients
                  </label>
                </div>

                {/* Acknowledgment deadline */}
                {requiresAcknowledgment && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Acknowledgment Deadline
                    </label>
                    <input
                      type="date"
                      value={acknowledgmentDeadline}
                      onChange={(e) => setAcknowledgmentDeadline(e.target.value)}
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                )}

                {/* Is compliance relevant */}
                {permissions?.can_mark_compliance && (
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="compliance-relevant"
                      checked={isComplianceRelevant}
                      onChange={(e) => setIsComplianceRelevant(e.target.checked)}
                      className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <label htmlFor="compliance-relevant" className="text-sm text-gray-700">
                      Compliance-relevant (for audit trail)
                    </label>
                  </div>
                )}

                {/* Document URL */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Document URL
                  </label>
                  <input
                    type="url"
                    value={documentUrl}
                    onChange={(e) => setDocumentUrl(e.target.value)}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    placeholder="https://..."
                  />
                  <p className="text-xs text-gray-400 mt-0.5">
                    Link to SDS, procedure document, or training material
                  </p>
                </div>
              </div>
            )}

            {/* Priority + Target row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Priority
                </label>
                <select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value as "info" | "warning" | "critical")}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="info">Info</option>
                  <option value="warning">Warning</option>
                  <option value="critical">Critical</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Target
                </label>
                <select
                  value={targetType}
                  onChange={(e) => {
                    setTargetType(e.target.value as typeof targetType);
                    setTargetValue("");
                  }}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="everyone">Everyone</option>
                  <option value="functional_area">Functional Area</option>
                  <option value="employee_type">Employee Type</option>
                  <option value="specific_employees">Specific Employees</option>
                </select>
              </div>
            </div>

            {/* Conditional target value selects */}
            {targetType === "functional_area" && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Functional Area
                </label>
                <select
                  value={targetValue}
                  onChange={(e) => setTargetValue(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">Select area...</option>
                  {FUNCTIONAL_AREAS.map((a) => (
                    <option key={a.value} value={a.value}>
                      {a.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {targetType === "employee_type" && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Employee Type
                </label>
                <select
                  value={targetValue}
                  onChange={(e) => setTargetValue(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">Select type...</option>
                  {EMPLOYEE_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Pin + Expires row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-end">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Expires At
                </label>
                <input
                  type="date"
                  value={expiresAt}
                  onChange={(e) => setExpiresAt(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div className="flex items-center gap-2 pb-1">
                <input
                  type="checkbox"
                  id="pin-to-top"
                  checked={pinToTop}
                  onChange={(e) => setPinToTop(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <label htmlFor="pin-to-top" className="text-sm text-gray-700">
                  Pin to top
                </label>
              </div>
            </div>

            <div className="pt-2">
              <Button type="submit" disabled={submitting}>
                {submitting
                  ? "Posting..."
                  : contentType === "safety_notice"
                    ? "Post Safety Notice"
                    : "Post Announcement"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Announcements List */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Recent Announcements</CardTitle>
        </CardHeader>
        <CardContent>
          {listLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 bg-gray-100 rounded animate-pulse" />
              ))}
            </div>
          ) : announcements.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-6">
              No announcements yet.
            </p>
          ) : (
            <div className="divide-y divide-gray-100">
              {announcements.map((a) => (
                <div key={a.id} className="py-3 flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-gray-900">
                        {a.title}
                      </span>
                      {contentTypeBadge(a.content_type)}
                      {priorityBadge(a.priority)}
                      {isExpired(a) ? (
                        <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">
                          Expired
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                          Active
                        </span>
                      )}
                      {a.content_type === "safety_notice" && a.requires_acknowledgment && (
                        <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                          Ack required
                        </span>
                      )}
                      {a.content_type === "safety_notice" && a.is_compliance_relevant && (
                        <span className="inline-flex items-center rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700">
                          Compliance
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      {targetLabel(a)}
                      {a.content_type === "safety_notice" && a.safety_category && (
                        <>
                          {" "}&middot;{" "}
                          {SAFETY_CATEGORIES.find((c) => c.value === a.safety_category)?.label ?? a.safety_category}
                        </>
                      )}
                      {a.created_by_name && <> &middot; by {a.created_by_name}</>}
                      {a.created_at && (
                        <>
                          {" "}
                          &middot;{" "}
                          {new Date(a.created_at).toLocaleDateString()}
                        </>
                      )}
                    </p>
                  </div>
                  {permissions?.can_create && (
                    <button
                      onClick={() => handleDelete(a.id)}
                      className="p-1.5 rounded hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors shrink-0"
                      aria-label="Delete announcement"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
