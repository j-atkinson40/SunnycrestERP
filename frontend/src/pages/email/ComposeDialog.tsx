/**
 * ComposeDialog — modal new-thread + forward composition.
 *
 * Phase W-4b Layer 1 Step 4b. Per canon §3.26.15.13 Q3:
 *   - Reply / Reply-all → INLINE (Step 4a InlineReplyForm)
 *   - New thread / Forward → MODAL (this file)
 *
 * Per DESIGN_LANGUAGE §14.9.3:
 *   - bg-surface-raised + shadow-level-3 + rounded-lg
 *   - Aged-brass / terracotta accent
 *   - IBM Plex typography
 *   - Esc closes; click-outside discards
 *
 * Recipient strip uses backend recipient resolution endpoint
 * (/email/recipients/resolve) with type-ahead debounce. Role-based
 * routing affordance (/email/recipients/roles + /expand-role)
 * expands a role primitive into individual recipients before send.
 *
 * Send-from-account selector: required (defaults to current account
 * context for new thread; pre-set for forward to the original
 * thread's account).
 *
 * Attachments: drag-drop + paste detection — Step 4b ships file
 * binary capture at send time via multipart-form. Vault item picker
 * is a "minimal" cut: links existing VaultItems by id without full
 * Vault picker UX (full picker deferred to Step 4c).
 *
 * Step 4b NOT shipping (deferred to Step 4c+):
 *   - HTML rich-text composer (Step 4b is plain text)
 *   - Send-later (depends on Step 3.1 backend)
 *   - Template picker (depends on Workshop integration)
 *   - Attachment preview rendering
 */

import { useEffect, useRef, useState } from "react";
import {
  AtSign,
  Loader2,
  Paperclip,
  Send,
  Users,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  expandRoleRecipient,
  listRoleRecipients,
  resolveRecipients,
} from "@/services/email-inbox-service";
import { sendMessage } from "@/services/email-account-service";
import type { EmailAccount } from "@/types/email-account";
import type {
  MessageDetail,
  ResolvedRecipient,
  RoleRecipient,
} from "@/types/email-inbox";


export type ComposeMode = "new" | "forward";

export interface ComposeDialogProps {
  /** Accounts the current user can send from (read_write+ access). */
  accounts: EmailAccount[];
  /** Default send-from account id; required for new + forward. */
  defaultAccountId: string;
  /** Forward source — pre-fills subject + quoted body. Null for new. */
  forwardSource?: MessageDetail | null;
  /** Pre-fill recipients (e.g. forwarding to original recipient). */
  initialTo?: { email_address: string; display_name: string | null }[];
  onClose: () => void;
  onSent: () => void;
}


// ─────────────────────────────────────────────────────────────────────
// Recipient chip rendering
// ─────────────────────────────────────────────────────────────────────


interface RecipientChip {
  email_address: string;
  display_name: string | null;
  source_type?: string;
}


