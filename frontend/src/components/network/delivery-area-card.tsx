/**
 * DeliveryAreaCard — inline county selector for the preferences page.
 *
 * Simplified version of the full territory setup. Uses the same underlying
 * manufacturer_service_territories table.
 */

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { MapPin, Plus, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { US_STATES, getStateName } from "@/data/us-states";
import apiClient from "@/lib/api-client";

// ---------------------------------------------------------------------------
// County data — fetched from Census FIPS or inline for common states
// We use a lightweight API approach: fetch county names per state on demand.
// For now, we use a backend endpoint. If that's not available, we generate
// county names from the service_territory table.
// ---------------------------------------------------------------------------

interface SavedCounty {
  id?: string;
  state_code: string;
  county_name: string;
  county_fips?: string | null;
}

interface StateCountyGroup {
  stateCode: string;
  counties: string[];
  selectedCounties: Set<string>;
  loading: boolean;
}

interface DeliveryAreaCardProps {
  facilityState: string | null;
  deliveryAreaConfigured: boolean;
  /** Called when territory is saved — parent can use to check completion */
  onSaved?: () => void;
  /** Mode: "onboarding" shows setup-later option, "settings" doesn't */
  mode?: "onboarding" | "settings";
}

export function DeliveryAreaCard({
  facilityState,
  deliveryAreaConfigured,
  onSaved,
  mode = "settings",
}: DeliveryAreaCardProps) {
  const [setupMode, setSetupMode] = useState<"counties" | "later" | null>(
    deliveryAreaConfigured ? "counties" : null,
  );
  const [stateGroups, setStateGroups] = useState<StateCountyGroup[]>([]);
  const [saving, setSaving] = useState(false);
  const [initialLoaded, setInitialLoaded] = useState(false);
  const [showAddState, setShowAddState] = useState(false);

  // Load existing territories on mount
  useEffect(() => {
    const load = async () => {
      try {
        const resp = await apiClient.get("/settings/service-territories");
        const existing: SavedCounty[] = resp.data.counties ?? [];
        if (existing.length > 0) {
          // Group by state
          const byState: Record<string, Set<string>> = {};
          for (const c of existing) {
            if (!byState[c.state_code]) byState[c.state_code] = new Set();
            byState[c.state_code].add(c.county_name);
          }
          const groups: StateCountyGroup[] = [];
          for (const [stateCode, selected] of Object.entries(byState)) {
            groups.push({
              stateCode,
              counties: [],
              selectedCounties: selected,
              loading: false,
            });
          }
          setStateGroups(groups);
          setSetupMode("counties");
          // Fetch county lists for each state
          for (const g of groups) {
            fetchCountiesForState(g.stateCode);
          }
        } else if (facilityState && !deliveryAreaConfigured) {
          // Pre-add facility state but don't select anything
        }
      } catch {
        // Silent
      } finally {
        setInitialLoaded(true);
      }
    };
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchCountiesForState = useCallback(async (stateCode: string) => {
    // Fetch counties from Census API (free, no key required)
    try {
      setStateGroups((prev) =>
        prev.map((g) => (g.stateCode === stateCode ? { ...g, loading: true } : g)),
      );
      const resp = await fetch(
        `https://api.census.gov/data/2020/dec/pl?get=NAME&for=county:*&in=state:${getStateFips(stateCode)}`,
      );
      if (resp.ok) {
        const data: string[][] = await resp.json();
        // First row is header, rest are [county_name, state_fips, county_fips]
        const counties = data
          .slice(1)
          .map((row) => row[0].replace(/ County$| Parish$| Borough$| Census Area$| Municipality$/, ""))
          .sort();
        setStateGroups((prev) =>
          prev.map((g) =>
            g.stateCode === stateCode ? { ...g, counties, loading: false } : g,
          ),
        );
      } else {
        setStateGroups((prev) =>
          prev.map((g) => (g.stateCode === stateCode ? { ...g, loading: false } : g)),
        );
      }
    } catch {
      setStateGroups((prev) =>
        prev.map((g) => (g.stateCode === stateCode ? { ...g, loading: false } : g)),
      );
    }
  }, []);

  const handleSelectCounties = () => {
    setSetupMode("counties");
    if (stateGroups.length === 0 && facilityState) {
      const newGroup: StateCountyGroup = {
        stateCode: facilityState,
        counties: [],
        selectedCounties: new Set(),
        loading: false,
      };
      setStateGroups([newGroup]);
      fetchCountiesForState(facilityState);
    }
  };

  const addState = (stateCode: string) => {
    if (stateGroups.find((g) => g.stateCode === stateCode)) return;
    const newGroup: StateCountyGroup = {
      stateCode,
      counties: [],
      selectedCounties: new Set(),
      loading: false,
    };
    setStateGroups((prev) => [...prev, newGroup]);
    fetchCountiesForState(stateCode);
  };

  const removeState = (stateCode: string) => {
    setStateGroups((prev) => prev.filter((g) => g.stateCode !== stateCode));
  };

  const toggleCounty = (stateCode: string, county: string) => {
    setStateGroups((prev) =>
      prev.map((g) => {
        if (g.stateCode !== stateCode) return g;
        const next = new Set(g.selectedCounties);
        if (next.has(county)) next.delete(county);
        else next.add(county);
        return { ...g, selectedCounties: next };
      }),
    );
  };

  const totalSelected = stateGroups.reduce(
    (sum, g) => sum + g.selectedCounties.size,
    0,
  );

  const handleSave = async () => {
    setSaving(true);
    try {
      const counties: { state_code: string; county_name: string }[] = [];
      for (const g of stateGroups) {
        for (const c of g.selectedCounties) {
          counties.push({ state_code: g.stateCode, county_name: c });
        }
      }
      await apiClient.post("/settings/service-territories", { counties });
      toast.success(`Saved ${counties.length} counties`);
      onSaved?.();
    } catch {
      toast.error("Failed to save delivery area");
    } finally {
      setSaving(false);
    }
  };

  if (!initialLoaded) return null;

  // States not yet added
  const availableStates = US_STATES.filter(
    (s) => !stateGroups.find((g) => g.stateCode === s.code),
  );

  return (
    <div className="rounded-xl border bg-white p-6">
      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gray-100 text-gray-600">
          <MapPin className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-gray-900">Your Delivery Area</h3>
          <p className="mt-1 text-sm text-gray-500 leading-relaxed">
            Define the counties you serve. This helps funeral homes in your area
            find and connect with you on the platform.
          </p>
        </div>
      </div>

      {deliveryAreaConfigured && setupMode === "counties" && (
        <div className="ml-12 mb-3">
          <p className="text-xs text-emerald-600 bg-emerald-50 rounded-md px-3 py-1.5">
            Your territory was previously configured. Review and update if needed.
          </p>
        </div>
      )}

      {/* Setup mode selection (onboarding only) */}
      {!setupMode && mode === "onboarding" && (
        <div className="ml-12 space-y-2">
          <p className="text-sm text-gray-600 font-medium mb-2">
            How would you like to define your territory?
          </p>
          <label
            className="flex items-center gap-3 rounded-lg border p-3 cursor-pointer hover:bg-gray-50"
            onClick={handleSelectCounties}
          >
            <input type="radio" name="delivery_area_mode" />
            <span className="text-sm text-gray-900">
              Select counties you serve
            </span>
          </label>
          <label
            className="flex items-center gap-3 rounded-lg border p-3 cursor-pointer hover:bg-gray-50"
            onClick={() => setSetupMode("later")}
          >
            <input type="radio" name="delivery_area_mode" />
            <span className="text-sm text-gray-900">
              I'll set this up later
            </span>
          </label>
        </div>
      )}

      {/* Settings mode — always show county selector */}
      {!setupMode && mode === "settings" && (
        <div className="ml-12">
          <button
            onClick={handleSelectCounties}
            className="rounded-lg border border-blue-300 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100 transition-colors"
          >
            Set up delivery area
          </button>
        </div>
      )}

      {setupMode === "later" && (
        <div className="ml-12 mt-2">
          <p className="text-xs text-gray-400">
            You can configure this later from Settings &rarr; Network Preferences.
          </p>
          <button
            onClick={handleSelectCounties}
            className="mt-2 text-xs text-blue-600 hover:underline"
          >
            Actually, let me set this up now
          </button>
        </div>
      )}

      {/* County selector */}
      {setupMode === "counties" && (
        <div className="ml-12 mt-3 space-y-4">
          {stateGroups.map((group) => (
            <div key={group.stateCode} className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-gray-700">
                  State: {getStateName(group.stateCode)}
                </label>
                {stateGroups.length > 1 && (
                  <button
                    onClick={() => removeState(group.stateCode)}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    <X className="h-3 w-3" />
                  </button>
                )}
              </div>

              {group.loading ? (
                <p className="text-xs text-gray-400">Loading counties...</p>
              ) : group.counties.length === 0 ? (
                <p className="text-xs text-gray-400">
                  No county data available. Type county names manually.
                </p>
              ) : (
                <div className="max-h-48 overflow-y-auto rounded-md border p-2 space-y-0.5">
                  {group.counties.map((county) => (
                    <label
                      key={county}
                      className={cn(
                        "flex items-center gap-2 rounded px-2 py-1 cursor-pointer text-sm",
                        group.selectedCounties.has(county)
                          ? "bg-blue-50 text-blue-900"
                          : "hover:bg-gray-50 text-gray-700",
                      )}
                    >
                      <input
                        type="checkbox"
                        checked={group.selectedCounties.has(county)}
                        onChange={() => toggleCounty(group.stateCode, county)}
                        className="rounded"
                      />
                      {county} County
                    </label>
                  ))}
                </div>
              )}
            </div>
          ))}

          {/* Add another state */}
          {!showAddState ? (
            <button
              onClick={() => setShowAddState(true)}
              className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700"
            >
              <Plus className="h-3.5 w-3.5" />
              Add counties from another state
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <select
                className="rounded-md border px-3 py-1.5 text-sm"
                defaultValue=""
                onChange={(e) => {
                  if (e.target.value) {
                    addState(e.target.value);
                    setShowAddState(false);
                  }
                }}
              >
                <option value="">Select a state...</option>
                {availableStates.map((s) => (
                  <option key={s.code} value={s.code}>
                    {s.name}
                  </option>
                ))}
              </select>
              <button
                onClick={() => setShowAddState(false)}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                Cancel
              </button>
            </div>
          )}

          {/* Count + save */}
          <div className="flex items-center justify-between pt-2 border-t">
            <span className="text-sm text-gray-500">
              {totalSelected} {totalSelected === 1 ? "county" : "counties"}{" "}
              selected
            </span>
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded-lg bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {saving ? "Saving..." : "Save territory"}
            </button>
          </div>

          {/* Link to full territory page */}
          <p className="text-xs text-gray-400">
            Need more options?{" "}
            <a
              href="/settings/territory"
              className="text-blue-500 hover:underline"
            >
              Full territory settings &rarr;
            </a>
          </p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// State FIPS lookup for Census API
// ---------------------------------------------------------------------------

function getStateFips(stateCode: string): string {
  const fips: Record<string, string> = {
    AL: "01", AK: "02", AZ: "04", AR: "05", CA: "06", CO: "08",
    CT: "09", DE: "10", FL: "12", GA: "13", HI: "15", ID: "16",
    IL: "17", IN: "18", IA: "19", KS: "20", KY: "21", LA: "22",
    ME: "23", MD: "24", MA: "25", MI: "26", MN: "27", MS: "28",
    MO: "29", MT: "30", NE: "31", NV: "32", NH: "33", NJ: "34",
    NM: "35", NY: "36", NC: "37", ND: "38", OH: "39", OK: "40",
    OR: "41", PA: "42", RI: "44", SC: "45", SD: "46", TN: "47",
    TX: "48", UT: "49", VT: "50", VA: "51", WA: "53", WV: "54",
    WI: "55", WY: "56", DC: "11",
  };
  return fips[stateCode] || "17";
}
