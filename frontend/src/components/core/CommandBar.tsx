// CommandBar.tsx — Bridgeable Core Command Bar (Cmd+K)

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Calendar,
  CheckSquare,
  Clock,
  Layers,
  Loader2,
  Mic,
  MicOff,
  Navigation,
  Phone,
  PlusCircle,
  Search,
  Shield,
  Sun,
  Truck,
  Users,
  X,
  Zap,
} from "lucide-react";
import apiClient from "@/lib/api-client";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { useMicrophone } from "@/hooks/useMicrophone";
import type { CommandAction, RecentAction } from "@/core/actionRegistry";
import {
  addRecentAction,
  filterActionsByRole,
  getActionsForVertical,
  getRecentActions,
  matchLocalActions,
} from "@/core/actionRegistry";
import { useAuth } from "@/contexts/auth-context";
import { useCommandBar } from "@/core/CommandBarProvider";
import { WorkflowController, type WorkflowRunState } from "@/components/workflows/WorkflowController";
import { NaturalLanguageOverlay } from "@/components/workflows/NaturalLanguageOverlay";
import { SlideOver } from "@/components/ui/SlideOver";

// ── Icon map ────────────────────────────────────────────────────────────────

// Result ordering within the command bar — action items rank above navigation.
// WORKFLOW first, then ACTION, then RECORD/VIEW, then NAV, then ASK.
// Stable within each type so backend/local relevance order is preserved.
const TYPE_RANK: Record<string, number> = {
  WORKFLOW: 0,
  ANSWER: 1,
  ACTION: 2,
  RECORD: 3,
  DOCUMENT: 4,
  VIEW: 5,
  NAV: 6,
  ASK: 7,
  ASK_AI: 99,  // always last
};

function sortByTypeRank(actions: CommandAction[]): CommandAction[] {
  return [...actions].sort((a, b) => {
    const ra = TYPE_RANK[a.type] ?? 99;
    const rb = TYPE_RANK[b.type] ?? 99;
    return ra - rb;
  });
}

const ICON_MAP: Record<string, React.ReactNode> = {
  "plus-circle": <PlusCircle className="h-4 w-4" />,
  truck: <Truck className="h-4 w-4" />,
  layers: <Layers className="h-4 w-4" />,
  "check-square": <CheckSquare className="h-4 w-4" />,
  calendar: <Calendar className="h-4 w-4" />,
  "alert-triangle": <AlertTriangle className="h-4 w-4" />,
  sun: <Sun className="h-4 w-4" />,
  phone: <Phone className="h-4 w-4" />,
  zap: <Zap className="h-4 w-4" />,
  shield: <Shield className="h-4 w-4" />,
  users: <Users className="h-4 w-4" />,
  navigation: <Navigation className="h-4 w-4" />,
  clock: <Clock className="h-4 w-4" />,
};

function ActionIcon({ icon }: { icon: string }) {
  return (
    <span className="flex h-7 w-7 items-center justify-center rounded-md bg-gray-100 text-gray-500 flex-shrink-0">
      {ICON_MAP[icon] ?? <Search className="h-4 w-4" />}
    </span>
  );
}

// ── Type badge ───────────────────────────────────────────────────────────────

const TYPE_BADGE_CLASSES: Record<string, string> = {
  WORKFLOW: "bg-violet-100 text-violet-700",
  ACTION: "bg-blue-100 text-blue-700",
  ANSWER: "bg-yellow-100 text-yellow-800",
  DOCUMENT: "bg-slate-100 text-slate-600",
  VIEW: "bg-slate-100 text-slate-600",
  RECORD: "bg-emerald-100 text-emerald-700",
  NAV: "bg-purple-100 text-purple-700",
  ASK: "bg-amber-100 text-amber-700",
  ASK_AI: "bg-indigo-100 text-indigo-700",
};

