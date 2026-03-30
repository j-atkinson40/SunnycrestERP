import { useCallback, useEffect, useRef, useState } from "react";
import { Check, ExternalLink, Info, Loader2, Plus, X } from "lucide-react";
import { cn } from "@/lib/utils";
import apiClient from "@/lib/api-client";
import type { CustomerListItem } from "@/types/customer";

interface FuneralHomePickerProps {
  value: string | null;
  displayValue: string;
  onChange: (id: string | null, name: string) => void;
  className?: string;
  guidedKey?: string;
}

interface NewCustomerBanner {
  id: string;
  name: string;
}

export function FuneralHomePicker({
  value,
  displayValue,
  onChange,
  className,
  guidedKey,
}: FuneralHomePickerProps) {
  const [query, setQuery] = useState(displayValue);
  const [results, setResults] = useState<CustomerListItem[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const [newBanner, setNewBanner] = useState<NewCustomerBanner | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync display value when parent changes value externally
  useEffect(() => {
    setQuery(displayValue);
  }, [displayValue]);

  // Click-outside to close
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const search = useCallback(async (q: string) => {
    if (q.length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    try {
      const res = await apiClient.get("/customers", {
        params: { search: q, per_page: 8, include_hidden: false },
      });
      setResults(res.data.items ?? []);
      setOpen(true);
      setActiveIdx(-1);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const q = e.target.value;
    setQuery(q);
    // Clear selection if user edits
    if (value) onChange(null, q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(q), 300);
  }

  function selectCustomer(c: CustomerListItem) {
    setQuery(c.name);
    onChange(c.id, c.name);
    setOpen(false);
    setResults([]);
  }

  async function handleInlineCreate() {
    if (!query.trim() || creating) return;
    setCreating(true);
    try {
      const res = await apiClient.post("/customers/quick-create", {
        name: query.trim(),
        customer_type: "funeral_home",
      });
      const customer = res.data;
      setQuery(customer.name);
      onChange(customer.id, customer.name);
      setOpen(false);
      setResults([]);
      setNewBanner({ id: customer.id, name: customer.name });
    } catch {
      // silently fail — user can retry
    } finally {
      setCreating(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    const total = results.length + (showInlineCreate ? 1 : 0);
    if (!open || total === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, total - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, -1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (activeIdx >= 0 && activeIdx < results.length) {
        selectCustomer(results[activeIdx]);
      } else if (activeIdx === results.length && showInlineCreate) {
        void handleInlineCreate();
      }
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  const showInlineCreate = query.trim().length >= 2 && !loading;

  return (
    <div ref={containerRef} className={cn("relative", className)} data-guided={guidedKey}>
      {/* Input */}
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleInputChange}
          onFocus={() => { if (query.length >= 2) search(query); }}
          onKeyDown={handleKeyDown}
          placeholder="Search funeral home..."
          className={cn(
            "flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-xs",
            "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
            value && "pr-7",
          )}
        />
        {value && !loading && (
          <Check className="absolute right-2.5 top-2.5 h-4 w-4 text-green-500 pointer-events-none" />
        )}
        {loading && (
          <Loader2 className="absolute right-2.5 top-2.5 h-4 w-4 animate-spin text-muted-foreground pointer-events-none" />
        )}
      </div>

      {/* Dropdown */}
      {open && (results.length > 0 || showInlineCreate) && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-60 overflow-y-auto rounded-md border border-gray-200 bg-white shadow-md">
          {results.length === 0 && (
            <div className="px-3 py-2 text-xs text-muted-foreground">
              No results for &ldquo;{query}&rdquo;
            </div>
          )}
          {results.map((c, idx) => (
            <button
              key={c.id}
              type="button"
              onMouseDown={(e) => { e.preventDefault(); selectCustomer(c); }}
              className={cn(
                "w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center gap-2",
                idx === activeIdx && "bg-blue-50",
              )}
            >
              <span className="flex-1 truncate">{c.name}</span>
              {c.city && (
                <span className="text-xs text-muted-foreground shrink-0">
                  {c.city}{c.state ? `, ${c.state}` : ""}
                </span>
              )}
            </button>
          ))}
          {showInlineCreate && (
            <button
              type="button"
              onMouseDown={(e) => { e.preventDefault(); void handleInlineCreate(); }}
              disabled={creating}
              className={cn(
                "w-full text-left px-3 py-2 text-sm font-medium text-blue-700",
                "flex items-center gap-2 border-t border-gray-100 hover:bg-blue-50",
                results.length === activeIdx && "bg-blue-50",
                creating && "opacity-60 cursor-not-allowed",
              )}
            >
              {creating ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />
              ) : (
                <Plus className="h-3.5 w-3.5 shrink-0" />
              )}
              <span>
                {creating
                  ? "Creating\u2026"
                  : `Add "${query.trim()}" as new funeral home`}
              </span>
            </button>
          )}
        </div>
      )}

      {/* New customer banner */}
      {newBanner && (
        <div className="mt-2 flex items-start gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800">
          <Info className="h-3.5 w-3.5 mt-0.5 shrink-0 text-blue-500" />
          <span className="flex-1">
            New customer created. Complete their profile later:{" "}
            <a
              href={`/customers/${newBanner.id}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-0.5 font-medium underline underline-offset-2 hover:text-blue-900"
            >
              Open {newBanner.name}
              <ExternalLink className="h-3 w-3" />
            </a>
          </span>
          <button
            type="button"
            onClick={() => setNewBanner(null)}
            className="text-blue-400 hover:text-blue-600"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
