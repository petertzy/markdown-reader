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
          const health = await fetch(`${candidate}/api/health`, {
            cache: "no-store",
          });
          if (health.ok) {
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
  init?: RequestInit
): Promise<T> {
  const base = await getBaseUrl();
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API ${path} → ${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

async function apiFetchBlob(
  path: string,
  init?: RequestInit
): Promise<Blob> {
  const base = await getBaseUrl();
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API ${path} → ${res.status}: ${detail}`);
  }
  return res.blob();
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
    apiFetch<{ markdown: string }>("/api/files/convert-to-markdown", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

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

export const Markdown = {
  render: (payload: RenderPayload) =>
    apiFetch<{ html: string }>("/api/markdown/render", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  htmlToMarkdown: (html: string) =>
    apiFetch<{ markdown: string }>("/api/markdown/convert/html", {
      method: "POST",
      body: JSON.stringify({ html }),
    }),

  pdfToMarkdown: (path: string, use_docling = false) =>
    apiFetch<{ markdown: string }>("/api/markdown/convert/pdf", {
      method: "POST",
      body: JSON.stringify({ path, use_docling }),
    }),

  wordCount: (content: string) =>
    apiFetch<WordCountResult>("/api/markdown/wordcount", {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
};

// ── AI API ────────────────────────────────────────────────────────────────────

export type AgentChatPayload = {
  message: string;
  document_text?: string;
  selected_text?: string;
  chat_history?: { role: string; content: string }[];
};

export type AgentResponse = {
  assistant_message: string;
  proposed_action: {
    type: "replace_document" | "replace_selection" | "none";
    content: string;
    reason: string;
  };
  used_provider: string;
};

export const AI = {
  getSettings: () => apiFetch<Record<string, unknown>>("/api/ai/settings"),

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
    apiFetch<{ provider: string; models: string[] }>(
      `/api/ai/models/${provider}${base_url_override ? `?base_url_override=${encodeURIComponent(base_url_override)}` : ""}`
    ),

  chat: (payload: AgentChatPayload) =>
    apiFetch<AgentResponse>("/api/ai/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getChatHistory: () =>
    apiFetch<{ histories: unknown[] }>("/api/ai/chat/history"),

  saveChatHistory: (histories: unknown[]) =>
    apiFetch<{ saved: boolean }>("/api/ai/chat/history", {
      method: "POST",
      body: JSON.stringify(histories),
    }),

  getAutomationTemplates: () =>
    apiFetch<{ templates: unknown[] }>("/api/ai/automation/templates"),

  getAutomationLogs: (limit = 100) =>
    apiFetch<{ logs: unknown[] }>(`/api/ai/automation/logs?limit=${limit}`),

  translate: (content: string, source_language: string, target_language: string) =>
    apiFetch<{ translated: string }>("/api/ai/translate", {
      method: "POST",
      body: JSON.stringify({ content, source_language, target_language }),
    }),
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
    apiFetch<{ path: string }>("/api/export/html", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  downloadHtml: (payload: ExportPayload) =>
    apiFetchBlob("/api/export/html/download", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  toPdf: (payload: ExportPayload) =>
    apiFetch<{ path: string }>("/api/export/pdf", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  toDocx: (payload: ExportPayload) =>
    apiFetch<{ path: string }>("/api/export/docx", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
