"use client";

/**
 * useEditor.ts
 * ============
 * Central state hook for the editor page.
 * Manages: open tabs, current file content, preview HTML,
 *          recent files, dirty state, word count stats.
 */

import { useState, useCallback, useRef } from "react";
import { Files, Markdown, Export, type ExportPayload, type WordCountResult } from "@/lib/api";

export type Tab = {
  id: string;
  label: string;       // Display name (filename)
  filePath: string | null;
  content: string;
  dirty: boolean;
};

function makeTab(id: string, label = "Untitled", content = "", filePath: string | null = null): Tab {
  return { id, label, content, filePath, dirty: false };
}

let _tabCounter = 0;
function nextTabId() {
  return `tab-${++_tabCounter}`;
}

export function useEditor() {
  const [tabs, setTabs] = useState<Tab[]>([makeTab(nextTabId())]);
  const [activeTabId, setActiveTabId] = useState<string>(tabs[0].id);
  const [previewHtml, setPreviewHtml] = useState<string>("");
  const [recentFiles, setRecentFiles] = useState<string[]>([]);
  const [wordCount, setWordCount] = useState<WordCountResult | null>(null);
  const [darkMode, setDarkMode] = useState(false);
  const [fontSize, setFontSize] = useState(14);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── derived state ──────────────────────────────────────────────────────────
  const activeTab = tabs.find((t) => t.id === activeTabId) ?? tabs[0];

  // ── helpers ────────────────────────────────────────────────────────────────
  const updateTab = useCallback((id: string, patch: Partial<Tab>) => {
    setTabs((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t)));
  }, []);

  // ── preview refresh ────────────────────────────────────────────────────────
  const refreshPreview = useCallback(
    (content: string, baseDirOverride?: string) => {
      const baseDir = baseDirOverride ?? (activeTab.filePath ? activeTab.filePath.replace(/[^/\\]+$/, "") : undefined);
      Markdown.render({ content, base_dir: baseDir, dark_mode: darkMode, font_size: fontSize })
        .then(({ html }) => setPreviewHtml(html))
        .catch(console.error);

      // Debounced word-count update
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        Markdown.wordCount(content).then(setWordCount).catch(console.error);
      }, 400);
    },
    [activeTab.filePath, darkMode, fontSize]
  );

  // ── content change ─────────────────────────────────────────────────────────
  const handleContentChange = useCallback(
    (value: string | undefined) => {
      const v = value ?? "";
      updateTab(activeTabId, { content: v, dirty: true });
      refreshPreview(v);
    },
    [activeTabId, updateTab, refreshPreview]
  );

  // ── file ops ───────────────────────────────────────────────────────────────
  const openFile = useCallback(
    async (filePath: string) => {
      // Check if already open
      const existing = tabs.find((t) => t.filePath === filePath);
      if (existing) {
        setActiveTabId(existing.id);
        refreshPreview(existing.content, filePath);
        return;
      }
      try {
        const { content } = await Files.read(filePath);
        const label = filePath.split(/[/\\]/).pop() ?? filePath;
        const id = nextTabId();
        const newTab = makeTab(id, label, content, filePath);
        setTabs((prev) => [...prev, newTab]);
        setActiveTabId(id);
        refreshPreview(content, filePath);
        // Record in recent files
        Files.addRecent(filePath)
          .then(({ entries }) => setRecentFiles(entries))
          .catch(console.error);
      } catch (err) {
        console.error("Failed to open file:", err);
      }
    },
    [tabs, refreshPreview]
  );

  const openTextAsTab = useCallback(
    (label: string, content: string, filePath: string | null = null) => {
      const id = nextTabId();
      const tabLabel = label.trim() || "Untitled";
      const newTab = makeTab(id, tabLabel, content, filePath);
      setTabs((prev) => [...prev, newTab]);
      setActiveTabId(id);
      refreshPreview(content, filePath ?? undefined);
    },
    [refreshPreview]
  );

  const saveFile = useCallback(
    async (filePath?: string) => {
      const path = filePath ?? activeTab.filePath;
      if (path) {
        await Files.write(path, activeTab.content);
        updateTab(activeTabId, { dirty: false, filePath: path, label: path.split(/[/\\]/).pop() ?? path });
        return;
      }

      // Save As flow: ask user for a destination when the tab has no path yet.
      const rawLabel = activeTab.label.trim() || "Untitled";
      const suggestedName = /\.[A-Za-z0-9]+$/.test(rawLabel) ? rawLabel : `${rawLabel}.md`;

      // In Tauri desktop mode, use native save dialog and persist via backend API.
      const isTauri = typeof window !== "undefined" && "__TAURI__" in window;
      if (isTauri) {
        try {
          const { save } = await import("@tauri-apps/plugin-dialog");
          const target = await save({
            defaultPath: suggestedName,
            filters: [{ name: "Markdown", extensions: ["md", "markdown", "txt"] }],
          });

          if (!target) return;

          const resolvedPath = Array.isArray(target) ? target[0] : target;
          await Files.write(resolvedPath, activeTab.content);
          updateTab(activeTabId, {
            dirty: false,
            filePath: resolvedPath,
            label: resolvedPath.split(/[/\\]/).pop() ?? resolvedPath,
          });
          Files.addRecent(resolvedPath)
            .then(({ entries }) => setRecentFiles(entries))
            .catch(console.error);
        } catch {
          // No dialog capability in runtime: silently no-op.
        }
        return;
      }

      // In browser mode, use the native file save picker when available.
      const maybePicker = (window as Window & {
        showSaveFilePicker?: (options?: {
          suggestedName?: string;
          types?: Array<{ description?: string; accept: Record<string, string[]> }>;
        }) => Promise<{
          createWritable: () => Promise<{
            write: (data: string) => Promise<void>;
            close: () => Promise<void>;
          }>;
          name?: string;
        }>;
      }).showSaveFilePicker;

      if (!maybePicker) return;

      try {
        const handle = await maybePicker({
          suggestedName,
          types: [
            {
              description: "Markdown files",
              accept: {
                "text/markdown": [".md", ".markdown"],
                "text/plain": [".txt"],
              },
            },
          ],
        });
        const writable = await handle.createWritable();
        await writable.write(activeTab.content);
        await writable.close();
        updateTab(activeTabId, { dirty: false, label: handle.name || suggestedName });
      } catch {
        // No picker capability (or picker cancelled): silently no-op.
      }
    },
    [activeTab, activeTabId, updateTab]
  );

  const newTab = useCallback(() => {
    const id = nextTabId();
    setTabs((prev) => [...prev, makeTab(id)]);
    setActiveTabId(id);
    setPreviewHtml("");
  }, []);

  const closeTab = useCallback(
    (id: string) => {
      setTabs((prev) => {
        const next = prev.filter((t) => t.id !== id);
        if (next.length === 0) {
          const fresh = makeTab(nextTabId());
          setActiveTabId(fresh.id);
          return [fresh];
        }
        if (id === activeTabId) {
          setActiveTabId(next[next.length - 1].id);
        }
        return next;
      });
    },
    [activeTabId]
  );

  // ── recent files ───────────────────────────────────────────────────────────
  const loadRecentFiles = useCallback(async () => {
    const { entries } = await Files.getRecent();
    setRecentFiles(entries);
  }, []);

  // ── export ─────────────────────────────────────────────────────────────────
  const exportAs = useCallback(
    async (format: "html" | "pdf" | "docx", outputPath?: string) => {
      const payload: ExportPayload = {
        content: activeTab.content,
        base_dir: activeTab.filePath?.replace(/[^/\\]+$/, ""),
        dark_mode: darkMode,
        font_size: fontSize,
        output_path: outputPath,
      };
      if (format === "html") return Export.toHtml(payload);
      if (format === "pdf") return Export.toPdf(payload);
      return Export.toDocx(payload);
    },
    [activeTab, darkMode, fontSize]
  );

  return {
    tabs,
    activeTabId,
    activeTab,
    previewHtml,
    recentFiles,
    wordCount,
    darkMode,
    fontSize,
    setActiveTabId,
    setDarkMode,
    setFontSize,
    handleContentChange,
    openFile,
    openTextAsTab,
    saveFile,
    newTab,
    closeTab,
    loadRecentFiles,
    refreshPreview,
    exportAs,
  };
}
