import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  documentsV2Service,
  type DocumentLogItem,
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
import { statusToneClass } from "@/components/documents/statusTone";

// Bounded document_type values seeded through Phase D-1 / D-2. Free
// text here made typos silently hide results — D-8 converts to a
// dropdown driven by this list. Extend as new document types ship.
const DOCUMENT_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All document types" },
  { value: "invoice", label: "Invoice" },
  { value: "statement", label: "Statement" },
  { value: "price_list", label: "Price list" },
  { value: "release_form", label: "Release form" },
  { value: "delivery_confirmation", label: "Delivery confirmation" },
  { value: "legacy_vault_print", label: "Legacy vault print" },
  { value: "social_service_certificate", label: "SS certificate" },
  { value: "safety_program", label: "Safety program" },
  { value: "signing_certificate", label: "Signing certificate" },
  { value: "ai_document", label: "AI-authored document" },
];

const ENTITY_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All entities" },
  { value: "sales_order", label: "Sales order" },
  { value: "invoice", label: "Invoice" },
  { value: "customer_statement", label: "Customer statement" },
  { value: "fh_case", label: "FH case" },
  { value: "disinterment_case", label: "Disinterment case" },
  { value: "price_list_version", label: "Price list version" },
  { value: "safety_program_generation", label: "Safety program gen" },
];

/**
 * DocumentLog — D-2 observability surface for canonical Documents.
 *
 * Shows every document produced in the last 7 days by default, with
 * filters for type / template / status / entity / intelligence-generated.
 * Click a row to open DocumentDetail.
 */
export default function DocumentLog() {
  const [params, setParams] = useSearchParams();
  const documentType = params.get("document_type") ?? "";
  const templateKey = params.get("template_key") ?? "";
  const entityType = params.get("entity_type") ?? "";
  const status = params.get("status") ?? "";
  const intelligenceGenerated = params.get("intelligence_generated") ?? "";

  const [items, setItems] = useState<DocumentLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const rows = await documentsV2Service.listDocumentLog({
        document_type: documentType || undefined,
        template_key: templateKey || undefined,
        entity_type: entityType || undefined,
        status: status || undefined,
        intelligence_generated:
          intelligenceGenerated === "true"
            ? true
            : intelligenceGenerated === "false"
              ? false
              : undefined,
        limit: 200,
      });
      setItems(rows);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [documentType, templateKey, entityType, status, intelligenceGenerated]);

  useEffect(() => {
    load();
  }, [load]);

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
    documentType !== "" ||
    templateKey !== "" ||
    entityType !== "" ||
    status !== "" ||
    intelligenceGenerated !== "";

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold">Document Log</h1>
        <p className="text-muted-foreground">
          Every document rendered in the last 7 days. Drill in to see
          entity linkage, AI provenance, and version history.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t pt-4">
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={documentType}
          onChange={(e) => updateParam("document_type", e.target.value)}
        >
          {DOCUMENT_TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <Input
          className="w-56"
          placeholder="Template key (e.g. email.statement)"
          value={templateKey}
          onChange={(e) => updateParam("template_key", e.target.value)}
        />
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={entityType}
          onChange={(e) => updateParam("entity_type", e.target.value)}
        >
          {ENTITY_TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={status}
          onChange={(e) => updateParam("status", e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="rendered">Rendered</option>
          <option value="signed">Signed</option>
          <option value="delivered">Delivered</option>
          <option value="archived">Archived</option>
          <option value="failed">Failed</option>
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={intelligenceGenerated}
          onChange={(e) =>
            updateParam("intelligence_generated", e.target.value)
          }
        >
          <option value="">All documents</option>
          <option value="true">AI-generated only</option>
          <option value="false">Non-AI only</option>
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
              <TableHead>Created</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Template</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Linked entity</TableHead>
              <TableHead>Source</TableHead>
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
                  No documents in this window.
                </TableCell>
              </TableRow>
            ) : (
              items.map((doc) => (
                <TableRow key={doc.id}>
                  <TableCell
                    className="text-xs text-muted-foreground"
                    title={doc.created_at}
                  >
                    {new Date(doc.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-xs">
                    {doc.document_type}
                  </TableCell>
                  <TableCell
                    className="max-w-[280px] truncate text-sm"
                    title={doc.title}
                  >
                    <Link
                      to={`/vault/documents/${doc.id}`}
                      className="underline"
                    >
                      {doc.title}
                    </Link>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {doc.template_key ?? "—"}
                    {doc.template_version != null && (
                      <span className="ml-1 text-muted-foreground">
                        v{doc.template_version}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge
                      className={
                        "text-[10px] " + statusToneClass(doc.status)
                      }
                    >
                      {doc.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {doc.entity_type ? (
                      <>
                        {doc.entity_type}
                        {doc.entity_id && (
                          <span className="ml-1 font-mono">
                            {doc.entity_id.slice(0, 8)}
                          </span>
                        )}
                      </>
                    ) : (
                      "—"
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {doc.intelligence_execution_id ? (
                      <Link
                        to={`/vault/intelligence/executions/${doc.intelligence_execution_id}`}
                        className="underline"
                        title="AI-generated — view Intelligence execution"
                      >
                        AI
                      </Link>
                    ) : doc.caller_workflow_run_id ? (
                      <span>Workflow</span>
                    ) : (
                      <span>{doc.caller_module?.split(".")[0] ?? "—"}</span>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
