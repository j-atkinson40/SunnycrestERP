import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Globe, Check, X, ArrowRight, Sparkles, Shield, Loader2 } from "lucide-react";
import * as intelligenceService from "@/services/website-intelligence-service";
import type {
  WebsiteIntelligence,
  WebsiteSuggestion,
} from "@/types/website-intelligence";

// ── Confidence badge ──────────────────────────────────────────────

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const label =
    confidence >= 0.9
      ? "High confidence"
      : confidence >= 0.7
        ? "Likely"
        : "Possible";
  const color =
    confidence >= 0.9
      ? "bg-green-100 text-green-700 border-green-200"
      : confidence >= 0.7
        ? "bg-blue-100 text-blue-700 border-blue-200"
        : "bg-amber-100 text-amber-700 border-amber-200";

  return (
    <Badge variant="outline" className={cn("text-[10px]", color)}>
      {label}
    </Badge>
  );
}

// ── Suggestion card ───────────────────────────────────────────────

function SuggestionCard({
  suggestion,
  onAccept,
  onDismiss,
}: {
  suggestion: WebsiteSuggestion;
  onAccept: (id: string) => void;
  onDismiss: (id: string) => void;
}) {
  const isAccepted = suggestion.status === "accepted";
  const isDismissed = suggestion.status === "dismissed";

  return (
    <Card
      className={cn(
        "transition-all",
        isAccepted && "border-green-200 bg-green-50/50",
        isDismissed && "border-muted bg-muted/30 opacity-60",
      )}
    >
      <CardContent className="flex items-start gap-4 py-4">
        {/* Content */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold">{suggestion.suggestion_label}</h4>
            <ConfidenceBadge confidence={suggestion.confidence} />
          </div>
          {suggestion.evidence && (
            <p className="mt-1 text-xs italic text-muted-foreground">
              &ldquo;{suggestion.evidence}&rdquo;
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex shrink-0 items-center gap-2">
          {isAccepted ? (
            <>
              <Badge className="gap-1 bg-green-600 text-white">
                <Check className="h-3 w-3" /> Yes, we carry this
              </Badge>
              <button
                onClick={() => onDismiss(suggestion.id)}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                Undo
              </button>
            </>
          ) : isDismissed ? (
            <>
              <Badge variant="secondary" className="gap-1 text-muted-foreground">
                <X className="h-3 w-3" /> Not for us
              </Badge>
              <button
                onClick={() => onAccept(suggestion.id)}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                Undo
              </button>
            </>
          ) : (
            <>
              <Button
                size="sm"
                className="gap-1 bg-green-600 hover:bg-green-700"
                onClick={() => onAccept(suggestion.id)}
              >
                <Check className="h-3.5 w-3.5" /> Yes, we carry this
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="gap-1 text-muted-foreground"
                onClick={() => onDismiss(suggestion.id)}
              >
                <X className="h-3.5 w-3.5" /> Not for us
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ── Group suggestions by type ─────────────────────────────────────

const SECTION_CONFIG: Record<
  string,
  { title: string; icon: typeof Globe; description: string }
> = {
  vault_line: {
    title: "Product lines we found on your website",
    icon: Globe,
    description:
      "These look like vault lines you manufacture or distribute. Confirm the ones you carry.",
  },
  certification: {
    title: "Certifications we found",
    icon: Shield,
    description:
      "We detected these certifications or affiliations on your website.",
  },
  urn_category: {
    title: "Urn categories",
    icon: Sparkles,
    description: "These urn product categories were detected on your website.",
  },
  other: {
    title: "Other things we noticed",
    icon: Sparkles,
    description: "Additional details about your business.",
  },
};

function getSectionKey(type: string): string {
  if (type === "vault_line") return "vault_line";
  if (type === "certification") return "certification";
  if (type === "urn_category") return "urn_category";
  return "other";
}

// ── Main page ─────────────────────────────────────────────────────

export default function WebsiteSuggestionsReview() {
  const navigate = useNavigate();
  const [intelligence, setIntelligence] =
    useState<WebsiteIntelligence | null>(null);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);

  // Local suggestion state for optimistic updates
  const [localSuggestions, setLocalSuggestions] = useState<WebsiteSuggestion[]>(
    [],
  );

  const fetchData = useCallback(async () => {
    const data = await intelligenceService.getIntelligence();
    if (data) {
      setIntelligence(data);
      setLocalSuggestions(data.suggestions);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ── Accept / dismiss handlers ──────────────────────────────────

  const handleAccept = useCallback(
    async (id: string) => {
      // Optimistic update
      setLocalSuggestions((prev) =>
        prev.map((s) => (s.id === id ? { ...s, status: "accepted" as const } : s)),
      );
      try {
        await intelligenceService.updateSuggestion(id, "accepted");
      } catch {
        // Revert on error
        setLocalSuggestions((prev) =>
          prev.map((s) => (s.id === id ? { ...s, status: "pending" as const } : s)),
        );
        toast.error("Failed to update suggestion");
      }
    },
    [],
  );

  const handleDismiss = useCallback(
    async (id: string) => {
      setLocalSuggestions((prev) =>
        prev.map((s) =>
          s.id === id ? { ...s, status: "dismissed" as const } : s,
        ),
      );
      try {
        await intelligenceService.updateSuggestion(id, "dismissed");
      } catch {
        setLocalSuggestions((prev) =>
          prev.map((s) => (s.id === id ? { ...s, status: "pending" as const } : s)),
        );
        toast.error("Failed to update suggestion");
      }
    },
    [],
  );

  // ── Accept all pending ──────────────────────────────────────────

  const handleAcceptAll = useCallback(async () => {
    const pending = localSuggestions.filter((s) => s.status === "pending");
    setLocalSuggestions((prev) =>
      prev.map((s) =>
        s.status === "pending" ? { ...s, status: "accepted" as const } : s,
      ),
    );
    try {
      await Promise.all(
        pending.map((s) =>
          intelligenceService.updateSuggestion(s.id, "accepted"),
        ),
      );
    } catch {
      toast.error("Failed to accept some suggestions");
      fetchData();
    }
  }, [localSuggestions, fetchData]);

  // ── Continue to catalog builder ──────────────────────────────────

  const handleContinue = useCallback(async () => {
    setApplying(true);
    try {
      await intelligenceService.markApplied();
      navigate("/onboarding/catalog-builder");
    } catch {
      toast.error("Failed to save. You can still proceed.");
      navigate("/onboarding/catalog-builder");
    } finally {
      setApplying(false);
    }
  }, [navigate]);

  // ── Group suggestions by section ────────────────────────────────

  const sections = useMemo(() => {
    const groups: Record<string, WebsiteSuggestion[]> = {};
    for (const s of localSuggestions) {
      const key = getSectionKey(s.suggestion_type);
      if (!groups[key]) groups[key] = [];
      groups[key].push(s);
    }
    return groups;
  }, [localSuggestions]);

  const pendingCount = localSuggestions.filter(
    (s) => s.status === "pending",
  ).length;
  const acceptedCount = localSuggestions.filter(
    (s) => s.status === "accepted",
  ).length;

  // ── Loading ─────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!intelligence || localSuggestions.length === 0) {
    // Nothing to review; go straight to catalog builder
    navigate("/onboarding/catalog-builder", { replace: true });
    return null;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8 p-6">
      {/* ── Header ──────────────────────────────────────────────── */}
      <div>
        <div className="mb-2 flex items-center gap-2">
          <Globe className="h-6 w-6 text-teal-600" />
          <h1 className="text-2xl font-bold tracking-tight">
            We found some information about your business
          </h1>
        </div>
        <p className="text-sm text-muted-foreground">
          We scanned your website and detected the following products and
          certifications. Confirm what's accurate so we can pre-fill your
          catalog.
        </p>
      </div>

      {/* ── Summary box ─────────────────────────────────────────── */}
      {intelligence.summary && (
        <Card className="border-teal-200 bg-teal-50/50">
          <CardContent className="py-4">
            <div className="flex items-start gap-3">
              <Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-teal-600" />
              <div>
                <p className="text-sm font-medium text-teal-900">
                  Business Summary
                </p>
                <p className="mt-1 text-sm text-teal-800">
                  {intelligence.summary}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Quick actions ───────────────────────────────────────── */}
      {pendingCount > 0 && (
        <div className="flex items-center justify-between rounded-lg border bg-muted/30 px-4 py-3">
          <p className="text-sm text-muted-foreground">
            {pendingCount} suggestion{pendingCount !== 1 ? "s" : ""} waiting for
            your review
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={handleAcceptAll}
            className="gap-1"
          >
            <Check className="h-3.5 w-3.5" /> Accept all
          </Button>
        </div>
      )}

      {/* ── Suggestion sections ─────────────────────────────────── */}
      {Object.entries(sections).map(([sectionKey, items]) => {
        const config = SECTION_CONFIG[sectionKey] ?? SECTION_CONFIG.other;
        const SectionIcon = config.icon;

        return (
          <div key={sectionKey} className="space-y-3">
            <div className="flex items-center gap-2">
              <SectionIcon className="h-5 w-5 text-muted-foreground" />
              <div>
                <h2 className="text-base font-semibold">{config.title}</h2>
                <p className="text-xs text-muted-foreground">
                  {config.description}
                </p>
              </div>
            </div>
            <div className="space-y-2">
              {items
                .sort((a, b) => b.confidence - a.confidence)
                .map((suggestion) => (
                  <SuggestionCard
                    key={suggestion.id}
                    suggestion={suggestion}
                    onAccept={handleAccept}
                    onDismiss={handleDismiss}
                  />
                ))}
            </div>
          </div>
        );
      })}

      {/* ── Continue button ─────────────────────────────────────── */}
      <div className="flex items-center justify-between border-t pt-6">
        <p className="text-sm text-muted-foreground">
          {acceptedCount} item{acceptedCount !== 1 ? "s" : ""} accepted
        </p>
        <Button
          onClick={handleContinue}
          disabled={applying}
          className="gap-2"
          size="lg"
        >
          {applying ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <ArrowRight className="h-4 w-4" />
          )}
          Looks good, let's continue
        </Button>
      </div>
    </div>
  );
}
