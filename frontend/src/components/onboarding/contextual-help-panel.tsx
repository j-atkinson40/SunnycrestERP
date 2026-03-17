import { useState, useEffect, useCallback } from "react";
import { useLocation } from "react-router-dom";

// ── Help content keyed by route prefix ─────────────────────────

const HELP_CONTENT: Record<
  string,
  { title: string; sections: Array<{ heading: string; body: string }> }
> = {
  "/orders": {
    title: "Creating Orders",
    sections: [
      {
        heading: "Quick Start",
        body: "Click 'New Order' to start. Select a customer, add products, set a delivery date, and confirm.",
      },
      {
        heading: "Delivery Types",
        body: "Funeral vault deliveries require coordination with the funeral home and cemetery. Standard deliveries go directly to job sites.",
      },
      {
        heading: "Pricing",
        body: "Prices pull automatically from your product catalog. You can override prices on individual line items if needed.",
      },
    ],
  },
  "/production": {
    title: "Production Board",
    sections: [
      {
        heading: "How Work Orders Flow",
        body: "Work orders start in Draft, move to Open when released, then progress through Scheduled, In Progress, Curing, QC, and Complete.",
      },
      {
        heading: "Pour Events",
        body: "A pour event represents a single production run. It can include items from multiple work orders using the same mix design.",
      },
      {
        heading: "Cure Tracking",
        body: "After pouring, products appear on the cure board with countdown timers. Standard concrete reaches 70% strength in 7 days.",
      },
    ],
  },
  "/delivery": {
    title: "Delivery Scheduling",
    sections: [
      {
        heading: "Dispatch Board",
        body: "Drag unscheduled deliveries onto driver routes to schedule them. The system checks vehicle capacity and driver availability.",
      },
      {
        heading: "SMS Confirmation",
        body: "Drivers confirm deliveries by texting keywords -- DELIVERED, PICKED, or ISSUE. No app installation required.",
      },
      {
        heading: "Funeral Vault Deliveries",
        body: "Vault deliveries include funeral home and cemetery coordination. Time-sensitive deliveries are highlighted in red.",
      },
    ],
  },
  "/safety": {
    title: "Safety Module",
    sections: [
      {
        heading: "Getting Started",
        body: "Start by setting up your safety programs and inspection checklists. The system tracks OSHA recordables and generates your 300 log automatically.",
      },
      {
        heading: "Inspections",
        body: "Create inspection templates for equipment, facilities, and PPE. Assign inspections on a schedule -- daily, weekly, or monthly.",
      },
      {
        heading: "LOTO Procedures",
        body: "Document lockout/tagout procedures for each machine. Track authorized vs affected employees for compliance.",
      },
    ],
  },
  "/funeral-home": {
    title: "Funeral Home Module",
    sections: [
      {
        heading: "Case Management",
        body: "Each case represents a decedent and their family. Track the case from first call through final disposition.",
      },
      {
        heading: "FTC Compliance",
        body: "The FTC Funeral Rule requires itemized pricing and specific disclosures. Your General Price List (GPL) is generated automatically.",
      },
      {
        heading: "Vault Ordering",
        body: "Order vaults directly from your manufacturer through the platform. Orders are tracked from placement through delivery.",
      },
    ],
  },
  "/inventory": {
    title: "Inventory Management",
    sections: [
      {
        heading: "Stock Levels",
        body: "View current stock for every product. Set minimum levels to get alerts when stock runs low.",
      },
      {
        heading: "Production Entry",
        body: "Record daily production -- units produced go into inventory automatically after QC approval.",
      },
      {
        heading: "Sage Export",
        body: "Inventory transactions export to Sage-formatted CSV for your accounting team.",
      },
    ],
  },
};

// ── Helpers ─────────────────────────────────────────────────────

const VISIT_KEY = "contextual_help_visits";
const MAX_AUTO_OPEN_VISITS = 3;

function getVisitCount(): number {
  return parseInt(localStorage.getItem(VISIT_KEY) || "0", 10);
}

function incrementVisitCount(): number {
  const n = getVisitCount() + 1;
  localStorage.setItem(VISIT_KEY, String(n));
  return n;
}

function matchRoute(pathname: string): string | null {
  for (const key of Object.keys(HELP_CONTENT)) {
    if (pathname === key || pathname.startsWith(key + "/")) return key;
  }
  return null;
}

// ── Component ──────────────────────────────────────────────────

export function ContextualHelpPanel() {
  const location = useLocation();
  const [isOpen, setIsOpen] = useState(false);
  const [matchedKey, setMatchedKey] = useState<string | null>(null);

  // Match route and auto-open for new tenants
  useEffect(() => {
    const key = matchRoute(location.pathname);
    setMatchedKey(key);

    if (key) {
      const visits = incrementVisitCount();
      if (visits <= MAX_AUTO_OPEN_VISITS) {
        setIsOpen(true);
      }
    } else {
      setIsOpen(false);
    }
  }, [location.pathname]);

  const content = matchedKey ? HELP_CONTENT[matchedKey] : null;

  const toggle = useCallback(() => setIsOpen((o) => !o), []);

  // No help available for this route
  if (!content) return null;

  return (
    <>
      {/* Floating help button */}
      {!isOpen && (
        <button
          type="button"
          onClick={toggle}
          className="fixed bottom-6 right-6 z-40 flex h-10 w-10 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/90 transition-colors"
          aria-label="Open help panel"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
            <path d="M12 17h.01" />
          </svg>
        </button>
      )}

      {/* Slide-in panel */}
      {isOpen && (
        <aside className="fixed right-0 top-0 z-50 flex h-full w-[300px] flex-col border-l bg-background shadow-xl animate-in slide-in-from-right duration-200">
          {/* Header */}
          <div className="flex items-center justify-between border-b px-4 py-3">
            <h2 className="text-sm font-semibold">{content.title}</h2>
            <button
              type="button"
              onClick={toggle}
              className="text-muted-foreground hover:text-foreground transition-colors"
              aria-label="Close help panel"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M18 6 6 18" />
                <path d="m6 6 12 12" />
              </svg>
            </button>
          </div>

          {/* Sections */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">
            {content.sections.map((section, i) => (
              <div key={i}>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
                  {section.heading}
                </h3>
                <p className="text-sm leading-relaxed text-foreground/80">
                  {section.body}
                </p>
              </div>
            ))}
          </div>

          {/* Footer */}
          <div className="border-t px-4 py-3">
            <p className="text-[11px] text-muted-foreground">
              This panel auto-opens for the first {MAX_AUTO_OPEN_VISITS} visits. Click the
              &nbsp;<span className="font-semibold">?</span>&nbsp;button to reopen any time.
            </p>
          </div>
        </aside>
      )}
    </>
  );
}
