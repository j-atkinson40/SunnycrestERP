import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { X } from "lucide-react";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";
import { getApiErrorMessage } from "@/lib/api-error";
import { userService } from "@/services/user-service";
import { roleService } from "@/services/role-service";
import EmployeeCreationWizard from "@/components/admin/EmployeeCreationWizard";
import { functionalAreaService } from "@/services/functional-area-service";
import { dismissHelp, getDismissedHelp } from "@/services/onboarding-service";
import type { User } from "@/types/auth";
import type { RoleResponse } from "@/types/role";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

/**
 * Which status a row reports, and whether Resend/Cancel are offered.
 *
 * ⚠️ **EXPORTED SO BOTH BRANCHES CAN BE TESTED WITHOUT RENDERING THE PAGE** —
 * the convention `EmployeeCreationWizard` set with `wizardOutcome`. CLAUDE.md's
 * comment-code discipline is explicit that a conditional render needs a test
 * per branch: DotNav's empty-spaces early return survived 14 months because
 * only the populated path was ever exercised.
 *
 * ⚠️ `=== true`, NOT TRUTHINESS. `has_outstanding_invite` is absent on older
 * payloads and on the auth `/me` shape, and `undefined` means "not known"
 * rather than "no invite". A falsy check conflates the two, and conflating
 * them hides the Resend button from the only person who needs it.
 */
export function userRowState(user: {
  is_active: boolean
  has_outstanding_invite?: boolean
}): { status: "invited" | "active" | "inactive"; offersInviteActions: boolean } {
  if (user.has_outstanding_invite === true) {
    return { status: "invited", offersInviteActions: true }
  }
  return {
    // A pending invitee is `is_active = true` and would otherwise read as
    // "Active", which is the one thing she is not. The invite state wins the
    // cell because it is the more specific fact.
    status: user.is_active ? "active" : "inactive",
    offersInviteActions: false,
  }
}

/**
 * What a resend reports. ⚠️ **ONE OUTCOME, NEVER TWO** — the same discipline
 * the wizard needed after a failed invite fired both a success toast and an
 * error toast.
 *
 * A resend that minted a token nobody received is WORSE than not resending,
 * because the old link is dead too, so `email_sent: false` is an error rather
 * than a qualified success. ⚠️ `=== false`, not truthiness: an older server
 * that omits the field has not reported failure, and treating absence as
 * failure would cry wolf on every resend.
 */
export function resendOutcome(
  data: { email_sent?: boolean } | undefined,
  name: string,
  email: string,
): { level: "success" | "error"; message: string } {
  if (data?.email_sent === false) {
    return {
      level: "error",
      message:
        `The old link is now dead and the new email did NOT send. ` +
        `${name} has no way in. Check email settings, then resend.`,
    }
  }
  return { level: "success", message: `New invitation sent to ${email}.` }
}

/**
 * What a cancel reports. `cancelled: false` is NOT an error — the server
 * refuses to delete someone who has signed in, so that branch means the list
 * was stale and she is a colleague now. Saying so is more useful than a
 * generic failure, and it is the branch that proves Cancel cannot delete a
 * real user.
 */
export function cancelOutcome(
  data: { cancelled?: boolean } | undefined,
  name: string,
  email: string,
): { level: "success" | "info"; message: string } {
  if (data?.cancelled === true) {
    return { level: "success", message: `Invitation for ${email} cancelled.` }
  }
  return {
    level: "info",
    message:
      `${name} has already signed in, so there was no invitation to ` +
      `cancel. Their account is untouched.`,
  }
}

