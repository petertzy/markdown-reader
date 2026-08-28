"use client";

import { useState, useRef, useEffect, type ReactNode } from "react";
import { useAIChat } from "@/hooks/useAIChat";
import { AI, getDefaultAISettings, type AISettings } from "@/lib/api";

export type AIPanelTab = "chat" | "translate" | "settings";
type Tab = AIPanelTab;

type Props = {
  documentText: string;
  selectedText?: string;
  onApplyAction?: (type: string, content: string) => void;
  /** Force the panel to switch to this tab (e.g. deep-linking from a slash command) */
  initialTab?: Tab;
};

const LANGUAGES = [
  "Auto Detect", "English", "Chinese", "Spanish", "French", "German",
  "Japanese", "Korean", "Portuguese", "Russian", "Arabic", "Hindi",
  "Italian", "Dutch", "Polish", "Turkish",
];

const INSERT_TABLE_MARKDOWN =
  "| Column 1 | Column 2 | Column 3 |\n| --- | --- | --- |\n| Cell | Cell | Cell |";

const CHAT_SLASH_PROMPTS: Record<string, string> = {
  "/summarize": "generate summary",
  "/format": "format this section",
  "/toc": "generate table of contents",
  "/fix-code": "format code blocks and correct syntax",
};

function normalizeBaseUrl(url: string) {
  return url.trim().replace(/\/+$/, "");
}

function renderInlineMarkdown(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)|(https?:\/\/[^\s]+))/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    if (match[2]) {
      nodes.push(<strong key={match.index}>{match[2]}</strong>);
    } else if (match[3]) {
      nodes.push(
        <code
          key={match.index}
          className="rounded bg-black/10 dark:bg-white/10 px-1 py-0.5 font-mono text-[11px]"
        >
          {match[3]}
        </code>
      );
    } else {
      const label = match[4] ?? match[6];
      const href = match[5] ?? match[6];
      nodes.push(
        <a
          key={match.index}
          href={href}
          target="_blank"
          rel="noreferrer"
          className="underline underline-offset-2 hover:text-blue-600 dark:hover:text-blue-300"
        >
          {label}
        </a>
      );
    }

    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}

