/**
 * The shell an area-limited user gets: no sidebar, the note as home, and the
 * sphere as the entrance.
 *
 * ⚠️ **THE SPLIT IS BY AREA-LIMITATION, NOT BY ROLE.** James's ruling 3 of
 * 2026-11-17: `limited_to_areas` not NULL → this shell; NULL → the current one.
 * A role name would have to be enumerated and would drift the moment a second
 * limited role exists; the area limit is the property that makes the old chrome
 * wrong, because a sidebar whose every item is refused is worse than no sidebar.
 *
 * ⚠️ **TEMPORARY, WITH A STATED EXIT.** Ruling 3 again: everyone moves to this
 * shell when the new home build lands, at which point the split — and this
 * file's reason for existing separately from `app-layout.tsx` — is deleted. It
 * is recorded in STATE with that exit condition so it does not quietly become
 * the permanent arrangement.
 *
 * ⚠️ **WHAT IS DELIBERATELY ABSENT, AND WHY EACH ABSENCE IS A DECISION.**
 *   Sidebar        every entry is nav into areas she cannot reach.
 *   DotNav         spaces are a power-operator surface; she has one job.
 *   MobileTabBar   same, and it would be the only chrome on a phone.
 *   command bar    ruling 2: she gets Opas's command line, never the platform
 *                  bar — which would answer with orders, invoices and contacts.
 *   notifications  not yet composed per area. Showing it would surface other
 *                  areas' work, which is the leak this whole arc is closing.
 *
 * ⚠️ **WHAT IS PRESENT IS THE MINIMUM FOR SOMEONE TO WORK AND TO LEAVE.** Her
 * name, so she can tell whose session this is; the tenant, because a licensee
 * network means more than one; and Sign Out, because a shell with no way out
 * is a trap. Everything else arrives through the note and through Opas.
 */
import { Outlet, useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { useAuth } from "@/contexts/auth-context"

export function LimitedShell() {
  const { user, company, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate("/login")
  }

  return (
    <div
      data-testid="limited-shell"
      className="flex h-screen flex-col bg-surface-base font-sans text-content-base"
    >
      <header
        data-testid="limited-shell-topbar"
        className="flex h-12 flex-none items-center justify-between border-b border-border-subtle bg-surface-elevated px-4"
      >
        <span className="text-body-sm text-content-muted">
          {company?.name ?? ""}
        </span>
        <div className="flex items-center gap-3">
          <span data-testid="limited-shell-who" className="text-body-sm text-content-muted">
            {user?.first_name} {user?.last_name}
          </span>
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            Sign Out
          </Button>
        </div>
      </header>
      {/* ⚠️ NO `p-6`. The note sets its own measure — `--max-w-reading` — and a
          shell padding would fight it. The old shell pads because its pages are
          dashboards; this one has one page. */}
      <main data-testid="limited-shell-main" className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
