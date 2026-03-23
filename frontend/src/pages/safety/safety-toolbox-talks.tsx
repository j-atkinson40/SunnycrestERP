import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Plus, Users, Clock, MessageSquare, Lightbulb, Check, X, RefreshCw } from "lucide-react";
import apiClient from "@/lib/api-client";

const CATEGORIES = [
  { value: "safety_procedure", label: "Safety Procedure" },
  { value: "equipment", label: "Equipment" },
  { value: "hazard_awareness", label: "Hazard Awareness" },
  { value: "housekeeping", label: "Housekeeping" },
  { value: "emergency", label: "Emergency" },
  { value: "other", label: "Other" },
];

interface Talk {
  id: string;
  topic_title: string;
  topic_category: string;
  conducted_at: string | null;
  conducted_by_name: string;
  attendee_count: number;
  duration_minutes: number | null;
  description: string | null;
  notes: string | null;
}

interface Employee {
  user_id: string;
  first_name: string;
  last_name: string;
  track: string;
}

interface Suggestion {
  id: string;
  suggestion_date: string;
  topic_title: string;
  topic_category: string;
  trigger_type: string;
  trigger_description: string;
  talking_points: string[] | null;
  talking_points_generated_at: string | null;
  status: string;
}

const TRIGGER_LABELS: Record<string, string> = {
  recent_incident: "Incident Follow-up",
  inspection_failure: "Inspection Finding",
  seasonal: "Seasonal Awareness",
  monthly_training: "Training Reinforcement",
  compliance_gap: "Compliance Gap",
  topic_overdue: "Topic Refresh",
};

