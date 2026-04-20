import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  documentsV2Service,
  type InboxItem,
} from "@/services/documents-v2-service";
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
import { statusToneClass } from "@/components/documents/statusTone";

/**
 * D-6 admin inbox — documents shared TO this tenant from others.
 * D-8 adds per-user read tracking: unread count, row-level unread
 * highlight, Mark-all-read action, auto-mark on click-through.
 *
 * Tenant-user-facing inbox is a later phase; D-6/D-8 ship admin-only.
 */
export default function DocumentInbox() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const documentType = params.get("document_type") ?? "";
  const includeRevoked = params.get("include_revoked") === "true";
  const unreadOnly = params.get("unread") === "true";

  const [items, setItems] = useState<InboxItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [marking, setMarking] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const rows = await documentsV2Service.listInbox({
        document_type: documentType || undefined,
        include_revoked: includeRevoked,
        limit: 200,
      });
      setItems(rows);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [documentType, includeRevoked]);

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

  async function handleOpen(item: InboxItem) {
    // Mark-read first so the badge updates on return — but don't
    // block navigation on the API round-trip.
    if (!item.is_read) {
      documentsV2Service
        .markShareRead(item.share_id)
        .then(() => {
          setItems((prev) =>
            prev.map((i) =>
              i.share_id === item.share_id
                ? { ...i, is_read: true, read_at: new Date().toISOString() }
                : i
            )
          );
        })
        .catch(() => {
          /* non-fatal — next reload will reconcile */
        });
    }
    navigate(`/vault/documents/${item.document_id}`);
  }

  async function handleMarkAllRead() {
    setMarking(true);
    try {
      await documentsV2Service.markAllInboxRead();
      setItems((prev) =>
        prev.map((i) =>
          i.is_read
            ? i
            : { ...i, is_read: true, read_at: new Date().toISOString() }
        )
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setMarking(false);
    }
  }

  const activeItems = items.filter((i) => !i.revoked_at);
  const unreadCount = activeItems.filter((i) => !i.is_read).length;
  const visibleItems = unreadOnly
    ? items.filter((i) => !i.is_read)
    : items;

  return (
    <div className="space-y-6 p-6">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-3xl font-bold">Document Inbox</h1>
          {unreadCount > 0 && (
            <Badge className="bg-blue-600 text-white hover:bg-blue-600">
              {unreadCount} unread
            </Badge>
          )}
        </div>
        <p className="text-muted-foreground">
          Documents shared with this tenant from others — statements,
          delivery confirmations, legacy vault prints, and more. Each
          item lives in the owner tenant; revocation cuts off future
          access but not already-downloaded copies.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t pt-4">
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={documentType}
          onChange={(e) => updateParam("document_type", e.target.value)}
        >
          <option value="">All document types</option>
          <option value="statement">Statements</option>
          <option value="delivery_confirmation">Delivery confirmations</option>
          <option value="legacy_vault_print">Legacy vault prints</option>
          <option value="invoice">Invoices</option>
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) =>
              updateParam("unread", e.target.checked ? "true" : "")
            }
          />
          Unread only
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={includeRevoked}
            onChange={(e) =>
              updateParam("include_revoked", e.target.checked ? "true" : "")
            }
          />
          Include revoked
        </label>
        <div className="text-sm text-muted-foreground">
          {activeItems.length} active share
          {activeItems.length === 1 ? "" : "s"}
        </div>
        <div className="ml-auto">
          <Button
            variant="outline"
            size="sm"
            disabled={marking || unreadCount === 0}
            onClick={handleMarkAllRead}
          >
            {marking ? "Marking…" : "Mark all read"}
          </Button>
        </div>
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
              <TableHead className="w-6"></TableHead>
              <TableHead>Received</TableHead>
              <TableHead>From</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Reason</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  Loading…
                </TableCell>
              </TableRow>
            ) : visibleItems.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={7}
                  className="py-6 text-center text-muted-foreground"
                >
                  {unreadOnly
                    ? "No unread documents."
                    : "No documents in your inbox."}
                </TableCell>
              </TableRow>
            ) : (
              visibleItems.map((i) => {
                const unread = !i.is_read && !i.revoked_at;
                return (
                  <TableRow
                    key={i.share_id}
                    className={unread ? "bg-blue-50/60" : ""}
                  >
                    <TableCell className="w-6 px-2">
                      {unread ? (
                        <span
                          className="inline-block h-2 w-2 rounded-full bg-blue-600"
                          title="Unread"
                          aria-label="Unread"
                        />
                      ) : null}
                    </TableCell>
                    <TableCell
                      className="text-xs text-muted-foreground"
                      title={i.granted_at}
                    >
                      {new Date(i.granted_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-xs">
                      {i.owner_company_name ?? i.owner_company_id.slice(0, 8)}
                    </TableCell>
                    <TableCell className="text-xs">
                      {i.document_type}
                    </TableCell>
                    <TableCell
                      className={
                        "max-w-[360px] truncate text-sm " +
                        (unread ? "font-semibold" : "")
                      }
                      title={i.document_title}
                    >
                      <Link
                        to={`/vault/documents/${i.document_id}`}
                        onClick={(e) => {
                          e.preventDefault();
                          handleOpen(i);
                        }}
                        className="underline"
                      >
                        {i.document_title}
                      </Link>
                    </TableCell>
                    <TableCell className="max-w-[280px] truncate text-xs text-muted-foreground">
                      {i.reason ?? "—"}
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={
                          "text-[10px] " +
                          statusToneClass(i.revoked_at ? "revoked" : "active")
                        }
                      >
                        {i.revoked_at ? "revoked" : "active"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
