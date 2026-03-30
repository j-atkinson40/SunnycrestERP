/**
 * Cemetery Setup Wizard — 3-step onboarding flow for manufacturer cemeteries.
 *
 * Step 0 — Platform:       Connect to cemetery tenants already on Bridgeable.
 * Step 1 — Add Cemeteries: Search & add cemeteries with inline equipment config.
 * Step 2 — Complete:       Review, amber county warnings, submit.
 */

import { useState, useEffect } from "react";
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
  CemeteryNameAutocomplete,
  type AutocompleteResult,
} from "@/components/cemetery-name-autocomplete";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronUp,
  Link2,
  Loader2,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import type {
  CemeteryEquipmentSettings,
  CemeteryManualEntry,
  CemeteryPlatformMatch,
  CemeterySelectionItem,
} from "@/types/cemetery-directory";
import * as cemeteryService from "@/services/cemetery-directory-service";
import apiClient from "@/lib/api-client";

// ── LocalStorage keys ────────────────────────────────────────────────────────

const LS_STEP = "cem-onboard-step";
const LS_ENTRIES = "cem-onboard-entries";

function safeParse<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

// ── Entry type (Step 1) ──────────────────────────────────────────────────────

interface CemeteryEntry {
  /** React key */
  _id: string;
  name: string;
  city: string;
  state: string;
  county: string;
  /** OSM place_id — null for manually typed entries */
  place_id: string | null;
  /** ID of an existing operational Cemetery record */
  cemetery_id: string | null;
  lat: number | null;
  lng: number | null;
  /** True if this cemetery is already in the operational cemeteries table */
  already_added: boolean;
  /** Whether the equipment/details section is expanded */
  expanded: boolean;
  /** Equipment flags */
  provides_lowering_device: boolean;
  provides_grass: boolean;
  provides_tent: boolean;
  provides_chairs: boolean;
  equipment_note: string;
  /** Historical order count — populated when pre-filled from import history */
  order_count?: number;
}

