import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  documentsV2Service,
  type DeliveryListItem,
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

/**
 * D-7 delivery log — every email / SMS / future-channel send routed
 * through DeliveryService appears here, scoped to the current tenant.
 *
 * Status meanings:
 *   pending    — row created, not yet dispatched
 *   sending    — in flight
 *   sent       — provider accepted
 *   delivered  — provider webhook confirmed (D-7 leaves this empty;
 *                requires webhook wiring — DEBT.md)
 *   bounced    — hard bounce reported
 *   failed     — retries exhausted or non-retryable error
 *   rejected   — pre-send rejection (e.g. SMS stub)
 *
 * D-8: status colors come from the shared `statusTone` palette so the
 * Delivery / Document / Inbox logs share one legend.
 */

export default function DeliveryLog() {
  const [params, setParams] = useSearchParams();
  const channel = params.get("channel") ?? "";
  const statusFilter = params.get("status") ?? "";
  const recipient = params.get("recipient") ?? "";
  const templateKey = params.get("template_key") ?? "";

  const [items, setItems] = useState<DeliveryListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const rows = await documentsV2Service.listDeliveries({
        channel: channel || undefined,
        status: statusFilter || undefined,
        recipient_search: recipient || undefined,
        template_key: templateKey || undefined,
        limit: 200,
      });
      setItems(rows);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [channel, statusFilter, recipient, templateKey]);

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
    channel !== "" || statusFilter !== "" || recipient !== "" || templateKey !== "";

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold">Delivery Log</h1>
        <p className="text-muted-foreground">
          Every email / SMS / future-channel send in the last 7 days.
          Delivery rows capture the recipient, template, provider message
          ID, and full provider response for debugging. Click a row for
          detail + resend.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t pt-4">
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={channel}
          onChange={(e) => updateParam("channel", e.target.value)}
        >
          <option value="">All channels</option>
          <option value="email">Email</option>
          <option value="sms">SMS</option>
        </select>
        <select
          className="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
          value={statusFilter}
          onChange={(e) => updateParam("status", e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="sent">Sent</option>
          <option value="delivered">Delivered</option>
          <option value="bounced">Bounced</option>
          <option value="failed">Failed</option>
          <option value="rejected">Rejected</option>
        </select>
        <Input
          className="w-56"
          placeholder="Recipient search"
          value={recipient}
          onChange={(e) => updateParam("recipient", e.target.value)}
        />
        <Input
          className="w-56"
          placeholder="Template key"
          value={templateKey}
          onChange={(e) => updateParam("template_key", e.target.value)}
        />
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
              <TableHead>Sent</TableHead>
              <TableHead>Channel</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Recipient</TableHead>
              <TableHead>Subject / Template</TableHead>
              <TableHead>Provider</TableHead>
              <TableHead>Error</TableHead>
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
                  No deliveries in this window.
                </TableCell>
              </TableRow>
            ) : (
              items.map((d) => (
                <TableRow key={d.id}>
                  <TableCell
                    className="text-xs text-muted-foreground"
                    title={d.sent_at ?? d.created_at}
                  >
                    {new Date(d.sent_at ?? d.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-[10px]">
                      {d.channel}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] uppercase ${statusToneClass(
                        d.status
                      )}`}
                    >
                      {d.status}
                    </span>
                  </TableCell>
                  <TableCell className="text-xs">
                    <Link
                      to={`/admin/documents/deliveries/${d.id}`}
                      className="underline"
                    >
                      {d.recipient_value}
                    </Link>
                    {d.recipient_name && (
                      <span className="ml-1 text-muted-foreground">
                        ({d.recipient_name})
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="max-w-[280px] truncate text-xs">
                    {d.subject ?? "—"}
                    {d.template_key && (
                      <div className="font-mono text-[10px] text-muted-foreground">
                        {d.template_key}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {d.provider ?? "—"}
                  </TableCell>
                  <TableCell
                    className="max-w-[200px] truncate text-xs text-destructive"
                    title={d.error_message ?? ""}
                  >
                    {d.error_message ?? ""}
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
