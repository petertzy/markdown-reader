"use client";

import { useRef, useState, useCallback } from "react";
import { AI, type AgentChatPayload, type AgentResponse } from "@/lib/api";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  proposedAction?: AgentResponse["proposed_action"];
  provider?: string;
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
const SENTENCE_END_CHARS = ".!?。！？";

function splitTextIntoTranslationUnits(content: string) {
  const text = content.trim();
  if (!text) return [];
  const units: string[] = [];
  let buffer = "";
  let inCodeBlock = false;

  const flush = () => {
    const unit = buffer.trim();
    if (unit) units.push(unit);
    buffer = "";
  };

  const lines = text.split(/\r?\n/);
  lines.forEach((line, lineIndex) => {
    const stripped = line.trim();
    if (stripped.startsWith("```")) {
      if (!inCodeBlock) {
        flush();
        buffer = line;
        inCodeBlock = true;
      } else {
        buffer += `\n${line}`;
        flush();
        inCodeBlock = false;
      }
      return;
    }
    if (inCodeBlock) {
      buffer += `${buffer ? "\n" : ""}${line}`;
      return;
    }
    if (!stripped) {
      flush();
      return;
    }
    if (/^(#{1,6}\s|>\s|[-*+]\s|\d+\.\s)/.test(stripped)) {
      flush();
      units.push(line);
      return;
    }
    for (let index = 0; index < line.length; index += 1) {
      const char = line[index];
      const nextChar = line[index + 1] ?? "";
      buffer += char;
      if (SENTENCE_END_CHARS.includes(char) && ["", " ", "\t", "\"", "'", ")", "]"].includes(nextChar)) {
        flush();
      }
    }
    if (lineIndex < lines.length - 1 && buffer) buffer += " ";
  });
  flush();
  return units;
}

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

export function useAIChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const translationAbortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (userMessage: string, documentText = "", selectedText = "") => {
      if (!userMessage.trim()) return;

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
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setLoading(false);
      }
    },
    [messages]
  );

  const translate = useCallback(
    async (
      content: string,
      sourceLang: string,
      targetLang: string
    ): Promise<string | null> => {
      setLoading(true);
      setError(null);
      const userMsg: ChatMessage = {
        id: msgId(),
        role: "user",
        content: `Translate ${sourceLang === "auto" ? "" : `from ${sourceLang} `}to ${targetLang}:\n\n${content.slice(0, 120)}${content.length > 120 ? "…" : ""}`,
      };
      setMessages((prev) => [...prev, userMsg]);
      try {
        const result = await AI.translate(content, sourceLang, targetLang);
        const assistantMsg: ChatMessage = {
          id: msgId(),
          role: "assistant",
          content: `Translation complete (→ ${targetLang}).`,
          proposedAction: { type: "replace_document", content: result.translated, reason: "translated" },
        };
        setMessages((prev) => [...prev, assistantMsg]);
        return result.translated;
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        return null;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const translateSentences = useCallback(
    async (
      content: string,
      sourceLang: string,
      targetLang: string,
      onProgress?: (progress: TranslationProgress) => void
    ): Promise<{ translated: string; pairs: TranslationPair[] } | null> => {
      setLoading(true);
      setError(null);
      translationAbortRef.current?.abort();
      const abortController = new AbortController();
      translationAbortRef.current = abortController;
      const userMsg: ChatMessage = {
        id: msgId(),
        role: "user",
        content: `Translate sentence by sentence ${sourceLang === "auto" ? "" : `from ${sourceLang} `}to ${targetLang}:\n\n${content.slice(0, 120)}${content.length > 120 ? "…" : ""}`,
      };
      setMessages((prev) => [...prev, userMsg]);
      try {
        const batches = batchTranslationUnits(splitTextIntoTranslationUnits(content));
        onProgress?.({ currentBatch: 0, totalBatches: batches.length });
        const pairs: TranslationPair[] = [];
        for (let index = 0; index < batches.length; index += 1) {
          if (abortController.signal.aborted) break;
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
          pairs.push(...result.pairs);
        }
        const stopped = abortController.signal.aborted;
        const result = {
          pairs,
          translated: pairs.map((pair) => pair.translated).join("\n\n"),
        };
        const assistantMsg: ChatMessage = {
          id: msgId(),
          role: "assistant",
          content: stopped
            ? `Sentence-by-sentence translation stopped (${pairs.length} pair${pairs.length === 1 ? "" : "s"} translated).`
            : `Sentence-by-sentence translation complete (→ ${targetLang}).`,
          proposedAction: { type: "replace_document", content: result.translated, reason: "translated_sentences" },
        };
        if (pairs.length || !stopped) {
          setMessages((prev) => [...prev, assistantMsg]);
        }
        return result;
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        return null;
      } finally {
        if (translationAbortRef.current === abortController) {
          translationAbortRef.current = null;
        }
        setLoading(false);
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

  return { messages, loading, error, sendMessage, translate, translateSentences, cancelTranslation, clearHistory };
}
