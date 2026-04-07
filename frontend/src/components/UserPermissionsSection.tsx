import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, Minus, RotateCcw, Plus, Shield } from "lucide-react";
import { permissionService } from "@/services/permission-service";
import type {
  CustomPermission,
  PermissionAuditEntry,
  UserPermissionDetails,
} from "@/services/permission-service";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface Props {
  userId: string;
  canEdit: boolean;
}

// Permissions to show as toggles in the UI, grouped by section
const TOGGLE_SECTIONS: Array<{
  title: string;
  subtitle?: string;
  permissions: Array<{
    slug: string;
    label: string;
    description?: string;
  }>;
}> = [
  {
    title: "Financials",
    permissions: [
      { slug: "financials.view", label: "Can view financials" },
      { slug: "financials.ar.view", label: "Can view AR" },
      { slug: "financials.ar.action", label: "Can take action on AR" },
      { slug: "financials.invoices.view", label: "Can view invoices" },
      { slug: "financials.invoices.create", label: "Can create invoices" },
      {
        slug: "invoice.approve",
        label: "Invoice approval",
        description: "Gets draft invoices in morning summary to approve",
      },
      { slug: "financials.ap.view", label: "Can view AP" },
      { slug: "financials.ap.action", label: "Can take action on AP" },
      { slug: "financials.statements.view", label: "Can view statements" },
      { slug: "financials.statements.create", label: "Can create statements" },
      { slug: "financials.price_management.view", label: "Can view price management" },
      { slug: "financials.price_management.edit", label: "Can edit price management" },
      { slug: "reports.view", label: "Can view reports" },
    ],
  },
  {
    title: "Operations",
    permissions: [
      { slug: "operations.view", label: "Can view operations" },
      { slug: "operations_board.view", label: "Can view Operations Board" },
      { slug: "operations_board.edit", label: "Can edit Operations Board" },
      { slug: "order_station.view", label: "Can view Order Station" },
      { slug: "scheduling_board.view", label: "Can view Scheduling Board" },
      { slug: "orders.view", label: "Can view orders" },
      { slug: "orders.create", label: "Can create orders" },
      { slug: "orders.edit", label: "Can edit orders" },
      { slug: "orders.edit_status", label: "Can update order status" },
    ],
  },
  {
    title: "CRM",
    permissions: [
      { slug: "crm.view", label: "Can view CRM" },
      { slug: "crm.companies.create", label: "Can create companies" },
      { slug: "crm.companies.edit", label: "Can edit companies" },
      { slug: "crm.contacts.create", label: "Can create contacts" },
      { slug: "crm.contacts.edit", label: "Can edit contacts" },
      { slug: "crm.call_log.view", label: "Can view call log" },
    ],
  },
  {
    title: "Legacy Studio",
    permissions: [
      { slug: "legacy.view", label: "Can view legacy proofs" },
      {
        slug: "legacy.create",
        label: "Can create legacy proofs",
      },
      {
        slug: "legacy.review",
        label: "Can review/approve proofs",
        description: "Only 2-3 people should have this",
      },
    ],
  },
  {
    title: "Production",
    permissions: [
      { slug: "production_hub.view", label: "Can view Production Hub" },
      { slug: "production_hub.edit", label: "Can edit Production Hub" },
    ],
  },
  {
    title: "Knowledge & Training",
    permissions: [
      { slug: "knowledge_base.view", label: "Can view Knowledge Base" },
      { slug: "knowledge_base.edit", label: "Can edit Knowledge Base" },
      { slug: "training.view", label: "Can view training" },
      { slug: "training.edit", label: "Can edit training" },
      { slug: "training.admin", label: "Administer training" },
    ],
  },
  {
    title: "Settings",
    permissions: [
      { slug: "settings.view", label: "Can view settings" },
      { slug: "settings.users.manage", label: "Can manage users" },
      { slug: "settings.permissions.manage", label: "Can manage permissions" },
      { slug: "settings.integrations.manage", label: "Can manage integrations" },
    ],
  },
];

