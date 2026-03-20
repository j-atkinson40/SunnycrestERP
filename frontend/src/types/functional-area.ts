export interface FunctionalArea {
  id: string;
  area_key: string;
  display_name: string;
  description: string | null;
  icon: string | null;
  required_extension: string | null;
  sort_order: number;
}

export interface FunctionalAreasResponse {
  areas: FunctionalArea[];
}
