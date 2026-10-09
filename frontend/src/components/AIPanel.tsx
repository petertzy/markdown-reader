"use client";

import { useState, useRef, useEffect, useCallback, type ReactNode } from "react";
import { useAIChat, type TranslationPair, type TranslationProgress } from "@/hooks/useAIChat";
import { AI, getDefaultAISettings, type AISettings, Knowledge, type KnowledgeStatus, type ProjectTranslationTask } from "@/lib/api";
import { tokenizeInlineMarkdown } from "@/lib/inline-markdown.mjs";

export type AIPanelTab = "chat" | "translate" | "settings" | "work";
type Tab = AIPanelTab;

type Props = {
  documentText: string;
  selectedText?: string;
  onApplyAction?: (type: string, content: string) => void;
  /** Force the panel to switch to this tab (e.g. deep-linking from a slash command) */
  initialTab?: Tab;
  executeWork?: (instruction: string) => Promise<void>;
  isWorking?: boolean;
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
  // The scan itself lives in lib/inline-markdown.mjs so the Node suite can test
  // where a bare URL ends; text runs stay bare strings, as before.
  return tokenizeInlineMarkdown(text).map((token, index) => {
    if (token.type === "strong") {
      return <strong key={index}>{token.value}</strong>;
    }
    if (token.type === "code") {
      return (
        <code
          key={index}
          className="rounded bg-black/10 dark:bg-white/10 px-1 py-0.5 font-mono text-[11px]"
        >
          {token.value}
        </code>
      );
    }
    if (token.type === "link") {
      return (
        <a
          key={index}
          href={token.href}
          target="_blank"
          rel="noreferrer"
          className="underline underline-offset-2 hover:text-blue-600 dark:hover:text-blue-300"
        >
          {token.label}
        </a>
      );
    }
    return token.value;
  });
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
  executeWork,
  isWorking,
}: Props) {
  const { messages, loading, error, sendMessage, translate, translateSentences, cancelTranslation, clearHistory } = useAIChat();
  const [tab, setTab] = useState<Tab>(initialTab ?? "chat");

  useEffect(() => {
    if (initialTab) setTab(initialTab);
  }, [initialTab]);

  const [input, setInput] = useState("");
  const [sourceLang, setSourceLang] = useState("Auto Detect");
  const [targetLang, setTargetLang] = useState("English");
  const [translateScope, setTranslateScope] = useState<"selection" | "document">("document");
  const [translationMode, setTranslationMode] = useState<"full" | "sentences">("full");
  const [translatedPreview, setTranslatedPreview] = useState<string | null>(null);
  const [translationPairs, setTranslationPairs] = useState<TranslationPair[]>([]);
  const [translationProgress, setTranslationProgress] = useState<TranslationProgress | null>(null);
  const [projectRoot, setProjectRoot] = useState("");
  const [projectTask, setProjectTask] = useState<ProjectTranslationTask | null>(null);
  const [projectError, setProjectError] = useState<string | null>(null);
  const [projectStarting, setProjectStarting] = useState(false);
  const [settings, setSettings] = useState<AISettings>(() => getDefaultAISettings());
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [modelsFetching, setModelsFetching] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null);
  const [provider, setProvider] = useState("openai_compatible");
  const [baseUrlChoice, setBaseUrlChoice] = useState("nvidia");
  const [localBaseUrlChoice, setLocalBaseUrlChoice] = useState("lm_studio");
  const [localBaseUrl, setLocalBaseUrl] = useState("[http://127.0.0.1:1234/v1](http://127.0.0.1:1234/v1)");
  const [model, setModel] = useState("");
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [apiKey, setApiKey] = useState("");
  const [knowledgeStatus, setKnowledgeStatus] = useState<KnowledgeStatus | null>(null);
  const [knowledgeEnabled, setKnowledgeEnabled] = useState(true);
  const [knowledgeIndexing, setKnowledgeIndexing] = useState(false);
  const [knowledgeError, setKnowledgeError] = useState<string | null>(null);
  const [knowledgePathInput, setKnowledgePathInput] = useState("");
  const [showKnowledgeManager, setShowKnowledgeManager] = useState(false);
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
      "[http://127.0.0.1:1234/v1](http://127.0.0.1:1234/v1)";
    setSettings(nextSettings);
    setProvider(nextProvider);
    setBaseUrlChoice(nextSettings.openai_compatible_base_url_choice || "nvidia");
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
            "[http://127.0.0.1:1234/v1](http://127.0.0.1:1234/v1)";
          if (nextLocalChoice !== "custom" || nextLocalBaseUrl.trim()) {
            void refreshModelOptions(
              "local",
              nextSettings.openai_compatible_base_url_choice || "nvidia",
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
      setLocalBaseUrl("[http://127.0.0.1:1234/v1](http://127.0.0.1:1234/v1)");
      localBaseUrlChoiceRef.current = "lm_studio";
      localBaseUrlRef.current = "[http://127.0.0.1:1234/v1](http://127.0.0.1:1234/v1)";
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

  const loadKnowledgeStatus = useCallback(async () => {
    try {
      const status = await Knowledge.getStatus();
      setKnowledgeStatus(status);
      setKnowledgeEnabled(status.enabled);
      setKnowledgePathInput(status.path);
    } catch {
      // Ignore initial status load failure
    }
  }, []);

  useEffect(() => {
    void loadKnowledgeStatus();
  }, [loadKnowledgeStatus]);

  const handleToggleKnowledge = async (enabled: boolean) => {
    setKnowledgeEnabled(enabled);
    try {
      await Knowledge.toggle(enabled);
      setKnowledgeStatus((prev) => (prev ? { ...prev, enabled } : prev));
    } catch (err) {
      setKnowledgeError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleIndexKnowledge = async (pathToUse?: string, force = false) => {
    const targetPath = (pathToUse ?? knowledgePathInput).trim();
    if (!targetPath) return;
    setKnowledgeIndexing(true);
    setKnowledgeError(null);
    try {
      await Knowledge.index(targetPath, force);
      await loadKnowledgeStatus();
      setShowKnowledgeManager(false);
    } catch (err) {
      setKnowledgeError(err instanceof Error ? err.message : String(err));
    } finally {
      setKnowledgeIndexing(false);
    }
  };

  const handleSelectKnowledgeDirectory = async () => {
    setKnowledgeError(null);
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({
        directory: true,
        multiple: false,
      });
      const selectedPath = selected ? (Array.isArray(selected) ? selected[0] : selected) : null;
      if (!selectedPath) return;
      setKnowledgePathInput(selectedPath);
      await handleIndexKnowledge(selectedPath);
    } catch {
      // If dialog is not available in browser mode, expand the path input
      setShowKnowledgeManager(true);
    }
  };

  const handleClearKnowledge = async () => {
    setKnowledgeIndexing(true);
    try {
      await Knowledge.clear();
      setKnowledgePathInput("");
      await loadKnowledgeStatus();
    } catch (err) {
      setKnowledgeError(err instanceof Error ? err.message : String(err));
    } finally {
      setKnowledgeIndexing(false);
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
    const sendOptions = {
      useKnowledgeBase: knowledgeEnabled && Boolean(knowledgeStatus?.exists),
    };
    const slashPrompt = CHAT_SLASH_PROMPTS[slashCommand];
    if (slashPrompt) {
      await sendMessage(slashPrompt, documentText, selectedText, sendOptions);
      return;
    }
    await sendMessage(msg, documentText, selectedText, sendOptions);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const projectTaskId = projectTask?.id ?? null;
  const projectStatus = projectTask?.status ?? null;
  const projectRunning = projectStatus === "running" || projectStatus === "pending";

  useEffect(() => {
    if (!projectTaskId || !projectRunning) return;
    let stopped = false;
    const timer = window.setInterval(() => {
      void AI.projectTranslationStatus(projectTaskId)
        .then((next) => {
          if (!stopped) setProjectTask(next);
        })
        .catch((err: unknown) => {
          if (!stopped) {
            setProjectError(err instanceof Error ? err.message : String(err));
          }
        });
    }, 800);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [projectRunning, projectTaskId]);

  const handleTranslateProject = async () => {
    const root = projectRoot.trim();
    if (!root || projectRunning) return;
    setProjectError(null);
    setProjectStarting(true);
    try {
      if (provider === "local") {
        await AI.setProvider(provider);
        await AI.setLocalAIBaseUrlChoice(localBaseUrlChoice, localBaseUrl);
      }
      const task = await AI.startProjectTranslation({
        root,
        source_language: sourceLang === "Auto Detect" ? "auto" : sourceLang,
        target_language: targetLang,
      });
      setProjectTask(task);
    } catch (err) {
      setProjectError(err instanceof Error ? err.message : String(err));
    } finally {
      setProjectStarting(false);
    }
  };

  const handleBrowseProject = async () => {
    setProjectError(null);
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({ directory: true, multiple: false });
      const selectedPath = selected ? (Array.isArray(selected) ? selected[0] : selected) : null;
      if (selectedPath) setProjectRoot(selectedPath);
    } catch {
      setProjectError("Folder browsing is available in the desktop app. Paste a folder path instead.");
    }
  };

  const handleCancelProject = async () => {
    if (!projectTask) return;
    try {
      setProjectTask(await AI.cancelProjectTranslation(projectTask.id));
    } catch (err) {
      setProjectError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleTranslate = async () => {
    const content = translateScope === "selection" && selectedText ? selectedText : documentText;
    if (!content.trim()) return;
    setTranslatedPreview(null);
    setTranslationPairs([]);
    setTranslationProgress(null);
    if (provider === "local") {
      await AI.setProvider(provider);
      await AI.setLocalAIBaseUrlChoice(localBaseUrlChoice, localBaseUrl);
    }
    const normalizedSourceLang = sourceLang === "Auto Detect" ? "auto" : sourceLang;
    if (translationMode === "sentences") {
      const result = await translateSentences(
        content,
        normalizedSourceLang,
        targetLang,
        setTranslationProgress
      );
      if (result) {
        setTranslatedPreview(result.translated);
        setTranslationPairs(result.pairs);
      }
      setTranslationProgress(null);
      return;
    }
    const result = await translate(content, normalizedSourceLang, targetLang);
    if (result) setTranslatedPreview(result);
  };

  const sentencePairApplyContent = () =>
    translationPairs
      .map((pair) => `${pair.source}\n\n${pair.translated}`)
      .join("\n\n");

  const translationApplyContent = () =>
    translationMode === "sentences" && translationPairs.length > 0
      ? sentencePairApplyContent()
      : translatedPreview ?? "";

  const applyTranslation = (type: "replace_document" | "replace_selection") => {
    const content = translationApplyContent();
    if (content && onApplyAction) {
      onApplyAction(type, content);
      setTranslatedPreview(null);
      setTranslationPairs([]);
    }
  };

  const insertBelow = () => {
    const content = translationApplyContent();
    if (content && onApplyAction) {
      const actionType =
        translateScope === "selection" && selectedText
          ? "insert_below_selection"
          : "insert_below_document";
      onApplyAction(actionType, content);
      setTranslatedPreview(null);
      setTranslationPairs([]);
    }
  };

  return (
    <div className="flex flex-col w-80 min-w-[280px] max-w-[380px] border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-[#1e1e1e] text-sm">
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700 shrink-0">
        <div className="flex gap-1">
          {(["chat", "work", "translate", "settings"] as Tab[]).map((t) => (
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
          {/* Notes Context / Local RAG Bar */}
          <div className="px-3 py-2 bg-gray-50 dark:bg-[#252525] border-b border-gray-200 dark:border-gray-700 text-xs shrink-0">
            <div className="flex items-center justify-between gap-1">
              <div className="flex items-center gap-1.5 overflow-hidden">
                <span className="font-medium truncate" title={knowledgeStatus?.path || "No notes directory selected"}>
                  📁 {knowledgeStatus?.exists && knowledgeStatus.path
                    ? `${knowledgeStatus.path.split(/[/\\]/).filter(Boolean).pop()} (${knowledgeStatus.file_count} note${knowledgeStatus.file_count === 1 ? "" : "s"})`
                    : "Notes context: None"}
                </span>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                {knowledgeStatus?.exists && (
                  <>
                    <button
                      onClick={() => handleToggleKnowledge(!knowledgeEnabled)}
                      className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase transition-colors ${
                        knowledgeEnabled
                          ? "bg-emerald-600 text-white"
                          : "bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
                      }`}
                      title={knowledgeEnabled ? "Directory context active" : "Directory context disabled"}
                    >
                      {knowledgeEnabled ? "ON" : "OFF"}
                    </button>
                    <button
                      onClick={() => handleIndexKnowledge()}
                      disabled={knowledgeIndexing}
                      className="p-1 text-gray-500 hover:text-blue-500 disabled:opacity-40"
                      title="Re-index notes directory"
                    >
                      ↻
                    </button>
                  </>
                )}
                <button
                  onClick={() => setShowKnowledgeManager((v) => !v)}
                  className="px-1.5 py-0.5 text-xs text-blue-600 dark:text-blue-400 hover:underline"
                  title="Configure notes directory"
                >
                  {knowledgeStatus?.exists ? "Change" : "Select"}
                </button>
              </div>
            </div>

            {/* Expandable Folder Configuration Form */}
            {showKnowledgeManager && (
              <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-700 space-y-1.5">
                <div className="flex gap-1">
                  <input
                    type="text"
                    value={knowledgePathInput}
                    onChange={(e) => setKnowledgePathInput(e.target.value)}
                    placeholder="Enter folder path e.g. ~/Notes"
                    className="flex-1 text-[11px] p-1 border border-gray-200 dark:border-gray-600 rounded bg-white dark:bg-[#1e1e1e]"
                  />
                  <button
                    onClick={handleSelectKnowledgeDirectory}
                    className="px-2 py-1 text-[11px] bg-gray-200 dark:bg-gray-700 rounded hover:bg-gray-300 dark:hover:bg-gray-600"
                    title="Browse local folders"
                  >
                    Browse
                  </button>
                  <button
                    onClick={() => handleIndexKnowledge()}
                    disabled={knowledgeIndexing || !knowledgePathInput.trim()}
                    className="px-2 py-1 text-[11px] bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-40"
                  >
                    {knowledgeIndexing ? "Indexing…" : "Index"}
                  </button>
                </div>
                {knowledgeStatus?.exists && (
                  <div className="flex justify-between items-center text-[10px] text-gray-500 dark:text-gray-400">
                    <span>{knowledgeStatus.file_count} notes, {knowledgeStatus.chunk_count} chunks indexed</span>
                    <button
                      onClick={handleClearKnowledge}
                      disabled={knowledgeIndexing}
                      className="text-red-500 hover:underline"
                    >
                      Clear Index
                    </button>
                  </div>
                )}
                {knowledgeError && (
                  <p className="text-[11px] text-red-500">{knowledgeError}</p>
                )}
              </div>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {messages.length === 0 && (
              <p className="text-gray-400 dark:text-gray-500 text-xs">
                {knowledgeStatus?.exists && knowledgeEnabled
                  ? "Ask anything about your notes, or try /summarize, /format, /toc, /fix-code."
                  : "Try /summarize, /translate, /format, /toc, /fix-code, or /insert-table."}
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
                    <ChatMessageContent content={msg.content}/>
                  ) : (
                    <span className="whitespace-pre-wrap">{msg.content}</span>
                  )}
                </div>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1 text-[10px] text-gray-500 dark:text-gray-400 px-1">
                    <span className="font-medium">Sources:</span>
                    {msg.sources.map((src, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700"
                        title={src.rel_path + (src.section ? ` > ${src.section}` : "")}
                      >
                        📄 {src.title || src.rel_path}
                      </span>
                    ))}
                  </div>
                )}
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
      ) : tab === "work" ? (
        <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
          <div className="text-xs text-gray-500 dark:text-gray-400">
            Describe a task, and the AI will directly modify the active document.
          </div>
          <textarea 
            className="w-full h-32 p-2 text-sm border rounded resize-none dark:bg-gray-800 dark:border-gray-600 dark:text-white"
            placeholder="e.g., 'Rewrite this document to be more professional' or 'Fix all typos'"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <button 
            className="w-full bg-blue-600 text-white py-1.5 px-3 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
            onClick={() => {
              if (executeWork) {
                const instruction = input.trim();
                setInput("");
                void executeWork(instruction);
              }
            }}
            disabled={!input.trim() || isWorking}
          >
            {isWorking ? "Working..." : "Apply Changes"}
          </button>
        </div>
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
            <label className="text-xs text-gray-500 dark:text-gray-400">Mode</label>
            <div className="grid grid-cols-2 gap-1">
              {(["full", "sentences"] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => {
                    setTranslationMode(mode);
                    setTranslatedPreview(null);
                    setTranslationPairs([]);
                    setTranslationProgress(null);
                  }}
                  className={`py-1 text-xs rounded border ${
                    translationMode === mode
                      ? "bg-blue-500 text-white border-blue-500"
                      : "border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-[#2d2d2d]"
                  }`}
                >
                  {mode === "full" ? "Full Text" : "Sentence Pairs"}
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
            disabled={loading || !(translateScope === "selection" && selectedText ? selectedText : documentText).trim()}
            className="py-1.5 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-40"
          >
            {loading ? "Translating…" : "Translate"}
          </button>

          <div className="flex flex-col gap-1.5 rounded border border-gray-200 dark:border-gray-700 p-2">
            <div className="text-xs font-medium text-gray-700 dark:text-gray-200">Project folder</div>
            <p className="text-[11px] leading-snug text-gray-500 dark:text-gray-400">
              Translates every Markdown file into <span className="font-mono">.markdown-reader/translations</span>. Source files stay unchanged.
            </p>
            <div className="flex gap-1">
              <input
                type="text"
                value={projectRoot}
                onChange={(event) => setProjectRoot(event.target.value)}
                placeholder={knowledgeStatus?.path || "Folder path"}
                className="flex-1 text-[11px] p-1 border border-gray-200 dark:border-gray-600 rounded bg-white dark:bg-[#1e1e1e]"
              />
              <button
                onClick={() => { void handleBrowseProject(); }}
                className="px-2 py-1 text-[11px] bg-gray-200 dark:bg-gray-700 rounded hover:bg-gray-300 dark:hover:bg-gray-600"
              >
                Browse
              </button>
            </div>
            {knowledgeStatus?.exists && knowledgeStatus.path && projectRoot !== knowledgeStatus.path && (
              <button
                onClick={() => setProjectRoot(knowledgeStatus.path)}
                className="self-start text-[11px] text-blue-600 dark:text-blue-400 hover:underline"
              >
                Use notes folder
              </button>
            )}
            <div className="flex gap-1">
              <button
                onClick={() => { void handleTranslateProject(); }}
                disabled={projectStarting || projectRunning || !projectRoot.trim()}
                className="flex-1 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-40"
              >
                {projectRunning ? "Translating project…" : "Translate project"}
              </button>
              {projectRunning && (
                <button
                  onClick={() => { void handleCancelProject(); }}
                  className="px-2 py-1 text-xs border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-[#2d2d2d]"
                >
                  Stop
                </button>
              )}
            </div>
            {projectTask && (
              <div className="flex flex-col gap-1 text-[11px] text-gray-600 dark:text-gray-300">
                <div className="flex items-center justify-between">
                  <span>
                    {projectTask.completed}/{projectTask.total} files
                    {projectTask.failed > 0 ? `, ${projectTask.failed} failed` : ""}
                  </span>
                  <span className="capitalize">{projectTask.status}</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded bg-gray-200 dark:bg-gray-700">
                  <div
                    className="h-full rounded bg-blue-500 transition-all"
                    style={{
                      width: `${projectTask.total > 0 ? Math.round((projectTask.completed / projectTask.total) * 100) : 0}%`,
                    }}
                  />
                </div>
                <div className="max-h-28 overflow-y-auto font-mono">
                  {projectTask.files.map((file) => (
                    <div key={file.rel_path} title={file.error ?? file.status} className="truncate">
                      {file.status === "failed" ? "✕" : file.status === "translated" || file.status === "unchanged" ? "✓" : file.status === "cancelled" ? "–" : "·"} {file.rel_path}
                    </div>
                  ))}
                </div>
                {projectTask.status !== "running" && projectTask.output_dir && (
                  <div className="break-all text-gray-500 dark:text-gray-400">Output: {projectTask.output_dir}</div>
                )}
              </div>
            )}
            {projectError && (
              <div className="text-xs text-red-500 bg-red-50 dark:bg-red-900/20 px-2 py-1 rounded">{projectError}</div>
            )}
          </div>

          {translationMode === "sentences" && (translationProgress || loading) && (
            <div className="flex flex-col gap-1 rounded border border-blue-100 bg-blue-50 p-2 text-xs text-blue-700 dark:border-blue-900/50 dark:bg-blue-950/30 dark:text-blue-200">
              <div className="flex items-center justify-between">
                <span>{translationProgress ? "Translating batches" : "Preparing translation"}</span>
                <div className="flex items-center gap-2">
                  <span>
                    {translationProgress
                      ? `${translationProgress.currentBatch}/${translationProgress.totalBatches}`
                      : "0/0"}
                  </span>
                  <button
                    onClick={cancelTranslation}
                    className="rounded border border-blue-200 px-1.5 py-0.5 text-[11px] font-medium hover:bg-blue-100 dark:border-blue-700 dark:hover:bg-blue-900/50"
                  >
                    Stop
                  </button>
                </div>
              </div>
              <div className="h-1.5 overflow-hidden rounded bg-blue-100 dark:bg-blue-900/60">
                <div
                  className="h-full rounded bg-blue-500 transition-all"
                  style={{
                    width: `${Math.round(
                      translationProgress && translationProgress.totalBatches > 0
                        ? (translationProgress.currentBatch / translationProgress.totalBatches) * 100
                        : 0
                    )}%`,
                  }}
                />
              </div>
            </div>
          )}

          {error && (
            <div className="text-xs text-red-500 bg-red-50 dark:bg-red-900/20 px-2 py-1 rounded">{error}</div>
          )}

          {translationMode === "sentences" && translationPairs.length > 0 ? (
            <div className="flex flex-col gap-2">
              <div className="text-xs text-gray-500 dark:text-gray-400 font-medium">Preview</div>
              <div className="flex max-h-72 flex-col gap-2 overflow-y-auto">
                {translationPairs.map((pair, index) => (
                  <div
                    key={`${pair.source}-${index}`}
                    className="rounded border border-gray-200 bg-gray-50 p-2 text-xs dark:border-gray-600 dark:bg-[#2d2d2d]"
                  >
                    <div className="mb-1 whitespace-pre-wrap text-gray-500 dark:text-gray-400">
                      {pair.source}
                    </div>
                    <div className="whitespace-pre-wrap border-t border-gray-200 pt-1 text-gray-900 dark:border-gray-600 dark:text-gray-100">
                      {pair.translated}
                    </div>
                  </div>
                ))}
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
          ) : translatedPreview && (
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
                      placeholder="[http://127.0.0.1:1234/v1](http://127.0.0.1:1234/v1)"
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

              {/* Personal Notes / Directory Context Section */}
              <div className="pt-3 border-t border-gray-200 dark:border-gray-700 flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-gray-700 dark:text-gray-200">
                    Directory Context / Notes RAG
                  </label>
                  {knowledgeStatus?.exists && (
                    <button
                      onClick={() => handleToggleKnowledge(!knowledgeEnabled)}
                      className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${
                        knowledgeEnabled
                          ? "bg-emerald-600 text-white"
                          : "bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
                      }`}
                    >
                      {knowledgeEnabled ? "Enabled" : "Disabled"}
                    </button>
                  )}
                </div>
                <p className="text-[11px] text-gray-500 dark:text-gray-400">
                  Indexing and retrieval stay local. When notes context is enabled, matching excerpts are sent to the selected AI provider with your chat message.
                </p>
                <div className="flex gap-1">
                  <input
                    type="text"
                    value={knowledgePathInput}
                    onChange={(e) => setKnowledgePathInput(e.target.value)}
                    placeholder="Enter folder path e.g. ~/Notes"
                    className="flex-1 text-xs p-1.5 border border-gray-200 dark:border-gray-600 rounded bg-gray-50 dark:bg-[#2d2d2d] text-gray-800 dark:text-gray-100"
                  />
                  <button
                    onClick={handleSelectKnowledgeDirectory}
                    className="px-2 py-1.5 text-xs border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-[#2d2d2d]"
                  >
                    Browse
                  </button>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleIndexKnowledge()}
                    disabled={knowledgeIndexing || !knowledgePathInput.trim()}
                    className="flex-1 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-40"
                  >
                    {knowledgeIndexing ? "Indexing…" : "Index Notes"}
                  </button>
                  {knowledgeStatus?.exists && (
                    <button
                      onClick={handleClearKnowledge}
                      disabled={knowledgeIndexing}
                      className="px-2 py-1 text-xs border border-red-300 dark:border-red-800 text-red-600 dark:text-red-400 rounded hover:bg-red-50 dark:hover:bg-red-950/20"
                    >
                      Clear
                    </button>
                  )}
                </div>
                {knowledgeStatus?.exists && (
                  <div className="text-[11px] text-gray-500 dark:text-gray-400">
                    Indexed {knowledgeStatus.file_count} note{knowledgeStatus.file_count === 1 ? "" : "s"} ({knowledgeStatus.chunk_count} chunk{knowledgeStatus.chunk_count === 1 ? "" : "s"}).
                  </div>
                )}
                {knowledgeError && (
                  <div className="text-xs text-red-500 bg-red-50 dark:bg-red-900/20 px-2 py-1 rounded">
                    {knowledgeError}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
