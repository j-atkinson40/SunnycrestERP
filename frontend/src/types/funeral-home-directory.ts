export interface DirectoryEntry {
  id: string;
  place_id: string;
  name: string;
  address: string | null;
  city: string | null;
  state_code: string | null;
  zip_code: string | null;
  phone: string | null;
  website: string | null;
  google_rating: number | null;
  google_review_count: number | null;
  latitude: number | null;
  longitude: number | null;
}

export interface PlatformMatch {
  id: string;
  name: string;
  slug: string;
}

export interface DirectorySelection {
  directory_entry_id: string;
  action: "added_as_customer" | "skipped";
  invite: boolean;
}

export interface ManualCustomer {
  name: string;
  city: string;
  phone: string;
  invite: boolean;
}
