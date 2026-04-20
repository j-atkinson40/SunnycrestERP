/**
 * AIQuestionPanel — first interactive context panel in the triage
 * workspace. Phase 5 shipped the pluggable panel architecture; only
 * document_preview was wired. Follow-up 2 wires this, establishing
 * the precedent for future interactive panels (communication_thread,
 * fully-interactive related_entities) when they land post-arc.
 *
 * UX pattern:
 *   - Suggested-question chips at the top (from panel config); click
 *     to populate input.
 *   - Textarea for the question with max-length counter.
 *   - Submit on click OR ⌘↵ / Ctrl+↵.
 *   - Session question history below — per-item, most recent first.
 *     Cleared when `itemId` changes (via useEffect).
 *   - Loading dot while waiting; friendly toast-style inline error
 *     on failure with retry.
 *   - Rate-limit responses surface as a specific friendly copy
 *     ("Pausing AI questions for a moment — try again in Ns").
 *
 * Keyboard-focus discipline:
 *   The `useTriageKeyboard` hook already suppresses triage shortcuts
 *   when focus is on INPUT/TEXTAREA/SELECT/contenteditable
 *   (`hooks/useTriageKeyboard.ts:36-41`). Our textarea inherits that
 *   protection — pressing Enter or "n" while typing a question does
 *   NOT fire the Skip action. Verified by unit test.
 */

import {
  type FormEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { AlertCircle, CheckCircle2, Circle, Loader2, Send } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  askQuestion,
  TriageRateLimitedError,
} from "@/services/triage-service";
import type {
  ConfidenceTier,
  TriageContextPanelConfig,
  TriageQuestionAnswer,
} from "@/types/triage";
import { cn } from "@/lib/utils";

interface Props {
  panel: TriageContextPanelConfig;
  sessionId: string;
  itemId: string;
}

interface HistoryEntry {
  id: string;
  answer: TriageQuestionAnswer;
}

const DEFAULT_MAX_LENGTH = 500;

export function AIQuestionPanel({ panel, sessionId, itemId }: Props) {
  const maxLength = panel.max_question_length ?? DEFAULT_MAX_LENGTH;
  const suggestions = panel.suggested_questions ?? [];

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Per-item history reset — the panel is not re-mounted when the
  // user navigates to the next item (parent re-renders with a new
  // itemId prop), so clear state on itemId change. This matches the
  // approved scope: history is session+item-local, ephemeral.
  useEffect(() => {
    setHistory([]);
    setError(null);
    setInput("");
  }, [itemId]);

  const submit = useCallback(
    async (questionText: string) => {
      const trimmed = questionText.trim();
      if (!trimmed) return;
      setLoading(true);
      setError(null);
      try {
        const answer = await askQuestion(sessionId, itemId, trimmed);
        setHistory((prev) => [
          { id: answer.execution_id, answer },
          ...prev,
        ]);
        setInput("");
      } catch (err) {
        if (err instanceof TriageRateLimitedError) {
          setError(err.friendlyMessage);
        } else {
          const axiosLike = err as {
            response?: { data?: { detail?: unknown } };
          };
          const detail = axiosLike?.response?.data?.detail;
          setError(
            typeof detail === "string"
              ? detail
              : "Couldn't get an answer — please try again.",
          );
        }
      } finally {
        setLoading(false);
      }
    },
    [sessionId, itemId],
  );

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    void submit(input);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // ⌘↵ (Meta) or Ctrl+↵ submits without a form-submit round-trip.
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      void submit(input);
    }
  };

  const handleSuggestion = (suggestion: string) => {
    setInput(suggestion);
    textareaRef.current?.focus();
  };

  const retry = () => {
    if (history[0]) {
      void submit(history[0].answer.question);
    } else {
      setError(null);
    }
  };

  const tooLong = input.length > maxLength;

  return (
    <div className="space-y-3" data-testid="ai-question-panel">
      {suggestions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => handleSuggestion(s)}
              className="rounded-full border bg-muted/50 px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
              data-testid="ai-question-suggestion"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-2">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={2}
          placeholder="Ask a question about this item…"
          className={cn(
            "min-h-[44px] w-full resize-none rounded-md border bg-background px-2.5 py-1.5 text-sm",
            "focus:outline-none focus:ring-2 focus:ring-[color:var(--space-accent,var(--preset-accent))]",
            tooLong && "border-destructive",
          )}
          disabled={loading}
          aria-label="Ask a question about this item"
          data-testid="ai-question-input"
        />
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <kbd className="rounded border bg-muted px-1 py-0.5 text-[10px]">⌘↵</kbd>
            to submit
          </span>
          <div className="flex items-center gap-3">
            <span
              className={cn(
                "tabular-nums",
                tooLong && "text-destructive font-medium",
              )}
              data-testid="ai-question-counter"
            >
              {input.length}/{maxLength}
            </span>
            <Button
              type="submit"
              size="sm"
              disabled={loading || !input.trim() || tooLong}
              className="h-7 gap-1.5"
              data-testid="ai-question-submit"
            >
              {loading ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Send className="size-3.5" />
              )}
              Ask
            </Button>
          </div>
        </div>
      </form>

      {error && (
        <div
          className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-2 text-xs text-amber-900"
          role="alert"
          data-testid="ai-question-error"
        >
          <AlertCircle className="mt-0.5 size-3.5 shrink-0" />
          <div className="flex-1">
            <p>{error}</p>
            <button
              type="button"
              onClick={retry}
              className="mt-1 text-amber-900 underline hover:no-underline"
              data-testid="ai-question-retry"
            >
              Try again
            </button>
          </div>
        </div>
      )}

      {history.length > 0 && (
        <div
          className="space-y-3 border-t pt-2.5"
          data-testid="ai-question-history"
        >
          {history.map((entry) => (
            <AnswerCard key={entry.id} answer={entry.answer} />
          ))}
        </div>
      )}

      {history.length === 0 && !error && !loading && (
        <p className="text-xs text-muted-foreground">
          Ask about priority, history, context — answers are grounded in
          this item and related records.
        </p>
      )}
    </div>
  );
}

