/**
 * Searchable document picker — replaces the pasted-UUID input in the
 * Create Envelope wizard (D-8 polish of a D-4 deferred item).
 *
 * Behavior:
 *   - Loads the latest tenant documents via `listDocumentLog` (D-2 log).
 *   - Client-side filter by title, template_key, document_type, or
 *     id-prefix — the log endpoint doesn't accept a free-text search.
 *   - Optional document_type filter (populated from the loaded set).
 *   - Clicking a row selects the document and lifts its id via
 *     `onChange(id)`.
 *   - Advanced-user fallback: toggle a "Paste UUID" input for cases
 *     where the document isn't in the recent list (historical docs,
 *     test fixtures, etc).
 *
 * Intentionally presentational — the parent wizard owns the selected
 * id and submits it. Keeps this reusable for future callers (workflow
 * designer's `document_id` fields, regenerate-from-template flows, etc).
 */
import { useEffect, useMemo, useState } from "react";
import {
  documentsV2Service,
  type DocumentLogItem,
} from "@/services/documents-v2-service";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface Props {
  value: string;
  onChange: (documentId: string) => void;
  /** Narrow the candidate list to a specific document_type if known. */
  documentType?: string;
  /** Max items to fetch from the log endpoint. Default 100. */
  fetchLimit?: number;
}

const STATUS_BADGE: Record<string, string> = {
  current: "bg-emerald-100 text-emerald-800",
  superseded: "bg-slate-100 text-slate-600",
  draft: "bg-amber-100 text-amber-800",
  failed: "bg-red-100 text-red-800",
};

export default function DocumentPicker({
  value,
  onChange,
  documentType,
  fetchLimit = 100,
}: Props) {
  const [items, setItems] = useState<DocumentLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>(documentType ?? "");
  const [showPasteFallback, setShowPasteFallback] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setErr(null);
    documentsV2Service
      .listDocumentLog({
        document_type: typeFilter || undefined,
        limit: fetchLimit,
      })
      .then((rows) => {
        if (!alive) return;
        setItems(rows);
      })
      .catch((e: unknown) => {
        if (!alive) return;
        const msg =
          (e as { response?: { data?: { detail?: string } } }).response?.data
            ?.detail ?? (e instanceof Error ? e.message : String(e));
        setErr(msg);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [typeFilter, fetchLimit]);

  // Gather unique document_types from loaded rows to populate the
  // type filter dropdown. Memoized so it doesn't recompute on every
  // search keystroke.
  const availableTypes = useMemo(() => {
    const set = new Set<string>();
    for (const it of items) set.add(it.document_type);
    return Array.from(set).sort();
  }, [items]);

  const filtered = useMemo(() => {
    if (!search.trim()) return items;
    const q = search.trim().toLowerCase();
    return items.filter((it) => {
      if (it.title.toLowerCase().includes(q)) return true;
      if (it.id.toLowerCase().startsWith(q)) return true;
      if ((it.template_key ?? "").toLowerCase().includes(q)) return true;
      if (it.document_type.toLowerCase().includes(q)) return true;
      return false;
    });
  }, [items, search]);

  const selected = items.find((it) => it.id === value) ?? null;

  return (
    <div className="space-y-2">
      {selected && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium text-emerald-950">
                {selected.title}
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-emerald-800">
                <Badge className="bg-emerald-100 text-emerald-900">
                  {selected.document_type}
                </Badge>
                {selected.template_key && (
                  <span className="font-mono text-[11px]">
                    {selected.template_key}
                  </span>
                )}
                <span>·</span>
                <span>
                  {selected.rendered_at
                    ? new Date(selected.rendered_at).toLocaleString()
                    : new Date(selected.created_at).toLocaleString()}
                </span>
              </div>
              <div className="mt-1 font-mono text-[11px] text-emerald-700">
                {selected.id}
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onChange("")}
              className="text-emerald-900 hover:bg-emerald-100"
            >
              Change
            </Button>
          </div>
        </div>
      )}

      {!selected && (
        <>
          <div className="flex items-center gap-2">
            <Input
              placeholder="Search by title, type, or ID…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1"
            />
            {availableTypes.length > 1 && (
              <select
                className="h-9 rounded-md border bg-transparent px-2 text-sm"
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
              >
                <option value="">All types</option>
                {availableTypes.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            )}
          </div>

          {loading && (
            <div className="rounded-md border bg-muted/10 p-4 text-center text-sm text-muted-foreground">
              Loading documents…
            </div>
          )}
          {err && (
            <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
              {err}
            </div>
          )}

          {!loading && !err && (
            <div className="max-h-80 overflow-y-auto rounded-md border">
              {filtered.length === 0 ? (
                <div className="p-4 text-center text-sm text-muted-foreground">
                  {items.length === 0
                    ? "No documents found for this tenant. Paste a UUID below."
                    : "No documents match your search."}
                </div>
              ) : (
                <ul className="divide-y">
                  {filtered.map((it) => (
                    <li key={it.id}>
                      <button
                        type="button"
                        onClick={() => onChange(it.id)}
                        className="w-full cursor-pointer px-3 py-2 text-left hover:bg-muted/20"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-sm font-medium">
                              {it.title}
                            </div>
                            <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                              <Badge
                                className={
                                  STATUS_BADGE[it.status] ?? STATUS_BADGE.current
                                }
                              >
                                {it.document_type}
                              </Badge>
                              {it.template_key && (
                                <span className="font-mono text-[11px]">
                                  {it.template_key}
                                </span>
                              )}
                              <span>·</span>
                              <span>
                                {new Date(
                                  it.rendered_at ?? it.created_at
                                ).toLocaleDateString()}
                              </span>
                              <span>·</span>
                              <span className="font-mono text-[10px] opacity-70">
                                {it.id.slice(0, 8)}…
                              </span>
                            </div>
                          </div>
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <div className="text-xs">
            <button
              type="button"
              onClick={() => setShowPasteFallback((v) => !v)}
              className="text-muted-foreground underline-offset-2 hover:underline"
            >
              {showPasteFallback ? "Hide" : "Advanced:"} paste a document UUID
            </button>
          </div>
          {showPasteFallback && (
            <Input
              placeholder="document_id (UUID)"
              value={value}
              onChange={(e) => onChange(e.target.value)}
              className="font-mono"
            />
          )}
        </>
      )}
    </div>
  );
}
