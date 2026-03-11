export interface AIPromptRequest {
  system_prompt: string;
  user_message: string;
  context_data?: Record<string, unknown> | null;
}

export interface AIPromptResponse {
  success: boolean;
  data: Record<string, unknown> | null;
  error: string | null;
}
