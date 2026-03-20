import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { X } from "lucide-react";
import { userService } from "@/services/user-service";
import { roleService } from "@/services/role-service";
import { employeeProfileService } from "@/services/employee-profile-service";
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
import FunctionalAreaMatrix from "@/components/functional-area-matrix";
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
    first_name: "",
    last_name: "",
    email: "",
    password: "",
    role_id: "",
  });
  const [createTrack, setCreateTrack] = useState<"office_management" | "production_delivery">("office_management");
  const [createUsername, setCreateUsername] = useState("");
  const [createPin, setCreatePin] = useState("");
  const [createConsoles, setCreateConsoles] = useState<string[]>([]);
  const [createError, setCreateError] = useState("");
  const [newUserAreas, setNewUserAreas] = useState<string[]>([]);

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
      const payload: UserCreate = {
        first_name: newUser.first_name,
        last_name: newUser.last_name,
        role_id: newUser.role_id,
      };
      if (createTrack === "production_delivery") {
        payload.track = "production_delivery";
        payload.username = createUsername;
        payload.pin = createPin;
        payload.console_access = createConsoles;
      } else {
        payload.email = newUser.email;
        payload.password = newUser.password;
      }

      const created = await userService.createUser(payload);

      // Save functional areas for office users
      if (createTrack === "office_management" && newUserAreas.length > 0) {
        try {
          await employeeProfileService.updateProfile(created.id, {
            functional_areas: newUserAreas,
          });
        } catch {
          // Non-critical
        }
      }

      // Save console access for production users
      if (createTrack === "production_delivery" && createConsoles.length > 0) {
        try {
          await userService.updateUser(created.id, { console_access: createConsoles });
        } catch {
          // Non-critical
        }
      }

      setDialogOpen(false);
      const employeeRole = roles.find(
        (r) => r.is_system && r.slug === "employee"
      );
      setNewUser({
        first_name: "",
        last_name: "",
        email: "",
        password: "",
        role_id: employeeRole?.id || "",
      });
      setCreateTrack("office_management");
      setCreateUsername("");
      setCreatePin("");
      setCreateConsoles([]);
      setNewUserAreas([]);
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
              {/* Track toggle */}
              <div className="space-y-2">
                <Label>Employee Type</Label>
                <div className="flex rounded-md border overflow-hidden text-sm w-fit">
                  <button
                    type="button"
                    className={`px-4 py-1.5 transition-colors ${
                      createTrack === "office_management"
                        ? "bg-primary text-primary-foreground"
                        : "hover:bg-muted"
                    }`}
                    onClick={() => setCreateTrack("office_management")}
                  >
                    Office / Management
                  </button>
                  <button
                    type="button"
                    className={`px-4 py-1.5 transition-colors ${
                      createTrack === "production_delivery"
                        ? "bg-blue-600 text-white"
                        : "hover:bg-muted"
                    }`}
                    onClick={() => setCreateTrack("production_delivery")}
                  >
                    Production / Delivery
                  </button>
                </div>
              </div>

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

              {createTrack === "office_management" ? (
                <>
                  <div className="space-y-2">
                    <Label>Email</Label>
                    <Input
                      type="email"
                      value={newUser.email ?? ""}
                      onChange={(e) =>
                        setNewUser({ ...newUser, email: e.target.value })
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Password</Label>
                    <Input
                      type="password"
                      value={newUser.password ?? ""}
                      onChange={(e) =>
                        setNewUser({ ...newUser, password: e.target.value })
                      }
                    />
                  </div>
                </>
              ) : (
                <>
                  <div className="space-y-2">
                    <Label>Username</Label>
                    <Input
                      value={createUsername}
                      onChange={(e) => setCreateUsername(e.target.value)}
                      placeholder="john.s"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>PIN (4 digits)</Label>
                    <Input
                      inputMode="numeric"
                      maxLength={4}
                      value={createPin}
                      onChange={(e) => {
                        const v = e.target.value.replace(/\D/g, "").slice(0, 4);
                        setCreatePin(v);
                      }}
                      placeholder="1234"
                      className="font-mono"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Console Access</Label>
                    <div className="space-y-1">
                      {[
                        { key: "delivery_console", label: "Delivery Console" },
                        { key: "production_console", label: "Production Console" },
                      ].map((opt) => (
                        <label key={opt.key} className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={createConsoles.includes(opt.key)}
                            onChange={() =>
                              setCreateConsoles((prev) =>
                                prev.includes(opt.key)
                                  ? prev.filter((k) => k !== opt.key)
                                  : [...prev, opt.key]
                              )
                            }
                            className="size-4 rounded"
                          />
                          {opt.label}
                        </label>
                      ))}
                    </div>
                  </div>
                </>
              )}

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

              {createTrack === "office_management" && (
                <div className="space-y-2">
                  <Label>Functional Areas</Label>
                  <p className="text-xs text-muted-foreground">
                    What parts of the business will this person work in?
                  </p>
                  <FunctionalAreaMatrix
                    selectedAreas={newUserAreas}
                    onChange={setNewUserAreas}
                  />
                </div>
              )}
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
