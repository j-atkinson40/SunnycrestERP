/**
 * /settings/portal-users — Workflow Arc Phase 8e.2.1.
 *
 * Tenant-admin surface for managing portal users (drivers today;
 * future yard operators, removal staff, family/supplier portals).
 *
 * The canonical path for creating new drivers: admin invites a
 * portal user into a driver space → auto-creates Driver row →
 * sends invite email → user sets password via token → logs in.
 *
 * Phase 8e.2.1 ships the full CRUD with status filters, per-row
 * actions, and invite flow. Mobile-responsive but desktop-first
 * per audit (admin pages aren't the primary mobile surface).
 */

import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  KeyRound,
  LockKeyhole,
  Mail,
  MoreHorizontal,
  Plus,
  UserX,
} from "lucide-react";
import { toast } from "sonner";

import { Alert } from "@/components/ui/alert";
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
  deactivatePortalUser,
  invitePortalUser,
  listPortalUsers,
  reactivatePortalUser,
  resendInvite,
  resetPortalUserPassword,
  unlockPortalUser,
} from "@/services/portal-admin-service";
import { useSpaces } from "@/contexts/space-context";
import type {
  PortalUserStatus,
  PortalUserSummary,
} from "@/types/portal-admin";

// ── Status → pill mapping ────────────────────────────────────────

const STATUS_MAP: Record<PortalUserStatus, { label: string; variant: "success" | "warning" | "error" | "neutral" }> = {
  active: { label: "Active", variant: "success" },
  pending: { label: "Pending invite", variant: "warning" },
  locked: { label: "Locked", variant: "error" },
  inactive: { label: "Inactive", variant: "neutral" },
};


// ── Main page ─────────────────────────────────────────────────────


