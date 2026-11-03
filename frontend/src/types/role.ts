export interface RoleResponse {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  is_system: boolean;
  is_active: boolean;
  permission_keys: string[];
  /**
   * Area keys this role is limited to. `null` = not limited.
   *
   * ⚠️ Rendered wherever a role is listed, deliberately. A limited role and an
   * unlimited one must never look the same: a limited one is refused every
   * endpoint outside its areas on the SERVER, so assigning one believing it is
   * ordinary silently cuts a person off from the rest of the app.
   */
  limited_to_areas: string[] | null;
  created_at: string;
}

export interface RoleCreate {
  name: string;
  slug: string;
  description?: string;
  permission_keys: string[];
  /** Omit or send null for an unlimited role. */
  limited_to_areas?: string[] | null;
}

export interface RoleUpdate {
  name?: string;
  description?: string;
  is_active?: boolean;
  /**
   * ⚠️ OMITTING THIS LEAVES THE AREAS ALONE; SENDING `null` MAKES THE ROLE
   * UNLIMITED. The server distinguishes the two with `model_fields_set`, so
   * don't "helpfully" default it — a PATCH that always sent null would clear
   * every limit on every rename.
   */
  limited_to_areas?: string[] | null;
}

export interface PermissionRegistry {
  [module: string]: string[];
}

export interface PermissionOverride {
  permission_key: string;
  granted: boolean;
}

/** `GET /roles/areas` — the single producer of the area vocabulary. */
export interface KnownAreasResponse {
  areas: string[];
  /** Path prefixes every signed-in user reaches regardless of area. */
  always_available: string[];
}
