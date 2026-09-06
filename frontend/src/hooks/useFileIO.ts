"use client";

import { useCallback, useEffect, useRef } from "react";
import type { ChangeEvent, DragEvent, MutableRefObject } from "react";
import type { editor as MonacoEditor } from "monaco-editor";
import type { useEditor } from "@/hooks/useEditor";
import { Export, Files, type ExportPayload } from "@/lib/api";

const OPEN_FILE_EXTENSIONS = ["md", "markdown", "txt", "html", "htm", "pdf", "docx"];
const CONVERTIBLE_EXTENSIONS = new Set(["html", "htm", "pdf", "docx"]);
const SUPPORTED_FILE_EXTENSIONS = new Set(OPEN_FILE_EXTENSIONS);
type EditorController = ReturnType<typeof useEditor>;

function fileExtension(name: string) { return name.split(".").pop()?.toLowerCase() ?? ""; }
function isSupportedFile(name: string) { return SUPPORTED_FILE_EXTENSIONS.has(fileExtension(name)); }
function convertedMarkdownLabel(name: string) {
  const withoutExtension = name.replace(/\.[^/.]+$/, "");
  return `${withoutExtension || "converted"}.md`;
}
function arrayBufferToBase64(buffer: ArrayBuffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  return window.btoa(binary);
}
function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = filename; document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
}

type Options = {
  editor: EditorController;
  isDesktopRuntime: boolean;
  backendStatus: "starting" | "ready" | "error";
  monacoRef: MutableRefObject<MonacoEditor.IStandaloneCodeEditor | null>;
};

