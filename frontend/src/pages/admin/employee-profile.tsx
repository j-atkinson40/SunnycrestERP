import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PlusIcon, SettingsIcon, Trash2Icon } from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { departmentService } from "@/services/department-service";
import { employeeProfileService } from "@/services/employee-profile-service";
import { userService } from "@/services/user-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
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
import type { User } from "@/types/auth";
import type { Department } from "@/types/department";
import type { EmployeeProfile } from "@/types/employee-profile";
import apiClient from "@/lib/api-client";

export default function AdminEmployeeProfile() {
  const { userId } = useParams<{ userId: string }>();
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("employees.edit");
  const canViewNotes = hasPermission("employees.view_notes");

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [targetUser, setTargetUser] = useState<User | null>(null);

  // Profile fields
  const [phone, setPhone] = useState("");
  const [position, setPosition] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [hireDate, setHireDate] = useState("");
  const [addressStreet, setAddressStreet] = useState("");
  const [addressCity, setAddressCity] = useState("");
  const [addressState, setAddressState] = useState("");
  const [addressZip, setAddressZip] = useState("");
  const [emergencyName, setEmergencyName] = useState("");
  const [emergencyPhone, setEmergencyPhone] = useState("");
  const [notes, setNotes] = useState("");

  // Departments list
  const [departments, setDepartments] = useState<Department[]>([]);

  // Reset password dialog
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [resetNewPassword, setResetNewPassword] = useState("");
  const [resetConfirmPassword, setResetConfirmPassword] = useState("");
  const [resettingPassword, setResettingPassword] = useState(false);
  const [resetPasswordError, setResetPasswordError] = useState("");

  // Manage departments dialog
  const [deptDialogOpen, setDeptDialogOpen] = useState(false);
  const [newDeptName, setNewDeptName] = useState("");
  const [newDeptDesc, setNewDeptDesc] = useState("");
  const [creatingDept, setCreatingDept] = useState(false);

  function populateForm(p: EmployeeProfile) {
    setPhone(p.phone || "");
    setPosition(p.position || "");
    setDepartmentId(p.department_id || "");
    setHireDate(p.hire_date || "");
    setAddressStreet(p.address_street || "");
    setAddressCity(p.address_city || "");
    setAddressState(p.address_state || "");
    setAddressZip(p.address_zip || "");
    setEmergencyName(p.emergency_contact_name || "");
    setEmergencyPhone(p.emergency_contact_phone || "");
    setNotes(p.notes || "");
  }

  async function loadDepartments() {
    try {
      const depts = await departmentService.getDepartments();
      setDepartments(depts);
    } catch {
      // Non-critical — dropdown will just be empty
    }
  }

  const loadData = useCallback(async () => {
    if (!userId) return;
    try {
      setLoading(true);
      const [userRes, profile] = await Promise.all([
        apiClient.get<User>(`/users/${userId}`),
        employeeProfileService.getProfile(userId),
        loadDepartments(),
      ]);
      setTargetUser(userRes.data);
      populateForm(profile);
    } catch {
      setError("Failed to load employee profile");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!userId) return;
    setError("");
    setSaving(true);
    try {
      const updated = await employeeProfileService.updateProfile(userId, {
        phone,
        position,
        department_id: departmentId || null,
        hire_date: hireDate || undefined,
        address_street: addressStreet,
        address_city: addressCity,
        address_state: addressState,
        address_zip: addressZip,
        emergency_contact_name: emergencyName,
        emergency_contact_phone: emergencyPhone,
        notes,
      });
      populateForm(updated);
      toast.success("Employee profile saved");
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Failed to save profile"));
    } finally {
      setSaving(false);
    }
  }

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault();
    if (!userId) return;
    setResetPasswordError("");

    if (resetNewPassword.length < 8) {
      setResetPasswordError("Password must be at least 8 characters");
      return;
    }
    if (resetNewPassword !== resetConfirmPassword) {
      setResetPasswordError("Passwords do not match");
      return;
    }

    setResettingPassword(true);
    try {
      await userService.resetPassword(userId, resetNewPassword);
      toast.success("Password reset successfully");
      setResetDialogOpen(false);
      setResetNewPassword("");
      setResetConfirmPassword("");
    } catch (err: unknown) {
      setResetPasswordError(getApiErrorMessage(err, "Failed to reset password"));
    } finally {
      setResettingPassword(false);
    }
  }

  async function handleCreateDepartment(e: React.FormEvent) {
    e.preventDefault();
    if (!newDeptName.trim()) return;
    setCreatingDept(true);
    try {
      await departmentService.createDepartment({
        name: newDeptName.trim(),
        description: newDeptDesc.trim() || undefined,
      });
      toast.success("Department created");
      setNewDeptName("");
      setNewDeptDesc("");
      await loadDepartments();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to create department"));
    } finally {
      setCreatingDept(false);
    }
  }

  async function handleDeleteDepartment(id: string) {
    try {
      await departmentService.deleteDepartment(id);
      toast.success("Department deactivated");
      await loadDepartments();
      // If current profile uses this department, clear it
      if (departmentId === id) {
        setDepartmentId("");
      }
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err, "Failed to delete department"));
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl space-y-6">
        <h1 className="text-2xl font-bold">Employee Profile</h1>
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">
          Employee Profile —{" "}
          {targetUser
            ? `${targetUser.first_name} ${targetUser.last_name}`
            : "Unknown"}
        </h1>
        <Link
          to="/admin/users"
          className="text-sm text-muted-foreground hover:underline"
        >
          ← Back to Users
        </Link>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* User info — read-only */}
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Account Information</h2>
          {canEdit && (
            <Dialog
              open={resetDialogOpen}
              onOpenChange={(open) => {
                setResetDialogOpen(open);
                if (!open) {
                  setResetNewPassword("");
                  setResetConfirmPassword("");
                  setResetPasswordError("");
                }
              }}
            >
              <DialogTrigger
                render={<Button variant="outline" size="sm" />}
              >
                Reset Password
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Reset Password</DialogTitle>
                  <DialogDescription>
                    Set a new password for{" "}
                    {targetUser
                      ? `${targetUser.first_name} ${targetUser.last_name}`
                      : "this user"}
                    . They will be notified that their password was reset.
                  </DialogDescription>
                </DialogHeader>
                <form onSubmit={handleResetPassword}>
                  {resetPasswordError && (
                    <div className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                      {resetPasswordError}
                    </div>
                  )}
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label>New Password</Label>
                      <Input
                        type="password"
                        value={resetNewPassword}
                        onChange={(e) => setResetNewPassword(e.target.value)}
                        placeholder="Min. 8 characters"
                        required
                        minLength={8}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Confirm Password</Label>
                      <Input
                        type="password"
                        value={resetConfirmPassword}
                        onChange={(e) =>
                          setResetConfirmPassword(e.target.value)
                        }
                        placeholder="Re-enter password"
                        required
                        minLength={8}
                      />
                    </div>
                  </div>
                  <DialogFooter className="mt-4">
                    <Button type="submit" disabled={resettingPassword}>
                      {resettingPassword ? "Resetting..." : "Reset Password"}
                    </Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          )}
        </div>
        <Separator className="my-4" />
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Name</Label>
            <Input
              value={
                targetUser
                  ? `${targetUser.first_name} ${targetUser.last_name}`
                  : ""
              }
              disabled
            />
          </div>
          <div className="space-y-2">
            <Label>Email</Label>
            <Input value={targetUser?.email || ""} disabled />
          </div>
        </div>
      </Card>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Professional Info */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold">Professional Information</h2>
          <Separator className="my-4" />
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Position / Title</Label>
                <Input
                  value={position}
                  onChange={(e) => setPosition(e.target.value)}
                  disabled={!canEdit}
                  placeholder="e.g. Delivery Driver"
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Department</Label>
                  {canEdit && (
                    <Dialog
                      open={deptDialogOpen}
                      onOpenChange={setDeptDialogOpen}
                    >
                      <DialogTrigger
                        render={
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            className="h-5 w-5"
                          />
                        }
                      >
                        <SettingsIcon className="size-3.5" />
                      </DialogTrigger>
                      <DialogContent className="sm:max-w-md">
                        <DialogHeader>
                          <DialogTitle>Manage Departments</DialogTitle>
                          <DialogDescription>
                            Create and manage departments for your organization.
                          </DialogDescription>
                        </DialogHeader>

                        {/* New department form */}
                        <form
                          onSubmit={handleCreateDepartment}
                          className="space-y-3"
                        >
                          <div className="flex gap-2">
                            <Input
                              value={newDeptName}
                              onChange={(e) => setNewDeptName(e.target.value)}
                              placeholder="Department name"
                              className="flex-1"
                              required
                            />
                            <Button
                              type="submit"
                              size="icon"
                              disabled={creatingDept || !newDeptName.trim()}
                            >
                              <PlusIcon className="size-4" />
                            </Button>
                          </div>
                          <Input
                            value={newDeptDesc}
                            onChange={(e) => setNewDeptDesc(e.target.value)}
                            placeholder="Description (optional)"
                          />
                        </form>

                        <Separator />

                        {/* Existing departments list */}
                        <div className="max-h-60 space-y-2 overflow-y-auto">
                          {departments.length === 0 ? (
                            <p className="text-sm text-muted-foreground">
                              No departments yet.
                            </p>
                          ) : (
                            departments.map((dept) => (
                              <div
                                key={dept.id}
                                className="flex items-center justify-between rounded-md border p-2 text-sm"
                              >
                                <div>
                                  <span className="font-medium">
                                    {dept.name}
                                  </span>
                                  {dept.description && (
                                    <p className="text-xs text-muted-foreground">
                                      {dept.description}
                                    </p>
                                  )}
                                </div>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="icon-sm"
                                  onClick={() => handleDeleteDepartment(dept.id)}
                                >
                                  <Trash2Icon className="size-3.5 text-destructive" />
                                </Button>
                              </div>
                            ))
                          )}
                        </div>

                        <DialogFooter showCloseButton />
                      </DialogContent>
                    </Dialog>
                  )}
                </div>
                <select
                  value={departmentId}
                  onChange={(e) => setDepartmentId(e.target.value)}
                  disabled={!canEdit}
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-[color,box-shadow] focus-visible:border-ring focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <option value="">No department</option>
                  {departments.map((dept) => (
                    <option key={dept.id} value={dept.id}>
                      {dept.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Phone</Label>
                <Input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  disabled={!canEdit}
                  placeholder="(555) 123-4567"
                />
              </div>
              <div className="space-y-2">
                <Label>Hire Date</Label>
                <Input
                  type="date"
                  value={hireDate}
                  onChange={(e) => setHireDate(e.target.value)}
                  disabled={!canEdit}
                />
              </div>
            </div>
          </div>
        </Card>

        {/* Address */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold">Address</h2>
          <Separator className="my-4" />
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Street Address</Label>
              <Input
                value={addressStreet}
                onChange={(e) => setAddressStreet(e.target.value)}
                disabled={!canEdit}
                placeholder="123 Main St"
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>City</Label>
                <Input
                  value={addressCity}
                  onChange={(e) => setAddressCity(e.target.value)}
                  disabled={!canEdit}
                  placeholder="City"
                />
              </div>
              <div className="space-y-2">
                <Label>State</Label>
                <Input
                  value={addressState}
                  onChange={(e) => setAddressState(e.target.value)}
                  disabled={!canEdit}
                  placeholder="CA"
                />
              </div>
              <div className="space-y-2">
                <Label>ZIP Code</Label>
                <Input
                  value={addressZip}
                  onChange={(e) => setAddressZip(e.target.value)}
                  disabled={!canEdit}
                  placeholder="90210"
                />
              </div>
            </div>
          </div>
        </Card>

        {/* Emergency Contact */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold">Emergency Contact</h2>
          <Separator className="my-4" />
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Contact Name</Label>
              <Input
                value={emergencyName}
                onChange={(e) => setEmergencyName(e.target.value)}
                disabled={!canEdit}
                placeholder="Jane Doe"
              />
            </div>
            <div className="space-y-2">
              <Label>Contact Phone</Label>
              <Input
                value={emergencyPhone}
                onChange={(e) => setEmergencyPhone(e.target.value)}
                disabled={!canEdit}
                placeholder="(555) 987-6543"
              />
            </div>
          </div>
        </Card>

        {/* Notes — admin only */}
        {canViewNotes && (
          <Card className="p-6">
            <h2 className="text-lg font-semibold">Admin Notes</h2>
            <Separator className="my-4" />
            <div className="space-y-2">
              <Label>Notes</Label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                disabled={!canEdit}
                rows={4}
                className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs transition-[color,box-shadow] focus-visible:border-ring focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
                placeholder="Internal notes about this employee..."
              />
            </div>
          </Card>
        )}

        {canEdit && (
          <div className="flex justify-end">
            <Button type="submit" disabled={saving}>
              {saving ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        )}
      </form>
    </div>
  );
}
