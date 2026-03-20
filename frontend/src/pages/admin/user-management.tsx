import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { X } from "lucide-react";
import { userService } from "@/services/user-service";
import { roleService } from "@/services/role-service";
import { functionalAreaService } from "@/services/functional-area-service";
import { dismissHelp, getDismissedHelp } from "@/services/onboarding-service";
import { getApiErrorMessage } from "@/lib/api-error";
import type { User } from "@/types/auth";
import type { UserCreate } from "@/types/user";
import type { RoleResponse } from "@/types/role";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  DialogFooter,
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
  const [newUser, setNewUser] = useState<UserCreate>({
    email: "",
    password: "",
    first_name: "",
    last_name: "",
    role_id: "",
  });
  const [createError, setCreateError] = useState("");

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
      // Set default role_id to the employee system role
      const employeeRole = data.find(
        (r) => r.is_system && r.slug === "employee"
      );
      if (employeeRole) {
        setNewUser((prev) =>
          prev.role_id ? prev : { ...prev, role_id: employeeRole.id }
        );
      }
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

  async function handleCreate() {
    setCreateError("");
    try {
      await userService.createUser(newUser);
      setDialogOpen(false);
      const employeeRole = roles.find(
        (r) => r.is_system && r.slug === "employee"
      );
      setNewUser({
        email: "",
        password: "",
        first_name: "",
        last_name: "",
        role_id: employeeRole?.id || "",
      });
      loadUsers();
    } catch (err: unknown) {
      setCreateError(getApiErrorMessage(err, "Failed to create user"));
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
            Add User
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New User</DialogTitle>
              <DialogDescription>
                Add a new user to the system.
              </DialogDescription>
            </DialogHeader>
            {createError && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {createError}
              </div>
            )}
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>First Name</Label>
                  <Input
                    value={newUser.first_name}
                    onChange={(e) =>
                      setNewUser({ ...newUser, first_name: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Last Name</Label>
                  <Input
                    value={newUser.last_name}
                    onChange={(e) =>
                      setNewUser({ ...newUser, last_name: e.target.value })
                    }
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Email</Label>
                <Input
                  type="email"
                  value={newUser.email}
                  onChange={(e) =>
                    setNewUser({ ...newUser, email: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Password</Label>
                <Input
                  type="password"
                  value={newUser.password}
                  onChange={(e) =>
                    setNewUser({ ...newUser, password: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Role</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
                  value={newUser.role_id}
                  onChange={(e) =>
                    setNewUser({ ...newUser, role_id: e.target.value })
                  }
                >
                  {roles.length === 0 ? (
                    <option value="">Loading roles...</option>
                  ) : (
                    roles
                      .filter((r) => r.is_active)
                      .map((role) => (
                        <option key={role.id} value={role.id}>
                          {role.name}
                        </option>
                      ))
                  )}
                </select>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreate}>Create User</Button>
            </DialogFooter>
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
                    {user.first_name} {user.last_name}
                  </TableCell>
                  <TableCell>{user.email}</TableCell>
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
