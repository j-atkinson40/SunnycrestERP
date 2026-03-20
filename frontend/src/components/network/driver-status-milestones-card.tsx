/**
 * DriverStatusMilestonesCard — configure which driver milestones
 * trigger notifications AND show action buttons on the driver console.
 *
 * Used by both onboarding and settings network-preferences pages.
 */

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Activity, AlertTriangle } from "lucide-react";

interface MilestoneSettings {
  milestone_scheduled_enabled: boolean;
  milestone_on_my_way_enabled: boolean;
  milestone_arrived_enabled: boolean;
  milestone_delivered_enabled: boolean;
}

interface DriverStatusMilestonesCardProps {
  value: MilestoneSettings;
  onChange: (key: keyof MilestoneSettings, value: boolean) => void;
  /** When true, card is muted with a note that the master switch is off */
  disabled?: boolean;
}

interface MilestoneRow {
  key: keyof MilestoneSettings;
  label: string;
  description: string;
  buttonPreview: string;
  automatic?: boolean;
}

const MILESTONES: MilestoneRow[] = [
  {
    key: "milestone_scheduled_enabled",
    label: "Scheduled",
    description:
      "Notification sent automatically when a delivery is assigned to a driver or schedule.",
    buttonPreview: "Automatic — no driver action",
    automatic: true,
  },
  {
    key: "milestone_on_my_way_enabled",
    label: "On My Way",
    description:
      'Driver taps "On My Way" when leaving the plant. Connected funeral homes see the update in real time.',
    buttonPreview: '"On My Way" button',
  },
  {
    key: "milestone_arrived_enabled",
    label: "Arrived",
    description:
      "Driver taps \"I've Arrived\" at the delivery location. Notifies the funeral home their vault is on site.",
    buttonPreview: '"I\'ve Arrived" button',
  },
  {
    key: "milestone_delivered_enabled",
    label: "Delivered",
    description:
      'Driver taps "Mark Delivered" after setup is complete. This finalizes the delivery record and triggers invoicing.',
    buttonPreview: '"Mark Delivered" button',
  },
];

export function DriverStatusMilestonesCard({
  value,
  onChange,
  disabled = false,
}: DriverStatusMilestonesCardProps) {
  const [showDeliveredWarning, setShowDeliveredWarning] = useState(false);

  const handleToggle = (key: keyof MilestoneSettings) => {
    const newValue = !value[key];

    // Special warning when disabling "Delivered"
    if (key === "milestone_delivered_enabled" && !newValue) {
      setShowDeliveredWarning(true);
      return;
    }

    onChange(key, newValue);
  };

  const confirmDisableDelivered = () => {
    setShowDeliveredWarning(false);
    onChange("milestone_delivered_enabled", false);
  };

  return (
    <div
      className={cn(
        "rounded-xl border bg-white p-6 transition-opacity",
        disabled && "opacity-50 pointer-events-none",
      )}
    >
      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gray-100 text-gray-600">
          <Activity className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-gray-900">
            Driver Status Milestones
          </h3>
          <p className="mt-1 text-sm text-gray-500 leading-relaxed">
            Choose which status milestones your drivers can set and which
            trigger notifications to connected funeral homes. Disabling a
            milestone hides the button from the driver console and stops
            notifications for that step.
          </p>
        </div>
      </div>

      {disabled && (
        <div className="ml-12 mb-4">
          <p className="text-xs text-amber-600 bg-amber-50 rounded-md px-3 py-1.5">
            Delivery notifications are turned off. Enable them above to
            configure individual milestones.
          </p>
        </div>
      )}

      {/* Milestone rows */}
      <div className="ml-12 space-y-3">
        {MILESTONES.map((m) => (
          <label
            key={m.key}
            className={cn(
              "flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors",
              value[m.key]
                ? "border-blue-200 bg-blue-50/40"
                : "border-gray-200 hover:bg-gray-50",
            )}
          >
            <input
              type="checkbox"
              checked={value[m.key]}
              onChange={() => handleToggle(m.key)}
              className="mt-0.5 rounded"
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-900">
                  {m.label}
                </span>
                {m.automatic && (
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-500">
                    Auto
                  </span>
                )}
              </div>
              <p className="mt-0.5 text-xs text-gray-500 leading-relaxed">
                {m.description}
              </p>
              <p className="mt-1 text-[11px] text-gray-400 italic">
                {m.buttonPreview}
              </p>
            </div>
          </label>
        ))}
      </div>

      {/* Warning modal for disabling "Delivered" */}
      {showDeliveredWarning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="mx-4 max-w-sm rounded-xl border bg-white p-6 shadow-lg">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100 text-red-600">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <h4 className="font-semibold text-gray-900">
                  Disable "Mark Delivered"?
                </h4>
                <p className="mt-1 text-sm text-gray-500 leading-relaxed">
                  Disabling this milestone means drivers will not be able to
                  mark deliveries as complete from the console. Deliveries
                  will need to be completed manually from the scheduling
                  board. Auto-invoicing on delivery completion will also stop
                  working.
                </p>
              </div>
            </div>
            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                onClick={() => setShowDeliveredWarning(false)}
                className="rounded-lg border px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Keep enabled
              </button>
              <button
                onClick={confirmDisableDelivered}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
              >
                Disable anyway
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
