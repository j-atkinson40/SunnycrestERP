import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { X, RefreshCw, Check, ChevronRight, Pin, AlertTriangle, FileText, Eye, CreditCard, Send, CheckCircle, BookOpen, Clock, Truck } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/auth-context";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RecordPaymentDialog } from "@/components/record-payment-dialog";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";

// ── Types ──

interface BriefingItem {
  number: number;
  text: string;
  priority: "critical" | "warning" | "info";
  related_entity_type?: string;
  related_entity_hint?: string;
}

interface BriefingResponse {
  content: string | null;
  items: BriefingItem[];
  tier: "primary_area" | "executive" | "role_based";
  primary_area: string | null;
  was_cached: boolean;
  generated_at: string;
  briefing_date: string;
  reason?: string;
}

interface AnnouncementItem {
  id: string;
  title: string;
  body: string | null;
  priority: "info" | "warning" | "critical";
  content_type: string; // "announcement" | "note" | "safety_notice"
  pin_to_top: boolean;
  created_at: string | null;
  expires_at: string | null;
  created_by_name: string | null;
  is_read: boolean;
  is_dismissed: boolean;
  // Safety notice fields
  safety_category: string | null;
  requires_acknowledgment: boolean;
  is_compliance_relevant: boolean;
  document_url: string | null;
  document_filename: string | null;
  acknowledgment_deadline: string | null;
  is_acknowledged: boolean;
}

// ── Safety category labels ──

const SAFETY_CATEGORY_LABELS: Record<string, string> = {
  procedure: "New Procedure",
  equipment_alert: "Equipment Alert",
  osha_reminder: "OSHA Reminder",
  incident_followup: "Incident Follow-up",
  training_assignment: "Training Assignment",
  toolbox_talk: "Toolbox Talk",
};

// ── Action link inference ──

function inferActionLink(
  item: BriefingItem,
  primaryArea: string | null,
): { label: string; route: string } | null {
  const text = item.text.toLowerCase();

  if (primaryArea === "funeral_scheduling") {
    if (text.includes("unassigned") || text.includes("no driver"))
      return { label: "Schedule", route: "/scheduling" };
    if (text.includes("vault not") || text.includes("inventory"))
      return { label: "Check inventory", route: "/inventory" };
    if (text.includes("spring burial"))
      return { label: "Spring burials", route: "/orders?tab=spring-burials" };
    if (text.includes("unscheduled order"))
      return { label: "View orders", route: "/orders?filter=unscheduled" };
  }

  if (primaryArea === "invoicing_ar") {
    if (text.includes("overdue") || text.includes("unpaid") || text.includes("past due"))
      return { label: "View invoices", route: "/invoices?filter=overdue" };
    if (text.includes("sync error") || text.includes("not syncing"))
      return { label: "Fix sync", route: "/settings/integrations/accounting" };
    if (text.includes("uninvoiced") || text.includes("not sent"))
      return { label: "Send invoices", route: "/invoices?filter=unsent" };
  }

  if (primaryArea === "safety_compliance") {
    if (text.includes("inspection") || text.includes("overdue"))
      return { label: "View safety", route: "/safety" };
    if (text.includes("incident"))
      return { label: "View incidents", route: "/safety/incidents" };
  }

  if (primaryArea === "full_admin") {
    if (text.includes("overdue") || text.includes("unpaid"))
      return { label: "View AR", route: "/invoices?filter=overdue" };
    if (text.includes("sync"))
      return { label: "Fix sync", route: "/settings/integrations/accounting" };
  }

  return null;
}

// ── Helpers ──

