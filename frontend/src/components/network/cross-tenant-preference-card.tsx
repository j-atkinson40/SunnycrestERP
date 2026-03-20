/**
 * Reusable preference card for cross-tenant network preferences.
 *
 * Used by both the onboarding wizard and the post-onboarding settings page.
 */

import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface CrossTenantPreferenceCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
  bullets?: string[];
  deliveryMethods?: { email: boolean; sms: boolean };
  yesLabel?: string;
  noLabel?: string;
  value: boolean;
  onChange: (value: boolean) => void;
  muted?: string;
  hidden?: boolean;
}

export function CrossTenantPreferenceCard({
  icon: Icon,
  title,
  description,
  bullets,
  yesLabel = "Yes",
  noLabel = "No",
  value,
  onChange,
  muted,
  hidden,
}: CrossTenantPreferenceCardProps) {
  if (hidden) return null;

  return (
    <div className="rounded-xl border bg-white p-6">
      {/* Header */}
      <div className="flex items-start gap-3 mb-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gray-100 text-gray-600">
          <Icon className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-gray-900">{title}</h3>
          <p className="mt-1 text-sm text-gray-500 leading-relaxed">
            {description}
          </p>
        </div>
      </div>

      {/* Bullets */}
      {bullets && bullets.length > 0 && (
        <div className="ml-12 mb-4">
          <p className="text-xs font-medium text-gray-500 mb-1.5">
            What they receive:
          </p>
          <ul className="space-y-1">
            {bullets.map((bullet, i) => (
              <li
                key={i}
                className="text-sm text-gray-600 flex items-start gap-1.5"
              >
                <span className="text-gray-400 mt-0.5">•</span>
                {bullet}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Muted note */}
      {muted && (
        <div className="ml-12 mb-4">
          <p className="text-xs text-amber-600 bg-amber-50 rounded-md px-3 py-1.5">
            {muted}
          </p>
        </div>
      )}

      {/* Yes/No toggle */}
      <div className="ml-12 space-y-2">
        <label
          className={cn(
            "flex items-center gap-3 rounded-lg border p-3 cursor-pointer transition-colors",
            value ? "border-blue-500 bg-blue-50/50" : "hover:bg-gray-50",
          )}
        >
          <input
            type="radio"
            name={title}
            checked={value}
            onChange={() => onChange(true)}
          />
          <span className="text-sm text-gray-900">
            {yesLabel}
          </span>
        </label>
        <label
          className={cn(
            "flex items-center gap-3 rounded-lg border p-3 cursor-pointer transition-colors",
            !value ? "border-gray-400 bg-gray-50/50" : "hover:bg-gray-50",
          )}
        >
          <input
            type="radio"
            name={title}
            checked={!value}
            onChange={() => onChange(false)}
          />
          <span className="text-sm text-gray-900">
            {noLabel}
          </span>
        </label>
      </div>
    </div>
  );
}
