/**
 * Settings → Email Accounts — Phase W-4b Layer 1 Step 1.
 *
 * Tenant-admin surface for connecting / managing EmailAccount records
 * + per-account access scope. Subsequent Steps 2-N add the inbox UI
 * + composition surface; Step 1 ships the connection lifecycle.
 *
 * Architectural note: this is the *conversation/inbox* email primitive
 * (BRIDGEABLE_MASTER §3.26.15), distinct from existing transactional
 * send infrastructure (Phase D-7 DeliveryService, /admin/documents/deliveries).
 *
 * OAuth flow scaffolding: clicking "Connect Gmail" or "Connect Microsoft"
 * fetches an authorize URL from the backend and navigates the user to
 * the provider's consent screen. Step 1 returns a placeholder URL with
 * `client_id=REPLACE_IN_STEP_2`; Step 2 wires real client credentials.
 */

import { useEffect, useState } from "react";
import {
  Mail,
  MoreHorizontal,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  createAccount,
  deleteAccount,
  getOAuthAuthorizeUrl,
  grantAccess,
  listAccessGrants,
  listAccounts,
  listProviders,
  revokeAccess,
  syncNow,
  updateAccount,
} from "@/services/email-account-service";
import { setPendingConnect } from "./EmailOAuthCallback";
import type {
  AccessLevel,
  AccountType,
  EmailAccount,
  EmailAccountAccess,
  ProviderInfo,
  ProviderType,
} from "@/types/email-account";

const PROVIDER_LABEL: Record<ProviderType, string> = {
  gmail: "Gmail",
  msgraph: "Microsoft 365",
  imap: "IMAP",
  transactional: "Transactional (outbound only)",
};