export function useFileIO({ editor, isDesktopRuntime, backendStatus, monacoRef }: Options) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const openFileRef = useRef(editor.openFile);
  const openTextAsTabRef = useRef(editor.openTextAsTab);
  const lastDroppedPathsRef = useRef<{ signature: string; at: number } | null>(null);
  const dragCounterRef = useRef(0);

  useEffect(() => {
    openFileRef.current = editor.openFile;
    openTextAsTabRef.current = editor.openTextAsTab;
  }, [editor.openFile, editor.openTextAsTab]);

  const handleOpenFile = useCallback(async () => {
    if (isDesktopRuntime && backendStatus !== "ready") return;
    let filePath: string | null = null;
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({ multiple: false, filters: [
        { name: "Supported documents", extensions: OPEN_FILE_EXTENSIONS },
        { name: "Markdown", extensions: ["md", "markdown", "txt"] },
        { name: "Convertible documents", extensions: ["html", "htm", "pdf", "docx"] },
      ] });
      filePath = selected ? (Array.isArray(selected) ? selected[0] : selected) : null;
    } catch {
      if (isDesktopRuntime) return;
      fileInputRef.current?.click();
      return;
    }
    if (!filePath) return;
    try { await editor.openFile(filePath); }
    catch (error) { alert(`Open failed: ${error instanceof Error ? error.message : String(error)}`); }
  }, [backendStatus, editor, isDesktopRuntime]);

  const handleFileInputChange = useCallback(async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      if (CONVERTIBLE_EXTENSIONS.has(fileExtension(file.name))) {
        const result = await Files.convertToMarkdown({ filename: file.name, content_base64: arrayBufferToBase64(await file.arrayBuffer()) });
        editor.openTextAsTab(convertedMarkdownLabel(file.name), result.markdown, null, null, true);
      } else editor.openTextAsTab(file.name, await file.text(), null);
    } catch (error) { alert(`Open failed: ${error instanceof Error ? error.message : String(error)}`); }
    finally { event.target.value = ""; }
  }, [editor]);

  const handleExport = useCallback(async (format: "html" | "pdf" | "docx") => {
    try {
      const content = monacoRef.current?.getValue() ?? editor.activeTab.content;
      const extension = format === "pdf" ? "pdf" : format === "docx" ? "docx" : "html";
      const defaultName = `${editor.activeTab.label.replace(/\.[^/.]+$/, "") || "document"}.${extension}`;
      let outputPath: string | undefined;
      try {
        const { save } = await import("@tauri-apps/plugin-dialog");
        const selected = await save({ defaultPath: defaultName, filters: [{ name: `${extension.toUpperCase()} files`, extensions: [extension] }] });
        if (!selected) return;
        outputPath = Array.isArray(selected) ? selected[0] : selected;
      } catch {
        if (format !== "html") { alert("PDF/DOCX export requires Tauri desktop app for save dialog."); return; }
        const payload: ExportPayload = { content, base_dir: editor.activeTab.filePath?.replace(/[^/\\]+$/, ""), dark_mode: editor.darkMode, font_size: editor.fontSize };
        downloadBlob(await Export.downloadHtml(payload), defaultName);
        return;
      }
      const result = await editor.exportAs(format, outputPath, content);
      if (result) alert(`Exported to:\n${result.path}`);
    } catch (error) { alert(`Export failed: ${error instanceof Error ? error.message : String(error)}`); }
  }, [editor, monacoRef]);

  const openDroppedPaths = useCallback(async (paths: string[]) => {
    const supportedPaths = paths.filter(isSupportedFile);
    if (!supportedPaths.length) return;
    const signature = supportedPaths.join("\n");
    const previous = lastDroppedPathsRef.current;
    const now = Date.now();
    if (previous?.signature === signature && now - previous.at < 750) return;
    lastDroppedPathsRef.current = { signature, at: now };
    for (const path of supportedPaths) {
      try { await openFileRef.current(path); }
      catch (error) { alert(`Open failed: ${error instanceof Error ? error.message : String(error)}`); }
    }
  }, []);

  useEffect(() => {
    if (!isDesktopRuntime) return;
    let cancelled = false; let unlisten: (() => void) | null = null;
    import("@tauri-apps/api/webview")
      .then(({ getCurrentWebview }) => getCurrentWebview().onDragDropEvent((event) => { if (event.payload.type === "drop") void openDroppedPaths(event.payload.paths); }))
      .then((cleanup) => { if (cancelled) cleanup(); else unlisten = cleanup; })
      .catch(console.error);
    return () => { cancelled = true; unlisten?.(); };
  }, [isDesktopRuntime, openDroppedPaths]);

  useEffect(() => {
    if (!isDesktopRuntime) return;
    let cancelled = false; let unlisten: (() => void) | null = null;
    const openPaths = (paths: string[]) => { if (paths.length) void openDroppedPaths(paths); };
    import("@tauri-apps/api/event")
      .then(({ listen }) => listen<string[]>("open-file-paths", (event) => openPaths(event.payload)))
      .then((cleanup) => { if (cancelled) cleanup(); else unlisten = cleanup; return import("@tauri-apps/api/core"); })
      .then(({ invoke }) => invoke<string[]>("take_pending_open_files"))
      .then((paths) => { if (!cancelled) openPaths(paths); })
      .catch(console.error);
    return () => { cancelled = true; unlisten?.(); };
  }, [isDesktopRuntime, openDroppedPaths]);

  const handleDragEnter = useCallback((event: DragEvent) => { event.preventDefault(); dragCounterRef.current += 1; }, []);
  const handleDragLeave = useCallback((event: DragEvent) => { event.preventDefault(); dragCounterRef.current -= 1; }, []);
  const handleDragOver = useCallback((event: DragEvent) => { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; }, []);
  const handleDrop = useCallback(async (event: DragEvent) => {
    event.preventDefault(); dragCounterRef.current = 0;
    const files = Array.from(event.dataTransfer.files);
    if (!files.length) return;
    if (isDesktopRuntime) {
      await openDroppedPaths(files.map((file) => (file as File & { path?: string }).path).filter((path): path is string => Boolean(path)));
      return;
    }
    for (const file of files) {
      if (!isSupportedFile(file.name)) continue;
      try {
        if (CONVERTIBLE_EXTENSIONS.has(fileExtension(file.name))) {
          const result = await Files.convertToMarkdown({ filename: file.name, content_base64: arrayBufferToBase64(await file.arrayBuffer()) });
          openTextAsTabRef.current(convertedMarkdownLabel(file.name), result.markdown, null, null, true);
        } else openTextAsTabRef.current(file.name, await file.text(), null);
      } catch (error) { alert(`Open failed: ${error instanceof Error ? error.message : String(error)}`); }
    }
  }, [isDesktopRuntime, openDroppedPaths]);

  return { fileInputRef, handleOpenFile, handleFileInputChange, handleExport, handleDragEnter, handleDragLeave, handleDragOver, handleDrop };
}
