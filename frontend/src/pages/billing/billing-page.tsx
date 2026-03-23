/**
 * Billing page — two tabs: Invoices (existing) and Statements (new).
 */

import { useState } from "react"
import { useSearchParams } from "react-router-dom"
import { cn } from "@/lib/utils"
import { StatementsTab } from "./statements-tab"

const TABS = [
  { key: "invoices", label: "Invoices" },
  { key: "statements", label: "Statements" },
] as const

type TabKey = (typeof TABS)[number]["key"]

export default function BillingPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialTab = (searchParams.get("tab") as TabKey) || "invoices"
  const [activeTab, setActiveTab] = useState<TabKey>(initialTab)

  const switchTab = (tab: TabKey) => {
    setActiveTab(tab)
    setSearchParams({ tab })
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Billing</h1>
        <p className="text-sm text-gray-500 mt-1">
          Manage invoices and monthly customer statements
        </p>
      </div>

      {/* Tab bar */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex gap-6">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => switchTab(tab.key)}
              className={cn(
                "pb-3 text-sm font-medium border-b-2 transition-colors",
                activeTab === tab.key
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              )}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === "invoices" && (
        <div>
          <p className="text-sm text-gray-500">
            Invoice management is available from the existing invoice views.
          </p>
        </div>
      )}

      {activeTab === "statements" && <StatementsTab />}
    </div>
  )
}
