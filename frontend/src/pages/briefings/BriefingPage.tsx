/**
 * Phase 6 — `/briefing` and `/briefing/:id` — full-page briefing view.
 *
 * Renders the narrative text + structured sections as expandable cards.
 * Pulls the latest morning briefing by default (via useBriefing), or a
 * specific briefing id if the URL carries one.
 *
 * Explicitly DOES NOT replace `MorningBriefingCard` — that legacy widget
 * still renders on manufacturing-dashboard.tsx + order-station.tsx per
 * the coexist strategy. This page is the new canonical detail view
 * linked from Cmd+K / space pins / email CTA.
 */

import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  ChevronDown,
  ChevronRight,
  RefreshCw,
  CheckCircle2,
  Settings as SettingsIcon,
  AlertTriangle,
  ListChecks,
  PhoneCall,
  Calendar,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SkeletonCard, SkeletonLines } from "@/components/ui/skeleton";
import { InlineError } from "@/components/ui/inline-error";
import { OnboardingTouch } from "@/components/onboarding/OnboardingTouch";
import {
  generateBriefing,
  getBriefing,
  markBriefingRead,
} from "@/services/briefing-service";
import type {
  BriefingSummary,
  BriefingType,
  FlagSection,
  PendingDecisionSection,
  QueueSummarySection,
} from "@/types/briefing";
import { useBriefing } from "@/hooks/useBriefing";
import { usePeekOptional } from "@/contexts/peek-context";
import type { PeekEntityType } from "@/types/peek";

