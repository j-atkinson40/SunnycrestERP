import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import apiClient from "@/lib/api-client";
import {
  Loader2,
  Check,
  AlertTriangle,
  HelpCircle,
  CheckCircle2,
  Package,
  Users,
  ArrowRight,
  ChevronLeft,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

// ── Types ────────────────────────────────────────────────────────

interface MatchItem {
  source_name: string;
  matched_name: string | null;
  matched_id: string | null;
  confidence: number;
  status: "auto_matched" | "needs_review" | "no_match";
  alternatives: { id: string; name: string; confidence: number }[];
}

type FilterKey = "all" | "auto_matched" | "needs_review" | "no_match";

// ── Main Component ───────────────────────────────────────────────

export default function ImportMatching() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<"products" | "customers">("products");
  const [productMatches, setProductMatches] = useState<MatchItem[]>([]);
  const [customerMatches, setCustomerMatches] = useState<MatchItem[]>([]);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importProgress, setImportProgress] = useState(0);
  const [sessionId, setSessionId] = useState<string | null>(null);

  useEffect(() => {
    async function fetchMatches() {
      try {
        // Session ID should be stored from the onboarding flow
        const stored = sessionStorage.getItem("import_session_id");
        if (!stored) {
          toast.error("No import session found. Please upload a file first.");
          return;
        }
        setSessionId(stored);

        const [prodRes, custRes] = await Promise.all([
          apiClient.post<{ matches: MatchItem[] }>("/data-import/match-products", {
            session_id: stored,
          }),
          apiClient.post<{ matches: MatchItem[] }>("/data-import/match-customers", {
            session_id: stored,
          }),
        ]);
        setProductMatches(prodRes.data.matches);
        setCustomerMatches(custRes.data.matches);
      } catch {
        toast.error("Failed to load matching data");
      } finally {
        setLoading(false);
      }
    }
    fetchMatches();
  }, []);

  const currentMatches = activeTab === "products" ? productMatches : customerMatches;
  const setCurrentMatches = activeTab === "products" ? setProductMatches : setCustomerMatches;

  const filteredMatches = filter === "all"
    ? currentMatches
    : currentMatches.filter((m) => m.status === filter);

  const counts = {
    all: currentMatches.length,
    auto_matched: currentMatches.filter((m) => m.status === "auto_matched").length,
    needs_review: currentMatches.filter((m) => m.status === "needs_review").length,
    no_match: currentMatches.filter((m) => m.status === "no_match").length,
  };

  const confirmAll = useCallback(() => {
    setCurrentMatches((prev: MatchItem[]) =>
      prev.map((m) =>
        m.status === "auto_matched" ? { ...m, status: "auto_matched" as const } : m,
      ),
    );
    toast.success("All auto-matched items confirmed");
  }, [setCurrentMatches]);

  const updateMatch = useCallback(
    (index: number, matchedId: string, matchedName: string) => {
      const realIndex = filter === "all"
        ? index
        : currentMatches.findIndex((m) => m === filteredMatches[index]);

      setCurrentMatches((prev: MatchItem[]) => {
        const updated = [...prev];
        updated[realIndex] = {
          ...updated[realIndex],
          matched_id: matchedId,
          matched_name: matchedName,
          status: "auto_matched",
          confidence: 1,
        };
        return updated;
      });
    },
    [filter, currentMatches, filteredMatches, setCurrentMatches],
  );

  const handleImport = async () => {
    if (!sessionId) return;
    setImporting(true);
    setImportProgress(0);

    try {
      const confirmedProducts = productMatches
        .filter((m) => m.matched_id)
        .map((m) => ({
          source_name: m.source_name,
          matched_id: m.matched_id,
        }));
      const confirmedCustomers = customerMatches
        .filter((m) => m.matched_id)
        .map((m) => ({
          source_name: m.source_name,
          matched_id: m.matched_id,
        }));

      // Simulated progress
      const progressInterval = setInterval(() => {
        setImportProgress((prev) => Math.min(prev + 10, 90));
      }, 500);

      await apiClient.post("/data-import/execute", {
        session_id: sessionId,
        confirmed_product_matches: confirmedProducts,
        confirmed_customer_matches: confirmedCustomers,
      });

      clearInterval(progressInterval);
      setImportProgress(100);

      toast.success("Import completed successfully");
      setTimeout(() => navigate("/onboarding"), 1500);
    } catch {
      toast.error("Import failed. Please try again.");
    } finally {
      setImporting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-muted-foreground" />
          <p className="mt-3 text-muted-foreground">Matching your data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => navigate("/onboarding")}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <h1 className="text-2xl font-semibold">Import Matching</h1>
          </div>
          <p className="mt-1 text-muted-foreground">
            Review and confirm how your data maps to Bridgeable records.
          </p>
        </div>
        <Button onClick={handleImport} disabled={importing}>
          {importing ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Importing...
            </>
          ) : (
            <>
              Execute Import
              <ArrowRight className="ml-2 h-4 w-4" />
            </>
          )}
        </Button>
      </div>

      {/* Import Progress */}
      {importing && (
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span>Importing data...</span>
                  <span>{importProgress}%</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary transition-all duration-300"
                    style={{ width: `${importProgress}%` }}
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-1 rounded-lg border bg-muted p-1">
        <button
          type="button"
          onClick={() => { setActiveTab("products"); setFilter("all"); }}
          className={cn(
            "flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors",
            activeTab === "products" ? "bg-background shadow" : "hover:bg-background/50",
          )}
        >
          <Package className="h-4 w-4" />
          Products ({productMatches.length})
        </button>
        <button
          type="button"
          onClick={() => { setActiveTab("customers"); setFilter("all"); }}
          className={cn(
            "flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors",
            activeTab === "customers" ? "bg-background shadow" : "hover:bg-background/50",
          )}
        >
          <Users className="h-4 w-4" />
          Customers ({customerMatches.length})
        </button>
      </div>

      {/* Filter + Bulk Actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {(["all", "auto_matched", "needs_review", "no_match"] as FilterKey[]).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={cn(
                "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                filter === f
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80",
              )}
            >
              {f === "all" && `All (${counts.all})`}
              {f === "auto_matched" && `Auto-matched (${counts.auto_matched})`}
              {f === "needs_review" && `Needs Review (${counts.needs_review})`}
              {f === "no_match" && `No Match (${counts.no_match})`}
            </button>
          ))}
        </div>
        {counts.auto_matched > 0 && (
          <Button variant="outline" size="sm" onClick={confirmAll}>
            <CheckCircle2 className="mr-2 h-4 w-4" />
            Confirm All Auto-matched
          </Button>
        )}
      </div>

      {/* Matching Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {activeTab === "products" ? "Product" : "Customer"} Matching
          </CardTitle>
          <CardDescription>
            {filteredMatches.length} items shown
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {/* Header row */}
            <div className="grid grid-cols-12 gap-2 border-b pb-2 text-xs font-medium uppercase text-muted-foreground">
              <div className="col-span-4">Your Name</div>
              <div className="col-span-1 text-center">
                <ArrowRight className="mx-auto h-3 w-3" />
              </div>
              <div className="col-span-4">Bridgeable Match</div>
              <div className="col-span-1 text-center">Confidence</div>
              <div className="col-span-2 text-right">Action</div>
            </div>

            {filteredMatches.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No items in this category.
              </p>
            ) : (
              filteredMatches.map((match, idx) => (
                <div
                  key={`${match.source_name}-${idx}`}
                  className={cn(
                    "grid grid-cols-12 items-center gap-2 rounded-lg border p-3",
                    match.status === "auto_matched" && "border-green-200 bg-green-50/50",
                    match.status === "needs_review" && "border-amber-200 bg-amber-50/50",
                    match.status === "no_match" && "border-red-200 bg-red-50/50",
                  )}
                >
                  {/* Source name */}
                  <div className="col-span-4">
                    <span className="text-sm font-medium">{match.source_name}</span>
                  </div>

                  {/* Arrow */}
                  <div className="col-span-1 text-center">
                    <ArrowRight className="mx-auto h-4 w-4 text-muted-foreground" />
                  </div>

                  {/* Matched name or dropdown */}
                  <div className="col-span-4">
                    {match.status === "auto_matched" && match.matched_name ? (
                      <span className="text-sm">{match.matched_name}</span>
                    ) : match.alternatives.length > 0 ? (
                      <Select
                        value={match.matched_id ?? ""}
                        onValueChange={(val) => {
                          const alt = match.alternatives.find((a) => a.id === val);
                          if (alt) updateMatch(idx, alt.id, alt.name);
                        }}
                      >
                        <SelectTrigger className="h-8 text-xs">
                          <SelectValue placeholder="Select a match..." />
                        </SelectTrigger>
                        <SelectContent>
                          {match.alternatives.map((alt) => (
                            <SelectItem key={alt.id} value={alt.id}>
                              {alt.name} ({Math.round(alt.confidence * 100)}%)
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    ) : (
                      <span className="text-sm italic text-muted-foreground">
                        No matches found
                      </span>
                    )}
                  </div>

                  {/* Confidence */}
                  <div className="col-span-1 text-center">
                    {match.status === "auto_matched" ? (
                      <Badge variant="secondary" className="bg-green-100 text-green-700">
                        {Math.round(match.confidence * 100)}%
                      </Badge>
                    ) : match.status === "needs_review" ? (
                      <Badge variant="secondary" className="bg-amber-100 text-amber-700">
                        {Math.round(match.confidence * 100)}%
                      </Badge>
                    ) : (
                      <Badge variant="secondary" className="bg-red-100 text-red-700">
                        0%
                      </Badge>
                    )}
                  </div>

                  {/* Status icon */}
                  <div className="col-span-2 flex justify-end">
                    {match.status === "auto_matched" && (
                      <div className="flex items-center gap-1 text-green-600">
                        <Check className="h-4 w-4" />
                        <span className="text-xs">Matched</span>
                      </div>
                    )}
                    {match.status === "needs_review" && (
                      <div className="flex items-center gap-1 text-amber-600">
                        <AlertTriangle className="h-4 w-4" />
                        <span className="text-xs">Review</span>
                      </div>
                    )}
                    {match.status === "no_match" && (
                      <div className="flex items-center gap-1 text-red-600">
                        <HelpCircle className="h-4 w-4" />
                        <span className="text-xs">No Match</span>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
