/**
 * Maps extension keys to lucide-react icon component names.
 * Import the corresponding icon from "lucide-react" using this mapping.
 */

import {
  Award,
  BarChart3,
  Beaker,
  Blocks,
  Box,
  Building2,
  Calendar,
  CheckSquare,
  Droplets,
  FileText,
  Flame,
  Flower2,
  HeartHandshake,
  Layers,
  ListTree,
  Printer,
  Puzzle,
  Settings,
  ShoppingBag,
  Sparkles,
  TrendingUp,
  Video,
  Wrench,
  type LucideIcon,
} from "lucide-react";

export const EXTENSION_ICONS: Record<string, LucideIcon> = {
  wastewater_treatment: Droplets,
  redi_rock: Blocks,
  rosetta_hardscapes: Layers,
  npca_audit_prep: Award,
  work_orders: Wrench,
  pour_events_cure_tracking: Beaker,
  pour_events_batch_tickets: Beaker,
  qc_module_full: CheckSquare,
  full_qc_module: CheckSquare,
  ai_obituary_builder: Sparkles,
  pre_need_contracts: FileText,
  cremation_workflow: Flame,
  clergy_scheduling: Calendar,
  florist_one: Flower2,
  florist: Flower2,
  livestreaming: Video,
  printed_memorials: Printer,
  aftercare_program: HeartHandshake,
  aftercare: HeartHandshake,
  merchandise_ecommerce: ShoppingBag,
  merchandise: ShoppingBag,
  trade_crematory: Building2,
  bill_of_materials: ListTree,
  equipment_maintenance: Settings,
  advanced_reporting: BarChart3,
  mold_inventory: Box,
  capacity_planning: TrendingUp,
};

const DEFAULT_ICON: LucideIcon = Puzzle;

export function getExtensionIcon(extensionKey: string): LucideIcon {
  return EXTENSION_ICONS[extensionKey] ?? DEFAULT_ICON;
}