export default function BriefingPage() {
  const { id } = useParams<{ id?: string }>();
  const navigate = useNavigate();
  const [briefingType, setBriefingType] = useState<BriefingType>("morning");

  // When :id is supplied, fetch that specific briefing. When not, use
  // the latest-morning hook. This keeps the common path one network
  // round-trip.
  const { briefing: latest, loading: latestLoading, error: latestError, reload } =
    useBriefing(briefingType);
  const [pinned, setPinned] = useState<BriefingSummary | null>(null);
  const [pinnedLoading, setPinnedLoading] = useState<boolean>(!!id);
  const [pinnedError, setPinnedError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (id) {
      setPinnedLoading(true);
      getBriefing(id)
        .then((b) => {
          if (!cancelled) setPinned(b);
        })
        .catch((e) => {
          if (!cancelled) {
            setPinnedError(e instanceof Error ? e.message : "Failed");
          }
        })
        .finally(() => {
          if (!cancelled) setPinnedLoading(false);
        });
    } else {
      setPinned(null);
      setPinnedError(null);
    }
    return () => {
      cancelled = true;
    };
  }, [id]);

  const briefing = id ? pinned : latest;
  const loading = id ? pinnedLoading : latestLoading;
  const error = id ? pinnedError : latestError;

  const regenerate = useCallback(async () => {
    try {
      const fresh = await generateBriefing(briefingType, false);
      toast.success("Briefing regenerated");
      if (id) {
        navigate(`/briefing/${fresh.id}`, { replace: true });
      } else {
        await reload();
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Regenerate failed");
    }
  }, [briefingType, id, navigate, reload]);

  const markRead = useCallback(async () => {
    if (!briefing) return;
    try {
      const updated = await markBriefingRead(briefing.id);
      if (id) {
        setPinned(updated);
      } else {
        await reload();
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Mark read failed");
    }
  }, [briefing, id, reload]);

  return (
    <div className="relative mx-auto max-w-3xl space-y-6 p-6">
      <OnboardingTouch
        touchKey="briefing_intro"
        title="Briefings are generated automatically."
        body="Morning orients you forward; evening closes the day. Configure sections + delivery time in preferences."
        position="bottom"
        className="right-6 top-2 w-72"
      />
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">
            {briefingType === "morning" ? "Morning briefing" : "End of day summary"}
          </h1>
          {briefing ? (
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span>
                {new Date(briefing.generated_at).toLocaleString()}
              </span>
              {briefing.active_space_name ? (
                <Badge variant="outline" className="bg-slate-50">
                  {briefing.active_space_name} space
                </Badge>
              ) : null}
              {briefing.read_at ? (
                <Badge variant="outline" className="bg-green-50 text-green-800">
                  Read
                </Badge>
              ) : null}
            </div>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2">
          {!id ? (
            <div className="inline-flex rounded-md border">
              <button
                className={
                  "px-3 py-1.5 text-sm " +
                  (briefingType === "morning" ? "bg-muted font-medium" : "")
                }
                onClick={() => setBriefingType("morning")}
                type="button"
              >
                Morning
              </button>
              <button
                className={
                  "px-3 py-1.5 text-sm border-l " +
                  (briefingType === "evening" ? "bg-muted font-medium" : "")
                }
                onClick={() => setBriefingType("evening")}
                type="button"
              >
                Evening
              </button>
            </div>
          ) : null}
          <Button variant="outline" size="sm" onClick={regenerate}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Regenerate
          </Button>
          {briefing && !briefing.read_at ? (
            <Button size="sm" onClick={markRead}>
              <CheckCircle2 className="mr-2 h-4 w-4" />
              Mark read
            </Button>
          ) : null}
          <Button
            variant="ghost"
            size="sm"
            render={<Link to="/settings/briefings" />}
          >
            <SettingsIcon className="mr-2 h-4 w-4" />
            Preferences
          </Button>
        </div>
      </header>

      {loading ? (
        <div className="space-y-4" data-testid="briefing-loading">
          <Card>
            <CardContent className="p-6 space-y-3">
              <SkeletonLines count={5} />
            </CardContent>
          </Card>
          <SkeletonCard lines={3} />
          <SkeletonCard lines={3} />
        </div>
      ) : error ? (
        <InlineError
          message="Couldn't load your briefing."
          hint={error}
          onRetry={() => {
            if (id) {
              setPinnedError(null);
              setPinnedLoading(true);
              getBriefing(id)
                .then(setPinned)
                .catch((e) =>
                  setPinnedError(e instanceof Error ? e.message : "Failed"),
                )
                .finally(() => setPinnedLoading(false));
            } else {
              void reload();
            }
          }}
          data-testid="briefing-error"
        />
      ) : !briefing ? (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            No briefing yet. The scheduler generates one daily at your
            configured delivery time —{" "}
            <Link to="/settings/briefings" className="text-primary hover:underline">
              configure times
            </Link>{" "}
            or regenerate now.
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardContent
              className="p-6"
              role="region"
              aria-label="Briefing narrative"
              aria-live="polite"
            >
              <p className="whitespace-pre-wrap text-base leading-relaxed">
                {briefing.narrative_text}
              </p>
            </CardContent>
          </Card>
          <StructuredSectionsRender sections={briefing.structured_sections} />
        </>
      )}
    </div>
  );
}

// ── Structured sections renderer ────────────────────────────────────

function StructuredSectionsRender({
  sections,
}: {
  sections: Record<string, unknown>;
}) {
  // Render known sections in a deterministic order.
  const blocks: React.ReactNode[] = [];

  if (Array.isArray(sections["queue_summaries"])) {
    blocks.push(
      <QueuesCard
        key="queues"
        items={sections["queue_summaries"] as QueueSummarySection[]}
      />,
    );
  }
  if (Array.isArray(sections["pending_decisions"])) {
    blocks.push(
      <PendingDecisionsCard
        key="decisions"
        title="Pending decisions"
        items={sections["pending_decisions"] as PendingDecisionSection[]}
      />,
    );
  }
  if (Array.isArray(sections["pending_decisions_remaining"])) {
    blocks.push(
      <PendingDecisionsCard
        key="decisions_remaining"
        title="Still pending"
        items={
          sections["pending_decisions_remaining"] as PendingDecisionSection[]
        }
      />,
    );
  }
  if (sections["overnight_calls"]) {
    blocks.push(
      <OvernightCallsCard
        key="calls"
        data={sections["overnight_calls"] as Record<string, unknown>}
      />,
    );
  }
  if (sections["today_calendar"]) {
    blocks.push(
      <CalendarCard
        key="calendar"
        title="Today"
        data={sections["today_calendar"] as Record<string, unknown>}
      />,
    );
  }
  if (sections["tomorrow_preview"]) {
    blocks.push(
      <CalendarCard
        key="tomorrow"
        title="Tomorrow"
        data={sections["tomorrow_preview"] as Record<string, unknown>}
      />,
    );
  }
  if (Array.isArray(sections["flags"])) {
    blocks.push(
      <FlagsCard
        key="flags"
        title="Flags"
        items={sections["flags"] as FlagSection[]}
      />,
    );
  }
  if (Array.isArray(sections["flagged_for_tomorrow"])) {
    blocks.push(
      <FlagsCard
        key="flagged_tomorrow"
        title="Flagged for tomorrow"
        items={sections["flagged_for_tomorrow"] as FlagSection[]}
      />,
    );
  }

  if (blocks.length === 0) return null;
  return <div className="space-y-3">{blocks}</div>;
}

function QueuesCard({ items }: { items: QueueSummarySection[] }) {
  const [open, setOpen] = useState(true);
  return (
    <CollapsibleCard
      title="Queues"
      icon={<ListChecks className="h-4 w-4" />}
      open={open}
      onToggle={() => setOpen((v) => !v)}
    >
      <ul className="space-y-2 text-sm">
        {items.map((q) => (
          <li key={q.queue_id} className="flex items-center justify-between">
            <Link
              to={`/triage/${encodeURIComponent(q.queue_id)}`}
              className="font-medium text-primary hover:underline"
            >
              {q.queue_name}
            </Link>
            <span className="text-muted-foreground">
              {q.pending_count} pending · {q.estimated_time_minutes} min
            </span>
          </li>
        ))}
      </ul>
    </CollapsibleCard>
  );
}

// Follow-up 4 — map briefing link_type tokens to peek entity types.
// link_type comes from Claude-rendered structured_sections + isn't
// strictly typed; this defensive map is a known-set whitelist.
// Unmapped link_types fall back to the plain "Open →" link.
const _BRIEFING_LINK_TYPE_TO_PEEK: Record<string, PeekEntityType> = {
  "fh-cases": "fh_case",
  "fh/cases": "fh_case",
  cases: "fh_case",
  invoices: "invoice",
  "ar/invoices": "invoice",
  "sales-orders": "sales_order",
  orders: "sales_order",
  "order-station/orders": "sales_order",
  tasks: "task",
  contacts: "contact",
  "vault/crm/contacts": "contact",
  "saved-views": "saved_view",
};


function PendingDecisionsCard({
  title,
  items,
}: {
  title: string;
  items: PendingDecisionSection[];
}) {
  const [open, setOpen] = useState(true);
  const peek = usePeekOptional();
  return (
    <CollapsibleCard
      title={title}
      icon={<CheckCircle2 className="h-4 w-4" />}
      open={open}
      onToggle={() => setOpen((v) => !v)}
    >
      <ul className="space-y-2 text-sm">
        {items.map((p, i) => {
          // Resolve a peek entity type if the link_type is known.
          const peekEntityType =
            p.link_type && _BRIEFING_LINK_TYPE_TO_PEEK[p.link_type];
          const peekable =
            peek != null && peekEntityType && p.link_id;
          return (
            <li
              key={`${p.title}-${i}`}
              className="flex items-center gap-2"
            >
              {peekable ? (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    peek!.openPeek({
                      entityType: peekEntityType as PeekEntityType,
                      entityId: p.link_id!,
                      triggerType: "click",
                      anchorElement: e.currentTarget as HTMLElement,
                    });
                  }}
                  className="text-left hover:underline"
                  data-testid="briefing-decision-peek-trigger"
                  data-peek-entity-type={peekEntityType}
                  data-peek-entity-id={p.link_id}
                >
                  {p.title}
                </button>
              ) : (
                <span>{p.title}</span>
              )}
              {p.link_id && p.link_type ? (
                <Link
                  to={`/${p.link_type}/${p.link_id}`}
                  className="ml-auto text-xs text-primary hover:underline"
                >
                  Open →
                </Link>
              ) : null}
            </li>
          );
        })}
      </ul>
    </CollapsibleCard>
  );
}

function FlagsCard({ title, items }: { title: string; items: FlagSection[] }) {
  const [open, setOpen] = useState(true);
  return (
    <CollapsibleCard
      title={title}
      icon={<AlertTriangle className="h-4 w-4 text-amber-600" />}
      open={open}
      onToggle={() => setOpen((v) => !v)}
    >
      <ul className="space-y-2 text-sm">
        {items.map((f, i) => (
          <li key={`${f.title}-${i}`}>
            <span className="font-medium">{f.title}</span>
            {f.detail ? (
              <span className="text-muted-foreground"> — {f.detail}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </CollapsibleCard>
  );
}

function OvernightCallsCard({
  data,
}: {
  data: Record<string, unknown>;
}) {
  const [open, setOpen] = useState(false);
  return (
    <CollapsibleCard
      title="Overnight calls"
      icon={<PhoneCall className="h-4 w-4" />}
      open={open}
      onToggle={() => setOpen((v) => !v)}
    >
      <dl className="grid grid-cols-2 gap-2 text-sm">
        {Object.entries(data).map(([k, v]) => (
          <div key={k} className="flex items-center justify-between border-b py-1">
            <dt className="text-muted-foreground">{k.replace(/_/g, " ")}</dt>
            <dd className="font-medium">{String(v)}</dd>
          </div>
        ))}
      </dl>
    </CollapsibleCard>
  );
}

function CalendarCard({
  title,
  data,
}: {
  title: string;
  data: Record<string, unknown>;
}) {
  const [open, setOpen] = useState(false);
  return (
    <CollapsibleCard
      title={title}
      icon={<Calendar className="h-4 w-4" />}
      open={open}
      onToggle={() => setOpen((v) => !v)}
    >
      <pre className="whitespace-pre-wrap text-xs text-muted-foreground">
        {JSON.stringify(data, null, 2)}
      </pre>
    </CollapsibleCard>
  );
}

function CollapsibleCard({
  title,
  icon,
  open,
  onToggle,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader
        className="cursor-pointer flex flex-row items-center gap-2 py-3"
        onClick={onToggle}
      >
        {icon}
        <CardTitle className="text-sm flex-1">{title}</CardTitle>
        {open ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
      </CardHeader>
      {open ? <CardContent className="pt-0">{children}</CardContent> : null}
    </Card>
  );
}

