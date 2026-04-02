import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { X } from "lucide-react";
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
                    <Badge
                      variant={user.is_active ? "default" : "destructive"}
                    >
                      {user.is_active ? "Active" : "Inactive"}
                    </Badge>
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
