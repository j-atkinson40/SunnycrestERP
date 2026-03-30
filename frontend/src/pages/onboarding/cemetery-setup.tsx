/**
 * Cemetery Setup Wizard — 4-step onboarding flow for manufacturer cemeteries.
 *
 * Step 0 — Platform:    Connect to cemetery tenants already on Bridgeable.
 * Step 1 — Discover:   Browse Google Places results, select cemeteries to add.
 * Step 2 — Add Missing: Manually enter cemeteries not found in the search.
 * Step 3 — Complete:   Configure equipment settings per cemetery, then submit.
 */

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { ContextualExplanation } from "@/components/contextual-explanation";
import { CemeteryInlineAddDemo } from "@/components/cemetery-inline-add-demo";
import {
  Check,
  ChevronDown,
  ChevronUp,
  Link2,
  Loader2,
  MapPin,
  Plus,
  RefreshCw,
  Star,
  Trash2,
  ArrowRight,
  X,
} from "lucide-react";
import type {
  CemeteryDirectoryEntry,
  CemeteryEquipmentSettings,
  CemeteryManualEntry,
  CemeteryPlatformMatch,
  CemeterySelectionItem,
} from "@/types/cemetery-directory";
import * as cemeteryService from "@/services/cemetery-directory-service";
import apiClient from "@/lib/api-client";

// ── LocalStorage keys ────────────────────────────────────────────────────────

const LS_STEP = "cem-onboard-step";
const LS_RADIUS = "cem-onboard-radius";
const LS_SELECTED = "cem-onboard-selected";
const LS_MANUAL = "cem-onboard-manual";

function safeParse<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

const DEFAULT_EQUIPMENT: CemeteryEquipmentSettings = {
  provides_lowering_device: false,
  provides_grass: false,
  provides_tent: false,
  provides_chairs: false,
};

// ── Manual entry row (includes internal _id for React keys) ──────────────────

interface ManualRow extends CemeteryManualEntry {
  _id: string;
}

function emptyManualRow(defaultState: string): ManualRow {
  return {
    _id: Math.random().toString(36).slice(2),
    name: "",
    city: null,
    state: defaultState || null,
    county: null,
    equipment: { ...DEFAULT_EQUIPMENT },
    equipment_note: null,
  };
}

// ── Cemetery config used in Step 3 ───────────────────────────────────────────

interface CemeteryConfig {
  /** Unique key within this wizard session — place_id or "m-{_id}" */
  _key: string;
  /** null for manual entries */
  place_id: string | null;
  name: string;
  locationLabel: string;
  equipment: CemeteryEquipmentSettings;
  county: string;
  equipment_note: string;
  expanded: boolean;
}

// ── Equipment checkbox group ──────────────────────────────────────────────────

function EquipmentCheckboxes({
  value,
  onChange,
}: {
  value: CemeteryEquipmentSettings;
  onChange: (v: CemeteryEquipmentSettings) => void;
}) {
  const items: { key: keyof CemeteryEquipmentSettings; label: string }[] = [
    { key: "provides_lowering_device", label: "Lowering device" },
    { key: "provides_grass", label: "Grass service" },
    { key: "provides_tent", label: "Tent" },
    { key: "provides_chairs", label: "Chairs" },
  ];
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
      {items.map(({ key, label }) => (
        <label key={key} className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={value[key]}
            onChange={(e) => onChange({ ...value, [key]: e.target.checked })}
            className="rounded border-gray-300"
          />
          {label}
        </label>
      ))}
    </div>
  );
}

// ── Cemetery card (Step 1) ────────────────────────────────────────────────────