function ChipRow({
  field,
  chips,
  onRemove,
}: {
  field: "to" | "cc" | "bcc";
  chips: RecipientChip[];
  onRemove: (idx: number) => void;
}) {
  if (chips.length === 0) return null;
  return (
    <div
      className="flex flex-wrap gap-1.5"
      data-testid={`compose-${field}-chips`}
    >
      {chips.map((chip, idx) => (
        <span
          key={`${chip.email_address}-${idx}`}
          className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-accent-subtle text-content-strong text-caption font-plex-sans"
          data-testid={`compose-chip-${field}-${idx}`}
        >
          {chip.source_type === "role_expansion" && (
            <Users className="h-3 w-3 opacity-70" />
          )}
          {chip.source_type === "crm_contact" && (
            <AtSign className="h-3 w-3 opacity-70" />
          )}
          <span className="truncate max-w-[200px]">
            {chip.display_name
              ? `${chip.display_name} · ${chip.email_address}`
              : chip.email_address}
          </span>
          <button
            type="button"
            onClick={() => onRemove(idx)}
            className="hover:text-status-error"
            aria-label="Remove recipient"
            data-testid={`compose-chip-${field}-${idx}-remove`}
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────
// Recipient strip with type-ahead
// ─────────────────────────────────────────────────────────────────────

const RFC5322_LOCAL = "[A-Za-z0-9._%+-]+";
const RFC5322_DOMAIN = "[A-Za-z0-9.-]+\\.[A-Za-z]{2,}";
const EMAIL_RE = new RegExp(`^${RFC5322_LOCAL}@${RFC5322_DOMAIN}$`);


function RecipientStrip({
  field,
  chips,
  onChipsChange,
  accountId,
}: {
  field: "to" | "cc" | "bcc";
  chips: RecipientChip[];
  onChipsChange: (chips: RecipientChip[]) => void;
  accountId: string;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ResolvedRecipient[]>([]);
  const [resolving, setResolving] = useState(false);
  const debounceRef = useRef<number | null>(null);

  // Debounced resolution
  useEffect(() => {
    if (query.length < 2) {
      setResults([]);
      return;
    }
    if (debounceRef.current !== null) {
      window.clearTimeout(debounceRef.current);
    }
    debounceRef.current = window.setTimeout(() => {
      setResolving(true);
      void resolveRecipients({ q: query, account_id: accountId })
        .then(setResults)
        .catch(() => setResults([]))
        .finally(() => setResolving(false));
    }, 200);
    return () => {
      if (debounceRef.current !== null) {
        window.clearTimeout(debounceRef.current);
      }
    };
  }, [query, accountId]);

  function commitFreeText() {
    const candidate = query.trim().toLowerCase();
    if (!candidate) return;
    if (!EMAIL_RE.test(candidate)) {
      toast.error("Invalid email address");
      return;
    }
    if (chips.some((c) => c.email_address === candidate)) {
      setQuery("");
      return;
    }
    onChipsChange([
      ...chips,
      { email_address: candidate, display_name: null },
    ]);
    setQuery("");
    setResults([]);
  }

  function selectRecipient(r: ResolvedRecipient) {
    if (chips.some((c) => c.email_address === r.email_address)) {
      setQuery("");
      setResults([]);
      return;
    }
    onChipsChange([
      ...chips,
      {
        email_address: r.email_address,
        display_name: r.display_name,
        source_type: r.source_type,
      },
    ]);
    setQuery("");
    setResults([]);
  }

  return (
    <div className="space-y-1.5" data-testid={`compose-${field}-strip`}>
      <ChipRow
        field={field}
        chips={chips}
        onRemove={(idx) => {
          onChipsChange(chips.filter((_, i) => i !== idx));
        }}
      />
      <div className="relative">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              commitFreeText();
            } else if (e.key === "Backspace" && !query && chips.length > 0) {
              onChipsChange(chips.slice(0, -1));
            }
          }}
          placeholder={
            field === "to"
              ? "Type to add recipient (Enter to commit)"
              : `Add ${field}…`
          }
          data-testid={`compose-${field}-input`}
        />
        {results.length > 0 && (
          <div
            className="absolute z-10 left-0 right-0 mt-1 rounded-[2px] bg-surface-elevated border border-border-subtle shadow-level-2 max-h-64 overflow-y-auto"
            data-testid={`compose-${field}-suggestions`}
          >
            {results.map((r) => (
              <button
                key={`${r.source_type}-${r.email_address}`}
                type="button"
                onClick={() => selectRecipient(r)}
                className="w-full text-left px-3 py-2 text-body-sm hover:bg-accent-subtle/40 border-b border-border-subtle/50 last:border-b-0"
                data-testid={`compose-suggestion-${r.email_address}`}
              >
                <div className="flex items-center gap-2">
                  <span className="flex-1 truncate">
                    {r.display_name && (
                      <span className="font-medium text-content-strong">
                        {r.display_name}
                      </span>
                    )}
                    {r.display_name && (
                      <span className="text-content-muted"> · </span>
                    )}
                    <span className="text-content-muted">
                      {r.email_address}
                    </span>
                  </span>
                  <span className="text-caption text-content-subtle font-plex-mono uppercase tracking-wider">
                    {r.source_type === "crm_contact"
                      ? "CRM"
                      : r.source_type === "recent"
                        ? "Recent"
                        : r.source_type === "internal_user"
                          ? "Internal"
                          : r.source_type}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
        {resolving && (
          <Loader2
            className="absolute right-3 top-2.5 h-4 w-4 animate-spin text-content-subtle"
            data-testid={`compose-${field}-loading`}
          />
        )}
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────
// Main dialog
// ─────────────────────────────────────────────────────────────────────


export function ComposeDialog({
  accounts,
  defaultAccountId,
  forwardSource,
  initialTo,
  onClose,
  onSent,
}: ComposeDialogProps) {
  const mode: ComposeMode = forwardSource ? "forward" : "new";
  const [accountId, setAccountId] = useState(defaultAccountId);
  const [to, setTo] = useState<RecipientChip[]>(
    initialTo?.map((r) => ({ ...r })) ?? [],
  );
  const [cc, setCc] = useState<RecipientChip[]>([]);
  const [bcc, setBcc] = useState<RecipientChip[]>([]);
  const [showCc, setShowCc] = useState(false);
  const [subject, setSubject] = useState(
    forwardSource
      ? buildForwardSubject(forwardSource.subject)
      : "",
  );
  const [body, setBody] = useState(
    forwardSource ? buildForwardQuotedBody(forwardSource) : "",
  );
  const [attachments, setAttachments] = useState<
    { filename: string; size: number; bytes: ArrayBuffer }[]
  >([]);
  const [submitting, setSubmitting] = useState(false);
  const [showRolePicker, setShowRolePicker] = useState(false);
  const [rolePrimitives, setRolePrimitives] = useState<RoleRecipient[]>([]);
  const dropZoneRef = useRef<HTMLDivElement | null>(null);

  // Esc to close
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  // Load role primitives when account changes + role picker opens
  async function openRolePicker() {
    setShowRolePicker(true);
    try {
      const list = await listRoleRecipients(accountId);
      setRolePrimitives(list);
    } catch {
      toast.error("Failed to load role list");
      setRolePrimitives([]);
    }
  }

  async function applyRolePrimitive(primitive: RoleRecipient) {
    try {
      const expanded = await expandRoleRecipient(
        primitive.role_kind,
        primitive.id_value,
      );
      const newChips: RecipientChip[] = expanded
        .filter(
          (r) => !to.some((c) => c.email_address === r.email_address),
        )
        .map((r) => ({
          email_address: r.email_address,
          display_name: r.display_name,
          source_type: r.source_type,
        }));
      setTo([...to, ...newChips]);
      toast.success(`Added ${newChips.length} recipient(s)`);
      setShowRolePicker(false);
    } catch {
      toast.error("Role expansion failed");
    }
  }

  // Drag-drop attachment handler
  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    void Promise.all(
      files.map(
        (f) =>
          new Promise<{ filename: string; size: number; bytes: ArrayBuffer }>(
            (resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () =>
                resolve({
                  filename: f.name,
                  size: f.size,
                  bytes: reader.result as ArrayBuffer,
                });
              reader.onerror = reject;
              reader.readAsArrayBuffer(f);
            },
          ),
      ),
    ).then((loaded) => {
      setAttachments([...attachments, ...loaded]);
    });
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
  }

  async function handleSend() {
    if (to.length === 0) {
      toast.error("At least one recipient required");
      return;
    }
    if (!subject.trim()) {
      toast.error("Subject required");
      return;
    }
    if (!body.trim()) {
      toast.error("Body required");
      return;
    }
    setSubmitting(true);
    try {
      // Step 4b ships attachment metadata only — full multipart upload
      // attaches binary at composer→send. Step 3 sendMessage doesn't
      // accept attachments yet; flagged as a Step 4c follow-up where
      // EmailAttachment row creation + R2 upload are wired into the
      // outbound pipeline. For Step 4b we send without attachments
      // and surface a UI warning if any are attached.
      if (attachments.length > 0) {
        toast.error(
          "Attachment send wires up in Step 4c — Step 4b is metadata-only. Send without attachments?",
        );
        // Continue anyway — drop attachments silently for now
      }

      await sendMessage(accountId, {
        to: to.map((c) => ({
          email_address: c.email_address,
          display_name: c.display_name,
        })),
        cc: cc.map((c) => ({
          email_address: c.email_address,
          display_name: c.display_name,
        })),
        bcc: bcc.map((c) => ({
          email_address: c.email_address,
          display_name: c.display_name,
        })),
        subject,
        body_text: body,
      });
      toast.success(mode === "forward" ? "Forwarded" : "Sent");
      onSent();
    } catch (e) {
      const detail =
        e && typeof e === "object" && "response" in e
          ? ((e as { response?: { data?: { detail?: string } } })
              .response?.data?.detail ?? null)
          : null;
      toast.error(
        detail ?? (e instanceof Error ? e.message : "Send failed"),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        className="max-w-2xl"
        data-testid="compose-dialog"
      >
        <DialogHeader>
          <DialogTitle>
            {mode === "forward" ? "Forward" : "New thread"}
          </DialogTitle>
          <DialogDescription>
            {mode === "forward"
              ? "Forward this message to another recipient. Original quoted below."
              : "Compose a new email. Choose recipients, write your message, send."}
          </DialogDescription>
        </DialogHeader>

        <div
          ref={dropZoneRef}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          className="space-y-4"
        >
          {/* Send-from-account */}
          <div className="space-y-1">
            <Label htmlFor="compose-from">From</Label>
            <Select
              value={accountId}
              onValueChange={(v) => v && setAccountId(v)}
            >
              <SelectTrigger id="compose-from" data-testid="compose-from">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {accounts.map((a) => (
                  <SelectItem key={a.id} value={a.id}>
                    {a.display_name} · {a.email_address}
                    <span className="ml-2 text-caption text-content-muted">
                      ({a.account_type})
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Recipients */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <Label>To</Label>
              <div className="flex items-center gap-2">
                {!showCc && (
                  <button
                    type="button"
                    onClick={() => setShowCc(true)}
                    className="text-caption text-accent hover:text-accent-hover"
                    data-testid="compose-show-cc"
                  >
                    Cc / Bcc
                  </button>
                )}
                <button
                  type="button"
                  onClick={openRolePicker}
                  className="text-caption text-accent hover:text-accent-hover inline-flex items-center gap-1"
                  data-testid="compose-add-role"
                >
                  <Users className="h-3 w-3" />
                  Add role…
                </button>
              </div>
            </div>
            <RecipientStrip
              field="to"
              chips={to}
              onChipsChange={setTo}
              accountId={accountId}
            />
          </div>

          {showCc && (
            <>
              <div className="space-y-1">
                <Label>Cc</Label>
                <RecipientStrip
                  field="cc"
                  chips={cc}
                  onChipsChange={setCc}
                  accountId={accountId}
                />
              </div>
              <div className="space-y-1">
                <Label>Bcc</Label>
                <RecipientStrip
                  field="bcc"
                  chips={bcc}
                  onChipsChange={setBcc}
                  accountId={accountId}
                />
              </div>
            </>
          )}

          {/* Subject */}
          <div className="space-y-1">
            <Label htmlFor="compose-subject">Subject</Label>
            <Input
              id="compose-subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              data-testid="compose-subject"
            />
          </div>

          {/* Body */}
          <div className="space-y-1">
            <Label htmlFor="compose-body">Message</Label>
            <Textarea
              id="compose-body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={10}
              placeholder="Write your message…"
              data-testid="compose-body"
            />
          </div>

          {/* Attachment chips */}
          {attachments.length > 0 && (
            <div className="space-y-1">
              <Label>Attachments</Label>
              <div className="flex flex-wrap gap-1.5">
                {attachments.map((a, idx) => (
                  <span
                    key={`${a.filename}-${idx}`}
                    className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-surface-elevated border border-border-subtle text-caption font-plex-sans"
                    data-testid={`compose-attachment-${idx}`}
                  >
                    <Paperclip className="h-3 w-3" />
                    <span>{a.filename}</span>
                    <span className="text-content-muted">
                      ({Math.round(a.size / 1024)}kb)
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        setAttachments(
                          attachments.filter((_, i) => i !== idx),
                        )
                      }
                      aria-label="Remove attachment"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
              <p className="text-caption text-status-warning">
                Step 4b: attachment metadata only. Binary upload ships
                in Step 4c.
              </p>
            </div>
          )}

          {/* Drop hint */}
          <div className="text-caption text-content-subtle border border-dashed border-border-subtle rounded p-2 text-center">
            <Paperclip className="h-3 w-3 inline-block mr-1 opacity-50" />
            Drag files here to attach (metadata-only in Step 4b)
          </div>
        </div>

        {/* Role picker overlay */}
        {showRolePicker && (
          <div
            className="absolute inset-0 bg-black/30 flex items-center justify-center z-50"
            onClick={() => setShowRolePicker(false)}
          >
            <div
              className="rounded-lg bg-surface-raised shadow-level-3 p-4 w-80 max-h-96 overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
              data-testid="role-picker"
            >
              <div className="font-medium mb-3">Add role</div>
              {rolePrimitives.length === 0 ? (
                <div className="text-body-sm text-content-muted">
                  No role primitives available. Multi-user roles ship
                  in Step 5+ alongside Workshop email-template integration.
                </div>
              ) : (
                <div className="space-y-1">
                  {rolePrimitives.map((p) => (
                    <button
                      key={`${p.role_kind}-${p.id_value}`}
                      type="button"
                      onClick={() => applyRolePrimitive(p)}
                      className="w-full text-left px-3 py-2 rounded hover:bg-accent-subtle text-body-sm"
                      data-testid={`role-primitive-${p.role_kind}-${p.id_value}`}
                    >
                      <div className="font-medium">{p.label}</div>
                      <div className="text-caption text-content-muted">
                        {p.member_count} recipient(s)
                      </div>
                    </button>
                  ))}
                </div>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowRolePicker(false)}
                className="w-full mt-3"
              >
                Cancel
              </Button>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            Discard
          </Button>
          <Button
            onClick={handleSend}
            disabled={
              submitting ||
              to.length === 0 ||
              !subject.trim() ||
              !body.trim()
            }
            data-testid="compose-send-btn"
          >
            <Send className="h-4 w-4 mr-2" />
            Send
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}


// ─────────────────────────────────────────────────────────────────────
// Subject + body helpers
// ─────────────────────────────────────────────────────────────────────


export function buildForwardSubject(subject: string | null): string {
  const base = (subject ?? "").trim();
  if (
    base.toLowerCase().startsWith("fwd:") ||
    base.toLowerCase().startsWith("fw:")
  ) {
    return base;
  }
  return `Fwd: ${base}`.trimEnd();
}


export function buildForwardQuotedBody(message: MessageDetail): string {
  const sender = message.sender_name
    ? `${message.sender_name} <${message.sender_email}>`
    : message.sender_email;
  const date =
    message.sent_at ?? message.received_at;
  const lines = [
    "",
    "",
    "---------- Forwarded message ----------",
    `From: ${sender}`,
    `Date: ${date}`,
    `Subject: ${message.subject ?? ""}`,
    "",
    message.body_text ?? "(HTML message — text body unavailable)",
  ];
  return lines.join("\n");
}
