import apiClient from "@/lib/api-client";
import type {
  AIAPParseResponse,
  AIInventoryParseResponse,
  AIPromptRequest,
  AIPromptResponse,
} from "@/types/ai";

export const aiService = {
  async sendPrompt(
    systemPrompt: string,
    userMessage: string,
    contextData?: Record<string, unknown>,
  ): Promise<AIPromptResponse> {
    const payload: AIPromptRequest = {
      system_prompt: systemPrompt,
      user_message: userMessage,
    };
    if (contextData) {
      payload.context_data = contextData;
    }
    const response = await apiClient.post<AIPromptResponse>(
      "/ai/prompt",
      payload,
    );
    return response.data;
  },

  async parseInventoryCommand(
    userInput: string,
  ): Promise<AIInventoryParseResponse> {
    const response = await apiClient.post<AIInventoryParseResponse>(
      "/ai/parse-inventory",
      { user_input: userInput },
    );
    return response.data;
  },

  async parseAPCommand(
    userInput: string,
  ): Promise<AIAPParseResponse> {
    const response = await apiClient.post<AIAPParseResponse>(
      "/ai/parse-ap",
      { user_input: userInput },
    );
    return response.data;
  },
};
