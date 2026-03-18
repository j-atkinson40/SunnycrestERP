import { Check, Settings as GearIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { getExtensionIcon } from "./extension-icons";
import type { ExtensionCatalogItem } from "@/types/extension";
import { CATEGORY_LABELS, type ExtensionCategory } from "@/types/extension";

// ── Preset accent colors ──

const PRESET_ACCENTS: Record<string, { hover: string; accent: string }> = {
  manufacturing: { hover: "hover:border-slate-400", accent: "border-l-slate-500" },
  funeral_home: { hover: "hover:border-stone-400", accent: "border-l-stone-500" },
  cemetery: { hover: "hover:border-green-600", accent: "border-l-green-700" },
  crematory: { hover: "hover:border-red-800", accent: "border-l-red-800" },
};

function getAccent(vertical: string | null) {
  return PRESET_ACCENTS[vertical ?? ""] ?? PRESET_ACCENTS.manufacturing;
}

// ── Badge rendering ──

type BadgeVariant = "installed" | "coming_soon" | "advanced" | "most_popular" | "pending_setup";

const BADGE_STYLES: Record<BadgeVariant, string> = {
  installed: "bg-green-50 text-green-700",
  coming_soon: "bg-blue-50 text-blue-600",
  advanced: "bg-slate-100 text-slate-600",
  most_popular: "bg-amber-50 text-amber-700",
  pending_setup: "bg-amber-50 text-amber-700",
};

const BADGE_LABELS: Record<BadgeVariant, string> = {
  installed: "Installed \u2713",
  coming_soon: "Coming Soon",
  advanced: "Advanced",
  most_popular: "Most Popular",
  pending_setup: "Setup Required",
};

function Badge({ variant }: { variant: BadgeVariant }) {
  return (
    <span
      className={cn(
        "text-xs font-medium px-2 py-0.5 rounded-full",
        BADGE_STYLES[variant],
      )}
    >
      {BADGE_LABELS[variant]}
    </span>
  );
}

// ── Extension Card ──

interface ExtensionCardProps {
  extension: ExtensionCatalogItem;
  badge?: string;
  vertical?: string | null;
  onClick: () => void;
  onNotifyMe?: (extensionKey: string) => void;
  notifiedKeys?: Set<string>;
}

export function ExtensionCard({
  extension,
  badge,
  vertical,
  onClick,
  onNotifyMe,
  notifiedKeys,
}: ExtensionCardProps) {
  const ext = extension;
  const Icon = getExtensionIcon(ext.extension_key);
  const accent = getAccent(vertical ?? null);
  const isInstalled = ext.installed && ext.install_status === "active";
  const isComingSoon = ext.status === "coming_soon";
  const isPendingSetup = ext.install_status === "pending_setup";
  const isNotified = notifiedKeys?.has(ext.extension_key) ?? false;

  // Determine top-right badge
  let badgeVariant: BadgeVariant | null = null;
  if (isInstalled) badgeVariant = "installed";
  else if (isPendingSetup) badgeVariant = "pending_setup";
  else if (isComingSoon) badgeVariant = "coming_soon";
  if (badge === "Advanced") badgeVariant = "advanced";
  if (badge === "Most Popular") badgeVariant = "most_popular";

  // Access model label
  const accessLabel =
    ext.access_model === "included"
      ? "Included"
      : ext.access_model === "paid_addon" && ext.addon_price_monthly
        ? `$${ext.addon_price_monthly}/mo`
        : null;

  // Feature bullets (max 2)
  const bullets = ext.feature_bullets?.slice(0, 2) ?? [];

  return (
    <button
      onClick={onClick}
      className={cn(
        "relative flex flex-col text-left w-full rounded-xl border border-l-4 bg-white p-5 transition-all duration-200",
        "hover:shadow-md hover:-translate-y-0.5",
        accent.hover,
        accent.accent,
        isComingSoon && "opacity-80",
      )}
    >
      {/* Top-right badge */}
      {badgeVariant && (
        <div className="absolute top-3 right-3">
          <Badge variant={badgeVariant} />
        </div>
      )}

      {/* Icon + Name */}
      <div className="flex items-start gap-3 pr-24">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-600">
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <h3 className="font-semibold text-gray-900 truncate">{ext.name}</h3>
          {ext.tagline && (
            <p className="mt-0.5 text-sm text-gray-500 line-clamp-1">{ext.tagline}</p>
          )}
        </div>
      </div>

      {/* Category tag */}
      <div className="mt-3">
        <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 font-medium">
          {CATEGORY_LABELS[ext.category as ExtensionCategory] || ext.category}
        </span>
      </div>

      {/* Feature bullets */}
      {bullets.length > 0 && (
        <ul className="mt-3 space-y-1">
          {bullets.map((bullet, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-gray-600">
              <Check className="h-3.5 w-3.5 shrink-0 text-green-500 mt-0.5" />
              <span className="line-clamp-1">{bullet}</span>
            </li>
          ))}
        </ul>
      )}

      {/* Bottom: access model + action */}
      <div className="mt-auto pt-4 flex items-center justify-between gap-2">
        {accessLabel && (
          <span className={cn(
            "text-xs font-medium px-2 py-0.5 rounded-full",
            ext.access_model === "included"
              ? "bg-green-50 text-green-700"
              : "bg-gray-100 text-gray-700",
          )}>
            {accessLabel}
          </span>
        )}
        {!accessLabel && <span />}

        {/* Action indicator */}
        {isInstalled ? (
          <span className="flex items-center gap-1 text-xs text-gray-400">
            <GearIcon className="h-3.5 w-3.5" />
          </span>
        ) : isComingSoon ? (
          <span
            role="button"
            onClick={(e) => {
              e.stopPropagation();
              if (!isNotified && onNotifyMe) onNotifyMe(ext.extension_key);
            }}
            className={cn(
              "text-xs font-medium px-3 py-1 rounded-md border transition-colors",
              isNotified
                ? "border-gray-200 text-gray-400 cursor-default"
                : "border-gray-300 text-gray-600 hover:bg-gray-50",
            )}
          >
            {isNotified ? "Notified \u2713" : "Notify Me"}
          </span>
        ) : ext.access_model === "included" || ext.access_model === "paid_addon" ? (
          <span className="text-xs font-medium px-3 py-1 rounded-md bg-green-600 text-white">
            {ext.access_model === "paid_addon" && ext.addon_price_monthly
              ? `Add for $${ext.addon_price_monthly}/mo`
              : "Enable"}
          </span>
        ) : (
          <span className="text-xs font-medium px-3 py-1 rounded-md bg-indigo-600 text-white">
            Upgrade
          </span>
        )}
      </div>
    </button>
  );
}
