export interface ExtractedFieldValue {
  value: string | number | boolean | null;
  confidence: number;
  is_new: boolean;
}

export interface FirstCallExtractionResult {
  extracted: Record<string, ExtractedFieldValue>;
  not_extracted: string[];
  fields_updated: number;
}

export interface FirstCallFormValues {
  // Deceased
  deceased_first_name: string;
  deceased_last_name: string;
  deceased_date_of_death: string;
  deceased_time_of_death: string;
  deceased_place_of_death: string;
  deceased_place_of_death_name: string;
  deceased_place_of_death_city: string;
  deceased_place_of_death_state: string;
  deceased_age_at_death: string;
  deceased_date_of_birth: string;
  deceased_gender: string;
  deceased_veteran: boolean;
  // Contact
  contact_first_name: string;
  contact_last_name: string;
  contact_relationship: string;
  contact_phone_primary: string;
  contact_phone_secondary: string;
  contact_email: string;
  send_portal: boolean;
  // Service
  disposition_type: string;
  service_type: string;
  disposition_location: string;
  estimated_service_date: string;
  // Assignment
  assigned_director_id: string;
  referral_source: string;
  notes: string;
}
