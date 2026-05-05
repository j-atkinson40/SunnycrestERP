/**
 * Settings → Calendar Accounts — Phase W-4b Layer 1 Calendar Step 1.
 *
 * Tenant-admin surface for managing CalendarAccount records + per-account
 * access scope. Subsequent Steps 2-N add the calendar surface (grid /
 * agenda views) + sync activation; Step 1 ships the account-management
 * lifecycle.
 *
 * Mirrors the EmailAccountsPage shape but tighter — Step 1 doesn't ship
 * OAuth flows, sync activation, or outbound, so the Step 1 page is
 * scoped to: list accounts + create/edit/delete + access scope
 * management. Sync status renders a placeholder pill until Step 2.
 *
 * **Per Q3 confirmed pre-build**: only 3 provider types in the picker
 * (google_calendar / msgraph / local). CalDAV omitted entirely.
 *
 * **Per Q4 confirmed pre-build**: local provider ships functional —
 * tenant admins can immediately create local calendar accounts +
 * events without OAuth.
 */

import { useEffect, useState } from "react";
import {
  Calendar as CalendarIcon,
  MoreHorizontal,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
  calendarSyncNow,
  createCalendarAccount,
  deleteCalendarAccount,
  getCalendarOAuthAuthorizeUrl,
  grantCalendarAccess,
  listCalendarAccessGrants,
  listCalendarAccounts,
  listCalendarProviders,
  revokeCalendarAccess,
} from "@/services/calendar-account-service";
import { setPendingCalendarConnect } from "@/pages/settings/CalendarOAuthCallback";
import type {
  CalendarAccessLevel,
  CalendarAccount,
  CalendarAccountAccess,
  CalendarAccountType,
  CalendarProviderInfo,
  CalendarProviderType,
} from "@/types/calendar-account";

// ─────────────────────────────────────────────────────────────────────
// Provider display helpers
// ─────────────────────────────────────────────────────────────────────

function providerLabel(
  providers: CalendarProviderInfo[],
  ptype: CalendarProviderType,
): string {
  return providers.find((p) => p.provider_type === ptype)?.display_label ?? ptype;
}

// ─────────────────────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────────────────────

