// EntityTimeline.tsx — Slide-over panel showing vault items for a given entity

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  Calendar,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  FileText,
  Loader2,
  MessageSquare,
  Package,
  Shield,
  Truck,
  X,
  Zap,
} from "lucide-react";
import apiClient from "@/lib/api-client";

// ── Types ─────────────────────────────────────────────────────────────────────

interface VaultItem {
  id: string;
  item_type: string;
  event_type?: string | null;
  event_type_sub?: string | null;
  title: string;
  description?: string | null;
  event_start?: string | null;
  event_end?: string | null;
  created_at: string;
  status: string;
  source: string;
  mime_type?: string | null;
  document_type?: string | null;
  metadata_json?: Record<string, unknown> | null;
}

type FilterTab = "all" | "event" | "document" | "communication";

interface DateGroup {
  label: string;
  items: VaultItem[];
}

// ── Icon helpers ──────────────────────────────────────────────────────────────

function itemIcon(item: VaultItem): React.ReactNode {
  const t = item.item_type;
  const et = item.event_type ?? "";
  if (t === "document") return <FileText className="h-4 w-4 text-blue-500" />;
  if (t === "communication") return <MessageSquare className="h-4 w-4 text-purple-500" />;
  if (et.includes("delivery") || et.includes("route"))
    return <Truck className="h-4 w-4 text-green-500" />;
  if (et.includes("safety") || et.includes("training"))
    return <Shield className="h-4 w-4 text-amber-500" />;
  if (et.includes("production") || et.includes("pour"))
    return <Package className="h-4 w-4 text-slate-500" />;
  if (et.includes("compliance"))
    return <AlertTriangle className="h-4 w-4 text-red-500" />;
  if (t === "event") return <Calendar className="h-4 w-4 text-indigo-500" />;
  if (t === "compliance_item") return <CheckCircle className="h-4 w-4 text-emerald-500" />;
  return <Zap className="h-4 w-4 text-gray-400" />;
}

// ── Date grouping ─────────────────────────────────────────────────────────────

function getDateLabel(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const dayMs = 86400000;
  const diff = now.getTime() - date.getTime();

  if (diff < dayMs && now.getDate() === date.getDate()) return "Today";
  if (diff < 2 * dayMs) return "Yesterday";
  if (diff < 7 * dayMs) return "This Week";
  return "Earlier";
}

const DATE_GROUP_ORDER = ["Today", "Yesterday", "This Week", "Earlier"];

function groupByDate(items: VaultItem[]): DateGroup[] {
  const groups: Record<string, VaultItem[]> = {};
  for (const item of items) {
    const ts = item.event_start ?? item.created_at;
    const label = getDateLabel(ts);
    if (!groups[label]) groups[label] = [];
    groups[label].push(item);
  }
  return DATE_GROUP_ORDER.filter((l) => groups[l]).map((label) => ({
    label,
    items: groups[label],
  }));
}

