/**
 * api.ts
 * ======
 * Typed client for the Markdown Reader FastAPI backend.
 *
 * Port resolution strategy:
 *   1. Tauri desktop app  → call invoke('get_backend_port'), retry until ready.
 *      The sidecar picks a free OS port at startup and announces it on stdout;
 *      the Rust host captures it and exposes it via this Tauri command.
 *   2. Browser / Next.js dev server → use NEXT_PUBLIC_API_BASE_URL env var,
 *      falling back to http://127.0.0.1:8000 for convenience.
 *
 * This means NO hard-coded port leaks into the packaged desktop app.
 */

import {
  DEFAULT_REQUEST_TIMEOUT_MS,
  LONG_REQUEST_TIMEOUT_MS,
  fetchWithTimeout,
  runWithTimeout,
} from "./http-timeout.mjs";

export { DEFAULT_REQUEST_TIMEOUT_MS, LONG_REQUEST_TIMEOUT_MS, fetchWithTimeout };

// Detect Tauri without relying only on globals. Tauri v2 may not expose
// window.__TAURI__ unless withGlobalTauri is enabled, while packaged pages are
// served from tauri.localhost and usually include "Tauri" in the user agent.
function isTauriRuntime() {
  if (typeof window === "undefined") return false;

  return (
    "__TAURI__" in window ||
    "__TAURI_INTERNALS__" in window ||
    window.location.hostname === "tauri.localhost" ||
    window.navigator.userAgent.includes("Tauri")
  );
}

let _resolvedBaseUrl: string | null = null;
type BackendProxyResponse = {
  status: number;
  bodyBase64: string;
  contentType: string | null;
};

function decodeBase64(bodyBase64: string): Uint8Array {
  return Uint8Array.from(atob(bodyBase64), (char) => char.charCodeAt(0));
}

function decodeProxyText(response: BackendProxyResponse): string {
  return new TextDecoder().decode(decodeBase64(response.bodyBase64));
}

async function proxyBackendRequest(
  path: string,
  init?: RequestInit,
  signal?: AbortSignal
): Promise<BackendProxyResponse> {
  const { invoke } = await import("@tauri-apps/api/core");
  const requestId = crypto.randomUUID();
  const cancel = () => {
    void invoke("cancel_backend_request", { requestId });
  };
  if (signal?.aborted) {
    cancel();
    throw new DOMException("Aborted", "AbortError");
  }
  signal?.addEventListener("abort", cancel, { once: true });
  try {
    return await invoke<BackendProxyResponse>("proxy_backend_request", {
    request: {
      requestId,
      path,
      method: init?.method ?? "GET",
      body: typeof init?.body === "string" ? init.body : undefined,
    },
    });
  } finally {
    signal?.removeEventListener("abort", cancel);
  }
}

/**
 * Returns the backend base URL, resolving it once and caching the result.
 * In Tauri the first call may take several seconds while the packaged sidecar
 * unpacks and starts.
 */
export async function getBaseUrl(): Promise<string> {
  if (_resolvedBaseUrl) return _resolvedBaseUrl;

  if (isTauriRuntime()) {
    const { invoke } = await import("@tauri-apps/api/core");
    // PyInstaller onefile sidecars can take a while to unpack on first launch.
    // Wait for both the announced port and an accepting HTTP server.
    for (let attempt = 0; attempt < 120; attempt++) {
      const port = await invoke<number | null>("get_backend_port");
      if (port) {
        const candidate = `http://127.0.0.1:${port}`;
        try {
          const health = await proxyBackendRequest("/api/health");
          if (health.status >= 200 && health.status < 300) {
            _resolvedBaseUrl = candidate;
            return _resolvedBaseUrl;
          }
        } catch {
          // The Rust host has received the port, but Uvicorn is not listening yet.
        }
      }
      await new Promise((r) => setTimeout(r, 500));
    }
    throw new Error("Backend sidecar did not become ready within 60 s.");
  }

  // Browser / dev mode
  _resolvedBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
  return _resolvedBaseUrl;
}

