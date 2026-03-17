import { useState, useRef, useEffect } from "react";

interface HelpTooltipProps {
  helpKey: string;
  title: string;
  body: string;
  learnMoreUrl?: string;
}

const DISMISSED_KEY = "help_tooltips_dismissed";

function getDismissed(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(DISMISSED_KEY) || "[]"));
  } catch {
    return new Set();
  }
}

function setDismissed(keys: Set<string>) {
  localStorage.setItem(DISMISSED_KEY, JSON.stringify([...keys]));
}

export function HelpTooltip({ helpKey, title, body, learnMoreUrl }: HelpTooltipProps) {
  const [open, setOpen] = useState(false);
  const [hidden, setHidden] = useState(() => getDismissed().has(helpKey));
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  if (hidden) return null;

  return (
    <div ref={ref} className="relative inline-flex">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-muted text-[10px] font-semibold text-muted-foreground hover:bg-muted-foreground/20 transition-colors"
        aria-label={`Help: ${title}`}
      >
        ?
      </button>

      {open && (
        <div className="absolute left-6 top-0 z-50 w-64 rounded-lg border bg-popover p-3 shadow-md animate-in fade-in-0 zoom-in-95">
          <div className="flex items-start justify-between gap-2">
            <h4 className="text-sm font-semibold leading-tight">{title}</h4>
            <button
              type="button"
              onClick={() => {
                const d = getDismissed();
                d.add(helpKey);
                setDismissed(d);
                setHidden(true);
                setOpen(false);
              }}
              className="shrink-0 text-xs text-muted-foreground hover:text-foreground"
              aria-label="Dismiss"
            >
              &times;
            </button>
          </div>
          <p className="mt-1 text-xs text-muted-foreground leading-relaxed">{body}</p>
          {learnMoreUrl && (
            <a
              href={learnMoreUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-block text-xs font-medium text-primary hover:underline"
            >
              Learn more &rarr;
            </a>
          )}
        </div>
      )}
    </div>
  );
}
