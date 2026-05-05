/**
 * Settings → Calendar consent — Phase W-4b Layer 1 Calendar Step 4.1.
 *
 * Per BRIDGEABLE_MASTER §3.26.16.6 + §3.26.16.14 + §3.26.11.10
 * cross-tenant Focus consent precedent: bilateral consent state
 * machine for PTR `calendar_freebusy_consent`. Tenant admins manage
 * per-relationship consent state through this surface.
 *
 * Four consent states visualized via badge:
 *   default          → gray "Privacy-preserving"
 *   pending_outbound → status-warning "Awaiting partner"
 *   pending_inbound  → status-info "Partner requested upgrade"
 *                      (with [Accept] inline action)
 *   active           → status-success "Full details" (with [Revoke])
 *
 * **Avoid `asChild` violation per CLAUDE.md §12** — pre-existing
 * CalendarAccountsPage.tsx ships an asChild on Button>Link which is
 * NOT compatible with shadcn/ui v4 + @base-ui/react. Use
 * ``buttonVariants()`` for any Link-as-button styling.
 */

import { useEffect, useState } from "react";
import {
  AlertCircle,
  Check,
  Loader2,
  RefreshCw,
  ShieldCheck,
  X,
} from "lucide-react";
import { toast } from "sonner";

import {
  Alert,
  AlertDescription,
  AlertTitle,
} from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusPill } from "@/components/ui/status-pill";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  acceptUpgrade,
  type ConsentState,
  listConsentStates,
  type PartnerConsentRow,
  requestUpgrade,
  revokeUpgrade,
} from "@/services/calendar-consent-service";


type PendingAction =
  | { type: "request"; row: PartnerConsentRow }
  | { type: "accept"; row: PartnerConsentRow }
  | { type: "revoke"; row: PartnerConsentRow }
  | null;


function _stateLabel(state: ConsentState): string {
  switch (state) {
    case "default":
      return "Privacy-preserving";
    case "pending_outbound":
      return "Awaiting partner";
    case "pending_inbound":
      return "Partner requested upgrade";
    case "active":
      return "Full details";
  }
}


/** Map our ConsentState → StatusPill semantic key. */
function _pillStatus(state: ConsentState): string {
  switch (state) {
    case "default":
      return "neutral";
    case "pending_outbound":
      return "pending";
    case "pending_inbound":
      return "pending_review";
    case "active":
      return "active";
  }
}


function _formatRelative(iso: string | null): string {
  if (!iso) return "Never updated";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}


