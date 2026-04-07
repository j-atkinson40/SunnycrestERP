// KBCoachingBanner — contextual banner suggesting KB content uploads.
// Shows vertical-aware coaching based on how much content has been uploaded.

import { useEffect, useState } from "react";
import apiClient from "@/lib/api-client";
import {
  BookOpen,
  Upload,
  ChevronRight,
  Lightbulb,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";

interface KBStats {
  documents: number;
  chunks: number;
  pricing_entries: number;
  categories: number;
}

const COACHING_STEPS = [
  {
    threshold: 0,
    title: "Get Started with Your Knowledge Base",
    description:
      "Upload your product pricing sheets, company policies, and cemetery requirements. Call Intelligence will use this information to assist employees during phone calls.",
    action: "Upload your first document",
  },
  {
    threshold: 1,
    title: "Add More Context for Better Results",
    description:
      "Great start! Add more document types — pricing, product specs, and cemetery requirements help your team answer questions faster during calls.",
    action: "Upload more documents",
  },
  {
    threshold: 5,
    title: "Review Your Pricing Data",
    description:
      "Your knowledge base is growing. Check that pricing entries are accurate — these are shown to employees during live calls when customers ask about pricing.",
    action: "Review pricing entries",
  },
  {
    threshold: 15,
    title: "Knowledge Base Active",
    description:
      "Your knowledge base is well-populated and actively assisting during calls. Keep documents up to date as pricing and policies change.",
    action: null,
  },
];

export function KBCoachingBanner({ onNavigate }: { onNavigate?: (section: string) => void }) {
  const [stats, setStats] = useState<KBStats | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    apiClient
      .get("/knowledge-base/stats")
      .then((r) => setStats(r.data))
      .catch(() => {});
  }, []);

  if (dismissed || !stats) return null;

  // Find the right coaching step
  const step =
    [...COACHING_STEPS].reverse().find((s) => stats.documents >= s.threshold) ??
    COACHING_STEPS[0];

  // Don't show banner if fully populated and no action
  if (!step.action && stats.documents >= 15) return null;

  return (
    <div className="rounded-xl border bg-gradient-to-r from-indigo-50 to-purple-50 p-5 relative">
      <button
        onClick={() => setDismissed(true)}
        className="absolute top-3 right-3 p-1 rounded hover:bg-white/60 transition-colors"
      >
        <X className="h-4 w-4 text-muted-foreground" />
      </button>

      <div className="flex items-start gap-4">
        <div className="rounded-lg bg-indigo-100 p-2.5 shrink-0">
          <Lightbulb className="h-5 w-5 text-indigo-600" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-sm text-gray-900">{step.title}</h3>
          <p className="text-sm text-muted-foreground mt-1">{step.description}</p>

          {/* Stats row */}
          <div className="flex gap-4 mt-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <BookOpen className="h-3.5 w-3.5" />
              {stats.documents} documents
            </span>
            <span>{stats.chunks} chunks</span>
            <span>{stats.pricing_entries} pricing entries</span>
          </div>

          {step.action && (
            <Button
              size="sm"
              variant="outline"
              className="mt-3"
              onClick={() => onNavigate?.(stats.documents === 0 ? "upload" : "pricing")}
            >
              <Upload className="h-4 w-4 mr-1.5" />
              {step.action}
              <ChevronRight className="h-3.5 w-3.5 ml-1" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
