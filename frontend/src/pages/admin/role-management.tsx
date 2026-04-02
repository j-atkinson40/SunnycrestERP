import { useCallback, useEffect, useState } from "react";
import { roleService } from "@/services/role-service";
import type { RoleResponse, PermissionRegistry } from "@/types/role";
import { useAuth } from "@/contexts/auth-context";
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
import { toast } from "sonner";
import { getApiErrorMessage } from "@/lib/api-error";

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function PermissionChecklist({
  registry,
  selected,
  onChange,
}: {
  registry: PermissionRegistry;
  selected: Set<string>;
  onChange: (keys: Set<string>) => void;
}) {
  function toggle(key: string) {
    const next = new Set(selected);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onChange(next);
  }

  function toggleModule(module: string, actions: string[]) {
    const keys = actions.map((a) => `${module}.${a}`);
    const allChecked = keys.every((k) => selected.has(k));
    const next = new Set(selected);
    if (allChecked) {
      keys.forEach((k) => next.delete(k));
    } else {
      keys.forEach((k) => next.add(k));
    }
    onChange(next);
  }

  return (
    <div className="space-y-4 max-h-64 overflow-y-auto pr-2">
      {Object.entries(registry).map(([module, actions]) => {
        const keys = actions.map((a) => `${module}.${a}`);
        const allChecked = keys.every((k) => selected.has(k));
        const someChecked =
          !allChecked && keys.some((k) => selected.has(k));

        return (
          <div key={module} className="space-y-2">
            <label className="flex items-center gap-2 font-medium text-sm capitalize cursor-pointer">
              <input
                type="checkbox"
                className="rounded accent-primary h-4 w-4"
                checked={allChecked}
                ref={(el) => {
                  if (el) el.indeterminate = someChecked;
                }}
                onChange={() => toggleModule(module, actions)}
              />
              {module}
            </label>
            <div className="ml-6 grid grid-cols-2 gap-1">
              {actions.map((action) => {
                const key = `${module}.${action}`;
                return (
                  <label
                    key={key}
                    className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer hover:text-foreground"
                  >
                    <input
                      type="checkbox"
                      className="rounded accent-primary h-3.5 w-3.5"
                      checked={selected.has(key)}
                      onChange={() => toggle(key)}
                    />
                    {action}
                  </label>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function RoleManagement() {
  const { hasPermission } = useAuth();
  const [roles, setRoles] = useState<RoleResponse[]>([]);
  const [registry, setRegistry] = useState<PermissionRegistry>({});
  const [loading, setLoading] = useState(true);

  // Create dialog state
  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createSlug, setCreateSlug] = useState("");
  const [createDesc, setCreateDesc] = useState("");
  const [createPerms, setCreatePerms] = useState<Set<string>>(new Set());
  const [createError, setCreateError] = useState("");
  const [slugManual, setSlugManual] = useState(false);

  // Edit dialog state
  const [editRole, setEditRole] = useState<RoleResponse | null>(null);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editPerms, setEditPerms] = useState<Set<string>>(new Set());
  const [editError, setEditError] = useState("");

  // Delete confirmation state
  const [deleteRole, setDeleteRole] = useState<RoleResponse | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [rolesData, registryData] = await Promise.all([
        roleService.getRoles(),
        roleService.getPermissionRegistry(),
      ]);
      setRoles(rolesData);
      setRegistry(registryData);
    } catch {
      toast.error("Failed to load roles");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // --- Create ---

  function resetCreateForm() {
    setCreateName("");
    setCreateSlug("");
    setCreateDesc("");
    setCreatePerms(new Set());
    setCreateError("");
    setSlugManual(false);
  }

  async function handleCreate() {
    setCreateError("");
    const slug = createSlug || slugify(createName);
    if (!createName.trim() || !slug) {
      setCreateError("Name is required");
      return;
    }
    try {
      await roleService.createRole({
        name: createName.trim(),
        slug,
        description: createDesc.trim() || undefined,
        permission_keys: Array.from(createPerms),
      });
      setCreateOpen(false);
      resetCreateForm();
      toast.success("Role created");
      loadData();
    } catch (err: unknown) {
      setCreateError(getApiErrorMessage(err, "Failed to create role"));
    }
  }

  // --- Edit ---

  function openEdit(role: RoleResponse) {
    setEditRole(role);
    setEditName(role.name);
    setEditDesc(role.description || "");
    setEditPerms(new Set(role.permission_keys));
    setEditError("");
  }

  async function handleEdit() {
    if (!editRole) return;
    setEditError("");
    try {
      // Update role metadata
      await roleService.updateRole(editRole.id, {
        name: editName.trim(),
        description: editDesc.trim() || undefined,
      });
      // Update permissions (only if not system admin)
      if (!(editRole.is_system && editRole.slug === "admin")) {
        await roleService.setRolePermissions(
          editRole.id,
          Array.from(editPerms)
        );
      }
      setEditRole(null);
      toast.success("Role updated");
      loadData();
    } catch (err: unknown) {
      setEditError(getApiErrorMessage(err, "Failed to update role"));
    }
  }

  // --- Delete ---

  async function handleDelete() {
    if (!deleteRole) return;
    try {
      await roleService.deleteRole(deleteRole.id);
      setDeleteRole(null);
      toast.success("Role deleted");
      loadData();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to delete role"));
      setDeleteRole(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Role Management</h1>
          <p className="text-muted-foreground">
            {roles.length} role{roles.length !== 1 ? "s" : ""}
          </p>
        </div>
        {hasPermission("roles.create") && (
          <Dialog
            open={createOpen}
            onOpenChange={(open) => {
              setCreateOpen(open);
              if (!open) resetCreateForm();
            }}
          >
            <DialogTrigger render={<Button />}>Create Role</DialogTrigger>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>Create New Role</DialogTitle>
                <DialogDescription>
                  Define a custom role with specific permissions.
                </DialogDescription>
              </DialogHeader>
              {createError && (
                <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                  {createError}
                </div>
              )}
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input
                    placeholder="e.g. Sales Manager"
                    value={createName}
                    onChange={(e) => {
                      setCreateName(e.target.value);
                      if (!slugManual) {
                        setCreateSlug(slugify(e.target.value));
                      }
                    }}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Slug</Label>
                  <Input
                    placeholder="e.g. sales-manager"
                    value={createSlug}
                    onChange={(e) => {
                      setSlugManual(true);
                      setCreateSlug(e.target.value);
                    }}
                  />
                  <p className="text-xs text-muted-foreground">
                    URL-friendly identifier. Auto-generated from name.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label>Description</Label>
                  <Input
                    placeholder="Optional description"
                    value={createDesc}
                    onChange={(e) => setCreateDesc(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Permissions</Label>
                  <PermissionChecklist
                    registry={registry}
                    selected={createPerms}
                    onChange={setCreatePerms}
                  />
                </div>
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => {
                    setCreateOpen(false);
                    resetCreateForm();
                  }}
                >
                  Cancel
                </Button>
                <Button onClick={handleCreate}>Create Role</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {/* System roles overview */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {roles.filter((r) => r.is_system).map((role) => {
          const icons: Record<string, string> = {
            admin: "👑", manager: "🛡️", office_staff: "💼", accounting: "📊",
            legacy_designer: "🎨", driver: "🚛", production: "🏭", employee: "👤",
          }
          const userCount: number = 0 // TODO: add user_count to role API response
          return (
            <div key={role.id} className="rounded-lg border bg-white p-3 space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-lg">{icons[role.slug] || "⚙"}</span>
                <span className="font-semibold text-sm">{role.name}</span>
              </div>
              <p className="text-xs text-muted-foreground">{role.description}</p>
              <p className="text-[11px] text-muted-foreground/60">
                {role.slug === "admin" ? "All permissions" : `${role.permission_keys?.length || 0} permissions`}
                {userCount > 0 ? ` · ${userCount} employee${userCount !== 1 ? "s" : ""}` : ""}
              </p>
            </div>
          )
        })}
      </div>

      <p className="text-xs text-muted-foreground">
        System roles cannot be modified. Use per-user exceptions for specific adjustments, or create a custom role below.
      </p>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Role</TableHead>
              <TableHead>Slug</TableHead>
              <TableHead>Permissions</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Status</TableHead>
              {hasPermission("roles.edit") && (
                <TableHead className="text-right">Actions</TableHead>
              )}
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : roles.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center">
                  No roles found
                </TableCell>
              </TableRow>
            ) : (
              roles.map((role) => (
                <TableRow key={role.id}>
                  <TableCell className="font-medium">
                    <div>
                      {role.name}
                      {role.description && (
                        <p className="text-xs text-muted-foreground">
                          {role.description}
                        </p>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                      {role.slug}
                    </code>
                  </TableCell>
                  <TableCell>
                    {role.is_system && role.slug === "admin" ? (
                      <Badge variant="default">All</Badge>
                    ) : (
                      <span className="text-sm">
                        {role.permission_keys.length} permission
                        {role.permission_keys.length !== 1 ? "s" : ""}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    {role.is_system ? (
                      <Badge variant="secondary">System</Badge>
                    ) : (
                      <Badge variant="outline">Custom</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={role.is_active ? "default" : "destructive"}
                    >
                      {role.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  {hasPermission("roles.edit") && (
                    <TableCell className="text-right space-x-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openEdit(role)}
                      >
                        Edit
                      </Button>
                      {hasPermission("roles.delete") &&
                        !role.is_system && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:text-destructive"
                            onClick={() => setDeleteRole(role)}
                          >
                            Delete
                          </Button>
                        )}
                    </TableCell>
                  )}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Edit Role Dialog */}
      <Dialog
        open={!!editRole}
        onOpenChange={(open) => {
          if (!open) setEditRole(null);
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Role: {editRole?.name}</DialogTitle>
            <DialogDescription>
              Update role details and permissions.
            </DialogDescription>
          </DialogHeader>
          {editError && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {editError}
            </div>
          )}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                disabled={editRole?.is_system}
              />
              {editRole?.is_system && (
                <p className="text-xs text-muted-foreground">
                  System role names cannot be changed.
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Input
                value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
              />
            </div>
            {editRole && !(editRole.is_system && editRole.slug === "admin") && (
              <div className="space-y-2">
                <Label>Permissions</Label>
                <PermissionChecklist
                  registry={registry}
                  selected={editPerms}
                  onChange={setEditPerms}
                />
              </div>
            )}
            {editRole?.is_system && editRole.slug === "admin" && (
              <p className="text-sm text-muted-foreground">
                The Admin role has all permissions by default and cannot be
                modified.
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditRole(null)}>
              Cancel
            </Button>
            <Button onClick={handleEdit}>Save Changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={!!deleteRole}
        onOpenChange={(open) => {
          if (!open) setDeleteRole(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Role</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete the role &ldquo;
              {deleteRole?.name}&rdquo;? This action cannot be undone. Roles
              with assigned users cannot be deleted.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteRole(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
