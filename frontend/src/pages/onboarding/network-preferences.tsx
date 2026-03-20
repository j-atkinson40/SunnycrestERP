/**
 * Cross-Tenant Preferences — Onboarding step.
 *
 * Six preference cards that control how the manufacturer interacts
 * with connected funeral homes and cemeteries:
 * 1. Delivery Notifications
 * 2. Cemetery Notifications
 * 3. Spring Burial Portal Scheduling
 * 4. Legacy Print Submission
 * 5. Delivery Area (county selector)
 * 6. Driver Status Milestones
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, ArrowRight, Mail, Building2, Leaf, Image } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CrossTenantPreferenceCard } from "@/components/network/cross-tenant-preference-card";
import { DeliveryAreaCard } from "@/components/network/delivery-area-card";
import { DriverStatusMilestonesCard } from "@/components/network/driver-status-milestones-card";
import apiClient from "@/lib/api-client";

interface Preferences {
  delivery_notifications_enabled: boolean;
  cemetery_delivery_notifications: boolean;
  allow_portal_spring_burial_requests: boolean;
  accept_legacy_print_submissions: boolean;
  milestone_scheduled_enabled: boolean;
  milestone_on_my_way_enabled: boolean;
  milestone_arrived_enabled: boolean;
  milestone_delivered_enabled: boolean;
}

export default function NetworkPreferencesPage() {
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [springBurialsEnabled, setSpringBurialsEnabled] = useState(false);
  const [hasCemeteryCustomers, setHasCemeteryCustomers] = useState<boolean | null>(null);
  const [deliveryAreaConfigured, setDeliveryAreaConfigured] = useState(false);
  const [facilityState, setFacilityState] = useState<string | null>(null);
  const [prefs, setPrefs] = useState<Preferences>({
    delivery_notifications_enabled: true,
    cemetery_delivery_notifications: true,
    allow_portal_spring_burial_requests: true,
    accept_legacy_print_submissions: true,
    milestone_scheduled_enabled: true,
    milestone_on_my_way_enabled: true,
    milestone_arrived_enabled: true,
    milestone_delivered_enabled: true,
  });

  useEffect(() => {
    Promise.all([
      apiClient.get("/tenant-onboarding/cross-tenant-preferences"),
      apiClient.get("/customers", { params: { customer_type: "cemetery", limit: 1 } }).catch(() => ({ data: { items: [] } })),
    ]).then(([prefsRes, custRes]) => {
      const d = prefsRes.data;
      setPrefs({
        delivery_notifications_enabled: d.delivery_notifications_enabled ?? true,
        cemetery_delivery_notifications: d.cemetery_delivery_notifications ?? true,
        allow_portal_spring_burial_requests: d.allow_portal_spring_burial_requests ?? true,
        accept_legacy_print_submissions: d.accept_legacy_print_submissions ?? true,
        milestone_scheduled_enabled: d.milestone_scheduled_enabled ?? true,
        milestone_on_my_way_enabled: d.milestone_on_my_way_enabled ?? true,
        milestone_arrived_enabled: d.milestone_arrived_enabled ?? true,
        milestone_delivered_enabled: d.milestone_delivered_enabled ?? true,
      });
      setSpringBurialsEnabled(d.spring_burials_enabled ?? false);
      setDeliveryAreaConfigured(d.delivery_area_configured ?? false);
      setFacilityState(d.facility_state ?? null);
      const items = custRes.data?.items ?? custRes.data ?? [];
      setHasCemeteryCustomers(Array.isArray(items) && items.length > 0);
    }).finally(() => setLoading(false));
  }, []);

  const update = (key: keyof Preferences, value: boolean) => {
    setPrefs((p) => ({ ...p, [key]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.post("/tenant-onboarding/cross-tenant-preferences", prefs);
      toast.success("Network preferences saved");
      navigate("/onboarding");
    } catch {
      toast.error("Failed to save preferences");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate("/onboarding")}
          className="mb-4 flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to onboarding
        </button>
        <h1 className="text-2xl font-bold text-gray-900">
          How would you like to work with your network?
        </h1>
        <p className="mt-1 text-gray-500">
          These settings control how your connected funeral homes and cemeteries
          interact with your account. You can change these anytime.
        </p>
      </div>

      <div className="space-y-5">
        {/* Card 1 — Delivery Notifications */}
        <CrossTenantPreferenceCard
          icon={Mail}
          title="Delivery Notifications"
          description="Automatically notify connected funeral homes when their vault is scheduled, your driver departs, and delivery is complete."
          bullets={[
            '"Your vault is scheduled for [date]"',
            '"Your driver is on the way"',
            '"Your vault has been delivered"',
          ]}
          yesLabel="Yes — keep them informed automatically"
          noLabel="No — I'll communicate directly"
          value={prefs.delivery_notifications_enabled}
          onChange={(v) => update("delivery_notifications_enabled", v)}
        />

        {/* Card 2 — Cemetery Notifications */}
        <CrossTenantPreferenceCard
          icon={Building2}
          title="Cemetery Notifications"
          description="Automatically notify connected cemeteries when equipment or vaults are scheduled for delivery to their location."
          yesLabel="Yes"
          noLabel="No"
          value={prefs.cemetery_delivery_notifications}
          onChange={(v) => update("cemetery_delivery_notifications", v)}
          muted={
            hasCemeteryCustomers === false
              ? "You haven't added any cemetery customers yet. This will apply when you do."
              : undefined
          }
        />

        {/* Card 3 — Spring Burial Portal Scheduling */}
        <CrossTenantPreferenceCard
          icon={Leaf}
          title="Spring Burial Portal Scheduling"
          description="Allow connected funeral homes to schedule their spring burials directly through their portal. You'll see their requests on your spring burial board and confirm or adjust scheduling."
          bullets={[
            "Funeral home submits a spring burial request",
            "You see it on your spring burial board",
            "You confirm the date — they're notified",
          ]}
          yesLabel="Yes — they request, I confirm"
          noLabel="No — I handle all spring burial scheduling"
          value={prefs.allow_portal_spring_burial_requests}
          onChange={(v) => update("allow_portal_spring_burial_requests", v)}
          hidden={!springBurialsEnabled}
        />

        {/* Card 4 — Legacy Print Submission */}
        <CrossTenantPreferenceCard
          icon={Image}
          title="Legacy Print Submission"
          description="Receive legacy print production files automatically from connected funeral homes. Files arrive ready for Wilbert submission — no phone calls or emails required."
          yesLabel="Yes"
          noLabel="No — not applicable to my operation"
          value={prefs.accept_legacy_print_submissions}
          onChange={(v) => update("accept_legacy_print_submissions", v)}
        />

        {/* Card 5 — Delivery Area */}
        <DeliveryAreaCard
          facilityState={facilityState}
          deliveryAreaConfigured={deliveryAreaConfigured}
          onSaved={() => setDeliveryAreaConfigured(true)}
          mode="onboarding"
        />

        {/* Card 6 — Driver Status Milestones */}
        <DriverStatusMilestonesCard
          value={{
            milestone_scheduled_enabled: prefs.milestone_scheduled_enabled,
            milestone_on_my_way_enabled: prefs.milestone_on_my_way_enabled,
            milestone_arrived_enabled: prefs.milestone_arrived_enabled,
            milestone_delivered_enabled: prefs.milestone_delivered_enabled,
          }}
          onChange={(key, val) => update(key, val)}
          disabled={!prefs.delivery_notifications_enabled}
        />
      </div>

      {/* Footer */}
      <div className="mt-8 flex items-center justify-between">
        <button
          onClick={() => navigate("/onboarding")}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save preferences"}
          {!saving && <ArrowRight className="ml-2 h-4 w-4" />}
        </Button>
      </div>
    </div>
  );
}