function formatTime(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function isAfterNoon(): boolean {
  return new Date().getHours() >= 12;
}

function todayDateString(): string {
  return new Date().toISOString().slice(0, 10);
}

function isAllClear(data: BriefingResponse): boolean {
  if (data.content?.toLowerCase().startsWith("all clear")) return true;
  if (data.content?.startsWith("\u2713")) return true;
  if (data.items.length <= 1 && data.items.every((i) => i.priority === "info")) return true;
  return false;
}

function relativeTime(isoString: string): string {
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDays = Math.floor(diffHr / 24);
  if (diffDays === 1) return "yesterday";
  return `${diffDays}d ago`;
}

function deadlineStatus(deadline: string | null): "ok" | "approaching" | "past" | null {
  if (!deadline) return null;
  const now = Date.now();
  const dl = new Date(deadline).getTime();
  if (dl < now) return "past";
  if (dl - now < 24 * 60 * 60 * 1000) return "approaching";
  return "ok";
}

// ── Sort announcements: required unacknowledged safety first, then pinned, then rest ──

function sortAnnouncements(items: AnnouncementItem[]): AnnouncementItem[] {
  return [...items].sort((a, b) => {
    const aRequired = a.content_type === "safety_notice" && a.requires_acknowledgment && !a.is_acknowledged;
    const bRequired = b.content_type === "safety_notice" && b.requires_acknowledgment && !b.is_acknowledged;
    if (aRequired && !bRequired) return -1;
    if (!aRequired && bRequired) return 1;
    if (a.pin_to_top && !b.pin_to_top) return -1;
    if (!a.pin_to_top && b.pin_to_top) return 1;
    return 0;
  });
}

// ── Action Items Types ──

interface ActionItemOrder {
  delivery_id: string;
  order_id: string | null;
  order_number: string | null;
  customer_name: string | null;
  deceased_name: string | null;
  cemetery_name: string | null;
  service_time: string | null;
  status: string;
  priority: string | null;
  assigned_driver_id: string | null;
}

interface ActionItemInvoice {
  id: string;
  number: string;
  customer_id: string;
  customer_name: string | null;
  total: string;
  amount_paid: string;
  balance_remaining: string;
  days_overdue: number;
  due_date: string | null;
  has_email: boolean;
}

interface ActionItemDraft {
  id: string;
  number: string;
  customer_name: string | null;
  total: string;
  has_exceptions: boolean;
  created_at: string | null;
}

interface ActionItems {
  orders_due_today: ActionItemOrder[];
  overdue_invoices: ActionItemInvoice[];
  draft_invoices: ActionItemDraft[];
  kb_recommendation: { show: boolean; document_count: number } | null;
}

function fmtCurrency(n: string | number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(n));
}

// ── BriefingActionItems sub-component ──

