// SmartPlantCommandBar.tsx — Touch-first voice command bar for plant environments

import { useCallback, useEffect, useState } from "react";
import { CheckCircle, Keyboard, Loader2, Mic, RotateCcw, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { useMicrophone } from "@/hooks/useMicrophone";
import { getActionsForVertical, matchLocalActions } from "@/services/actions";

// ── Types ─────────────────────────────────────────────────────────────────────

type ConfidenceLevel = "high" | "medium" | "low" | "idle";

interface PlantCommandResult {
  id: string;
  title: string;
  subtitle?: string;
  route?: string;
  confidence: number;
}

// ── Waveform ──────────────────────────────────────────────────────────────────

function PlantWaveform({ levels, active }: { levels: number[]; active: boolean }) {
  return (
    <div className="flex items-end gap-1 h-16 justify-center">
      {levels.map((level, i) => {
        const height = active ? Math.max(8, Math.round(level * 56)) : 8;
        return (
          <div
            key={i}
            className="w-2 rounded-full bg-blue-400 transition-all duration-75"
            style={{ height: `${height}px` }}
          />
        );
      })}
    </div>
  );
}

// ── Component ──────────────────────────────────────────────────────────────────

interface SmartPlantCommandBarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function SmartPlantCommandBar({ isOpen, onClose }: SmartPlantCommandBarProps) {
  const navigate = useNavigate();
  const [phase, setPhase] = useState<ConfidenceLevel>("idle");
  const [results, setResults] = useState<PlantCommandResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyboardMode, setKeyboardMode] = useState(false);
  const [keyboardQuery, setKeyboardQuery] = useState("");

  const { requestPermission } = useMicrophone();

  const processTranscript = useCallback(
    async (transcript: string) => {
      setLoading(true);
      try {
        // Try API first
        const res = await apiClient.post<{
          results: Array<{ id: string; title: string; subtitle?: string; route?: string; confidence?: number }>;
        }>("/core/command", {
          query: transcript,
          context: { source: "plant_bar", current_page: window.location.pathname },
        });

        const apiResults = res.data.results ?? [];
        if (apiResults.length > 0) {
          const mapped: PlantCommandResult[] = apiResults.map((r, i) => ({
            id: r.id,
            title: r.title,
            subtitle: r.subtitle,
            route: r.route,
            confidence: r.confidence ?? (i === 0 ? 0.9 : 0.7),
          }));

          const top = mapped[0];
          if (top.confidence >= 0.92) {
            setPhase("high");
            setResults([top]);
          } else if (top.confidence >= 0.7) {
            setPhase("medium");
            setResults(mapped.slice(0, 2));
          } else {
            setPhase("low");
            setResults(mapped.slice(0, 3));
          }
          return;
        }
      } catch {
        // fall through to local match
      }

      // Local fallback — SmartPlant runs on manufacturing tenants only,
      // so we pull the manufacturing slice directly rather than
      // threading a vertical prop through the plant-mode UI.
      const localMatches = matchLocalActions(
        transcript,
        getActionsForVertical("manufacturing"),
        3,
      );
      if (localMatches.length === 0) {
        setPhase("low");
        setResults([]);
      } else {
        // Assign synthetic confidence
        const scored: PlantCommandResult[] = localMatches.map((a, i) => ({
          id: a.id,
          title: a.title,
          subtitle: a.subtitle,
          route: a.route,
          confidence: i === 0 ? 0.75 : 0.6,
        }));
        const top = scored[0];
        if (top.confidence >= 0.92) {
          setPhase("high");
          setResults([top]);
        } else {
          setPhase("medium");
          setResults(scored.slice(0, 2));
        }
      }
    },
    []
  );

  const handleVoiceResult = useCallback(
    async (transcript: string) => {
      await processTranscript(transcript);
      setLoading(false);
    },
    [processTranscript]
  );

  const { isListening, interimTranscript, audioLevels, startListening, stopListening } =
    useVoiceInput({ onResult: handleVoiceResult });

  // Auto-execute high-confidence result
  useEffect(() => {
    if (phase !== "high" || results.length === 0) return;
    const r = results[0];
    toast.success(`Executing: ${r.title}`);
    const timer = setTimeout(() => {
      if (r.route) navigate(r.route);
      onClose();
    }, 1200);
    return () => clearTimeout(timer);
  }, [phase, results, navigate, onClose]);

  const handleMicTap = useCallback(async () => {
    if (isListening) {
      stopListening();
      return;
    }
    setPhase("idle");
    setResults([]);
    setLoading(false);
    const granted = await requestPermission();
    if (granted) {
      startListening();
    }
  }, [isListening, requestPermission, startListening, stopListening]);

  const handleKeyboardSubmit = useCallback(async () => {
    if (!keyboardQuery.trim()) return;
    setLoading(true);
    await processTranscript(keyboardQuery);
    setLoading(false);
  }, [keyboardQuery, processTranscript]);

  const handleRetry = useCallback(() => {
    setPhase("idle");
    setResults([]);
    setKeyboardQuery("");
    setKeyboardMode(false);
  }, []);

  const executeResult = useCallback(
    (result: PlantCommandResult) => {
      if (result.route) {
        navigate(result.route);
      }
      onClose();
    },
    [navigate, onClose]
  );

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-gray-900 flex flex-col items-center justify-center p-6">
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute right-4 top-4 rounded-full p-2 text-gray-400 hover:bg-gray-800 hover:text-white"
      >
        <X className="h-6 w-6" />
      </button>

      {/* Idle / listening state */}
      {(phase === "idle" || isListening) && !loading && (
        <div className="flex flex-col items-center gap-6">
          {/* Waveform while listening */}
          {isListening && (
            <PlantWaveform levels={audioLevels} active={isListening} />
          )}

          {/* Interim transcript */}
          {isListening && interimTranscript && (
            <p className="text-xl text-gray-300 text-center max-w-sm">
              {interimTranscript}
            </p>
          )}

          {/* Main mic button */}
          <button
            onClick={handleMicTap}
            className={`flex h-32 w-32 items-center justify-center rounded-full shadow-2xl transition-all active:scale-95 ${
              isListening
                ? "bg-red-500 hover:bg-red-400 ring-4 ring-red-300/40 animate-pulse"
                : "bg-blue-600 hover:bg-blue-500"
            }`}
          >
            <Mic className="h-16 w-16 text-white" />
          </button>

          <p className="text-lg text-gray-300">
            {isListening ? "Listening — tap to stop" : "Tap to speak"}
          </p>

          {/* Keyboard fallback */}
          {!isListening && (
            <button
              onClick={() => setKeyboardMode(true)}
              className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm text-gray-400 hover:bg-gray-800 hover:text-white"
            >
              <Keyboard className="h-4 w-4" />
              Use keyboard instead
            </button>
          )}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-12 w-12 animate-spin text-blue-400" />
          <p className="text-lg text-gray-300">Processing...</p>
        </div>
      )}

      {/* High confidence — auto-executing */}
      {phase === "high" && results.length > 0 && !loading && (
        <div className="flex flex-col items-center gap-6 text-center">
          <CheckCircle className="h-16 w-16 text-green-400" />
          <div>
            <p className="text-2xl font-bold text-white">{results[0].title}</p>
            {results[0].subtitle && (
              <p className="mt-1 text-gray-400">{results[0].subtitle}</p>
            )}
          </div>
          <p className="text-gray-400">Executing automatically...</p>
        </div>
      )}

      {/* Medium confidence — two large touch buttons */}
      {phase === "medium" && results.length > 0 && !loading && (
        <div className="flex flex-col items-center gap-6 w-full max-w-sm">
          <p className="text-xl text-gray-200 font-semibold">Did you mean?</p>
          <div className="flex flex-col gap-3 w-full">
            {results.map((r) => (
              <button
                key={r.id}
                onClick={() => executeResult(r)}
                className="w-full rounded-2xl bg-blue-600 px-6 py-5 text-left hover:bg-blue-500 active:scale-98 transition-all"
              >
                <p className="text-xl font-bold text-white">{r.title}</p>
                {r.subtitle && <p className="mt-1 text-blue-200 text-sm">{r.subtitle}</p>}
              </button>
            ))}
          </div>
          <button
            onClick={handleRetry}
            className="flex items-center gap-2 text-gray-400 hover:text-white"
          >
            <RotateCcw className="h-4 w-4" />
            Try again
          </button>
        </div>
      )}

      {/* Low confidence — keyboard input */}
      {(phase === "low" || keyboardMode) && !loading && (
        <div className="flex flex-col items-center gap-6 w-full max-w-sm">
          {phase === "low" && (
            <p className="text-lg text-gray-300">I didn&apos;t catch that clearly</p>
          )}
          <input
            type="text"
            value={keyboardQuery}
            onChange={(e) => setKeyboardQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleKeyboardSubmit()}
            placeholder="Type what you need..."
            autoFocus
            className="w-full rounded-2xl bg-gray-800 px-5 py-4 text-xl text-white placeholder:text-gray-500 outline-none ring-2 ring-blue-500 focus:ring-blue-400"
          />
          <div className="flex gap-3 w-full">
            <button
              onClick={handleKeyboardSubmit}
              className="flex-1 rounded-2xl bg-blue-600 py-4 text-lg font-semibold text-white hover:bg-blue-500 active:scale-98"
            >
              Search
            </button>
            <button
              onClick={handleMicTap}
              className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gray-700 text-gray-300 hover:bg-gray-600"
            >
              <Mic className="h-6 w-6" />
            </button>
          </div>
          <button
            onClick={handleRetry}
            className="flex items-center gap-2 text-gray-400 hover:text-white text-sm"
          >
            <RotateCcw className="h-4 w-4" />
            Start over
          </button>
        </div>
      )}
    </div>
  );
}
