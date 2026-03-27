/**
 * Platform admin — Training Content Generation
 *
 * Triggers Claude API to generate shared procedures and curriculum tracks
 * for the manufacturing vertical. Shows live streaming progress.
 */

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { BookOpen, CheckCircle, XCircle, Loader, RefreshCw, Zap } from "lucide-react";
import platformClient from "@/lib/platform-api-client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ContentStatus {
  shared_procedures: number;
  shared_curriculum_tracks: number;
  has_shared_content: boolean;
  procedures_expected: number;
  tracks_expected: number;
}

interface ProgressEvent {
  type: string;
  section?: string;
  index?: number;
  total?: number;
  item?: string;
  status?: string;
  error?: string;
  message?: string;
  created?: number;
  errors?: string[];
  procedures_created?: number;
  tracks_created?: number;
  procedures_total?: number;
  tracks_total?: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusBadge(status: ContentStatus | null) {
  if (!status) return null;
  if (status.shared_procedures >= status.procedures_expected && status.shared_curriculum_tracks >= status.tracks_expected) {
    return <Badge className="bg-green-100 text-green-800">Complete</Badge>;
  }
  if (status.has_shared_content) {
    return <Badge className="bg-yellow-100 text-yellow-800">Partial</Badge>;
  }
  return <Badge variant="outline" className="text-muted-foreground">Not Generated</Badge>;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function TrainingContentPage() {
  const [status, setStatus] = useState<ContentStatus | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState<ProgressEvent[]>([]);
  const [done, setDone] = useState(false);

  async function loadStatus() {
    try {
      const { data } = await platformClient.get<ContentStatus>("/training/content-status");
      setStatus(data);
    } catch {
      // non-critical
    } finally {
      setLoadingStatus(false);
    }
  }

  useEffect(() => {
    loadStatus();
  }, []);

  async function handleGenerate(force = false) {
    setGenerating(true);
    setProgress([]);
    setDone(false);

    try {
      const token = localStorage.getItem("platform_access_token") ?? "";
      const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
      const response = await fetch(`${apiBase}/api/platform/training/generate-content`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ force }),
      });

      if (!response.ok) {
        toast.error(`Generation failed: HTTP ${response.status}`);
        return;
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done: streamDone, value } = await reader.read();
        if (streamDone) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n").filter((l) => l.trim());
        for (const line of lines) {
          try {
            const event: ProgressEvent = JSON.parse(line);
            setProgress((prev) => [...prev, event]);
            if (event.type === "complete") {
              setDone(true);
              toast.success(`Done — ${event.procedures_created} procedures, ${event.tracks_created} tracks generated`);
              loadStatus();
            }
            if (event.type === "error") {
              toast.error(`Generation error: ${event.message}`);
            }
          } catch {
            // skip malformed lines
          }
        }
      }
    } catch (err: unknown) {
      toast.error("Generation failed — check console");
      console.error(err);
    } finally {
      setGenerating(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Training Content</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Generate shared procedures and curriculum tracks for all manufacturing tenants via Claude API.
          </p>
        </div>
        {statusBadge(status)}
      </div>

      {/* Status cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">Procedures</p>
          <p className="text-2xl font-bold">
            {loadingStatus ? "—" : status?.shared_procedures ?? 0}
            <span className="text-sm font-normal text-muted-foreground"> / {status?.procedures_expected ?? 24}</span>
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">Curriculum Tracks</p>
          <p className="text-2xl font-bold">
            {loadingStatus ? "—" : status?.shared_curriculum_tracks ?? 0}
            <span className="text-sm font-normal text-muted-foreground"> / {status?.tracks_expected ?? 3}</span>
          </p>
        </Card>
      </div>

      {/* Action buttons */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Content Generation</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Generates {status?.procedures_expected ?? 24} procedures and {status?.tracks_expected ?? 3} curriculum tracks
            (accounting, inside sales, operations) using Claude API. Content is shared across all manufacturing tenants.
            Generation takes 5–10 minutes.
          </p>
          <div className="flex gap-2">
            <Button
              onClick={() => handleGenerate(false)}
              disabled={generating || (status?.has_shared_content && !done)}
            >
              {generating ? (
                <>
                  <Loader className="h-4 w-4 mr-2 animate-spin" />
                  Generating…
                </>
              ) : (
                <>
                  <Zap className="h-4 w-4 mr-2" />
                  Generate Training Content
                </>
              )}
            </Button>
            {status?.has_shared_content && (
              <Button
                variant="outline"
                onClick={() => {
                  if (window.confirm("This will regenerate all content, overwriting existing procedures and tracks. Continue?")) {
                    handleGenerate(true);
                  }
                }}
                disabled={generating}
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Regenerate All
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Live progress */}
      {progress.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <BookOpen className="h-4 w-4" />
              Generation Progress
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1 font-mono text-xs max-h-96 overflow-y-auto">
              {progress.map((event, i) => {
                if (event.type === "start") {
                  return <p key={i} className="text-muted-foreground">Starting generation: {event.procedures_total} procedures + {event.tracks_total} curriculum tracks</p>;
                }
                if (event.type === "section_start") {
                  return <p key={i} className="text-muted-foreground font-semibold mt-2">── {event.section} ({event.total} items)</p>;
                }
                if (event.type === "progress") {
                  const icon = event.status === "done"
                    ? <CheckCircle className="h-3 w-3 text-green-600 inline mr-1" />
                    : event.status === "error"
                    ? <XCircle className="h-3 w-3 text-red-500 inline mr-1" />
                    : event.status === "skipped"
                    ? <span className="text-muted-foreground mr-1">–</span>
                    : <Loader className="h-3 w-3 animate-spin inline mr-1 text-blue-500" />;
                  return (
                    <p key={i} className={event.status === "error" ? "text-red-500" : event.status === "skipped" ? "text-muted-foreground" : ""}>
                      {icon}[{event.index}/{event.total}] {event.item} — {event.status}
                      {event.error ? ` (${event.error})` : ""}
                    </p>
                  );
                }
                if (event.type === "section_complete") {
                  return <p key={i} className="text-green-700 mt-1">✓ {event.section}: {event.created} created{event.errors?.length ? `, ${event.errors.length} errors` : ""}</p>;
                }
                if (event.type === "complete") {
                  return (
                    <p key={i} className="text-green-700 font-semibold mt-2">
                      ✓ Complete — {event.procedures_created} procedures, {event.tracks_created} tracks
                      {event.errors?.length ? ` (${event.errors.length} errors)` : ""}
                    </p>
                  );
                }
                return null;
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