function formatTime(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

// ── Component ──────────────────────────────────────────────────────────────────

interface EntityTimelineProps {
  entityType: string;
  entityId: string;
  entityName: string;
  isOpen: boolean;
  onClose: () => void;
}

export function EntityTimeline({
  entityType,
  entityId,
  entityName,
  isOpen,
  onClose,
}: EntityTimelineProps) {
  const [items, setItems] = useState<VaultItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterTab>("all");
  const [sortNewest, setSortNewest] = useState(true);
  const overlayRef = useRef<HTMLDivElement>(null);

  const fetchItems = useCallback(async () => {
    if (!isOpen || !entityId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.get("/vault/items", {
        params: {
          related_entity_type: entityType,
          related_entity_id: entityId,
          limit: 200,
        },
      });
      setItems(res.data.items ?? res.data ?? []);
    } catch {
      setError("Failed to load history.");
    } finally {
      setLoading(false);
    }
  }, [isOpen, entityType, entityId]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return;
    function handleClick(e: MouseEvent) {
      if (overlayRef.current && !overlayRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [isOpen, onClose]);

  // Filter
  const filtered = items.filter((item) => {
    if (filter === "all") return true;
    if (filter === "event") return item.item_type === "event";
    if (filter === "document") return item.item_type === "document";
    if (filter === "communication") return item.item_type === "communication";
    return true;
  });

  // Sort
  const sorted = [...filtered].sort((a, b) => {
    const aTs = a.event_start ?? a.created_at;
    const bTs = b.event_start ?? b.created_at;
    return sortNewest
      ? new Date(bTs).getTime() - new Date(aTs).getTime()
      : new Date(aTs).getTime() - new Date(bTs).getTime();
  });

  const groups = groupByDate(sorted);

  const FILTER_TABS: { key: FilterTab; label: string }[] = [
    { key: "all", label: "All" },
    { key: "event", label: "Events" },
    { key: "document", label: "Documents" },
    { key: "communication", label: "Comms" },
  ];

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div className="fixed inset-0 z-40 bg-black/20" onClick={onClose} />
      )}

      {/* Slide-over panel */}
      <div
        ref={overlayRef}
        className={`fixed right-0 top-0 z-50 h-full w-full max-w-[420px] bg-white shadow-2xl flex flex-col transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-start justify-between border-b border-gray-100 px-4 py-4">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Timeline</h2>
            <p className="text-sm text-gray-500 truncate max-w-[300px]">{entityName}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Filter tabs */}
        <div className="flex gap-1 border-b border-gray-100 px-4 py-2">
          {FILTER_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setFilter(tab.key)}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                filter === tab.key
                  ? "bg-blue-100 text-blue-700"
                  : "text-gray-500 hover:bg-gray-100"
              }`}
            >
              {tab.label}
            </button>
          ))}
          <div className="flex-1" />
          {/* Sort toggle */}
          <button
            onClick={() => setSortNewest((v) => !v)}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-gray-400 hover:bg-gray-100"
          >
            {sortNewest ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronUp className="h-3.5 w-3.5" />
            )}
            {sortNewest ? "Newest" : "Oldest"}
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-4 py-3">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
            </div>
          )}

          {error && (
            <p className="py-8 text-center text-sm text-red-500">{error}</p>
          )}

          {!loading && !error && sorted.length === 0 && (
            <div className="py-12 text-center">
              <p className="text-sm text-gray-400">No history yet for {entityName}</p>
            </div>
          )}

          {!loading &&
            !error &&
            groups.map((group) => (
              <div key={group.label} className="mb-4">
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
                  {group.label}
                </p>

                <div className="space-y-1">
                  {group.items.map((item) => {
                    const ts = item.event_start ?? item.created_at;
                    const isToday = getDateLabel(ts) === "Today";
                    const timeStr = isToday ? formatTime(ts) : formatDate(ts);

                    return (
                      <div
                        key={item.id}
                        className="flex items-start gap-3 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2.5 hover:border-gray-200 hover:bg-white transition-colors"
                      >
                        <div className="mt-0.5 flex-shrink-0">{itemIcon(item)}</div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-800 truncate">
                            {item.title}
                          </p>
                          {item.description && (
                            <p className="mt-0.5 text-xs text-gray-500 line-clamp-2">
                              {item.description}
                            </p>
                          )}
                          <div className="mt-1 flex items-center gap-2">
                            <span className="text-[10px] text-gray-400">{timeStr}</span>
                            {item.event_type && (
                              <span className="rounded bg-gray-200 px-1 py-0.5 text-[9px] text-gray-500">
                                {item.event_type.replace(/_/g, " ")}
                              </span>
                            )}
                            {item.status && item.status !== "active" && (
                              <span className="rounded bg-gray-200 px-1 py-0.5 text-[9px] text-gray-500">
                                {item.status}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
        </div>
      </div>
    </>
  );
}
