/**
 * Customer Type Manager
 *
 * Post-migration tool for reviewing and correcting customer classifications.
 * Shows all customers grouped by type, lets admins fix misclassified accounts,
 * and automatically updates extension visibility when types change.
 *
 * Route: /settings/data/customer-types
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  ChevronDown,
  HardHat,
  Loader2,
  Search,
  TreePine,
  Users,
} from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";

// ─── Types ────────────────────────────────────────────────────────────────────

interface CustomerRow {
  id: string;
  name: string;
  customer_type: string | null;
  classification_confidence: number | null;
  classification_method: string | null;
  classification_reasoning: string | null;
  account_number: string | null;
  city: string | null;
  state: string | null;
  is_extension_hidden: boolean;
}

type FilterTab = "all" | "needs_review" | "funeral_home" | "cemetery" | "contractor" | "individual" | "unknown";

const CUSTOMER_TYPES = [
  { key: "funeral_home", label: "Funeral Home", icon: <Building2 className="h-3.5 w-3.5" /> },
  { key: "cemetery", label: "Cemetery", icon: <TreePine className="h-3.5 w-3.5" /> },
  { key: "contractor", label: "Contractor", icon: <HardHat className="h-3.5 w-3.5" /> },
  { key: "individual", label: "Individual", icon: <Users className="h-3.5 w-3.5" /> },
  { key: "unknown", label: "Unknown", icon: null },
];

const TYPE_COLORS: Record<string, string> = {
  funeral_home: "bg-indigo-100 text-indigo-700",
  cemetery: "bg-emerald-100 text-emerald-700",
  contractor: "bg-orange-100 text-orange-700",
  individual: "bg-purple-100 text-purple-700",
  unknown: "bg-slate-100 text-slate-500",
};

function TypeBadge({ type }: { type: string | null }) {
  if (!type) return <span className="inline-block text-xs text-slate-400 italic">none</span>;
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_COLORS[type] ?? "bg-slate-100 text-slate-600"}`}>
      {type.replace("_", " ")}
    </span>
  );
}

function ConfidencePill({ confidence, method }: { confidence: number | null; method: string | null }) {
  if (confidence === null) return null;
  const pct = Math.round(confidence * 100);
  const color = pct >= 85 ? "text-green-600" : pct >= 70 ? "text-amber-600" : "text-red-600";
  return (
    <span className={`text-xs ${color}`} title={`Classified by ${method ?? "unknown"}`}>
      {pct}%
    </span>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function CustomerTypesPage() {
  const navigate = useNavigate();

  const [customers, setCustomers] = useState<CustomerRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const [search, setSearch] = useState("");
  const [reclassifying, setReclassifying] = useState<Set<string>>(new Set());
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);

  // Bulk selection
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkType, setBulkType] = useState("");
  const [bulkLoading, setBulkLoading] = useState(false);

  useEffect(() => {
    loadCustomers();
  }, []);

  async function loadCustomers() {
    setLoading(true);
    try {
      // Load all customers including hidden ones (contractors)
      const res = await apiClient.get("/customers", {
        params: { per_page: 500, include_hidden: true, include_inactive: false },
      });
      setCustomers(res.data.items ?? []);
    } catch {
      toast.error("Failed to load customers");
    } finally {
      setLoading(false);
    }
  }

  async function reclassify(customerId: string, newType: string) {
    setReclassifying((prev) => new Set(prev).add(customerId));
    setOpenDropdown(null);
    try {
      const res = await apiClient.patch(`/customers/${customerId}/reclassify`, { customer_type: newType });
      setCustomers((prev) =>
        prev.map((c) =>
          c.id === customerId
            ? {
                ...c,
                customer_type: newType,
                is_extension_hidden: res.data.is_extension_hidden,
                classification_confidence: res.data.classification_confidence,
                classification_method: res.data.classification_method,
              }
            : c
        )
      );
      toast.success(`Reclassified as ${newType.replace("_", " ")}`);
    } catch {
      toast.error("Failed to reclassify customer");
    } finally {
      setReclassifying((prev) => {
        const next = new Set(prev);
        next.delete(customerId);
        return next;
      });
    }
  }

  async function bulkReclassify() {
    if (!bulkType || selected.size === 0) return;
    setBulkLoading(true);
    let succeeded = 0;
    for (const id of selected) {
      try {
        const res = await apiClient.patch(`/customers/${id}/reclassify`, { customer_type: bulkType });
        setCustomers((prev) =>
          prev.map((c) =>
            c.id === id
              ? { ...c, customer_type: bulkType, is_extension_hidden: res.data.is_extension_hidden }
              : c
          )
        );
        succeeded++;
      } catch {
        // continue
      }
    }
    toast.success(`Reclassified ${succeeded} of ${selected.size} customers`);
    setSelected(new Set());
    setBulkType("");
    setBulkLoading(false);
  }

  // Filter customers
  const filtered = customers.filter((c) => {
    const matchSearch = !search || c.name.toLowerCase().includes(search.toLowerCase()) ||
      (c.account_number ?? "").toLowerCase().includes(search.toLowerCase());

    if (!matchSearch) return false;

    switch (activeTab) {
      case "needs_review":
        return !c.customer_type || c.customer_type === "unknown" ||
          (c.classification_confidence !== null && c.classification_confidence < 0.75);
      case "funeral_home":
        return c.customer_type === "funeral_home";
      case "cemetery":
        return c.customer_type === "cemetery";
      case "contractor":
        return c.customer_type === "contractor";
      case "individual":
        return c.customer_type === "individual";
      case "unknown":
        return !c.customer_type || c.customer_type === "unknown";
      default:
        return true;
    }
  });

  // Tab counts
  const counts: Record<string, number> = {
    all: customers.length,
    needs_review: customers.filter(
      (c) => !c.customer_type || c.customer_type === "unknown" ||
        (c.classification_confidence !== null && c.classification_confidence < 0.75)
    ).length,
    funeral_home: customers.filter((c) => c.customer_type === "funeral_home").length,
    cemetery: customers.filter((c) => c.customer_type === "cemetery").length,
    contractor: customers.filter((c) => c.customer_type === "contractor").length,
    individual: customers.filter((c) => c.customer_type === "individual").length,
    unknown: customers.filter((c) => !c.customer_type || c.customer_type === "unknown").length,
  };

  const TABS: Array<{ key: FilterTab; label: string }> = [
    { key: "all", label: `All (${counts.all})` },
    { key: "needs_review", label: `Needs Review (${counts.needs_review})` },
    { key: "funeral_home", label: `Funeral Homes (${counts.funeral_home})` },
    { key: "cemetery", label: `Cemeteries (${counts.cemetery})` },
    { key: "contractor", label: `Contractors (${counts.contractor})` },
    { key: "unknown", label: `Unknown (${counts.unknown})` },
  ];

  const allSelected = filtered.length > 0 && filtered.every((c) => selected.has(c.id));

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (allSelected) {
      setSelected((prev) => {
        const next = new Set(prev);
        filtered.forEach((c) => next.delete(c.id));
        return next;
      });
    } else {
      setSelected((prev) => {
        const next = new Set(prev);
        filtered.forEach((c) => next.add(c.id));
        return next;
      });
    }
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 p-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Customer Type Manager</h1>
          <p className="text-sm text-slate-500 mt-1">
            Review and correct customer classifications. Type changes automatically update extension visibility.
          </p>
        </div>
        <button
          onClick={() => navigate("/customers")}
          className="text-sm text-slate-500 hover:text-slate-700 border border-slate-300 rounded-lg px-3 py-1.5"
        >
          ← Back to Customers
        </button>
      </div>

      {/* Needs-review banner */}
      {counts.needs_review > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-amber-900">
              {counts.needs_review} customer{counts.needs_review > 1 ? "s" : ""} need classification review
            </p>
            <p className="text-xs text-amber-700 mt-0.5">
              These were imported but couldn't be classified with high confidence. Click the type buttons to assign them.
            </p>
          </div>
          <button
            onClick={() => setActiveTab("needs_review")}
            className="ml-auto shrink-0 text-sm font-medium text-amber-800 underline"
          >
            View
          </button>
        </div>
      )}

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="sticky top-4 z-20 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 flex items-center gap-3">
          <span className="text-sm font-medium text-blue-800">{selected.size} selected</span>
          <select
            value={bulkType}
            onChange={(e) => setBulkType(e.target.value)}
            className="text-sm rounded border border-blue-300 px-2 py-1 bg-white text-slate-700"
          >
            <option value="">Choose type…</option>
            {CUSTOMER_TYPES.map((t) => (
              <option key={t.key} value={t.key}>{t.label}</option>
            ))}
          </select>
          <button
            onClick={bulkReclassify}
            disabled={!bulkType || bulkLoading}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {bulkLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
            Apply to {selected.size}
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="ml-auto text-sm text-blue-700 hover:text-blue-900"
          >
            Clear
          </button>
        </div>
      )}

      {/* Tabs + search */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
        <div className="flex gap-1 flex-wrap">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => { setActiveTab(t.key); setSelected(new Set()); }}
              className={`px-3 py-1.5 text-sm rounded-full font-medium transition-colors ${
                activeTab === t.key
                  ? "bg-slate-900 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="relative ml-auto">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8 pr-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 w-52"
          />
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-16 text-slate-400">
          <Loader2 className="h-6 w-6 animate-spin mr-2" />
          Loading customers…
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <Users className="h-8 w-8 mx-auto mb-2 opacity-40" />
          <p className="text-sm">No customers found</p>
        </div>
      ) : (
        <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-xs font-medium text-slate-500 uppercase tracking-wide">
              <tr>
                <th className="px-4 py-2 text-left">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleSelectAll}
                    className="rounded"
                  />
                </th>
                <th className="px-4 py-2 text-left">Name</th>
                <th className="px-4 py-2 text-left">Location</th>
                <th className="px-4 py-2 text-left">Current Type</th>
                <th className="px-4 py-2 text-left">Confidence</th>
                <th className="px-4 py-2 text-left">Change Type</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((customer) => (
                <tr
                  key={customer.id}
                  className={`${selected.has(customer.id) ? "bg-blue-50" : "hover:bg-slate-50"} transition-colors`}
                >
                  <td className="px-4 py-2.5">
                    <input
                      type="checkbox"
                      checked={selected.has(customer.id)}
                      onChange={() => toggleSelect(customer.id)}
                      className="rounded"
                    />
                  </td>
                  <td className="px-4 py-2.5">
                    <button
                      onClick={() => navigate(`/customers/${customer.id}`)}
                      className="font-medium text-slate-900 hover:text-blue-600 text-left"
                    >
                      {customer.name}
                    </button>
                    {customer.account_number && (
                      <span className="block text-xs text-slate-400 font-mono">{customer.account_number}</span>
                    )}
                    {customer.is_extension_hidden && (
                      <span className="block text-xs text-orange-500 font-medium">· hidden (contractor)</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-slate-500 text-xs">
                    {[customer.city, customer.state].filter(Boolean).join(", ") || "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    <TypeBadge type={customer.customer_type} />
                  </td>
                  <td className="px-4 py-2.5">
                    <ConfidencePill
                      confidence={customer.classification_confidence}
                      method={customer.classification_method}
                    />
                    {customer.classification_reasoning && (
                      <span
                        className="block text-xs text-slate-400 truncate max-w-[180px]"
                        title={customer.classification_reasoning}
                      >
                        {customer.classification_reasoning}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="relative">
                      <button
                        onClick={() => setOpenDropdown(openDropdown === customer.id ? null : customer.id)}
                        disabled={reclassifying.has(customer.id)}
                        className="inline-flex items-center gap-1.5 rounded border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                      >
                        {reclassifying.has(customer.id) ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <>Change type <ChevronDown className="h-3 w-3" /></>
                        )}
                      </button>
                      {openDropdown === customer.id && (
                        <div className="absolute right-0 z-10 mt-1 w-40 rounded-lg border border-slate-200 bg-white shadow-lg">
                          {CUSTOMER_TYPES.map((t) => (
                            <button
                              key={t.key}
                              onClick={() => reclassify(customer.id, t.key)}
                              className={`w-full flex items-center gap-2 px-3 py-2 text-xs text-left hover:bg-slate-50 ${
                                customer.customer_type === t.key ? "font-semibold text-blue-700" : "text-slate-700"
                              }`}
                            >
                              {customer.customer_type === t.key && <CheckCircle2 className="h-3 w-3 text-blue-600" />}
                              {customer.customer_type !== t.key && <span className="h-3 w-3" />}
                              {t.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 500 && (
            <div className="px-4 py-3 text-xs text-slate-400 bg-slate-50 border-t border-slate-200">
              Showing first 500 results. Use search to narrow down.
            </div>
          )}
        </div>
      )}

      {/* Close dropdown on outside click */}
      {openDropdown && (
        <div
          className="fixed inset-0 z-0"
          onClick={() => setOpenDropdown(null)}
        />
      )}
    </div>
  );
}
