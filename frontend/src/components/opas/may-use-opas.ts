/**
 * Who may see the sphere.
 *
 * ⚠️ **ADMIN-ONLY UNTIL 2026-11-18.** James's ruling 2 of 2026-11-17: "Susan
 * gets Opas's own command line, never the platform command bar." Her role is
 * area-limited, she has no sidebar in the new shell, and the sphere is the only
 * entrance she has — so an admin-only gate would leave her with no way to ask
 * for anything.
 *
 * ⚠️ **`!= null`, NOT TRUTHINESS, AND THE DISTINCTION IS THE WHOLE FUNCTION.**
 * `limited_to_areas` has three states and two of them are falsey:
 *
 *     null / undefined   no limit was ever set  → unlimited → NOT the new shell
 *     []                 limited to NOTHING     → IS the new shell
 *     ["payroll"]        limited to these       → IS the new shell
 *
 * `if (limitedToAreas)` would put the `[]` role — a real, deliberate state —
 * into the admin shell, which is the opposite of what ruling 3 says. The model
 * comment on `Role.limited_to_areas` has warned about this since r221 and
 * `allowed_area_grants` exists on the server for the same reason.
 *
 * `undefined` is treated as unlimited deliberately: it is what `/auth/me`
 * returns before it has loaded, and a shell flip on a half-loaded profile would
 * show the wrong chrome and then swap it.
 */
export function isAreaLimited(limitedToAreas: string[] | null | undefined): boolean {
  return limitedToAreas != null
}

/** May this user see the sphere at all? */
export function mayUseOpas(
  isAdmin: boolean,
  limitedToAreas: string[] | null | undefined,
): boolean {
  return isAdmin || isAreaLimited(limitedToAreas)
}
