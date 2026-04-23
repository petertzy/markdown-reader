"use client";

import { useState, useCallback } from "react";
import { AI, type AgentChatPayload, type AgentResponse } from "@/lib/api";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  proposedAction?: AgentResponse["proposed_action"];
  provider?: string;
};

let _msgCounter = 0;
const msgId = () => `msg-${++_msgCounter}`;

export function useAIChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (
      userMessage: string,
      documentText = "",
      selectedText = ""
    ) => {
      if (!userMessage.trim()) return;

      const userMsg: ChatMessage = {
        id: msgId(),
        role: "user",
        content: userMessage,
      };

      setMessages((prev) => [...prev, userMsg]);
      setLoading(true);
      setError(null);

      const history = messages.map((m) => ({ role: m.role, content: m.content }));

      const payload: AgentChatPayload = {
        message: userMessage,
        document_text: documentText,
        selected_text: selectedText,
        chat_history: history,
      };

      try {
        const result = await AI.chat(payload);
        const assistantMsg: ChatMessage = {
          id: msgId(),
          role: "assistant",
          content: result.assistant_message,
          proposedAction: result.proposed_action,
          provider: result.used_provider,
        };
        setMessages((prev) => [...prev, assistantMsg]);
        return result;
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
      } finally {
        setLoading(false);
      }
    },
    [messages]
  );

  const clearHistory = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return { messages, loading, error, sendMessage, clearHistory };
}
