import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/contexts/auth-context";
import { deliveryService } from "@/services/delivery-service";
import { getApiErrorMessage } from "@/lib/api-error";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import type { DeliverySettings, DeliverySettingsUpdate } from "@/types/delivery";

interface ToggleDef {
  key: keyof DeliverySettingsUpdate;
  label: string;
  description: string;
}

const TOGGLE_GROUPS: { title: string; toggles: ToggleDef[] }[] = [
  {
    title: "Driver Requirements",
    toggles: [
      { key: "require_photo_on_delivery", label: "Require Photo on Delivery", description: "Drivers must take a photo at each delivery stop" },
      { key: "require_signature", label: "Require Signature", description: "Collect a signature from the receiving party" },
      { key: "require_weight_ticket", label: "Require Weight Ticket", description: "Drivers must submit a weight ticket for applicable deliveries" },
      { key: "require_setup_confirmation", label: "Require Setup Confirmation", description: "Confirm setup completion before marking stop as done" },
      { key: "require_departure_photo", label: "Require Departure Photo", description: "Take a photo after setup/delivery is complete" },
      { key: "require_mileage_entry", label: "Require Mileage Entry", description: "Drivers must log odometer readings at route start and end" },
    ],
  },
  {
    title: "Driver Permissions",
    toggles: [
      { key: "allow_partial_delivery", label: "Allow Partial Delivery", description: "Drivers can mark a delivery as partially fulfilled" },
      { key: "allow_driver_resequence", label: "Allow Driver Resequence", description: "Drivers can reorder their stops on the mobile app" },
      { key: "enable_driver_messaging", label: "Enable Driver Messaging", description: "In-app messaging between dispatch and drivers" },
    ],
  },
  {
    title: "Tracking & GPS",
    toggles: [
      { key: "track_gps", label: "Track GPS", description: "Record GPS coordinates at each delivery event" },
    ],
  },
  {
    title: "Customer Notifications",
    toggles: [
      { key: "notify_customer_on_dispatch", label: "Notify on Dispatch", description: "Send notification when delivery is dispatched" },
      { key: "notify_customer_on_arrival", label: "Notify on Arrival", description: "Send notification when driver arrives" },
      { key: "notify_customer_on_complete", label: "Notify on Complete", description: "Send notification when delivery is completed" },
    ],
  },
  {
    title: "Connected Tenant Notifications",
    toggles: [
      { key: "notify_connected_tenant_on_arrival", label: "Notify Tenant on Arrival", description: "Notify connected tenants (e.g., funeral homes) when driver arrives" },
      { key: "notify_connected_tenant_on_setup", label: "Notify Tenant on Setup", description: "Notify connected tenants when setup is confirmed" },
    ],
  },
  {
    title: "Portal & Automation",
    toggles: [
      { key: "enable_delivery_portal", label: "Enable Delivery Portal", description: "Customer-facing delivery tracking portal" },
      { key: "auto_create_delivery_from_order", label: "Auto-Create from Order", description: "Automatically create a delivery when a sales order is placed" },
      { key: "auto_invoice_on_complete", label: "Auto-Invoice on Complete", description: "Automatically generate an invoice when delivery completes" },
    ],
  },
  {
    title: "Third-Party Carriers",
    toggles: [
      { key: "sms_carrier_updates", label: "SMS Carrier Updates", description: "Send SMS to carriers with delivery details and accept keyword replies (PICKED/DELIVERED/ISSUE)" },
      { key: "carrier_portal", label: "Carrier Portal", description: "Enable a simplified portal for external carriers to view and update deliveries" },
    ],
  },
];

const PRESET_INFO: Record<string, { label: string; description: string; color: string }> = {
  standard: { label: "Standard", description: "Minimal requirements — good starting point", color: "bg-gray-100 text-gray-800" },
  funeral_vault: { label: "Funeral Vault", description: "Full compliance — photos, signatures, setup confirmation, all notifications", color: "bg-purple-100 text-purple-800" },
  precast: { label: "Precast", description: "Weight tickets, partial delivery, GPS tracking", color: "bg-blue-100 text-blue-800" },
  redi_rock: { label: "Redi-Rock", description: "Like Precast plus SMS carrier updates and carrier portal", color: "bg-orange-100 text-orange-800" },
};