export default function UserManagement() {
  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [roles, setRoles] = useState<RoleResponse[]>([]);

  // New functional area banner
  const [newAreaBanner, setNewAreaBanner] = useState<string | null>(null);

  useEffect(() => {
    // Check if there are extension-gated areas the admin hasn't seen
    Promise.all([
      functionalAreaService.getAreas(),
      getDismissedHelp(),
    ]).then(([res, dismissed]) => {
      const extensionGated = res.areas.filter((a) => a.required_extension);
      if (extensionGated.length > 0) {
        const key = `new_area_${extensionGated[0].area_key}`;
        if (!dismissed.includes(key)) {
          setNewAreaBanner(
            `New functional area available: ${extensionGated[0].display_name}. ` +
            `Assign employees to this area on their profile page.`
          );
        }
      }
    }).catch(() => {});
  }, []);

  async function dismissAreaBanner() {
    setNewAreaBanner(null);
    try {
      // Find the extension-gated area to build the dismiss key
      const res = await functionalAreaService.getAreas();
      const extensionGated = res.areas.filter((a) => a.required_extension);
      if (extensionGated.length > 0) {
        await dismissHelp(`new_area_${extensionGated[0].area_key}`);
      }
    } catch {
      // Non-critical
    }
  }

  // Create user dialog state
  const [dialogOpen, setDialogOpen] = useState(false);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await userService.getUsers(page, 20, search || undefined);
      setUsers(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  const loadRoles = useCallback(async () => {
    try {
      const data = await roleService.getRoles();
      setRoles(data);
    } catch {
      // Roles may not be available if user lacks roles.view permission
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  useEffect(() => {
    loadRoles();
  }, [loadRoles]);

  function getRoleName(roleId: string): string {
    const role = roles.find((r) => r.id === roleId);
    return role?.name || "Unknown";
  }

  function getRoleSlug(roleId: string): string {
    const role = roles.find((r) => r.id === roleId);
    return role?.slug || "";
  }

  async function handleResetTwoStep(user: User) {
    // Deliberately a confirm, not a silent action: it removes someone's second
    // factor, and the person clicking is not the person affected.
    const ok = window.confirm(
      `Clear two-step sign-in for ${user.first_name} ${user.last_name}?\n\n` +
        `They'll be asked to set it up again at their next sign-in. ` +
        `Do this only if they've lost both their phone and their recovery codes.`
    );
    if (!ok) return;
    try {
      const res = await apiClient.post(`/users/${user.id}/two-step/reset`);
      toast.success(
        res.data?.had_enrolment
          ? `${user.first_name} will set up two-step again at next sign-in.`
          : `${user.first_name} had no two-step setup to clear.`
      );
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Couldn't reset two-step sign-in."));
    }
  }

  /** Payroll 2 follow-up — a fresh link, and the old one dies. */
  async function handleResendInvite(user: User) {
    // ⚠️ The confirm names the consequence rather than asking "are you sure".
    // An admin resending usually does so BECAUSE the first link went somewhere
    // it should not have, and the fact they need to know is that the old one
    // stops working — otherwise they will tell her to use whichever mail
    // arrived first.
    const ok = window.confirm(
      `Send ${user.first_name} a new invitation link?\n\n` +
        `The link in their earlier email will stop working immediately. ` +
        `The new one is good for 72 hours.`
    );
    if (!ok) return;
    try {
      const res = await apiClient.post(`/users/${user.id}/invite/resend`);
      // ⚠️ ONE OUTCOME, NEVER TWO — the same discipline as the wizard. The
      // server reports `email_sent` honestly, and a resend that minted a token
      // nobody received is WORSE than not resending, because the old link is
      // now dead too. Reporting success here would assert a link exists in an
      // inbox when none was delivered.
      const out = resendOutcome(res.data, user.first_name, user.email);
      if (out.level === "success") toast.success(out.message);
      else toast.error(out.message);
      loadUsers();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Couldn't resend the invitation."));
    }
  }

  /** Payroll 2 follow-up — remove someone who never arrived. */
  async function handleCancelInvite(user: User) {
    const ok = window.confirm(
      `Cancel the invitation for ${user.first_name} ${user.last_name}?\n\n` +
        `Their link stops working and the pending account is removed. ` +
        `You can invite them again later.`
    );
    if (!ok) return;
    try {
      const res = await apiClient.delete(`/users/${user.id}/invite`);
      const out = cancelOutcome(res.data, user.first_name, user.email);
      if (out.level === "success") toast.success(out.message);
      else toast.info(out.message);
      loadUsers();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Couldn't cancel the invitation."));
    }
  }

  async function handleToggleActive(user: User) {
    if (user.is_active) {
      await userService.deleteUser(user.id);
    } else {
      await userService.updateUser(user.id, { is_active: true });
    }
    loadUsers();
  }

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="space-y-6">
      {newAreaBanner && (
        <div className="flex items-center justify-between gap-3 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-200">
          <span>{newAreaBanner}</span>
          <button
            onClick={dismissAreaBanner}
            className="shrink-0 rounded p-0.5 hover:bg-amber-200/50 dark:hover:bg-amber-800/50"
          >
            <X className="size-4" />
          </button>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">User Management</h1>
          <p className="text-muted-foreground">{total} total users</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger render={<Button />}>
            Add Employee
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Add Employee</DialogTitle>
              <DialogDescription>
                Set up a new employee account with role and permissions.
              </DialogDescription>
            </DialogHeader>
            <EmployeeCreationWizard
              onClose={() => setDialogOpen(false)}
              onCreated={() => { setDialogOpen(false); loadUsers() }}
            />
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex items-center gap-2">
        <Input
          placeholder="Search users..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          className="max-w-sm"
        />
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Position</TableHead>
              <TableHead>Department</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : users.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center">
                  No users found
                </TableCell>
              </TableRow>
            ) : (
              users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      {user.first_name} {user.last_name}
                      {user.track === "production_delivery" && (
                        <Badge variant="outline" className="text-xs border-blue-300 text-blue-700 dark:border-blue-700 dark:text-blue-400">
                          Production
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    {user.track === "production_delivery"
                      ? <span className="text-muted-foreground">@{user.username}</span>
                      : user.email}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {(user as User & { position?: string }).position || "—"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {(user as User & { department?: string }).department || "—"}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        getRoleSlug(user.role_id) === "admin"
                          ? "default"
                          : "secondary"
                      }
                    >
                      {user.role_name || getRoleName(user.role_id)}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {/* ⚠️ A pending invitee is `is_active = true` and would
                        otherwise read as "Active", which is the one thing she
                        is not — she has never signed in. The invite state wins
                        the cell because it is the more specific fact. */}
                    {userRowState(user).status === "invited" ? (
                      <Badge variant="secondary">Invited — not signed in</Badge>
                    ) : (
                      <Badge
                        variant={
                          userRowState(user).status === "active"
                            ? "default"
                            : "destructive"
                        }
                      >
                        {userRowState(user).status === "active"
                          ? "Active"
                          : "Inactive"}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right space-x-1">
                    <Link to={`/admin/users/${user.id}/profile`}>
                      <Button variant="ghost" size="sm">
                        Profile
                      </Button>
                    </Link>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleToggleActive(user)}
                    >
                      {user.is_active ? "Deactivate" : "Activate"}
                    </Button>
                    {/* Payroll 2 — the recovery path when someone loses their
                        phone AND their recovery codes. Offered for every user
                        rather than only required ones: the server refuses a
                        self-clear and reports whether there was anything to
                        clear, so the button cannot be used to discover who is
                        enrolled. */}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleResetTwoStep(user)}
                    >
                      Reset two-step
                    </Button>
                    {/* Payroll 2 follow-up — Resend and Cancel exist only for
                        someone who has not signed in yet. `=== true`, NOT
                        truthiness: the field is absent on older payloads, and
                        `undefined` means "not known" rather than "no invite".
                        A falsy check would conflate them and hide these from
                        the one person who needs them. */}
                    {userRowState(user).offersInviteActions && (
                      <>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleResendInvite(user)}
                        >
                          Resend invite
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleCancelInvite(user)}
                        >
                          Cancel invite
                        </Button>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
