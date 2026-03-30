export interface CemeteryDirectoryEntry {
  id: string;
  place_id: string;
  name: string;
  address: string | null;
  city: string | null;
  state_code: string | null;
  zip_code: string | null;
  county: string | null;
  google_rating: number | null;
  google_review_count: number | null;
  latitude: number | null;
  longitude: number | null;
  already_added: boolean;
}

export interface CemeteryEquipmentSettings {
  provides_lowering_device: boolean;
  provides_grass: boolean;
  provides_tent: boolean;
  provides_chairs: boolean;
}

export interface CemeterySelectionItem {
  place_id: string;
  name: string;
  action: "add" | "skip";
  equipment: CemeteryEquipmentSettings;
  county: string | null;
  equipment_note: string | null;
}

export interface CemeteryManualEntry {
  name: string;
  city: string | null;
  state: string | null;
  county: string | null;
  equipment: CemeteryEquipmentSettings;
  equipment_note: string | null;
}