async function apiFetch<T>(
  path: string,
  init?: RequestInit,
  timeoutMs: number = DEFAULT_REQUEST_TIMEOUT_MS
): Promise<T> {
  if (isTauriRuntime()) {
    return runWithTimeout(async (signal) => {
      const response = await proxyBackendRequest(path, init, signal);
      const text = decodeProxyText(response);
      if (response.status < 200 || response.status >= 300) {
        throw new Error(`API ${path} → ${response.status}: ${text}`);
      }
      return JSON.parse(text) as T;
    }, init?.signal ?? undefined, timeoutMs);
  }

  const base = await getBaseUrl();
  const token = process.env.NEXT_PUBLIC_BACKEND_TOKEN ?? null;
  return runWithTimeout(async (signal) => {
    const res = await fetch(`${base}${path}`, {
      ...init,
      signal,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "X-Markdown-Reader-Token": token } : {}),
        ...(init?.headers ?? {}),
      },
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(`API ${path} → ${res.status}: ${detail}`);
    }
    return res.json() as Promise<T>;
  }, init?.signal ?? undefined, timeoutMs);
}

async function apiFetchBlob(
  path: string,
  init?: RequestInit,
  timeoutMs: number = DEFAULT_REQUEST_TIMEOUT_MS
): Promise<Blob> {
  if (isTauriRuntime()) {
    return runWithTimeout(async (signal) => {
      const response = await proxyBackendRequest(path, init, signal);
      const bytes = decodeBase64(response.bodyBase64);
      if (response.status < 200 || response.status >= 300) {
        throw new Error(`API ${path} → ${response.status}: ${new TextDecoder().decode(bytes)}`);
      }
      const body = bytes.buffer.slice(
        bytes.byteOffset,
        bytes.byteOffset + bytes.byteLength
      ) as ArrayBuffer;
      return new Blob([body], { type: response.contentType ?? "application/octet-stream" });
    }, init?.signal ?? undefined, timeoutMs);
  }

  const base = await getBaseUrl();
  const token = process.env.NEXT_PUBLIC_BACKEND_TOKEN ?? null;
  return runWithTimeout(async (signal) => {
    const res = await fetch(`${base}${path}`, {
      ...init,
      signal,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "X-Markdown-Reader-Token": token } : {}),
        ...(init?.headers ?? {}),
      },
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(`API ${path} → ${res.status}: ${detail}`);
    }
    return res.blob();
  }, init?.signal ?? undefined, timeoutMs);
}

// ── File API ──────────────────────────────────────────────────────────────────

export type FileEntry = {
  name: string;
  path: string;
  is_dir: boolean;
  extension: string;
};

export type ConvertToMarkdownPayload = {
  path?: string;
  filename?: string;
  content_base64?: string;
};

export type SupportedFileFormat = {
  extension: string;
  description: string;
};

export type SupportedFormatsResponse = {
  native: SupportedFileFormat[];
  markitdown: SupportedFileFormat[];
  markitdown_available: boolean;
};

export const Files = {
  read: (path: string) =>
    apiFetch<{ path: string; content: string }>(
      `/api/files/read?path=${encodeURIComponent(path)}`
    ),

  write: (path: string, content: string) =>
    apiFetch<{ path: string; written: boolean }>(`/api/files/write`, {
      method: "POST",
      body: JSON.stringify({ path, content }),
    }),

  convertToMarkdown: (payload: ConvertToMarkdownPayload) =>
    apiFetch<{ markdown: string }>(
      "/api/files/convert-to-markdown",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      LONG_REQUEST_TIMEOUT_MS
    ),

  getSupportedFormats: () =>
    apiFetch<SupportedFormatsResponse>("/api/files/supported-formats"),

  list: (path: string, extensions?: string) => {
    const qs = `path=${encodeURIComponent(path)}${extensions ? `&extensions=${extensions}` : ""}`;
    return apiFetch<{ path: string; entries: FileEntry[] }>(
      `/api/files/list?${qs}`
    );
  },

  getRecent: () =>
    apiFetch<{ entries: string[] }>("/api/files/recent"),

  addRecent: (path: string) =>
    apiFetch<{ entries: string[] }>(
      `/api/files/recent?path=${encodeURIComponent(path)}`,
      { method: "POST" }
    ),

  clearRecent: () =>
    apiFetch<{ entries: string[] }>("/api/files/recent", { method: "DELETE" }),
};

