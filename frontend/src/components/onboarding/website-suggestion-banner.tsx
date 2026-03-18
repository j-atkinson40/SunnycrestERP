import { useState } from "react";
import { Globe, X } from "lucide-react";

interface WebsiteSuggestionBannerProps {
  extensionKey: string;
  label: string;
  evidence: string | null;
  confidenceLabel: string;
  hasSuggestions: boolean;
}

export function WebsiteSuggestionBanner(props: WebsiteSuggestionBannerProps) {
  const [dismissed, setDismissed] = useState(false);

  if (!props.hasSuggestions || dismissed) return null;

  return (
    <div className="mb-6 rounded-lg border border-teal-200 bg-teal-50 p-4">
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <Globe className="mt-0.5 h-5 w-5 shrink-0 text-teal-600" />
          <div>
            <p className="text-sm font-medium text-teal-900">
              Based on your website, we know you carry {props.label} products
            </p>
            <p className="mt-1 text-sm text-teal-700">
              We've pre-selected common items to get you started — just set your
              prices.
            </p>
            {props.evidence && (
              <p className="mt-2 text-xs italic text-teal-600">
                Found on your website: &ldquo;{props.evidence}&rdquo;
              </p>
            )}
          </div>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="text-teal-400 hover:text-teal-600"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