// ── Answer card ────────────────────────────────────────────────────

function AnswerCard({ answer }: { answer: TriageQuestionAnswer }) {
  return (
    <div className="space-y-1.5" data-testid="ai-question-answer">
      <p className="text-xs font-medium text-muted-foreground">
        {answer.question}
      </p>
      <p className="text-sm text-foreground whitespace-pre-wrap">
        {answer.answer}
      </p>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
        <ConfidenceDot tier={answer.confidence} />
        <span>
          {new Date(answer.asked_at).toLocaleTimeString([], {
            hour: "numeric",
            minute: "2-digit",
          })}{" "}
          · {Math.round(answer.latency_ms)} ms
        </span>
      </div>
      {answer.source_references.length > 0 && (
        <div
          className="flex flex-wrap gap-1.5 pt-1"
          data-testid="ai-question-sources"
        >
          {answer.source_references.map((s) => (
            <SourceChip
              key={`${s.entity_type}-${s.entity_id}`}
              source={s}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ConfidenceDot({ tier }: { tier: ConfidenceTier }) {
  const label = `${tier.charAt(0).toUpperCase()}${tier.slice(1)} confidence`;
  if (tier === "high") {
    return (
      <span
        className="inline-flex items-center gap-1"
        title={label}
        data-testid="ai-question-confidence-high"
      >
        <CheckCircle2 className="size-3 text-emerald-600" />
        High confidence
      </span>
    );
  }
  if (tier === "medium") {
    return (
      <span
        className="inline-flex items-center gap-1"
        title={label}
        data-testid="ai-question-confidence-medium"
      >
        <Circle className="size-3 fill-amber-400 stroke-amber-500" />
        Medium confidence
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1"
      title={label}
      data-testid="ai-question-confidence-low"
    >
      <Circle className="size-3 fill-muted stroke-muted-foreground" />
      Low confidence
    </span>
  );
}

function SourceChip({
  source,
}: {
  source: { entity_type: string; entity_id: string; display_label: string; snippet?: string | null };
}) {
  const href = _sourceHref(source.entity_type, source.entity_id);
  const content = (
    <span className="inline-flex items-center gap-1 rounded-full border bg-muted/30 px-2 py-0.5 text-[11px] hover:bg-muted">
      <span className="font-medium">{source.display_label}</span>
      <span className="text-muted-foreground">{source.entity_type}</span>
    </span>
  );
  if (href) {
    return (
      <a
        href={href}
        className="no-underline"
        title={source.snippet ?? undefined}
        data-testid="ai-question-source-link"
      >
        {content}
      </a>
    );
  }
  return (
    <span title={source.snippet ?? undefined} data-testid="ai-question-source">
      {content}
    </span>
  );
}

// Best-effort routing table for source-reference click-throughs. If
// an entity type doesn't have a known route here the chip renders as
// non-clickable rather than generating a 404.
function _sourceHref(entityType: string, entityId: string): string | null {
  const safe = encodeURIComponent(entityId);
  switch (entityType) {
    case "task":
      return `/tasks/${safe}`;
    case "sales_order":
      return `/order-station/orders/${safe}`;
    case "social_service_certificate":
      return `/social-service-certificates`;
    case "customer":
      return `/vault/crm/companies/${safe}`;
    case "fh_case":
    case "case":
      return `/fh/cases/${safe}`;
    case "invoice":
      return `/ar/invoices/${safe}`;
    case "contact":
      return `/vault/crm/contacts/${safe}`;
    default:
      return null;
  }
}
