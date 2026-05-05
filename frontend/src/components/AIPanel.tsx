"use client";

import { useState, useRef, useEffect } from "react";
import { useAIChat } from "@/hooks/useAIChat";

type Props = {
  documentText: string;
  selectedText?: string;
  onApplyAction?: (type: string, content: string) => void;
};

const LANGUAGES = [
  "Auto Detect", "English", "Chinese", "Spanish", "French", "German",
  "Japanese", "Korean", "Portuguese", "Russian", "Arabic", "Hindi",
  "Italian", "Dutch", "Polish", "Turkish",
];

type Tab = "chat" | "translate";

export default function AIPanel({ documentText, selectedText = "", onApplyAction }: Props) {
  const { messages, loading, error, sendMessage, translate, clearHistory } = useAIChat();
  const [tab, setTab] = useState<Tab>("chat");
  const [input, setInput] = useState("");
  const [sourceLang, setSourceLang] = useState("Auto Detect");
  const [targetLang, setTargetLang] = useState("English");
  const [translateScope, setTranslateScope] = useState<"selection" | "document">("document");
  const [translatedPreview, setTranslatedPreview] = useState<string | null>(null);
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
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const handleTranslate = async () => {
    const content = translateScope === "selection" && selectedText ? selectedText : documentText;
    if (!content.trim()) return;
    setTranslatedPreview(null);
    const result = await translate(content, sourceLang === "Auto Detect" ? "auto" : sourceLang, targetLang);
    if (result) setTranslatedPreview(result);
  };

  const applyTranslation = (type: "replace_document" | "replace_selection") => {
    if (translatedPreview && onApplyAction) {
      onApplyAction(type, translatedPreview);
      setTranslatedPreview(null);
    }
  };

  const insertBelow = () => {
    if (translatedPreview && onApplyAction) {
      onApplyAction("insert_below", translatedPreview);
      setTranslatedPreview(null);
    }
  };

  return (
    <div className="flex flex-col w-80 min-w-[280px] max-w-[380px] border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-[#1e1e1e] text-sm">
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700 shrink-0">
        <div className="flex gap-1">
          {(["chat", "translate"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${
                tab === t
                  ? "bg-blue-500 text-white"
                  : "text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        {tab === "chat" && (
          <button
            onClick={clearHistory}
            className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            Clear
          </button>
        )}
      </div>

      {tab === "chat" ? (
        <>
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
                <div className="px-3 py-2 rounded-lg text-xs bg-gray-100 dark:bg-[#2d2d2d] text-gray-500">Thinking…</div>
              </div>
            )}
            {error && (
              <div className="text-xs text-red-500 bg-red-50 dark:bg-red-900/20 px-2 py-1 rounded">{error}</div>
            )}
            <div ref={bottomRef} />
          </div>
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
        </>
      ) : (
        <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 dark:text-gray-400">Translate</label>
            <div className="flex gap-1">
              {(["document", "selection"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setTranslateScope(s)}
                  disabled={s === "selection" && !selectedText}
                  className={`flex-1 py-1 text-xs rounded border ${
                    translateScope === s
                      ? "bg-blue-500 text-white border-blue-500"
                      : "border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-[#2d2d2d]"
                  } disabled:opacity-30`}
                >
                  {s === "document" ? "Full Document" : "Selection"}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 dark:text-gray-400">From</label>
            <select
              value={sourceLang}
              onChange={(e) => setSourceLang(e.target.value)}
              className="text-xs p-1.5 border border-gray-200 dark:border-gray-600 rounded bg-gray-50 dark:bg-[#2d2d2d] text-gray-800 dark:text-gray-100"
            >
              {LANGUAGES.map((l) => <option key={l}>{l}</option>)}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 dark:text-gray-400">To</label>
            <select
              value={targetLang}
              onChange={(e) => setTargetLang(e.target.value)}
              className="text-xs p-1.5 border border-gray-200 dark:border-gray-600 rounded bg-gray-50 dark:bg-[#2d2d2d] text-gray-800 dark:text-gray-100"
            >
              {LANGUAGES.filter((l) => l !== "Auto Detect").map((l) => <option key={l}>{l}</option>)}
            </select>
          </div>

          <button
            onClick={handleTranslate}
            disabled={loading || !documentText.trim()}
            className="py-1.5 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-40"
          >
            {loading ? "Translating…" : "Translate"}
          </button>

          {error && (
            <div className="text-xs text-red-500 bg-red-50 dark:bg-red-900/20 px-2 py-1 rounded">{error}</div>
          )}

          {translatedPreview && (
            <div className="flex flex-col gap-2">
              <div className="text-xs text-gray-500 dark:text-gray-400 font-medium">Preview</div>
              <div className="text-xs bg-gray-50 dark:bg-[#2d2d2d] border border-gray-200 dark:border-gray-600 rounded p-2 max-h-48 overflow-y-auto whitespace-pre-wrap text-gray-800 dark:text-gray-100">
                {translatedPreview}
              </div>
              <div className="flex flex-col gap-1">
                <button
                  onClick={() => applyTranslation("replace_document")}
                  className="py-1 text-xs bg-green-500 text-white rounded hover:bg-green-600"
                >
                  Replace Document
                </button>
                {selectedText && (
                  <button
                    onClick={() => applyTranslation("replace_selection")}
                    className="py-1 text-xs bg-yellow-500 text-white rounded hover:bg-yellow-600"
                  >
                    Replace Selection
                  </button>
                )}
                <button
                  onClick={insertBelow}
                  className="py-1 text-xs border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-[#2d2d2d] text-gray-700 dark:text-gray-300"
                >
                  Insert Below
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}