import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Check,
  Clock,
  AlertTriangle,
  CalendarDays,
  Send,
  Eye,
} from "lucide-react";
import apiClient from "@/lib/api-client";

const MONTH_NAMES = [
  "", "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

interface ScheduleEntry {
  id: string;
  year: number;
  month_number: number;
  status: string;
  topic_key: string | null;
  topic_title: string | null;
  osha_standard: string | null;
  is_high_risk: boolean;
  posted_by_name: string | null;
  completion_rate: number | null;
  announcement_id: string | null;
}

function statusBadge(status: string) {
  switch (status) {
    case "complete":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
          <Check className="h-3 w-3" /> Complete
        </span>
      );
    case "posted":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
          <Check className="h-3 w-3" /> Posted
        </span>
      );
    case "reminder_sent":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
          <Clock className="h-3 w-3" /> Reminder sent
        </span>
      );
    case "overdue":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
          <AlertTriangle className="h-3 w-3" /> Overdue
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">
          <CalendarDays className="h-3 w-3" /> Upcoming
        </span>
      );
  }
}

export default function SafetyTrainingCalendarPage() {
  const navigate = useNavigate();
  const [year, setYear] = useState(new Date().getFullYear());
  const [schedule, setSchedule] = useState<ScheduleEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchSchedule = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get(`/safety/training/schedule?year=${year}`);
      setSchedule(res.data);
    } catch {
      setSchedule([]);
    } finally {
      setLoading(false);
    }
  }, [year]);

  useEffect(() => {
    fetchSchedule();
  }, [fetchSchedule]);

  const handleInitialize = async () => {
    try {
      await apiClient.post(`/safety/training/schedule/initialize?year=${year}`);
      toast.success(`Training schedule initialized for ${year}`);
      fetchSchedule();
    } catch {
      toast.error("Failed to initialize schedule");
    }
  };

  const posted = schedule.filter((s) => ["posted", "complete"].includes(s.status)).length;
  const avgCompletion = schedule.filter((s) => s.completion_rate != null).length > 0
    ? Math.round(
        schedule
          .filter((s) => s.completion_rate != null)
          .reduce((sum, s) => sum + (s.completion_rate ?? 0), 0) /
          schedule.filter((s) => s.completion_rate != null).length
      )
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">
            Safety Training Calendar
          </h2>
          <p className="text-sm text-gray-500">
            12 monthly OSHA training topics for your team
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm"
          >
            {[year - 1, year, year + 1].map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Stats */}
      {schedule.length > 0 && (
        <div className="grid grid-cols-2 gap-4">
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-gray-900">
                {posted} / 12
              </p>
              <p className="text-xs text-gray-500">Trainings posted</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-gray-900">
                {avgCompletion}%
              </p>
              <p className="text-xs text-gray-500">Avg completion rate</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* No schedule — initialize */}
      {!loading && schedule.length === 0 && (
        <Card>
          <CardContent className="p-8 text-center">
            <CalendarDays className="mx-auto h-10 w-10 text-gray-300 mb-3" />
            <p className="text-sm text-gray-600 mb-4">
              No training schedule for {year}. Initialize to create the 12-month
              training calendar.
            </p>
            <Button onClick={handleInitialize}>
              Initialize {year} Schedule
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Calendar table */}
      {schedule.length > 0 && (
        <Card>
          <CardContent className="p-0">
            <div className="divide-y divide-gray-100">
              {schedule.map((entry) => (
                <div
                  key={entry.id}
                  className="flex items-center justify-between px-4 py-3 hover:bg-gray-50"
                >
                  <div className="flex items-center gap-4 min-w-0 flex-1">
                    <span className="text-sm font-medium text-gray-500 w-20 shrink-0">
                      {MONTH_NAMES[entry.month_number]}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-gray-900 truncate">
                        {entry.topic_title}
                        {entry.is_high_risk && (
                          <span className="ml-1.5 text-xs text-red-600">
                            ⚠ High risk
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-gray-400">{entry.osha_standard}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    {statusBadge(entry.status)}
                    {entry.completion_rate != null && (
                      <span className="text-xs text-gray-500 w-12 text-right">
                        {Math.round(entry.completion_rate)}%
                      </span>
                    )}
                    {entry.posted_by_name && (
                      <span className="text-xs text-gray-400 hidden sm:inline">
                        {entry.posted_by_name}
                      </span>
                    )}
                    {["upcoming", "reminder_sent", "overdue"].includes(
                      entry.status
                    ) ? (
                      <Button
                        size="sm"
                        variant="default"
                        className="gap-1 text-xs"
                        onClick={() =>
                          navigate(`/safety/training/${entry.id}/post`)
                        }
                      >
                        <Send className="h-3 w-3" /> Post
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="gap-1 text-xs"
                        onClick={() =>
                          navigate(`/safety/training/${entry.id}/post`)
                        }
                      >
                        <Eye className="h-3 w-3" /> View
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {loading && (
        <div className="flex justify-center py-12">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-gray-600" />
        </div>
      )}
    </div>
  );
}
