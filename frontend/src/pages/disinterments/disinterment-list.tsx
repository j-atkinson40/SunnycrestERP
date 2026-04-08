import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";
import {
  Plus,
  Search,
  ChevronLeft,
  ChevronRight,
  Skull,
  Calendar,
  FileSignature,
  Clock,
  CheckCircle2,
  XCircle,
  ClipboardList,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface CaseListItem {
  id: string;
  case_number: string;
  decedent_name: string;
  status: string;
  cemetery_name: string | null;
  funeral_home_name: string | null;
  scheduled_date: string | null;
  created_at: string | null;
}

interface PaginatedResponse {
  items: CaseListItem[];
  total: number;
  page: number;
  per_page: number;
}

/* ------------------------------------------------------------------ */
/* Status config                                                       */
/* ------------------------------------------------------------------ */

const STATUS_TABS = [
  { key: "all", label: "All" },
  { key: "intake", label: "Intake" },
  { key: "quoted", label: "Quoted" },
  { key: "quote_accepted", label: "Accepted" },
  { key: "signatures_pending", label: "Signatures" },
  { key: "signatures_complete", label: "Sig. Complete" },
  { key: "scheduled", label: "Scheduled" },
  { key: "complete", label: "Complete" },
  { key: "cancelled", label: "Cancelled" },
] as const;

const STATUS_COLORS: Record<string, string> = {
  intake: "bg-blue-50 text-blue-700 border-blue-200",
  quoted: "bg-amber-50 text-amber-700 border-amber-200",
  quote_accepted: "bg-orange-50 text-orange-700 border-orange-200",
  signatures_pending: "bg-purple-50 text-purple-700 border-purple-200",
  signatures_complete: "bg-indigo-50 text-indigo-700 border-indigo-200",
  scheduled: "bg-emerald-50 text-emerald-700 border-emerald-200",
  complete: "bg-green-50 text-green-700 border-green-200",
  cancelled: "bg-gray-50 text-gray-500 border-gray-200",
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  intake: <ClipboardList className="h-3.5 w-3.5" />,
  quoted: <Clock className="h-3.5 w-3.5" />,
  quote_accepted: <CheckCircle2 className="h-3.5 w-3.5" />,
  signatures_pending: <FileSignature className="h-3.5 w-3.5" />,
  signatures_complete: <FileSignature className="h-3.5 w-3.5" />,
  scheduled: <Calendar className="h-3.5 w-3.5" />,
  complete: <CheckCircle2 className="h-3.5 w-3.5" />,
  cancelled: <XCircle className="h-3.5 w-3.5" />,
};

function statusLabel(s: string) {
  return s
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function DisintermentListPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState<PaginatedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(searchParams.get("search") || "");
  const [creating, setCreating] = useState(false);

  const activeStatus = searchParams.get("status") || "all";
  const page = parseInt(searchParams.get("page") || "1", 10);
  const perPage = 20;

  const fetchCases = () => {
    setLoading(true);
    const params: Record<string, string | number> = { page, per_page: perPage };
    if (activeStatus !== "all") params.status = activeStatus;
    if (search.trim()) params.search = search.trim();

    apiClient
      .get("/disinterments", { params })
      .then((r: { data: PaginatedResponse }) => setData(r.data))
      .catch(() => toast.error("Failed to load disinterment cases"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchCases();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeStatus, page]);

  const handleSearch = () => {
    setSearchParams((prev) => {
      prev.set("page", "1");
      if (search.trim()) prev.set("search", search.trim());
      else prev.delete("search");
      return prev;
    });
    fetchCases();
  };

  const setTab = (status: string) => {
    setSearchParams((prev) => {
      if (status === "all") prev.delete("status");
      else prev.set("status", status);
      prev.set("page", "1");
      return prev;
    });
  };

  const handleCreateCase = async () => {
    setCreating(true);
    try {
      const r = await apiClient.post("/disinterments");
      const c = r.data;
      // Copy intake link to clipboard
      const intakeUrl = `${window.location.origin}/intake/disinterment/${c.intake_token}`;
      await navigator.clipboard.writeText(intakeUrl);
      toast.success("Case created — intake link copied to clipboard");
      // Navigate to the new case
      window.location.href = `/disinterments/${c.id}`;
    } catch {
      toast.error("Failed to create case");
    } finally {
      setCreating(false);
    }
  };

  const totalPages = data ? Math.ceil(data.total / perPage) : 0;

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Disinterment Cases</h1>
          <p className="text-muted-foreground">
            Manage disinterment cases through the 5-stage pipeline
          </p>
        </div>
        <Button onClick={handleCreateCase} disabled={creating}>
          <Plus className="mr-2 h-4 w-4" />
          {creating ? "Creating..." : "New Disinterment"}
        </Button>
      </div>

      {/* Status tabs */}
      <div className="flex flex-wrap gap-1 border-b pb-2">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setTab(tab.key)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              activeStatus === tab.key
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search by decedent name, case number, cemetery..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
        </div>
        <Button variant="outline" onClick={handleSearch}>
          Search
        </Button>
      </div>

      {/* Table */}
      {loading ? (
        <div className="py-12 text-center text-muted-foreground">Loading...</div>
      ) : !data || data.items.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Skull className="mx-auto mb-4 h-12 w-12 text-muted-foreground/40" />
            <p className="text-muted-foreground">
              {activeStatus !== "all"
                ? `No cases with status "${statusLabel(activeStatus)}"`
                : "No disinterment cases yet. Create your first case to get started."}
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="rounded-md border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="p-3 text-left font-medium">Case #</th>
                  <th className="p-3 text-left font-medium">Decedent</th>
                  <th className="p-3 text-left font-medium">Status</th>
                  <th className="p-3 text-left font-medium">Cemetery</th>
                  <th className="p-3 text-left font-medium">Funeral Home</th>
                  <th className="p-3 text-left font-medium">Scheduled</th>
                  <th className="p-3 text-left font-medium">Created</th>
                  <th className="p-3 w-10"></th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((c) => (
                  <tr
                    key={c.id}
                    className="border-b last:border-0 hover:bg-muted/30 cursor-pointer"
                    onClick={() => (window.location.href = `/disinterments/${c.id}`)}
                  >
                    <td className="p-3">
                      <span className="font-mono text-xs font-medium">
                        {c.case_number}
                      </span>
                    </td>
                    <td className="p-3 font-medium">{c.decedent_name}</td>
                    <td className="p-3">
                      <Badge
                        variant="outline"
                        className={`text-xs gap-1 ${STATUS_COLORS[c.status] || ""}`}
                      >
                        {STATUS_ICONS[c.status]}
                        {statusLabel(c.status)}
                      </Badge>
                    </td>
                    <td className="p-3 text-muted-foreground">
                      {c.cemetery_name || "—"}
                    </td>
                    <td className="p-3 text-muted-foreground">
                      {c.funeral_home_name || "—"}
                    </td>
                    <td className="p-3 text-muted-foreground">
                      {c.scheduled_date
                        ? new Date(c.scheduled_date).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="p-3 text-muted-foreground">
                      {c.created_at
                        ? new Date(c.created_at).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="p-3">
                      <Link
                        to={`/disinterments/${c.id}`}
                        className="text-primary hover:underline text-xs"
                        onClick={(e) => e.stopPropagation()}
                      >
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                {data.total} case{data.total !== 1 ? "s" : ""} total
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() =>
                    setSearchParams((p) => {
                      p.set("page", String(page - 1));
                      return p;
                    })
                  }
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-sm">
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() =>
                    setSearchParams((p) => {
                      p.set("page", String(page + 1));
                      return p;
                    })
                  }
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
