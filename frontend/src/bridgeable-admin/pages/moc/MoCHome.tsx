/**
 * Maps of Content — home (Phase 1.2 two-pane).
 *
 * The admin front door, now two-pane (operator's mockup STRUCTURE in §18
 * materials): the persistent Verticals rail (MoCVerticalsRail) BESIDE a
 * content area. The verticals list lives in the rail; the home's content is
 * the overview / select-a-vertical prompt (no vertical is selected at "/").
 * Selecting a vertical navigates to /maps/:vertical (existing route — routing
 * unchanged) where MoCPage renders the same rail beside that vertical's map.
 *
 * A NEW admin surface (NOT a Space — PlatformUser has no preferences). §18
 * surface-base island within the admin shell, so §18 content renders legibly
 * in both modes (the 1.2 contrast fix).
 */

import { Map as MapIcon } from "lucide-react"

import { MoCVerticalsRail } from "@/bridgeable-admin/components/moc/MoCVerticalsRail"
import { EmptyState } from "@/components/ui/empty-state"

export default function MoCHome() {
  return (
    <div
      className="flex min-h-[calc(100vh-7rem)] overflow-hidden rounded-lg border border-border-subtle bg-surface-base"
      data-testid="moc-home"
    >
      <MoCVerticalsRail />
      <div className="flex-1 p-6" data-testid="moc-home-content">
        <h1 className="text-h4 font-semibold text-content-strong">
          Maps of Content
        </h1>
        <p className="mt-1 text-body-sm text-content-muted">
          Artifact-first navigation, one map per vertical.
        </p>
        <div className="mt-10">
          <EmptyState
            variant="quiet"
            icon={MapIcon}
            title="Select a vertical"
            description="Choose a vertical from the rail to open its map — the workflows, focuses, widgets, and documents that run it."
          />
        </div>
      </div>
    </div>
  )
}
