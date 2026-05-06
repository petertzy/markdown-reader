"use client";

import { useState, useRef, useEffect } from "react";
import { useAIChat } from "@/hooks/useAIChat";
import { AI, type AISettings } from "@/lib/api";

type Props = {
  documentText: string;
  selectedText?: string;
  onApplyAction?: (type: string, content: string) => void;
  requestedTab?: Tab;
  tabRequestId?: number;
};

const LANGUAGES = [
  "Auto Detect", "English", "Chinese", "Spanish", "French", "German",
  "Japanese", "Korean", "Portuguese", "Russian", "Arabic", "Hindi",
  "Italian", "Dutch", "Polish", "Turkish",
];

export type Tab = "chat" | "translate" | "settings";

export default function AIPanel({
  documentText,
  selectedText = "",
  onApplyAction,
  requestedTab,
  tabRequestId = 0,
}: Props) {
  const { messages, loading, error, sendMessage, translate, clearHistory } = useAIChat();
  const [tab, setTab] = useState<Tab>(requestedTab ?? "chat");
  const [input, setInput] = useState("");
  const [sourceLang, setSourceLang] = useState("Auto Detect");
  const [targetLang, setTargetLang] = useState("English");
  const [translateScope, setTranslateScope] = useState<"selection" | "document">("document");
  const [translatedPreview, setTranslatedPreview] = useState<string | null>(null);
  const [settings, setSettings] = useState<AISettings | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null);
  const [provider, setProvider] = useState("openai_compatible");
  const [baseUrlChoice, setBaseUrlChoice] = useState("navidia");
  const [model, setModel] = useState("");
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [apiKey, setApiKey] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (requestedTab) setTab(requestedTab);
  }, [requestedTab, tabRequestId]);

  useEffect(() => {
    if (tab !== "settings" || settings) return;
    void loadSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, settings]);

  const selectedBaseUrl = () => {
    return settings?.openai_compatible_base_url_options.find((item) => item.key === baseUrlChoice)?.url ?? "";
  };

  const syncSettingsForm = (nextSettings: AISettings) => {
    const nextProvider = nextSettings.ai_provider || nextSettings.provider_order[0] || "openai_compatible";
    const nextModel = nextSettings.providers[nextProvider]?.model ?? "";
    setSettings(nextSettings);
    setProvider(nextProvider);
    setBaseUrlChoice(nextSettings.openai_compatible_base_url_choice || "navidia");
    setModel(nextModel);
    setModelOptions(nextSettings.providers[nextProvider]?.default_models ?? []);
    setApiKey("");
  };

  const loadSettings = async () => {
    setSettingsLoading(true);
    setSettingsMessage(null);
    try {
      syncSettingsForm(await AI.getSettings());
    } catch (err) {
      setSettingsMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setSettingsLoading(false);
    }
  };

  const refreshModelOptions = async (nextProvider = provider, nextBaseChoice = baseUrlChoice) => {
    const baseUrl =
      nextProvider === "openai_compatible"
        ? settings?.openai_compatible_base_url_options.find((item) => item.key === nextBaseChoice)?.url ?? ""
        : "";
    setSettingsMessage(null);
    try {
      const result = apiKey.trim()
        ? await AI.fetchModelsWithKey(nextProvider, apiKey.trim(), baseUrl)
        : await AI.getModels(nextProvider, baseUrl);
      setModelOptions(result.models);
      if (result.models.length > 0 && !result.models.includes(model)) {
        setModel(result.models[0]);
      }
    } catch (err) {
      setSettingsMessage(err instanceof Error ? err.message : String(err));
    }
  };

  const handleProviderChange = (nextProvider: string) => {
    setProvider(nextProvider);
    const nextModels = settings?.providers[nextProvider]?.default_models ?? [];
    setModelOptions(nextModels);
    setModel(settings?.providers[nextProvider]?.model || nextModels[0] || "");
    setApiKey("");
    void refreshModelOptions(nextProvider, baseUrlChoice);
  };

  const handleBaseUrlChange = (nextChoice: string) => {
    setBaseUrlChoice(nextChoice);
    if (provider === "openai_compatible") {
      void refreshModelOptions(provider, nextChoice);
    }
  };

  const saveSettings = async () => {
    setSettingsSaving(true);
    setSettingsMessage(null);
    try {
      if (provider === "openai_compatible") {
        await AI.setOpenAICompatibleBaseUrlChoice(baseUrlChoice);
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

              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500 dark:text-gray-400">Model</label>
                <input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  list="ai-model-options"
                  className="text-xs p-1.5 border border-gray-200 dark:border-gray-600 rounded bg-gray-50 dark:bg-[#2d2d2d] text-gray-800 dark:text-gray-100"
                />
                <datalist id="ai-model-options">
                  {modelOptions.map((item) => (
                    <option key={item} value={item} />
                  ))}
                </datalist>
              </div>

              <button
                onClick={() => { void refreshModelOptions(); }}
                className="py-1 text-xs border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-[#2d2d2d] text-gray-700 dark:text-gray-300"
              >
                Fetch Models
              </button>

              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500 dark:text-gray-400">API Key</label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={
                    settings.providers[provider]?.key_configured
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
