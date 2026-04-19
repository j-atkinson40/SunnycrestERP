import { useCallback, useEffect, useState } from "react";
import {
  documentsV2Service,
  type DocumentShare,
} from "@/services/documents-v2-service";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/**
 * D-6 outbox panel — renders on DocumentDetail for owner-tenant admins.
 * Shows outgoing shares + grant/revoke actions. Read-only for
 * target-tenant admins (they see the document but can't share further).
 */
export default function DocumentSharesPanel({
  documentId,
  ownsDocument,
}: {
  documentId: string;
  ownsDocument: boolean;
}) {
  const [shares, setShares] = useState<DocumentShare[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [grantOpen, setGrantOpen] = useState(false);
  const [targetCompanyId, setTargetCompanyId] = useState("");
  const [reason, setReason] = useState("");
  const [includeRevoked, setIncludeRevoked] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    if (!ownsDocument) {
      // Non-owners can't list shares (API gates it). Hide the panel.
      setShares([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      const rows = await documentsV2Service.listShares(
        documentId,
        includeRevoked
      );
      setShares(rows);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [documentId, includeRevoked, ownsDocument]);

  useEffect(() => {
    load();
  }, [load]);

  async function grant() {
    setSubmitting(true);
    setErr(null);
    try {
      await documentsV2Service.createShare(documentId, {
        target_company_id: targetCompanyId.trim(),
        reason: reason.trim() || undefined,
      });
      setGrantOpen(false);
      setTargetCompanyId("");
      setReason("");
      await load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setErr(
        err.response?.data?.detail ??
          (e instanceof Error ? e.message : String(e))
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function revoke(shareId: string) {
    if (
      !window.confirm(
        "Revoke this share?\n\nRevoking prevents future access. Copies " +
          "already downloaded remain under the recipient's control."
      )
    )
      return;
    try {
      await documentsV2Service.revokeShare(shareId);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  if (!ownsDocument) {
    return (
      <section className="rounded-md border p-4 text-sm text-muted-foreground">
        This document was shared with you. Share management lives with the
        owner tenant.
      </section>
    );
  }

  return (
    <section className="rounded-md border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Shared with</h2>
          <p className="text-xs text-muted-foreground">
            Other tenants that have been granted read access to this document.
          </p>
        </div>
        <div className="flex gap-2">
          <label className="flex items-center gap-1 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={includeRevoked}
              onChange={(e) => setIncludeRevoked(e.target.checked)}
            />
            Include revoked
          </label>
          <Button size="sm" onClick={() => setGrantOpen(true)}>
            Share
          </Button>
        </div>
      </div>

      {err && (
        <div className="rounded-md border border-destructive bg-destructive/10 p-2 text-sm text-destructive">
          {err}
        </div>
      )}

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Target tenant</TableHead>
              <TableHead>Permission</TableHead>
              <TableHead>Granted</TableHead>
              <TableHead>Reason</TableHead>
              <TableHead>Status</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center">
                  Loading…
                </TableCell>
              </TableRow>
            ) : shares.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="py-4 text-center text-muted-foreground"
                >
                  No shares yet. Click <strong>Share</strong> to grant
                  another tenant read access.
                </TableCell>
              </TableRow>
            ) : (
              shares.map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="font-mono text-xs">
                    {s.target_company_id.slice(0, 12)}…
                  </TableCell>
                  <TableCell className="text-xs">{s.permission}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(s.granted_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="max-w-[240px] truncate text-xs">
                    {s.reason ?? "—"}
                  </TableCell>
                  <TableCell>
                    {s.revoked_at ? (
                      <Badge variant="outline" className="text-[10px]">
                        revoked
                      </Badge>
                    ) : (
                      <Badge variant="default" className="text-[10px]">
                        active
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {!s.revoked_at && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => revoke(s.id)}
                      >
                        Revoke
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={grantOpen} onOpenChange={setGrantOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Share this document</DialogTitle>
            <DialogDescription>
              Grant another tenant read access. Requires an active
              PlatformTenantRelationship between you and the target.
              Revocation later prevents future access but cannot recall
              already-downloaded copies.
            </DialogDescription>
          </DialogHeader>
          <Input
            placeholder="Target tenant ID (UUID)"
            value={targetCompanyId}
            onChange={(e) => setTargetCompanyId(e.target.value)}
            className="font-mono"
          />
          <Input
            placeholder="Reason (optional — shown in recipient's inbox)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setGrantOpen(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              onClick={grant}
              disabled={submitting || !targetCompanyId.trim()}
            >
              {submitting ? "Granting…" : "Grant access"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
