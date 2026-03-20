/**
 * Scheduling Board Setup — 3-question onboarding wizard.
 *
 * Configures driver count, Saturday handling, and lead time for the
 * funeral kanban scheduler (always-on core feature).
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, ArrowRight, Truck, Calendar, Clock } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import apiClient from "@/lib/api-client";

interface SchedulingConfig {
  driver_count: number;
  saturday_handling: "normal" | "surcharge" | "no_delivery";
  lead_time: "same_day" | "next_business_day" | "2_business_days" | "custom";
  lead_time_custom_days: number | null;
}

const SATURDAY_OPTIONS = [
  {
    value: "normal" as const,
    label: "We deliver on Saturdays",
    desc: "Schedule normally — no restrictions or surcharges",
  },
  {
    value: "surcharge" as const,
    label: "We deliver Saturdays with a surcharge",
    desc: "Use spring burial surcharge settings for Saturday deliveries",
  },
  {
    value: "no_delivery" as const,
    label: "We don't deliver on Saturdays",
    desc: "Show a warning when Saturday is selected",
  },
];

const LEAD_TIME_OPTIONS = [
  { value: "same_day" as const, label: "Same day", desc: "Emergency only" },
  { value: "next_business_day" as const, label: "Next business day", desc: "" },
  { value: "2_business_days" as const, label: "2 business days", desc: "Standard" },
  { value: "custom" as const, label: "Custom", desc: "" },
];

export default function SchedulingSetupPage() {
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState<SchedulingConfig>({
    driver_count: 2,
    saturday_handling: "normal",
    lead_time: "2_business_days",
    lead_time_custom_days: null,
  });

  // Load existing config if any
  useEffect(() => {
    apiClient
      .get("/tenant-onboarding/scheduling-board/config")
      .then(({ data }) => {
        if (data.configured) {
          setConfig({
            driver_count: data.driver_count ?? 2,
            saturday_handling: data.saturday_handling ?? "normal",
            lead_time: data.lead_time ?? "2_business_days",
            lead_time_custom_days: data.lead_time_custom_days ?? null,
          });
        }
      })
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.post("/tenant-onboarding/scheduling-board/configure", config);
      toast.success("Scheduling board configured");
      navigate("/onboarding");
    } catch {
      toast.error("Failed to save configuration");
    } finally {
      setSaving(false);
    }
  };

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
          Set up your scheduling board
        </h1>
        <p className="mt-1 text-gray-500">
          Three quick questions to configure your delivery scheduling board.
        </p>
      </div>

      <div className="space-y-10">
        {/* Question 1 — Driver count */}
        <section className="rounded-xl border bg-white p-6">
          <div className="flex items-start gap-3 mb-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <Truck className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900">
                How many drivers do you typically have available for funeral
                deliveries?
              </h2>
              <p className="text-sm text-gray-500 mt-0.5">
                This sets the default number of driver lanes on your Kanban
                board.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 ml-12">
            <button
              onClick={() =>
                setConfig((c) => ({
                  ...c,
                  driver_count: Math.max(1, c.driver_count - 1),
                }))
              }
              className="flex h-10 w-10 items-center justify-center rounded-lg border text-lg font-medium hover:bg-gray-50"
            >
              −
            </button>
            <span className="w-12 text-center text-2xl font-bold text-gray-900">
              {config.driver_count}
            </span>
            <button
              onClick={() =>
                setConfig((c) => ({
                  ...c,
                  driver_count: Math.min(20, c.driver_count + 1),
                }))
              }
              className="flex h-10 w-10 items-center justify-center rounded-lg border text-lg font-medium hover:bg-gray-50"
            >
              +
            </button>
            <span className="text-sm text-gray-400 ml-2">drivers</span>
          </div>
        </section>

        {/* Question 2 — Saturday handling */}
        <section className="rounded-xl border bg-white p-6">
          <div className="flex items-start gap-3 mb-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
              <Calendar className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900">
                How do you handle Saturday funeral deliveries?
              </h2>
            </div>
          </div>
          <div className="ml-12 space-y-2">
            {SATURDAY_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={cn(
                  "flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors",
                  config.saturday_handling === opt.value
                    ? "border-blue-500 bg-blue-50/50"
                    : "hover:bg-gray-50",
                )}
              >
                <input
                  type="radio"
                  name="saturday"
                  checked={config.saturday_handling === opt.value}
                  onChange={() =>
                    setConfig((c) => ({ ...c, saturday_handling: opt.value }))
                  }
                  className="mt-0.5"
                />
                <div>
                  <div className="font-medium text-gray-900 text-sm">
                    {opt.label}
                  </div>
                  <div className="text-xs text-gray-500">{opt.desc}</div>
                </div>
              </label>
            ))}
          </div>
        </section>

        {/* Question 3 — Lead time */}
        <section className="rounded-xl border bg-white p-6">
          <div className="flex items-start gap-3 mb-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-green-50 text-green-600">
              <Clock className="h-5 w-5" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900">
                What's your standard lead time for funeral vault orders?
              </h2>
            </div>
          </div>
          <div className="ml-12 space-y-2">
            {LEAD_TIME_OPTIONS.map((opt) => (
              <label
                key={opt.value}
                className={cn(
                  "flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors",
                  config.lead_time === opt.value
                    ? "border-blue-500 bg-blue-50/50"
                    : "hover:bg-gray-50",
                )}
              >
                <input
                  type="radio"
                  name="lead_time"
                  checked={config.lead_time === opt.value}
                  onChange={() =>
                    setConfig((c) => ({ ...c, lead_time: opt.value }))
                  }
                  className="mt-0.5"
                />
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-900 text-sm">
                    {opt.label}
                  </span>
                  {opt.desc && (
                    <span className="text-xs text-gray-400">({opt.desc})</span>
                  )}
                </div>
              </label>
            ))}

            {/* Custom days input */}
            {config.lead_time === "custom" && (
              <div className="flex items-center gap-2 ml-7 mt-2">
                <input
                  type="number"
                  min={1}
                  max={30}
                  value={config.lead_time_custom_days ?? ""}
                  onChange={(e) =>
                    setConfig((c) => ({
                      ...c,
                      lead_time_custom_days: e.target.value
                        ? parseInt(e.target.value)
                        : null,
                    }))
                  }
                  className="w-20 rounded-md border px-3 py-1.5 text-sm"
                  placeholder="Days"
                />
                <span className="text-sm text-gray-500">days</span>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Footer */}
      <div className="mt-8 flex justify-end">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save and continue"}
          {!saving && <ArrowRight className="ml-2 h-4 w-4" />}
        </Button>
      </div>
    </div>
  );
}
