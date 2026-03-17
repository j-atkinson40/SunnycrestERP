import { useEffect, useState, useCallback, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { funeralHomeService } from "@/services/funeral-home-service";
import type { FHCase, FHCaseStatus, FHDirector } from "@/types/funeral-home";
import { CASE_STATUS_LABELS, CASE_STATUS_COLORS, CASE_STATUS_FLOW } from "@/types/funeral-home";

const formatDate = (d?: string) => (d ? new Date(d).toLocaleDateString() : "—");

const BOARD_STATUSES: FHCaseStatus[] = [
  "first_call",
  "in_progress",
  "services_scheduled",
  "services_complete",
  "pending_invoice",
  "invoiced",
];

// ── Case Card (kanban) ────────────────────────────────────────

function CaseCard({ c }: { c: FHCase }) {
  const vaultWarning =
    c.vault_order && c.vault_order.status !== "delivered" && c.service_date
      ? daysBetween(new Date(), new Date(c.service_date)) <= 3
      : false;

  return (
    <Link to={`/cases/${c.id}`} className="block">
      <Card size="sm" className="hover:ring-2 hover:ring-primary/30 transition-all">
        <CardContent className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-xs font-semibold">{c.case_number}</span>
            {c.assigned_director_name && (
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-[10px] font-bold">
                {initials(c.assigned_director_name)}
              </span>
            )}
          </div>
          <p className="text-sm font-medium leading-tight truncate">
            {c.deceased_last_name}, {c.deceased_first_name}
          </p>
          {c.service_date && (
            <p className="text-xs text-muted-foreground">Service: {formatDate(c.service_date)}</p>
          )}
          <div className="flex items-center gap-2">
            {vaultWarning && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 font-medium">
                Vault
              </span>
            )}
            {c.days_since_opened !== undefined && (
              <span className="text-xs text-muted-foreground ml-auto">
                {c.days_since_opened}d open
              </span>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

// ── Kanban Column ─────────────────────────────────────────────

function KanbanColumn({ status, cases }: { status: FHCaseStatus; cases: FHCase[] }) {
  return (
    <div className="flex flex-col min-w-[220px]">
      <div className="mb-2 flex items-center gap-2">
        <h3 className="text-sm font-semibold">{CASE_STATUS_LABELS[status]}</h3>
        <Badge variant="secondary">{cases.length}</Badge>
      </div>
      <div
        className="flex-1 space-y-2 overflow-y-auto rounded-lg bg-muted/30 p-2"
        style={{ maxHeight: "calc(100vh - 280px)" }}
      >
        {cases.length === 0 && (
          <p className="py-6 text-center text-xs text-muted-foreground">No cases</p>
        )}
        {cases.map((c) => (
          <CaseCard key={c.id} c={c} />
        ))}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────

export default function CaseListPage() {
  const navigate = useNavigate();
  const [cases, setCases] = useState<FHCase[]>([]);
  const [boardData, setBoardData] = useState<Record<string, FHCase[]> | null>(null);
  const [directors, setDirectors] = useState<FHDirector[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<"list" | "board">("board");

  // Filters
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [directorFilter, setDirectorFilter] = useState<string>("all");
  const [dispositionFilter, setDispositionFilter] = useState<string>("all");

  const fetchData = useCallback(async () => {
    try {
      const [listResp, boardResp, dirs] = await Promise.all([
        funeralHomeService.listCases(),
        funeralHomeService.getBoard(),
        funeralHomeService.getDirectors(),
      ]);
      setCases(listResp.items);
      setBoardData(boardResp);
      setDirectors(dirs);
    } catch {
      toast.error("Failed to load cases");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60_000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const filteredCases = useMemo(() => {
    let result = cases;
    if (search) {
      const term = search.toLowerCase();
      result = result.filter(
        (c) =>
          c.case_number.toLowerCase().includes(term) ||
          c.deceased_first_name.toLowerCase().includes(term) ||
          c.deceased_last_name.toLowerCase().includes(term),
      );
    }
    if (statusFilter !== "all") {
      result = result.filter((c) => c.status === statusFilter);
    }
    if (directorFilter !== "all") {
      result = result.filter((c) => c.assigned_director_id === directorFilter);
    }
    if (dispositionFilter !== "all") {
      result = result.filter((c) => c.disposition_type === dispositionFilter);
    }
    return result;
  }, [cases, search, statusFilter, directorFilter, dispositionFilter]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading cases...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold">Cases</h1>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border">
            <button
              onClick={() => setView("board")}
              className={cn(
                "px-3 py-1.5 text-sm font-medium rounded-l-lg transition-colors",
                view === "board" ? "bg-primary text-primary-foreground" : "hover:bg-muted",
              )}
            >
              Board
            </button>
            <button
              onClick={() => setView("list")}
              className={cn(
                "px-3 py-1.5 text-sm font-medium rounded-r-lg transition-colors",
                view === "list" ? "bg-primary text-primary-foreground" : "hover:bg-muted",
              )}
            >
              List
            </button>
          </div>
          <Button onClick={() => navigate("/cases/new")}>New First Call</Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <Input
          placeholder="Search by name or case #..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-64"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-md border border-input px-3 py-1.5 text-sm"
        >
          <option value="all">All Statuses</option>
          {CASE_STATUS_FLOW.map((s) => (
            <option key={s} value={s}>
              {CASE_STATUS_LABELS[s]}
            </option>
          ))}
          <option value="cancelled">Cancelled</option>
        </select>
        <select
          value={directorFilter}
          onChange={(e) => setDirectorFilter(e.target.value)}
          className="rounded-md border border-input px-3 py-1.5 text-sm"
        >
          <option value="all">All Directors</option>
          {directors.map((d) => (
            <option key={d.id} value={d.id}>
              {d.first_name} {d.last_name}
            </option>
          ))}
        </select>
        <select
          value={dispositionFilter}
          onChange={(e) => setDispositionFilter(e.target.value)}
          className="rounded-md border border-input px-3 py-1.5 text-sm"
        >
          <option value="all">All Dispositions</option>
          <option value="burial">Burial</option>
          <option value="cremation">Cremation</option>
          <option value="entombment">Entombment</option>
          <option value="donation">Donation</option>
        </select>
      </div>

      {/* Board View */}
      {view === "board" && boardData && (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {BOARD_STATUSES.map((status) => (
            <KanbanColumn
              key={status}
              status={status}
              cases={boardData[status] ?? []}
            />
          ))}
        </div>
      )}

      {/* List View */}
      {view === "list" && (
        <Card>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Case #</TableHead>
                  <TableHead>Deceased Name</TableHead>
                  <TableHead>Service Date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Director</TableHead>
                  <TableHead className="text-right">Days Open</TableHead>
                  <TableHead>Vault</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredCases.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                      No cases found.
                    </TableCell>
                  </TableRow>
                )}
                {filteredCases.map((c) => (
                  <TableRow
                    key={c.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/cases/${c.id}`)}
                  >
                    <TableCell className="font-mono text-xs font-semibold">
                      {c.case_number}
                    </TableCell>
                    <TableCell className="font-medium">
                      {c.deceased_last_name}, {c.deceased_first_name}
                    </TableCell>
                    <TableCell>{formatDate(c.service_date)}</TableCell>
                    <TableCell>
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                          CASE_STATUS_COLORS[c.status],
                        )}
                      >
                        {CASE_STATUS_LABELS[c.status]}
                      </span>
                    </TableCell>
                    <TableCell>{c.assigned_director_name ?? "—"}</TableCell>
                    <TableCell className="text-right">{c.days_since_opened ?? "—"}</TableCell>
                    <TableCell>
                      {c.vault_order ? (
                        <span className="text-xs text-muted-foreground">
                          {c.vault_order.status}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────

function initials(name: string) {
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

function daysBetween(a: Date, b: Date) {
  return Math.ceil((b.getTime() - a.getTime()) / (1000 * 60 * 60 * 24));
}
