/**
 * Delivery type display utilities.
 *
 * Colors and labels can be overridden per-tenant by fetching from
 * GET /api/v1/delivery-types and calling setDeliveryTypeOverrides().
 */

export interface DeliveryTypeConfig {
  key: string;
  name: string;
  color: string;
  icon?: string;
  description?: string;
  driver_instructions?: string;
  requires_signature?: boolean;
  requires_photo?: boolean;
  requires_weight_ticket?: boolean;
  allows_partial?: boolean;
}

// Default type configs — used as fallback when tenant config hasn't loaded
const DEFAULT_TYPES: Record<string, DeliveryTypeConfig> = {
  standard: { key: "standard", name: "Standard", color: "gray" },
  funeral_vault: { key: "funeral_vault", name: "Vault", color: "purple" },
  precast: { key: "precast", name: "Precast", color: "blue" },
  redi_rock: { key: "redi_rock", name: "Redi-Rock", color: "orange" },
};

// Tenant-specific overrides (populated from API)
let _overrides: Record<string, DeliveryTypeConfig> = {};

/** Set tenant-specific delivery type definitions (call on app init). */
export function setDeliveryTypeOverrides(types: DeliveryTypeConfig[]) {
  _overrides = {};
  for (const t of types) {
    _overrides[t.key] = t;
  }
}

/** Get config for a delivery type key. */
export function getDeliveryType(key: string): DeliveryTypeConfig {
  return (
    _overrides[key] ||
    DEFAULT_TYPES[key] || { key, name: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()), color: "gray" }
  );
}

const COLOR_MAP: Record<string, string> = {
  purple: "bg-purple-100 text-purple-800",
  blue: "bg-blue-100 text-blue-800",
  orange: "bg-orange-100 text-orange-800",
  green: "bg-green-100 text-green-800",
  red: "bg-red-100 text-red-800",
  yellow: "bg-yellow-100 text-yellow-800",
  pink: "bg-pink-100 text-pink-800",
  indigo: "bg-indigo-100 text-indigo-800",
  gray: "bg-gray-100 text-gray-800",
};

/** Get Tailwind badge classes for a delivery type. */
export function getDeliveryTypeBadgeClass(key: string): string {
  const config = getDeliveryType(key);
  return COLOR_MAP[config.color] || COLOR_MAP.gray;
}

/** Get display name for a delivery type. */
export function getDeliveryTypeName(key: string): string {
  return getDeliveryType(key).name;
}

/** Get all known delivery type keys (from overrides or defaults). */
export function getAllDeliveryTypeKeys(): string[] {
  const keys = new Set([...Object.keys(DEFAULT_TYPES), ...Object.keys(_overrides)]);
  return Array.from(keys);
}
