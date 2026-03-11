import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/contexts/auth-context";
import { companyService } from "@/services/company-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import type { Company } from "@/types/company";

const TIMEZONE_OPTIONS = [
  { value: "America/New_York", label: "Eastern (ET)" },
  { value: "America/Chicago", label: "Central (CT)" },
  { value: "America/Denver", label: "Mountain (MT)" },
  { value: "America/Los_Angeles", label: "Pacific (PT)" },
  { value: "America/Anchorage", label: "Alaska (AKT)" },
  { value: "Pacific/Honolulu", label: "Hawaii (HT)" },
];

export default function CompanySettings() {
  const { hasPermission, refreshCompany } = useAuth();
  const canEdit = hasPermission("company.edit");

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Form state
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [addressStreet, setAddressStreet] = useState("");
  const [addressCity, setAddressCity] = useState("");
  const [addressState, setAddressState] = useState("");
  const [addressZip, setAddressZip] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [timezone, setTimezone] = useState("America/Los_Angeles");
  const [logoUrl, setLogoUrl] = useState("");

  const loadSettings = useCallback(async () => {
    try {
      setLoading(true);
      const company = await companyService.getSettings();
      populateForm(company);
    } catch {
      setError("Failed to load company settings");
    } finally {
      setLoading(false);
    }
  }, []);

  function populateForm(company: Company) {
    setName(company.name || "");
    setSlug(company.slug || "");
    setAddressStreet(company.address_street || "");
    setAddressCity(company.address_city || "");
    setAddressState(company.address_state || "");
    setAddressZip(company.address_zip || "");
    setPhone(company.phone || "");
    setEmail(company.email || "");
    setTimezone(company.timezone || "America/Los_Angeles");
    setLogoUrl(company.logo_url || "");
  }

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      // Convert empty strings to undefined so the backend receives null
      // (avoids pydantic EmailStr validation failing on "")
      const emptyToUndefined = (v: string) => v.trim() || undefined;
      const updated = await companyService.updateSettings({
        name,
        address_street: emptyToUndefined(addressStreet),
        address_city: emptyToUndefined(addressCity),
        address_state: emptyToUndefined(addressState),
        address_zip: emptyToUndefined(addressZip),
        phone: emptyToUndefined(phone),
        email: emptyToUndefined(email),
        timezone,
        logo_url: emptyToUndefined(logoUrl),
      });
      populateForm(updated);
      await refreshCompany();
      toast.success("Company settings saved");
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Failed to save settings"));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl space-y-6">
        <h1 className="text-2xl font-bold">Company Settings</h1>
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold">Company Settings</h1>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* General Info */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold">General Information</h2>
          <Separator className="my-4" />
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Company Name</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={!canEdit}
                required
              />
            </div>
            <div className="space-y-2">
              <Label>Slug</Label>
              <Input value={slug} disabled />
              <p className="text-xs text-muted-foreground">
                The URL slug cannot be changed after creation.
              </p>
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

        {/* Contact */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold">Contact Information</h2>
          <Separator className="my-4" />
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
              <Label>Email</Label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={!canEdit}
                placeholder="info@company.com"
              />
            </div>
          </div>
        </Card>

        {/* Configuration */}
        <Card className="p-6">
          <h2 className="text-lg font-semibold">Configuration</h2>
          <Separator className="my-4" />
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Timezone</Label>
              <select
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                disabled={!canEdit}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-[color,box-shadow] focus-visible:border-ring focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {TIMEZONE_OPTIONS.map((tz) => (
                  <option key={tz.value} value={tz.value}>
                    {tz.label} — {tz.value}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label>Logo URL</Label>
              <Input
                value={logoUrl}
                onChange={(e) => setLogoUrl(e.target.value)}
                disabled={!canEdit}
                placeholder="https://example.com/logo.png"
              />
              <p className="text-xs text-muted-foreground">
                Direct URL to your company logo image.
              </p>
            </div>
          </div>
        </Card>

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