function CemeteryCard({
  entry,
  selected,
  onToggle,
}: {
  entry: CemeteryDirectoryEntry;
  selected: boolean;
  onToggle: () => void;
}) {
  if (entry.already_added) {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-green-200 bg-green-50 px-3 py-2.5 opacity-80">
        <Check className="h-4 w-4 text-green-600 mt-0.5 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-green-800 truncate">{entry.name}</p>
          <p className="text-xs text-green-600">Already in your list</p>
        </div>
      </div>
    );
  }

  return (
    <button
      onClick={onToggle}
      className={cn(
        "w-full text-left flex items-start gap-3 rounded-lg border px-3 py-2.5 transition-colors",
        selected
          ? "border-blue-400 bg-blue-50"
          : "border-gray-200 hover:border-gray-300 hover:bg-gray-50",
      )}
    >
      <div
        className={cn(
          "mt-0.5 h-4 w-4 shrink-0 rounded border-2 flex items-center justify-center",
          selected ? "border-blue-500 bg-blue-500" : "border-gray-300",
        )}
      >
        {selected && <Check className="h-3 w-3 text-white" />}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium truncate">{entry.name}</p>
        <p className="text-xs text-muted-foreground">
          {[entry.city, entry.state_code].filter(Boolean).join(", ")}
          {entry.county ? ` · ${entry.county} County` : ""}
        </p>
        {entry.distance_miles !== null && entry.distance_miles !== undefined && (
          <p className="text-xs text-muted-foreground">{entry.distance_miles.toFixed(1)} mi away</p>
        )}
        {entry.google_rating != null && (
          <p className="text-xs text-muted-foreground flex items-center gap-0.5 mt-0.5">
            <Star className="h-3 w-3 text-yellow-500 fill-yellow-500" />
            {entry.google_rating.toFixed(1)}
            {entry.google_review_count != null && (
              <span className="ml-0.5">({entry.google_review_count})</span>
            )}
          </p>
        )}
      </div>
    </button>
  );
}

// ── Step indicator ────────────────────────────────────────────────────────────

function StepDots({ current }: { current: number }) {
  const STEPS = ["Platform", "Discover", "Add missing", "Equipment"];
  return (
    <div className="flex items-center gap-2 mb-8 flex-wrap">
      {STEPS.map((label, i) => (
        <div key={label} className="flex items-center gap-2">
          <div
            className={cn(
              "h-6 w-6 rounded-full flex items-center justify-center text-xs font-medium shrink-0",
              i < current
                ? "bg-green-500 text-white"
                : i === current
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-muted-foreground",
            )}
          >
            {i < current ? <Check className="h-3.5 w-3.5" /> : i + 1}
          </div>
          <span
            className={cn(
              "text-sm whitespace-nowrap",
              i === current ? "font-medium" : "text-muted-foreground",
            )}
          >
            {label}
          </span>
          {i < STEPS.length - 1 && <div className="w-8 border-t border-gray-200" />}
        </div>
      ))}
    </div>
  );
}

// ── STEP 0 — Platform Connections ────────────────────────────────────────────

