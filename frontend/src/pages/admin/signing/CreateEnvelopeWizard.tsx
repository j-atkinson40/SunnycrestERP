import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { signingService } from "@/services/signing-service";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import DocumentPicker from "@/components/documents/DocumentPicker";

interface PartyDraft {
  signing_order: number;
  role: string;
  display_name: string;
  email: string;
}

interface FieldDraft {
  signing_order: number;
  field_type: string;
  anchor_string: string;
  required: boolean;
  label: string;
}

/**
 * Simple 4-step wizard for creating + sending envelopes. Polish is D-8.
 */
export default function CreateEnvelopeWizard() {
  const navigate = useNavigate();
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);

  const [documentId, setDocumentId] = useState("");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [routingType, setRoutingType] = useState<"sequential" | "parallel">(
    "sequential"
  );
  const [expiresInDays, setExpiresInDays] = useState(30);
  const [parties, setParties] = useState<PartyDraft[]>([
    {
      signing_order: 1,
      role: "signer",
      display_name: "",
      email: "",
    },
  ]);
  const [fields, setFields] = useState<FieldDraft[]>([]);

  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function addParty() {
    setParties((prev) => [
      ...prev,
      {
        signing_order: prev.length + 1,
        role: "signer",
        display_name: "",
        email: "",
      },
    ]);
  }
  function removeParty(idx: number) {
    setParties((prev) =>
      prev
        .filter((_, i) => i !== idx)
        .map((p, i) => ({ ...p, signing_order: i + 1 }))
    );
  }
  function updateParty(idx: number, patch: Partial<PartyDraft>) {
    setParties((prev) =>
      prev.map((p, i) => (i === idx ? { ...p, ...patch } : p))
    );
  }

  function addField() {
    setFields((prev) => [
      ...prev,
      {
        signing_order: 1,
        field_type: "signature",
        anchor_string: "",
        required: true,
        label: "",
      },
    ]);
  }
  function removeField(idx: number) {
    setFields((prev) => prev.filter((_, i) => i !== idx));
  }
  function updateField(idx: number, patch: Partial<FieldDraft>) {
    setFields((prev) =>
      prev.map((f, i) => (i === idx ? { ...f, ...patch } : f))
    );
  }

  async function submit() {
    setSubmitting(true);
    setErr(null);
    try {
      const envelope = await signingService.createEnvelope({
        document_id: documentId,
        subject,
        description: description || undefined,
        routing_type: routingType,
        expires_in_days: expiresInDays,
        parties: parties.map((p) => ({
          signing_order: p.signing_order,
          role: p.role,
          display_name: p.display_name,
          email: p.email,
        })),
        fields: fields.map((f) => ({
          signing_order: f.signing_order,
          field_type: f.field_type,
          anchor_string: f.anchor_string || undefined,
          required: f.required,
          label: f.label || undefined,
        })),
      });
      navigate(`/admin/documents/signing/envelopes/${envelope.id}`);
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

  const canContinue1 = documentId.trim().length > 0;
  const canContinue2 =
    subject.trim().length > 0 &&
    parties.every((p) => p.display_name.trim() && p.email.trim());
  const canSubmit = canContinue1 && canContinue2;

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold">New signing envelope</h1>
        <p className="text-muted-foreground text-sm">
          Step {step} of 4
        </p>
      </div>

      {err && (
        <div className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
          {err}
        </div>
      )}

      {step === 1 && (
        <section className="space-y-3 rounded-md border p-4">
          <h2 className="text-lg font-semibold">1. Select document</h2>
          <p className="text-sm text-muted-foreground">
            Pick a document from this tenant's Document Log — the signing
            engine overlays anchor-based signature fields on the selected
            PDF.
          </p>
          <DocumentPicker value={documentId} onChange={setDocumentId} />
          <Input
            placeholder="Subject (shown in emails)"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
          />
          <textarea
            className="w-full h-20 rounded-md border bg-muted/10 p-2 text-sm"
            placeholder="Description (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <div className="flex justify-end">
            <Button
              onClick={() => setStep(2)}
              disabled={!canContinue1 || subject.trim().length === 0}
            >
              Continue
            </Button>
          </div>
        </section>
      )}

      {step === 2 && (
        <section className="space-y-3 rounded-md border p-4">
          <h2 className="text-lg font-semibold">2. Signers</h2>
          {parties.map((p, idx) => (
            <div
              key={idx}
              className="grid gap-2 md:grid-cols-4 rounded-md border bg-muted/10 p-3"
            >
              <Input
                placeholder="Name"
                value={p.display_name}
                onChange={(e) =>
                  updateParty(idx, { display_name: e.target.value })
                }
              />
              <Input
                placeholder="Email"
                type="email"
                value={p.email}
                onChange={(e) => updateParty(idx, { email: e.target.value })}
              />
              <Input
                placeholder="Role"
                value={p.role}
                onChange={(e) => updateParty(idx, { role: e.target.value })}
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removeParty(idx)}
                disabled={parties.length <= 1}
              >
                Remove
              </Button>
            </div>
          ))}
          <div className="flex items-center justify-between">
            <Button variant="outline" onClick={addParty}>
              Add signer
            </Button>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button
                onClick={() => setStep(3)}
                disabled={!canContinue2}
              >
                Continue
              </Button>
            </div>
          </div>
        </section>
      )}

      {step === 3 && (
        <section className="space-y-3 rounded-md border p-4">
          <h2 className="text-lg font-semibold">3. Signature fields</h2>
          <p className="text-sm text-muted-foreground">
            Optional. If omitted, the signer's captured signature still
            renders on a cover page. Anchor strings (e.g.{" "}
            <code>/sig_fh/</code>) position the field inline in the PDF.
          </p>
          {fields.map((f, idx) => (
            <div
              key={idx}
              className="grid gap-2 md:grid-cols-5 rounded-md border bg-muted/10 p-3"
            >
              <select
                className="h-9 rounded-md border bg-transparent px-2 text-sm"
                value={f.signing_order}
                onChange={(e) =>
                  updateField(idx, {
                    signing_order: parseInt(e.target.value, 10),
                  })
                }
              >
                {parties.map((p) => (
                  <option key={p.signing_order} value={p.signing_order}>
                    {p.display_name || `Signer ${p.signing_order}`}
                  </option>
                ))}
              </select>
              <select
                className="h-9 rounded-md border bg-transparent px-2 text-sm"
                value={f.field_type}
                onChange={(e) =>
                  updateField(idx, { field_type: e.target.value })
                }
              >
                <option value="signature">Signature</option>
                <option value="initial">Initial</option>
                <option value="date">Date</option>
                <option value="typed_name">Typed name</option>
                <option value="text">Text</option>
                <option value="checkbox">Checkbox</option>
              </select>
              <Input
                placeholder="Anchor /sig_x/"
                value={f.anchor_string}
                onChange={(e) =>
                  updateField(idx, { anchor_string: e.target.value })
                }
                className="font-mono"
              />
              <Input
                placeholder="Label (optional)"
                value={f.label}
                onChange={(e) =>
                  updateField(idx, { label: e.target.value })
                }
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removeField(idx)}
              >
                Remove
              </Button>
            </div>
          ))}
          <div className="flex items-center justify-between">
            <Button variant="outline" onClick={addField}>
              Add field
            </Button>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => setStep(2)}>
                Back
              </Button>
              <Button onClick={() => setStep(4)}>Continue</Button>
            </div>
          </div>
        </section>
      )}

      {step === 4 && (
        <section className="space-y-3 rounded-md border p-4">
          <h2 className="text-lg font-semibold">4. Review</h2>
          <div className="space-y-2 text-sm">
            <div>
              <strong>Subject:</strong> {subject}
            </div>
            <div>
              <strong>Document:</strong>{" "}
              <span className="font-mono text-xs">{documentId}</span>
            </div>
            <div>
              <strong>Routing:</strong> {routingType} ·{" "}
              <strong>Expires in:</strong> {expiresInDays} days
            </div>
            <div>
              <strong>Signers:</strong> {parties.length}
            </div>
            <div>
              <strong>Fields:</strong> {fields.length}
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <label>Routing</label>
            <select
              className="h-9 rounded-md border bg-transparent px-2 text-sm"
              value={routingType}
              onChange={(e) =>
                setRoutingType(e.target.value as "sequential" | "parallel")
              }
            >
              <option value="sequential">Sequential</option>
              <option value="parallel">Parallel</option>
            </select>
            <label className="ml-4">Expires in (days)</label>
            <Input
              type="number"
              min={1}
              max={365}
              className="w-24"
              value={expiresInDays}
              onChange={(e) =>
                setExpiresInDays(parseInt(e.target.value || "30", 10))
              }
            />
          </div>
          <p className="text-xs text-muted-foreground">
            Clicking "Create envelope" saves it as <strong>draft</strong>.
            Send it from the envelope detail page when you're ready.
          </p>
          <div className="flex items-center justify-between">
            <Button variant="ghost" onClick={() => setStep(3)}>
              Back
            </Button>
            <Button onClick={submit} disabled={!canSubmit || submitting}>
              {submitting ? "Creating…" : "Create envelope"}
            </Button>
          </div>
        </section>
      )}
    </div>
  );
}