export default function CalendarAccountsPage() {
  const [accounts, setAccounts] = useState<CalendarAccount[]>([]);
  const [providers, setProviders] = useState<CalendarProviderInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [accessOpen, setAccessOpen] = useState<CalendarAccount | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [accs, provs] = await Promise.all([
        listCalendarAccounts(true),
        listCalendarProviders(),
      ]);
      setAccounts(accs);
      setProviders(provs);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load calendar accounts",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleDelete(account: CalendarAccount) {
    if (
      !confirm(
        `Soft-delete calendar account "${account.display_name}"? It can be reactivated later.`,
      )
    ) {
      return;
    }
    try {
      await deleteCalendarAccount(account.id);
      toast.success(`${account.display_name} deactivated.`);
      refresh();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to delete account",
      );
    }
  }

  async function handleSyncNow(account: CalendarAccount) {
    try {
      await calendarSyncNow(account.id);
      toast.success(`Sync queued for ${account.display_name}.`);
      // Refresh after a beat so backfill_status updates surface.
      setTimeout(refresh, 500);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to start sync",
      );
    }
  }

  async function handleConnectProvider(
    providerType: "google_calendar" | "msgraph",
  ) {
    const email = window.prompt(
      `Connect ${providerType === "google_calendar" ? "Google Calendar" : "Microsoft 365"} — what's the primary email address for the calendar?`,
    );
    if (!email || !email.includes("@")) {
      return;
    }
    const redirectUri = `${window.location.origin}/settings/calendar/oauth-callback`;
    try {
      const r = await getCalendarOAuthAuthorizeUrl(providerType, redirectUri);
      // Stash pre-flight metadata so the callback page has it.
      setPendingCalendarConnect({
        provider_type: providerType,
        primary_email_address: email.trim().toLowerCase(),
        account_type: "personal",
        redirect_uri: redirectUri,
      });
      // Navigate to provider consent screen.
      window.location.href = r.authorize_url;
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to start OAuth flow",
      );
    }
  }

  return (
    <div className="space-y-6 p-6 max-w-6xl mx-auto">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-h2 font-plex-serif font-medium text-content-strong">
            Calendar Accounts
          </h1>
          <p className="text-body-sm text-content-muted mt-1 max-w-2xl">
            Manage calendar accounts that the platform syncs with. Connect
            external providers (Google Calendar, Microsoft 365) or create local
            Bridgeable-native calendars for purely operational events.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() => handleConnectProvider("google_calendar")}
          >
            <CalendarIcon className="h-4 w-4 mr-2" />
            Connect Google Calendar
          </Button>
          <Button
            variant="outline"
            onClick={() => handleConnectProvider("msgraph")}
          >
            <CalendarIcon className="h-4 w-4 mr-2" />
            Connect Microsoft 365
          </Button>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            New local calendar
          </Button>
        </div>
      </div>

      {/* Coexistence note */}
      <Alert>
        <CalendarIcon className="h-4 w-4" />
        <AlertTitle>Coexists with the Vault iCal feed</AlertTitle>
        <AlertDescription>
          Operators can still subscribe their phone calendars to the existing
          one-way <code className="text-body-sm">/vault/calendar.ics</code>{" "}
          feed. This page manages the new bidirectional Calendar primitive —
          provider sync, attendees, cross-tenant joint scheduling. Step 1 ships
          the foundation; sync activation lands in Step 2.
        </AlertDescription>
      </Alert>

      {error && (
        <Alert variant="error">
          <AlertTitle>Couldn't load accounts</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <Card>
          <CardContent className="py-12 text-center text-content-muted">
            Loading…
          </CardContent>
        </Card>
      ) : accounts.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <EmptyState
              icon={CalendarIcon}
              title="No calendar accounts yet"
              description="Create a local Bridgeable calendar to start tracking operational events, or connect Google / Microsoft to sync existing calendars."
              action={
                <Button onClick={() => setCreateOpen(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  New calendar account
                </Button>
              }
            />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Display name</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Sync status</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {accounts.map((acc) => (
                  <TableRow key={acc.id}>
                    <TableCell className="font-medium">
                      {acc.display_name}
                      {acc.is_default && (
                        <span className="ml-2 text-caption text-brass">
                          default
                        </span>
                      )}
                    </TableCell>
                    <TableCell>
                      {providerLabel(providers, acc.provider_type)}
                    </TableCell>
                    <TableCell className="font-plex-mono text-body-sm">
                      {acc.primary_email_address}
                    </TableCell>
                    <TableCell>
                      <span className="capitalize">{acc.account_type}</span>
                    </TableCell>
                    <TableCell>
                      {/* Step 1: sync_status is null until Step 2 ships sync.
                          Render a placeholder so admins see the status is
                          coming, not broken. */}
                      <StatusPill
                        status={acc.sync_status ?? "pending"}
                        label={
                          acc.sync_status === null
                            ? "Not yet synced"
                            : undefined
                        }
                      />
                    </TableCell>
                    <TableCell>
                      <StatusPill
                        status={acc.is_active ? "active" : "inactive"}
                      />
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          {acc.is_active && (
                            <DropdownMenuItem
                              onClick={() => handleSyncNow(acc)}
                            >
                              <RefreshCw className="h-4 w-4 mr-2" />
                              Sync now
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuItem onClick={() => setAccessOpen(acc)}>
                            <Users className="h-4 w-4 mr-2" />
                            Manage access
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          {acc.is_active && (
                            <DropdownMenuItem
                              onClick={() => handleDelete(acc)}
                              variant="destructive"
                            >
                              <Trash2 className="h-4 w-4 mr-2" />
                              Deactivate
                            </DropdownMenuItem>
                          )}
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

      {/* Step 2 boundary banner — explains what's deferred */}
      <Alert>
        <ShieldCheck className="h-4 w-4" />
        <AlertTitle>Step 2 shipped — what's next</AlertTitle>
        <AlertDescription className="space-y-1">
          <p>
            Real OAuth + sync activation for Google Calendar + Microsoft 365 +
            RRULE engine for recurring events ship today. Local Bridgeable-
            native events also work end-to-end. The following capabilities
            ship in subsequent steps:
          </p>
          <ul className="list-disc ml-6 text-body-sm">
            <li>
              <strong>Step 2.1:</strong> Provider webhook receivers (Google
              Push Notifications + MS Graph subscriptions) + materialization
              cache for ≤7-day instances.
            </li>
            <li>
              <strong>Step 3:</strong> Outbound iTIP scheduling + free/busy
              cross-tenant queries + state-changes-generate-events drafting.
            </li>
            <li>
              <strong>Step 4:</strong> Cross-tenant joint events + magic-link
              for external participants.
            </li>
            <li>
              <strong>Step 5:</strong> Calendar grid / agenda view + Pulse
              calendar widget + briefing integration.
            </li>
          </ul>
        </AlertDescription>
      </Alert>

      <CreateAccountDialog
        open={createOpen}
        providers={providers}
        onClose={() => setCreateOpen(false)}
        onCreated={refresh}
      />
      {accessOpen && (
        <AccessDialog
          account={accessOpen}
          onClose={() => setAccessOpen(null)}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Create dialog
// ─────────────────────────────────────────────────────────────────────

interface CreateDialogProps {
  open: boolean;
  providers: CalendarProviderInfo[];
  onClose: () => void;
  onCreated: () => void;
}

function CreateAccountDialog({
  open,
  providers,
  onClose,
  onCreated,
}: CreateDialogProps) {
  const [accountType, setAccountType] =
    useState<CalendarAccountType>("shared");
  const [providerType, setProviderType] =
    useState<CalendarProviderType>("local");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [timezone, setTimezone] = useState("America/New_York");
  const [isDefault, setIsDefault] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Reset form when dialog opens.
  useEffect(() => {
    if (open) {
      setAccountType("shared");
      setProviderType("local");
      setDisplayName("");
      setEmail("");
      setTimezone("America/New_York");
      setIsDefault(false);
      setErr(null);
    }
  }, [open]);

  async function handleSubmit() {
    setErr(null);
    if (!displayName.trim() || !email.includes("@")) {
      setErr("Display name and a valid email are required.");
      return;
    }
    setSubmitting(true);
    try {
      await createCalendarAccount({
        account_type: accountType,
        display_name: displayName.trim(),
        primary_email_address: email.trim().toLowerCase(),
        provider_type: providerType,
        default_event_timezone: timezone,
        is_default: isDefault,
      });
      toast.success(`Calendar account "${displayName}" created.`);
      onCreated();
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to create account");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New calendar account</DialogTitle>
          <DialogDescription>
            Create a calendar account this tenant tracks. Local accounts are
            functional immediately; external providers (Google / Microsoft)
            require OAuth in Step 2.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <Label htmlFor="provider-type">Provider</Label>
            <Select
              value={providerType}
              onValueChange={(v) =>
                setProviderType(v as CalendarProviderType)
              }
            >
              <SelectTrigger id="provider-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {providers.map((p) => (
                  <SelectItem key={p.provider_type} value={p.provider_type}>
                    {p.display_label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {providerType !== "local" && (
              <p className="text-caption text-content-muted mt-1">
                External providers require OAuth (Step 2). For now, this row
                is created as a placeholder; sync activates after OAuth lands.
              </p>
            )}
          </div>

          <div>
            <Label htmlFor="account-type">Account type</Label>
            <Select
              value={accountType}
              onValueChange={(v) => setAccountType(v as CalendarAccountType)}
            >
              <SelectTrigger id="account-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="shared">
                  Shared (multi-user, e.g. production schedule)
                </SelectItem>
                <SelectItem value="personal">
                  Personal (single-user)
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="display-name">Display name</Label>
            <Input
              id="display-name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Production Schedule"
              required
            />
          </div>

          <div>
            <Label htmlFor="primary-email">Primary email address</Label>
            <Input
              id="primary-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="production@your-tenant.com"
              required
            />
          </div>

          <div>
            <Label htmlFor="timezone">Default event timezone (IANA)</Label>
            <Input
              id="timezone"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              placeholder="America/New_York"
            />
          </div>

          <label className="flex items-center gap-2 text-body-sm">
            <input
              type="checkbox"
              checked={isDefault}
              onChange={(e) => setIsDefault(e.target.checked)}
            />
            Make this the tenant's default calendar
          </label>

          {err && (
            <Alert variant="error">
              <AlertDescription>{err}</AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Creating…" : "Create account"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Access dialog
// ─────────────────────────────────────────────────────────────────────

interface AccessDialogProps {
  account: CalendarAccount;
  onClose: () => void;
}

function AccessDialog({ account, onClose }: AccessDialogProps) {
  const [grants, setGrants] = useState<CalendarAccountAccess[]>([]);
  const [loading, setLoading] = useState(true);
  const [grantUserId, setGrantUserId] = useState("");
  const [grantLevel, setGrantLevel] =
    useState<CalendarAccessLevel>("read_write");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setErr(null);
    try {
      const result = await listCalendarAccessGrants(account.id, true);
      setGrants(result);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load access grants");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [account.id]);

  async function handleGrant() {
    if (!grantUserId.trim()) return;
    setSubmitting(true);
    setErr(null);
    try {
      await grantCalendarAccess(account.id, {
        user_id: grantUserId.trim(),
        access_level: grantLevel,
      });
      setGrantUserId("");
      toast.success("Access granted.");
      refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to grant access");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRevoke(userId: string) {
    if (!confirm("Revoke access for this user?")) return;
    try {
      await revokeCalendarAccess(account.id, userId);
      toast.success("Access revoked.");
      refresh();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to revoke");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => (o ? null : onClose())}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Access — {account.display_name}</DialogTitle>
          <DialogDescription>
            Manage which users in this tenant can read or modify this calendar.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {loading ? (
            <div className="text-content-muted text-body-sm">Loading…</div>
          ) : grants.length === 0 ? (
            <div className="text-content-muted text-body-sm py-4 text-center">
              No grants yet. The account creator was auto-granted admin access
              on create.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead>Access level</TableHead>
                  <TableHead>Granted</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead className="w-20"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {grants.map((g) => (
                  <TableRow key={g.id}>
                    <TableCell>
                      <div className="font-medium">
                        {g.user_name ?? g.user_email ?? g.user_id}
                      </div>
                      {g.user_email && g.user_name && (
                        <div className="text-caption text-content-muted">
                          {g.user_email}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="capitalize">
                      {g.access_level.replace("_", " ")}
                    </TableCell>
                    <TableCell className="text-body-sm text-content-muted">
                      {new Date(g.granted_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <StatusPill
                        status={g.revoked_at ? "inactive" : "active"}
                      />
                    </TableCell>
                    <TableCell>
                      {!g.revoked_at && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRevoke(g.user_id)}
                        >
                          Revoke
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          <div className="border-t border-border-subtle pt-4">
            <h3 className="text-body font-medium mb-2">Grant access</h3>
            <div className="flex gap-2">
              <Input
                placeholder="User ID"
                value={grantUserId}
                onChange={(e) => setGrantUserId(e.target.value)}
                className="flex-1"
              />
              <Select
                value={grantLevel}
                onValueChange={(v) =>
                  setGrantLevel(v as CalendarAccessLevel)
                }
              >
                <SelectTrigger className="w-40">
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
                disabled={submitting || !grantUserId.trim()}
              >
                Grant
              </Button>
            </div>
            <p className="text-caption text-content-muted mt-2">
              Step 1 boundary: user lookup by ID for now. Step 2 wires a user
              picker against the tenant directory.
            </p>
          </div>

          {err && (
            <Alert variant="error">
              <AlertDescription>{err}</AlertDescription>
            </Alert>
          )}
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