function emptyEntry(defaultState: string): CemeteryEntry {
  return {
    _id: Math.random().toString(36).slice(2),
    name: "",
    city: "",
    state: defaultState,
    county: "",
    place_id: null,
    cemetery_id: null,
    lat: null,
    lng: null,
    already_added: false,
    expanded: false,
    provides_lowering_device: false,
    provides_grass: false,
    provides_tent: false,
    provides_chairs: false,
    equipment_note: "",
  };
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

// ── Step indicator ────────────────────────────────────────────────────────────

function StepDots({ current }: { current: number }) {
  const STEPS = ["Platform", "Add Cemeteries", "Complete"];
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

// ── STEP 1 — Add Cemeteries ───────────────────────────────────────────────────

function EntryCard({
  entry,
  onUpdate,
  onRemove,
}: {
  entry: CemeteryEntry;
  onUpdate: (id: string, patch: Partial<CemeteryEntry>) => void;
  onRemove: (id: string) => void;
}) {
  const equipment: CemeteryEquipmentSettings = {
    provides_lowering_device: entry.provides_lowering_device,
    provides_grass: entry.provides_grass,
    provides_tent: entry.provides_tent,
    provides_chairs: entry.provides_chairs,
  };

  function handleAutocompleteSelect(result: AutocompleteResult | null) {
    if (!result) return;
    onUpdate(entry._id, {
      name: result.name,
      city: result.city ?? entry.city,
      state: result.state ?? entry.state,
      county: result.county ?? entry.county,
      lat: result.latitude,
      lng: result.longitude,
      place_id: result.place_id,
      cemetery_id: result.cemetery_id,
      already_added: result.already_added,
    });
  }

  return (
    <Card className="overflow-hidden">
      <div className="px-4 pt-3 pb-2 space-y-2">
        {/* Order count badge (from history pre-population) */}
        {entry.order_count !== undefined && entry.order_count > 0 && (
          <div className="flex items-center justify-between">
            <span className="text-xs bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full font-medium">
              {entry.order_count.toLocaleString()} historical orders
            </span>
          </div>
        )}
        {/* Name autocomplete */}
        <div>
          <Label className="text-xs">Cemetery name *</Label>
          <CemeteryNameAutocomplete
            value={entry.name}
            onChange={(name) => onUpdate(entry._id, { name, already_added: false, place_id: null, cemetery_id: null })}
            onSelect={handleAutocompleteSelect}
            placeholder="Search or type cemetery name..."
            className="mt-1"
          />
        </div>

        {/* Already-added notice */}
        {entry.already_added && (
          <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1 flex items-center gap-1.5">
            <AlertTriangle className="h-3 w-3 shrink-0" />
            Already in your cemetery list — equipment can be updated in Settings.
          </p>
        )}

        {/* Expand toggle */}
        {!entry.already_added && entry.name.trim() && (
          <button
            type="button"
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => onUpdate(entry._id, { expanded: !entry.expanded })}
          >
            {entry.expanded ? (
              <>
                <ChevronUp className="h-3.5 w-3.5" /> Hide details
              </>
            ) : (
              <>
                <ChevronDown className="h-3.5 w-3.5" /> Add details &amp; equipment
              </>
            )}
          </button>
        )}

        {/* Expanded section */}
        {entry.expanded && !entry.already_added && (
          <div className="space-y-3 pt-3 border-t">
            <div className="grid grid-cols-3 gap-2">
              <div>
                <Label className="text-xs">City</Label>
                <Input
                  value={entry.city}
                  onChange={(e) => onUpdate(entry._id, { city: e.target.value })}
                  placeholder="Auburn"
                  className="mt-1 h-8 text-sm"
                />
              </div>
              <div>
                <Label className="text-xs">State</Label>
                <Input
                  value={entry.state}
                  onChange={(e) => onUpdate(entry._id, { state: e.target.value })}
                  placeholder="NY"
                  maxLength={2}
                  className="mt-1 h-8 text-sm"
                />
              </div>
              <div>
                <Label className="text-xs">
                  County{" "}
                  <span className="font-normal text-muted-foreground">(tax)</span>
                </Label>
                <Input
                  value={entry.county}
                  onChange={(e) => onUpdate(entry._id, { county: e.target.value })}
                  placeholder="Cayuga"
                  className="mt-1 h-8 text-sm"
                />
              </div>
            </div>

            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                This cemetery provides:
              </p>
              <EquipmentCheckboxes
                value={equipment}
                onChange={(v) =>
                  onUpdate(entry._id, {
                    provides_lowering_device: v.provides_lowering_device,
                    provides_grass: v.provides_grass,
                    provides_tent: v.provides_tent,
                    provides_chairs: v.provides_chairs,
                  })
                }
              />
            </div>

            <div>
              <Label className="text-xs">
                Equipment note{" "}
                <span className="font-normal text-muted-foreground">(optional)</span>
              </Label>
              <Input
                value={entry.equipment_note}
                onChange={(e) => onUpdate(entry._id, { equipment_note: e.target.value })}
                placeholder="e.g. Call ahead for gate code"
                className="mt-1 h-8 text-sm"
              />
            </div>
          </div>
        )}
      </div>

      {/* Remove button */}
      <div className="px-4 pb-2 flex justify-end">
        <button
          type="button"
          onClick={() => onRemove(entry._id)}
          className="text-xs text-destructive hover:text-destructive/80 flex items-center gap-1"
        >
          <Trash2 className="h-3.5 w-3.5" />
          Remove
        </button>
      </div>
    </Card>
  );
}

function AddCemeteriesStep({
  entries,
  onUpdate,
  onAdd,
  onRemove,
  onNext,
  fromHistory,
}: {
  entries: CemeteryEntry[];
  onUpdate: (id: string, patch: Partial<CemeteryEntry>) => void;
  onAdd: () => void;
  onRemove: (id: string) => void;
  onNext: () => void;
  fromHistory: boolean;
}) {
  return (
    <div className="space-y-5">
      <div>
        {fromHistory ? (
          <>
            <h1 className="text-2xl font-bold">Review cemeteries from your history</h1>
            <p className="text-sm text-muted-foreground mt-1 max-w-xl">
              These are the cemeteries from your imported order history, ranked by order count.
              Review equipment settings, remove any you don&apos;t need, and add others.
            </p>
          </>
        ) : (
          <>
            <h1 className="text-2xl font-bold">Add cemeteries you deliver to</h1>
            <p className="text-sm text-muted-foreground mt-1 max-w-xl">
              Search by name — details like county and city auto-fill from OpenStreetMap. You can
              always add more cemeteries later from the order form or Settings.
            </p>
          </>
        )}
      </div>

      <ContextualExplanation explanationKey="cemetery_equipment_settings" />

      {entries.length > 0 && (
        <div className="space-y-3">
          {entries.map((entry) => (
            <EntryCard
              key={entry._id}
              entry={entry}
              onUpdate={onUpdate}
              onRemove={onRemove}
            />
          ))}
        </div>
      )}

      <Button variant="outline" size="sm" onClick={onAdd}>
        <Plus className="mr-1.5 h-4 w-4" />
        Add a cemetery
      </Button>

      {/* Reassurance callout */}
      <div>
        <p className="text-sm font-medium text-muted-foreground mb-2">
          Don&apos;t worry about adding every cemetery now
        </p>
        <CemeteryInlineAddDemo />
      </div>

      <div className="flex items-center justify-between pt-2 border-t">
        <button
          type="button"
          onClick={onNext}
          className="text-sm text-muted-foreground hover:text-foreground underline-offset-2 hover:underline"
        >
          Skip this step
        </button>
        <Button onClick={onNext}>
          Next <ArrowRight className="ml-1.5 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

// ── STEP 2 — Complete ─────────────────────────────────────────────────────────

function CompleteStep({
  entries,
  submitting,
  onBack,
  onComplete,
}: {
  entries: CemeteryEntry[];
  submitting: boolean;
  onBack: () => void;
  onComplete: () => void;
}) {
  const newEntries = entries.filter((e) => e.name.trim() && !e.already_added);
  const missingCounty = newEntries.filter((e) => !e.county.trim());

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Ready to save</h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-xl">
          Review the cemeteries below, then click Complete Setup to add them to your list.
        </p>
      </div>

      {/* Summary list */}
      {newEntries.length === 0 ? (
        <p className="text-sm text-muted-foreground italic py-4">
          No new cemeteries added. You can add them anytime from the order form or{" "}
          <strong>Settings → Cemeteries</strong>.
        </p>
      ) : (
        <div className="rounded-md border divide-y">
          {newEntries.map((e) => (
            <div key={e._id} className="flex items-center justify-between px-3 py-2 text-sm">
              <span className="font-medium">{e.name}</span>
              <span className="text-xs text-muted-foreground">
                {[e.city, e.state].filter(Boolean).join(", ")}
                {e.county ? ` · ${e.county} County` : ""}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Missing county warning */}
      {missingCounty.length > 0 && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 flex gap-3">
          <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
          <div className="text-sm text-amber-800">
            <p className="font-medium">County not set for {missingCounty.length === 1 ? "1 cemetery" : `${missingCounty.length} cemeteries`}:</p>
            <p className="mt-0.5 text-xs">
              {missingCounty.map((e) => e.name).join(", ")}
            </p>
            <p className="mt-1 text-xs">
              County determines the tax rate on orders. Go back to add counties, or update them
              later in <strong>Settings → Cemeteries</strong>.
            </p>
          </div>
        </div>
      )}

      {/* Inline-add demo */}
      <CemeteryInlineAddDemo />

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
          <strong>Settings → Cemeteries</strong>.
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
  const [platformDecisions, setPlatformDecisions] = useState<
    Record<string, "connected" | "skipped">
  >({});
  const [connecting, setConnecting] = useState<Set<string>>(new Set());

  // Step 1 — Cemetery entries
  const [entries, setEntries] = useState<CemeteryEntry[]>(() =>
    safeParse<CemeteryEntry[]>(LS_ENTRIES, []),
  );
  const [fromHistory, setFromHistory] = useState(false);

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

  // ── Pre-populate from historical import (when no entries saved yet) ───────
  useEffect(() => {
    const savedEntries = safeParse<CemeteryEntry[]>(LS_ENTRIES, []);
    if (savedEntries.length > 0) return; // Don't overwrite existing user work
    apiClient
      .get("/historical-orders/top-cemeteries", { params: { limit: 20 } })
      .then((res) => {
        const list = res.data as Array<{
          name: string;
          raw_name?: string;
          cemetery_id?: string;
          city?: string;
          state?: string;
          county?: string;
          order_count: number;
        }>;
        if (!Array.isArray(list) || list.length === 0) return;
        const prePopulated: CemeteryEntry[] = list
          .filter((c) => c.name && c.name.trim())
          .map((c) => ({
            _id: Math.random().toString(36).slice(2),
            name: c.name.trim(),
            city: c.city ?? "",
            state: c.state ?? "",
            county: c.county ?? "",
            place_id: null,
            cemetery_id: c.cemetery_id ?? null,
            lat: null,
            lng: null,
            already_added: !!c.cemetery_id,
            expanded: false,
            provides_lowering_device: false,
            provides_grass: false,
            provides_tent: false,
            provides_chairs: false,
            equipment_note: "",
            order_count: c.order_count,
          }));
        if (prePopulated.length > 0) {
          setEntries(prePopulated);
          setFromHistory(true);
        }
      })
      .catch(() => {
        // No historical import — user starts with blank entries
      });
  }, []);

  // ── Platform step handlers ────────────────────────────────────────────────
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

  // ── Entry management ───────────────────────────────────────────────────────
  function updateEntry(id: string, patch: Partial<CemeteryEntry>) {
    setEntries((prev) => prev.map((e) => (e._id === id ? { ...e, ...patch } : e)));
  }

  function addEntry() {
    setEntries((prev) => [...prev, emptyEntry(tenantState)]);
  }

  function removeEntry(id: string) {
    setEntries((prev) => prev.filter((e) => e._id !== id));
  }

  // ── Persist step / entries ────────────────────────────────────────────────
  useEffect(() => {
    localStorage.setItem(LS_STEP, JSON.stringify(step));
  }, [step]);

  useEffect(() => {
    localStorage.setItem(LS_ENTRIES, JSON.stringify(entries));
  }, [entries]);

  // ── Submit ─────────────────────────────────────────────────────────────────
  async function handleComplete() {
    setSubmitting(true);
    try {
      const newEntries = entries.filter((e) => e.name.trim() && !e.already_added);

      // Directory entries with an OSM place_id → selections[]
      const selections: CemeterySelectionItem[] = newEntries
        .filter((e) => e.place_id !== null)
        .map((e) => ({
          place_id: e.place_id!,
          name: e.name,
          action: "add" as const,
          equipment: {
            provides_lowering_device: e.provides_lowering_device,
            provides_grass: e.provides_grass,
            provides_tent: e.provides_tent,
            provides_chairs: e.provides_chairs,
          },
          county: e.county || null,
          equipment_note: e.equipment_note || null,
        }));

      // Manually typed entries without a place_id → manual_entries[]
      const manual: CemeteryManualEntry[] = newEntries
        .filter((e) => e.place_id === null)
        .map((e) => ({
          name: e.name,
          city: e.city || null,
          state: e.state || null,
          county: e.county || null,
          equipment: {
            provides_lowering_device: e.provides_lowering_device,
            provides_grass: e.provides_grass,
            provides_tent: e.provides_tent,
            provides_chairs: e.provides_chairs,
          },
          equipment_note: e.equipment_note || null,
        }));

      const result = await cemeteryService.recordSelections(selections, manual);

      // Clear localStorage
      [LS_STEP, LS_ENTRIES].forEach((k) => localStorage.removeItem(k));

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
        <AddCemeteriesStep
          entries={entries}
          onUpdate={updateEntry}
          onAdd={addEntry}
          onRemove={removeEntry}
          onNext={() => setStep(2)}
          fromHistory={fromHistory}
        />
      )}

      {step === 2 && (
        <CompleteStep
          entries={entries}
          submitting={submitting}
          onBack={() => setStep(1)}
          onComplete={handleComplete}
        />
      )}
    </div>
  );
}
