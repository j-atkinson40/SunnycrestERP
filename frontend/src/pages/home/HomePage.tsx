/**
 * HomePage — Phase W-4a Commit 5.
 *
 * The /home route renders the Home Space's PulseSurface. Per
 * BRIDGEABLE_MASTER §3.26.1.1, Home Space is "always present,
 * always first in navigation, contains the Pulse." Phase W-4a
 * Commit 1 seeded the Home system space (gate-less, leftmost in
 * DotNav, default_home_route="/home"); this page is the surface
 * that DotNav-Home-click navigates to.
 *
 * No permission gate — every authenticated tenant user can reach
 * /home. The Pulse composition itself is per-user-scoped on the
 * server (composition_engine.compose_for_user enforces tenant +
 * user isolation).
 *
 * Coexists with /dashboard during the Phase W-4a → W-5 transition.
 * Dashboard retires post-W-5 once My Stuff + Custom Spaces ship.
 */

import { PulseSurface } from "@/components/spaces/PulseSurface"


export default function HomePage() {
  return <PulseSurface />
}
