/**
 * InboxPage tests — Phase W-4b Layer 1 Step 4a.
 *
 * Coverage:
 *   - InboxPage renders with mocked threads
 *   - Filter strip applies filter via API
 *   - Thread row click loads detail
 *   - Empty state when no threads
 *   - InlineReplyForm tested in isolation (named export):
 *       * Pre-fills To from sender
 *       * Pre-fills Subject with Re: prefix (idempotent)
 *       * Reply-all pre-fills Cc from original to/cc minus self
 *       * Send routes through sendMessage with thread_id +
 *         in_reply_to_message_id
 *       * Discard button cancels
 *
 * Note: keyboard-shortcut UX (J/K/R/A/E/Esc) is exercised via
 * Playwright; vitest covers the dispatcher logic via direct callback
 * invocation when convenient, but full keyboard-routing testing
 * lives in E2E.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MessageDetail } from "@/types/email-inbox";


// ── Mocks ────────────────────────────────────────────────────────────

const mockListThreads = vi.fn();
const mockGetThreadDetail = vi.fn();
const mockMarkRead = vi.fn().mockResolvedValue(undefined);
const mockArchiveThread = vi.fn().mockResolvedValue(undefined);
const mockListMyAccounts = vi.fn();
const mockSendMessage = vi.fn();

vi.mock("@/services/email-inbox-service", () => ({
  listThreads: (...args: unknown[]) => mockListThreads(...args),
  getThreadDetail: (...args: unknown[]) => mockGetThreadDetail(...args),
  markRead: (...args: unknown[]) => mockMarkRead(...args),
  markUnread: vi.fn().mockResolvedValue(undefined),
  archiveThread: (...args: unknown[]) => mockArchiveThread(...args),
  unarchiveThread: vi.fn().mockResolvedValue(undefined),
  flagThread: vi.fn().mockResolvedValue(undefined),
  unflagThread: vi.fn().mockResolvedValue(undefined),
  // Step 4b additions — InboxPage imports these too now
  searchThreads: vi.fn().mockResolvedValue([]),
  snoozeThread: vi.fn().mockResolvedValue(undefined),
  unsnoozeThread: vi.fn().mockResolvedValue(undefined),
  listLabels: vi.fn().mockResolvedValue([]),
  createLabel: vi.fn(),
  addLabelToThread: vi.fn().mockResolvedValue(undefined),
  removeLabelFromThread: vi.fn().mockResolvedValue(undefined),
  resolveRecipients: vi.fn().mockResolvedValue([]),
  listRoleRecipients: vi.fn().mockResolvedValue([]),
  expandRoleRecipient: vi.fn().mockResolvedValue([]),
}));

vi.mock("@/services/email-account-service", () => ({
  listMyAccounts: (...args: unknown[]) => mockListMyAccounts(...args),
  sendMessage: (...args: unknown[]) => mockSendMessage(...args),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));


// ── Fixture data ─────────────────────────────────────────────────────

const ACCOUNT = {
  id: "acc-1",
  tenant_id: "t-1",
  account_type: "shared" as const,
  display_name: "Sales",
  email_address: "sales@example.com",
  provider_type: "gmail" as const,
  provider_config_keys: [],
  signature_html: null,
  reply_to_override: null,
  is_active: true,
  is_default: false,
  outbound_enabled: true,
  sync_status: "synced",
  created_by_user_id: null,
  created_at: "2026-05-07T00:00:00+00:00",
  updated_at: "2026-05-07T00:00:00+00:00",
};

const THREAD = {
  id: "thread-1",
  account_id: "acc-1",
  subject: "Hopkins case follow-up",
  sender_summary: "Hopkins FH <hopkins@example.com>",
  snippet: "Following up on the Anderson case...",
  last_message_at: "2026-05-07T10:00:00+00:00",
  message_count: 1,
  unread_count: 1,
  is_archived: false,
  is_flagged_thread: false,
  is_cross_tenant: true,
  cross_tenant_partner_tenant_id: "tenant-hopkins",
  label_ids: [],
  assigned_to_user_id: null,
};

const INBOUND_MESSAGE: MessageDetail = {
  id: "msg-1",
  thread_id: "thread-1",
  sender_email: "hopkins@example.com",
  sender_name: "Hopkins FH",
  subject: "Hopkins case follow-up",
  body_text: "Hi — following up on the Anderson case.",
  body_html: null,
  sent_at: "2026-05-07T10:00:00+00:00",
  received_at: "2026-05-07T10:00:00+00:00",
  direction: "inbound",
  is_read: false,
  is_flagged: false,
  in_reply_to_message_id: null,
  provider_message_id: "p-msg-1",
  to: [{ email_address: "sales@example.com", display_name: null }],
  cc: [],
  bcc: [],
};

const THREAD_DETAIL = {
  id: "thread-1",
  account_id: "acc-1",
  subject: "Hopkins case follow-up",
  is_archived: false,
  is_cross_tenant: true,
  cross_tenant_partner_tenant_id: "tenant-hopkins",
  label_ids: [],
  participants_summary: ["hopkins@example.com", "sales@example.com"],
  messages: [INBOUND_MESSAGE],
};


// ── InboxPage tests ──────────────────────────────────────────────────

describe("InboxPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListMyAccounts.mockResolvedValue([ACCOUNT]);
    mockListThreads.mockResolvedValue({
      threads: [THREAD],
      total: 1,
      page: 1,
      page_size: 50,
    });
    mockGetThreadDetail.mockResolvedValue(THREAD_DETAIL);
    // markRead returns void resolved
    mockMarkRead.mockResolvedValue(undefined);
  });

  async function renderInbox() {
    const { default: InboxPage } = await import("./InboxPage");
    return render(
      <MemoryRouter initialEntries={["/inbox"]}>
        <InboxPage />
      </MemoryRouter>,
    );
  }

  it("renders thread list from API", async () => {
    await renderInbox();
    expect(
      await screen.findByTestId("thread-row-thread-1"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Hopkins case follow-up/)).toBeInTheDocument();
  });

  it("filter strip switches status filter", async () => {
    const user = userEvent.setup();
    await renderInbox();
    await screen.findByTestId("thread-row-thread-1");
    await user.click(screen.getByTestId("filter-unread"));
    await waitFor(() => {
      const lastCallArgs = mockListThreads.mock.calls.at(-1)?.[0];
      expect(lastCallArgs?.status_filter).toBe("unread");
    });
  });

  it("clicking thread row loads detail + auto-marks read", async () => {
    const user = userEvent.setup();
    await renderInbox();
    await user.click(await screen.findByTestId("thread-row-thread-1"));
    await waitFor(() => {
      expect(mockGetThreadDetail).toHaveBeenCalledWith("thread-1");
    });
    // Auto-mark-read fires for inbound unread
    await waitFor(() => {
      expect(mockMarkRead).toHaveBeenCalledWith("msg-1");
    });
    // Cross-tenant pill renders
    expect(
      await screen.findByTestId("cross-tenant-pill"),
    ).toBeInTheDocument();
  });

  it("renders empty state when zero threads", async () => {
    mockListThreads.mockResolvedValue({
      threads: [],
      total: 0,
      page: 1,
      page_size: 50,
    });
    await renderInbox();
    // EmptyState renders "No threads" as title + description; just
    // assert at least one match exists.
    const matches = await screen.findAllByText(/No threads/i);
    expect(matches.length).toBeGreaterThan(0);
  });

  it("archive button mutates + optimistically removes thread", async () => {
    const user = userEvent.setup();
    await renderInbox();
    await user.click(await screen.findByTestId("thread-row-thread-1"));
    await screen.findByTestId("thread-archive-btn");
    await user.click(screen.getByTestId("thread-archive-btn"));
    await waitFor(() => {
      expect(mockArchiveThread).toHaveBeenCalledWith("thread-1");
    });
    // Optimistic removal — thread row gone
    await waitFor(() =>
      expect(screen.queryByTestId("thread-row-thread-1")).not.toBeInTheDocument(),
    );
  });
});


// ── InlineReplyForm tests (named export) ─────────────────────────────

describe("InlineReplyForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  async function renderForm(props: Partial<{
    mode: "reply" | "reply-all";
    originalMessage: typeof INBOUND_MESSAGE;
  }> = {}) {
    const { InlineReplyForm } = await import("./InboxPage");
    const onSent = vi.fn();
    const onCancel = vi.fn();
    render(
      <MemoryRouter>
        <InlineReplyForm
          account={ACCOUNT}
          sendFromAccountId={ACCOUNT.id}
          originalMessage={props.originalMessage ?? INBOUND_MESSAGE}
          mode={props.mode ?? "reply"}
          threadId="thread-1"
          onCancel={onCancel}
          onSent={onSent}
        />
      </MemoryRouter>,
    );
    return { onSent, onCancel };
  }

  it("pre-fills To with original sender + Re: subject prefix", async () => {
    await renderForm();
    const toInput = (await screen.findByTestId(
      "reply-to-input",
    )) as HTMLInputElement;
    expect(toInput.value).toBe("hopkins@example.com");
    const subj = (await screen.findByTestId(
      "reply-subject-input",
    )) as HTMLInputElement;
    expect(subj.value).toBe("Re: Hopkins case follow-up");
  });

  it("Re: subject prefix idempotent (no double-prefix)", async () => {
    const original = { ...INBOUND_MESSAGE, subject: "Re: Already prefixed" };
    await renderForm({ originalMessage: original });
    const subj = (await screen.findByTestId(
      "reply-subject-input",
    )) as HTMLInputElement;
    expect(subj.value).toBe("Re: Already prefixed");
  });

  it("reply-all pre-fills Cc from original to/cc minus self", async () => {
    const original = {
      ...INBOUND_MESSAGE,
      to: [
        { email_address: "sales@example.com", display_name: null }, // self — excluded
        { email_address: "other@example.com", display_name: null },
      ],
      cc: [{ email_address: "watcher@example.com", display_name: null }],
    };
    await renderForm({ mode: "reply-all", originalMessage: original });
    const cc = (await screen.findByTestId(
      "reply-cc-input",
    )) as HTMLInputElement;
    expect(cc.value).toContain("other@example.com");
    expect(cc.value).toContain("watcher@example.com");
    expect(cc.value).not.toContain("sales@example.com");
  });

  it("Send routes through sendMessage with thread_id + in_reply_to", async () => {
    const user = userEvent.setup();
    mockSendMessage.mockResolvedValue({
      message_id: "new-msg",
      thread_id: "thread-1",
      provider_message_id: "p-new",
      sent_at: "2026-05-07T11:00:00+00:00",
      direction: "outbound",
    });
    const { onSent } = await renderForm();
    await user.type(
      screen.getByTestId("reply-body-input"),
      "Sounds good.",
    );
    await user.click(screen.getByTestId("reply-send-btn"));
    await waitFor(() => {
      expect(mockSendMessage).toHaveBeenCalledWith(
        ACCOUNT.id,
        expect.objectContaining({
          to: [{ email_address: "hopkins@example.com" }],
          subject: "Re: Hopkins case follow-up",
          body_text: "Sounds good.",
          thread_id: "thread-1",
          in_reply_to_message_id: "msg-1",
        }),
      );
    });
    await waitFor(() => expect(onSent).toHaveBeenCalled());
  });

  it("Discard cancels without sending", async () => {
    const user = userEvent.setup();
    const { onCancel } = await renderForm();
    await user.click(screen.getByText(/^Discard$/));
    expect(onCancel).toHaveBeenCalled();
    expect(mockSendMessage).not.toHaveBeenCalled();
  });

  it("Send disabled when body empty", async () => {
    await renderForm();
    expect(screen.getByTestId("reply-send-btn")).toBeDisabled();
  });
});
