import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  documentsV2Service,
  type DocumentTemplateListItem,
} from "@/services/documents-v2-service";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/**
 * DocumentTemplateLibrary — Phase D-2 read surface.
 *
 * Lists every template (platform + current tenant), with filters for
 * document_type / output_format / scope / status / search. Mirrors
 * IntelligencePromptLibrary in layout + filter-persistence pattern.
 */
export default function DocumentTemplateLibrary() {
  const [params, setParams] = useSearchParams();
  const search = params.get("search") ?? "";
  const documentType = params.get("document_type") ?? "";
  const outputFormat = params.get("output_format") ?? "";
  const scope = params.get("scope") ?? "";
  const status = params.get("status") ?? "active";

  const [items, setItems] = useState<DocumentTemplateListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const res = await documentsV2Service.listTemplates({
        search: search || undefined,
        document_type: documentType || undefined,
        output_format: outputFormat || undefined,
        scope: (scope || undefined) as "platform" | "tenant" | "both" | undefined,
        status: status as "active" | "all",
        limit: 500,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [search, documentType, outputFormat, scope, status]);

  useEffect(() => {
    load();
  }, [load]);

  const documentTypeOptions = useMemo(() => {
    const set = new Set<string>();
    items.forEach((i) => set.add(i.document_type));
    return Array.from(set).sort();
  }, [items]);

  function updateParam(key: string, value: string) {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) next.set(key, value);
      else next.delete(key);
      return next;
    });
  }

  function resetFilters() {
    setParams({});
  }

  const hasFilters =
    search !== "" ||
    documentType !== "" ||
    outputFormat !== "" ||
    scope !== "" ||
    status !== "active";

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold">Document Templates</h1>
        <p className="text-muted-foreground">
          Managed templates for PDF + email output. Platform templates are
          available to every tenant; tenant-specific rows override them.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t pt-4">
        <Input
          className="w-64"
          placeholder="Search key / description"
          value={search}
          onChange={(e) => updateParam("search", e.target.value)}
          data-testid="template-search-input"
        />
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={documentType}
          onChange={(e) => updateParam("document_type", e.target.value)}
        >
          <option value="">All document types</option>
          {documentTypeOptions.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={outputFormat}
          onChange={(e) => updateParam("output_format", e.target.value)}
        >
          <option value="">All formats</option>
          <option value="pdf">PDF</option>
          <option value="html">HTML (email)</option>
          <option value="text">Text</option>
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={scope}
          onChange={(e) => updateParam("scope", e.target.value)}
        >
          <option value="">Platform + tenant</option>
          <option value="platform">Platform only</option>
          <option value="tenant">Tenant only</option>
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={status}
          onChange={(e) => updateParam("status", e.target.value)}
        >
          <option value="active">Active</option>
          <option value="all">All</option>
        </select>
        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={resetFilters}>
            Reset
          </Button>
        )}
      </div>

      {err && (
        <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
          {err}
        </div>
      )}

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Template Key</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>Document Type</TableHead>
              <TableHead>Format</TableHead>
              <TableHead>Scope</TableHead>
              <TableHead className="text-right">Version</TableHead>
              <TableHead>Activated</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  Loading…
                </TableCell>
              </TableRow>
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={7}
                  className="py-6 text-center text-muted-foreground"
                >
                  No templates match filters.{" "}
                  {hasFilters && (
                    <button
                      className="underline"
                      onClick={resetFilters}
                      type="button"
                    >
                      Reset
                    </button>
                  )}
                </TableCell>
              </TableRow>
            ) : (
              items.map((t) => (
                <TableRow key={t.id}>
                  <TableCell>
                    <Link
                      to={`/vault/documents/templates/${t.id}`}
                      className="font-mono text-xs underline"
                    >
                      {t.template_key}
                    </Link>
                    {t.has_draft && (
                      <Badge
                        className="ml-2 bg-amber-500/15 text-amber-900 text-[10px] hover:bg-amber-500/20"
                        variant="outline"
                        title="Draft version in progress"
                      >
                        draft
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell
                    className="max-w-[320px] truncate text-sm text-muted-foreground"
                    title={t.description ?? ""}
                  >
                    {t.description || "—"}
                  </TableCell>
                  <TableCell className="text-xs">
                    {t.document_type}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-[10px]">
                      {t.output_format}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        t.scope === "platform" ? "secondary" : "default"
                      }
                      className="text-[10px]"
                    >
                      {t.scope}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    {t.current_version_number ?? "—"}
                  </TableCell>
                  <TableCell
                    className="text-xs text-muted-foreground"
                    title={t.current_version_activated_at ?? ""}
                  >
                    {t.current_version_activated_at
                      ? new Date(
                          t.current_version_activated_at
                        ).toLocaleDateString()
                      : "—"}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {total > 0 && (
        <div className="text-xs text-muted-foreground">
          {total} template{total !== 1 ? "s" : ""}
        </div>
      )}
    </div>
  );
}
