import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  documentsV2Service,
  type DocumentDetail as DocDetail,
} from "@/services/documents-v2-service";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import DocumentSharesPanel from "@/components/documents/DocumentSharesPanel";
import { useAuth } from "@/contexts/auth-context";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/**
 * DocumentDetail — D-2 full-detail surface for canonical Documents.
 *
 * Summary header + linkage section + version history table + regenerate
 * dialog. Download links hit the tenant-scoped presigned R2 URL.
 */
export default function DocumentDetail() {
  const { documentId } = useParams<{ documentId: string }>();
  const { user } = useAuth();
  const [doc, setDoc] = useState<DocDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [regenOpen, setRegenOpen] = useState(false);
  const [regenReason, setRegenReason] = useState("");
  const [regenSubmitting, setRegenSubmitting] = useState(false);

  const load = useCallback(async () => {
    if (!documentId) return;
    setLoading(true);
    setErr(null);
    try {
      const d = await documentsV2Service.getDocument(documentId);
      setDoc(d);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    load();
  }, [load]);

  async function submitRegenerate() {
    if (!documentId) return;
    setRegenSubmitting(true);
    try {
      await documentsV2Service.regenerate(
        documentId,
        regenReason || "manual_regenerate"
      );
      setRegenOpen(false);
      setRegenReason("");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setRegenSubmitting(false);
    }
  }

  if (loading)
    return <div className="p-6 text-muted-foreground">Loading…</div>;
  if (err)
    return (
      <div className="p-6 text-destructive" role="alert">
        {err}
      </div>
    );
  if (!doc) return <div className="p-6">Document not found.</div>;

  return (
    <div className="space-y-6 p-6">
      <div>
        <Link
          to="/vault/documents"
          className="text-xs text-muted-foreground underline"
        >
          ← Document Log
        </Link>
        <h1 className="mt-1 text-2xl font-semibold">{doc.title}</h1>
        <div className="mt-1 flex items-center gap-2">
          <Badge variant="outline" className="text-[10px]">
            {doc.document_type}
          </Badge>
          <Badge variant="outline" className="text-[10px]">
            {doc.status}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {doc.file_size_bytes != null
              ? `${Math.round(doc.file_size_bytes / 1024)} KB`
              : ""}
          </span>
          <a
            href={documentsV2Service.getDownloadUrl(doc.id)}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Button size="sm" variant="outline">
              Download
            </Button>
          </a>
          <Button size="sm" onClick={() => setRegenOpen(true)}>
            Regenerate
          </Button>
        </div>
      </div>

      {/* Metadata */}
      <section className="grid gap-4 rounded-md border p-4 md:grid-cols-2">
        <Meta label="Template" value={
          doc.template_key
            ? `${doc.template_key} (v${doc.template_version ?? "?"})`
            : "—"
        } mono />
        <Meta
          label="Rendered"
          value={
            doc.rendered_at
              ? new Date(doc.rendered_at).toLocaleString()
              : "—"
          }
        />
        <Meta
          label="Created"
          value={new Date(doc.created_at).toLocaleString()}
        />
        <Meta
          label="Duration"
          value={
            doc.rendering_duration_ms != null
              ? `${doc.rendering_duration_ms}ms`
              : "—"
          }
        />
        <Meta
          label="MIME"
          value={doc.mime_type}
          mono
        />
        <Meta
          label="Context hash"
          value={doc.rendering_context_hash?.slice(0, 16) ?? "—"}
          mono
        />
      </section>

      {/* Linkage */}
      <section className="space-y-2 rounded-md border p-4">
        <h2 className="text-sm font-semibold uppercase text-muted-foreground">
          Linkage
        </h2>
        <div className="grid gap-2 text-sm md:grid-cols-2">
          <Meta
            label="Entity"
            value={
              doc.entity_type
                ? `${doc.entity_type} / ${doc.entity_id ?? "—"}`
                : "—"
            }
          />
          <Meta label="Sales order" value={doc.sales_order_id ?? "—"} mono />
          <Meta label="FH case" value={doc.fh_case_id ?? "—"} mono />
          <Meta
            label="Disinterment case"
            value={doc.disinterment_case_id ?? "—"}
            mono
          />
          <Meta label="Invoice" value={doc.invoice_id ?? "—"} mono />
          <Meta
            label="Customer statement"
            value={doc.customer_statement_id ?? "—"}
            mono
          />
          <Meta
            label="Price list version"
            value={doc.price_list_version_id ?? "—"}
            mono
          />
          <Meta
            label="Safety program generation"
            value={doc.safety_program_generation_id ?? "—"}
            mono
          />
          <Meta
            label="Caller module"
            value={doc.caller_module ?? "—"}
            mono
          />
          <Meta
            label="Workflow run"
            value={
              doc.caller_workflow_run_id ? (
                <Link
                  to={`/admin/workflow-runs/${doc.caller_workflow_run_id}`}
                  className="underline"
                >
                  {doc.caller_workflow_run_id.slice(0, 12)}…
                </Link>
              ) : (
                "—"
              )
            }
          />
          <Meta
            label="Intelligence execution"
            value={
              doc.intelligence_execution_id ? (
                <Link
                  to={`/vault/intelligence/executions/${doc.intelligence_execution_id}`}
                  className="underline"
                >
                  {doc.intelligence_execution_id.slice(0, 12)}…
                </Link>
              ) : (
                "—"
              )
            }
          />
        </div>
      </section>

      {/* Versions */}
      {/* D-6 — outbox panel (shares originated from this document) */}
      <DocumentSharesPanel
        documentId={doc.id}
        ownsDocument={user?.company_id === doc.company_id}
      />

      <section>
        <h2 className="mb-2 text-lg font-semibold">Version History</h2>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>Rendered</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>Current</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {doc.versions.map((v) => (
                <TableRow key={v.id}>
                  <TableCell className="font-mono text-xs">
                    v{v.version_number}
                  </TableCell>
                  <TableCell
                    className="text-xs text-muted-foreground"
                    title={v.rendered_at}
                  >
                    {new Date(v.rendered_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-xs">
                    {v.render_reason ?? "—"}
                  </TableCell>
                  <TableCell className="text-xs">
                    {v.file_size_bytes != null
                      ? `${Math.round(v.file_size_bytes / 1024)} KB`
                      : "—"}
                  </TableCell>
                  <TableCell>
                    {v.is_current ? (
                      <Badge variant="default" className="text-[10px]">
                        current
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground text-xs">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <a
                      href={documentsV2Service.getVersionDownloadUrl(
                        doc.id,
                        v.id
                      )}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <Button size="sm" variant="ghost">
                        Download
                      </Button>
                    </a>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </section>

      <Dialog open={regenOpen} onOpenChange={setRegenOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Regenerate document</DialogTitle>
            <DialogDescription>
              Produces a new version via the same template, flipping
              is_current on the prior version. For D-2, the context used
              matches whatever the caller passes — there is no "rebuild
              from source data" option in this UI.
            </DialogDescription>
          </DialogHeader>
          <Input
            placeholder="Reason (shown in version history)"
            value={regenReason}
            onChange={(e) => setRegenReason(e.target.value)}
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setRegenOpen(false)}
              disabled={regenSubmitting}
            >
              Cancel
            </Button>
            <Button
              onClick={submitRegenerate}
              disabled={regenSubmitting}
            >
              {regenSubmitting ? "Regenerating…" : "Regenerate"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Meta({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase text-muted-foreground">
        {label}
      </div>
      <div className={mono ? "font-mono text-xs" : "text-sm"}>{value}</div>
    </div>
  );
}
