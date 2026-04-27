import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Check, ChevronDown, Clock, MapPin, Plus, X } from "lucide-react";
import { cemeteryService } from "@/services/cemetery-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { Cemetery, CemeteryShortlistItem, EquipmentPrefill } from "@/types/customer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

interface GeographicItem {
  cemetery_id: string;
  cemetery_name: string;
  distance_miles: number | null;
  county: string | null;
  state: string | null;
  city: string | null;
}

interface CemeteryPickerProps {
  /** Funeral home customer ID — used to load shortlist */
  customerId: string | null;
  /** Currently selected cemetery_id */
  value: string | null;
  /** Display value to show in the input (cemetery name) */
  displayValue?: string;
  /** Called when selection changes */
  onChange: (cemeteryId: string | null, cemetery: Cemetery | null) => void;
  /** Called when equipment prefill fires (parent applies to order lines) */
  onEquipmentPrefill: (prefill: EquipmentPrefill) => void;
  /** CSS class for the container */
  className?: string;
  /** Whether this is in a guided-flow (adds data-guided attribute) */
  guidedKey?: string;
}

function cemeteryLocationLine(city?: string | null, county?: string | null, state?: string | null): string {
  if (city && state) return `${city}, ${state}`;
  if (city) return city;
  if (county && state) return `${county} County, ${state}`;
  if (county) return `${county} County`;
  if (state) return state;
  return "";
}

