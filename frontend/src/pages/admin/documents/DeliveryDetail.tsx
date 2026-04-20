import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  documentsV2Service,
  type DeliveryDetail as DeliveryDetailType,
} from "@/services/documents-v2-service";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function DeliveryDetail() {
  const { deliveryId = "" } = useParams<{ deliveryId: string }>();
  const [d, setD] = useState<DeliveryDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [resending, setResending] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const data = await documentsV2Service.getDelivery(deliveryId);
      setD(data);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [deliveryId]);

  useEffect(() => {
    load();
  }, [load]);

  async function resend() {
    setResending(true);
    try {
      const newDelivery = await documentsV2Service.resendDelivery(deliveryId);
      // Navigate to the new delivery
      window.location.href = `/vault/documents/deliveries/${newDelivery.id}`;
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setResending(false);
    }
  }

  if (loading) return <div className="p-6 text-muted-foreground">Loading…</div>;
  if (err && !d)
    return (
      <div className="p-6 text-destructive" role="alert">
        {err}
      </div>
    );
  if (!d) return <div className="p-6">Delivery not found.</div>;

  return (
    <div className="space-y-6 p-6">
      <div>
        <Link
          to="/vault/documents/deliveries"
          className="text-xs text-muted-foreground underline"
        >
          ← Delivery Log
        </Link>
        <div className="mt-1 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">
              {d.subject ?? "(no subject)"}
            </h1>
            <div className="mt-1 flex items-center gap-2 text-xs">
              <Badge variant="outline">{d.channel}</Badge>
              <Badge variant="outline">{d.status}</Badge>
              {d.provider && (
                <span className="text-muted-foreground">
                  via {d.provider}
                </span>
              )}
            </div>
          </div>
          <Button onClick={resend} disabled={resending}>
            {resending ? "Resending…" : "Resend"}
          </Button>
        </div>
      </div>

      {err && (
        <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
          {err}
        </div>
      )}

      {/* Metadata */}
      <section className="grid gap-4 rounded-md border p-4 md:grid-cols-2">
        <Meta
          label="Recipient"
          value={
            d.recipient_name
              ? `${d.recipient_name} <${d.recipient_value}>`
              : d.recipient_value
          }
        />
        <Meta label="Recipient type" value={d.recipient_type} mono />
        <Meta
          label="Created"
          value={new Date(d.created_at).toLocaleString()}
        />
        <Meta
          label="Sent"
          value={d.sent_at ? new Date(d.sent_at).toLocaleString() : "—"}
        />
        <Meta
          label="Delivered"
          value={
            d.delivered_at
              ? new Date(d.delivered_at).toLocaleString()
              : "— (requires provider webhook)"
          }
        />
        <Meta
          label="Failed"
          value={d.failed_at ? new Date(d.failed_at).toLocaleString() : "—"}
        />
        <Meta
          label="Provider message ID"
          value={d.provider_message_id ?? "—"}
          mono
        />
        <Meta
          label="Retries"
          value={`${d.retry_count} / ${d.max_retries}`}
        />
      </section>

      {/* Template */}
      {d.template_key && (
        <section className="rounded-md border p-4">
          <div className="text-xs font-semibold uppercase text-muted-foreground">
            Template
          </div>
          <div className="mt-1 font-mono text-sm">{d.template_key}</div>
        </section>
      )}

      {/* Error */}
      {(d.error_message || d.error_code) && (
        <section className="rounded-md border border-destructive/40 bg-destructive/5 p-4">
          <div className="text-xs font-semibold uppercase text-destructive">
            Error
          </div>
          <div className="mt-1 text-sm">
            <div>
              <strong>Code:</strong>{" "}
              <span className="font-mono">{d.error_code ?? "—"}</span>
            </div>
            <div className="mt-1 whitespace-pre-wrap">
              {d.error_message ?? "—"}
            </div>
          </div>
        </section>
      )}

      {/* Linkage */}
      <section className="space-y-2 rounded-md border p-4">
        <h2 className="text-sm font-semibold uppercase text-muted-foreground">
          Linkage
        </h2>
        <div className="grid gap-2 text-sm md:grid-cols-2">
          <Meta
            label="Caller module"
            value={d.caller_module ?? "—"}
            mono
          />
          <Meta
            label="Document"
            value={
              d.document_id ? (
                <Link
                  to={`/vault/documents/${d.document_id}`}
                  className="underline"
                >
                  {d.document_id.slice(0, 12)}…
                </Link>
              ) : (
                "—"
              )
            }
          />
          <Meta
            label="Workflow run"
            value={d.caller_workflow_run_id ?? "—"}
            mono
          />
          <Meta
            label="Workflow step"
            value={d.caller_workflow_step_id ?? "—"}
            mono
          />
          <Meta
            label="Intelligence execution"
            value={
              d.caller_intelligence_execution_id ? (
                <Link
                  to={`/vault/intelligence/executions/${d.caller_intelligence_execution_id}`}
                  className="underline"
                >
                  {d.caller_intelligence_execution_id.slice(0, 12)}…
                </Link>
              ) : (
                "—"
              )
            }
          />
          <Meta
            label="Signature envelope"
            value={
              d.caller_signature_envelope_id ? (
                <Link
                  to={`/vault/documents/signing/${d.caller_signature_envelope_id}`}
                  className="underline"
                >
                  {d.caller_signature_envelope_id.slice(0, 12)}…
                </Link>
              ) : (
                "—"
              )
            }
          />
        </div>
      </section>

      {/* Body preview */}
      {d.body_preview && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">
            Body preview (first 500 chars)
          </h2>
          <pre className="max-h-60 overflow-auto rounded-md border bg-muted/20 p-3 font-mono text-xs whitespace-pre-wrap">
            {d.body_preview}
          </pre>
        </section>
      )}

      {/* Provider response */}
      {d.provider_response && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">
            Provider response
          </h2>
          <pre className="max-h-60 overflow-auto rounded-md border bg-muted/20 p-3 font-mono text-xs">
            {JSON.stringify(d.provider_response, null, 2)}
          </pre>
        </section>
      )}
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
