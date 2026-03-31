// safety-log.tsx
// Routes: /console/operations/incident  (?type=incident)
//         /console/operations/observation (?type=observation)
// Uses ?type= search param to set the active tab; defaults to 'incident'.
//
// NOTE: Observations are submitted to POST /safety/incidents with type='observation'
// since no separate /safety/observations endpoint exists yet.

import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ChevronLeft, CheckCircle } from 'lucide-react'
import { toast } from 'sonner'
import apiClient from '@/lib/api-client'
import offlineQueue from '@/services/offline-queue'
import VoiceInputButton from '@/components/mobile/voice-input-button'

// ─── Types ────────────────────────────────────────────────────────────────────

type ActiveTab = 'incident' | 'observation'
type Step = 'form' | 'success'

type IncidentType =
  | 'near_miss'
  | 'first_aid'
  | 'recordable'
  | 'property_damage'
  | 'other'

type ObservationType = 'positive' | 'concern' | 'near_miss'

interface PersonRef {
  name: string
  matched_id: string | null
}

interface IncidentState {
  incident_type: IncidentType
  location: string
  people_involved: PersonRef[]
  description: string
  immediate_actions: string
}

interface ObservationState {
  observation_type: ObservationType | null
  location: string
  description: string
}

interface Employee {
  id: string
  name: string
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function SafetyLog() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const typeParam = searchParams.get('type') as ActiveTab | null
  const [activeTab, setActiveTab] = useState<ActiveTab>(
    typeParam === 'observation' ? 'observation' : 'incident',
  )

  const [step, setStep] = useState<Step>('form')
  const [employees, setEmployees] = useState<Employee[]>([])
  const [isOffline, setIsOffline] = useState(!navigator.onLine)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Incident form state
  const [incident, setIncident] = useState<IncidentState>({
    incident_type: 'near_miss',
    location: '',
    people_involved: [],
    description: '',
    immediate_actions: '',
  })

  // Observation form state
  const [observation, setObservation] = useState<ObservationState>({
    observation_type: null,
    location: '',
    description: '',
  })

  // People picker
  const [showPeoplePicker, setShowPeoplePicker] = useState(false)

  // Load employees on mount
  useEffect(() => {
    apiClient
      .get<{ id: string; full_name?: string; name?: string }[]>('/employees/profiles')
      .then((r) => {
        setEmployees(
          r.data.map((e) => ({
            id: e.id,
            name: e.full_name ?? e.name ?? e.id,
          })),
        )
      })
      .catch(() => {
        // Employees are optional context for voice — fail silently
      })
  }, [])