export default function SafetyToolboxTalksPage() {
  const [talks, setTalks] = useState<Talk[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [suggestionLoading, setSuggestionLoading] = useState(false);
  const [dismissing, setDismissing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [fromSuggestion, setFromSuggestion] = useState(false);

  // Form state
  const [topicTitle, setTopicTitle] = useState("");
  const [category, setCategory] = useState("safety_procedure");
  const [durationMinutes, setDurationMinutes] = useState("");
  const [description, setDescription] = useState("");
  const [notes, setNotes] = useState("");
  const [selectedAttendees, setSelectedAttendees] = useState<Set<string>>(new Set());
  const [externalAttendees, setExternalAttendees] = useState<string[]>([]);
  const [newExternal, setNewExternal] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [talksRes, empRes, suggRes] = await Promise.all([
        apiClient.get("/safety/toolbox-talks"),
        apiClient.get("/briefings/team-config").catch(() => ({ data: [] })),
        apiClient.get("/safety/toolbox-suggestions/active").catch(() => ({ data: { suggestion: null } })),
      ]);
      setTalks(talksRes.data);
      setEmployees(empRes.data);
      setSuggestion(suggRes.data.suggestion);
    } catch {
      toast.error("Failed to load toolbox talks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleUseSuggestion = () => {
    if (!suggestion) return;
    setTopicTitle(suggestion.topic_title);
    // Map suggestion category to form category
    const catMap: Record<string, string> = {
      incident_followup: "safety_procedure",
      seasonal: "hazard_awareness",
      training_reinforcement: "safety_procedure",
      equipment: "equipment",
      hazard_awareness: "hazard_awareness",
      other: "other",
    };
    setCategory(catMap[suggestion.topic_category] || "safety_procedure");
    setFromSuggestion(true);
    setShowForm(true);
  };

  const handleDismissSuggestion = async () => {
    if (!suggestion) return;
    setDismissing(true);
    try {
      await apiClient.post(`/safety/toolbox-suggestions/${suggestion.id}/dismiss`);
      setSuggestion(null);
      toast.success("Suggestion dismissed");
    } catch {
      toast.error("Failed to dismiss suggestion");
    } finally {
      setDismissing(false);
    }
  };

  const refreshSuggestionTalkingPoints = async () => {
    setSuggestionLoading(true);
    try {
      const res = await apiClient.get("/safety/toolbox-suggestions/active");
      setSuggestion(res.data.suggestion);
    } catch {
      toast.error("Failed to refresh");
    } finally {
      setSuggestionLoading(false);
    }
  };

  const toggleAttendee = (id: string) => {
    setSelectedAttendees((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const addExternal = () => {
    const name = newExternal.trim();
    if (name && !externalAttendees.includes(name)) {
      setExternalAttendees((prev) => [...prev, name]);
      setNewExternal("");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topicTitle.trim()) {
      toast.error("Topic is required");
      return;
    }
    setSubmitting(true);
    try {
      await apiClient.post("/safety/toolbox-talks", {
        topic_title: topicTitle.trim(),
        topic_category: category,
        duration_minutes: durationMinutes ? Number(durationMinutes) : null,
        description: description.trim() || null,
        notes: notes.trim() || null,
        attendees: [...selectedAttendees],
        attendees_external: externalAttendees.length > 0 ? externalAttendees : null,
        generated_from_suggestion_id: fromSuggestion && suggestion ? suggestion.id : null,
      });
      toast.success("Toolbox talk logged");
      setShowForm(false);
      setTopicTitle("");
      setCategory("safety_procedure");
      setDurationMinutes("");
      setDescription("");
      setNotes("");
      setSelectedAttendees(new Set());
      setExternalAttendees([]);
      setFromSuggestion(false);
      fetchData();
    } catch {
      toast.error("Failed to log toolbox talk");
    } finally {
      setSubmitting(false);
    }
  };

  const categoryLabel = (cat: string) =>
    CATEGORIES.find((c) => c.value === cat)?.label ?? cat;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Toolbox Talks</h2>
          <p className="text-sm text-gray-500">
            Log informal safety meetings and crew discussions
          </p>
        </div>
        <Button onClick={() => setShowForm(!showForm)} className="gap-1.5">
          <Plus className="h-4 w-4" />
          Log a Talk
        </Button>
      </div>

      {/* Suggestion card */}
      {suggestion && !showForm && (
        <Card className="border-amber-200 bg-amber-50/50">
          <CardContent className="p-5">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 rounded-full bg-amber-100 p-1.5">
                <Lightbulb className="h-4 w-4 text-amber-600" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="text-sm font-semibold text-gray-900">
                    Suggested Topic This Week
                  </h3>
                  <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                    {TRIGGER_LABELS[suggestion.trigger_type] || suggestion.trigger_type}
                  </span>
                </div>

                <p className="text-base font-medium text-gray-900 mb-2">
                  {suggestion.topic_title}
                </p>

                <p className="text-sm text-gray-600 mb-3">
                  <span className="font-medium text-gray-700">Why this week: </span>
                  {suggestion.trigger_description}
                </p>

                {/* Talking points */}
                {suggestion.talking_points && suggestion.talking_points.length > 0 ? (
                  <div className="mb-4">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                      Talking Points
                    </p>
                    <ul className="space-y-1.5">
                      {suggestion.talking_points.map((point, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                          <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-amber-400 shrink-0" />
                          {point}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : suggestion.talking_points_generated_at === null ? (
                  <div className="mb-4 flex items-center gap-2 text-sm text-gray-500">
                    {suggestionLoading ? (
                      <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="h-3.5 w-3.5" />
                    )}
                    <span>Generating talking points...</span>
                    <button
                      onClick={refreshSuggestionTalkingPoints}
                      className="text-amber-600 hover:text-amber-700 text-xs underline"
                    >
                      Refresh
                    </button>
                  </div>
                ) : (
                  <p className="mb-4 text-sm text-gray-500 italic">
                    Talking points unavailable — use the topic as a starting point for discussion.
                  </p>
                )}

                {/* Actions */}
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={handleUseSuggestion}
                    className="gap-1.5"
                  >
                    <Check className="h-3.5 w-3.5" />
                    Use this topic
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={handleDismissSuggestion}
                    disabled={dismissing}
                    className="gap-1.5 text-gray-500"
                  >
                    <X className="h-3.5 w-3.5" />
                    {dismissing ? "Dismissing..." : "Dismiss"}
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* No active suggestion placeholder */}
      {!suggestion && !showForm && !loading && (
        <Card className="border-gray-100 bg-gray-50/50">
          <CardContent className="p-4 flex items-center gap-3">
            <Lightbulb className="h-4 w-4 text-gray-300" />
            <p className="text-sm text-gray-400">
              No suggestion this week. Log a talk on any topic.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Create form */}
      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Log a Toolbox Talk</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Topic <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={topicTitle}
                    onChange={(e) => setTopicTitle(e.target.value)}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                    placeholder="e.g. Forklift pedestrian safety"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Category
                  </label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Duration (minutes)
                </label>
                <input
                  type="number"
                  value={durationMinutes}
                  onChange={(e) => setDurationMinutes(e.target.value)}
                  className="w-32 rounded-md border border-gray-300 px-3 py-2 text-sm"
                  placeholder="15"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Who attended?
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-48 overflow-y-auto border border-gray-200 rounded-md p-3">
                  {employees.map((emp) => (
                    <label
                      key={emp.user_id}
                      className="flex items-center gap-2 text-sm cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={selectedAttendees.has(emp.user_id)}
                        onChange={() => toggleAttendee(emp.user_id)}
                        className="h-4 w-4 rounded border-gray-300"
                      />
                      {emp.first_name} {emp.last_name}
                    </label>
                  ))}
                </div>
                {/* External attendees */}
                <div className="mt-2 flex items-center gap-2">
                  <input
                    type="text"
                    value={newExternal}
                    onChange={(e) => setNewExternal(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addExternal())}
                    className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm"
                    placeholder="Add external attendee name"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={addExternal}
                  >
                    Add
                  </Button>
                </div>
                {externalAttendees.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {externalAttendees.map((name, i) => (
                      <span
                        key={i}
                        className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs"
                      >
                        {name}
                        <button
                          type="button"
                          onClick={() =>
                            setExternalAttendees((prev) =>
                              prev.filter((_, idx) => idx !== i)
                            )
                          }
                          className="text-gray-400 hover:text-gray-600"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Notes (optional)
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={2}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  placeholder="What was discussed..."
                />
              </div>

              <div className="flex gap-2">
                <Button type="submit" disabled={submitting}>
                  {submitting ? "Saving..." : "Save Talk"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setShowForm(false)}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Talk list */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
        </div>
      ) : talks.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <MessageSquare className="mx-auto h-10 w-10 text-gray-300 mb-3" />
            <p className="text-sm text-gray-600">
              No toolbox talks logged yet. Click "Log a Talk" to record one.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {talks.map((talk) => (
            <Card key={talk.id}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className="text-sm font-semibold text-gray-900">
                      {talk.topic_title}
                    </h4>
                    <p className="text-xs text-gray-500 mt-0.5">
                      <span className="inline-flex items-center rounded-full bg-gray-100 px-1.5 py-0.5 text-xs font-medium text-gray-600 mr-2">
                        {categoryLabel(talk.topic_category)}
                      </span>
                      {talk.conducted_by_name}
                      {talk.conducted_at && (
                        <> · {new Date(talk.conducted_at).toLocaleDateString()}</>
                      )}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      <Users className="h-3.5 w-3.5" /> {talk.attendee_count}
                    </span>
                    {talk.duration_minutes && (
                      <span className="flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5" /> {talk.duration_minutes}m
                      </span>
                    )}
                  </div>
                </div>
                {talk.notes && (
                  <p className="text-sm text-gray-600 mt-2 line-clamp-2">
                    {talk.notes}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