// ── Markdown API ──────────────────────────────────────────────────────────────

export type RenderPayload = {
  content: string;
  base_dir?: string;
  dark_mode?: boolean;
  font_family?: string;
  font_size?: number;
};

export type WordCountResult = {
  words: number;
  chars_with_spaces: number;
  chars_without_spaces: number;
  reading_time: string;
};

export type BrowserPreviewResult = {
  path: string;
  url: string;
};

export const Markdown = {
  render: (payload: RenderPayload) =>
    apiFetch<{ html: string }>("/api/markdown/render", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  htmlToMarkdown: (html: string) =>
    apiFetch<{ markdown: string }>(
      "/api/markdown/convert/html",
      {
        method: "POST",
        body: JSON.stringify({ html }),
      },
      LONG_REQUEST_TIMEOUT_MS
    ),

  pdfToMarkdown: (path: string, use_docling = false) =>
    apiFetch<{ markdown: string }>(
      "/api/markdown/convert/pdf",
      {
        method: "POST",
        body: JSON.stringify({ path, use_docling }),
      },
      LONG_REQUEST_TIMEOUT_MS
    ),

  wordCount: (content: string) =>
    apiFetch<WordCountResult>("/api/markdown/wordcount", {
      method: "POST",
      body: JSON.stringify({ content }),
    }),

  openPreviewInBrowser: (payload: RenderPayload) =>
    apiFetch<BrowserPreviewResult>("/api/markdown/open-preview", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

// ── AI API ────────────────────────────────────────────────────────────────────

export type KnowledgeSource = {
  rel_path: string;
  title: string;
  section: string;
};

export type AgentChatPayload = {
  message: string;
  document_text?: string;
  selected_text?: string;
  chat_history?: { role: string; content: string }[];
  use_knowledge_base?: boolean;
  knowledge_top_k?: number;
};

export type AgentResponse = {
  assistant_message: string;
  proposed_action: {
    type:
      | "replace_document"
      | "replace_selection"
      | "insert_below_document"
      | "insert_below_selection"
      | "insert_below"
      | "none";
    content: string;
    reason: string;
  };
  used_provider: string;
  used_sources?: KnowledgeSource[];
};

export type AIAutomationTemplate = {
  id: string;
  title: string;
  prompt: string;
  requires_selection: boolean;
};

export type AIProviderInfo = {
  display_name: string;
  env_var: string;
  model: string;
  default_models: string[];
  key_configured: boolean;
};

export type OpenAICompatibleBaseUrlOption = {
  key: string;
  label: string;
  url: string;
};

export type LocalAIBaseUrlOption = {
  key: string;
  label: string;
  url: string;
};

export type AISettings = {
  ai_provider: string;
  ai_models?: Record<string, string>;
  providers: Record<string, AIProviderInfo>;
  provider_order: string[];
  openai_compatible_base_url_choice: string;
  openai_compatible_base_url_options: OpenAICompatibleBaseUrlOption[];
  local_ai_base_url: string;
  local_ai_base_url_choice: string;
  local_ai_custom_base_url: string;
  local_ai_base_url_options: LocalAIBaseUrlOption[];
  secure_key_storage_available: boolean;
};

const AI_PROVIDER_ORDER = [
  "local",
  "openai_compatible",
  "openrouter",
  "openai",
  "anthropic",
];

const AI_PROVIDER_DISPLAY_NAMES: Record<string, string> = {
  local: "Local Model",
  openai_compatible: "OpenAI Compatible",
  openrouter: "OpenRouter",
  openai: "OpenAI",
  anthropic: "Anthropic",
};

const AI_PROVIDER_ENV_VARS: Record<string, string> = {
  local: "LOCAL_AI_API_KEY",
  openai_compatible: "OPENAI_COMPATIBLE_API_KEY",
  openrouter: "OPENROUTER_API_KEY",
  openai: "OPENAI_API_KEY",
  anthropic: "ANTHROPIC_API_KEY",
};

const OPENAI_COMPATIBLE_BASE_URL_OPTIONS: OpenAICompatibleBaseUrlOption[] = [
  {
    key: "nvidia",
    label: "NVIDIA",
    url: "https://integrate.api.nvidia.com/v1",
  },
  {
    key: "groq",
    label: "Groq",
    url: "https://api.groq.com/openai/v1",
  },
];

const LOCAL_AI_BASE_URL_OPTIONS: LocalAIBaseUrlOption[] = [
  { key: "lm_studio", label: "LM Studio", url: "http://127.0.0.1:1234/v1" },
  { key: "ollama", label: "Ollama", url: "http://127.0.0.1:11434/v1" },
  { key: "custom", label: "Custom", url: "" },
];

type PartialAIProviderInfo = Partial<AIProviderInfo>;
type PartialAISettings = Partial<Omit<AISettings, "providers">> & {
  providers?: Record<string, PartialAIProviderInfo>;
};

function normalizeAISettings(raw: PartialAISettings): AISettings {
  const rawProviders = raw.providers ?? {};
  const providerOrder =
    Array.isArray(raw.provider_order) && raw.provider_order.length > 0
      ? raw.provider_order
      : AI_PROVIDER_ORDER.filter((name) => name in rawProviders).concat(
          AI_PROVIDER_ORDER.filter((name) => !(name in rawProviders))
        );
  const normalizedProviderOrder = Array.from(new Set(providerOrder));
  const normalizedProviders: Record<string, AIProviderInfo> = {};

  for (const name of normalizedProviderOrder) {
    const provider = rawProviders[name] ?? {};
    normalizedProviders[name] = {
      display_name:
        provider.display_name ?? AI_PROVIDER_DISPLAY_NAMES[name] ?? name,
      env_var: provider.env_var ?? AI_PROVIDER_ENV_VARS[name] ?? "",
      model: provider.model ?? provider.default_models?.[0] ?? "",
      default_models: provider.default_models ?? [],
      key_configured: provider.key_configured ?? false,
    };
  }

  const rawProvider = (raw.ai_provider ?? "").trim();
  const aiProvider = normalizedProviderOrder.includes(rawProvider)
    ? rawProvider
    : "openai_compatible";

  return {
    ...raw,
    ai_provider: aiProvider,
    providers: normalizedProviders,
    provider_order: normalizedProviderOrder,
    openai_compatible_base_url_choice:
      raw.openai_compatible_base_url_choice ?? "nvidia",
    openai_compatible_base_url_options:
      raw.openai_compatible_base_url_options ??
      OPENAI_COMPATIBLE_BASE_URL_OPTIONS,
    local_ai_base_url: raw.local_ai_base_url ?? "http://127.0.0.1:1234/v1",
    local_ai_base_url_choice: raw.local_ai_base_url_choice ?? "lm_studio",
    local_ai_custom_base_url: raw.local_ai_custom_base_url ?? "",
    local_ai_base_url_options:
      raw.local_ai_base_url_options ?? LOCAL_AI_BASE_URL_OPTIONS,
    secure_key_storage_available: raw.secure_key_storage_available ?? false,
  };
}

export function getDefaultAISettings(): AISettings {
  return normalizeAISettings({});
}

export const AI = {
  getSettings: async () =>
    normalizeAISettings(
      await apiFetch<PartialAISettings>("/api/ai/settings")
    ),

  setProvider: (provider: string) =>
    apiFetch<{ provider: string }>(
      `/api/ai/settings/provider?provider=${provider}`,
      { method: "POST" }
    ),

  setModel: (provider: string, model: string) =>
    apiFetch<{ provider: string; model: string }>("/api/ai/settings/model", {
      method: "POST",
      body: JSON.stringify({ provider, model }),
    }),

  saveApiKey: (provider: string, api_key: string) =>
    apiFetch<{ provider: string; saved: boolean }>(
      "/api/ai/settings/apikey",
      { method: "POST", body: JSON.stringify({ provider, api_key }) }
    ),

  deleteApiKey: (provider: string) =>
    apiFetch<{ provider: string; deleted: boolean }>(
      `/api/ai/settings/apikey/${provider}`,
      { method: "DELETE" }
    ),

  getModels: (provider: string, base_url_override = "") =>
    apiFetch<{ provider: string; models: string[]; message?: string }>(
      `/api/ai/models/${provider}${base_url_override ? `?base_url_override=${encodeURIComponent(base_url_override)}` : ""}`,
      {},
      LONG_REQUEST_TIMEOUT_MS
    ),

  fetchModelsWithKey: (provider: string, api_key: string, base_url_override = "") =>
    apiFetch<{ provider: string; models: string[]; message?: string }>(
      "/api/ai/models",
      {
        method: "POST",
        body: JSON.stringify({ provider, api_key, base_url_override }),
      },
      LONG_REQUEST_TIMEOUT_MS
    ),

  setOpenAICompatibleBaseUrlChoice: async (choice_key: string) => {
    try {
      return await apiFetch<{ choice: string }>(
        "/api/ai/settings/openai-compatible/base-url-choice",
        { method: "POST", body: JSON.stringify({ choice_key }) }
      );
    } catch (err) {
      if (err instanceof Error && err.message.includes("→ 404")) {
        return { choice: choice_key };
      }
      throw err;
    }
  },

  setLocalAIBaseUrl: (base_url: string) =>
    apiFetch<{ base_url: string }>("/api/ai/settings/local/base-url", {
      method: "POST",
      body: JSON.stringify({ base_url }),
    }),

  setLocalAIBaseUrlChoice: (choice_key: string, custom_base_url = "") =>
    apiFetch<{ choice: string; base_url: string }>(
      "/api/ai/settings/local/base-url-choice",
      {
        method: "POST",
        body: JSON.stringify({ choice_key, custom_base_url }),
      }
    ),

  chat: (payload: AgentChatPayload) =>
    apiFetch<AgentResponse>(
      "/api/ai/chat",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      LONG_REQUEST_TIMEOUT_MS
    ),

  work: (instruction: string, document_content: string) =>
    apiFetch<{ modified_content: string }>(
      "/api/ai/work",
      {
        method: "POST",
        body: JSON.stringify({ instruction, document_content }),
      },
      LONG_REQUEST_TIMEOUT_MS
    ),

  getChatHistory: () =>
    apiFetch<{ histories: unknown[] }>("/api/ai/chat/history"),

  saveChatHistory: (histories: unknown[]) =>
    apiFetch<{ saved: boolean }>("/api/ai/chat/history", {
      method: "POST",
      body: JSON.stringify(histories),
    }),

  getAutomationTemplates: () =>
    apiFetch<{ templates: AIAutomationTemplate[] }>("/api/ai/automation/templates"),

  getAutomationLogs: (limit = 100) =>
    apiFetch<{ logs: unknown[] }>(`/api/ai/automation/logs?limit=${limit}`),

  translate: (content: string, source_language: string, target_language: string) =>
    apiFetch<{ translated: string }>(
      "/api/ai/translate",
      {
        method: "POST",
        body: JSON.stringify({ content, source_language, target_language }),
      },
      LONG_REQUEST_TIMEOUT_MS
    ),

  translateSentences: (content: string, source_language: string, target_language: string) =>
    apiFetch<{ translated: string; pairs: { source: string; translated: string }[] }>(
      "/api/ai/translate/sentences",
      {
        method: "POST",
        body: JSON.stringify({ content, source_language, target_language }),
      },
      LONG_REQUEST_TIMEOUT_MS
    ),

  translateSentenceBatch: (
    items: string[],
    source_language: string,
    target_language: string,
    signal?: AbortSignal
  ) =>
    apiFetch<{ translated: string; pairs: { source: string; translated: string }[] }>(
      "/api/ai/translate/sentences/batch",
      {
        method: "POST",
        body: JSON.stringify({ items, source_language, target_language }),
        signal,
      },
      LONG_REQUEST_TIMEOUT_MS
    ),

  startProjectTranslation: (payload: {
    root: string;
    source_language: string;
    target_language: string;
    output_dir?: string;
  }) =>
    apiFetch<ProjectTranslationTask>("/api/ai/translate/project", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  projectTranslationStatus: (taskId: string) =>
    apiFetch<ProjectTranslationTask>(`/api/ai/translate/project/${taskId}`),

  cancelProjectTranslation: (taskId: string) =>
    apiFetch<ProjectTranslationTask>(`/api/ai/translate/project/${taskId}/cancel`, {
      method: "POST",
    }),
};

export type ProjectTranslationFile = {
  rel_path: string;
  status: string;
  error: string | null;
};

export type ProjectTranslationTask = {
  id: string;
  status: string;
  root: string;
  output_dir: string;
  source_language: string;
  target_language: string;
  total: number;
  completed: number;
  translated: number;
  unchanged: number;
  failed: number;
  cancelled: number;
  files: ProjectTranslationFile[];
};

// ── Export API ────────────────────────────────────────────────────────────────

export type ExportPayload = {
  content: string;
  output_path?: string;
  base_dir?: string;
  dark_mode?: boolean;
  font_family?: string;
  font_size?: number;
};

export const Export = {
  toHtml: (payload: ExportPayload) =>
    apiFetch<{ path: string }>(
      "/api/export/html",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      LONG_REQUEST_TIMEOUT_MS
    ),

  downloadHtml: (payload: ExportPayload) =>
    apiFetchBlob(
      "/api/export/html/download",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      LONG_REQUEST_TIMEOUT_MS
    ),

  toPdf: (payload: ExportPayload) =>
    apiFetch<{ path: string }>(
      "/api/export/pdf",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      LONG_REQUEST_TIMEOUT_MS
    ),

  toDocx: (payload: ExportPayload) =>
    apiFetch<{ path: string }>(
      "/api/export/docx",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      LONG_REQUEST_TIMEOUT_MS
    ),
};

// ── Citations API ────────────────────────────────────────────────────────────

export type CitationEntry = {
  key: string;
  entry_type: string;
  title: string;
  author: string;
  year: string;
  container: string;
};

export const Citations = {
  load: (path: string) =>
    apiFetch<{ path: string; count: number; entries: CitationEntry[] }>(
      "/api/citations/load",
      { method: "POST", body: JSON.stringify({ path }) }
    ),

  loadContent: (filename: string, content_base64: string) =>
    apiFetch<{ path: string; count: number; entries: CitationEntry[] }>(
      "/api/citations/load-content",
      { method: "POST", body: JSON.stringify({ filename, content_base64 }) }
    ),

  list: () =>
    apiFetch<{ path: string; entries: CitationEntry[] }>("/api/citations/list"),

  search: (query: string) =>
    apiFetch<{ entries: CitationEntry[] }>(
      `/api/citations/search?q=${encodeURIComponent(query)}`
    ),
};

// ── Knowledge Base / Directory Context API ────────────────────────────────────

export type KnowledgeStatus = {
  path: string;
  exists: boolean;
  enabled: boolean;
  file_count: number;
  chunk_count: number;
  last_indexed_at: number | null;
};

export type KnowledgeNote = {
  path: string;
  rel_path: string;
  title: string;
  mtime: number;
  size: number;
  chunk_count: number;
};

export type KnowledgeChunk = {
  id: number;
  file_path: string;
  rel_path: string;
  title: string;
  section: string;
  content: string;
  score?: number;
};

export const Knowledge = {
  getStatus: () => apiFetch<KnowledgeStatus>("/api/knowledge/status"),

  index: (path: string, force = false) =>
    apiFetch<{
      path: string;
      total_files: number;
      indexed_files: number;
      skipped_files: number;
      total_chunks: number;
      duration_ms: number;
    }>("/api/knowledge/index", {
      method: "POST",
      body: JSON.stringify({ path, force }),
    }),

  query: (query: string, top_k = 5) =>
    apiFetch<{ query: string; count: number; results: KnowledgeChunk[] }>(
      "/api/knowledge/query",
      {
        method: "POST",
        body: JSON.stringify({ query, top_k }),
      }
    ),

  listNotes: (limit = 100) =>
    apiFetch<{ count: number; notes: KnowledgeNote[] }>(
      `/api/knowledge/notes?limit=${limit}`
    ),

  toggle: (enabled: boolean) =>
    apiFetch<{ enabled: boolean }>("/api/knowledge/toggle", {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),

  clear: () =>
    apiFetch<{ cleared: boolean }>("/api/knowledge/index", {
      method: "DELETE",
    }),
};
