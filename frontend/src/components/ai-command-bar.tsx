import { useState } from "react";
import { Loader2Icon, SendIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { getApiErrorMessage } from "@/lib/api-error";
import { aiService } from "@/services/ai-service";

interface AICommandBarProps {
  placeholder: string;
  systemPrompt: string;
  contextData?: Record<string, unknown>;
  onResult: (data: Record<string, unknown>) => void;
  onError?: (error: string) => void;
  disabled?: boolean;
  className?: string;
}

export function AICommandBar({
  placeholder,
  systemPrompt,
  contextData,
  onResult,
  onError,
  disabled = false,
  className,
}: AICommandBarProps) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    try {
      const response = await aiService.sendPrompt(
        systemPrompt,
        trimmed,
        contextData,
      );
      if (response.success && response.data) {
        onResult(response.data);
        setInput("");
      } else {
        const errorMsg =
          response.error || "AI returned an unexpected response";
        if (onError) {
          onError(errorMsg);
        } else {
          toast.error(errorMsg);
        }
      }
    } catch (err: unknown) {
      const errorMsg = getApiErrorMessage(err, "Failed to process AI request");
      if (onError) {
        onError(errorMsg);
      } else {
        toast.error(errorMsg);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className={cn("flex items-center gap-2", className)}
    >
      <Input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder={placeholder}
        disabled={disabled || loading}
        className="flex-1"
      />
      <Button
        type="submit"
        size="icon"
        disabled={disabled || loading || !input.trim()}
      >
        {loading ? (
          <Loader2Icon className="size-4 animate-spin" />
        ) : (
          <SendIcon className="size-4" />
        )}
      </Button>
    </form>
  );
}
