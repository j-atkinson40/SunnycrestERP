/**
 * Billing page — two tabs: Invoices (existing) and Statements (new).
 */

import { useState, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import { cn } from "@/lib/utils"
import { StatementsTab } from "./statements-tab"
import { ReceivedStatementsList } from "./received-statements"
import apiClient from "@/lib/api-client"

const TABS = [
  { key: "invoices", label: "Invoices" },
  { key: "statements", label: "Statements" },
  { key: "received", label: "Received" },
] as const

type TabKey = (typeof TABS)[number]["key"]

export default function BillingPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialTab = (searchParams.get("tab") as TabKey) || "invoices"
  const [activeTab, setActiveTab] = useState<TabKey>(initialTab)
  const [receivedCount, setReceivedCount] = useState(0)

  useEffect(() => {
    apiClient
      .get("/statements/received/unread-count")
      .then((res) => setReceivedCount(res.data.count))
      .catch(() => {})
  }, [])

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
                "pb-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5",
                activeTab === tab.key
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
              )}
            >
              {tab.label}
              {tab.key === "received" && receivedCount > 0 && (
                <span className="inline-flex items-center justify-center h-5 min-w-5 rounded-full bg-blue-600 text-white text-xs px-1.5">
                  {receivedCount}
                </span>
              )}
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

      {activeTab === "received" && <ReceivedStatementsList />}
    </div>
  )
}
