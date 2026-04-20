/**
 * Phase 6 — BriefingCard.
 *
 * New dashboard widget that renders a condensed form of the latest
 * Phase-6 morning briefing + link to the full /briefing page.
 *
 * Explicit coexist discipline: this is NOT a replacement for
 * `MorningBriefingCard` (legacy, on manufacturing-dashboard.tsx +
 * order-station.tsx). Legacy surfaces keep consuming the legacy
 * endpoint. BriefingCard is the NEW surface users opt into by pinning
 * `/briefing` to a space or embedding this widget on a new dashboard.
 */

import { Link } from "react-router-dom";
import { Sunrise, Sunset, ChevronRight, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SkeletonLines } from "@/components/ui/skeleton";
import { useBriefing } from "@/hooks/useBriefing";
import type { BriefingType } from "@/types/briefing";

interface BriefingCardProps {
  briefingType?: BriefingType;
  /** Cap on narrative character count shown inline. */
  maxChars?: number;
}

export function BriefingCard({
  briefingType = "morning",
  maxChars = 320,
}: BriefingCardProps) {
  const { briefing, loading, error, reload } = useBriefing(briefingType);

  const icon =
    briefingType === "morning" ? (
      <Sunrise className="h-4 w-4" />
    ) : (
      <Sunset className="h-4 w-4" />
    );
  const title =
    briefingType === "morning" ? "Morning briefing" : "End of day summary";

  return (
    <Card data-testid={`briefing-card-${briefingType}`}>
      <CardHeader className="flex flex-row items-center gap-2">
        {icon}
        <CardTitle className="text-sm flex-1">{title}</CardTitle>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void reload()}
          aria-label="Refresh briefing"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {loading ? (
          <SkeletonLines count={3} />
        ) : error ? (
          <p className="text-destructive text-xs">{error}</p>
        ) : !briefing ? (
          <div className="text-muted-foreground">
            <p className="mb-2">No briefing yet today.</p>
            <Button asChild size="sm" variant="outline">
              <Link to="/briefing">Open briefing</Link>
            </Button>
          </div>
        ) : (
          <>
            <p className="whitespace-pre-wrap leading-relaxed">
              {_truncate(briefing.narrative_text, maxChars)}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {briefing.active_space_name ? (
                <Badge variant="outline" className="bg-slate-50 text-xs">
                  {briefing.active_space_name}
                </Badge>
              ) : null}
              {!briefing.read_at ? (
                <Badge variant="outline" className="bg-blue-50 text-blue-800 text-xs">
                  Unread
                </Badge>
              ) : null}
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link to={`/briefing/${briefing.id}`}>
                Read full briefing <ChevronRight className="ml-1 h-3 w-3" />
              </Link>
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function _truncate(s: string, n: number): string {
  if (s.length <= n) return s;
  // Truncate at last word boundary within n chars.
  const cut = s.slice(0, n);
  const lastSpace = cut.lastIndexOf(" ");
  return (lastSpace > 0 ? cut.slice(0, lastSpace) : cut) + "…";
}
