/**
 * Is this Focus read-only for the current user?
 *
 * ⚠️ ONE COMPUTATION, CONSUMED BY EVERY CORE. A core that decided this for
 * itself would drift, and the drift is invisible: a core that forgot the check
 * looks exactly like a core whose user happens to have the permission.
 *
 * Mirrors `PermissionGate`'s admin short-circuit deliberately — two places that
 * answer "may this user do X" and disagree about admins is worse than either
 * answer.
 *
 * ⚠️ NULL-SAFE ON AUTH, AND THAT WAS A DEFECT BEFORE IT WAS A DESIGN.
 * The first version called `useAuth`, which THROWS outside a provider. That
 * made a Focus unrenderable outside an auth tree and broke 12 tests across
 * `Focus.test.tsx` and `ReturnPill.test.tsx` — surfaces that legitimately
 * render without one, as `usePeekOptional` already anticipated for peek.
 *
 * With no auth context the gate CANNOT BE EVALUATED, and this returns false —
 * not read-only. Both answers assert something unknown; this one preserves the
 * behaviour that existed before the capability shipped, and the server remains
 * the enforcement boundary. ⚠️ THIS IS AN AFFORDANCE, NOT A SECURITY CONTROL:
 * it decides whether a control is offered, never whether an action is allowed.
 */

import { useAuthOptional } from "@/contexts/auth-context"
import type { FocusConfig } from "@/contexts/focus-registry"

export function useFocusReadOnly(config: FocusConfig | null): boolean {
  const auth = useAuthOptional()

  // A Focus that declares no edit gate is not read-only. See the field's
  // docstring: absence means "no gate declared", not "deny".
  if (!config?.editPermission) return false
  if (!auth) return false
  if (auth.isAdmin) return false
  return !auth.hasPermission(config.editPermission)
}
