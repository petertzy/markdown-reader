"use client";

/**
 * AIPanel.tsx
 * ===========
 * Slide-in AI assistant panel.
 */

import { useState, useRef, useEffect } from "react";
import { useAIChat } from "@/hooks/useAIChat";

type Props = {
  documentText: string;
  selectedText?: string;
  onApplyAction?: (type: string, content: string) => void;
};

export default function AIPanel({ documentText, selectedText = "", onApplyAction }: Props) {
  const { messages, loading, error, sendMessage, clearHistory } = useAIChat();
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || loading) return;
    setInput("");
    await sendMessage(msg, documentText, selectedText);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col w-80 min-w-[280px] max-w-[380px] border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-[#1e1e1e] text-sm">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700 shrink-0">
        <span className="font-semibold text-gray-700 dark:text-gray-200">AI Assistant</span>
        <button
          onClick={clearHistory}
          className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          title="Clear history"
        >
          Clear
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 && (
          <p className="text-gray-400 dark:text-gray-500 text-xs">
            Ask me to summarize, generate a TOC, translate, fix code blocks, or anything else…
          </p>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`flex flex-col gap-1 ${msg.role === "user" ? "items-end" : "items-start"}`}>
            <div
              className={`px-3 py-2 rounded-lg text-xs max-w-full whitespace-pre-wrap break-words ${
                msg.role === "user"
                  ? "bg-blue-500 text-white"
                  : "bg-gray-100 dark:bg-[#2d2d2d] text-gray-800 dark:text-gray-100"
              }`}
            >
              {msg.content}
            </div>
            {msg.proposedAction && msg.proposedAction.type !== "none" && onApplyAction && (
              <button
                onClick={() => onApplyAction(msg.proposedAction!.type, msg.proposedAction!.content)}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
              >
                ✅ Apply: {msg.proposedAction.type === "replace_document" ? "Replace document" : "Replace selection"}
              </button>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex items-start">
            <div className="px-3 py-2 rounded-lg text-xs bg-gray-100 dark:bg-[#2d2d2d] text-gray-500">
              Thinking…
            </div>
          </div>
        )}
        {error && (
          <div className="text-xs text-red-500 bg-red-50 dark:bg-red-900/20 px-2 py-1 rounded">
            {error}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 dark:border-gray-700 p-2 shrink-0">
        <div className="flex gap-1">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask AI… (Enter to send, Shift+Enter for newline)"
            rows={3}
            className="flex-1 resize-none text-xs p-2 border border-gray-200 dark:border-gray-600 rounded bg-gray-50 dark:bg-[#2d2d2d] text-gray-800 dark:text-gray-100 focus:outline-none focus:border-blue-400"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="px-2 self-end py-1.5 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
