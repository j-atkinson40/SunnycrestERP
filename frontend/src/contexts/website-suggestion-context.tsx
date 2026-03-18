import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import * as intelligenceService from "@/services/website-intelligence-service";
import type {
  WebsiteIntelligence,
  WebsiteSuggestion,
  SuggestedProduct,
} from "@/types/website-intelligence";

interface WebsiteSuggestionContextValue {
  intelligence: WebsiteIntelligence | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

const WebsiteSuggestionContext =
  createContext<WebsiteSuggestionContextValue | null>(null);

export function WebsiteSuggestionProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [intelligence, setIntelligence] =
    useState<WebsiteIntelligence | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const data = await intelligenceService.getIntelligence();
    setIntelligence(data);
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <WebsiteSuggestionContext.Provider value={{ intelligence, loading, refresh }}>
      {children}
    </WebsiteSuggestionContext.Provider>
  );
}

export function useWebsiteSuggestionContext() {
  return useContext(WebsiteSuggestionContext);
}

/**
 * Hook for extension catalog builders to get website-based suggestions
 * for a specific extension key.
 */
export function useWebsiteSuggestions(extensionKey: string) {
  const [suggestions, setSuggestions] = useState<WebsiteSuggestion[]>([]);

  useEffect(() => {
    intelligenceService
      .getSuggestionsForExtension(extensionKey)
      .then(setSuggestions)
      .catch(() => {});
  }, [extensionKey]);

  const accepted = suggestions.some((s) => s.status === "accepted");
  const evidence = suggestions.find((s) => s.evidence)?.evidence ?? null;
  const confidence = suggestions[0]?.confidence ?? 0;

  const confidenceLabel =
    confidence >= 0.9
      ? "High confidence"
      : confidence >= 0.7
        ? "Likely"
        : "Possible";

  const suggestedProducts: SuggestedProduct[] = suggestions
    .filter((s) => s.status === "accepted")
    .map((s) => ({
      product_key: s.suggestion_key,
      confidence: s.confidence,
      should_precheck: s.confidence >= 0.85,
      should_highlight: s.confidence >= 0.7 && s.confidence < 0.85,
    }));

  return {
    hasSuggestions: suggestions.length > 0,
    accepted,
    evidence,
    confidence,
    confidenceLabel,
    suggestedProducts,
    bannerProps: {
      extensionKey,
      label: suggestions[0]?.suggestion_label ?? extensionKey,
      evidence,
      confidenceLabel,
      hasSuggestions: suggestions.length > 0,
    },
  };
}
