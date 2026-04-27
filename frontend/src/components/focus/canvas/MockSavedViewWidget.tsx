/**
 * MockSavedViewWidget — placeholder widget used ONLY in Phase A
 * Session 3 to verify the canvas slot contract end-to-end.
 *
 * Replaced by the real pin system in Session 5 (saved + context-aware
 * + system-suggested pins rendered by Intelligence backbone + Vault
 * view machinery). This file should be deleted when the pin system
 * lands.
 */

import { cn } from "@/lib/utils"


const MOCK_ROWS = [
  { name: "Johnson family", status: "Active", date: "Apr 18" },
  { name: "Chen family", status: "Pending", date: "Apr 17" },
  { name: "Andersen family", status: "Completed", date: "Apr 15" },
  { name: "Martinez family", status: "Active", date: "Apr 14" },
  { name: "Nakamura family", status: "Pending", date: "Apr 12" },
]


const STATUS_TONE: Record<string, string> = {
  Active: "bg-status-info-muted text-status-info",
  Pending: "bg-status-warning-muted text-status-warning",
  Completed: "bg-status-success-muted text-status-success",
}


export function MockSavedViewWidget() {
  return (
    <div className="flex h-full flex-col bg-surface-elevated">
      <div className="border-b border-border-subtle px-3 py-2">
        <p className="text-micro uppercase tracking-wider text-content-muted">
          Saved view · placeholder
        </p>
        <h3 className="text-body-sm font-medium text-content-strong">
          Recent Cases
        </h3>
      </div>
      <div className="flex-1 overflow-auto">
        <table className="w-full border-collapse font-sans text-body-sm">
          <tbody>
            {MOCK_ROWS.map((row) => (
              <tr
                key={row.name}
                className="border-b border-border-subtle/60 last:border-b-0"
              >
                <td className="px-3 py-2 text-content-base">{row.name}</td>
                <td className="px-2 py-2">
                  <span
                    className={cn(
                      "rounded-sm px-1.5 py-0.5 text-micro font-medium",
                      STATUS_TONE[row.status] ?? "",
                    )}
                  >
                    {row.status}
                  </span>
                </td>
                <td className="px-3 py-2 text-right font-mono text-micro text-content-muted">
                  {row.date}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