export default function UserPermissionsSection({ userId, canEdit }: Props) {
  const [loading, setLoading] = useState(true);
  const [userPerms, setUserPerms] = useState<UserPermissionDetails | null>(null);
  const [customPerms, setCustomPerms] = useState<CustomPermission[]>([]);
  const [auditLog, setAuditLog] = useState<PermissionAuditEntry[]>([]);
  const [saving, setSaving] = useState<string | null>(null);

  // Custom permission creation
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newRouting, setNewRouting] = useState(true);
  const [newGating, setNewGating] = useState(false);
  const [creating, setCreating] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [perms, custom, audit] = await Promise.all([
        permissionService.getUserPermissions(userId),
        permissionService.getCustomPermissions(),
        permissionService.getAuditLog(userId),
      ]);
      setUserPerms(perms);
      setCustomPerms(custom);
      setAuditLog(audit);
    } catch {
      toast.error("Failed to load permissions");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading || !userPerms) {
    return <div className="py-4 text-center text-muted-foreground">Loading permissions...</div>;
  }

  if (userPerms.is_admin) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 rounded-md bg-blue-50 p-4 dark:bg-blue-950/30">
          <Shield className="size-5 text-blue-600 dark:text-blue-400" />
          <div>
            <p className="font-medium text-blue-900 dark:text-blue-200">
              Administrator
            </p>
            <p className="text-sm text-blue-700 dark:text-blue-300">
              This user has full access to everything. Individual permission
              toggles are not applicable for administrators.
            </p>
          </div>
        </div>
        <CustomPermissionsBlock
          userId={userId}
          customPerms={customPerms}
          effectivePerms={new Set(userPerms.effective_permissions)}
          canEdit={canEdit}
          onReload={loadData}
          showCreate={showCreate}
          setShowCreate={setShowCreate}
          newName={newName}
          setNewName={setNewName}
          newDesc={newDesc}
          setNewDesc={setNewDesc}
          newRouting={newRouting}
          setNewRouting={setNewRouting}
          newGating={newGating}
          setNewGating={setNewGating}
          creating={creating}
          setCreating={setCreating}
        />
      </div>
    );
  }

  const rolePerms = new Set(userPerms.role_permissions);
  const effectivePerms = new Set(userPerms.effective_permissions);
  const explicitGrantSlugs = new Set(
    userPerms.explicit_grants.map((g) => g.permission_key)
  );
  const explicitRevokeSlugs = new Set(
    userPerms.explicit_revokes.map((g) => g.permission_key)
  );

  async function handleToggle(slug: string) {
    setSaving(slug);
    try {
      if (effectivePerms.has(slug)) {
        if (rolePerms.has(slug)) {
          // It's from role default — need explicit revoke
          await permissionService.revokePermission(userId, slug);
        } else {
          // It's an explicit grant — reset to role default (which doesn't have it)
          await permissionService.resetPermission(userId, slug);
        }
      } else {
        // Not currently enabled — grant it
        await permissionService.grantPermission(userId, slug);
      }
      await loadData();
      toast.success("Permission updated");
    } catch {
      toast.error("Failed to update permission");
    } finally {
      setSaving(null);
    }
  }

  async function handleReset(slug: string) {
    setSaving(slug);
    try {
      await permissionService.resetPermission(userId, slug);
      await loadData();
      toast.success("Reset to role default");
    } catch {
      toast.error("Failed to reset permission");
    } finally {
      setSaving(null);
    }
  }

  function isOverridden(slug: string): boolean {
    return explicitGrantSlugs.has(slug) || explicitRevokeSlugs.has(slug);
  }

  function getOverrideInfo(slug: string) {
    const grant = userPerms!.explicit_grants.find(
      (g) => g.permission_key === slug
    );
    if (grant) return grant;
    return userPerms!.explicit_revokes.find((g) => g.permission_key === slug);
  }

  return (
    <div className="space-y-6">
      {/* Role info */}
      <div className="rounded-md border p-4">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-muted-foreground">
            Current Role:
          </span>
          <Badge variant="secondary" className="text-sm">
            {userPerms.role_name}
          </Badge>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {userPerms.role_permissions.length} default permissions from this role
        </p>
      </div>

      {/* Permission toggles */}
      <div>
        <h3 className="text-base font-semibold">Custom Access</h3>
        <p className="text-sm text-muted-foreground">
          Override role defaults for this employee
        </p>
      </div>

      {TOGGLE_SECTIONS.map((section) => (
        <div key={section.title} className="space-y-2">
          <h4 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            {section.title}
          </h4>
          <div className="divide-y rounded-md border">
            {section.permissions.map((perm) => {
              const enabled = effectivePerms.has(perm.slug);
              const overridden = isOverridden(perm.slug);
              const fromRole = rolePerms.has(perm.slug);
              const info = overridden ? getOverrideInfo(perm.slug) : null;

              return (
                <div
                  key={perm.slug}
                  className="flex items-center justify-between gap-4 px-4 py-3"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{perm.label}</span>
                      {fromRole && !overridden && (
                        <Badge
                          variant="outline"
                          className="text-xs text-muted-foreground"
                        >
                          Role default
                        </Badge>
                      )}
                      {overridden && (
                        <Badge
                          variant="outline"
                          className="text-xs border-amber-300 text-amber-700 dark:border-amber-700 dark:text-amber-400"
                        >
                          Overridden
                        </Badge>
                      )}
                    </div>
                    {perm.description && (
                      <p className="text-xs text-muted-foreground">
                        {perm.description}
                      </p>
                    )}
                    {info?.granted_at && (
                      <p className="text-xs text-muted-foreground">
                        {enabled ? "Granted" : "Revoked"}{" "}
                        {new Date(info.granted_at).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {overridden && canEdit && (
                      <button
                        onClick={() => handleReset(perm.slug)}
                        className="text-xs text-muted-foreground hover:text-foreground"
                        title="Reset to role default"
                      >
                        <RotateCcw className="size-3.5" />
                      </button>
                    )}
                    <button
                      onClick={() => canEdit && handleToggle(perm.slug)}
                      disabled={!canEdit || saving === perm.slug}
                      className={`flex size-8 items-center justify-center rounded-md border transition-colors ${
                        enabled
                          ? "border-green-500 bg-green-500 text-white"
                          : "border-gray-300 bg-white text-gray-400 dark:border-gray-600 dark:bg-gray-800"
                      } ${!canEdit ? "cursor-not-allowed opacity-50" : "cursor-pointer hover:opacity-80"}`}
                    >
                      {saving === perm.slug ? (
                        <span className="size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
                      ) : enabled ? (
                        <Check className="size-4" />
                      ) : (
                        <Minus className="size-4" />
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}

      <Separator />

      {/* Custom permissions */}
      <CustomPermissionsBlock
        userId={userId}
        customPerms={customPerms}
        effectivePerms={effectivePerms}
        canEdit={canEdit}
        onReload={loadData}
        showCreate={showCreate}
        setShowCreate={setShowCreate}
        newName={newName}
        setNewName={setNewName}
        newDesc={newDesc}
        setNewDesc={setNewDesc}
        newRouting={newRouting}
        setNewRouting={setNewRouting}
        newGating={newGating}
        setNewGating={setNewGating}
        creating={creating}
        setCreating={setCreating}
      />

      <Separator />

      {/* Audit log */}
      {auditLog.length > 0 && (
        <div>
          <h3 className="mb-3 text-base font-semibold">
            Permission Change History
          </h3>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Permission</TableHead>
                  <TableHead>Change</TableHead>
                  <TableHead>By</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {auditLog.slice(0, 20).map((entry, i) => (
                  <TableRow key={i}>
                    <TableCell className="text-sm">
                      {entry.granted_at
                        ? new Date(entry.granted_at).toLocaleDateString()
                        : "—"}
                    </TableCell>
                    <TableCell className="text-sm">
                      {entry.permission_name}
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={
                          entry.granted
                            ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                            : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                        }
                      >
                        {entry.change}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {entry.granted_by}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Custom permissions sub-component
// ---------------------------------------------------------------------------

function CustomPermissionsBlock({
  userId,
  customPerms,
  effectivePerms,
  canEdit,
  onReload,
  showCreate,
  setShowCreate,
  newName,
  setNewName,
  newDesc,
  setNewDesc,
  newRouting,
  setNewRouting,
  newGating,
  setNewGating,
  creating,
  setCreating,
}: {
  userId: string;
  customPerms: CustomPermission[];
  effectivePerms: Set<string>;
  canEdit: boolean;
  onReload: () => Promise<void>;
  showCreate: boolean;
  setShowCreate: (v: boolean) => void;
  newName: string;
  setNewName: (v: string) => void;
  newDesc: string;
  setNewDesc: (v: string) => void;
  newRouting: boolean;
  setNewRouting: (v: boolean) => void;
  newGating: boolean;
  setNewGating: (v: boolean) => void;
  creating: boolean;
  setCreating: (v: boolean) => void;
}) {
  async function handleToggleCustom(slug: string) {
    try {
      if (effectivePerms.has(slug)) {
        await permissionService.revokePermission(userId, slug);
      } else {
        await permissionService.grantPermission(userId, slug);
      }
      await onReload();
      toast.success("Permission updated");
    } catch {
      toast.error("Failed to update permission");
    }
  }

  async function handleCreate() {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await permissionService.createCustomPermission({
        name: newName,
        description: newDesc || undefined,
        notification_routing: newRouting,
        access_gating: newGating,
      });
      setNewName("");
      setNewDesc("");
      setNewRouting(true);
      setNewGating(false);
      setShowCreate(false);
      await onReload();
      toast.success("Custom permission created");
    } catch {
      toast.error("Failed to create custom permission");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold">Specialty Permissions</h3>
          <p className="text-sm text-muted-foreground">
            Assign custom permissions created by your organization
          </p>
        </div>
        {canEdit && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowCreate(!showCreate)}
          >
            <Plus className="mr-1 size-3.5" />
            Create New
          </Button>
        )}
      </div>

      {showCreate && canEdit && (
        <div className="mt-4 space-y-3 rounded-md border p-4">
          <div className="space-y-2">
            <Label>Name</Label>
            <Input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder='e.g., "Approve Spring Burials"'
            />
          </div>
          <div className="space-y-2">
            <Label>Description</Label>
            <Input
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder="What does this permission control or route?"
            />
          </div>
          <div className="flex gap-6">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={newRouting}
                onChange={(e) => setNewRouting(e.target.checked)}
                className="rounded border-gray-300"
              />
              Route to morning summary
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={newGating}
                onChange={(e) => setNewGating(e.target.checked)}
                className="rounded border-gray-300"
              />
              Use as access gate
            </label>
          </div>
          <Button onClick={handleCreate} disabled={creating || !newName.trim()}>
            {creating ? "Creating..." : "Create Permission"}
          </Button>
        </div>
      )}

      {customPerms.length > 0 && (
        <div className="mt-4 divide-y rounded-md border">
          {customPerms.map((cp) => {
            const enabled = effectivePerms.has(cp.slug);
            return (
              <div
                key={cp.id}
                className="flex items-center justify-between gap-4 px-4 py-3"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">{cp.name}</p>
                  {cp.description && (
                    <p className="text-xs text-muted-foreground">
                      {cp.description}
                    </p>
                  )}
                  <div className="mt-1 flex gap-2">
                    {cp.notification_routing && (
                      <Badge variant="outline" className="text-xs">
                        Morning summary
                      </Badge>
                    )}
                    {cp.access_gating && (
                      <Badge variant="outline" className="text-xs">
                        Access gate
                      </Badge>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => canEdit && handleToggleCustom(cp.slug)}
                  disabled={!canEdit}
                  className={`flex size-8 items-center justify-center rounded-md border transition-colors ${
                    enabled
                      ? "border-green-500 bg-green-500 text-white"
                      : "border-gray-300 bg-white text-gray-400 dark:border-gray-600 dark:bg-gray-800"
                  } ${!canEdit ? "cursor-not-allowed opacity-50" : "cursor-pointer hover:opacity-80"}`}
                >
                  {enabled ? (
                    <Check className="size-4" />
                  ) : (
                    <Minus className="size-4" />
                  )}
                </button>
              </div>
            );
          })}
        </div>
      )}

      {customPerms.length === 0 && !showCreate && (
        <p className="mt-4 text-sm text-muted-foreground">
          No custom permissions created yet. Click "Create New" to add one.
        </p>
      )}
    </div>
  );
}
