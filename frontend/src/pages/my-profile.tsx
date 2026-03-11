import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/contexts/auth-context";
import { employeeProfileService } from "@/services/employee-profile-service";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import type { EmployeeProfile } from "@/types/employee-profile";

export default function MyProfile() {
  const { user, hasPermission } = useAuth();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [profile, setProfile] = useState<EmployeeProfile | null>(null);

  // Self-editable fields
  const [phone, setPhone] = useState("");
  const [addressStreet, setAddressStreet] = useState("");
  const [addressCity, setAddressCity] = useState("");
  const [addressState, setAddressState] = useState("");
  const [addressZip, setAddressZip] = useState("");
  const [emergencyName, setEmergencyName] = useState("");
  const [emergencyPhone, setEmergencyPhone] = useState("");

  const loadProfile = useCallback(async () => {
    try {
      setLoading(true);
      const p = await employeeProfileService.getMyProfile();
      setProfile(p);
      setPhone(p.phone || "");
      setAddressStreet(p.address_street || "");
      setAddressCity(p.address_city || "");
      setAddressState(p.address_state || "");
      setAddressZip(p.address_zip || "");
      setEmergencyName(p.emergency_contact_name || "");
      setEmergencyPhone(p.emergency_contact_phone || "");
    } catch {
      setError("Failed to load profile");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      const updated = await employeeProfileService.updateMyProfile({
        phone,
        address_street: addressStreet,
        address_city: addressCity,
        address_state: addressState,
        address_zip: addressZip,
        emergency_contact_name: emergencyName,
        emergency_contact_phone: emergencyPhone,
      });
      setProfile(updated);
      toast.success("Profile saved");
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
        <h1 className="text-2xl font-bold">My Profile</h1>
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold">My Profile</h1>

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
              value={`${user?.first_name || ""} ${user?.last_name || ""}`}
              disabled
            />
          </div>
          <div className="space-y-2">
            <Label>Email</Label>
            <Input value={user?.email || ""} disabled />
          </div>
        </div>
        {/* Admin-managed fields shown read-only */}
        {(profile?.position || profile?.department || profile?.hire_date) && (
          <div className="mt-4 grid grid-cols-3 gap-4">
            {profile?.position && (
              <div className="space-y-2">
                <Label>Position</Label>
                <Input value={profile.position} disabled />
              </div>
            )}
            {profile?.department && (
              <div className="space-y-2">
                <Label>Department</Label>
                <Input value={profile.department} disabled />
              </div>
            )}
            {profile?.hire_date && (
              <div className="space-y-2">
                <Label>Hire Date</Label>
                <Input value={profile.hire_date} disabled />
              </div>
            )}
          </div>
        )}
      </Card>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Contact */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold">Contact Information</h2>
          <Separator className="my-4" />
          <div className="space-y-2">
            <Label>Phone</Label>
            <Input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="(555) 123-4567"
            />
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
                placeholder="123 Main St"
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>City</Label>
                <Input
                  value={addressCity}
                  onChange={(e) => setAddressCity(e.target.value)}
                  placeholder="City"
                />
              </div>
              <div className="space-y-2">
                <Label>State</Label>
                <Input
                  value={addressState}
                  onChange={(e) => setAddressState(e.target.value)}
                  placeholder="CA"
                />
              </div>
              <div className="space-y-2">
                <Label>ZIP Code</Label>
                <Input
                  value={addressZip}
                  onChange={(e) => setAddressZip(e.target.value)}
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
                placeholder="Jane Doe"
              />
            </div>
            <div className="space-y-2">
              <Label>Contact Phone</Label>
              <Input
                value={emergencyPhone}
                onChange={(e) => setEmergencyPhone(e.target.value)}
                placeholder="(555) 987-6543"
              />
            </div>
          </div>
        </Card>

        {/* Notes — visible only if user has view_notes permission */}
        {hasPermission("employees.view_notes") && profile?.notes && (
          <Card className="p-6">
            <h2 className="text-lg font-semibold">Notes</h2>
            <Separator className="my-4" />
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">
              {profile.notes}
            </p>
          </Card>
        )}

        <div className="flex justify-end">
          <Button type="submit" disabled={saving}>
            {saving ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </form>
    </div>
  );
}
