/**
 * Config UI for the `send_document` workflow step type (Phase D-7 step;
 * UI shipped in D-8 polish).
 *
 * Replaces the generic JSON editor when step_type === "send_document".
 * Admins get:
 *   - Channel dropdown (email, sms)
 *   - Recipient type + value (supports {variable.references})
 *   - Recipient display name (optional)
 *   - Template key dropdown (email templates from the managed registry)
 *   - Subject override (optional — template subject used if unset)
 *   - Body fallback (only when no template)
 *   - Reply-to (optional)
 *   - Document ID (optional — attaches the document PDF)
 *   - Context JSON editor (template variables)
 *
 * The step's output is referenceable downstream as
 * `{output.<step_key>.delivery_id}` / `.status` / `.provider_message_id`.
 */

import { Input } from "@/components/ui/input";

// Keep in sync with email.* templates seeded by the D-2 migration and
// refreshed in D-8's design pass. Add new templates here as they ship.
const EMAIL_TEMPLATE_KEYS: { value: string; label: string }[] = [
  { value: "", label: "— No template (use Body below) —" },
  { value: "email.statement", label: "Statement notification" },
  { value: "email.collections", label: "Collections" },
  { value: "email.invitation", label: "User invitation" },
  { value: "email.accountant_invitation", label: "Accountant invitation" },
  { value: "email.alert_digest", label: "Agent alert digest" },
  { value: "email.signing_invite", label: "Signing invite" },
  { value: "email.signing_completed", label: "Signing completed" },
  { value: "email.signing_declined", label: "Signing declined" },
  { value: "email.signing_voided", label: "Signing voided" },
  { value: "email.legacy_proof", label: "Legacy proof" },
  { value: "email.base_wrapper", label: "Base wrapper (custom body)" },
];

const CHANNEL_OPTIONS: { value: string; label: string; help?: string }[] = [
  { value: "email", label: "Email", help: "Via Resend (D-7 default)" },
  {
    value: "sms",
    label: "SMS (stub)",
    help: "Returns NOT_IMPLEMENTED — native SMS pending",
  },
];

const RECIPIENT_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "email_address", label: "Email address" },
  { value: "phone_number", label: "Phone number" },
  { value: "user_id", label: "User ID" },
  { value: "contact_id", label: "Contact ID" },
];

interface Props {
  cfg: Record<string, unknown>;
  onConfigChange: (patch: Record<string, unknown>) => void;
}

export function SendDocumentConfig({ cfg, onConfigChange }: Props) {
  const channel = (cfg.channel as string) || "email";
  const recipient = (cfg.recipient as Record<string, string>) || {};
  const recipientType = recipient.type || "email_address";
  const recipientValue = recipient.value || "";
  const recipientName = recipient.name || "";
  const templateKey = (cfg.template_key as string) || "";
  const subject = (cfg.subject as string) || "";
  const body = (cfg.body as string) || "";
  const replyTo = (cfg.reply_to as string) || "";
  const documentId = (cfg.document_id as string) || "";
  const templateContext =
    (cfg.template_context as Record<string, unknown>) || {};

  function setRecipient(patch: Partial<Record<string, string>>) {
    onConfigChange({
      recipient: {
        type: recipientType,
        value: recipientValue,
        name: recipientName,
        ...patch,
      },
    });
  }

  function updateContext(text: string) {
    try {
      const parsed = JSON.parse(text || "{}");
      onConfigChange({ template_context: parsed });
    } catch {
      /* leave as-is; user will fix the JSON */
    }
  }

  return (
    <div className="space-y-3">
      <Field label="Channel" hint="Email via Resend is the only active channel in D-7.">
        <select
          value={channel}
          onChange={(e) => onConfigChange({ channel: e.target.value })}
          className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
        >
          {CHANNEL_OPTIONS.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
              {c.help ? ` — ${c.help}` : ""}
            </option>
          ))}
        </select>
      </Field>

      <div className="grid gap-3 md:grid-cols-3">
        <Field label="Recipient type">
          <select
            value={recipientType}
            onChange={(e) => setRecipient({ type: e.target.value })}
            className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
          >
            {RECIPIENT_TYPE_OPTIONS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </Field>
        <Field
          label="Recipient value"
          hint="Supports {variable.references}."
        >
          <Input
            value={recipientValue}
            onChange={(e) => setRecipient({ value: e.target.value })}
            placeholder={
              recipientType === "email_address"
                ? "{input.ask_email.value}"
                : "+15551234567"
            }
          />
        </Field>
        <Field label="Recipient name (optional)">
          <Input
            value={recipientName}
            onChange={(e) => setRecipient({ name: e.target.value })}
            placeholder="{output.extract_customer.name}"
          />
        </Field>
      </div>

      <Field
        label="Template"
        hint="Rendered via the managed template registry. Tenant overrides apply automatically."
      >
        <select
          value={templateKey}
          onChange={(e) => onConfigChange({ template_key: e.target.value })}
          className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
        >
          {EMAIL_TEMPLATE_KEYS.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </Field>

      {templateKey ? (
        <Field
          label="Template context (JSON)"
          hint="Variables the template expects. Supports {variable.references} in values."
        >
          <textarea
            className="h-32 w-full rounded border border-slate-300 bg-white p-2 font-mono text-xs leading-5"
            defaultValue={JSON.stringify(templateContext, null, 2)}
            onBlur={(e) => updateContext(e.target.value)}
            spellCheck={false}
          />
        </Field>
      ) : (
        <Field
          label="Body (HTML or text)"
          hint="Used only when no template is selected."
        >
          <textarea
            className="h-32 w-full rounded border border-slate-300 bg-white p-2 font-mono text-xs leading-5"
            value={body}
            onChange={(e) => onConfigChange({ body: e.target.value })}
            placeholder="<p>Hi {input.ask_name.value},</p>"
            spellCheck={false}
          />
        </Field>
      )}

      <Field
        label="Subject (optional)"
        hint="Overrides the template's subject_template if both are set."
      >
        <Input
          value={subject}
          onChange={(e) => onConfigChange({ subject: e.target.value })}
          placeholder="{output.extract_invoice.number} — {company.name}"
        />
      </Field>

      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Reply-to (optional)">
          <Input
            value={replyTo}
            onChange={(e) => onConfigChange({ reply_to: e.target.value })}
            placeholder="support@{company.slug}.com"
          />
        </Field>
        <Field
          label="Document ID (optional)"
          hint="If set, DeliveryService auto-attaches the document PDF."
        >
          <Input
            value={documentId}
            onChange={(e) => onConfigChange({ document_id: e.target.value })}
            placeholder="{output.generate_invoice.document_id}"
          />
        </Field>
      </div>

      <div className="rounded border border-blue-200 bg-blue-50 p-2 text-[11px] text-blue-900">
        The delivery row will appear in the Delivery Log with linkage
        back to this workflow run. Downstream steps can reference{" "}
        <code className="font-mono">{`{output.<step_key>.delivery_id}`}</code>
        ,{" "}
        <code className="font-mono">{`{output.<step_key>.status}`}</code>
        , and{" "}
        <code className="font-mono">{`{output.<step_key>.provider_message_id}`}</code>
        .
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between">
        <label className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
          {label}
        </label>
        {hint && <span className="text-[10px] text-slate-400">{hint}</span>}
      </div>
      {children}
    </div>
  );
}
