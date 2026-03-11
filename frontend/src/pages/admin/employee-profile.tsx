import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { employeeProfileService } from "@/services/employee-profile-service";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import type { User } from "@/types/auth";
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
  const [department, setDepartment] = useState("");
  const [hireDate, setHireDate] = useState("");
  const [addressStreet, setAddressStreet] = useState("");
  const [addressCity, setAddressCity] = useState("");
  const [addressState, setAddressState] = useState("");
  const [addressZip, setAddressZip] = useState("");
  const [emergencyName, setEmergencyName] = useState("");
  const [emergencyPhone, setEmergencyPhone] = useState("");
  const [notes, setNotes] = useState("");

  function populateForm(p: EmployeeProfile) {
    setPhone(p.phone || "");
    setPosition(p.position || "");
    setDepartment(p.department || "");
    setHireDate(p.hire_date || "");
    setAddressStreet(p.address_street || "");
    setAddressCity(p.address_city || "");
    setAddressState(p.address_state || "");
    setAddressZip(p.address_zip || "");
    setEmergencyName(p.emergency_contact_name || "");
    setEmergencyPhone(p.emergency_contact_phone || "");
    setNotes(p.notes || "");
  }

  const loadData = useCallback(async () => {
    if (!userId) return;
    try {
      setLoading(true);
      const [userRes, profile] = await Promise.all([
        apiClient.get<User>(`/users/${userId}`),
        employeeProfileService.getProfile(userId),
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
        department,
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
      const message =
        (err as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail || "Failed to save profile";
      setError(message);
    } finally {
      setSaving(false);
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
        <h2 className="text-lg font-semibold">Account Information</h2>
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
                <Label>Department</Label>
                <Input
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  disabled={!canEdit}
                  placeholder="e.g. Logistics"
                />
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