export default function CalendarConsentPage() {
  const [partners, setPartners] = useState<PartnerConsentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingAction>(null);
  const [actionInFlight, setActionInFlight] = useState(false);

  async function loadConsent(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const r = await listConsentStates();
      setPartners(r.partners);
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ??
          "Failed to load partner consent states.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadConsent();
  }, []);

  async function handleConfirm(): Promise<void> {
    if (!pending) return;
    setActionInFlight(true);
    try {
      if (pending.type === "request") {
        await requestUpgrade(pending.row.relationship_id);
        toast.success(
          `Upgrade request sent to ${
            pending.row.partner_tenant_name ?? "partner tenant"
          }`,
        );
      } else if (pending.type === "accept") {
        await acceptUpgrade(pending.row.relationship_id);
        toast.success("Bilateral consent now active");
      } else {
        await revokeUpgrade(pending.row.relationship_id);
        toast.success("Consent revoked");
      }
      setPending(null);
      await loadConsent();
    } catch (err: any) {
      const detail =
        err?.response?.data?.detail ??
        (pending.type === "request"
          ? "Couldn't send upgrade request"
          : pending.type === "accept"
          ? "Couldn't accept upgrade"
          : "Couldn't revoke consent");
      toast.error(detail);
    } finally {
      setActionInFlight(false);
    }
  }

  return (
    <div className="container mx-auto max-w-5xl space-y-6 p-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-h2 font-plex-serif font-medium text-content-strong">
            Calendar consent — partner tenants
          </h1>
          <p className="mt-1 max-w-2xl text-body-sm text-content-muted">
            Bilateral consent unlocks subject + location + attendee
            details on cross-tenant free/busy queries. Either tenant can
            revoke at any time.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadConsent}
            disabled={loading}
          >
            <RefreshCw
              className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
              aria-hidden="true"
            />
            <span className="ml-2">Refresh</span>
          </Button>
        </div>
      </div>

      {error ? (
        <Alert variant="error">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Couldn't load consent states</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-2 p-4">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : partners.length === 0 ? (
            <EmptyState
              icon={ShieldCheck}
              title="No partner relationships yet"
              description="Connect with a partner tenant first to manage cross-tenant calendar consent."
              size="sm"
              tone="neutral"
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Partner tenant</TableHead>
                  <TableHead>Relationship</TableHead>
                  <TableHead>Consent state</TableHead>
                  <TableHead>Last updated</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {partners.map((row) => (
                  <TableRow key={row.relationship_id}>
                    <TableCell className="font-medium text-content-strong">
                      {row.partner_tenant_name ?? row.partner_tenant_id}
                    </TableCell>
                    <TableCell className="text-body-sm text-content-base">
                      {row.relationship_type}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <StatusPill status={_pillStatus(row.state)}>
                          {_stateLabel(row.state)}
                        </StatusPill>
                      </div>
                    </TableCell>
                    <TableCell className="text-body-sm text-content-muted">
                      {_formatRelative(row.updated_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <RowActions
                        row={row}
                        onAction={(type) => setPending({ type, row })}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog
        open={pending !== null}
        onOpenChange={(open) => {
          if (!open) setPending(null);
        }}
      >
        <DialogContent>
          {pending ? (
            <>
              <DialogHeader>
                <DialogTitle>
                  {pending.type === "request"
                    ? "Request bilateral upgrade?"
                    : pending.type === "accept"
                    ? "Accept bilateral upgrade?"
                    : "Revoke consent?"}
                </DialogTitle>
                <DialogDescription>
                  {pending.type === "request"
                    ? "This sends a request to the partner tenant. Bilateral consent activates only after they accept."
                    : pending.type === "accept"
                    ? "Accepting activates full-details consent for both tenants. Either side can revoke later."
                    : "Revoking immediately drops full-details consent for both tenants. Cross-tenant free/busy returns privacy-preserving windows only."}
                </DialogDescription>
              </DialogHeader>
              <div className="rounded border border-border-subtle bg-surface-sunken p-3 text-body-sm">
                <div className="font-medium text-content-strong">
                  {pending.row.partner_tenant_name ??
                    pending.row.partner_tenant_id}
                </div>
                <div className="text-content-muted">
                  {pending.row.relationship_type} ·{" "}
                  {_stateLabel(pending.row.state)}
                </div>
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setPending(null)}
                  disabled={actionInFlight}
                >
                  Cancel
                </Button>
                <Button
                  variant={
                    pending.type === "revoke" ? "destructive" : "default"
                  }
                  onClick={handleConfirm}
                  disabled={actionInFlight}
                >
                  {actionInFlight ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : null}
                  <span className={actionInFlight ? "ml-2" : ""}>
                    {pending.type === "request"
                      ? "Send request"
                      : pending.type === "accept"
                      ? "Accept"
                      : "Revoke"}
                  </span>
                </Button>
              </DialogFooter>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}


function RowActions({
  row,
  onAction,
}: {
  row: PartnerConsentRow;
  onAction: (type: "request" | "accept" | "revoke") => void;
}) {
  switch (row.state) {
    case "default":
      return (
        <Button size="sm" onClick={() => onAction("request")}>
          Request full details
        </Button>
      );
    case "pending_outbound":
      return (
        <Button
          variant="outline"
          size="sm"
          onClick={() => onAction("revoke")}
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="ml-1.5">Cancel request</span>
        </Button>
      );
    case "pending_inbound":
      return (
        <div className="flex justify-end gap-2">
          <Button size="sm" onClick={() => onAction("accept")}>
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="ml-1.5">Accept</span>
          </Button>
        </div>
      );
    case "active":
      return (
        <Button
          variant="outline"
          size="sm"
          onClick={() => onAction("revoke")}
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="ml-1.5">Revoke</span>
        </Button>
      );
  }
}
