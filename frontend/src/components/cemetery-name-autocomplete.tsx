/**
 * CemeteryNameAutocomplete — debounced search input for cemetery name fields.
 *
 * Dropdown sections:
 *  1. "Your Cemeteries"  — existing operational cemetery records (already_added=true)
 *  2. "OpenStreetMap"    — directory cache results (already_added=false)
 *  3. "Use as typed"     — always available so the user can add any name
 *
 * On selection, fires `onSelect` with the full result so the parent can
 * auto-populate city / county / state / lat / lng fields.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Check, ChevronDown, MapPin, X } from "lucide-react";
import apiClient from "@/lib/api-client";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface AutocompleteResult {
  cemetery_id: string | null;
  place_id: string | null;
  name: string;
  city: string | null;
  state: string | null;
  county: string | null;
  latitude: number | null;
  longitude: number | null;
  already_added: boolean;
  source: string;
}

interface CemeteryNameAutocompleteProps {
  value: string;
  onChange: (name: string) => void;
  onSelect: (result: AutocompleteResult | null) => void;
  placeholder?: string;
  className?: string;
  /** When true, shows "Already in your list" confirmation badge */
  showAlreadyAdded?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CemeteryNameAutocomplete({
  value,
  onChange,
  onSelect,
  placeholder = "Cemetery name...",
  className,
  showAlreadyAdded = true,
}: CemeteryNameAutocompleteProps) {
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState<AutocompleteResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastSelected, setLastSelected] = useState<AutocompleteResult | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const fetchResults = useCallback((q: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) {
      setResults([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const { data } = await apiClient.get<AutocompleteResult[]>(
          "/cemeteries/autocomplete",
          { params: { q, limit: 8 } },
        );
        setResults(data);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
  }, []);

  function handleInput(text: string) {
    onChange(text);
    setLastSelected(null);
    onSelect(null);
    setOpen(true);
    fetchResults(text);
  }

  function handleFocus() {
    if (value.trim() && !lastSelected) {
      setOpen(true);
      fetchResults(value);
    }
  }

  function handleSelect(result: AutocompleteResult) {
    onChange(result.name);
    setLastSelected(result);
    onSelect(result);
    setOpen(false);
    setResults([]);
  }

  function handleClear() {
    onChange("");
    setLastSelected(null);
    onSelect(null);
    setResults([]);
    setOpen(false);
  }

  const existing = results.filter((r) => r.already_added);
  const suggestions = results.filter((r) => !r.already_added);

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      {/* Input */}
      <div className="relative">
        <input
          type="text"
          value={value}
          onChange={(e) => handleInput(e.target.value)}
          onFocus={handleFocus}
          placeholder={placeholder}
          autoComplete="off"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 pr-16"
        />
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
          {value && (
            <button
              type="button"
              onClick={handleClear}
              className="p-0.5 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
      </div>

      {/* Confirmation badges */}
      {lastSelected && !lastSelected.already_added && lastSelected.source !== "manual" && (
        <p className="mt-0.5 text-xs text-green-700 flex items-center gap-1">
          <Check className="h-3 w-3" />
          Details filled from OpenStreetMap
        </p>
      )}
      {lastSelected && lastSelected.already_added && showAlreadyAdded && (
        <p className="mt-0.5 text-xs text-amber-700 flex items-center gap-1">
          <Check className="h-3 w-3" />
          Already in your cemetery list
        </p>
      )}

      {/* Dropdown */}
      {open && value.trim().length > 0 && (
        <div className="absolute z-50 w-full mt-1 rounded-md border bg-white shadow-lg max-h-64 overflow-y-auto">
          {loading && (
            <div className="px-3 py-2 text-xs text-muted-foreground">Searching...</div>
          )}

          {/* Existing cemetery section */}
          {!loading && existing.length > 0 && (
            <>
              <div className="px-3 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wide bg-gray-50 border-b">
                Your Cemeteries
              </div>
              {existing.map((r) => (
                <button
                  key={r.cemetery_id ?? r.name}
                  type="button"
                  onClick={() => handleSelect(r)}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-accent flex items-start gap-2"
                >
                  <Check className="h-3.5 w-3.5 text-green-600 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-medium">{r.name}</div>
                    {(r.city || r.county || r.state) && (
                      <div className="text-xs text-muted-foreground">
                        {[r.city, r.county ? `${r.county} County` : null, r.state]
                          .filter(Boolean)
                          .join(", ")}
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </>
          )}

          {/* OSM suggestions section */}
          {!loading && suggestions.length > 0 && (
            <>
              {existing.length > 0 && <div className="border-t" />}
              <div className="px-3 py-1 text-xs font-medium text-muted-foreground uppercase tracking-wide bg-gray-50 border-b">
                <span className="flex items-center gap-1">
                  <MapPin className="h-3 w-3" />
                  OpenStreetMap
                </span>
              </div>
              {suggestions.map((r) => (
                <button
                  key={r.place_id ?? r.name}
                  type="button"
                  onClick={() => handleSelect(r)}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-accent"
                >
                  <div className="font-medium">{r.name}</div>
                  {(r.city || r.county || r.state) && (
                    <div className="text-xs text-muted-foreground">
                      {[r.city, r.county ? `${r.county} County` : null, r.state]
                        .filter(Boolean)
                        .join(", ")}
                    </div>
                  )}
                </button>
              ))}
            </>
          )}

          {/* Use as typed */}
          {!loading && value.trim() && (
            <>
              {(existing.length > 0 || suggestions.length > 0) && <div className="border-t" />}
              <button
                type="button"
                onClick={() =>
                  handleSelect({
                    cemetery_id: null,
                    place_id: null,
                    name: value.trim(),
                    city: null,
                    state: null,
                    county: null,
                    latitude: null,
                    longitude: null,
                    already_added: false,
                    source: "manual",
                  })
                }
                className="w-full text-left px-3 py-2 text-sm text-muted-foreground hover:bg-accent"
              >
                Use &ldquo;{value.trim()}&rdquo; as entered
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
