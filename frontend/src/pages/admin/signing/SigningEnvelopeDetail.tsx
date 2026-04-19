import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  signingService,
  type EnvelopeDetail,
  type SignatureEvent,
} from "@/services/signing-service";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export default function SigningEnvelopeDetail() {
  const { envelopeId = "" } = useParams<{ envelopeId: string }>();
  const [env, setEnv] = useState<EnvelopeDetail | null>(null);
  const [events, setEvents] = useState<SignatureEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [voidOpen, setVoidOpen] = useState(false);
  const [voidReason, setVoidReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const [e, ev] = await Promise.all([
        signingService.getEnvelope(envelopeId),
        signingService.listEvents(envelopeId, { limit: 200 }),
      ]);
      setEnv(e);
      setEvents(ev);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [envelopeId]);

  useEffect(() => {
    load();
  }, [load]);

  async function sendEnvelope() {
    setSubmitting(true);
    try {
      await signingService.sendEnvelope(envelopeId);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  async function voidEnvelope() {
    setSubmitting(true);
    try {
      await signingService.voidEnvelope(envelopeId, voidReason);
      setVoidOpen(false);
      setVoidReason("");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  async function resend(partyId: string) {
    try {
      await signingService.resendToParty(partyId);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  if (loading)
    return <div className="p-6 text-muted-foreground">Loading…</div>;
  if (err && !env)
    return <div className="p-6 text-destructive">{err}</div>;
  if (!env) return <div className="p-6">Envelope not found.</div>;

  const terminal = ["completed", "declined", "voided", "expired"].includes(
    env.status
  );

  return (
    <div className="space-y-6 p-6">
      <div>
        <Link
          to="/admin/documents/signing/envelopes"
          className="text-xs text-muted-foreground underline"
        >
          ← All envelopes
        </Link>
        <div className="mt-1 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">{env.subject}</h1>
            <div className="mt-1 flex items-center gap-2">
              <Badge variant="outline" className="text-[10px]">
                {env.status}
              </Badge>
              <Badge variant="secondary" className="text-[10px]">
                {env.routing_type}
              </Badge>
              {env.expires_at && (
                <span className="text-xs text-muted-foreground">
                  Expires {new Date(env.expires_at).toLocaleDateString()}
                </span>
              )}
            </div>
            {env.description && (
              <p className="mt-2 text-sm text-muted-foreground">
                {env.description}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            {env.status === "draft" && (
              <Button onClick={sendEnvelope} disabled={submitting}>
                {submitting ? "Sending…" : "Send"}
              </Button>
            )}
            {!terminal && env.status !== "draft" && (
              <Button
                variant="destructive"
                onClick={() => setVoidOpen(true)}
              >
                Void
              </Button>
            )}
            {env.status === "completed" && env.certificate_document_id && (
              <a
                href={`/api/v1/documents-v2/${env.certificate_document_id}/download`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <Button variant="outline">Certificate</Button>
              </a>
            )}
            {env.status === "completed" && (
              <a
                href={`/api/v1/documents-v2/${env.document_id}/download`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <Button variant="outline">Signed document</Button>
              </a>
            )}
          </div>
        </div>
      </div>

      {err && (
        <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
          {err}
        </div>
      )}

      {/* Parties */}
      <section>
        <h2 className="mb-2 text-lg font-semibold">Parties</h2>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Order</TableHead>
                <TableHead>Name / email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Signed</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {env.parties.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-mono text-xs">
                    {p.signing_order}
                  </TableCell>
                  <TableCell className="text-sm">
                    <div>{p.display_name}</div>
                    <div className="text-xs text-muted-foreground">
                      {p.email}
                    </div>
                  </TableCell>
                  <TableCell className="text-xs">{p.role}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-[10px]">
                      {p.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {p.signed_at
                      ? new Date(p.signed_at).toLocaleString()
                      : "—"}
                  </TableCell>
                  <TableCell>
                    {["sent", "viewed", "consented"].includes(p.status) && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => resend(p.id)}
                      >
                        Resend
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </section>

      {/* Fields */}
      {env.fields.length > 0 && (
        <section>
          <h2 className="mb-2 text-lg font-semibold">Fields</h2>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Anchor / position</TableHead>
                  <TableHead>Required</TableHead>
                  <TableHead>Value</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {env.fields.map((f) => (
                  <TableRow key={f.id}>
                    <TableCell className="text-xs">{f.field_type}</TableCell>
                    <TableCell className="font-mono text-xs">
                      {f.anchor_string ??
                        (f.page_number != null
                          ? `p${f.page_number} @ ${f.position_x ?? "?"},${f.position_y ?? "?"}`
                          : "—")}
                    </TableCell>
                    <TableCell className="text-xs">
                      {f.required ? "yes" : "no"}
                    </TableCell>
                    <TableCell className="text-xs">
                      {f.value ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </section>
      )}

      {/* Events */}
      <section>
        <h2 className="mb-2 text-lg font-semibold">Activity</h2>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>When</TableHead>
                <TableHead>Event</TableHead>
                <TableHead>Party</TableHead>
                <TableHead>IP</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.map((e) => (
                <TableRow key={e.id}>
                  <TableCell className="font-mono text-xs">
                    {e.sequence_number}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {new Date(e.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    <Badge variant="outline" className="text-[10px]">
                      {e.event_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs">
                    {e.party_id
                      ? env.parties.find((p) => p.id === e.party_id)
                          ?.display_name ?? e.party_id.slice(0, 8)
                      : "—"}
                  </TableCell>
                  <TableCell className="text-xs">{e.ip_address ?? "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </section>

      {/* Document hash */}
      <section className="rounded-md border p-3 text-xs">
        <div className="font-semibold uppercase text-muted-foreground">
          Document hash (SHA-256 at envelope creation)
        </div>
        <div className="font-mono break-all">{env.document_hash}</div>
      </section>

      <Dialog open={voidOpen} onOpenChange={setVoidOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Void envelope?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Voiding cancels all pending signers. The audit log keeps a
            permanent record of this envelope.
          </p>
          <Input
            placeholder="Reason (required)"
            value={voidReason}
            onChange={(e) => setVoidReason(e.target.value)}
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setVoidOpen(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={voidEnvelope}
              disabled={submitting || !voidReason.trim()}
            >
              {submitting ? "Voiding…" : "Confirm void"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