function TypeBadge({ type }: { type: string }) {
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
        TYPE_BADGE_CLASSES[type] ?? "bg-gray-100 text-gray-500"
      }`}
    >
      {type}
    </span>
  );
}

// ── Shortcut badge ───────────────────────────────────────────────────────────

function ShortcutBadge({ n }: { n: number }) {
  // ⌥ = Option key on Mac. We've switched the primary quick-pick modifier
  // to Option because Cmd+1-8 is reserved by Mac browsers for tab switching.
  return (
    <span
      className="flex items-center justify-center rounded border border-gray-200 bg-white font-mono text-[10px] text-gray-400 shadow-sm flex-shrink-0 px-1.5 h-5"
      title={`Option+${n} (or Cmd+${n})`}
    >
      ⌥{n}
    </span>
  );
}

// ── Waveform ─────────────────────────────────────────────────────────────────

function VoiceWaveform({ levels, active }: { levels: number[]; active: boolean }) {
  return (
    <div className="flex items-end gap-[2px] h-8">
      {levels.map((level, i) => {
        const height = active ? Math.max(4, Math.round(level * 28)) : 4;
        return (
          <div
            key={i}
            className="w-[3px] rounded-full bg-blue-500 transition-all duration-75"
            style={{ height: `${height}px` }}
          />
        );
      })}
    </div>
  );
}

// ── API response types ───────────────────────────────────────────────────────

interface CoreCommandResponse {
  results: Array<{
    id: string;
    title: string;
    subtitle?: string;
    icon?: string;
    type: "ACTION" | "NAV" | "VIEW" | "RECORD" | "ASK";
    route?: string;
    handler_type?: string;
  }>;
  search_only?: boolean;
  answer?: string;
}

interface DocumentOrAnswerResult {
  result_type: "answer" | "document";
  id: string;
  // answer
  headline?: string;
  // document
  title?: string;
  excerpt?: string;
  // both
  source_title?: string;
  source_section?: string | null;
  source_id: string;
  content_source: string;
  chunk_id?: string | null;
  confidence?: number;
}

// Unified command-bar search response shape from /core/command-bar/search
interface CommandBarSearchResponse {
  intent?: "question" | "search" | "action" | "navigate" | "empty";
  answered?: boolean;
  answer?: {
    id: string;
    headline: string;
    source_title?: string;
    source_label?: string;
    source_section?: string | null;
    route?: string;
    related_record_ids?: string[];
  } | null;
  records?: Array<{
    result_type: "record";
    record_type: string;
    id: string;
    record_id: string;
    title: string;
    subtitle?: string;
    icon?: string;
    route?: string;
  }>;
  documents?: DocumentOrAnswerResult[];
  ask_ai?: {
    result_type: "ask_ai";
    id: string;
    icon: string;
    title: string;
    subtitle: string;
    query: string;
  } | null;
}

// ── Main component ────────────────────────────────────────────────────────────

interface CommandBarProps {
  isOpen: boolean;
  onClose: () => void;
  voiceMode?: boolean;
}

export function CommandBar({ isOpen, onClose, voiceMode = false }: CommandBarProps) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<CommandAction[]>([]);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [recentActions, setRecentActions] = useState<RecentAction[]>([]);
  const [searchOnly, setSearchOnly] = useState(false);
  const [apiAnswer, setApiAnswer] = useState<string | null>(null);
  const [searchingDocs, setSearchingDocs] = useState(false);
  const [activeWorkflow, setActiveWorkflow] = useState<{ id: string; title: string } | null>(null);
  const [activeNLWorkflow, setActiveNLWorkflow] = useState<{
    id: string
    name: string
    steps: Array<{ step_order: number; step_key: string; step_type: string; config?: Record<string, unknown> }>
  } | null>(null);
  const [aiMode, setAiMode] = useState<{ query: string; answer: string; loading: boolean } | null>(null);
  const [openSlideOver, setOpenSlideOver] = useState<{ recordType: string; recordId: string; title: string } | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const { user, company } = useAuth();
  const { setShortcutRefs } = useCommandBar();
  // The auth User model exposes the role as `role_slug` (e.g. "admin", "office").
  const userRole = (user as unknown as { role_slug?: string })?.role_slug;
  // Pick registry based on tenant vertical — FH tenants get funeral_home actions,
  // manufacturer tenants get manufacturing actions. Never mix the two.
  const tenantVertical =
    ((company as unknown as { vertical?: string; tenant_type?: string }) || {}).vertical ||
    ((company as unknown as { vertical?: string; tenant_type?: string }) || {}).tenant_type ||
    "manufacturing";
  const verticalActions = getActionsForVertical(tenantVertical);
  const permittedActions = filterActionsByRole(verticalActions, userRole);

  const { showMic, requestPermission } = useMicrophone();

  const handleVoiceResult = useCallback(
    (transcript: string) => {
      setQuery(transcript);
    },
    []
  );

  const { isListening, interimTranscript, audioLevels, startListening, stopListening } =
    useVoiceInput({
      onResult: handleVoiceResult,
    });

  // Reset state on open
  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setResults([]);
      setSelectedIdx(0);
      setSearchOnly(false);
      setApiAnswer(null);
      setRecentActions(getRecentActions());
      if (voiceMode) {
        // Auto-start voice
        requestPermission().then((granted) => {
          if (granted) startListening();
        });
      } else {
        setTimeout(() => inputRef.current?.focus(), 50);
      }
    } else {
      if (isListening) stopListening();
    }
  }, [isOpen, voiceMode]); // eslint-disable-line react-hooks/exhaustive-deps

  // Debounced search
  useEffect(() => {
    if (!isOpen) return;
    const q = query.trim();
    if (q.length < 2) {
      setResults([]);
      setApiAnswer(null);
      return;
    }

    const timer = setTimeout(async () => {
      setLoading(true);
      setSearchOnly(false);

      // Cancel previous request
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        // Fire core command + workflow command-bar + document search in parallel
        setSearchingDocs(q.length >= 3);
        const [coreRes, wfRes, docsRes] = await Promise.allSettled([
          apiClient.post<CoreCommandResponse>(
            "/core/command",
            { query: q, context: { current_page: window.location.pathname } },
            { signal: controller.signal }
          ),
          apiClient.get<Array<{
            workflow_id: string;
            title: string;
            subtitle: string;
            icon: string;
            first_step_preview: string;
            priority: number;
          }>>("/workflows/command-bar", { params: { q }, signal: controller.signal }),
          q.length >= 3
            ? apiClient.get<CommandBarSearchResponse>(
                "/core/command-bar/search",
                { params: { q, include_documents: true }, signal: controller.signal }
              )
            : Promise.resolve({ data: { documents: [] } as CommandBarSearchResponse }),
        ]);
        setSearchingDocs(false);

        // Workflow results — always ranked above everything else
        const workflowActions: CommandAction[] =
          wfRes.status === "fulfilled"
            ? (wfRes.value.data || []).map((w) => ({
                id: `wf_${w.workflow_id}`,
                keywords: [],
                title: w.title,
                subtitle: w.first_step_preview || w.subtitle,
                icon: w.icon || "zap",
                type: "WORKFLOW",
                roles: [],
                vertical: tenantVertical,
                workflowId: w.workflow_id,
                firstStepPreview: w.first_step_preview,
              }))
            : [];

        const coreData: CoreCommandResponse | null =
          coreRes.status === "fulfilled" ? coreRes.value.data : null;
        setSearchOnly(!!coreData?.search_only);
        setApiAnswer(coreData?.answer ?? null);

        // Map API core-command results (could be empty)
        const apiResults: CommandAction[] = (coreData?.results || []).map((r) => ({
          id: r.id,
          keywords: [],
          title: r.title,
          subtitle: r.subtitle,
          icon: r.icon ?? "navigation",
          type: r.type,
          route: r.route,
          roles: [],
          vertical: "manufacturing",
        }));
        const filteredApiResults = filterActionsByRole(apiResults, userRole);

        // Local action matches — ALWAYS compute them so they can fill
        // the list when the API returns nothing actionable.
        const rawLocalMatches = matchLocalActions(q, permittedActions);

        // Dedup: when the universal Create Order workflow is present,
        // suppress the local "create_order" / "create_disinterment"
        // ACTION entries that cover the same intent.
        const hasUniversalOrder = workflowActions.some(
          (w) => w.workflowId === "wf_create_order",
        );
        const SUPPRESSED_BY_UNIVERSAL_ORDER = new Set([
          "create_order",
          "create_disinterment",
          "create_disinterment_order",
          "new_order",
          "place_order",
        ]);
        const localMatches = hasUniversalOrder
          ? rawLocalMatches.filter(
              (a) => !(a.type === "ACTION" && SUPPRESSED_BY_UNIVERSAL_ORDER.has(a.id)),
            )
          : rawLocalMatches;

        // Unified search response: records + inline answer + document hits
        const searchData: CommandBarSearchResponse =
          docsRes.status === "fulfilled" ? docsRes.value.data || {} : {};
        const docs = searchData.documents || [];
        const liveRecords = searchData.records || [];
        const inlineAnswer = searchData.answer || null;
        const wasAnswered = !!searchData.answered;

        const answerActions: CommandAction[] = inlineAnswer
          ? [{
              id: inlineAnswer.id,
              keywords: [],
              title: inlineAnswer.headline,
              subtitle: inlineAnswer.source_label || inlineAnswer.source_title || undefined,
              icon: "zap",
              type: "ANSWER",
              roles: [],
              vertical: "manufacturing",
              route: inlineAnswer.route,
              sourceSection: inlineAnswer.source_section || null,
            } as CommandAction]
          : [];

        const recordActions: CommandAction[] = liveRecords.map((r) => ({
          id: r.id,
          keywords: [],
          title: r.title,
          subtitle: r.subtitle,
          icon: r.icon || "navigation",
          type: "RECORD",
          route: r.route,
          roles: [],
          vertical: "manufacturing",
        }));

        const docActions: CommandAction[] = docs.map((d) => {
          if (d.result_type === "answer") {
            return {
              id: d.id,
              keywords: [],
              title: d.headline || "Answer",
              subtitle: d.source_section
                ? `${d.source_title} · ${d.source_section}`
                : d.source_title,
              icon: "zap",
              type: "ANSWER",
              roles: [],
              vertical: "manufacturing",
              contentSource: d.content_source,
              sourceId: d.source_id,
              chunkId: d.chunk_id || undefined,
              sourceSection: d.source_section || null,
              confidence: d.confidence,
            } as CommandAction;
          }
          return {
            id: d.id,
            keywords: [],
            title: d.title || d.source_title || "Document",
            subtitle: d.excerpt || d.source_section || undefined,
            icon: "shield",
            type: "DOCUMENT",
            roles: [],
            vertical: "manufacturing",
            contentSource: d.content_source,
            sourceId: d.source_id,
            chunkId: d.chunk_id || undefined,
            sourceSection: d.source_section || null,
            excerpt: d.excerpt,
          } as CommandAction;
        });

        // Always offer an explicit Ask AI action — it's ranked last so it
        // appears only after all deterministic results.
        const askAi = searchData.ask_ai;
        const askAiActions: CommandAction[] = askAi
          ? [{
              id: askAi.id,
              keywords: [],
              title: askAi.title,
              subtitle: askAi.subtitle,
              icon: "zap",
              type: "ASK_AI",
              roles: [],
              vertical: "manufacturing",
            } as CommandAction]
          : [];

        // When a question was pattern-answered, suppress generic nav/action
        // clutter so the answer and its related records own the results.
        // Ask AI stays in both branches so users can always escalate to AI.
        const sources: CommandAction[][] = wasAnswered
          ? [answerActions, recordActions, docActions, askAiActions]
          : [workflowActions, answerActions, filteredApiResults, recordActions, docActions, localMatches, askAiActions];

        const byId = new Map<string, CommandAction>();
        for (const a of sources.flat()) {
          if (!byId.has(a.id)) byId.set(a.id, a);
        }

        // Sort: WORKFLOW > ANSWER > ACTION > RECORD > DOCUMENT > VIEW > NAV > ASK
        const merged = sortByTypeRank(Array.from(byId.values()));
        setResults(merged.slice(0, 7));
        setSearchOnly(
          filteredApiResults.length === 0 &&
            workflowActions.length === 0 &&
            docActions.length === 0 &&
            recordActions.length === 0 &&
            answerActions.length === 0,
        );
        setSelectedIdx(0);
      } catch (err: unknown) {
        if ((err as { name?: string }).name === "CanceledError") return;
        // Fallback to local match on API error
        setResults(sortByTypeRank(matchLocalActions(q, permittedActions)));
        setSearchOnly(true);
        setSelectedIdx(0);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query, isOpen]);

  const executeAction = useCallback(
    (action: CommandAction) => {
      // Log action
      const recentEntry: RecentAction = {
        id: `${action.id}_${Date.now()}`,
        title: action.title,
        subtitle: action.subtitle,
        icon: action.icon,
        type: action.type,
        action: { id: action.id, route: action.route },
        timestamp: Date.now(),
      };
      addRecentAction(recentEntry);

      // Fire log-action (non-blocking)
      apiClient
        .post("/core/log-action", { action_id: action.id, action_type: action.type })
        .catch(() => {});

      // WORKFLOW — switch to inline controller or NL overlay depending
      // on how many input steps the workflow has.
      if (action.type === "WORKFLOW" && action.workflowId) {
        apiClient
          .get<{
            id: string
            name: string
            overlay_config?: { input_style?: string } | null
            steps?: Array<{
              step_order: number
              step_key: string
              step_type: string
              config?: Record<string, unknown>
            }>
          }>(`/workflows/${action.workflowId}`)
          .then((r) => {
            const wf = r.data
            const inputSteps = (wf.steps || []).filter(
              (s) => s.step_type === "input",
            )
            const useNL =
              wf.overlay_config?.input_style === "natural_language" ||
              inputSteps.length >= 3
            if (useNL) {
              setActiveNLWorkflow({
                id: wf.id,
                name: wf.name,
                steps: wf.steps || [],
              })
            } else {
              setActiveWorkflow({
                id: action.workflowId as string,
                title: action.title,
              })
            }
          })
          .catch(() => {
            // Fallback to the sequential controller if lookup fails
            setActiveWorkflow({
              id: action.workflowId as string,
              title: action.title,
            })
          })
        return;
      }

      // ASK_AI — open the AI panel inline. Only fires when user clicks.
      if (action.type === "ASK_AI") {
        const aiQuery = query.trim();
        if (!aiQuery) return;
        setAiMode({ query: aiQuery, answer: "", loading: true });
        apiClient
          .post<{ answer: string; confidence: number; referenced_record_ids: string[] }>(
            "/core/command-bar/ai",
            { query: aiQuery, history: [] }
          )
          .then((r) => {
            setAiMode({ query: aiQuery, answer: r.data.answer || "", loading: false });
          })
          .catch(() => {
            setAiMode({
              query: aiQuery,
              answer: "Sorry — I couldn't reach Bridgeable AI right now.",
              loading: false,
            });
          });
        return;
      }

      // ANSWER — copy the extracted answer to clipboard and close
      if (action.type === "ANSWER") {
        try {
          void navigator.clipboard?.writeText(action.title);
        } catch { /* clipboard may be unavailable */ }
        onClose();
        return;
      }

      // DOCUMENT — navigate to a viewer per content source (when known).
      // Falls back to copying the excerpt for now.
      if (action.type === "DOCUMENT") {
        const source = action.contentSource
        const sourceId = action.sourceId
        const chunk = action.chunkId
        const query = chunk ? `?highlight=${encodeURIComponent(chunk)}` : ""
        if (source === "kb_article" && sourceId) {
          navigate(`/knowledge-base/articles/${sourceId}${query}`)
          onClose()
          return
        }
        if (source === "safety_program" && sourceId) {
          navigate(`/safety/programs/${sourceId}${query}`)
          onClose()
          return
        }
        // Fallback — copy excerpt
        try {
          void navigator.clipboard?.writeText(action.excerpt || action.title);
        } catch { /* noop */ }
        onClose();
        return;
      }

      if (action.handler) {
        if (typeof action.handler === "function") {
          action.handler();
        }
        // Named string handlers are resolved by the caller for now (future work).
        onClose();
        return;
      }
      if (action.route) {
        navigate(action.route);
        onClose();
        return;
      }
      onClose();
    },
    [navigate, onClose]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      // Option+1..5 (primary — never browser-reserved) or Cmd+1..5 (best-effort).
      // Module-level capture listener in main.tsx fires first, but we also handle
      // here as a safety net for when the browser/OS intercepts Cmd+N before JS.
      const hasAlt = e.altKey && !e.metaKey && !e.ctrlKey && !e.shiftKey;
      const hasCmd = (e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey;
      if (hasAlt || hasCmd) {
        // Prefer e.code (physical key) — Mac Option layer rewrites e.key to
        // special chars (¡™£¢∞…).
        const fromCode = e.code && e.code.startsWith("Digit") ? parseInt(e.code.slice(5), 10) : NaN;
        const fromKey = parseInt(e.key, 10);
        const num = !Number.isNaN(fromCode) && fromCode >= 1 && fromCode <= 5
          ? fromCode
          : (!Number.isNaN(fromKey) && fromKey >= 1 && fromKey <= 5 ? fromKey : null);
        if (num) {
          e.preventDefault();
          e.stopPropagation();
          const native = e.nativeEvent as KeyboardEvent & { stopImmediatePropagation?: () => void };
          native.stopImmediatePropagation?.();
          const r = results[num - 1];
          if (r) executeAction(r);
          return;
        }
      }

      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "Enter") {
        const r = results[selectedIdx];
        if (r) executeAction(r);
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIdx((prev) => Math.min(prev + 1, results.length - 1));
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIdx((prev) => Math.max(prev - 1, 0));
      }
    },
    [results, selectedIdx, executeAction, onClose]
  );

  // Cmd+1..5 quick-pick — implemented at the provider level so the
  // listener is attached once for the app lifetime (not when this
  // component mounts/unmounts). Here we just publish current results
  // and the executor to the provider via setShortcutRefs.
  useEffect(() => {
    setShortcutRefs({ results, execute: executeAction });
  }, [results, executeAction, setShortcutRefs]);

  const toggleVoice = useCallback(async () => {
    if (isListening) {
      stopListening();
    } else {
      const granted = await requestPermission();
      if (granted) startListening();
    }
  }, [isListening, requestPermission, startListening, stopListening]);

  if (!isOpen) return null;

  const showRecent = !query && recentActions.length > 0;
  const displayInterim = isListening && interimTranscript;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      {/* Modal */}
      <div
        className="relative w-full max-w-[640px] mx-4 bg-white rounded-xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Input row */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100">
          <Search className="h-5 w-5 text-gray-400 flex-shrink-0" />
          <input
            ref={inputRef}
            value={displayInterim ? interimTranscript : query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search, create, or ask anything..."
            className="flex-1 text-base outline-none bg-transparent placeholder:text-gray-400 text-gray-900"
            readOnly={isListening}
          />
          {loading && <Loader2 className="h-4 w-4 animate-spin text-gray-400 flex-shrink-0" />}

          {/* Mic button */}
          {showMic && (
            <button
              onClick={toggleVoice}
              className={`flex-shrink-0 rounded-md p-1 transition-colors ${
                isListening
                  ? "bg-red-100 text-red-500"
                  : "text-gray-400 hover:text-gray-600 hover:bg-gray-100"
              }`}
              title={isListening ? "Stop listening" : "Voice input (⌘⇧K)"}
            >
              {isListening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
            </button>
          )}

          <button
            onClick={onClose}
            className="flex-shrink-0 text-gray-400 hover:text-gray-600 rounded-md p-1 hover:bg-gray-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Voice waveform */}
        {isListening && (
          <div className="flex items-center gap-3 px-4 py-2 bg-blue-50 border-b border-blue-100">
            <VoiceWaveform levels={audioLevels} active={isListening} />
            <span className="text-sm text-blue-600">
              {interimTranscript || "Listening..."}
            </span>
          </div>
        )}

        {/* Active natural-language workflow — replaces results view */}
        {activeNLWorkflow && (
          <NaturalLanguageOverlay
            workflow={activeNLWorkflow}
            onComplete={(run) => {
              const outputs = (run.output_data || {}) as Record<string, unknown>;
              for (const key of Object.keys(outputs)) {
                const val = outputs[key] as Record<string, unknown>;
                if (val?.type === "open_slide_over") {
                  setOpenSlideOver({
                    recordType: String(val.record_type),
                    recordId: String(val.record_id),
                    title: activeNLWorkflow.name,
                  });
                }
              }
              setActiveNLWorkflow(null);
              setTimeout(() => onClose(), 400);
            }}
            onCancel={() => {
              setActiveNLWorkflow(null);
              onClose();
            }}
          />
        )}

        {/* Active workflow — replaces results view while running */}
        {!activeNLWorkflow && activeWorkflow && (
          <WorkflowController
            workflowId={activeWorkflow.id}
            workflowTitle={activeWorkflow.title}
            onComplete={(run: WorkflowRunState) => {
              // Handle output actions from the final step
              const outputs = (run.output_data || {}) as Record<string, unknown>;
              for (const key of Object.keys(outputs)) {
                const val = outputs[key] as Record<string, unknown>;
                if (val?.type === "open_slide_over") {
                  setOpenSlideOver({
                    recordType: String(val.record_type),
                    recordId: String(val.record_id),
                    title: activeWorkflow.title,
                  });
                }
              }
              setActiveWorkflow(null);
              // Close the command bar after a successful workflow unless
              // a slide-over is opening — SlideOver lives in its own overlay.
              setTimeout(() => onClose(), 400);
            }}
            onCancel={() => {
              setActiveWorkflow(null);
              onClose();
            }}
          />
        )}

        {/* AI panel — opened when the user selects Ask Bridgeable AI */}
        {!activeWorkflow && !activeNLWorkflow && aiMode && (
          <div className="flex flex-col">
            <div className="flex items-center gap-3 border-b border-gray-100 px-4 py-3">
              <button
                onClick={() => setAiMode(null)}
                className="text-sm font-medium text-gray-500 hover:text-gray-800"
              >
                ← Back
              </button>
              <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
                <span>🤖</span>
                Bridgeable AI
              </div>
            </div>
            <div className="border-b border-gray-100 bg-gray-50 px-4 py-3 text-sm italic text-gray-600">
              "{aiMode.query}"
            </div>
            <div className="max-h-[320px] min-h-[120px] overflow-y-auto px-4 py-4">
              {aiMode.loading ? (
                <div className="flex items-center gap-2 text-sm text-gray-400">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Thinking…
                </div>
              ) : (
                <div className="whitespace-pre-wrap text-sm leading-relaxed text-gray-800">
                  {aiMode.answer}
                </div>
              )}
            </div>
            {!aiMode.loading && aiMode.answer && (
              <div className="flex items-center gap-3 border-t border-gray-100 px-4 py-2">
                <button
                  onClick={() => {
                    try {
                      void navigator.clipboard?.writeText(aiMode.answer)
                    } catch { /* noop */ }
                  }}
                  className="text-xs text-gray-500 hover:text-gray-800"
                >
                  Copy answer
                </button>
              </div>
            )}
          </div>
        )}

        {/* Results */}
        {!activeWorkflow && !activeNLWorkflow && !aiMode && <div className="max-h-[380px] overflow-y-auto">
          {/* Recent actions when empty */}
          {showRecent && (
            <div className="p-2">
              <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
                Recent
              </p>
              {recentActions.slice(0, 5).map((recent, i) => (
                <button
                  key={recent.id}
                  onClick={() => {
                    if (recent.action.route) {
                      navigate(recent.action.route as string);
                      onClose();
                    }
                  }}
                  className="flex w-full items-center gap-3 rounded-md px-2 py-2 text-sm hover:bg-gray-50"
                >
                  <ShortcutBadge n={i + 1} />
                  <ActionIcon icon={recent.icon} />
                  <div className="flex-1 min-w-0 text-left">
                    <p className="font-medium text-gray-800 truncate">{recent.title}</p>
                    {recent.subtitle && (
                      <p className="text-xs text-gray-400 truncate">{recent.subtitle}</p>
                    )}
                  </div>
                  <span className="flex items-center gap-1">
                    <TypeBadge type={recent.type} />
                  </span>
                </button>
              ))}
            </div>
          )}

          {/* Search results */}
          {results.length > 0 && (
            <div className="p-2">
              {searchOnly && (
                <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
                  Local results
                </p>
              )}
              {results.slice(0, 7).map((action, i) => {
                // ANSWER rows can be long — wrap instead of truncating so
                // the full extracted answer is always readable.
                const isAnswer = action.type === "ANSWER"
                const isAskAi = action.type === "ASK_AI"
                // Visual separator above the Ask AI row so it reads as a
                // distinct escape hatch below the deterministic results.
                const prevIsAskAi = i > 0 && results[i - 1]?.type === "ASK_AI"
                const showDividerBefore = isAskAi && !prevIsAskAi && i > 0
                return (
                  <div key={action.id}>
                    {showDividerBefore && (
                      <div className="mx-2 my-1 border-t border-gray-100" />
                    )}
                  <button
                    onClick={() => executeAction(action)}
                    className={`flex w-full gap-3 rounded-md px-2 py-2 text-sm transition-colors ${
                      isAnswer ? "items-start" : "items-center"
                    } ${
                      i === selectedIdx
                        ? "bg-blue-50 text-blue-700"
                        : "hover:bg-gray-50 text-gray-800"
                    }`}
                  >
                    <div className={isAnswer ? "mt-0.5" : ""}>
                      <ShortcutBadge n={i + 1} />
                    </div>
                    <div className={isAnswer ? "mt-0.5" : ""}>
                      <ActionIcon icon={action.icon} />
                    </div>
                    <div className="flex-1 min-w-0 text-left">
                      <p
                        className={`font-medium ${
                          isAnswer ? "whitespace-normal break-words leading-snug" : "truncate"
                        }`}
                      >
                        {action.title}
                      </p>
                      {action.subtitle && (
                        <p
                          className={`text-xs text-gray-400 ${
                            isAnswer ? "whitespace-normal break-words mt-0.5" : "truncate"
                          }`}
                        >
                          {action.subtitle}
                        </p>
                      )}
                    </div>
                    <div className={isAnswer ? "mt-0.5 flex-shrink-0" : "flex-shrink-0"}>
                      <TypeBadge type={action.type} />
                    </div>
                  </button>
                  </div>
                )
              })}
            </div>
          )}

          {/* API answer */}
          {apiAnswer && (
            <div className="mx-2 mb-2 rounded-lg bg-amber-50 p-3 border border-amber-100">
              <p className="text-xs font-semibold text-amber-700 mb-1">Answer</p>
              <p className="text-sm text-gray-800">{apiAnswer}</p>
            </div>
          )}

          {/* Document search loading indicator — shown while docs resolve */}
          {searchingDocs && results.length > 0 && (
            <div className="mx-2 mb-2 flex items-center gap-2 border-t border-dashed border-gray-200 pt-2 text-[11px] text-gray-400">
              <Loader2 className="h-3 w-3 animate-spin" />
              Searching documents…
            </div>
          )}

          {/* Empty state (has query, not loading, no results) */}
          {query.length >= 2 && !loading && !searchingDocs && results.length === 0 && !apiAnswer && (
            <div className="py-8 text-center text-sm text-gray-400">
              No results for &ldquo;{query}&rdquo;
            </div>
          )}
        </div>}

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-gray-100 bg-gray-50 px-4 py-2 text-[10px] text-gray-400">
          <span>↑↓ navigate · Enter select · Esc close · ⌥1–5 quick-pick</span>
          <span className="flex items-center gap-1">
            {searchOnly && (
              <span className="rounded bg-gray-200 px-1 py-0.5 text-[9px] font-medium text-gray-500">
                LOCAL
              </span>
            )}
            Bridgeable AI
          </span>
        </div>
      </div>

      {/* SlideOver triggered by workflow output (stays mounted across command bar close) */}
      {openSlideOver && (
        <SlideOver
          isOpen={true}
          onClose={() => setOpenSlideOver(null)}
          title={openSlideOver.title}
          width="md"
        >
          <div className="space-y-3 text-sm">
            <div className="text-slate-600">
              Record created: <span className="font-mono text-xs">{openSlideOver.recordType}/{openSlideOver.recordId}</span>
            </div>
            <div className="bg-slate-50 border border-slate-200 rounded p-3 text-xs text-slate-500">
              Record editor embedding is coming in Phase W-2. For now, open the record from the matching page.
            </div>
          </div>
        </SlideOver>
      )}
    </div>
  );
}
