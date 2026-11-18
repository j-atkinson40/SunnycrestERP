/**
 * Which shell a tenant user gets.
 *
 * ⚠️ **ONE DECISION, IN ONE PLACE, SO IT CANNOT DISAGREE WITH ITSELF.** The
 * split is James's ruling 3 of 2026-11-17 — `limited_to_areas` not NULL → the
 * new shell — and the predicate is `isAreaLimited`, shared with the Opas gate.
 * Two call sites each writing `limitedToAreas != null` would be two chances to
 * write `if (limitedToAreas)` instead, which puts the limited-to-nothing role
 * in the wrong shell.
 *
 * ⚠️ **BOTH SHELLS RENDER THE SAME `<Outlet/>`, SO ROUTING IS UNTOUCHED.** This
 * swaps chrome, not routes: every path an area-limited user can reach is still
 * gated by the same `ProtectedRoute` permissions and, on the server, by the
 * same area guard. A shell is not a permission, and nothing here should ever be
 * mistaken for one.
 *
 * ⚠️ **TEMPORARY.** Ruling 3's exit condition: everyone moves to the new shell
 * when the new home build lands, and then this file and the old `AppLayout`
 * collapse into one. Recorded in STATE.
 */
import { useAuth } from "@/contexts/auth-context"
import { isAreaLimited } from "@/components/opas/may-use-opas"
import { AppLayout } from "./app-layout"
import { LimitedShell } from "./limited-shell"

export function TenantShell() {
  const { limitedToAreas } = useAuth()
  return isAreaLimited(limitedToAreas) ? <LimitedShell /> : <AppLayout />
}