export default function EmailAccountsPage() {
  const [accounts, setAccounts] = useState<EmailAccount[]>([]);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connectOpen, setConnectOpen] = useState(false);
  const [accessDialogAccount, setAccessDialogAccount] =
    useState<EmailAccount | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<EmailAccount | null>(null);

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const [a, p] = await Promise.all([
        listAccounts(true),
        listProviders(),
      ]);
      setAccounts(a);
      setProviders(p);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Failed to load email accounts.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  return (
    <div className="container max-w-5xl mx-auto py-8 space-y-6" data-testid="email-accounts-page">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-h2 font-plex-serif font-medium text-content-strong">
            Email accounts
          </h1>
          <p className="text-body text-content-muted mt-1 max-w-2xl">
            Connect Gmail, Microsoft 365, or IMAP mailboxes to bring
            email conversations into Bridgeable. Each account can be
            shared across teammates with read / read-write / admin
            access scoped per user.
          </p>
        </div>
        <Button onClick={() => setConnectOpen(true)} data-testid="connect-account-btn">
          <Plus className="h-4 w-4 mr-2" />
          Connect account
        </Button>
      </header>

      {error && (
        <Alert variant="error">
          <AlertTitle>Couldn't load email accounts</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {!loading && accounts.length === 0 ? (
        <EmptyState
          icon={Mail}
          title="No email accounts yet"
          description={
            "Connect your first inbox to start managing conversations " +
            "in Bridgeable. Shared mailboxes (sales@, info@) work " +
            "alongside personal accounts."
          }
          action={
            <Button onClick={() => setConnectOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Connect account
            </Button>
          }
        />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Account</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {accounts.map((acc) => (
                  <TableRow key={acc.id} data-testid={`account-row-${acc.id}`}>
                    <TableCell>
                      <div className="font-medium text-content-strong">
                        {acc.display_name}
                        {acc.is_default && (
                          <span className="ml-2 text-caption text-accent">
                            default
                          </span>
                        )}
                      </div>
                      <div className="text-body-sm text-content-muted">
                        {acc.email_address}
                      </div>
                      {/* Step 2 — credential status sub-row. Surfaces
                       OAuth-completed vs pending state so admins see
                       which accounts have credentials persisted vs
                       awaiting OAuth completion. */}
                      {acc.last_credential_op && (
                        <div className="text-caption text-content-subtle font-plex-mono mt-0.5">
                          credentials: {acc.last_credential_op}
                          {acc.last_credential_op_at &&
                            ` · ${new Date(acc.last_credential_op_at).toLocaleDateString()}`}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-body-sm">
                      {PROVIDER_LABEL[acc.provider_type] ?? acc.provider_type}
                    </TableCell>
                    <TableCell className="text-body-sm capitalize">
                      {acc.account_type}
                    </TableCell>
                    <TableCell>
                      {acc.is_active ? (
                        <StatusPill status={acc.sync_status ?? "pending"} />
                      ) : (
                        <StatusPill status="inactive" />
                      )}
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger
                          render={
                            <Button
                              variant="ghost"
                              size="icon"
                              data-testid={`account-menu-${acc.id}`}
                            >
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          }
                        />
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onSelect={async () => {
                              try {
                                await syncNow(acc.id);
                                toast.success("Sync queued");
                                reload();
                              } catch (e) {
                                toast.error(
                                  e instanceof Error
                                    ? e.message
                                    : "Sync failed",
                                );
                              }
                            }}
                            data-testid={`sync-now-${acc.id}`}
                          >
                            <RefreshCw className="h-4 w-4 mr-2" />
                            Sync now
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onSelect={() => setAccessDialogAccount(acc)}
                          >
                            <Users className="h-4 w-4 mr-2" />
                            Manage access
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onSelect={async () => {
                              await updateAccount(acc.id, {
                                is_default: !acc.is_default,
                              });
                              toast.success(
                                acc.is_default
                                  ? "Removed as default"
                                  : "Set as default",
                              );
                              reload();
                            }}
                          >
                            <ShieldCheck className="h-4 w-4 mr-2" />
                            {acc.is_default ? "Remove as default" : "Set as default"}
                          </DropdownMenuItem>
                          {acc.is_active ? (
                            <DropdownMenuItem
                              onSelect={async () => {
                                await updateAccount(acc.id, {
                                  is_active: false,
                                });
                                toast.success("Account disabled");
                                reload();
                              }}
                            >
                              Disable
                            </DropdownMenuItem>
                          ) : (
                            <DropdownMenuItem
                              onSelect={async () => {
                                await updateAccount(acc.id, {
                                  is_active: true,
                                });
                                toast.success("Account re-enabled");
                                reload();
                              }}
                            >
                              Re-enable
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onSelect={() => setConfirmDelete(acc)}
                            className="text-status-error"
                          >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <ConnectAccountDialog
        open={connectOpen}
        onClose={() => setConnectOpen(false)}
        providers={providers}
        onCreated={() => {
          setConnectOpen(false);
          reload();
        }}
      />

      {accessDialogAccount && (
        <ManageAccessDialog
          account={accessDialogAccount}
          onClose={() => setAccessDialogAccount(null)}
        />
      )}

      {confirmDelete && (
        <Dialog open onOpenChange={(o) => !o && setConfirmDelete(null)}>
          <DialogContent data-testid="confirm-delete-dialog">
            <DialogHeader>
              <DialogTitle>Delete email account?</DialogTitle>
              <DialogDescription>
                {confirmDelete.email_address} will be soft-disabled. Past
                conversations remain in audit logs but no new email will
                sync. You can re-enable later from the inactive list.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setConfirmDelete(null)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={async () => {
                  await deleteAccount(confirmDelete.id);
                  toast.success("Email account deleted");
                  setConfirmDelete(null);
                  reload();
                }}
              >
                Delete
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Connect Account dialog
// ─────────────────────────────────────────────────────────────────────

interface ConnectDialogProps {
  open: boolean;
  onClose: () => void;
  providers: ProviderInfo[];
  onCreated: () => void;
}

function ConnectAccountDialog({
  open,
  onClose,
  providers,
  onCreated,
}: ConnectDialogProps) {
  const [step, setStep] = useState<"pick-provider" | "config">("pick-provider");
  const [providerType, setProviderType] = useState<ProviderType | null>(null);
  const [accountType, setAccountType] = useState<AccountType>("shared");
  const [displayName, setDisplayName] = useState("");
  const [emailAddress, setEmailAddress] = useState("");
  const [imapServer, setImapServer] = useState("");
  const [imapPort, setImapPort] = useState("993");
  const [smtpServer, setSmtpServer] = useState("");
  const [smtpPort, setSmtpPort] = useState("587");
  const [imapUsername, setImapUsername] = useState("");
  const [imapPassword, setImapPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function reset() {
    setStep("pick-provider");
    setProviderType(null);
    setAccountType("shared");
    setDisplayName("");
    setEmailAddress("");
    setImapServer("");
    setImapPort("993");
    setSmtpServer("");
    setSmtpPort("587");
    setImapUsername("");
    setImapPassword("");
    setSubmitting(false);
  }

  async function handleOAuthConnect(p: "gmail" | "msgraph") {
    // Step 2 OAuth flow:
    //   1. User MUST supply email_address + display_name first so we
    //      can stash pre-flight metadata for the callback to use.
    //   2. We issue an authorize URL (backend stamps a CSRF state nonce
    //      in oauth_state_nonces).
    //   3. We localStorage-stash the pre-flight metadata.
    //   4. We navigate to the provider's consent screen.
    //   5. Provider redirects back to /settings/email/oauth-callback
    //      which POSTs the code+state to /oauth/callback for exchange.
    if (!emailAddress.trim()) {
      toast.error(
        "Enter the email address first so we know which account you " +
          "are connecting.",
      );
      return;
    }
    try {
      const redirectUri = `${window.location.origin}/settings/email/oauth-callback`;
      const { authorize_url } = await getOAuthAuthorizeUrl(p, redirectUri);
      setPendingConnect({
        provider_type: p,
        email_address: emailAddress.trim().toLowerCase(),
        display_name: displayName.trim() || emailAddress.trim(),
        account_type: accountType,
        redirect_uri: redirectUri,
      });
      window.location.href = authorize_url;
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "Failed to start OAuth flow.",
      );
    }
  }

  async function handleSubmit() {
    if (!providerType) return;
    setSubmitting(true);
    try {
      const provider_config: Record<string, unknown> = {};
      if (providerType === "imap") {
        provider_config.imap_server = imapServer;
        provider_config.imap_port = Number(imapPort);
        provider_config.smtp_server = smtpServer;
        provider_config.smtp_port = Number(smtpPort);
        provider_config.username = imapUsername;
        // NOTE Step 1: password captured plaintext in provider_config.
        // Step 2 wires encryption-at-rest layer + drops password from
        // any read response. Don't ship Step 1 to production.
        provider_config.password_step_1_placeholder = imapPassword;
      }
      await createAccount({
        account_type: accountType,
        display_name: displayName.trim(),
        email_address: emailAddress.trim().toLowerCase(),
        provider_type: providerType,
        provider_config,
      });
      toast.success("Email account connected");
      reset();
      onCreated();
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "Failed to create account.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          reset();
          onClose();
        }
      }}
    >
      <DialogContent className="max-w-lg" data-testid="connect-dialog">
        <DialogHeader>
          <DialogTitle>
            {step === "pick-provider"
              ? "Connect an email account"
              : `Connect ${providerType ? PROVIDER_LABEL[providerType] : ""}`}
          </DialogTitle>
          <DialogDescription>
            {step === "pick-provider"
              ? "Choose a provider. OAuth providers redirect you to the provider's sign-in page."
              : "Configure the account details below."}
          </DialogDescription>
        </DialogHeader>

        {step === "pick-provider" && (
          <div className="space-y-2" data-testid="provider-picker">
            {providers.map((p) => (
              <Button
                key={p.provider_type}
                variant="outline"
                className="w-full justify-start text-left h-auto py-3"
                onClick={() => {
                  setProviderType(p.provider_type);
                  // ALL providers go through the config step now —
                  // even OAuth providers need email_address + display_name
                  // captured first so the post-redirect callback knows
                  // which account is being connected (Step 2 pre-flight
                  // metadata stash).
                  setStep("config");
                }}
                data-testid={`provider-${p.provider_type}`}
              >
                <div>
                  <div className="font-medium">{p.display_label}</div>
                  <div className="text-caption text-content-muted">
                    {p.supports_inbound
                      ? p.supports_realtime
                        ? "Inbound + outbound, realtime sync"
                        : "Inbound + outbound, polling sync"
                      : "Outbound only"}
                  </div>
                </div>
              </Button>
            ))}
          </div>
        )}

        {step === "config" && providerType && (
          <div className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="display-name">Display name</Label>
              <Input
                id="display-name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Sales Inbox"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="email-address">Email address</Label>
              <Input
                id="email-address"
                type="email"
                value={emailAddress}
                onChange={(e) => setEmailAddress(e.target.value)}
                placeholder="sales@yourdomain.com"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="account-type">Account type</Label>
              <Select
                value={accountType}
                onValueChange={(v) => setAccountType(v as AccountType)}
              >
                <SelectTrigger id="account-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="shared">
                    Shared (multiple teammates can access)
                  </SelectItem>
                  <SelectItem value="personal">
                    Personal (single user inbox)
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            {providerType === "imap" && (
              <div className="space-y-3 border-t border-border-subtle pt-4">
                <div className="text-body-sm font-medium">IMAP / SMTP credentials</div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label htmlFor="imap-server">IMAP server</Label>
                    <Input
                      id="imap-server"
                      value={imapServer}
                      onChange={(e) => setImapServer(e.target.value)}
                      placeholder="imap.example.com"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="imap-port">IMAP port</Label>
                    <Input
                      id="imap-port"
                      value={imapPort}
                      onChange={(e) => setImapPort(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="smtp-server">SMTP server</Label>
                    <Input
                      id="smtp-server"
                      value={smtpServer}
                      onChange={(e) => setSmtpServer(e.target.value)}
                      placeholder="smtp.example.com"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="smtp-port">SMTP port</Label>
                    <Input
                      id="smtp-port"
                      value={smtpPort}
                      onChange={(e) => setSmtpPort(e.target.value)}
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="imap-username">Username</Label>
                  <Input
                    id="imap-username"
                    value={imapUsername}
                    onChange={(e) => setImapUsername(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="imap-password">Password</Label>
                  <Input
                    id="imap-password"
                    type="password"
                    value={imapPassword}
                    onChange={(e) => setImapPassword(e.target.value)}
                  />
                </div>
              </div>
            )}

            {providerType === "transactional" && (
              <Alert variant="info">
                <AlertTitle>Outbound only</AlertTitle>
                <AlertDescription>
                  Transactional accounts route through the platform's
                  existing email infrastructure (Resend). They cannot
                  receive replies into the Bridgeable inbox. Use Gmail
                  or Microsoft 365 for two-way conversations.
                </AlertDescription>
              </Alert>
            )}
          </div>
        )}

        <DialogFooter>
          {step === "config" && (
            <>
              <Button
                variant="outline"
                onClick={() => setStep("pick-provider")}
              >
                Back
              </Button>
              {providerType === "gmail" || providerType === "msgraph" ? (
                <Button
                  onClick={() => handleOAuthConnect(providerType)}
                  disabled={!emailAddress.trim()}
                  data-testid="submit-oauth-connect"
                >
                  Continue to {PROVIDER_LABEL[providerType]} sign-in
                </Button>
              ) : (
                <Button
                  onClick={handleSubmit}
                  disabled={submitting || !displayName || !emailAddress}
                  data-testid="submit-create-account"
                >
                  Create account
                </Button>
              )}
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Manage Access dialog
// ─────────────────────────────────────────────────────────────────────

function ManageAccessDialog({
  account,
  onClose,
}: {
  account: EmailAccount;
  onClose: () => void;
}) {
  const [grants, setGrants] = useState<EmailAccountAccess[]>([]);
  const [loading, setLoading] = useState(true);
  const [newUserId, setNewUserId] = useState("");
  const [newLevel, setNewLevel] = useState<AccessLevel>("read");

  async function reload() {
    setLoading(true);
    try {
      setGrants(await listAccessGrants(account.id));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [account.id]);

  async function handleGrant() {
    if (!newUserId.trim()) return;
    try {
      await grantAccess(account.id, newUserId.trim(), newLevel);
      toast.success("Access granted");
      setNewUserId("");
      reload();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to grant access.");
    }
  }

  async function handleRevoke(userId: string) {
    try {
      await revokeAccess(account.id, userId);
      toast.success("Access revoked");
      reload();
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "Failed to revoke access.",
      );
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl" data-testid="access-dialog">
        <DialogHeader>
          <DialogTitle>Manage access — {account.display_name}</DialogTitle>
          <DialogDescription>
            Control which teammates can read or send from this email
            account. Read = view threads. Read-write = view + reply / send.
            Admin = full control including managing access.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <div className="text-body-sm font-medium mb-2">Current access</div>
            {loading ? (
              <div className="text-body-sm text-content-muted">Loading…</div>
            ) : grants.length === 0 ? (
              <div className="text-body-sm text-content-muted">
                No active access grants.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User</TableHead>
                    <TableHead>Access level</TableHead>
                    <TableHead className="w-12"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {grants.map((g) => (
                    <TableRow key={g.id} data-testid={`grant-row-${g.id}`}>
                      <TableCell>
                        <div className="font-medium">
                          {g.user_name ?? g.user_id}
                        </div>
                        {g.user_email && (
                          <div className="text-caption text-content-muted">
                            {g.user_email}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <StatusPill status={g.access_level} />
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRevoke(g.user_id)}
                        >
                          Revoke
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>

          <div className="border-t border-border-subtle pt-4 space-y-3">
            <div className="text-body-sm font-medium">Grant access</div>
            <div className="grid grid-cols-[1fr_auto_auto] gap-2">
              <Input
                placeholder="User ID (uuid)"
                value={newUserId}
                onChange={(e) => setNewUserId(e.target.value)}
                data-testid="grant-user-id"
              />
              <Select
                value={newLevel}
                onValueChange={(v) => setNewLevel(v as AccessLevel)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="read">Read</SelectItem>
                  <SelectItem value="read_write">Read &amp; write</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
              <Button
                onClick={handleGrant}
                disabled={!newUserId.trim()}
                data-testid="submit-grant-access"
              >
                Grant
              </Button>
            </div>
            <div className="text-caption text-content-subtle">
              Step 1: enter raw user UUIDs. A user picker dropdown ships
              alongside the inbox UI in Step 4.
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
