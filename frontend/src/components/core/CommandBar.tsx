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
  getRecentActions,
  manufacturingActions,
  matchLocalActions,
} from "@/core/actionRegistry";

// ── Icon map ────────────────────────────────────────────────────────────────

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
  ACTION: "bg-blue-100 text-blue-700",
  VIEW: "bg-slate-100 text-slate-600",
  RECORD: "bg-emerald-100 text-emerald-700",
  NAV: "bg-purple-100 text-purple-700",
  ASK: "bg-amber-100 text-amber-700",
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
  return (
    <span className="flex h-5 w-5 items-center justify-center rounded border border-gray-200 bg-white font-mono text-[10px] text-gray-400 shadow-sm flex-shrink-0">
      {n}
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
  const abortRef = useRef<AbortController | null>(null);

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
        const res = await apiClient.post<CoreCommandResponse>(
          "/core/command",
          { query: q, context: { current_page: window.location.pathname } },
          { signal: controller.signal }
        );

        const data = res.data;
        setSearchOnly(!!data.search_only);
        setApiAnswer(data.answer ?? null);

        if (data.results && data.results.length > 0) {
          // Map API results to CommandAction shape
          const mapped: CommandAction[] = data.results.map((r) => ({
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
          setResults(mapped);
        } else {
          // Fallback to local match
          setResults(matchLocalActions(q, manufacturingActions));
          setSearchOnly(true);
        }
        setSelectedIdx(0);
      } catch (err: unknown) {
        if ((err as { name?: string }).name === "CanceledError") return;
        // Fallback to local match on API error
        setResults(matchLocalActions(q, manufacturingActions));
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

      if (action.handler) {
        action.handler();
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

  // Cmd+1-5 handled in provider via ref callback — expose results via a data attr
  // (Provider reads from CommandBar.currentResults)

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
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
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

        {/* Results */}
        <div className="max-h-[380px] overflow-y-auto">
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
              {results.slice(0, 5).map((action, i) => (
                <button
                  key={action.id}
                  onClick={() => executeAction(action)}
                  className={`flex w-full items-center gap-3 rounded-md px-2 py-2 text-sm transition-colors ${
                    i === selectedIdx
                      ? "bg-blue-50 text-blue-700"
                      : "hover:bg-gray-50 text-gray-800"
                  }`}
                >
                  <ShortcutBadge n={i + 1} />
                  <ActionIcon icon={action.icon} />
                  <div className="flex-1 min-w-0 text-left">
                    <p className="font-medium truncate">{action.title}</p>
                    {action.subtitle && (
                      <p className="text-xs text-gray-400 truncate">{action.subtitle}</p>
                    )}
                  </div>
                  <TypeBadge type={action.type} />
                </button>
              ))}
            </div>
          )}

          {/* API answer */}
          {apiAnswer && (
            <div className="mx-2 mb-2 rounded-lg bg-amber-50 p-3 border border-amber-100">
              <p className="text-xs font-semibold text-amber-700 mb-1">Answer</p>
              <p className="text-sm text-gray-800">{apiAnswer}</p>
            </div>
          )}

          {/* Empty state (has query, not loading, no results) */}
          {query.length >= 2 && !loading && results.length === 0 && !apiAnswer && (
            <div className="py-8 text-center text-sm text-gray-400">
              No results for &ldquo;{query}&rdquo;
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-gray-100 bg-gray-50 px-4 py-2 text-[10px] text-gray-400">
          <span>↑↓ navigate · Enter select · Esc close · ⌘1–5 quick-pick</span>
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
    </div>
  );
}