function ChatMessageContent({ content }: { content: string }) {
  const blocks: ReactNode[] = [];
  const paragraphLines: string[] = [];
  let listItems: string[] = [];
  let codeLines: string[] = [];
  let inCodeBlock = false;

  const flushParagraph = () => {
    if (!paragraphLines.length) return;
    const text = paragraphLines.join(" ");
    blocks.push(
      <p key={`p-${blocks.length}`} className="mb-2 last:mb-0">
        {renderInlineMarkdown(text)}
      </p>
    );
    paragraphLines.length = 0;
  };

  const flushList = () => {
    if (!listItems.length) return;
    blocks.push(
      <ul key={`ul-${blocks.length}`} className="mb-2 list-disc space-y-1 pl-4 last:mb-0">
        {listItems.map((item, index) => (
          <li key={index}>{renderInlineMarkdown(item)}</li>
        ))}
      </ul>
    );
    listItems = [];
  };

  const flushCodeBlock = () => {
    blocks.push(
      <pre
        key={`pre-${blocks.length}`}
        className="mb-2 overflow-x-auto rounded border border-gray-200 bg-gray-50 p-2 font-mono text-[11px] leading-relaxed dark:border-gray-600 dark:bg-[#242424]"
      >
        <code>{codeLines.join("\n")}</code>
      </pre>
    );
    codeLines = [];
  };

  for (const line of content.split(/\r?\n/)) {
    if (line.trim().startsWith("```")) {
      flushParagraph();
      flushList();
      if (inCodeBlock) {
        flushCodeBlock();
      }
      inCodeBlock = !inCodeBlock;
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    const listMatch = line.match(/^\s*[-*]\s+(.+)$/);
    if (listMatch) {
      flushParagraph();
      listItems.push(listMatch[1]);
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }

    flushList();
    paragraphLines.push(line.trim());
  }

  flushParagraph();
  flushList();
  if (inCodeBlock || codeLines.length) {
    flushCodeBlock();
  }

  return <>{blocks}</>;
}

export default function AIPanel({
  documentText,
  selectedText = "",
  onApplyAction,
  initialTab,
}: Props) {
  const { messages, loading, error, sendMessage, translate, clearHistory } = useAIChat();
  const [tab, setTab] = useState<Tab>(initialTab ?? "chat");

  useEffect(() => {
    if (initialTab) setTab(initialTab);
  }, [initialTab]);

  const [input, setInput] = useState("");
  const [sourceLang, setSourceLang] = useState("Auto Detect");
  const [targetLang, setTargetLang] = useState("English");
  const [translateScope, setTranslateScope] = useState<"selection" | "document">("document");
  const [translatedPreview, setTranslatedPreview] = useState<string | null>(null);
  const [settings, setSettings] = useState<AISettings>(() => getDefaultAISettings());
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [modelsFetching, setModelsFetching] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null);
  const [provider, setProvider] = useState("openai_compatible");
  const [baseUrlChoice, setBaseUrlChoice] = useState("navidia");
  const [localBaseUrlChoice, setLocalBaseUrlChoice] = useState("lm_studio");
  const [localBaseUrl, setLocalBaseUrl] = useState("http://127.0.0.1:1234/v1");
  const [model, setModel] = useState("");
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [apiKey, setApiKey] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const settingsRequestSeq = useRef(0);
  const modelRequestSeq = useRef(0);
  const providerRef = useRef(provider);
  const localBaseUrlChoiceRef = useRef(localBaseUrlChoice);
  const localBaseUrlRef = useRef(localBaseUrl);

  const currentLocalBaseUrl = () => {
    const choice = localBaseUrlChoiceRef.current;
    const customUrl = localBaseUrlRef.current;
    const optionUrl =
      settings?.local_ai_base_url_options.find((item) => item.key === choice)?.url ??
      "";
    return choice === "custom" ? customUrl : optionUrl;
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (tab !== "settings") return;
    void loadSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const selectedBaseUrl = () => {
    return settings?.openai_compatible_base_url_options.find((item) => item.key === baseUrlChoice)?.url ?? "";
  };

  const selectedLocalBaseUrl = (
    choice = localBaseUrlChoice,
    customUrl = localBaseUrl
  ) => {
    const optionUrl =
      settings?.local_ai_base_url_options.find((item) => item.key === choice)?.url ??
      "";
    return choice === "custom" ? customUrl : optionUrl;
  };

  const syncSettingsForm = (nextSettings: AISettings) => {
    const nextProvider = nextSettings.ai_provider || nextSettings.provider_order[0] || "openai_compatible";
    const nextModel = nextSettings.providers[nextProvider]?.model ?? "";
    const nextLocalChoice = nextSettings.local_ai_base_url_choice || "lm_studio";
    const nextLocalBaseUrl =
      nextSettings.local_ai_custom_base_url ||
      nextSettings.local_ai_base_url ||
      "http://127.0.0.1:1234/v1";
    setSettings(nextSettings);
    setProvider(nextProvider);
    setBaseUrlChoice(nextSettings.openai_compatible_base_url_choice || "navidia");
    setLocalBaseUrlChoice(nextLocalChoice);
    setLocalBaseUrl(nextLocalBaseUrl);
    providerRef.current = nextProvider;
    localBaseUrlChoiceRef.current = nextLocalChoice;
    localBaseUrlRef.current = nextLocalBaseUrl;
    if (nextProvider === "local") {
      setModel("");
      setModelOptions([]);
    } else {
      setModel(nextModel);
      setModelOptions(Array.from(new Set(nextSettings.providers[nextProvider]?.default_models ?? [])));
    }
    setApiKey("");
  };

  const loadSettings = async () => {
    const requestId = ++settingsRequestSeq.current;
    setSettingsLoading(true);
    setSettingsMessage(null);
    try {
      const nextSettings = await AI.getSettings();
      if (requestId === settingsRequestSeq.current) {
        syncSettingsForm(nextSettings);
        if (nextSettings.ai_provider === "local") {
          const nextLocalChoice = nextSettings.local_ai_base_url_choice || "lm_studio";
          const nextLocalBaseUrl =
            nextSettings.local_ai_custom_base_url ||
            nextSettings.local_ai_base_url ||
            "http://127.0.0.1:1234/v1";
          if (nextLocalChoice !== "custom" || nextLocalBaseUrl.trim()) {
            void refreshModelOptions(
              "local",
              nextSettings.openai_compatible_base_url_choice || "navidia",
              nextLocalChoice,
              nextLocalBaseUrl
            );
          }
        }
      }
    } catch (err) {
      if (requestId === settingsRequestSeq.current) {
        setSettingsMessage(err instanceof Error ? err.message : String(err));
      }
    } finally {
      if (requestId === settingsRequestSeq.current) {
        setSettingsLoading(false);
      }
    }
  };

  const refreshModelOptions = async (
    nextProvider = provider,
    nextBaseChoice = baseUrlChoice,
    nextLocalChoice = localBaseUrlChoice,
    nextLocalBaseUrl = localBaseUrl
  ) => {
    const requestId = ++modelRequestSeq.current;
    const baseUrl =
      nextProvider === "openai_compatible"
        ? settings?.openai_compatible_base_url_options.find((item) => item.key === nextBaseChoice)?.url ?? ""
        : nextProvider === "local"
          ? selectedLocalBaseUrl(nextLocalChoice, nextLocalBaseUrl)
        : "";
    if (nextProvider === "local" && !baseUrl.trim()) {
      setModelOptions([]);
      setModel("");
      setSettingsMessage("Enter a custom Base URL before fetching models.");
      return;
    }
    setSettingsMessage(null);
    setModelsFetching(true);
    try {
      const result = apiKey.trim()
        ? await AI.fetchModelsWithKey(nextProvider, apiKey.trim(), baseUrl)
        : await AI.getModels(nextProvider, baseUrl);
      if (requestId !== modelRequestSeq.current) return;
      if (
        nextProvider === "local" &&
        (providerRef.current !== "local" ||
          normalizeBaseUrl(baseUrl) !== normalizeBaseUrl(currentLocalBaseUrl()))
      ) {
        return;
      }
      const models = Array.from(new Set(result.models));
      setModelOptions(models);
      if (models.length > 0 && !models.includes(model)) {
        setModel(models[0]);
      } else if (models.length === 0) {
        setModel("");
      }
      setSettingsMessage(result.message || `${models.length} models available.`);
    } catch (err) {
      if (requestId === modelRequestSeq.current) {
        setSettingsMessage(err instanceof Error ? err.message : String(err));
      }
    } finally {
      if (requestId === modelRequestSeq.current) {
        setModelsFetching(false);
      }
    }
  };

  const handleProviderChange = (nextProvider: string) => {
    modelRequestSeq.current += 1;
    setProvider(nextProvider);
    providerRef.current = nextProvider;
    const nextModels = Array.from(new Set(settings?.providers[nextProvider]?.default_models ?? []));
    setModelOptions(nextProvider === "local" ? [] : nextModels);
    setModel(nextProvider === "local" ? "" : settings?.providers[nextProvider]?.model || nextModels[0] || "");
    setApiKey("");
    if (nextProvider === "local") {
      setLocalBaseUrlChoice("lm_studio");
      setLocalBaseUrl("http://127.0.0.1:1234/v1");
      localBaseUrlChoiceRef.current = "lm_studio";
      localBaseUrlRef.current = "http://127.0.0.1:1234/v1";
      setSettingsMessage(null);
      void AI.setLocalAIBaseUrlChoice("lm_studio").catch((err) => {
        setSettingsMessage(err instanceof Error ? err.message : String(err));
      });
    }
    void AI.setProvider(nextProvider).catch((err) => {
      setSettingsMessage(err instanceof Error ? err.message : String(err));
    });
    if (nextProvider !== "local") {
      void refreshModelOptions(nextProvider, baseUrlChoice);
    }
  };

  const handleBaseUrlChange = (nextChoice: string) => {
    modelRequestSeq.current += 1;
    setBaseUrlChoice(nextChoice);
    if (provider === "openai_compatible") {
      void refreshModelOptions(provider, nextChoice);
    }
  };

  const handleLocalBaseUrlChoiceChange = (nextChoice: string) => {
    modelRequestSeq.current += 1;
    setLocalBaseUrlChoice(nextChoice);
    const optionUrl = settings?.local_ai_base_url_options.find((item) => item.key === nextChoice)?.url;
    const nextLocalBaseUrl = optionUrl || localBaseUrl;
    if (optionUrl) {
      setLocalBaseUrl(optionUrl);
    }
    localBaseUrlChoiceRef.current = nextChoice;
    localBaseUrlRef.current = nextLocalBaseUrl;
    setModelOptions([]);
    setModel("");
    setSettingsMessage(
      nextChoice === "custom"
        ? "Enter a custom Base URL before fetching models."
        : "Fetching models..."
    );
    if (nextChoice !== "custom") {
      void refreshModelOptions("local", baseUrlChoice, nextChoice, nextLocalBaseUrl);
    }
  };

  const handleFetchModels = async () => {
    settingsRequestSeq.current += 1;
    setSettingsLoading(false);
    if (provider === "local") {
      const currentLocalBaseUrl = selectedLocalBaseUrl(localBaseUrlChoice, localBaseUrl);
      if (!currentLocalBaseUrl.trim()) {
        setModelOptions([]);
        setModel("");
        setSettingsMessage("Enter a custom Base URL before fetching models.");
        return;
      }
      await AI.setProvider(provider);
      await AI.setLocalAIBaseUrlChoice(localBaseUrlChoice, currentLocalBaseUrl);
      await refreshModelOptions(
        provider,
        baseUrlChoice,
        localBaseUrlChoice,
        currentLocalBaseUrl
      );
      return;
    }
    await refreshModelOptions();
  };

  const saveSettings = async () => {
    setSettingsSaving(true);
    setSettingsMessage(null);
    try {
      if (provider === "openai_compatible") {
        await AI.setOpenAICompatibleBaseUrlChoice(baseUrlChoice);
      }
      if (provider === "local") {
        await AI.setLocalAIBaseUrlChoice(localBaseUrlChoice, localBaseUrl);
      }
      if (apiKey.trim()) {
        await AI.saveApiKey(provider, apiKey.trim());
      }
      if (model.trim()) {
        await AI.setModel(provider, model.trim());
      }
      await AI.setProvider(provider);
      syncSettingsForm(await AI.getSettings());
      setSettingsMessage("Settings saved.");
    } catch (err) {
      setSettingsMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setSettingsSaving(false);
    }
  };

  const deleteKey = async () => {
    setSettingsSaving(true);
    setSettingsMessage(null);
    try {
      const keyProvider =
        provider === "openai_compatible" ? `openai_compatible_${baseUrlChoice}` : provider;
      await AI.deleteApiKey(keyProvider);
      await AI.setProvider(provider);
      setApiKey("");
      syncSettingsForm(await AI.getSettings());
      setSettingsMessage("Stored key deleted.");
    } catch (err) {
      setSettingsMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setSettingsSaving(false);
    }
  };

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || loading) return;
    setInput("");
    const slashCommand = msg.toLowerCase();
    if (slashCommand === "/translate") {
      setTab("translate");
      return;
    }
    if (slashCommand === "/insert-table") {
      onApplyAction?.("replace_selection", INSERT_TABLE_MARKDOWN);
      return;
    }
    const slashPrompt = CHAT_SLASH_PROMPTS[slashCommand];
    if (slashPrompt) {
      await sendMessage(slashPrompt, documentText, selectedText);
      return;
    }
    await sendMessage(msg, documentText, selectedText);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const handleTranslate = async () => {
    const content = translateScope === "selection" && selectedText ? selectedText : documentText;
    if (!content.trim()) return;
    setTranslatedPreview(null);
    if (provider === "local") {
      await AI.setProvider(provider);
      await AI.setLocalAIBaseUrlChoice(localBaseUrlChoice, localBaseUrl);
    }
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
      const actionType =
        translateScope === "selection" && selectedText
          ? "insert_below_selection"
          : "insert_below_document";
      onApplyAction(actionType, translatedPreview);
      setTranslatedPreview(null);
    }
  };

  return (
    <div className="flex flex-col w-80 min-w-[280px] max-w-[380px] border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-[#1e1e1e] text-sm">
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700 shrink-0">
        <div className="flex gap-1">
          {(["chat", "translate", "settings"] as Tab[]).map((t) => (
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
                Try /summarize, /translate, /format, /toc, /fix-code, or /insert-table.
              </p>
            )}
            {messages.map((msg) => (
              <div key={msg.id} className={`flex flex-col gap-1 ${msg.role === "user" ? "items-end" : "items-start"}`}>
                <div
                  className={`px-3 py-2 rounded-lg text-xs max-w-full break-words ${
                    msg.role === "user"
                      ? "bg-blue-500 text-white"
                      : "bg-gray-100 dark:bg-[#2d2d2d] text-gray-800 dark:text-gray-100"
                  }`}
                >
                  {msg.role === "assistant" ? (
                    <ChatMessageContent content={msg.content} />
                  ) : (
                    <span className="whitespace-pre-wrap">{msg.content}</span>
                  )}
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
      ) : tab === "translate" ? (
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
      ) : (
        <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="text-xs font-semibold text-gray-700 dark:text-gray-200">AI Provider</div>
            <button
              onClick={() => { void loadSettings(); }}
              disabled={settingsLoading}
              className="text-xs text-blue-600 dark:text-blue-400 hover:underline disabled:opacity-40"
            >
              Refresh
            </button>
          </div>

          {settingsLoading && (
            <div className="text-xs text-gray-500 dark:text-gray-400">Loading settings...</div>
          )}

          {settingsMessage && (
            <div
              className={`text-xs px-2 py-1 rounded ${
                settingsMessage.toLowerCase().includes("error") ||
                settingsMessage.toLowerCase().includes("api ")
                  ? "text-red-500 bg-red-50 dark:bg-red-900/20"
                  : "text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-[#2d2d2d]"
              }`}
            >
              {settingsMessage}
            </div>
          )}

          {settings && (
            <>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500 dark:text-gray-400">Provider</label>
                <select
                  value={provider}
                  onChange={(e) => handleProviderChange(e.target.value)}
                  className="text-xs p-1.5 border border-gray-200 dark:border-gray-600 rounded bg-gray-50 dark:bg-[#2d2d2d] text-gray-800 dark:text-gray-100"
                >
                  {settings.provider_order.map((name) => (
                    <option key={name} value={name}>
                      {settings.providers[name]?.display_name ?? name}
                    </option>
                  ))}
                </select>
              </div>

              {provider === "openai_compatible" && (
                <div className="flex flex-col gap-1">
                  <label className="text-xs text-gray-500 dark:text-gray-400">Base URL</label>
                  <select
                    value={baseUrlChoice}
                    onChange={(e) => handleBaseUrlChange(e.target.value)}
                    className="text-xs p-1.5 border border-gray-200 dark:border-gray-600 rounded bg-gray-50 dark:bg-[#2d2d2d] text-gray-800 dark:text-gray-100"
                  >
                    {settings.openai_compatible_base_url_options.map((item) => (
                      <option key={item.key} value={item.key}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                  <div className="text-[11px] text-gray-400 dark:text-gray-500 break-all">
                    {selectedBaseUrl()}
                  </div>
                </div>
              )}

              {provider === "local" && (
                <div className="flex flex-col gap-1">
                  <label className="text-xs text-gray-500 dark:text-gray-400">Local Provider</label>
                  <select
                    value={localBaseUrlChoice}
                    onChange={(e) => handleLocalBaseUrlChoiceChange(e.target.value)}
                    className="text-xs p-1.5 border border-gray-200 dark:border-gray-600 rounded bg-gray-50 dark:bg-[#2d2d2d] text-gray-800 dark:text-gray-100"
                  >
                    {settings.local_ai_base_url_options.map((item) => (
                      <option key={item.key} value={item.key}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                  {localBaseUrlChoice === "custom" ? (
                    <input
                      type="text"
                      value={localBaseUrl}
                      onChange={(e) => {
                        const nextCustomBaseUrl = e.target.value;
                        setLocalBaseUrl(nextCustomBaseUrl);
                        localBaseUrlRef.current = nextCustomBaseUrl;
                        setModelOptions([]);
                        setModel("");
                        setSettingsMessage(
                          nextCustomBaseUrl.trim()
                            ? "Fetch models from the custom endpoint."
                            : "Enter a custom Base URL before fetching models."
                        );
                      }}
                      placeholder="http://127.0.0.1:1234/v1"
                      className="text-xs p-1.5 border border-gray-200 dark:border-gray-600 rounded bg-gray-50 dark:bg-[#2d2d2d] text-gray-800 dark:text-gray-100"
                    />
                  ) : (
                    <div className="text-[11px] text-gray-400 dark:text-gray-500 break-all">
                      {selectedLocalBaseUrl()}
                    </div>
                  )}
                  <div className="text-[11px] text-gray-400 dark:text-gray-500 break-all">
                    Fetch URL: {selectedLocalBaseUrl() || "Not configured"}
                  </div>
                </div>
              )}

              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500 dark:text-gray-400">Model</label>
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="text-xs p-1.5 border border-gray-200 dark:border-gray-600 rounded bg-gray-50 dark:bg-[#2d2d2d] text-gray-800 dark:text-gray-100"
                >
                  {provider !== "local" && model && !modelOptions.includes(model) && (
                    <option value={model}>{model}</option>
                  )}
                  {modelOptions.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                  {provider === "local" && modelOptions.length === 0 && (
                    <option value="">No models loaded</option>
                  )}
                </select>
              </div>

              <button
                onClick={() => { void handleFetchModels(); }}
                disabled={modelsFetching}
                className="py-1 text-xs border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-[#2d2d2d] text-gray-700 dark:text-gray-300 disabled:opacity-40"
              >
                {modelsFetching ? "Fetching..." : "Fetch Models"}
              </button>

              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500 dark:text-gray-400">API Key</label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={
                    provider === "local"
                      ? "Optional for local endpoints"
                      : settings.providers[provider]?.key_configured
                      ? "Stored key is configured"
                      : "Enter API key"
                  }
                  className="text-xs p-1.5 border border-gray-200 dark:border-gray-600 rounded bg-gray-50 dark:bg-[#2d2d2d] text-gray-800 dark:text-gray-100"
                />
                <div className="text-[11px] text-gray-400 dark:text-gray-500">
                  {settings.secure_key_storage_available
                    ? "Keys are saved in the system credential store."
                    : "Secure key storage is not available on this system."}
                </div>
              </div>

              <div className="flex gap-2 pt-1">
                <button
                  onClick={() => { void deleteKey(); }}
                  disabled={settingsSaving}
                  className="flex-1 py-1.5 text-xs border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-[#2d2d2d] text-gray-700 dark:text-gray-300 disabled:opacity-40"
                >
                  Delete Key
                </button>
                <button
                  onClick={() => { void saveSettings(); }}
                  disabled={settingsSaving || !model.trim()}
                  className="flex-1 py-1.5 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-40"
                >
                  {settingsSaving ? "Saving..." : "Save"}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
