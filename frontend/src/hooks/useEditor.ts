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
import { needsConversion } from "@/lib/supportedFormats";
import { resolveTabClose } from "@/lib/tabLifecycle.mjs";
import { settleSavedTab } from "@/lib/save-settle.mjs";
import { parentDirOf, resolvePreviewBaseDir } from "@/lib/preview-base-dir.mjs";

export type Tab = {
  id: string;
  label: string;       // Display name (filename)
  filePath: string | null;
  /**
   * Folder relative image paths resolve against. Normally the parent of
   * `filePath`, but a document converted on open (html/pdf/docx) has no
   * `filePath` yet still needs the folder it came from.
   */
  previewBaseDir?: string;
  browserHandle?: FileSystemFileHandle | null;
  content: string;
  dirty: boolean;
};

function convertedMarkdownLabel(name: string) {
  const baseName = name.split(/[/\\]/).pop() ?? name;
  const withoutExtension = baseName.replace(/\.[^/.]+$/, "");
  return `${withoutExtension || "converted"}.md`;
}

function makeTab(
  id: string,
  label = "Untitled",
  content = "",
  filePath: string | null = null,
  browserHandle: FileSystemFileHandle | null = null,
  previewBaseDir?: string
): Tab {
  return {
    id,
    label,
    content,
    filePath,
    previewBaseDir: previewBaseDir ?? parentDirOf(filePath),
    browserHandle,
    dirty: false,
  };
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

  // ── preview refresh ────────────────────────────────────────────────────────
  const refreshPreview = useCallback(
    (content: string, baseDirOverride?: string) => {
      const baseDir = resolvePreviewBaseDir(
        baseDirOverride,
        activeTab.previewBaseDir,
        activeTab.filePath
      );
      Markdown.render({ content, base_dir: baseDir, dark_mode: darkMode, font_size: fontSize })
        .then(({ html }) => setPreviewHtml(html))
        .catch(console.error);

      // Debounced word-count update
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        Markdown.wordCount(content).then(setWordCount).catch(console.error);
      }, 400);
    },
    [activeTab.previewBaseDir, activeTab.filePath, darkMode, fontSize]
  );

  // ── content change ─────────────────────────────────────────────────────────
  const handleContentChange = useCallback(
    (value: string | undefined) => {
      if (typeof value !== "string") return;
      const v = value;
      if (activeTab.content === v) return;

      setTabs((prev) =>
        prev.map((t) => {
          if (t.id !== activeTabId) return t;
          return { ...t, content: v, dirty: true };
        })
      );

      refreshPreview(v, activeTab.filePath ?? undefined);
    },
    [activeTab.content, activeTab.filePath, activeTabId, refreshPreview]
  );

  // ── file ops ───────────────────────────────────────────────────────────────
  const openFile = useCallback(
    async (filePath: string) => {
      if (needsConversion(filePath)) {
        try {
          const { markdown } = await Files.convertToMarkdown({ path: filePath });
          const label = convertedMarkdownLabel(filePath);
          const id = nextTabId();
          const newTab = {
            ...makeTab(id, label, markdown, null, null, parentDirOf(filePath)),
            dirty: true,
          };
          setTabs((prev) => [...prev, newTab]);
          setActiveTabId(id);
          refreshPreview(markdown, newTab.previewBaseDir);
          Files.addRecent(filePath)
            .then(({ entries }) => setRecentFiles(entries))
            .catch(console.error);
        } catch (err) {
          console.error("Failed to convert file:", err);
          throw err;
        }
        return;
      }

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
        const newTab = makeTab(id, label, content, filePath, null);
        setTabs((prev) => [...prev, newTab]);
        setActiveTabId(id);
        refreshPreview(content, filePath);
        // Record in recent files
        Files.addRecent(filePath)
          .then(({ entries }) => setRecentFiles(entries))
          .catch(console.error);
      } catch (err) {
        console.error("Failed to open file:", err);
        throw err;
      }
    },
    [tabs, refreshPreview]
  );

  const openTextAsTab = useCallback(
    (
      label: string,
      content: string,
      filePath: string | null = null,
      browserHandle: FileSystemFileHandle | null = null,
      dirty = false
    ) => {
      const id = nextTabId();
      const tabLabel = label.trim() || "Untitled";
      const newTab = { ...makeTab(id, tabLabel, content, filePath, browserHandle), dirty };
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
        // Snapshot what is being written, then compare it against the buffer
        // after the round trip: anything typed in between is not on disk and
        // must stay marked dirty.
        const writtenContent = activeTab.content;
        await Files.write(path, writtenContent);
        setTabs((prev) =>
          prev.map((t) =>
            t.id === activeTabId
              ? {
                  ...t,
                  ...settleSavedTab({
                    writtenContent,
                    currentContent: t.content,
                    savedPath: path,
                  }),
                  previewBaseDir: parentDirOf(path),
                }
              : t
          )
        );
        Files.addRecent(path)
          .then(({ entries }) => setRecentFiles(entries))
          .catch(console.error);
        return;
      }

      const rawLabel = activeTab.label.trim() || "Untitled";
      const suggestedName = /\.[A-Za-z0-9]+$/.test(rawLabel) ? rawLabel : `${rawLabel}.md`;

      try {
        const { save } = await import("@tauri-apps/plugin-dialog");
        const selected = await save({
          defaultPath: suggestedName,
          filters: [{ name: "Markdown", extensions: ["md", "markdown", "txt"] }],
        });

        if (!selected) return;

        const resolvedPath = Array.isArray(selected) ? selected[0] : selected;
        const writtenContent = activeTab.content;
        await Files.write(resolvedPath, writtenContent);
        setTabs((prev) =>
          prev.map((t) =>
            t.id === activeTabId
              ? {
                  ...t,
                  ...settleSavedTab({
                    writtenContent,
                    currentContent: t.content,
                    savedPath: resolvedPath,
                  }),
                  previewBaseDir: parentDirOf(resolvedPath),
                  browserHandle: null,
                }
              : t
          )
        );
        Files.addRecent(resolvedPath)
          .then(({ entries }) => setRecentFiles(entries))
          .catch(console.error);
        return;
      } catch {
        // Outside Tauri native runtime, keep silent.
      }

      // No explicit path available and no native save dialog capability.
      return;
    },
    [activeTab, activeTabId]
  );

  const newTab = useCallback(() => {
    const id = nextTabId();
    setTabs((prev) => [...prev, makeTab(id)]);
    setActiveTabId(id);
    setPreviewHtml("");
  }, []);

  const closeTab = useCallback(
    (id: string) => {
      const { remaining, nextActiveTabId, previewTab } = resolveTabClose(tabs, activeTabId, id);
      if (remaining.length === 0) {
        // Closing the last tab leaves a fresh empty tab behind, so the preview
        // and word count of the document that was just closed must not linger.
        const fresh = makeTab(nextTabId());
        setTabs([fresh]);
        setActiveTabId(fresh.id);
        setPreviewHtml("");
        setWordCount(null);
        return;
      }
      setTabs(remaining);
      if (nextActiveTabId) setActiveTabId(nextActiveTabId);
      // The preview pane and the status-bar word count still show the closed
      // document unless they are refreshed for the tab that became active.
      if (previewTab) {
        refreshPreview(
          previewTab.content,
          previewTab.previewBaseDir ?? previewTab.filePath ?? undefined
        );
      }
    },
    [tabs, activeTabId, refreshPreview]
  );

  const closeAllTabs = useCallback(() => {
    const fresh = makeTab(nextTabId());
    setTabs([fresh]);
    setActiveTabId(fresh.id);
    setPreviewHtml("");
    setWordCount(null);
  }, []);

  // ── recent files ───────────────────────────────────────────────────────────
  const loadRecentFiles = useCallback(async () => {
    const { entries } = await Files.getRecent();
    setRecentFiles(entries);
  }, []);

  // ── export ─────────────────────────────────────────────────────────────────
  const exportAs = useCallback(
    async (format: "html" | "pdf" | "docx", outputPath?: string, contentOverride?: string) => {
      const payload: ExportPayload = {
        content: contentOverride ?? activeTab.content,
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
    closeAllTabs,
    loadRecentFiles,
    refreshPreview,
    exportAs,
  };
}
