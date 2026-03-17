/**
 * Platform Admin — Extension Demand Signal Dashboard
 *
 * Shows coming_soon extensions sorted by notify_me_count descending.
 * Product prioritization view: build what customers want most.
 */

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import platformClient from "@/lib/platform-api-client";
import type { DemandSignalItem } from "@/types/extension";

export default function ExtensionDemandPage() {
  const [items, setItems] = useState<DemandSignalItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedKey, setExpandedKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const { data } = await platformClient.get<DemandSignalItem[]>(
        "/extensions/notify-requests/demand",
      );
      setItems(data);
    } catch {
      toast.error("Failed to load demand signals");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleUpdateStatus = async (item: DemandSignalItem, newStatus: string) => {
    try {
      await platformClient.put(`/extensions/${item.id}`, { status: newStatus });
      toast.success(`${item.name} marked as ${newStatus}`);
      load();
    } catch {
      toast.error("Failed to update status");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white/50" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Extension Demand Signals</h1>
        <p className="text-slate-400 mt-1">
          Coming soon extensions ranked by tenant interest — build what customers want most.
        </p>
      </div>

      {items.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          No coming soon extensions with notify-me requests yet.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item, index) => (
            <div
              key={item.id}
              className="bg-slate-800 border border-slate-700 rounded-lg p-4"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-4 flex-1">
                  {/* Rank + count */}
                  <div className="text-center shrink-0">
                    <div className="text-3xl font-bold text-white">
                      {item.notify_me_count}
                    </div>
                    <div className="text-xs text-slate-500 uppercase">
                      requests
                    </div>
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs text-slate-500 font-mono">
                        #{index + 1}
                      </span>
                      <h3 className="font-semibold text-white">
                        {item.name}
                      </h3>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-300">
                        {item.category}
                      </span>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          item.status === "coming_soon"
                            ? "bg-amber-900/50 text-amber-300"
                            : "bg-purple-900/50 text-purple-300"
                        }`}
                      >
                        {item.status}
                      </span>
                    </div>
                    {item.tagline && (
                      <p className="text-sm text-slate-400 mt-1">
                        {item.tagline}
                      </p>
                    )}

                    {/* Expandable tenant list */}
                    {item.tenant_names.length > 0 && (
                      <div className="mt-2">
                        <button
                          onClick={() =>
                            setExpandedKey(
                              expandedKey === item.extension_key
                                ? null
                                : item.extension_key,
                            )
                          }
                          className="text-xs text-blue-400 hover:text-blue-300"
                        >
                          {expandedKey === item.extension_key
                            ? "Hide"
                            : `Show ${item.tenant_names.length} requesting tenant${item.tenant_names.length > 1 ? "s" : ""}`}
                        </button>
                        {expandedKey === item.extension_key && (
                          <ul className="mt-1 space-y-0.5">
                            {item.tenant_names.map((name) => (
                              <li
                                key={name}
                                className="text-xs text-slate-400 pl-3"
                              >
                                {name}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Action buttons */}
                <div className="flex items-center gap-2 shrink-0">
                  {item.status === "coming_soon" && (
                    <button
                      onClick={() => handleUpdateStatus(item, "beta")}
                      className="px-3 py-1.5 text-xs font-medium bg-purple-600 text-white rounded hover:bg-purple-700 transition-colors"
                    >
                      Mark In Development
                    </button>
                  )}
                  {(item.status === "coming_soon" || item.status === "beta") && (
                    <button
                      onClick={() => handleUpdateStatus(item, "active")}
                      className="px-3 py-1.5 text-xs font-medium bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
                    >
                      Mark Active
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
