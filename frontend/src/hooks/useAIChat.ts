"use client";

import { useRef, useState, useCallback, useLayoutEffect } from "react";
import { AI, type AgentChatPayload, type AgentResponse } from "@/lib/api";
import { splitTextIntoTranslationUnits } from "@/lib/translation-units.mjs";
import { createDocumentRequestGuard } from "@/lib/work-result-guard.mjs";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  proposedAction?: AgentResponse["proposed_action"];
  provider?: string;
  sources?: AgentResponse["used_sources"];
};

export type TranslationPair = {
  source: string;
  translated: string;
};

export type TranslationProgress = {
  currentBatch: number;
  totalBatches: number;
};

let _msgCounter = 0;
const msgId = () => `msg-${++_msgCounter}`;
const SENTENCE_BATCH_CHAR_LIMIT = 3000;

function batchTranslationUnits(units: string[]) {
  const batches: string[][] = [];
  let current: string[] = [];
  let currentSize = 0;
  for (const unit of units) {
    if (current.length && currentSize + unit.length > SENTENCE_BATCH_CHAR_LIMIT) {
      batches.push(current);
      current = [];
      currentSize = 0;
    }
    current.push(unit);
    currentSize += unit.length;
  }
  if (current.length) batches.push(current);
  return batches;
}

export function useAIChat(documentId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastOperation, setLastOperation] = useState<"chat" | "translation" | null>(null);
  const translationAbortRef = useRef<AbortController | null>(null);
  const requestGuard = useRef(createDocumentRequestGuard(documentId));

  useLayoutEffect(() => {
    if (!requestGuard.current.setDocument(documentId)) return;
    translationAbortRef.current?.abort();
    translationAbortRef.current = null;
    setMessages([]);
    setLoading(false);
    setError(null);
  }, [documentId]);

  const sendMessage = useCallback(
    async (
      userMessage: string,
      documentText = "",
      selectedText = "",
      options?: { useKnowledgeBase?: boolean; knowledgeTopK?: number }
    ) => {
      if (!userMessage.trim()) return;

      setLastOperation("chat");
      const request = requestGuard.current.issue();
      const userMsg: ChatMessage = { id: msgId(), role: "user", content: userMessage };
      setMessages((prev) => [...prev, userMsg]);
      setLoading(true);
      setError(null);

      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      const payload: AgentChatPayload = {
        message: userMessage,
        document_text: documentText,
        selected_text: selectedText,
        chat_history: history,
        use_knowledge_base: options?.useKnowledgeBase,
        knowledge_top_k: options?.knowledgeTopK,
      };

      try {
        const result = await AI.chat(payload);
        if (!requestGuard.current.isCurrent(request)) return;
        const assistantMsg: ChatMessage = {
          id: msgId(),
          role: "assistant",
          content: result.assistant_message,
          proposedAction: result.proposed_action,
          provider: result.used_provider,
          sources: result.used_sources,
        };
        setMessages((prev) => [...prev, assistantMsg]);
        return result;
      } catch (err) {
        if (requestGuard.current.isCurrent(request)) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (requestGuard.current.isCurrent(request)) setLoading(false);
      }
    },
    [messages]
  );

  const translate = useCallback(
    async (
      content: string,
      sourceLang: string,
      targetLang: string,
      prepare?: () => Promise<void>
    ): Promise<string | null> => {
      setLastOperation("translation");
      const request = requestGuard.current.issue();
      setLoading(true);
      setError(null);
      try {
        if (prepare) await prepare();
        const result = await AI.translate(content, sourceLang, targetLang);
        if (!requestGuard.current.isCurrent(request)) return null;
        return result.translated;
      } catch (err) {
        if (requestGuard.current.isCurrent(request)) {
          setError(err instanceof Error ? err.message : String(err));
        }
        return null;
      } finally {
        if (requestGuard.current.isCurrent(request)) setLoading(false);
      }
    },
    []
  );

  const translateSentences = useCallback(
    async (
      content: string,
      sourceLang: string,
      targetLang: string,
      onProgress?: (progress: TranslationProgress) => void,
      prepare?: () => Promise<void>
    ): Promise<{ translated: string; pairs: TranslationPair[] } | null> => {
      setLastOperation("translation");
      const request = requestGuard.current.issue();
      setLoading(true);
      setError(null);
      translationAbortRef.current?.abort();
      const abortController = new AbortController();
      translationAbortRef.current = abortController;
      const pairs: TranslationPair[] = [];
      try {
        if (prepare) await prepare();
        const batches = batchTranslationUnits(splitTextIntoTranslationUnits(content));
        onProgress?.({ currentBatch: 0, totalBatches: batches.length });
        for (let index = 0; index < batches.length; index += 1) {
          if (abortController.signal.aborted || !requestGuard.current.isCurrent(request)) break;
          onProgress?.({ currentBatch: index + 1, totalBatches: batches.length });
          let result: { pairs: TranslationPair[] };
          try {
            result = await AI.translateSentenceBatch(
              batches[index],
              sourceLang,
              targetLang,
              abortController.signal
            );
          } catch (err) {
            if (abortController.signal.aborted) break;
            throw err;
          }
          if (!requestGuard.current.isCurrent(request)) return null;
          pairs.push(...result.pairs);
        }
        if (!requestGuard.current.isCurrent(request)) return null;
        const result = {
          pairs,
          translated: pairs.map((pair) => pair.translated).join("\n\n"),
        };
        return result;
      } catch (err) {
        if (abortController.signal.aborted) {
          return {
            pairs,
            translated: pairs.map((pair) => pair.translated).join("\n\n"),
          };
        }
        if (requestGuard.current.isCurrent(request)) {
          setError(err instanceof Error ? err.message : String(err));
        }
        return null;
      } finally {
        if (translationAbortRef.current === abortController) {
          translationAbortRef.current = null;
        }
        if (requestGuard.current.isCurrent(request)) setLoading(false);
      }
    },
    []
  );

  const cancelTranslation = useCallback(() => {
    translationAbortRef.current?.abort();
  }, []);

  const clearHistory = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return { messages, loading, error, lastOperation, sendMessage, translate, translateSentences, cancelTranslation, clearHistory };
}
