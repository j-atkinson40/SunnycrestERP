/**
 * /inbox — Unified Email Inbox surface — Phase W-4b Layer 1 Step 4a.
 *
 * Two-pane layout (desktop) / stacked (mobile):
 *   - Left pane: account selector + filter strip + thread list
 *   - Right pane: thread detail + chronological messages + inline reply
 *
 * Per canon §3.26.15.9 + §3.26.15.13 + DESIGN_LANGUAGE §14.9:
 *   - Pattern 2 chrome (rounded-[2px] + bg-surface-elevated +
 *     border-border-subtle + shadow-level-1)
 *   - Aged-brass / terracotta accent (single-value cross-mode per
 *     Aesthetic Arc Session 2)
 *   - IBM Plex Sans / Serif / Mono typography
 *   - Inline reply per Q3 Phase B (reply + reply-all inline; new +
 *     forward modal — modal flows ship in Step 4b)
 *
 * Per canon §3.26.15.16 Discipline 1 "Keyboard-first everything":
 *   - J / K — next / prev thread
 *   - R — reply
 *   - A — reply-all
 *   - E — archive
 *   - Esc — close inline reply
 *
 * Step 4a defers (to Step 4b):
 *   - Modal new-thread / forward composition
 *   - Recipient mechanics (contact resolution, role-based routing)
 *   - Attachments + drag-drop
 *   - Template picker / slash-command snippets
 *   - Search
 *   - Snooze affordance UX
 *   - Label management UX
 *   - Operational-action affordance chrome (per §14.9.5)
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Archive,
  ArchiveRestore,
  Flag,
  Mail,
  Reply,
  ReplyAll,
  Send,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { listMyAccounts } from "@/services/email-account-service";
import {
  archiveThread,
  flagThread,
  getThreadDetail,
  listThreads,
  markRead,
  unarchiveThread,
  unflagThread,
} from "@/services/email-inbox-service";
import { sendMessage } from "@/services/email-account-service";
import type { EmailAccount } from "@/types/email-account";
import type {
  EmailStatusFilter,
  MessageDetail,
  ThreadDetail,
  ThreadSummary,
} from "@/types/email-inbox";


const STATUS_FILTERS: { value: EmailStatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "unread", label: "Unread" },
  { value: "flagged", label: "Flagged" },
  { value: "archived", label: "Archived" },
];


export default function InboxPage() {
  const [accounts, setAccounts] = useState<EmailAccount[]>([]);
  const [accountId, setAccountId] = useState<string | null>(null); // null = all
  const [statusFilter, setStatusFilter] = useState<EmailStatusFilter>("all");
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null);
  const [threadDetail, setThreadDetail] = useState<ThreadDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Load accessible accounts for selector ─────────────────────────
  useEffect(() => {
    void listMyAccounts()
      .then(setAccounts)
      .catch((e) => {
        setError(
          e instanceof Error ? e.message : "Failed to load accounts.",
        );
      });
  }, []);

  // ── Load thread list when filters change ──────────────────────────
  const reloadThreads = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await listThreads({
        account_id: accountId,
        status_filter: statusFilter,
      });
      setThreads(r.threads);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load inbox.");
    } finally {
      setLoading(false);
    }
  }, [accountId, statusFilter]);

  useEffect(() => {
    void reloadThreads();
  }, [reloadThreads]);

  // ── Load thread detail when selection changes ─────────────────────
  useEffect(() => {
    if (!selectedThreadId) {
      setThreadDetail(null);
      return;
    }
    setDetailLoading(true);
    void getThreadDetail(selectedThreadId)
      .then((d) => {
        setThreadDetail(d);
        // Auto-mark unread inbound messages read on open. Per canon
        // discipline: dwell + open. Step 4a uses immediate-on-open;
        // Step 4b can refine to dwell-time behavior if user research
        // surfaces edge cases.
        const unreadInbound = d.messages.filter(
          (m) => m.direction === "inbound" && !m.is_read,
        );
        if (unreadInbound.length > 0) {
          void Promise.all(
            unreadInbound.map((m) => markRead(m.id).catch(() => {})),
          ).then(() => {
            // Optimistic local update; backend audit log captured
            // server-side.
            setThreads((prev) =>
              prev.map((t) =>
                t.id === selectedThreadId
                  ? { ...t, unread_count: 0 }
                  : t,
              ),
            );
          });
        }
      })
      .catch((e) => {
        setError(
          e instanceof Error ? e.message : "Failed to load thread.",
        );
      })
      .finally(() => setDetailLoading(false));
  }, [selectedThreadId]);

  // ── Status mutation helpers (optimistic UI + rollback on error) ──
  async function handleArchive(threadId: string) {
    const previous = threads;
    setThreads((prev) => prev.filter((t) => t.id !== threadId));
    if (selectedThreadId === threadId) {
      setSelectedThreadId(null);
    }
    try {
      await archiveThread(threadId);
      toast.success("Archived");
    } catch (e) {
      setThreads(previous);
      toast.error(
        e instanceof Error ? e.message : "Archive failed",
      );
    }
  }

  async function handleUnarchive(threadId: string) {
    try {
      await unarchiveThread(threadId);
      toast.success("Restored");
      void reloadThreads();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Restore failed");
    }
  }

  async function handleFlagToggle(thread: ThreadSummary | ThreadDetail) {
    const isFlagged =
      "is_flagged_thread" in thread
        ? thread.is_flagged_thread
        : false;
    try {
      if (isFlagged) {
        await unflagThread(thread.id);
      } else {
        await flagThread(thread.id);
      }
      void reloadThreads();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Flag toggle failed");
    }
  }

  // ── Keyboard shortcuts (canon §3.26.15.16 Discipline 1) ───────────
  const selectedIndex = useMemo(
    () => threads.findIndex((t) => t.id === selectedThreadId),
    [threads, selectedThreadId],
  );

  const keyHandlerRef = useRef<((e: KeyboardEvent) => void) | null>(null);
  keyHandlerRef.current = (e: KeyboardEvent) => {
    // Don't fire shortcuts while typing in an input
    const target = e.target as HTMLElement | null;
    if (
      target &&
      (target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable)
    ) {
      return;
    }

    if (e.key === "j" || e.key === "ArrowDown") {
      const next = Math.min(threads.length - 1, selectedIndex + 1);
      if (next >= 0 && threads[next]) {
        e.preventDefault();
        setSelectedThreadId(threads[next].id);
      }
    } else if (e.key === "k" || e.key === "ArrowUp") {
      const prev = Math.max(0, selectedIndex - 1);
      if (prev < threads.length && threads[prev]) {
        e.preventDefault();
        setSelectedThreadId(threads[prev].id);
      }
    } else if (e.key === "e" && selectedThreadId) {
      e.preventDefault();
      void handleArchive(selectedThreadId);
    }
  };

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      keyHandlerRef.current?.(e);
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <div
      className="flex flex-col h-[calc(100vh-3.5rem)]"
      data-testid="inbox-page"
    >
      <header className="border-b border-border-subtle bg-surface-base px-6 py-3 flex items-center gap-4">
        <h1 className="text-h3 font-plex-serif font-medium text-content-strong">
          Inbox
        </h1>
        <div className="flex-1" />
        {accounts.length > 0 && (
          <Select
            value={accountId ?? "__all__"}
            onValueChange={(v) =>
              setAccountId(v === "__all__" ? null : v)
            }
          >
            <SelectTrigger className="w-72" data-testid="account-selector">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All accounts</SelectItem>
              {accounts.map((a) => (
                <SelectItem key={a.id} value={a.id}>
                  {a.display_name} · {a.email_address}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </header>

      <div className="flex flex-1 min-h-0">
        {/* ── Left pane: filter strip + thread list ─────────────── */}
        <div className="w-96 border-r border-border-subtle bg-surface-base flex flex-col min-h-0">
          <div
            className="flex items-center gap-1 px-3 py-2 border-b border-border-subtle"
            data-testid="filter-strip"
          >
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => setStatusFilter(f.value)}
                className={
                  "px-3 py-1 rounded text-body-sm font-medium transition-colors duration-quick " +
                  (statusFilter === f.value
                    ? "bg-accent-subtle text-accent"
                    : "text-content-muted hover:bg-surface-elevated/40")
                }
                data-testid={`filter-${f.value}`}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto" data-testid="thread-list">
            {loading ? (
              <div className="p-6 text-body-sm text-content-muted text-center">
                Loading…
              </div>
            ) : error ? (
              <div className="p-6 text-body-sm text-status-error text-center">
                {error}
              </div>
            ) : threads.length === 0 ? (
              <EmptyState
                icon={Mail}
                title="No threads"
                description={
                  statusFilter === "unread"
                    ? "Inbox zero. Nothing to act on."
                    : "No threads match this filter."
                }
              />
            ) : (
              <ul className="divide-y divide-border-subtle">
                {threads.map((thread) => (
                  <ThreadRow
                    key={thread.id}
                    thread={thread}
                    isSelected={thread.id === selectedThreadId}
                    onSelect={() => setSelectedThreadId(thread.id)}
                  />
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* ── Right pane: thread detail ─────────────────────────── */}
        <div className="flex-1 bg-surface-base flex flex-col min-h-0">
          {!selectedThreadId ? (
            <div className="flex-1 flex items-center justify-center text-content-muted">
              <div className="text-center">
                <Mail className="h-10 w-10 mx-auto mb-3 text-content-subtle" />
                <p className="text-body-sm">Select a thread to view it</p>
                <p className="text-caption mt-2">
                  J/K to navigate · R to reply · E to archive
                </p>
              </div>
            </div>
          ) : detailLoading ? (
            <div className="flex-1 flex items-center justify-center text-body-sm text-content-muted">
              Loading thread…
            </div>
          ) : threadDetail ? (
            <ThreadDetailPane
              detail={threadDetail}
              accounts={accounts}
              onArchive={() => handleArchive(threadDetail.id)}
              onUnarchive={() => handleUnarchive(threadDetail.id)}
              onFlagToggle={() => handleFlagToggle(threadDetail)}
              onReplySent={() => {
                void reloadThreads();
                void getThreadDetail(threadDetail.id).then(setThreadDetail);
              }}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────
// ThreadRow — single inbox row per §14.9.1
// ─────────────────────────────────────────────────────────────────────

function ThreadRow({
  thread,
  isSelected,
  onSelect,
}: {
  thread: ThreadSummary;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const isUnread = thread.unread_count > 0;
  return (
    <li
      onClick={onSelect}
      className={
        "px-4 py-3 cursor-pointer transition-colors duration-quick " +
        (isSelected
          ? "bg-accent-subtle/30 border-l-2 border-accent"
          : "border-l-2 border-transparent hover:bg-surface-elevated/40")
      }
      data-testid={`thread-row-${thread.id}`}
    >
      <div className="flex items-start gap-3">
        {/* Unread dot */}
        <div className="pt-1.5">
          {isUnread ? (
            <div
              className="w-2 h-2 rounded-full bg-accent"
              data-testid={`unread-dot-${thread.id}`}
            />
          ) : (
            <div className="w-2 h-2" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline justify-between gap-2 mb-0.5">
            <p
              className={
                "truncate font-plex-sans text-body-sm " +
                (isUnread
                  ? "font-medium text-content-strong"
                  : "text-content-base")
              }
            >
              {thread.sender_summary || "(no sender)"}
            </p>
            {thread.last_message_at && (
              <span className="font-plex-mono text-caption text-content-muted shrink-0">
                {formatRelative(thread.last_message_at)}
              </span>
            )}
          </div>
          <div className="flex items-baseline gap-1.5 mb-0.5">
            {thread.is_flagged_thread && (
              <Flag className="h-3 w-3 text-accent shrink-0" />
            )}
            {thread.is_cross_tenant && (
              <span
                className="inline-flex items-center text-caption text-accent"
                title="Cross-tenant thread"
              >
                ↔
              </span>
            )}
            <p
              className={
                "truncate font-plex-sans text-body-sm " +
                (isUnread
                  ? "font-medium text-content-strong"
                  : "text-content-muted")
              }
            >
              {thread.subject || "(no subject)"}
            </p>
            {thread.message_count > 1 && (
              <span className="font-plex-mono text-caption text-content-muted shrink-0">
                {thread.message_count}
              </span>
            )}
          </div>
          {thread.snippet && (
            <p className="truncate font-plex-sans text-caption text-content-muted">
              {thread.snippet}
            </p>
          )}
        </div>
      </div>
    </li>
  );
}


// ─────────────────────────────────────────────────────────────────────
// ThreadDetailPane — right pane composition per §14.9.2
// ─────────────────────────────────────────────────────────────────────

function ThreadDetailPane({
  detail,
  accounts,
  onArchive,
  onUnarchive,
  onFlagToggle,
  onReplySent,
}: {
  detail: ThreadDetail;
  accounts: EmailAccount[];
  onArchive: () => void;
  onUnarchive: () => void;
  onFlagToggle: () => void;
  onReplySent: () => void;
}) {
  const [replyMode, setReplyMode] = useState<"none" | "reply" | "reply-all">(
    "none",
  );
  const account = accounts.find((a) => a.id === detail.account_id);

  // Per §3.26.15.13: send-from-account = account that received the
  // original message. Step 4a uses thread.account_id (the inbox the
  // thread lives in). Future Step 5+ may refine when threads span
  // multiple accounts.
  const sendFromAccountId = detail.account_id;

  const lastInbound = useMemo(() => {
    for (let i = detail.messages.length - 1; i >= 0; i--) {
      if (detail.messages[i].direction === "inbound") {
        return detail.messages[i];
      }
    }
    return null;
  }, [detail.messages]);

  // Keyboard shortcuts within thread detail (R / A)
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      if (e.key === "r" && lastInbound) {
        e.preventDefault();
        setReplyMode("reply");
      } else if (e.key === "a" && lastInbound) {
        e.preventDefault();
        setReplyMode("reply-all");
      } else if (e.key === "Escape") {
        setReplyMode("none");
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [lastInbound]);

  return (
    <div className="flex-1 flex flex-col min-h-0" data-testid="thread-detail">
      <div className="border-b border-border-subtle px-6 py-3 flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <h2 className="text-h4 font-plex-serif font-medium text-content-strong truncate">
            {detail.subject || "(no subject)"}
          </h2>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-caption text-content-muted">
              {detail.participants_summary.join(", ")}
            </span>
            {detail.is_cross_tenant && (
              <span
                className="inline-flex items-center px-2 py-0.5 rounded-full text-caption bg-accent-subtle text-accent"
                data-testid="cross-tenant-pill"
              >
                ↔ Cross-tenant
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={onFlagToggle}
            data-testid="thread-flag-btn"
            aria-label="Toggle flag"
          >
            <Flag className="h-4 w-4" />
          </Button>
          {detail.is_archived ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={onUnarchive}
              data-testid="thread-unarchive-btn"
              aria-label="Unarchive thread"
            >
              <ArchiveRestore className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              onClick={onArchive}
              data-testid="thread-archive-btn"
              aria-label="Archive thread"
            >
              <Archive className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      <div
        className="flex-1 overflow-y-auto px-6 py-4 space-y-3"
        data-testid="message-list"
      >
        {detail.messages.map((m) => (
          <MessageCard key={m.id} message={m} />
        ))}

        {replyMode !== "none" && lastInbound && account && (
          <InlineReplyForm
            account={account}
            sendFromAccountId={sendFromAccountId}
            originalMessage={lastInbound}
            mode={replyMode}
            threadId={detail.id}
            onCancel={() => setReplyMode("none")}
            onSent={() => {
              setReplyMode("none");
              onReplySent();
            }}
          />
        )}

        {replyMode === "none" && lastInbound && (
          <div className="flex gap-2 pt-2">
            <Button
              size="sm"
              onClick={() => setReplyMode("reply")}
              data-testid="reply-btn"
            >
              <Reply className="h-4 w-4 mr-2" />
              Reply
              <kbd className="ml-2 text-caption opacity-70">R</kbd>
            </Button>
            {(lastInbound.cc?.length ?? 0) > 0 && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setReplyMode("reply-all")}
                data-testid="reply-all-btn"
              >
                <ReplyAll className="h-4 w-4 mr-2" />
                Reply all
                <kbd className="ml-2 text-caption opacity-70">A</kbd>
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────
// MessageCard — per-message Pattern 2 chrome per §14.9.2
// ─────────────────────────────────────────────────────────────────────

function MessageCard({ message }: { message: MessageDetail }) {
  return (
    <div
      className="rounded-[2px] bg-surface-elevated border border-border-subtle shadow-level-1 p-4"
      data-testid={`message-${message.id}`}
    >
      <div className="flex items-baseline justify-between gap-2 mb-3">
        <div className="min-w-0">
          <p className="font-plex-sans text-body-sm font-medium text-content-strong truncate">
            {message.sender_name
              ? `${message.sender_name}`
              : message.sender_email}
            {message.direction === "outbound" && (
              <span className="ml-2 text-caption text-content-muted">
                (you)
              </span>
            )}
          </p>
          <p className="font-plex-sans text-caption text-content-muted truncate">
            {message.sender_name && message.sender_email}
          </p>
        </div>
        <span className="font-plex-mono text-caption text-content-muted shrink-0">
          {message.sent_at
            ? formatRelative(message.sent_at)
            : formatRelative(message.received_at)}
        </span>
      </div>

      {/* Body — text first; HTML body deferred to Step 4b alongside
       sandboxed iframe per §3.26.15.5 (preventing inbound HTML script
       execution). Step 4a renders text fallback inline; HTML
       messages with no text body show "[HTML message — preview in
       Step 4b]" placeholder. */}
      {message.body_text ? (
        <pre className="font-plex-sans text-body-sm text-content-base whitespace-pre-wrap break-words">
          {message.body_text}
        </pre>
      ) : message.body_html ? (
        <div className="text-body-sm text-content-muted italic">
          [HTML message — sandboxed preview ships in Step 4b]
        </div>
      ) : (
        <div className="text-body-sm text-content-muted italic">
          (no body)
        </div>
      )}
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────
// InlineReplyForm — per §3.26.15.13 + §14.9.3
//
// Exported as named export so vitest can render it directly without
// going through the parent dropdown/keyboard flow (matches Step 3
// SendTestMessageDialog pattern).
// ─────────────────────────────────────────────────────────────────────

export function InlineReplyForm({
  account,
  sendFromAccountId,
  originalMessage,
  mode,
  threadId,
  onCancel,
  onSent,
}: {
  account: EmailAccount;
  sendFromAccountId: string;
  originalMessage: MessageDetail;
  mode: "reply" | "reply-all";
  threadId: string;
  onCancel: () => void;
  onSent: () => void;
}) {
  // Reply-all = original sender + all original to/cc minus self.
  const initialTo = useMemo(
    () => originalMessage.sender_email,
    [originalMessage],
  );
  const initialCc = useMemo(() => {
    if (mode !== "reply-all") return "";
    const others = [
      ...originalMessage.to,
      ...originalMessage.cc,
    ]
      .map((p) => p.email_address)
      .filter((addr) => addr.toLowerCase() !== account.email_address.toLowerCase());
    return [...new Set(others)].join(", ");
  }, [mode, originalMessage, account.email_address]);

  const initialSubject = useMemo(() => {
    const base = originalMessage.subject ?? "";
    if (base.toLowerCase().startsWith("re:")) return base;
    return `Re: ${base}`.trimEnd();
  }, [originalMessage.subject]);

  const [to, setTo] = useState(initialTo);
  const [cc, setCc] = useState(initialCc);
  const [subject, setSubject] = useState(initialSubject);
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSend() {
    if (!body.trim()) {
      toast.error("Body required");
      return;
    }
    setSubmitting(true);
    try {
      await sendMessage(sendFromAccountId, {
        to: to
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean)
          .map((email_address) => ({ email_address })),
        cc: cc
          ? cc
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean)
              .map((email_address) => ({ email_address }))
          : [],
        subject,
        body_text: body,
        thread_id: threadId,
        in_reply_to_message_id: originalMessage.id,
      });
      toast.success("Reply sent");
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
    <div
      className="rounded-[2px] bg-surface-elevated border border-border-subtle shadow-level-1 p-4 space-y-3"
      data-testid="inline-reply-form"
    >
      <div className="flex items-center justify-between">
        <span className="font-plex-sans text-body-sm font-medium text-content-strong">
          {mode === "reply-all" ? "Reply all" : "Reply"}
        </span>
        <Button
          size="sm"
          variant="ghost"
          onClick={onCancel}
          aria-label="Cancel reply"
          data-testid="reply-cancel-btn"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="grid grid-cols-[60px_1fr] gap-2 items-baseline">
        <span className="text-caption text-content-muted">To</span>
        <Input
          value={to}
          onChange={(e) => setTo(e.target.value)}
          data-testid="reply-to-input"
        />
        {mode === "reply-all" && (
          <>
            <span className="text-caption text-content-muted">Cc</span>
            <Input
              value={cc}
              onChange={(e) => setCc(e.target.value)}
              data-testid="reply-cc-input"
            />
          </>
        )}
        <span className="text-caption text-content-muted">Subject</span>
        <Input
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          data-testid="reply-subject-input"
        />
      </div>
      <Textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={6}
        placeholder="Write your reply…"
        data-testid="reply-body-input"
      />
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel}>
          Discard
        </Button>
        <Button
          size="sm"
          onClick={handleSend}
          disabled={submitting || !body.trim()}
          data-testid="reply-send-btn"
        >
          <Send className="h-4 w-4 mr-2" />
          Send
        </Button>
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────────────────────────────
// Time formatting — relative ("2h ago" / "Yesterday" / "Apr 5")
// ─────────────────────────────────────────────────────────────────────

function formatRelative(iso: string): string {
  try {
    const d = new Date(iso);
    const diffMs = Date.now() - d.getTime();
    const minutes = Math.floor(diffMs / 60000);
    if (minutes < 1) return "just now";
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d`;
    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso.slice(0, 10);
  }
}