function BriefingActionItems({ items, onRefresh }: { items: ActionItems; onRefresh: () => void }) {
  const navigate = useNavigate();
  const [paymentTarget, setPaymentTarget] = useState<{ id: string; name: string; invoiceId: string } | null>(null);
  const [sendingInvoiceId, setSendingInvoiceId] = useState<string | null>(null);
  const [approvingInvoiceId, setApprovingInvoiceId] = useState<string | null>(null);

  const handleSendInvoice = async (invoiceId: string) => {
    setSendingInvoiceId(invoiceId);
    try {
      await apiClient.post(`/sales/invoices/${invoiceId}/send`);
      toast.success("Invoice sent");
      onRefresh();
    } catch {
      toast.error("Failed to send invoice");
    } finally {
      setSendingInvoiceId(null);
    }
  };

  const handleApproveAndSend = async (invoiceId: string) => {
    setApprovingInvoiceId(invoiceId);
    try {
      await apiClient.post(`/sales/invoices/${invoiceId}/approve`);
      try {
        await apiClient.post(`/sales/invoices/${invoiceId}/send`);
        toast.success("Invoice approved and sent");
      } catch {
        toast.success("Invoice approved (email send failed — send manually)");
      }
      onRefresh();
    } catch {
      toast.error("Failed to approve invoice");
    } finally {
      setApprovingInvoiceId(null);
    }
  };

  const hasContent =
    items.orders_due_today.length > 0 ||
    items.overdue_invoices.length > 0 ||
    items.draft_invoices.length > 0 ||
    items.kb_recommendation?.show;

  if (!hasContent) return null;

  return (
    <>
      <div className="mt-4 pt-3 border-t border-gray-100 space-y-4">
        {/* Orders Due Today */}
        {items.orders_due_today.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <Truck className="h-3.5 w-3.5 text-blue-600" />
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Orders Due Today
              </h4>
              <Badge variant="secondary" className="text-[10px] ml-1">
                {items.orders_due_today.length}
              </Badge>
            </div>
            <div className="space-y-1.5">
              {items.orders_due_today.map((order) => (
                <div
                  key={order.delivery_id}
                  className="flex items-center justify-between py-1.5 px-2 rounded-md hover:bg-gray-50 group"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900 truncate">
                        {order.order_number || "Delivery"}
                      </span>
                      {order.service_time && (
                        <span className="text-xs text-gray-500 flex items-center gap-0.5">
                          <Clock className="h-3 w-3" />
                          {order.service_time}
                        </span>
                      )}
                      {!order.assigned_driver_id && (
                        <Badge variant="outline" className="text-[10px] border-amber-300 text-amber-700">
                          No driver
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 truncate">
                      {[order.customer_name, order.deceased_name, order.cemetery_name]
                        .filter(Boolean)
                        .join(" — ")}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                    onClick={() => navigate(order.order_id ? `/ar/orders/${order.order_id}` : "/scheduling")}
                  >
                    <Eye className="h-3 w-3 mr-1" />
                    View
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Overdue Invoices */}
        {items.overdue_invoices.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <CreditCard className="h-3.5 w-3.5 text-red-600" />
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Overdue Invoices
              </h4>
              <Badge variant="secondary" className="text-[10px] ml-1 border-red-200 text-red-700 bg-red-50">
                {items.overdue_invoices.length}
              </Badge>
            </div>
            <div className="space-y-1.5">
              {items.overdue_invoices.map((inv) => (
                <div
                  key={inv.id}
                  className="flex items-center justify-between py-1.5 px-2 rounded-md hover:bg-gray-50 group"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <Link
                        to={`/ar/invoices/${inv.id}`}
                        className="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        {inv.number}
                      </Link>
                      <span className="text-xs text-gray-500">{inv.customer_name}</span>
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-[10px]",
                          inv.days_overdue > 60
                            ? "border-red-300 text-red-700"
                            : inv.days_overdue > 30
                              ? "border-amber-300 text-amber-700"
                              : "border-yellow-300 text-yellow-700",
                        )}
                      >
                        {inv.days_overdue}d overdue
                      </Badge>
                    </div>
                    <p className="text-xs text-gray-500">
                      Balance: {fmtCurrency(inv.balance_remaining)}
                    </p>
                  </div>
                  <div className="flex gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => setPaymentTarget({
                        id: inv.customer_id,
                        name: inv.customer_name || "Customer",
                        invoiceId: inv.id,
                      })}
                    >
                      <CreditCard className="h-3 w-3 mr-1" />
                      Pay
                    </Button>
                    {inv.has_email && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 text-xs"
                        disabled={sendingInvoiceId === inv.id}
                        onClick={() => handleSendInvoice(inv.id)}
                      >
                        <Send className="h-3 w-3 mr-1" />
                        {sendingInvoiceId === inv.id ? "..." : "Send"}
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Draft Invoices */}
        {items.draft_invoices.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <FileText className="h-3.5 w-3.5 text-gray-600" />
              <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                Draft Invoices
              </h4>
              <Badge variant="secondary" className="text-[10px] ml-1">
                {items.draft_invoices.length}
              </Badge>
            </div>
            <div className="space-y-1.5">
              {items.draft_invoices.map((inv) => (
                <div
                  key={inv.id}
                  className="flex items-center justify-between py-1.5 px-2 rounded-md hover:bg-gray-50 group"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <Link
                        to={`/ar/invoices/${inv.id}`}
                        className="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        {inv.number}
                      </Link>
                      <span className="text-xs text-gray-500">{inv.customer_name}</span>
                      <span className="text-xs font-medium text-gray-700">{fmtCurrency(inv.total)}</span>
                      {inv.has_exceptions && (
                        <Badge variant="outline" className="text-[10px] border-amber-300 text-amber-700">
                          Exceptions
                        </Badge>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => navigate(`/ar/invoices/${inv.id}`)}
                    >
                      <Eye className="h-3 w-3 mr-1" />
                      Review
                    </Button>
                    {!inv.has_exceptions && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 text-xs"
                        disabled={approvingInvoiceId === inv.id}
                        onClick={() => handleApproveAndSend(inv.id)}
                      >
                        <CheckCircle className="h-3 w-3 mr-1" />
                        {approvingInvoiceId === inv.id ? "..." : "Approve & Send"}
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* KB Recommendation */}
        {items.kb_recommendation?.show && (
          <div className="flex items-center gap-3 py-2 px-2 rounded-md bg-indigo-50/50">
            <BookOpen className="h-4 w-4 text-indigo-600 shrink-0" />
            <p className="text-sm text-gray-700 flex-1">
              {items.kb_recommendation.document_count === 0
                ? "Upload documents to your Knowledge Base to power Call Intelligence."
                : `Your Knowledge Base has ${items.kb_recommendation.document_count} documents — add more for better call assistance.`}
            </p>
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs shrink-0"
              onClick={() => navigate("/knowledge-base")}
            >
              <BookOpen className="h-3 w-3 mr-1" />
              Open KB
            </Button>
          </div>
        )}
      </div>

      {/* Payment Dialog */}
      {paymentTarget && (
        <RecordPaymentDialog
          open={!!paymentTarget}
          onClose={() => setPaymentTarget(null)}
          onSuccess={() => {
            setPaymentTarget(null);
            onRefresh();
          }}
          customerId={paymentTarget.id}
          customerName={paymentTarget.name}
          defaultInvoiceId={paymentTarget.invoiceId}
        />
      )}
    </>
  );
}

// ── Component ──

export function MorningBriefingCard() {
  const { user } = useAuth();
  const [data, setData] = useState<BriefingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [autoDismissProgress, setAutoDismissProgress] = useState(100);
  const [userInteracted, setUserInteracted] = useState(false);
  const [announcements, setAnnouncements] = useState<AnnouncementItem[]>([]);
  const [announcementsLoading, setAnnouncementsLoading] = useState(true);
  const [acknowledgingId, setAcknowledgingId] = useState<string | null>(null);
  const [ackNote, setAckNote] = useState("");
  const autoDismissTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const autoDismissTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  // Action items (structured data with entity IDs)
  const [actionItems, setActionItems] = useState<ActionItems | null>(null);

  // AI-enhanced briefing items
  const [aiNarrative, setAiNarrative] = useState<string | null>(null);
  const [aiPatterns, setAiPatterns] = useState<{alert_id: string; message: string; action_url: string | null}[]>([]);

  // Load AI enhancements after briefing data loads
  useEffect(() => {
    if (!data || !data.items) return;
    apiClient.post("/ai/briefing/enhance", {
      briefing_data: {
        today_count: data.items.length,
        legacy_proofs_pending_review: 0,
        crm_today_followups: 0,
        crm_overdue_followups: 0,
        crm_at_risk_accounts: [],
        crm_follow_up_items: [],
      },
    }).then((r) => {
      const items = r.data.items || [];
      for (const item of items) {
        if (item.type === "ai_narrative") setAiNarrative(item.content);
        if (item.type === "pattern_alert") setAiPatterns((prev) => [...prev, { alert_id: item.alert_id, message: item.message, action_url: item.action_url }]);
      }
    }).catch(() => {}); // AI features fail silently
  }, [data]);

  function dismissPattern(alertId: string) {
    apiClient.post(`/ai/pattern-alerts/${alertId}/dismiss`).catch(() => {});
    setAiPatterns((prev) => prev.filter((p) => p.alert_id !== alertId));
  }

  const dismissKey = `briefing_dismissed_${user?.id ?? "anon"}_${todayDateString()}`;

  // Check sessionStorage on mount
  useEffect(() => {
    if (sessionStorage.getItem(dismissKey) === "true") {
      setDismissed(true);
    }
  }, [dismissKey]);

  // Fetch briefing
  const fetchBriefing = useCallback(async () => {
    try {
      const res = await apiClient.get<BriefingResponse>("/briefings/briefing");
      setData(res.data);
    } catch {
      // Fail silently — don't show card
      setData(null);
    }
  }, []);

  // Fetch announcements
  const fetchAnnouncements = useCallback(async () => {
    try {
      const res = await apiClient.get<AnnouncementItem[]>("/announcements/my");
      setAnnouncements(res.data);
    } catch {
      setAnnouncements([]);
    } finally {
      setAnnouncementsLoading(false);
    }
  }, []);

  // Fetch action items
  const fetchActionItems = useCallback(async () => {
    try {
      const res = await apiClient.get<ActionItems>("/briefings/action-items");
      setActionItems(res.data);
    } catch {
      setActionItems(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      await Promise.all([fetchBriefing(), fetchAnnouncements(), fetchActionItems()]);
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [fetchBriefing, fetchAnnouncements, fetchActionItems]);

  // Mark unread announcements as read (fire-and-forget)
  useEffect(() => {
    if (announcementsLoading) return;
    announcements.forEach((a) => {
      if (!a.is_read) {
        apiClient.post(`/announcements/${a.id}/read`).catch(() => {});
      }
    });
  }, [announcements, announcementsLoading]);

  const handleDismissAnnouncement = async (id: string) => {
    try {
      await apiClient.post(`/announcements/${id}/dismiss`);
    } catch {
      // continue removing from UI
    }
    setAnnouncements((prev) => prev.filter((a) => a.id !== id));
  };

  const handleAcknowledge = async (id: string) => {
    try {
      await apiClient.post(`/announcements/${id}/acknowledge`, { note: ackNote || null });
      setAnnouncements(prev => prev.filter(a => a.id !== id));
      setAcknowledgingId(null);
      setAckNote("");
    } catch {
      // silent fail
    }
  };

  // Auto-dismiss for all-clear
  useEffect(() => {
    if (!data || userInteracted || dismissed) return;
    if (!isAllClear(data)) return;

    const duration = 10_000;
    const interval = 50;
    let elapsed = 0;

    autoDismissTimer.current = setInterval(() => {
      elapsed += interval;
      setAutoDismissProgress(Math.max(0, 100 - (elapsed / duration) * 100));
    }, interval);

    autoDismissTimeout.current = setTimeout(() => {
      sessionStorage.setItem(dismissKey, "true");
      setDismissed(true);
    }, duration);

    return () => {
      if (autoDismissTimer.current) clearInterval(autoDismissTimer.current);
      if (autoDismissTimeout.current) clearTimeout(autoDismissTimeout.current);
    };
  }, [data, userInteracted, dismissed, dismissKey]);

  // Stop auto-dismiss on user interaction
  const handleInteraction = useCallback(() => {
    if (userInteracted) return;
    setUserInteracted(true);
    setAutoDismissProgress(100);
    if (autoDismissTimer.current) clearInterval(autoDismissTimer.current);
    if (autoDismissTimeout.current) clearTimeout(autoDismissTimeout.current);
  }, [userInteracted]);

  const handleDismiss = () => {
    sessionStorage.setItem(dismissKey, "true");
    setDismissed(true);
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const res = await apiClient.post<BriefingResponse>("/briefings/briefing/refresh");
      setData(res.data);
    } catch {
      // Silently fail
    } finally {
      setRefreshing(false);
    }
  };

  const hasAnnouncements = announcements.length > 0;
  const sortedAnnouncements = sortAnnouncements(announcements);
  const unacknowledgedSafetyCount = announcements.filter(
    a => a.content_type === "safety_notice" && a.requires_acknowledgment && !a.is_acknowledged
  ).length;

  // Don't render conditions
  if (dismissed && !hasAnnouncements) return null;
  if (loading) {
    return (
      <Card className="relative overflow-hidden">
        <CardContent className="p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="h-5 w-16 bg-gray-200 rounded animate-pulse" />
            <div className="h-4 w-14 bg-gray-200 rounded animate-pulse" />
          </div>
          <div className="space-y-3">
            <div className="h-4 w-full bg-gray-200 rounded animate-pulse" />
            <div className="h-4 w-4/5 bg-gray-200 rounded animate-pulse" />
            <div className="h-4 w-3/5 bg-gray-200 rounded animate-pulse" />
          </div>
        </CardContent>
      </Card>
    );
  }

  const briefingDisabled = data?.content === null && data?.reason === "disabled";
  const hasBriefing = data && !briefingDisabled && !dismissed;

  if (!hasBriefing && !hasAnnouncements) return null;

  // ── Announcements section (reused across variants) ──
  const announcementsSection = hasAnnouncements ? (
    <div>
      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
        Announcements
        {unacknowledgedSafetyCount > 0 && (
          <span className="ml-2 inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
            {unacknowledgedSafetyCount} safety
          </span>
        )}
      </h4>
      <div className="space-y-2">
        {sortedAnnouncements.map((a) => {
          // Case A: Required safety notice (requires_acknowledgment && !is_acknowledged)
          if (a.content_type === "safety_notice" && a.requires_acknowledgment && !a.is_acknowledged) {
            const dlStatus = deadlineStatus(a.acknowledgment_deadline);
            const isAcknowledging = acknowledgingId === a.id;

            return (
              <div
                key={a.id}
                className={cn(
                  "pl-3 pr-2 py-2 rounded-sm border-l-2",
                  dlStatus === "past" ? "border-l-red-500 bg-red-50/50" : "border-l-amber-500 bg-amber-50/50",
                )}
              >
                {isAcknowledging ? (
                  // Confirmation overlay
                  <div className="space-y-2">
                    <p className="text-sm font-semibold text-gray-900">
                      Confirm acknowledgment
                    </p>
                    <p className="text-xs text-gray-600">
                      By acknowledging, you confirm you have read and understood this safety notice.
                    </p>
                    <textarea
                      value={ackNote}
                      onChange={(e) => setAckNote(e.target.value)}
                      rows={2}
                      className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      placeholder="Optional note..."
                    />
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => handleAcknowledge(a.id)}
                      >
                        Confirm
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs"
                        onClick={() => { setAcknowledgingId(null); setAckNote(""); }}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  // Normal required safety notice content
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <AlertTriangle className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                      <span className="text-xs font-semibold text-amber-700 uppercase tracking-wide">
                        Safety Notice — Action Required
                      </span>
                    </div>
                    <p className="text-sm font-semibold text-gray-900 mt-1">{a.title}</p>
                    {a.body && (
                      <p className="text-sm text-gray-700 mt-0.5 leading-relaxed">{a.body}</p>
                    )}
                    {a.document_url && (
                      <a
                        href={a.document_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 mt-1"
                      >
                        <FileText className="h-3 w-3" />
                        {a.document_filename || "View document"}
                      </a>
                    )}
                    <div className="flex items-center gap-3 mt-1">
                      <p className="text-xs text-gray-400">
                        {a.created_by_name && <>from {a.created_by_name} &middot; </>}
                        {a.created_at ? relativeTime(a.created_at) : ""}
                      </p>
                      {a.acknowledgment_deadline && (
                        <span
                          className={cn(
                            "text-xs font-medium",
                            dlStatus === "past" && "text-red-600",
                            dlStatus === "approaching" && "text-amber-600",
                            dlStatus === "ok" && "text-gray-500",
                          )}
                        >
                          {dlStatus === "past" ? "Overdue" : `Due ${new Date(a.acknowledgment_deadline).toLocaleDateString()}`}
                        </span>
                      )}
                    </div>
                    <button
                      onClick={() => setAcknowledgingId(a.id)}
                      className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-amber-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-700 transition-colors"
                    >
                      <Check className="h-3 w-3" />
                      I have read and understood this
                    </button>
                  </div>
                )}
              </div>
            );
          }

          // Case B: Informational safety notice (content_type === "safety_notice" && !requires_acknowledgment)
          if (a.content_type === "safety_notice" && !a.requires_acknowledgment) {
            const categoryLabel = a.safety_category
              ? SAFETY_CATEGORY_LABELS[a.safety_category] || a.safety_category
              : "General";

            return (
              <div
                key={a.id}
                className="pl-3 pr-2 py-2 rounded-sm border-l-2 border-l-blue-400 bg-blue-50/50"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="shrink-0" role="img" aria-label="Safety vest">
                        🦺
                      </span>
                      <span className="text-xs font-semibold text-blue-700 uppercase tracking-wide">
                        Safety Notice — {categoryLabel}
                      </span>
                    </div>
                    <p className="text-sm font-semibold text-gray-900 mt-1">{a.title}</p>
                    {a.body && (
                      <p className="text-sm text-gray-700 mt-0.5 leading-relaxed">{a.body}</p>
                    )}
                    {a.document_url && (
                      <a
                        href={a.document_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 mt-1"
                      >
                        <FileText className="h-3 w-3" />
                        {a.document_filename || "View document"}
                      </a>
                    )}
                    <p className="text-xs text-gray-400 mt-1">
                      {a.created_by_name && <>from {a.created_by_name} &middot; </>}
                      {a.created_at ? relativeTime(a.created_at) : ""}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDismissAnnouncement(a.id)}
                    className="p-0.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors shrink-0 mt-0.5"
                    aria-label="Dismiss announcement"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            );
          }

          // Case C: Regular announcement/note (existing behavior)
          return (
            <div
              key={a.id}
              className={cn(
                "pl-3 pr-2 py-2 rounded-sm border-l-2",
                a.priority === "critical" && "border-l-red-500 bg-red-50/50",
                a.priority === "warning" && "border-l-amber-500 bg-amber-50/50",
                a.priority === "info" && "border-l-blue-400 bg-blue-50/50",
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    {a.pin_to_top && (
                      <Pin className="h-3 w-3 text-gray-400 shrink-0" />
                    )}
                    <span className="text-sm font-semibold text-gray-900">
                      {a.title}
                    </span>
                  </div>
                  {a.body && (
                    <p className="text-sm text-gray-700 mt-0.5 leading-relaxed">
                      {a.body}
                    </p>
                  )}
                  <p className="text-xs text-gray-400 mt-1">
                    {a.created_by_name && <>from {a.created_by_name} &middot; </>}
                    {a.created_at ? relativeTime(a.created_at) : ""}
                  </p>
                </div>
                <button
                  onClick={() => handleDismissAnnouncement(a.id)}
                  className="p-0.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors shrink-0 mt-0.5"
                  aria-label="Dismiss announcement"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  ) : null;

  const allClear = hasBriefing ? isAllClear(data!) : false;
  const afternoon = isAfterNoon();
  const headerTitle = data?.tier === "role_based" ? "Your day" : afternoon ? "Current Status" : "Today";
  const timeLabel = data
    ? afternoon
      ? `as of ${formatTime(data.generated_at)}`
      : formatTime(data.generated_at)
    : "";

  // ── Announcements-only (no briefing to show) ──
  if (!hasBriefing && hasAnnouncements) {
    return (
      <Card ref={cardRef} className="relative overflow-hidden">
        <CardContent className="p-5">
          {announcementsSection}
        </CardContent>
      </Card>
    );
  }

  // ── Driver / role_based paragraph variant ──
  if (data!.tier === "role_based") {
    return (
      <Card
        ref={cardRef}
        className="relative overflow-hidden"
        onMouseEnter={handleInteraction}
        onClick={handleInteraction}
      >
        <CardContent className="p-5">
          {announcementsSection}
          {hasAnnouncements && (
            <div className="my-3 border-t border-gray-100" />
          )}
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-900">{headerTitle}</h3>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400">{timeLabel}</span>
              <button
                onClick={handleDismiss}
                className="p-0.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
                aria-label="Dismiss briefing"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
          <p className="text-sm text-gray-700 leading-relaxed">
            {data!.content ?? data!.items.map((i) => i.text).join(" ")}
          </p>
        </CardContent>
      </Card>
    );
  }

  // ── All-clear variant ──
  if (allClear) {
    const displayText = data!.content ?? data!.items[0]?.text ?? "All clear. No flags.";
    return (
      <Card
        ref={cardRef}
        className="relative overflow-hidden"
        onMouseEnter={handleInteraction}
        onClick={handleInteraction}
      >
        <CardContent className="p-5">
          {announcementsSection}
          {hasAnnouncements && (
            <div className="my-3 border-t border-gray-100" />
          )}
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-900">{headerTitle}</h3>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400">{timeLabel}</span>
              <button
                onClick={handleDismiss}
                className="p-0.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
                aria-label="Dismiss briefing"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <Check className="h-4 w-4 text-green-600 mt-0.5 shrink-0" />
            <p className="text-sm text-gray-700 leading-relaxed">{displayText}</p>
          </div>
        </CardContent>
        {/* Auto-dismiss progress bar */}
        {!userInteracted && (
          <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gray-100">
            <div
              className="h-full bg-green-500 transition-all duration-50 ease-linear"
              style={{ width: `${autoDismissProgress}%` }}
            />
          </div>
        )}
      </Card>
    );
  }

  // ── Standard numbered items variant ──
  return (
    <Card
      ref={cardRef}
      className="relative overflow-hidden"
      onMouseEnter={handleInteraction}
      onClick={handleInteraction}
    >
      <CardContent className="p-5">
        {/* Announcements */}
        {announcementsSection}
        {hasAnnouncements && data!.items.length > 0 && (
          <div className="my-3 border-t border-gray-100" />
        )}

        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-900">{headerTitle}</h3>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">{timeLabel}</span>
            <button
              onClick={handleDismiss}
              className="p-0.5 rounded hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
              aria-label="Dismiss briefing"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* AI Narrative — shown above items if available */}
        {aiNarrative && (
          <div className="mb-4 p-3 bg-blue-50/50 rounded-lg border border-blue-100 relative">
            <span className="absolute top-2 right-2 text-xs text-blue-400">✨</span>
            <p className="text-[15px] text-gray-800 leading-relaxed">{aiNarrative}</p>
          </div>
        )}

        {/* Pattern Alerts */}
        {aiPatterns.length > 0 && (
          <div className="mb-4 space-y-2">
            {aiPatterns.map((p) => (
              <div key={p.alert_id} className="flex items-start gap-2 p-2 bg-amber-50 rounded-lg border border-amber-100 text-sm">
                <span className="text-amber-500 mt-0.5">💡</span>
                <div className="flex-1">
                  <p className="text-gray-700">{p.message}</p>
                  {p.action_url && <a href={p.action_url} className="text-xs text-blue-600 hover:underline">View account →</a>}
                </div>
                <button onClick={() => dismissPattern(p.alert_id)} className="text-xs text-gray-400 hover:text-gray-600">Dismiss</button>
              </div>
            ))}
          </div>
        )}

        {/* Items */}
        <div className="space-y-3">
          {data!.items.map((item) => {
            const action = inferActionLink(item, data!.primary_area);
            return (
              <div
                key={item.number}
                className={cn(
                  "flex items-start gap-3 pl-2 py-1",
                  item.priority === "critical" && "border-l-2 border-l-red-500",
                  item.priority === "warning" && "border-l-2 border-l-amber-500",
                )}
              >
                <span className="text-xs font-medium text-gray-400 mt-0.5 shrink-0 w-4 text-right">
                  {item.number}.
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-700 leading-relaxed">
                    {item.text}
                    {item.priority === "info" &&
                      item.text.toLowerCase().includes("assigned") &&
                      !action && (
                        <span className="ml-1 text-green-600">
                          <Check className="inline h-3.5 w-3.5" />
                        </span>
                      )}
                  </p>
                </div>
                {action && (
                  <Link
                    to={action.route}
                    className="shrink-0 text-xs font-medium text-blue-600 hover:text-blue-800 flex items-center gap-0.5 mt-0.5 whitespace-nowrap"
                  >
                    {action.label}
                    <ChevronRight className="h-3 w-3" />
                  </Link>
                )}
              </div>
            );
          })}
        </div>

        {/* Action Items */}
        {actionItems && (
          <BriefingActionItems items={actionItems} onRefresh={fetchActionItems} />
        )}

        {/* Footer / Refresh */}
        <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between">
          <div className="text-xs text-gray-400">
            {data!.was_cached && (
              <span>Generated at {formatTime(data!.generated_at)} &middot; </span>
            )}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing}
            className="h-7 text-xs text-gray-500 hover:text-gray-700 gap-1.5"
          >
            <RefreshCw className={cn("h-3 w-3", refreshing && "animate-spin")} />
            Refresh
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
