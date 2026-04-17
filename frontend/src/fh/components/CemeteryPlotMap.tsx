import { useEffect, useState } from "react"
import { fhApi } from "../lib/fh-api"

export interface PlotData {
  id: string
  section: string | null
  row: string | null
  number: string | null
  plot_label: string
  plot_type: string
  status: "available" | "reserved" | "sold" | "unavailable"
  map_x: number | null
  map_y: number | null
  map_width: number | null
  map_height: number | null
  price: number | null
  opening_closing_fee: number | null
}

interface Props {
  cemeteryCompanyId: string
  mode?: "browse" | "select" | "manage"
  onPlotSelected?: (plot: PlotData) => void
  reservedPlotId?: string
  caseId?: string
}

const STATUS_COLORS: Record<string, string> = {
  available: "#4ade80",
  reserved: "#fbbf24",
  sold: "#9ca3af",
  unavailable: "#f87171",
}

export function CemeteryPlotMap({
  cemeteryCompanyId,
  mode = "select",
  onPlotSelected,
  reservedPlotId,
}: Props) {
  const [plots, setPlots] = useState<PlotData[]>([])
  const [counts, setCounts] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(true)
  const [selectedPlot, setSelectedPlot] = useState<PlotData | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [sectionFilter, setSectionFilter] = useState<string>("all")
  const [hoverPlot, setHoverPlot] = useState<PlotData | null>(null)

  useEffect(() => {
    setLoading(true)
    fhApi
      .cemeteryMap(cemeteryCompanyId)
      .then((data: any) => {
        setPlots(data.plots || [])
        setCounts(data.counts || {})
      })
      .catch(() => {
        setPlots([])
        setCounts({})
      })
      .finally(() => setLoading(false))
  }, [cemeteryCompanyId])

  const sections = Array.from(new Set(plots.map((p) => p.section).filter(Boolean))) as string[]

  const visiblePlots = plots.filter((p) => {
    if (statusFilter !== "all" && p.status !== statusFilter) return false
    if (sectionFilter !== "all" && p.section !== sectionFilter) return false
    return true
  })

  if (loading) {
    return <div className="text-center text-slate-400 py-8">Loading map…</div>
  }

  if (plots.length === 0) {
    return (
      <div className="bg-slate-50 border border-slate-200 rounded p-8 text-center text-slate-500">
        No plots configured for this cemetery yet.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex flex-wrap gap-2 text-sm">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-2 py-1 border border-slate-200 rounded text-xs"
        >
          <option value="all">All statuses</option>
          <option value="available">Available only</option>
          <option value="reserved">Reserved</option>
          <option value="sold">Sold</option>
          <option value="unavailable">Unavailable</option>
        </select>
        {sections.length > 0 && (
          <select
            value={sectionFilter}
            onChange={(e) => setSectionFilter(e.target.value)}
            className="px-2 py-1 border border-slate-200 rounded text-xs"
          >
            <option value="all">All sections</option>
            {sections.map((s) => (
              <option key={s} value={s}>
                Section {s}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="flex gap-4">
        {/* Map */}
        <div className="flex-1 bg-slate-100 rounded overflow-hidden border border-slate-200" style={{ minHeight: 400 }}>
          <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet" className="w-full h-full" style={{ minHeight: 400 }}>
            {visiblePlots.map((p) => {
              const isHover = hoverPlot?.id === p.id
              const isSelected = selectedPlot?.id === p.id || reservedPlotId === p.id
              const fill = isSelected ? "#60a5fa" : STATUS_COLORS[p.status] || "#d1d5db"
              return (
                <rect
                  key={p.id}
                  x={p.map_x ?? 0}
                  y={p.map_y ?? 0}
                  width={Math.max(p.map_width ?? 2, 1)}
                  height={Math.max(p.map_height ?? 2, 1)}
                  fill={fill}
                  stroke={isHover || isSelected ? "#1e293b" : "#fff"}
                  strokeWidth={isHover || isSelected ? 0.4 : 0.15}
                  style={{ cursor: mode === "select" && p.status === "available" ? "pointer" : "default" }}
                  onMouseEnter={() => setHoverPlot(p)}
                  onMouseLeave={() => setHoverPlot(null)}
                  onClick={() => {
                    if (mode === "select" && p.status === "available") {
                      setSelectedPlot(p)
                      onPlotSelected?.(p)
                    } else if (mode === "manage") {
                      setSelectedPlot(p)
                      onPlotSelected?.(p)
                    }
                  }}
                />
              )
            })}
          </svg>
        </div>

        {/* Right detail panel */}
        <div className="w-72 flex-shrink-0 space-y-3">
          {hoverPlot && !selectedPlot && (
            <div className="bg-white border border-slate-200 rounded p-3 text-sm">
              <div className="font-medium">{hoverPlot.plot_label}</div>
              <div className="text-xs text-slate-500 mt-1">{hoverPlot.plot_type.replace(/_/g, " ")}</div>
              {hoverPlot.price && (
                <div className="text-xs text-slate-700 mt-1">${hoverPlot.price.toLocaleString()}</div>
              )}
            </div>
          )}
          {selectedPlot && (
            <div className="bg-white border-2 border-blue-400 rounded p-3 text-sm">
              <div className="text-xs text-slate-500 uppercase">Selected</div>
              <div className="font-medium text-base mt-1">{selectedPlot.plot_label}</div>
              <div className="text-xs text-slate-600 mt-1">
                Type: {selectedPlot.plot_type.replace(/_/g, " ")}
              </div>
              <div className="text-xs text-slate-600">Status: {selectedPlot.status}</div>
              {selectedPlot.price && (
                <div className="text-sm mt-2">
                  Price: <span className="font-semibold">${selectedPlot.price.toLocaleString()}</span>
                </div>
              )}
              {selectedPlot.opening_closing_fee && (
                <div className="text-xs text-slate-600">
                  Opening/closing: ${selectedPlot.opening_closing_fee.toLocaleString()}
                </div>
              )}
              {selectedPlot.price && selectedPlot.opening_closing_fee && (
                <div className="text-sm mt-1 font-medium">
                  Total: ${(selectedPlot.price + selectedPlot.opening_closing_fee).toLocaleString()}
                </div>
              )}
            </div>
          )}

          {/* Legend */}
          <div className="bg-white border border-slate-200 rounded p-3 text-xs">
            <div className="font-semibold text-slate-700 mb-2">Legend</div>
            {Object.entries(STATUS_COLORS).map(([status, color]) => (
              <div key={status} className="flex items-center gap-2 mb-1">
                <span className="h-3 w-3 rounded" style={{ background: color }} />
                <span className="capitalize">{status}</span>
                {counts[status] && (
                  <span className="text-slate-400 ml-auto">{counts[status]}</span>
                )}
              </div>
            ))}
            <div className="flex items-center gap-2 mt-1">
              <span className="h-3 w-3 rounded" style={{ background: "#60a5fa" }} />
              <span>Selected</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
