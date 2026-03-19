import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Check,
  ChevronDown,
  ChevronUp,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Star,
  Phone,
  Trash2,
  ArrowRight,
  Link2,
  X,
  AlertTriangle,
} from "lucide-react";
import type {
  DirectoryEntry,
  PlatformMatch,
  DirectorySelection,
  ManualCustomer,
} from "@/types/funeral-home-directory";
import * as directoryService from "@/services/funeral-home-directory-service";

// ── Local Storage Keys ───────────────────────────────────────────

const LS_KEY_STEP = "fh-onboard-step";
const LS_KEY_MATCH_DECISIONS = "fh-onboard-match-decisions";
const LS_KEY_SELECTED = "fh-onboard-selected";
const LS_KEY_INVITES = "fh-onboard-invites";
const LS_KEY_MANUAL = "fh-onboard-manual";

// ── Helper: safe JSON parse ──────────────────────────────────────

function safeParse<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

// ── Completion stats ─────────────────────────────────────────────

interface CompletionStats {
  connected: number;
  fromDirectory: number;
  manual: number;
  invited: number;
  total: number;
}

// ── Main Component ───────────────────────────────────────────────

export default function FuneralHomeCustomersWizard() {
  const navigate = useNavigate();

  // Wizard step (1 = Connect, 2 = Discover, 3 = Add Missing, 4 = Complete)
  const [currentStep, setCurrentStep] = useState<number>(() =>
    safeParse(LS_KEY_STEP, 1)
  );

  // Platform matches (Step 1)
  const [platformMatches, setPlatformMatches] = useState<PlatformMatch[]>([]);
  const [matchDecisions, setMatchDecisions] = useState<
    Record<string, "connected" | "skipped">
  >(() => safeParse(LS_KEY_MATCH_DECISIONS, {}));
  const [matchesLoading, setMatchesLoading] = useState(true);

  // Directory entries (Step 2)
  const [entries, setEntries] = useState<DirectoryEntry[]>([]);
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(safeParse<string[]>(LS_KEY_SELECTED, []))
  );
  const [invites, setInvites] = useState<Set<string>>(
    () => new Set(safeParse<string[]>(LS_KEY_INVITES, []))
  );
  const [directoryLoading, setDirectoryLoading] = useState(false);
  const [directoryFetched, setDirectoryFetched] = useState(false);
  const [search, setSearch] = useState("");
  const [cityFilter, setCityFilter] = useState("all");
  const [refreshing, setRefreshing] = useState(false);

  // Manual entries (Step 3)
  const [manualRows, setManualRows] = useState<ManualCustomer[]>(() =>
    safeParse(LS_KEY_MANUAL, [{ name: "", city: "", phone: "", invite: false }])
  );

  // Submission
  const [submitting, setSubmitting] = useState(false);
  const [completionStats, setCompletionStats] =
    useState<CompletionStats | null>(null);

  // ── Persist to localStorage on change ──────────────────────────

  useEffect(() => {
    localStorage.setItem(LS_KEY_STEP, JSON.stringify(currentStep));
  }, [currentStep]);

  useEffect(() => {
    localStorage.setItem(LS_KEY_MATCH_DECISIONS, JSON.stringify(matchDecisions));
  }, [matchDecisions]);

  useEffect(() => {
    localStorage.setItem(LS_KEY_SELECTED, JSON.stringify([...selected]));
  }, [selected]);

  useEffect(() => {
    localStorage.setItem(LS_KEY_INVITES, JSON.stringify([...invites]));
  }, [invites]);

  useEffect(() => {
    localStorage.setItem(LS_KEY_MANUAL, JSON.stringify(manualRows));
  }, [manualRows]);

  // ── Fetch platform matches on mount ────────────────────────────

  useEffect(() => {
    directoryService
      .getPlatformMatches()
      .then(setPlatformMatches)
      .catch(() => toast.error("Failed to load platform matches"))
      .finally(() => setMatchesLoading(false));
  }, []);

  // ── Fetch directory when Step 2 becomes active ─────────────────

  useEffect(() => {
    if (currentStep === 2 && !directoryFetched) {
      setDirectoryLoading(true);
      directoryService
        .getDirectory()
        .then((data) => {
          setEntries(data);
          setDirectoryFetched(true);
        })
        .catch(() => toast.error("Failed to load directory"))
        .finally(() => setDirectoryLoading(false));
    }
  }, [currentStep, directoryFetched]);

  // ── Refresh directory ──────────────────────────────────────────

  const handleRefreshDirectory = useCallback(async () => {
    setRefreshing(true);
    try {
      const data = await directoryService.refreshDirectory();
      setEntries(data);
      toast.success("Directory refreshed");
    } catch {
      toast.error("Failed to refresh directory");
    } finally {
      setRefreshing(false);
    }
  }, []);

  // ── Step 1 handlers ────────────────────────────────────────────

  const handleConnectMatch = useCallback((id: string) => {
    setMatchDecisions((prev) => ({ ...prev, [id]: "connected" }));
  }, []);

  const handleSkipMatch = useCallback((id: string) => {
    setMatchDecisions((prev) => ({ ...prev, [id]: "skipped" }));
  }, []);

  const undoMatchDecision = useCallback((id: string) => {
    setMatchDecisions((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }, []);

  const step1Connected = useMemo(
    () =>
      Object.values(matchDecisions).filter((v) => v === "connected").length,
    [matchDecisions]
  );
  const step1Skipped = useMemo(
    () =>
      Object.values(matchDecisions).filter((v) => v === "skipped").length,
    [matchDecisions]
  );

  // ── Step 2 handlers ────────────────────────────────────────────

  const toggleSelect = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
        setInvites((inv) => {
          const n = new Set(inv);
          n.delete(id);
          return n;
        });
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const setInvite = useCallback((id: string, val: boolean) => {
    setInvites((prev) => {
      const next = new Set(prev);
      if (val) next.add(id);
      else next.delete(id);
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    const ids = filteredEntries.map((e) => e.id);
    setSelected(new Set(ids));
  }, []);

  const selectNone = useCallback(() => {
    setSelected(new Set());
    setInvites(new Set());
  }, []);

  const inviteAllSelected = useCallback(() => {
    setInvites(new Set(selected));
  }, [selected]);

  // Filter + sort entries
  const cities = useMemo(() => {
    const set = new Set<string>();
    entries.forEach((e) => {
      if (e.city) set.add(e.city);
    });
    return [...set].sort();
  }, [entries]);

  const filteredEntries = useMemo(() => {
    let result = entries;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (e) =>
          e.name.toLowerCase().includes(q) ||
          e.address?.toLowerCase().includes(q) ||
          e.phone?.includes(q)
      );
    }
    if (cityFilter !== "all") {
      result = result.filter((e) => e.city === cityFilter);
    }
    return result;
  }, [entries, search, cityFilter]);

  // ── Step 3 handlers ────────────────────────────────────────────

  const updateManualRow = useCallback(
    (index: number, field: keyof ManualCustomer, value: string | boolean) => {
      setManualRows((prev) =>
        prev.map((row, i) =>
          i === index ? { ...row, [field]: value } : row
        )
      );
    },
    []
  );

  const addManualRow = useCallback(() => {
    setManualRows((prev) => [
      ...prev,
      { name: "", city: "", phone: "", invite: false },
    ]);
  }, []);

  const removeManualRow = useCallback((index: number) => {
    setManualRows((prev) => {
      if (prev.length <= 1) return [{ name: "", city: "", phone: "", invite: false }];
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  // Duplicate detection for manual entries
  const getDuplicateWarning = useCallback(
    (name: string): string | null => {
      if (!name.trim()) return null;
      const lower = name.trim().toLowerCase();

      const matchedPlatform = platformMatches.find(
        (m) => m.name.toLowerCase() === lower
      );
      if (matchedPlatform) return "Already on platform \u2014 connect in Step 1";

      const matchedDirectory = entries.find(
        (e) => e.name.toLowerCase() === lower
      );
      if (matchedDirectory) return "In your Step 2 list \u2014 select it there";

      return null;
    },
    [platformMatches, entries]
  );

  // ── Submit all ─────────────────────────────────────────────────

  const handleComplete = useCallback(async () => {
    setSubmitting(true);
    try {
      // Build directory selections
      const directorySelections: DirectorySelection[] = entries.map(
        (entry) => ({
          directory_entry_id: entry.id,
          action: selected.has(entry.id)
            ? ("added_as_customer" as const)
            : ("skipped" as const),
          invite: invites.has(entry.id),
        })
      );

      // Filter valid manual entries
      const validManual = manualRows.filter((r) => r.name.trim());

      // Send requests
      const [selResult, manualResult] = await Promise.all([
        directorySelections.length > 0
          ? directoryService.recordSelections(directorySelections)
          : Promise.resolve({
              created_customers: 0,
              invitations_sent: 0,
              skipped: 0,
            }),
        validManual.length > 0
          ? directoryService.addManualCustomers(validManual)
          : Promise.resolve({ created_customers: 0 }),
      ]);

      const stats: CompletionStats = {
        connected: step1Connected,
        fromDirectory: selResult.created_customers,
        manual: manualResult.created_customers,
        invited:
          selResult.invitations_sent +
          validManual.filter((r) => r.invite).length,
        total:
          step1Connected +
          selResult.created_customers +
          manualResult.created_customers,
      };

      setCompletionStats(stats);
      setCurrentStep(4);

      // Clear localStorage
      [
        LS_KEY_STEP,
        LS_KEY_MATCH_DECISIONS,
        LS_KEY_SELECTED,
        LS_KEY_INVITES,
        LS_KEY_MANUAL,
      ].forEach((k) => localStorage.removeItem(k));

      toast.success("Funeral home customers saved!");
    } catch {
      toast.error("Failed to save. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }, [
    entries,
    selected,
    invites,
    manualRows,
    step1Connected,
  ]);

  const handleSaveLater = useCallback(() => {
    toast.success("Progress saved. You can come back anytime.");
    navigate("/onboarding");
  }, [navigate]);

  const handleContinue = useCallback(() => {
    navigate("/onboarding");
  }, [navigate]);

  // ── Completion screen ──────────────────────────────────────────

  if (completionStats) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <CompletionSummary stats={completionStats} onContinue={handleContinue} />
      </div>
    );
  }

  // ── Main render ────────────────────────────────────────────────

  return (
    <div className="mx-auto max-w-4xl p-6">
      {/* Page header */}
      <h1 className="text-2xl font-bold">Add Your Funeral Home Customers</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Connect, discover, and add the funeral homes you deliver to
      </p>

      {/* Step indicators */}
      <div className="mt-4 flex items-center gap-4">
        {[
          { num: 1, label: "Connect" },
          { num: 2, label: "Discover" },
          { num: 3, label: "Add Missing" },
        ].map((step) => (
          <div
            key={step.num}
            className={cn(
              "flex items-center gap-2",
              currentStep > step.num
                ? "text-green-600"
                : currentStep === step.num
                  ? "font-medium text-primary"
                  : "text-muted-foreground"
            )}
          >
            {currentStep > step.num ? (
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-green-100">
                <Check className="h-3.5 w-3.5 text-green-600" />
              </div>
            ) : (
              <div
                className={cn(
                  "flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold",
                  currentStep === step.num
                    ? "bg-primary text-white"
                    : "bg-muted text-muted-foreground"
                )}
              >
                {step.num}
              </div>
            )}
            <span className="text-sm">{step.label}</span>
          </div>
        ))}
      </div>

      {/* Sections */}
      <div className="mt-8 space-y-4">
        {/* Step 1 — Connect */}
        <SectionWrapper
          stepNum={1}
          title="Connect to Platform Funeral Homes"
          currentStep={currentStep}
          onExpand={() => setCurrentStep(1)}
          completedSummary={`${step1Connected} connected, ${step1Skipped} skipped`}
        >
          <ConnectSection
            platformMatches={platformMatches}
            matchDecisions={matchDecisions}
            loading={matchesLoading}
            onConnect={handleConnectMatch}
            onSkip={handleSkipMatch}
            onUndo={undoMatchDecision}
            onComplete={() => setCurrentStep(2)}
          />
        </SectionWrapper>

        {/* Step 2 — Discover */}
        <SectionWrapper
          stepNum={2}
          title="Discover Funeral Homes in Your Area"
          currentStep={currentStep}
          onExpand={() => setCurrentStep(2)}
          completedSummary={`${selected.size} selected, ${invites.size} to invite`}
        >
          <DiscoverSection
            entries={filteredEntries}
            allEntries={entries}
            selected={selected}
            invites={invites}
            loading={directoryLoading}
            search={search}
            onSearchChange={setSearch}
            cityFilter={cityFilter}
            onCityFilterChange={setCityFilter}
            cities={cities}
            refreshing={refreshing}
            onRefresh={handleRefreshDirectory}
            onToggleSelect={toggleSelect}
            onSetInvite={setInvite}
            onSelectAll={selectAll}
            onSelectNone={selectNone}
            onInviteAllSelected={inviteAllSelected}
            onComplete={() => setCurrentStep(3)}
          />
        </SectionWrapper>

        {/* Step 3 — Add Missing */}
        <SectionWrapper
          stepNum={3}
          title="Add Missing Funeral Homes"
          currentStep={currentStep}
          onExpand={() => setCurrentStep(3)}
          completedSummary={`${manualRows.filter((r) => r.name.trim()).length} added manually`}
        >
          <AddMissingSection
            rows={manualRows}
            onUpdateRow={updateManualRow}
            onAddRow={addManualRow}
            onRemoveRow={removeManualRow}
            getDuplicateWarning={getDuplicateWarning}
          />
        </SectionWrapper>
      </div>

      {/* Footer */}
      <div className="mt-8 flex justify-between border-t pt-4">
        <Button variant="ghost" onClick={handleSaveLater}>
          Save and finish later
        </Button>
        <Button
          className="bg-green-600 text-white hover:bg-green-700"
          onClick={handleComplete}
          disabled={submitting}
        >
          {submitting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>All done &mdash; save and continue <ArrowRight className="ml-2 h-4 w-4" /></>
          )}
        </Button>
      </div>
    </div>
  );
}

// ── Section Wrapper ──────────────────────────────────────────────

function SectionWrapper({
  stepNum,
  title,
  currentStep,
  onExpand,
  completedSummary,
  children,
}: {
  stepNum: number;
  title: string;
  currentStep: number;
  onExpand: () => void;
  completedSummary: string;
  children: React.ReactNode;
}) {
  const isExpanded = currentStep === stepNum;
  const isCompleted = currentStep > stepNum;

  return (
    <div className="rounded-lg border bg-white">
      <button
        type="button"
        className="flex w-full items-center justify-between px-5 py-4 text-left"
        onClick={onExpand}
      >
        <div className="flex items-center gap-3">
          {isCompleted ? (
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-green-100">
              <Check className="h-3.5 w-3.5 text-green-600" />
            </div>
          ) : (
            <div
              className={cn(
                "flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold",
                isExpanded
                  ? "bg-primary text-white"
                  : "bg-muted text-muted-foreground"
              )}
            >
              {stepNum}
            </div>
          )}
          <span className={cn("font-medium", isCompleted && "text-green-700")}>
            {isCompleted
              ? `Step ${stepNum} Complete \u2014 ${completedSummary}`
              : title}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {isCompleted && (
            <span className="text-sm text-muted-foreground">Edit</span>
          )}
          {isExpanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
      </button>

      {isExpanded && <div className="border-t px-5 pb-5 pt-4">{children}</div>}
    </div>
  );
}

// ── Step 1: Connect Section ──────────────────────────────────────

function ConnectSection({
  platformMatches,
  matchDecisions,
  loading,
  onConnect,
  onSkip,
  onUndo,
  onComplete,
}: {
  platformMatches: PlatformMatch[];
  matchDecisions: Record<string, "connected" | "skipped">;
  loading: boolean;
  onConnect: (id: string) => void;
  onSkip: (id: string) => void;
  onUndo: (id: string) => void;
  onComplete: () => void;
}) {
  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-16 animate-pulse rounded-lg border bg-muted"
          />
        ))}
      </div>
    );
  }

  if (platformMatches.length === 0) {
    return (
      <div className="py-8 text-center">
        <Link2 className="mx-auto h-10 w-10 text-muted-foreground" />
        <p className="mt-3 text-sm text-muted-foreground">
          No funeral homes in your area are on the platform yet.
        </p>
        <Button className="mt-4" onClick={onComplete}>
          Continue to discover nearby funeral homes <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    );
  }

  const undecided = platformMatches.filter((m) => !matchDecisions[m.id]);
  const decided = platformMatches.filter((m) => matchDecisions[m.id]);

  return (
    <div className="space-y-4">
      {/* Undecided matches */}
      {undecided.length > 0 && (
        <div className="space-y-3">
          {undecided.map((match) => (
            <div
              key={match.id}
              className="flex items-center justify-between rounded-lg border p-4"
            >
              <div>
                <p className="font-medium">{match.name}</p>
                <p className="text-sm text-muted-foreground">
                  Already on the platform
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onSkip(match.id)}
                >
                  Not my customer
                </Button>
                <Button size="sm" onClick={() => onConnect(match.id)}>
                  Connect
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Already decided */}
      {decided.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Decided
          </p>
          {decided.map((match) => {
            const decision = matchDecisions[match.id];
            return (
              <div
                key={match.id}
                className={cn(
                  "flex items-center justify-between rounded-lg border p-3",
                  decision === "connected"
                    ? "border-l-4 border-l-green-500 bg-green-50/50"
                    : "bg-gray-50"
                )}
              >
                <div className="flex items-center gap-2">
                  {decision === "connected" ? (
                    <Check className="h-4 w-4 text-green-600" />
                  ) : (
                    <X className="h-4 w-4 text-muted-foreground" />
                  )}
                  <span
                    className={cn(
                      "text-sm",
                      decision === "skipped" && "text-muted-foreground"
                    )}
                  >
                    {match.name}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {decision === "connected" ? "Connected" : "Skipped"}
                  </span>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-xs"
                  onClick={() => onUndo(match.id)}
                >
                  Undo
                </Button>
              </div>
            );
          })}
        </div>
      )}

      {/* Complete button */}
      <div className="pt-2">
        <Button onClick={onComplete} className="w-full">
          Mark complete and continue{" "}
          <ChevronDown className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

// ── Step 2: Discover Section ─────────────────────────────────────

function DiscoverSection({
  entries,
  allEntries,
  selected,
  invites,
  loading,
  search,
  onSearchChange,
  cityFilter,
  onCityFilterChange,
  cities,
  refreshing,
  onRefresh,
  onToggleSelect,
  onSetInvite,
  onSelectAll,
  onSelectNone,
  onInviteAllSelected,
  onComplete,
}: {
  entries: DirectoryEntry[];
  allEntries: DirectoryEntry[];
  selected: Set<string>;
  invites: Set<string>;
  loading: boolean;
  search: string;
  onSearchChange: (v: string) => void;
  cityFilter: string;
  onCityFilterChange: (v: string) => void;
  cities: string[];
  refreshing: boolean;
  onRefresh: () => void;
  onToggleSelect: (id: string) => void;
  onSetInvite: (id: string, val: boolean) => void;
  onSelectAll: () => void;
  onSelectNone: () => void;
  onInviteAllSelected: () => void;
  onComplete: () => void;
}) {
  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-24 animate-pulse rounded-lg border bg-muted"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search funeral homes..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9"
          />
        </div>
        <select
          value={cityFilter}
          onChange={(e) => onCityFilterChange(e.target.value)}
          className="h-9 rounded-md border border-input bg-background px-3 text-sm"
        >
          <option value="all">All cities</option>
          {cities.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <Button
          size="sm"
          variant="outline"
          onClick={onRefresh}
          disabled={refreshing}
        >
          <RefreshCw
            className={cn("mr-1 h-3.5 w-3.5", refreshing && "animate-spin")}
          />
          Refresh
        </Button>
      </div>

      {/* Batch controls */}
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <Button size="sm" variant="ghost" onClick={onSelectAll}>
          Select all
        </Button>
        <Button size="sm" variant="ghost" onClick={onSelectNone}>
          Select none
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={onInviteAllSelected}
          disabled={selected.size === 0}
        >
          Invite all selected
        </Button>
        <span className="ml-auto text-muted-foreground">
          {selected.size} selected &middot; {invites.size} to invite
        </span>
      </div>

      {/* Card grid */}
      {entries.length === 0 ? (
        <div className="py-8 text-center text-sm text-muted-foreground">
          {allEntries.length === 0
            ? "No funeral homes found in your area. Try refreshing or add them manually in Step 3."
            : "No results match your search."}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {entries.map((entry) => (
            <DirectoryCard
              key={entry.id}
              entry={entry}
              isSelected={selected.has(entry.id)}
              isInvited={invites.has(entry.id)}
              onToggleSelect={() => onToggleSelect(entry.id)}
              onSetInvite={(val) => onSetInvite(entry.id, val)}
            />
          ))}
        </div>
      )}

      {/* Complete button */}
      <div className="pt-2">
        <Button onClick={onComplete} className="w-full">
          Mark complete and continue{" "}
          <ChevronDown className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

// ── Directory Entry Card ─────────────────────────────────────────

function DirectoryCard({
  entry,
  isSelected,
  isInvited,
  onToggleSelect,
  onSetInvite,
}: {
  entry: DirectoryEntry;
  isSelected: boolean;
  isInvited: boolean;
  onToggleSelect: () => void;
  onSetInvite: (val: boolean) => void;
}) {
  return (
    <div
      onClick={onToggleSelect}
      className={cn(
        "cursor-pointer rounded-lg border p-4 transition-all",
        isSelected
          ? "border-l-4 border-l-teal-500 bg-teal-50/50"
          : "hover:bg-gray-50"
      )}
    >
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={onToggleSelect}
          onClick={(e) => e.stopPropagation()}
          className="mt-1 h-4 w-4 rounded border-gray-300"
        />
        <div className="min-w-0 flex-1">
          <p className="font-medium">{entry.name}</p>
          {entry.address && (
            <p className="text-sm text-muted-foreground">{entry.address}</p>
          )}
          <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            {entry.phone && (
              <span className="flex items-center gap-1">
                <Phone className="h-3 w-3" />
                {entry.phone}
              </span>
            )}
            {entry.google_rating != null && (
              <span className="flex items-center gap-1">
                <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                {entry.google_rating}
                {entry.google_review_count != null && (
                  <span>({entry.google_review_count} reviews)</span>
                )}
              </span>
            )}
          </div>

          {/* Invite toggle — only shown when selected */}
          {isSelected && (
            <div
              className="mt-2 flex items-center gap-3 text-sm"
              onClick={(e) => e.stopPropagation()}
            >
              <span className="text-muted-foreground">
                Invite to platform:
              </span>
              <label className="flex items-center gap-1">
                <input
                  type="radio"
                  name={`invite-${entry.id}`}
                  checked={isInvited}
                  onChange={() => onSetInvite(true)}
                />
                Yes
              </label>
              <label className="flex items-center gap-1">
                <input
                  type="radio"
                  name={`invite-${entry.id}`}
                  checked={!isInvited}
                  onChange={() => onSetInvite(false)}
                />
                No
              </label>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Step 3: Add Missing Section ──────────────────────────────────

function AddMissingSection({
  rows,
  onUpdateRow,
  onAddRow,
  onRemoveRow,
  getDuplicateWarning,
}: {
  rows: ManualCustomer[];
  onUpdateRow: (
    index: number,
    field: keyof ManualCustomer,
    value: string | boolean
  ) => void;
  onAddRow: () => void;
  onRemoveRow: (index: number) => void;
  getDuplicateWarning: (name: string) => string | null;
}) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Add any funeral homes not found above. They will be created as customers
        in your account.
      </p>

      {/* Table header */}
      <div className="hidden sm:grid sm:grid-cols-[1fr_1fr_1fr_80px_40px] sm:gap-2 sm:px-1 sm:text-xs sm:font-medium sm:uppercase sm:tracking-wide sm:text-muted-foreground">
        <span>Name</span>
        <span>City</span>
        <span>Phone</span>
        <span>Invite</span>
        <span />
      </div>

      {/* Rows */}
      <div className="space-y-2">
        {rows.map((row, index) => {
          const warning = getDuplicateWarning(row.name);
          return (
            <div key={index}>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_1fr_1fr_80px_40px]">
                <Input
                  placeholder="Funeral home name"
                  value={row.name}
                  onChange={(e) =>
                    onUpdateRow(index, "name", e.target.value)
                  }
                />
                <Input
                  placeholder="City"
                  value={row.city}
                  onChange={(e) =>
                    onUpdateRow(index, "city", e.target.value)
                  }
                />
                <Input
                  placeholder="Phone"
                  value={row.phone}
                  onChange={(e) =>
                    onUpdateRow(index, "phone", e.target.value)
                  }
                />
                <div className="flex items-center justify-center">
                  <input
                    type="checkbox"
                    checked={row.invite}
                    onChange={(e) =>
                      onUpdateRow(index, "invite", e.target.checked)
                    }
                    className="h-4 w-4 rounded border-gray-300"
                  />
                </div>
                <div className="flex items-center justify-center">
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                    onClick={() => onRemoveRow(index)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
              {warning && (
                <div className="mt-1 flex items-center gap-1 px-1 text-xs text-amber-600">
                  <AlertTriangle className="h-3 w-3" />
                  {warning}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Add row button */}
      <Button
        size="sm"
        variant="ghost"
        className="text-sm"
        onClick={onAddRow}
      >
        <Plus className="mr-1 h-3.5 w-3.5" />
        Add another
      </Button>
    </div>
  );
}

// ── Completion Summary ───────────────────────────────────────────

function CompletionSummary({
  stats,
  onContinue,
}: {
  stats: CompletionStats;
  onContinue: () => void;
}) {
  return (
    <div className="mx-auto max-w-md py-12 text-center">
      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
        <Check className="h-8 w-8 text-green-600" />
      </div>
      <h2 className="text-xl font-semibold">Funeral home customers added</h2>

      <div className="mt-6 space-y-2 text-sm">
        <div className="flex justify-between">
          <span>Connected to platform:</span>
          <span>{stats.connected}</span>
        </div>
        <div className="flex justify-between">
          <span>Added from your area:</span>
          <span>{stats.fromDirectory}</span>
        </div>
        <div className="flex justify-between">
          <span>Added manually:</span>
          <span>{stats.manual}</span>
        </div>
        <hr />
        <div className="flex justify-between font-semibold">
          <span>Total funeral homes:</span>
          <span>{stats.total}</span>
        </div>
        <div className="flex justify-between text-muted-foreground">
          <span>Invitations sent:</span>
          <span>{stats.invited}</span>
        </div>
      </div>

      <Button className="mt-8" onClick={onContinue}>
        Continue to next step <ArrowRight className="ml-2 h-4 w-4" />
      </Button>
    </div>
  );
}