export default function DeliverySettingsPage() {
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("delivery.edit");

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState<DeliverySettings | null>(null);
  const [presets, setPresets] = useState<string[]>([]);

  const loadSettings = useCallback(async () => {
    try {
      setLoading(true);
      const [s, p] = await Promise.all([
        deliveryService.getSettings(),
        deliveryService.listPresets(),
      ]);
      setSettings(s);
      setPresets(p.presets);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const handleToggle = async (key: string, value: boolean) => {
    if (!settings || !canEdit) return;
    const prev = { ...settings };
    setSettings({ ...settings, [key]: value });
    try {
      setSaving(true);
      const updated = await deliveryService.updateSettings({ [key]: value } as DeliverySettingsUpdate);
      setSettings(updated);
    } catch (err) {
      setSettings(prev);
      toast.error(getApiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleNumberChange = async (key: string, value: number | null) => {
    if (!settings || !canEdit) return;
    const prev = { ...settings };
    setSettings({ ...settings, [key]: value } as DeliverySettings);
    try {
      setSaving(true);
      const updated = await deliveryService.updateSettings({ [key]: value } as DeliverySettingsUpdate);
      setSettings(updated);
    } catch (err) {
      setSettings(prev);
      toast.error(getApiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleApplyPreset = async (presetName: string) => {
    try {
      setSaving(true);
      const updated = await deliveryService.applyPreset(presetName);
      setSettings(updated);
      toast.success(`Applied "${PRESET_INFO[presetName]?.label || presetName}" preset`);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-muted-foreground">Loading delivery settings...</p>
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="flex h-64 items-center justify-center">
        <p className="text-destructive">Failed to load settings</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Delivery Settings</h1>
        <p className="text-sm text-muted-foreground">
          Configure delivery requirements, notifications, and automation for your organization.
        </p>
      </div>

      {/* Current Preset */}
      <Card className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">Current Preset</p>
            <p className="text-lg font-semibold">{PRESET_INFO[settings.preset]?.label || settings.preset}</p>
          </div>
          {saving && <Badge variant="outline">Saving...</Badge>}
        </div>
      </Card>

      {/* Preset Cards */}
      {canEdit && (
        <div>
          <h2 className="mb-3 text-lg font-semibold">Quick Presets</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {presets.map((name) => {
              const info = PRESET_INFO[name];
              const isActive = settings.preset === name;
              return (
                <Card
                  key={name}
                  className={`cursor-pointer p-4 transition-colors ${isActive ? "border-primary ring-2 ring-primary/20" : "hover:border-muted-foreground/30"}`}
                  onClick={() => !isActive && handleApplyPreset(name)}
                >
                  <div className="flex items-start justify-between">
                    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${info?.color || "bg-gray-100 text-gray-800"}`}>
                      {info?.label || name}
                    </span>
                    {isActive && (
                      <Badge variant="default" className="text-xs">Active</Badge>
                    )}
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {info?.description || name}
                  </p>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      <Separator />

      {/* Toggle Groups */}
      <div className="space-y-6">
        {TOGGLE_GROUPS.map((group) => (
          <div key={group.title}>
            <h2 className="mb-3 text-lg font-semibold">{group.title}</h2>
            <Card className="divide-y">
              {group.toggles.map((toggle) => {
                const value = settings[toggle.key as keyof DeliverySettings];
                return (
                  <div key={toggle.key} className="flex items-center justify-between px-4 py-3">
                    <div className="space-y-0.5 pr-4">
                      <Label className="text-sm font-medium">{toggle.label}</Label>
                      <p className="text-xs text-muted-foreground">{toggle.description}</p>
                    </div>
                    <Switch
                      checked={value === true}
                      onCheckedChange={(checked: boolean) => handleToggle(toggle.key, checked)}
                      disabled={!canEdit || saving}
                    />
                  </div>
                );
              })}
            </Card>
          </div>
        ))}
      </div>

      <Separator />

      {/* Numeric Settings */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">Limits & Defaults</h2>
        <Card className="space-y-4 p-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="max_stops">Max Stops Per Route</Label>
              <Input
                id="max_stops"
                type="number"
                min={1}
                max={100}
                value={settings.max_stops_per_route ?? ""}
                placeholder="No limit"
                disabled={!canEdit || saving}
                onChange={(e) => {
                  const val = e.target.value ? parseInt(e.target.value, 10) : null;
                  handleNumberChange("max_stops_per_route", val);
                }}
              />
              <p className="text-xs text-muted-foreground">Maximum number of stops allowed on a single route</p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="window_minutes">Default Delivery Window (minutes)</Label>
              <Input
                id="window_minutes"
                type="number"
                min={15}
                max={480}
                step={15}
                value={settings.default_delivery_window_minutes ?? ""}
                placeholder="No default"
                disabled={!canEdit || saving}
                onChange={(e) => {
                  const val = e.target.value ? parseInt(e.target.value, 10) : null;
                  handleNumberChange("default_delivery_window_minutes", val);
                }}
              />
              <p className="text-xs text-muted-foreground">Default time window for delivery appointments</p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