  // Track online status
  useEffect(() => {
    const onOnline = () => setIsOffline(false)
    const onOffline = () => setIsOffline(true)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [])

  // Auto-navigate after success
  useEffect(() => {
    if (step === 'success') {
      const t = setTimeout(() => navigate('/console/operations'), 3000)
      return () => clearTimeout(t)
    }
  }, [step, navigate])

  // Sync tab change to search params
  function switchTab(tab: ActiveTab) {
    setActiveTab(tab)
    setSearchParams({ type: tab }, { replace: true })
  }

  // ─── Voice result handler ──────────────────────────────────────────────────

  function handleVoiceResult(raw: Record<string, unknown>) {
    if (activeTab === 'incident') {
      setIncident((prev) => ({
        ...prev,
        incident_type:
          (raw.incident_type as IncidentType | undefined) ?? prev.incident_type,
        location: (raw.location as string | undefined) ?? prev.location,
        description: (raw.description as string | undefined) ?? prev.description,
        immediate_actions:
          (raw.immediate_actions as string | undefined) ?? prev.immediate_actions,
        people_involved: (raw.people_involved as PersonRef[] | undefined) ?? prev.people_involved,
      }))
    } else {
      setObservation((prev) => ({
        ...prev,
        observation_type:
          (raw.observation_type as ObservationType | undefined) ??
          prev.observation_type,
        location: (raw.location as string | undefined) ?? prev.location,
        description: (raw.description as string | undefined) ?? prev.description,
      }))
    }
  }

  // ─── People helpers ────────────────────────────────────────────────────────

  function addPerson(employeeId: string) {
    const emp = employees.find((e) => e.id === employeeId)
    if (!emp) return
    if (incident.people_involved.some((p) => p.matched_id === employeeId)) return
    setIncident((prev) => ({
      ...prev,
      people_involved: [
        ...prev.people_involved,
        { name: emp.name, matched_id: emp.id },
      ],
    }))
    setShowPeoplePicker(false)
  }

  function removePerson(matchedId: string | null, name: string) {
    setIncident((prev) => ({
      ...prev,
      people_involved: prev.people_involved.filter(
        (p) => !(p.matched_id === matchedId && p.name === name),
      ),
    }))
  }

  // ─── Submit ────────────────────────────────────────────────────────────────

  async function handleSubmit() {
    let payload: Record<string, unknown>
    let queueType: 'incident' | 'safety_observation'

    if (activeTab === 'incident') {
      if (!incident.description.trim()) {
        toast.error('Please describe what happened')
        return
      }
      payload = {
        type: 'incident',
        incident_type: incident.incident_type,
        location: incident.location,
        people_involved: incident.people_involved,
        description: incident.description,
        immediate_actions: incident.immediate_actions,
        occurred_at: new Date().toISOString(),
      }
      queueType = 'incident'
    } else {
      if (!observation.observation_type) {
        toast.error('Please select an observation type')
        return
      }
      if (!observation.description.trim()) {
        toast.error('Please describe the observation')
        return
      }
      // POST to /safety/incidents with type='observation' (no separate observations endpoint)
      payload = {
        type: 'observation',
        observation_type: observation.observation_type,
        location: observation.location,
        description: observation.description,
        occurred_at: new Date().toISOString(),
      }
      queueType = 'safety_observation'
    }

    setIsSubmitting(true)
    try {
      if (navigator.onLine) {
        await apiClient.post('/safety/incidents', payload)
      } else {
        await offlineQueue.enqueue(queueType, payload)
      }
      setStep('success')
    } catch {
      toast.error('Failed to submit — saved offline')
      await offlineQueue.enqueue(queueType, payload)
      setStep('success')
    } finally {
      setIsSubmitting(false)
    }
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  const incidentTypeOptions: { value: IncidentType; label: string }[] = [
    { value: 'near_miss', label: 'Near Miss' },
    { value: 'first_aid', label: 'First Aid' },
    { value: 'recordable', label: 'Recordable' },
    { value: 'property_damage', label: 'Property Damage' },
    { value: 'other', label: 'Other' },
  ]

  const observationTiles: {
    value: ObservationType
    label: string
    icon: string
    color: string
  }[] = [
    { value: 'positive', label: 'Positive', icon: '✓', color: 'green' },
    { value: 'concern', label: 'Concern', icon: '⚠', color: 'amber' },
    { value: 'near_miss', label: 'Near Miss', icon: '⚡', color: 'red' },
  ]

  return (
    <div className="mobile-page-container">
      <div className="max-w-lg mx-auto min-h-screen flex flex-col">

        {/* SUCCESS */}
        {step === 'success' && (
          <div className="flex-1 flex flex-col items-center justify-center bg-green-50 px-6">
            <CheckCircle className="h-24 w-24 text-green-500 mx-auto" />
            <h2 className="text-3xl font-bold text-center text-green-800 mt-4">
              Logged
            </h2>
            <p className="text-center text-green-700 mt-2">
              {activeTab === 'incident' ? 'Incident' : 'Observation'} recorded
            </p>
            {isOffline && (
              <p className="text-amber-600 text-center text-sm mt-2">
                Queued for sync
              </p>
            )}
          </div>
        )}

        {/* FORM */}
        {step === 'form' && (
          <>
            {/* Header */}
            <div className="flex items-center gap-3 px-4 pt-safe pt-4 pb-4 border-b border-gray-100">
              <button
                onClick={() => navigate('/console/operations')}
                className="p-2 -ml-2 rounded-lg active:bg-gray-100"
                aria-label="Back"
              >
                <ChevronLeft className="h-6 w-6 text-gray-600" />
              </button>
              <h1 className="text-xl font-bold">Safety Log</h1>
            </div>

            {/* Tabs */}
            <div className="flex px-4 pt-3 pb-0 gap-2">
              <button
                onClick={() => switchTab('incident')}
                className={`flex-1 h-[52px] rounded-xl text-base font-semibold transition-colors ${
                  activeTab === 'incident'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                ⚠ Incident
              </button>
              <button
                onClick={() => switchTab('observation')}
                className={`flex-1 h-[52px] rounded-xl text-base font-semibold transition-colors ${
                  activeTab === 'observation'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                👁 Observation
              </button>
            </div>

            {/* Scrollable form body */}
            <div className="flex-1 overflow-y-auto px-4 py-5 space-y-5">

              {/* Voice input — shared */}
              <div>
                <p className="text-center text-gray-600 mb-6">
                  What happened? Tap and tell me.
                </p>
                <div className="flex justify-center mb-6">
                  <VoiceInputButton
                    context={activeTab === 'incident' ? 'incident' : 'safety_observation'}
                    onResult={handleVoiceResult}
                    availableEmployees={employees}
                  />
                </div>
              </div>

              {/* ── INCIDENT FIELDS ─────────────────────────────────────── */}
              {activeTab === 'incident' && (
                <>
                  {/* Incident type */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Type
                    </label>
                    <select
                      value={incident.incident_type}
                      onChange={(e) =>
                        setIncident((prev) => ({
                          ...prev,
                          incident_type: e.target.value as IncidentType,
                        }))
                      }
                      className="w-full border border-gray-300 rounded-xl p-3 text-base bg-white"
                      style={{ height: 56 }}
                    >
                      {incidentTypeOptions.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Time — read-only */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Time
                    </label>
                    <div className="w-full border border-gray-200 rounded-xl px-3 py-3 text-base bg-gray-50 text-gray-600 flex items-center justify-between" style={{ height: 52 }}>
                      <span>Now</span>
                      <span className="text-xs text-gray-400">
                        {new Date().toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                  </div>

                  {/* Location */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Location
                    </label>
                    <input
                      type="text"
                      value={incident.location}
                      onChange={(e) =>
                        setIncident((prev) => ({
                          ...prev,
                          location: e.target.value,
                        }))
                      }
                      placeholder="e.g. Loading dock, Casting floor"
                      className="w-full border border-gray-300 rounded-xl px-3 text-base bg-white"
                      style={{ height: 52, fontSize: 16 }}
                    />
                  </div>

                  {/* People involved */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      People Involved
                    </label>
                    <div className="flex flex-wrap gap-2 mb-2">
                      {incident.people_involved.map((person) => (
                        <span
                          key={`${person.matched_id}-${person.name}`}
                          className="inline-flex items-center gap-1 bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm"
                        >
                          {person.name}
                          <button
                            onClick={() => removePerson(person.matched_id, person.name)}
                            className="ml-1 text-blue-500 hover:text-blue-700 leading-none"
                            aria-label={`Remove ${person.name}`}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    {showPeoplePicker ? (
                      <select
                        className="w-full border border-gray-300 rounded-xl p-3 text-base bg-white"
                        defaultValue=""
                        onChange={(e) => {
                          if (e.target.value) addPerson(e.target.value)
                        }}
                      >
                        <option value="">Select employee…</option>
                        {employees.map((emp) => (
                          <option key={emp.id} value={emp.id}>
                            {emp.name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <button
                        onClick={() => setShowPeoplePicker(true)}
                        className="text-sm text-blue-600 underline"
                      >
                        + Add person
                      </button>
                    )}
                  </div>

                  {/* Description */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Description
                    </label>
                    <textarea
                      value={incident.description}
                      onChange={(e) =>
                        setIncident((prev) => ({
                          ...prev,
                          description: e.target.value,
                        }))
                      }
                      placeholder="Describe what happened…"
                      className="w-full border border-gray-300 rounded-xl p-3 bg-white resize-none"
                      style={{ minHeight: 100, fontSize: 16 }}
                    />
                  </div>

                  {/* Immediate actions */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Immediate Actions Taken
                    </label>
                    <textarea
                      value={incident.immediate_actions}
                      onChange={(e) =>
                        setIncident((prev) => ({
                          ...prev,
                          immediate_actions: e.target.value,
                        }))
                      }
                      placeholder="What was done immediately after?"
                      className="w-full border border-gray-300 rounded-xl p-3 bg-white resize-none"
                      style={{ minHeight: 80, fontSize: 16 }}
                    />
                  </div>
                </>
              )}

              {/* ── OBSERVATION FIELDS ──────────────────────────────────── */}
              {activeTab === 'observation' && (
                <>
                  {/* Type tiles */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Type
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      {observationTiles.map((tile) => {
                        const selected = observation.observation_type === tile.value
                        const colorMap: Record<string, string> = {
                          green: selected
                            ? 'border-green-500 bg-green-50 text-green-800'
                            : 'border-gray-200 text-gray-600',
                          amber: selected
                            ? 'border-amber-500 bg-amber-50 text-amber-800'
                            : 'border-gray-200 text-gray-600',
                          red: selected
                            ? 'border-red-500 bg-red-50 text-red-800'
                            : 'border-gray-200 text-gray-600',
                        }
                        return (
                          <button
                            key={tile.value}
                            onClick={() =>
                              setObservation((prev) => ({
                                ...prev,
                                observation_type: tile.value,
                              }))
                            }
                            className={`flex flex-col items-center justify-center h-20 border-2 rounded-xl transition-colors ${colorMap[tile.color]}`}
                          >
                            <span className="text-xl mb-1">{tile.icon}</span>
                            <span className="text-xs font-semibold">{tile.label}</span>
                          </button>
                        )
                      })}
                    </div>
                  </div>

                  {/* Location */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Location
                    </label>
                    <input
                      type="text"
                      value={observation.location}
                      onChange={(e) =>
                        setObservation((prev) => ({
                          ...prev,
                          location: e.target.value,
                        }))
                      }
                      placeholder="e.g. Loading dock, Yard"
                      className="w-full border border-gray-300 rounded-xl px-3 bg-white"
                      style={{ height: 52, fontSize: 16 }}
                    />
                  </div>

                  {/* Description */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Description
                    </label>
                    <textarea
                      value={observation.description}
                      onChange={(e) =>
                        setObservation((prev) => ({
                          ...prev,
                          description: e.target.value,
                        }))
                      }
                      placeholder="Describe what you observed…"
                      className="w-full border border-gray-300 rounded-xl p-3 bg-white resize-none"
                      style={{ minHeight: 100, fontSize: 16 }}
                    />
                  </div>
                </>
              )}
            </div>

            {/* Submit button — sticky footer */}
            <div className="px-4 pb-safe pb-6 pt-3 border-t border-gray-100 bg-white">
              <button
                onClick={handleSubmit}
                disabled={isSubmitting}
                className={`mobile-primary-btn w-full text-white disabled:opacity-50 disabled:cursor-not-allowed ${
                  activeTab === 'incident' ? 'bg-red-600' : 'bg-blue-600'
                }`}
              >
                {isSubmitting
                  ? 'Submitting…'
                  : activeTab === 'incident'
                    ? 'Submit Incident'
                    : 'Submit Observation'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