export default function PortalUsersSettings() {
  const [users, setUsers] = useState<PortalUserSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<PortalUserStatus | "all">(
    "all",
  );
  const [inviteOpen, setInviteOpen] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const r = await listPortalUsers(
        statusFilter === "all" ? {} : { status: statusFilter },
      );
      setUsers(r.users);
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "Couldn't load portal users.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  return (
    <div className="mx-auto max-w-content p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-h2 font-display font-medium text-content-strong">
            Portal users
          </h1>
          <p className="mt-1 text-body-sm text-content-muted">
            Invite and manage users who access the tenant portal
            (drivers today; future operational roles). Drivers
            invited into a Driver space are auto-linked to a new
            Driver record.
          </p>
        </div>
        <Button
          onClick={() => setInviteOpen(true)}
          data-testid="invite-portal-user-btn"
        >
          <Plus className="mr-1.5 h-4 w-4" />
          Invite user
        </Button>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-3">
        <Label htmlFor="status-filter" className="text-body-sm">
          Status:
        </Label>
        <Select
          value={statusFilter}
          onValueChange={(v) =>
            setStatusFilter((v ?? "all") as typeof statusFilter)
          }
        >
          <SelectTrigger id="status-filter" className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="pending">Pending invite</SelectItem>
            <SelectItem value="locked">Locked</SelectItem>
            <SelectItem value="inactive">Inactive</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-8 text-center text-body-sm text-content-muted">
              Loading…
            </div>
          ) : users.length === 0 ? (
            <div className="p-6">
              <EmptyState
                title="No portal users yet"
                description={
                  statusFilter === "all"
                    ? "Invite your first portal user to get started. Drivers invited into a Driver space are auto-linked to a Driver record."
                    : `No users match the ${statusFilter} filter.`
                }
                action={
                  statusFilter === "all" ? (
                    <Button
                      onClick={() => setInviteOpen(true)}
                      data-testid="empty-state-invite-btn"
                    >
                      <Plus className="mr-1.5 h-4 w-4" />
                      Invite user
                    </Button>
                  ) : null
                }
              />
            </div>
          ) : (
            <Table data-testid="portal-users-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Space</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last login</TableHead>
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((u) => (
                  <PortalUserRow
                    key={u.id}
                    user={u}
                    onRefresh={refresh}
                  />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <InviteDialog
        open={inviteOpen}
        onOpenChange={setInviteOpen}
        onInvited={() => {
          void refresh();
        }}
      />
    </div>
  );
}


// ── Per-row component ────────────────────────────────────────────

function PortalUserRow({
  user,
  onRefresh,
}: {
  user: PortalUserSummary;
  onRefresh: () => Promise<void> | void;
}) {
  const cfg = STATUS_MAP[user.status];

  async function handleDeactivate() {
    try {
      await deactivatePortalUser(user.id);
      toast.success(`${user.first_name} ${user.last_name} deactivated.`);
      await onRefresh();
    } catch (err) {
      toast.error("Couldn't deactivate.");
    }
  }

  async function handleReactivate() {
    try {
      await reactivatePortalUser(user.id);
      toast.success(`${user.first_name} ${user.last_name} reactivated.`);
      await onRefresh();
    } catch (err) {
      toast.error("Couldn't reactivate.");
    }
  }

  async function handleUnlock() {
    try {
      await unlockPortalUser(user.id);
      toast.success("Account unlocked.");
      await onRefresh();
    } catch (err) {
      toast.error("Couldn't unlock.");
    }
  }

  async function handleResetPassword() {
    try {
      await resetPortalUserPassword(user.id);
      toast.success("Reset-password email sent.");
    } catch (err) {
      toast.error("Couldn't send reset email.");
    }
  }

  async function handleResendInvite() {
    try {
      await resendInvite(user.id);
      toast.success("Invite email resent.");
      await onRefresh();
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "Couldn't resend invite.");
    }
  }

  return (
    <TableRow data-testid={`portal-user-row-${user.id}`}>
      <TableCell className="font-medium">
        {user.first_name} {user.last_name}
      </TableCell>
      <TableCell className="text-content-muted">{user.email}</TableCell>
      <TableCell>{user.assigned_space_name ?? "—"}</TableCell>
      <TableCell>
        <StatusPill status={cfg.variant === "neutral" ? "neutral" : cfg.variant}>
          {cfg.label}
        </StatusPill>
      </TableCell>
      <TableCell className="text-content-muted">
        {user.last_login_at
          ? new Date(user.last_login_at).toLocaleDateString()
          : "Never"}
      </TableCell>
      <TableCell>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                data-testid={`row-actions-${user.id}`}
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            }
          />
          <DropdownMenuContent align="end" className="w-52">
            {user.status === "pending" ? (
              <DropdownMenuItem onSelect={handleResendInvite}>
                <Mail className="mr-2 h-4 w-4" />
                Resend invite
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem onSelect={handleResetPassword}>
                <KeyRound className="mr-2 h-4 w-4" />
                Reset password
              </DropdownMenuItem>
            )}
            {user.status === "locked" && (
              <DropdownMenuItem onSelect={handleUnlock}>
                <LockKeyhole className="mr-2 h-4 w-4" />
                Unlock account
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            {user.status === "inactive" ? (
              <DropdownMenuItem onSelect={handleReactivate}>
                <CheckCircle2 className="mr-2 h-4 w-4" />
                Reactivate
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem
                onSelect={handleDeactivate}
                className="text-status-error"
              >
                <UserX className="mr-2 h-4 w-4" />
                Deactivate
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </TableCell>
    </TableRow>
  );
}


// ── Invite dialog ────────────────────────────────────────────────

function InviteDialog({
  open,
  onOpenChange,
  onInvited,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onInvited: () => void;
}) {
  const { spaces } = useSpaces();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [spaceId, setSpaceId] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filter to portal-shaped spaces only — office spaces can't host portal users.
  const portalSpaces = useMemo(
    () =>
      spaces.filter(
        (s) =>
          s.access_mode === "portal_partner" ||
          s.access_mode === "portal_external",
      ),
    [spaces],
  );

  useEffect(() => {
    if (!open) {
      setFirstName("");
      setLastName("");
      setEmail("");
      setSpaceId("");
      setError(null);
    } else if (portalSpaces.length === 1 && !spaceId) {
      // Auto-pick if only one portal space exists.
      setSpaceId(portalSpaces[0].space_id);
    }
  }, [open, portalSpaces, spaceId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!firstName || !lastName || !email || !spaceId) {
      setError("All fields are required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await invitePortalUser({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim().toLowerCase(),
        assigned_space_id: spaceId,
      });
      toast.success(`Invite sent to ${email}.`);
      onInvited();
      onOpenChange(false);
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      setError(e?.response?.data?.detail ?? "Invite failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invite a portal user</DialogTitle>
          <DialogDescription>
            They&rsquo;ll receive an email with a link to set their password.
            Drivers invited into a Driver space are automatically
            linked to a new Driver record.
          </DialogDescription>
        </DialogHeader>
        {portalSpaces.length === 0 ? (
          <Alert variant="warning">
            No portal-shaped spaces exist yet. Create one at{" "}
            <a href="/settings/spaces" className="underline">
              /settings/spaces
            </a>{" "}
            first (with access_mode="portal_partner" or
            "portal_external").
          </Alert>
        ) : (
          <form
            className="space-y-3"
            onSubmit={handleSubmit}
            data-testid="invite-portal-user-form"
          >
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="invite-first">First name</Label>
                <Input
                  id="invite-first"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  autoFocus
                  data-testid="invite-first-name"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="invite-last">Last name</Label>
                <Input
                  id="invite-last"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  data-testid="invite-last-name"
                />
              </div>
            </div>
            <div className="space-y-1">
              <Label htmlFor="invite-email">Email</Label>
              <Input
                id="invite-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                data-testid="invite-email"
              />
            </div>
            <div className="space-y-1">
              <Label>Assigned space</Label>
              <Select value={spaceId} onValueChange={(v) => setSpaceId(v ?? "")}>
                <SelectTrigger data-testid="invite-space">
                  <SelectValue placeholder="Pick a portal space…" />
                </SelectTrigger>
                <SelectContent>
                  {portalSpaces.map((s) => (
                    <SelectItem key={s.space_id} value={s.space_id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {error ? <Alert variant="error">{error}</Alert> : null}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={busy}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={busy}
                data-testid="invite-submit"
              >
                <Mail className="mr-1.5 h-4 w-4" />
                Send invite
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