function PlatformStep({
  matches,
  decisions,
  loading,
  connecting,
  onConnect,
  onSkip,
  onUndo,
  onNext,
}: {
  matches: CemeteryPlatformMatch[];
  decisions: Record<string, "connected" | "skipped">;
  loading: boolean;
  connecting: Set<string>;
  onConnect: (id: string) => void;
  onSkip: (id: string) => void;
  onUndo: (id: string) => void;
  onNext: () => void;
}) {
  const undecided = matches.filter((m) => !decisions[m.id] && !m.connected);
  const decided = matches.filter((m) => decisions[m.id] || m.connected);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Cemeteries already on Bridgeable</h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-xl">
          These cemetery businesses are already using Bridgeable in your area. Connect with them to
          enable future integrations.
        </p>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg border bg-muted" />
          ))}
        </div>
      ) : matches.length === 0 ? (
        <div className="py-8 text-center">
          <Link2 className="mx-auto h-10 w-10 text-muted-foreground opacity-40" />
          <p className="mt-3 text-sm text-muted-foreground">
            No cemeteries in your area are on the platform yet.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Undecided */}
          {undecided.map((match) => (
            <div
              key={match.id}
              className="flex items-center justify-between rounded-lg border p-4"
            >
              <div>
                <p className="font-medium text-sm">{match.name}</p>
                <p className="text-xs text-muted-foreground">
                  {[match.city, match.state].filter(Boolean).join(", ")} · Already on Bridgeable
                </p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => onSkip(match.id)}>
                  Skip
                </Button>
                <Button
                  size="sm"
                  onClick={() => onConnect(match.id)}
                  disabled={connecting.has(match.id)}
                >
                  {connecting.has(match.id) ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    "Connect"
                  )}
                </Button>
              </div>
            </div>
          ))}

          {/* Decided */}
          {decided.length > 0 && (
            <div className="space-y-2">
              {decided.length > 0 && undecided.length > 0 && (
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground pt-1">
                  Decided
                </p>
              )}
              {decided.map((match) => {
                const decision = decisions[match.id];
                const isConnected = decision === "connected" || match.connected;
                return (
                  <div
                    key={match.id}
                    className={cn(
                      "flex items-center justify-between rounded-lg border p-3",
                      isConnected
                        ? "border-l-4 border-l-green-500 bg-green-50/50"
                        : "bg-gray-50",
                    )}
                  >
                    <div className="flex items-center gap-2">
                      {isConnected ? (
                        <Check className="h-4 w-4 text-green-600 shrink-0" />
                      ) : (
                        <X className="h-4 w-4 text-muted-foreground shrink-0" />
                      )}
                      <div>
                        <span
                          className={cn(
                            "text-sm",
                            !isConnected && "text-muted-foreground",
                          )}
                        >
                          {match.name}
                        </span>
                        <span className="ml-2 text-xs text-muted-foreground">
                          {isConnected ? "Connected" : "Skipped"}
                        </span>
                      </div>
                    </div>
                    {!match.connected && (
                      <button
                        onClick={() => onUndo(match.id)}
                        className="text-xs text-muted-foreground hover:text-foreground"
                      >
                        Undo
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      <div className="flex justify-end pt-2 border-t">
        <Button onClick={onNext}>
          Next <ArrowRight className="ml-1.5 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}


// ── STEP 1 — Discover ─────────────────────────────────────────────────────────

function DiscoverStep({
  entries,
  loading,
  radius,
  selected,
  toggleSelect,
  onChangeRadius,
  onRefresh,
  onNext,
}: {
  entries: CemeteryDirectoryEntry[];
  loading: boolean;
  radius: number;
  selected: Set<string>;
  toggleSelect: (placeId: string) => void;
  onChangeRadius: (r: number) => void;
  onRefresh: (r: number) => void;
  onNext: () => void;
}) {
  const RADIUS_OPTIONS = [25, 50, 100];
  const [nameFilter, setNameFilter] = useState("");
  const [displayCount, setDisplayCount] = useState(30);
  const [sortMode, setSortMode] = useState<"distance" | "alpha">("distance");

  // Reset displayCount when filter or radius changes
  useEffect(() => {
    setDisplayCount(30);
  }, [nameFilter, radius]);

  // Filter and sort entries
  const filteredEntries = entries.filter((e) => {
    if (!nameFilter.trim()) return true;
    return e.name.toLowerCase().includes(nameFilter.toLowerCase().trim());
  });

  const sortedEntries = [...filteredEntries].sort((a, b) => {
    if (sortMode === "distance") {
      const da = a.distance_miles ?? 9999;
      const db2 = b.distance_miles ?? 9999;
      return da - db2;
    }
    return a.name.localeCompare(b.name);
  });

  const visibleEntries = sortedEntries.slice(0, displayCount);
  const hasMore = sortedEntries.length > displayCount;

  const selectable = filteredEntries.filter((e) => !e.already_added);

  function selectAll() {
    selectable.forEach((e) => {
      if (!selected.has(e.place_id)) toggleSelect(e.place_id);
    });
  }
  function deselectAll() {
    selectable.forEach((e) => {
      if (selected.has(e.place_id)) toggleSelect(e.place_id);
    });
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Find cemeteries in your area</h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-xl">
          We searched OpenStreetMap for cemeteries within {radius} miles of your facility.
          Check the ones you deliver to.
        </p>
      </div>

      {/* Radius selector */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm text-muted-foreground">Radius:</span>
        {RADIUS_OPTIONS.map((r) => (
          <button
            key={r}
            onClick={() => {
              onChangeRadius(r);
              onRefresh(r);
            }}
            className={cn(
              "px-3 py-1 text-sm rounded-full border transition-colors",
              radius === r
                ? "border-blue-500 bg-blue-50 text-blue-700 font-medium"
                : "border-gray-200 hover:border-gray-300 text-muted-foreground",
            )}
          >
            {r} mi
          </button>
        ))}
        <button
          onClick={() => onRefresh(radius)}
          disabled={loading}
          className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          {loading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          Refresh
        </button>
      </div>

      {/* Name filter */}
      {entries.length > 0 && (
        <div>
          <input
            type="text"
            placeholder="Filter by name..."
            value={nameFilter}
            onChange={(e) => setNameFilter(e.target.value)}
            className="w-full max-w-sm rounded-md border border-gray-200 px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
      )}

      {/* Sort options */}
      {entries.length > 0 && (
        <div className="flex items-center gap-3 text-xs">
          <span className="text-muted-foreground">Sort:</span>
          <button
            onClick={() => setSortMode("distance")}
            className={cn("font-medium", sortMode === "distance" ? "text-blue-600" : "text-muted-foreground hover:text-foreground")}
          >
            Nearest first
          </button>
          <span className="text-muted-foreground">·</span>
          <button
            onClick={() => setSortMode("alpha")}
            className={cn("font-medium", sortMode === "alpha" ? "text-blue-600" : "text-muted-foreground hover:text-foreground")}
          >
            A–Z
          </button>
        </div>
      )}

      {/* Batch controls */}
      {selectable.length > 0 && (
        <div className="flex items-center gap-3 text-sm">
          <button onClick={selectAll} className="text-blue-600 hover:text-blue-700 font-medium">
            Select all ({selectable.length})
          </button>
          <span className="text-muted-foreground">·</span>
          <button onClick={deselectAll} className="text-muted-foreground hover:text-foreground">
            Deselect all
          </button>
          {selected.size > 0 && (
            <>
              <span className="text-muted-foreground">·</span>
              <span className="text-muted-foreground">{selected.size} selected</span>
            </>
          )}
          {selectable.some((e) => (e.distance_miles ?? 9999) <= 25) && (
            <>
              <span className="text-muted-foreground">·</span>
              <button
                onClick={() => {
                  selectable.filter((e) => (e.distance_miles ?? 9999) <= 25).forEach((e) => {
                    if (!selected.has(e.place_id)) toggleSelect(e.place_id);
                  });
                }}
                className="text-blue-600 hover:text-blue-700 font-medium"
              >
                Select within 25 mi
              </button>
            </>
          )}
        </div>
      )}

      {/* Result count */}
      {!loading && filteredEntries.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Showing {Math.min(displayCount, filteredEntries.length)} of {filteredEntries.length} cemeteries
          {nameFilter ? ` matching "${nameFilter}"` : ` within ${radius} miles`}
        </p>
      )}

      {/* Cemetery grid */}
      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : filteredEntries.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <MapPin className="h-8 w-8 mx-auto mb-2 opacity-40" />
          <p className="text-sm">
            {nameFilter ? `No cemeteries match "${nameFilter}".` : `No cemeteries found within ${radius} miles.`}
          </p>
          {!nameFilter && (
            <p className="text-xs mt-1">
              Make sure your facility address is set in company settings, or try a larger radius.
            </p>
          )}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {visibleEntries.map((entry) => (
              <CemeteryCard
                key={entry.place_id}
                entry={entry}
                selected={selected.has(entry.place_id)}
                onToggle={() => toggleSelect(entry.place_id)}
              />
            ))}
          </div>
          {hasMore && (
            <div className="text-center">
              <button
                onClick={() => setDisplayCount((n) => n + 30)}
                className="text-sm text-blue-600 hover:text-blue-700 font-medium px-4 py-2 rounded-md border border-blue-200 hover:border-blue-300 transition-colors"
              >
                Show {Math.min(30, sortedEntries.length - displayCount)} more
              </button>
            </div>
          )}
        </>
      )}

      {/* Inline-add demo callout */}
      <CemeteryInlineAddDemo />

      <div className="flex items-center justify-between pt-2 border-t">
        <button
          onClick={onNext}
          className="text-sm text-muted-foreground hover:text-foreground underline-offset-2 hover:underline"
        >
          Skip this step
        </button>
        <Button onClick={onNext} disabled={loading}>
          Next <ArrowRight className="ml-1.5 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

// ── STEP 2 — Add Missing ──────────────────────────────────────────────────────

function AddMissingStep({
  rows,
  setRows,
  tenantState,
  onBack,
  onNext,
}: {
  rows: ManualRow[];
  setRows: (r: ManualRow[]) => void;
  tenantState: string;
  onBack: () => void;
  onNext: () => void;
}) {
  function addRow() {
    setRows([...rows, emptyManualRow(tenantState)]);
  }

  function update(id: string, patch: Partial<ManualRow>) {
    setRows(rows.map((r) => (r._id === id ? { ...r, ...patch } : r)));
  }

  function remove(id: string) {
    setRows(rows.filter((r) => r._id !== id));
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Any cemeteries we missed?</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Add cemeteries not found in our search. You can also add these anytime from{" "}
          <strong>Customers → Cemeteries</strong>.
        </p>
      </div>

      {rows.length > 0 && (
        <div className="space-y-3">
          {rows.map((row) => (
            <Card key={row._id} className="p-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <Label className="text-xs">Cemetery name *</Label>
                  <Input
                    value={row.name}
                    onChange={(e) => update(row._id, { name: e.target.value })}
                    placeholder="Oak Hill Cemetery"
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-xs">City *</Label>
                  <Input
                    value={row.city ?? ""}
                    onChange={(e) => update(row._id, { city: e.target.value || null })}
                    placeholder="Auburn"
                    className="mt-1"
                  />
                </div>
                <div>
                  <Label className="text-xs">State</Label>
                  <Input
                    value={row.state ?? ""}
                    onChange={(e) => update(row._id, { state: e.target.value || null })}
                    placeholder="NY"
                    maxLength={2}
                    className="mt-1"
                  />
                </div>
                <div className="col-span-2">
                  <Label className="text-xs">
                    County{" "}
                    <span className="text-muted-foreground font-normal">
                      (optional — affects tax rate on orders)
                    </span>
                  </Label>
                  <Input
                    value={row.county ?? ""}
                    onChange={(e) => update(row._id, { county: e.target.value || null })}
                    placeholder="Cayuga"
                    className="mt-1"
                  />
                </div>
              </div>
              <div className="mt-3 flex justify-end">
                <button
                  onClick={() => remove(row._id)}
                  className="text-xs text-destructive hover:text-destructive/80 flex items-center gap-1"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Remove
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Button variant="outline" size="sm" onClick={addRow}>
        <Plus className="mr-1.5 h-4 w-4" />
        Add a cemetery
      </Button>

      <div className="flex items-center justify-between pt-2 border-t">
        <Button variant="outline" onClick={onBack}>
          ← Back
        </Button>
        <Button onClick={onNext}>
          Next <ArrowRight className="ml-1.5 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

// ── STEP 3 — Equipment Settings ───────────────────────────────────────────────

function EquipmentStep({
  configs,
  onUpdate,
  submitting,
  onBack,
  onComplete,
}: {
  configs: CemeteryConfig[];
  onUpdate: (key: string, patch: Partial<CemeteryConfig>) => void;
  submitting: boolean;
  onBack: () => void;
  onComplete: () => void;
}) {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Configure equipment settings</h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-xl">
          Some cemeteries provide their own lowering devices or tents. Set that up now so orders
          auto-fill correctly.
        </p>
      </div>

      <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        <strong>Most cemeteries provide nothing</strong> — leave all boxes unchecked for those.
        Only check what the cemetery actually handles themselves.
      </div>

      <ContextualExplanation explanationKey="cemetery_equipment_settings" />

      {configs.length === 0 ? (
        <p className="text-sm text-muted-foreground italic py-4">
          No cemeteries selected. Click Complete Setup to finish, or go back to select some.
        </p>
      ) : (
        <div className="space-y-2">
          {configs.map((cfg) => (
            <Card key={cfg._key} className="overflow-hidden">
              <button
                className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors"
                onClick={() => onUpdate(cfg._key, { expanded: !cfg.expanded })}
              >
                <div>
                  <p className="font-medium text-sm">{cfg.name}</p>
                  {cfg.locationLabel && (
                    <p className="text-xs text-muted-foreground">{cfg.locationLabel}</p>
                  )}
                </div>
                {cfg.expanded ? (
                  <ChevronUp className="h-4 w-4 text-muted-foreground shrink-0" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
                )}
              </button>

              {cfg.expanded && (
                <div className="px-4 pb-4 space-y-4 border-t">
                  <div className="pt-3">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                      This cemetery provides:
                    </p>
                    <EquipmentCheckboxes
                      value={cfg.equipment}
                      onChange={(v) => onUpdate(cfg._key, { equipment: v })}
                    />
                  </div>

                  <div>
                    <Label className="text-xs">
                      County{" "}
                      <span className="text-muted-foreground font-normal">
                        (important for tax calculation)
                      </span>
                    </Label>
                    <Input
                      value={cfg.county}
                      onChange={(e) => onUpdate(cfg._key, { county: e.target.value })}
                      placeholder="e.g. Cayuga"
                      className="mt-1"
                    />
                  </div>

                  <div>
                    <Label className="text-xs">
                      Equipment note{" "}
                      <span className="text-muted-foreground font-normal">
                        (optional, e.g. "Call ahead")
                      </span>
                    </Label>
                    <Input
                      value={cfg.equipment_note}
                      onChange={(e) => onUpdate(cfg._key, { equipment_note: e.target.value })}
                      placeholder="Optional note for your team"
                      className="mt-1"
                    />
                  </div>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between pt-2 border-t">
        <Button variant="outline" onClick={onBack}>
          ← Back
        </Button>
        <Button onClick={onComplete} disabled={submitting}>
          {submitting ? (
            <>
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              Complete Setup <ArrowRight className="ml-1.5 h-4 w-4" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

// ── Success screen ────────────────────────────────────────────────────────────

function SuccessScreen({ created, onContinue }: { created: number; onContinue: () => void }) {
  return (
    <div className="text-center py-12 space-y-4">
      <div className="inline-flex h-14 w-14 items-center justify-center rounded-full bg-green-100 mx-auto">
        <Check className="h-7 w-7 text-green-600" />
      </div>
      <div>
        <h2 className="text-xl font-bold">
          {created} {created === 1 ? "cemetery" : "cemeteries"} added to your list
        </h2>
        <p className="text-sm text-muted-foreground mt-1 max-w-sm mx-auto">
          Equipment settings saved. You can update these anytime from{" "}
          <strong>Customers → Cemeteries</strong>.
        </p>
      </div>
      <Button onClick={onContinue}>
        Go to order station <ArrowRight className="ml-1.5 h-4 w-4" />
      </Button>
    </div>
  );
}

// ── Main wizard ───────────────────────────────────────────────────────────────

export default function CemeterySetupWizard() {
  const navigate = useNavigate();

  const [step, setStep] = useState<number>(() => safeParse(LS_STEP, 0));
  const [done, setDone] = useState(false);
  const [createdCount, setCreatedCount] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [tenantState, setTenantState] = useState("");

  // Step 0 — Platform connections
  const [platformMatches, setPlatformMatches] = useState<CemeteryPlatformMatch[]>([]);
  const [platformLoading, setPlatformLoading] = useState(true);
  const [platformDecisions, setPlatformDecisions] = useState<Record<string, "connected" | "skipped">>({});
  const [connecting, setConnecting] = useState<Set<string>>(new Set());

  // Step 1
  const [entries, setEntries] = useState<CemeteryDirectoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [radius, setRadius] = useState<number>(() => safeParse(LS_RADIUS, 50));
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set<string>(safeParse<string[]>(LS_SELECTED, [])),
  );

  // Step 2
  const [manualRows, setManualRows] = useState<ManualRow[]>(() => safeParse(LS_MANUAL, []));

  // Step 3 — equipment/county/note state keyed by _key (place_id or "m-{_id}")
  const [configs, setConfigs] = useState<CemeteryConfig[]>([]);

  // ── Load tenant info ───────────────────────────────────────────────────────
  useEffect(() => {
    apiClient
      .get("/auth/me")
      .then((res) => {
        const company = res.data?.company;
        if (company?.facility_state) setTenantState(company.facility_state as string);
      })
      .catch(() => {});
  }, []);

  // ── Load platform matches on mount ────────────────────────────────────────
  useEffect(() => {
    cemeteryService
      .getPlatformMatches()
      .then(setPlatformMatches)
      .catch(() => {})
      .finally(() => setPlatformLoading(false));
  }, []);

  // ── Connect a platform cemetery ───────────────────────────────────────────
  async function handlePlatformConnect(id: string) {
    setConnecting((prev) => new Set(prev).add(id));
    try {
      await cemeteryService.connectPlatformCemetery(id);
      setPlatformDecisions((prev) => ({ ...prev, [id]: "connected" }));
    } catch {
      toast.error("Failed to connect. Please try again.");
    } finally {
      setConnecting((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  function handlePlatformSkip(id: string) {
    setPlatformDecisions((prev) => ({ ...prev, [id]: "skipped" }));
  }

  function handlePlatformUndo(id: string) {
    setPlatformDecisions((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }

  // ── Load directory on Step 1 ───────────────────────────────────────────────
  const loadDirectory = useCallback(async (r: number, forceRefresh = false) => {
    setLoading(true);
    try {
      const data = forceRefresh
        ? await cemeteryService.refreshCemeteryDirectory(r)
        : await cemeteryService.getCemeteryDirectory(r);
      setEntries(data);
    } catch {
      toast.error("Failed to load cemetery directory");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (step === 1) loadDirectory(radius);
  }, [step, radius, loadDirectory]);

  // ── Build step 3 configs when transitioning from step 2 ───────────────────
  useEffect(() => {
    if (step !== 3) return;

    const entryMap = new Map(entries.map((e) => [e.place_id, e]));
    const configMap = new Map(configs.map((c) => [c._key, c]));
    const next: CemeteryConfig[] = [];

    // Directory selections
    for (const placeId of selected) {
      const entry = entryMap.get(placeId);
      if (!entry || entry.already_added) continue;
      const key = placeId;
      const existing = configMap.get(key);
      next.push({
        _key: key,
        place_id: placeId,
        name: entry.name,
        locationLabel: [entry.city, entry.state_code].filter(Boolean).join(", "),
        equipment: existing?.equipment ?? { ...DEFAULT_EQUIPMENT },
        county: existing?.county ?? entry.county ?? "",
        equipment_note: existing?.equipment_note ?? "",
        expanded: existing?.expanded ?? false,
      });
    }

    // Manual entries
    for (const row of manualRows) {
      if (!row.name.trim()) continue;
      const key = `m-${row._id}`;
      const existing = configMap.get(key);
      next.push({
        _key: key,
        place_id: null,
        name: row.name.trim(),
        locationLabel: [row.city, row.state].filter(Boolean).join(", "),
        equipment: existing?.equipment ?? { ...DEFAULT_EQUIPMENT },
        county: existing?.county ?? row.county ?? "",
        equipment_note: existing?.equipment_note ?? "",
        expanded: existing?.expanded ?? false,
      });
    }

    setConfigs(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  // ── Persist step / radius / selected / manual ──────────────────────────────
  useEffect(() => { localStorage.setItem(LS_STEP, JSON.stringify(step)); }, [step]);
  useEffect(() => { localStorage.setItem(LS_RADIUS, JSON.stringify(radius)); }, [radius]);
  useEffect(() => { localStorage.setItem(LS_SELECTED, JSON.stringify([...selected])); }, [selected]);
  useEffect(() => { localStorage.setItem(LS_MANUAL, JSON.stringify(manualRows)); }, [manualRows]);

  // ── Toggle selection ───────────────────────────────────────────────────────
  function toggleSelect(placeId: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(placeId)) next.delete(placeId);
      else next.add(placeId);
      return next;
    });
  }

  // ── Update a single config in step 3 ──────────────────────────────────────
  function updateConfig(key: string, patch: Partial<CemeteryConfig>) {
    setConfigs((prev) => prev.map((c) => (c._key === key ? { ...c, ...patch } : c)));
  }

  // ── Submit ─────────────────────────────────────────────────────────────────
  async function handleComplete() {
    setSubmitting(true);
    try {
      const entryMap = new Map(entries.map((e) => [e.place_id, e]));

      const selections: CemeterySelectionItem[] = [];

      // "add" selections from step 3 configs (directory entries)
      for (const cfg of configs) {
        if (cfg.place_id === null) continue;
        selections.push({
          place_id: cfg.place_id,
          name: cfg.name,
          action: "add",
          equipment: cfg.equipment,
          county: cfg.county || entryMap.get(cfg.place_id)?.county || null,
          equipment_note: cfg.equipment_note || null,
        });
      }

      // "skip" selections for entries that were shown but not selected
      for (const entry of entries) {
        if (!selected.has(entry.place_id) && !entry.already_added) {
          selections.push({
            place_id: entry.place_id,
            name: entry.name,
            action: "skip",
            equipment: { ...DEFAULT_EQUIPMENT },
            county: null,
            equipment_note: null,
          });
        }
      }

      // Manual entries from step 3 configs
      const manual: CemeteryManualEntry[] = configs
        .filter((c) => c.place_id === null)
        .map((c) => ({
          name: c.name,
          city: null,
          state: null,
          county: c.county || null,
          equipment: c.equipment,
          equipment_note: c.equipment_note || null,
        }));

      const result = await cemeteryService.recordSelections(selections, manual);

      // Clear localStorage
      [LS_STEP, LS_RADIUS, LS_SELECTED, LS_MANUAL].forEach((k) =>
        localStorage.removeItem(k),
      );

      setCreatedCount(result.created);
      setDone(true);
    } catch {
      toast.error("Failed to save cemeteries. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  if (done) {
    return (
      <div className="max-w-2xl mx-auto p-6">
        <SuccessScreen
          created={createdCount}
          onContinue={() => navigate("/order-station")}
        />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-6">
      <StepDots current={step} />

      {step === 0 && (
        <PlatformStep
          matches={platformMatches}
          decisions={platformDecisions}
          loading={platformLoading}
          connecting={connecting}
          onConnect={handlePlatformConnect}
          onSkip={handlePlatformSkip}
          onUndo={handlePlatformUndo}
          onNext={() => setStep(1)}
        />
      )}

      {step === 1 && (
        <DiscoverStep
          entries={entries}
          loading={loading}
          radius={radius}
          selected={selected}
          toggleSelect={toggleSelect}
          onChangeRadius={setRadius}
          onRefresh={(r) => loadDirectory(r, true)}
          onNext={() => setStep(2)}
        />
      )}

      {step === 2 && (
        <AddMissingStep
          rows={manualRows}
          setRows={setManualRows}
          tenantState={tenantState}
          onBack={() => setStep(1)}
          onNext={() => setStep(3)}
        />
      )}

      {step === 3 && (
        <EquipmentStep
          configs={configs}
          onUpdate={updateConfig}
          submitting={submitting}
          onBack={() => setStep(2)}
          onComplete={handleComplete}
        />
      )}
    </div>
  );
}
