import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Plus, Users, Clock, MessageSquare } from "lucide-react";
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

export default function SafetyToolboxTalksPage() {
  const [talks, setTalks] = useState<Talk[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

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
      const [talksRes, empRes] = await Promise.all([
        apiClient.get("/safety/toolbox-talks"),
        apiClient.get("/briefings/team-config").catch(() => ({ data: [] })),
      ]);
      setTalks(talksRes.data);
      setEmployees(empRes.data);
    } catch {
      toast.error("Failed to load toolbox talks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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