export function CemeteryPicker({
  customerId,
  value,
  displayValue: _displayValue,
  onChange,
  onEquipmentPrefill,
  className,
  guidedKey,
}: CemeteryPickerProps) {
  const [open, setOpen] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [searchResults, setSearchResults] = useState<Cemetery[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedCemetery, setSelectedCemetery] = useState<Cemetery | null>(null);
  const [prefill, setPrefill] = useState<EquipmentPrefill | null>(null);
  const [prefillVisible, setPrefillVisible] = useState(false);

  // Shortlist state
  const [shortlist, setShortlist] = useState<CemeteryShortlistItem[]>([]);
  const [geoShortlist, setGeoShortlist] = useState<GeographicItem[]>([]);
  const [shortlistMode, setShortlistMode] = useState<"history" | "geo" | "none">("none");
  const [shortlistLoaded, setShortlistLoaded] = useState(false);

  // Tax county confirmation
  const [showCountyConfirm, setShowCountyConfirm] = useState(false);
  const [countyDraft, setCountyDraft] = useState("");
  const [confirmingCounty, setConfirmingCounty] = useState(false);

  // Cold-start nag (show once per session)
  const [showAddNag, setShowAddNag] = useState(false);
  const nagShownRef = useRef(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prefillTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Load shortlist when customerId changes
  useEffect(() => {
    if (!customerId) {
      setShortlist([]);
      setGeoShortlist([]);
      setShortlistMode("none");
      setShortlistLoaded(true);
      return;
    }

    let cancelled = false;

    async function loadShortlist() {
      setShortlistLoaded(false);
      try {
        const hist = await cemeteryService.getCemeteryShortlist(customerId!);
        if (cancelled) return;
        if (hist.length > 0) {
          setShortlist(hist);
          setShortlistMode("history");
          setShortlistLoaded(true);
          return;
        }
        // No history — try geographic
        const geo = await cemeteryService.getGeographicShortlist(customerId!);
        if (cancelled) return;
        setGeoShortlist(geo);
        setShortlistMode(geo.length > 0 ? "geo" : "none");

        // Show cold-start nag once
        if (geo.length < 3 && !nagShownRef.current) {
          nagShownRef.current = true;
          setShowAddNag(true);
        }
      } catch {
        // Non-critical
      } finally {
        if (!cancelled) setShortlistLoaded(true);
      }
    }

    loadShortlist();
    return () => { cancelled = true; };
  }, [customerId]);

  // Debounced search
  const handleSearchInput = useCallback((text: string) => {
    setSearchText(text);
    setOpen(true);

    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!text.trim()) { setSearchResults([]); return; }

    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const data = await cemeteryService.getCemeteries({ search: text, per_page: 8 });
        setSearchResults(data.items);
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
  }, []);

  async function handleSelect(cemeteryId: string, cemeteryName: string) {
    setOpen(false);
    setSearchText(cemeteryName);

    // Load full cemetery record
    try {
      const cem = await cemeteryService.getCemetery(cemeteryId);
      setSelectedCemetery(cem);
      onChange(cemeteryId, cem);

      // Show county confirmation if not confirmed
      if (!cem.tax_county_confirmed) {
        setShowCountyConfirm(true);
        setCountyDraft(cem.county || "");
      } else {
        setShowCountyConfirm(false);
      }

      // Load equipment prefill
      try {
        const p = await cemeteryService.getEquipmentPrefill(cemeteryId);
        setPrefill(p);
        setPrefillVisible(true);
        onEquipmentPrefill(p);

        // Auto-dismiss after 5s
        if (prefillTimerRef.current) clearTimeout(prefillTimerRef.current);
        if (!p.nothing_needed) {
          prefillTimerRef.current = setTimeout(() => setPrefillVisible(false), 5000);
        }
      } catch {
        // Non-critical
      }
    } catch {
      // Fallback — at least call onChange with id
      onChange(cemeteryId, null);
    }
  }

  async function handleCreateInline(name: string) {
    setOpen(false);
    try {
      const newCem = await cemeteryService.createCemetery({ name });
      setSelectedCemetery(newCem);
      setSearchText(newCem.name);
      onChange(newCem.id, newCem);
      toast.success(`"${newCem.name}" added to your cemeteries`);
      // New cemeteries have no county confirmed — show prompt
      setShowCountyConfirm(true);
      setCountyDraft("");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Failed to create cemetery"));
    }
  }

  async function handleConfirmCounty() {
    if (!selectedCemetery || !countyDraft.trim()) return;
    setConfirmingCounty(true);
    try {
      await cemeteryService.updateCemetery(selectedCemetery.id, {
        county: countyDraft.trim(),
        tax_county_confirmed: true,
      });
      setShowCountyConfirm(false);
      toast.success("Tax county confirmed");
    } catch {
      // Non-critical
    } finally {
      setConfirmingCounty(false);
    }
  }

  function handleClear() {
    setSearchText("");
    setSelectedCemetery(null);
    setPrefill(null);
    setPrefillVisible(false);
    setShowCountyConfirm(false);
    onChange(null, null);
  }

  const showShortlist = open && !searchText.trim() && shortlistLoaded && (shortlist.length > 0 || geoShortlist.length > 0);
  const showSearch = open && searchText.trim().length > 0;
  const notFound = searchText.trim().length > 1 && searchResults.length === 0 && !searching;

  return (
    <div ref={containerRef} className={`relative ${className ?? ""}`} data-guided={guidedKey}>
      {/* Input */}
      <div className="relative">
        <Input
          placeholder="Search cemetery..."
          value={searchText}
          onChange={(e) => handleSearchInput(e.target.value)}
          onFocus={() => setOpen(true)}
          autoComplete="off"
          className="pr-16"
        />
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {value && (
            <button
              type="button"
              onClick={handleClear}
              className="p-0.5 rounded text-muted-foreground hover:text-foreground"
              title="Clear"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          <button
            type="button"
            onClick={() => setOpen(!open)}
            className="p-0.5 rounded text-muted-foreground hover:text-foreground"
          >
            <ChevronDown className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Dropdown */}
      {open && (
        <div className="absolute z-50 w-full mt-1 rounded-md border bg-white shadow-lg">
          {/* Shortlist section */}
          {showShortlist && (
            <div>
              <div className="px-3 pt-2 pb-1 flex items-center gap-1.5">
                {shortlistMode === "history" ? (
                  <>
                    <Clock className="h-3 w-3 text-muted-foreground" />
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Recent</span>
                  </>
                ) : (
                  <>
                    <MapPin className="h-3 w-3 text-muted-foreground" />
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Nearby</span>
                    <span className="text-xs text-muted-foreground ml-1">— shortlist builds as you take orders</span>
                  </>
                )}
              </div>

              {shortlistMode === "history" && shortlist.map((s) => {
                const loc = cemeteryLocationLine(s.city, s.county, s.state);
                return (
                  <button
                    key={s.cemetery_id}
                    type="button"
                    className="w-full text-left px-3 py-2 text-sm hover:bg-accent-subtle"
                    onClick={() => handleSelect(s.cemetery_id, s.cemetery_name)}
                  >
                    <div className="font-medium">{s.cemetery_name}</div>
                    {loc && <div className="text-[11px] text-muted-foreground">{loc}</div>}
                  </button>
                );
              })}

              {shortlistMode === "geo" && geoShortlist.map((s) => {
                const loc = cemeteryLocationLine(s.city, s.county, s.state);
                return (
                  <button
                    key={s.cemetery_id}
                    type="button"
                    className="w-full text-left px-3 py-2 text-sm hover:bg-accent-subtle"
                    onClick={() => handleSelect(s.cemetery_id, s.cemetery_name)}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{s.cemetery_name}</span>
                      {s.distance_miles != null && (
                        <span className="text-xs text-muted-foreground">{s.distance_miles.toFixed(1)} mi</span>
                      )}
                    </div>
                    {loc && <div className="text-[11px] text-muted-foreground">{loc}</div>}
                  </button>
                );
              })}

              <div className="border-t my-1" />
              <div className="px-3 py-1.5 flex items-center gap-1.5">
                <span className="text-xs text-muted-foreground">🔍</span>
                <input
                  className="flex-1 text-sm bg-transparent outline-none placeholder:text-muted-foreground"
                  placeholder="Search all cemeteries..."
                  value={searchText}
                  onChange={(e) => handleSearchInput(e.target.value)}
                />
              </div>
            </div>
          )}

          {/* Search results */}
          {showSearch && (
            <div className="max-h-48 overflow-y-auto">
              {searching && (
                <div className="px-3 py-2 text-xs text-muted-foreground">Searching...</div>
              )}
              {!searching && searchResults.map((c) => {
                const loc = cemeteryLocationLine(c.city, c.county, c.state);
                return (
                  <button
                    key={c.id}
                    type="button"
                    className="w-full text-left px-3 py-2 text-sm hover:bg-accent-subtle"
                    onClick={() => handleSelect(c.id, c.name)}
                  >
                    <div>{c.name}</div>
                    {loc && <div className="text-[11px] text-muted-foreground">{loc}</div>}
                  </button>
                );
              })}
              {notFound && (
                <button
                  type="button"
                  className="w-full text-left px-3 py-2 text-sm text-blue-600 hover:bg-accent-subtle flex items-center gap-2"
                  onClick={() => handleCreateInline(searchText)}
                >
                  <Plus className="h-3.5 w-3.5" />
                  Add &ldquo;{searchText}&rdquo; as new cemetery
                </button>
              )}
            </div>
          )}

          {/* No customer — search only hint */}
          {!showShortlist && !showSearch && !customerId && (
            <div className="px-3 py-2 text-xs text-muted-foreground">
              Type to search all cemeteries
            </div>
          )}
        </div>
      )}

      {/* Selected indicator */}
      {value && !open && (
        <p className="mt-0.5 text-xs text-green-700 flex items-center gap-1">
          <Check className="h-3 w-3" />
          Linked to cemetery record
        </p>
      )}

      {/* Tax county confirmation prompt */}
      {showCountyConfirm && (
        <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 p-3 space-y-2">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
            <p className="text-xs text-amber-800">
              Confirm tax county for this cemetery for accurate tax calculation
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Input
              value={countyDraft}
              onChange={(e) => setCountyDraft(e.target.value)}
              placeholder="County name"
              className="h-7 text-xs flex-1"
            />
            <Button
              type="button"
              size="sm"
              className="h-7 text-xs"
              onClick={handleConfirmCounty}
              disabled={confirmingCounty || !countyDraft.trim()}
            >
              {confirmingCounty ? "Saving..." : "Confirm"}
            </Button>
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground p-0.5"
              onClick={() => setShowCountyConfirm(false)}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Equipment prefill notification */}
      {prefill && prefillVisible && (
        <div className={`mt-2 rounded-md px-3 py-2 text-xs flex items-start gap-2 ${
          prefill.nothing_needed ? "bg-muted text-muted-foreground" : "bg-blue-50 text-blue-700"
        }`}>
          <span className="shrink-0">{prefill.nothing_needed ? "✓" : "🏕"}</span>
          <span className="flex-1">
            {prefill.equipment_note || (prefill.nothing_needed
              ? "Cemetery provides all equipment. No equipment charges needed."
              : `Equipment suggestion: ${prefill.suggestion_label}`)}
          </span>
          <button
            type="button"
            onClick={() => setPrefillVisible(false)}
            className="shrink-0 opacity-50 hover:opacity-100"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      )}

      {/* Cold-start nag — show once per session */}
      {showAddNag && customerId && geoShortlist.length < 3 && (
        <p className="mt-1 text-xs text-muted-foreground">
          💡{" "}
          <a href="/settings/cemeteries" className="underline hover:text-foreground">
            Add your common cemeteries
          </a>{" "}
          in Settings to enable smart suggestions here.
        </p>
      )}
    </div>
  );
}
