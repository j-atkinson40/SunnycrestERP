import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  signingService,
  type EnvelopeListItem,
} from "@/services/signing-service";
import { Button } from "@/components/ui/button";
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
 * Signing envelope library — tenant-scoped list of envelopes with
 * filters for status and document. Clicking a row opens the detail page.
 */
export default function SigningEnvelopeLibrary() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const statusFilter = params.get("status") ?? "";

  const [items, setItems] = useState<EnvelopeListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const rows = await signingService.listEnvelopes({
        status: statusFilter || undefined,
        limit: 200,
      });
      setItems(rows);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  function updateParam(k: string, v: string) {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (v) next.set(k, v);
      else next.delete(k);
      return next;
    });
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Signing Envelopes</h1>
          <p className="text-muted-foreground">
            Native e-signature envelopes for this tenant. Sent + in-progress
            envelopes have pending signers; completed envelopes have a
            Certificate of Completion attached.
          </p>
        </div>
        <Button
          onClick={() => navigate("/vault/documents/signing/new")}
        >
          New envelope
        </Button>
      </div>

      <div className="flex items-center gap-3 border-t pt-4">
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={statusFilter}
          onChange={(e) => updateParam("status", e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="sent">Sent</option>
          <option value="in_progress">In progress</option>
          <option value="completed">Completed</option>
          <option value="declined">Declined</option>
          <option value="voided">Voided</option>
          <option value="expired">Expired</option>
        </select>
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
              <TableHead>Subject</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Routing</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Expires</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center">
                  Loading…
                </TableCell>
              </TableRow>
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={5}
                  className="py-6 text-center text-muted-foreground"
                >
                  No envelopes yet.
                </TableCell>
              </TableRow>
            ) : (
              items.map((e) => (
                <TableRow key={e.id}>
                  <TableCell>
                    <Link
                      to={`/vault/documents/signing/${e.id}`}
                      className="font-medium underline"
                    >
                      {e.subject}
                    </Link>
                    {e.description && (
                      <div className="text-xs text-muted-foreground truncate max-w-[480px]">
                        {e.description}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-[10px]">
                      {e.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs">
                    {e.routing_type}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(e.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {e.expires_at
                      ? new Date(e.expires_at).toLocaleDateString()
                      : "—"}
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
