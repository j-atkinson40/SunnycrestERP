// legacy-settings.tsx — Legacy Studio settings shell with tabs
// Route: /legacy/settings

import { useState } from "react"
import { useSearchParams } from "react-router-dom"
import LegacyEmailSettingsTab from "./settings/email"
import LegacyDeliverySettingsTab from "./settings/delivery"
import LegacyGeneralSettingsTab from "./settings/general"

const TABS = [
  { key: "email", label: "✉ Email", component: LegacyEmailSettingsTab },
  { key: "delivery", label: "☁ Delivery", component: LegacyDeliverySettingsTab },
  { key: "general", label: "⚙ General", component: LegacyGeneralSettingsTab },
]

export default function LegacySettingsPage() {
  const [searchParams] = useSearchParams()
  const initialTab = searchParams.get("tab") || "email"
  const [activeTab, setActiveTab] = useState(initialTab)

  const ActiveComponent = TABS.find((t) => t.key === activeTab)?.component || LegacyEmailSettingsTab

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Legacy Settings</h1>
        <p className="text-sm text-gray-500 mt-1">Configure email, delivery, and general settings for Legacy Studio.</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
              activeTab === tab.key
                ? "border-gray-900 text-gray-900"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Active tab content */}
      <ActiveComponent />
    </div>
  )
}
