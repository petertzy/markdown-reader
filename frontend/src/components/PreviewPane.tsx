"use client";

/**
 * PreviewPane.tsx
 * ===============
 * Rendered Markdown HTML preview in an isolated iframe.
 *
 * Synced scrolling: when an editor instance is passed in, scrolling either
 * side scrolls the other to the same relative position, and (optionally)
 * clicking in the editor glides the preview to the clicked spot. The sync
 * logic lives in lib/preview-sync.mjs so the Node test suite can cover it.
 */

import { useCallback, useEffect, useMemo, useRef, type MutableRefObject } from "react";
import type { editor as MonacoEditor } from "monaco-editor";
import {
  ECHO_GUARD_MS,
  MSG_FROM_PREVIEW,
  MSG_PREVIEW_READY,
  MSG_SNAP,
  MSG_TO_PREVIEW,
  locateLine,
  scrollRatio,
  withSyncScript,
} from "@/lib/preview-sync.mjs";

type Props = {
  html: string;
  loading?: boolean;
  error?: string | null;
  /** Editor to keep in sync with the preview scroll position. */
  editorRef?: MutableRefObject<MonacoEditor.IStandaloneCodeEditor | null>;
  /** Changes whenever a new editor instance mounts, so listeners re-attach. */
  editorKey?: string | number | boolean;
  /** When true, clicking in the editor glides the preview to that spot. */
  snapOnClick?: boolean;
};

function editorRatio(ed: MonacoEditor.IStandaloneCodeEditor): number {
  return scrollRatio(ed.getScrollTop(), ed.getScrollHeight(), ed.getLayoutInfo().height);
}

export default function PreviewPane({ html, loading = false, error = null, editorRef, editorKey, snapOnClick = true }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const ignoreEditorUntil = useRef(0);

  const placeholder = error
    ? `<p style='color:#b91c1c;padding:24px;font-family:sans-serif'>Backend unavailable.</p>`
    : loading
      ? "<p style='color:#999;padding:24px;font-family:sans-serif'>Starting backend...</p>"
      : "<p style='color:#999;padding:24px;font-family:sans-serif'>Preview will appear here…</p>";

  const srcDoc = useMemo(
    () => (html && editorRef ? withSyncScript(html) : html || placeholder),
    [html, editorRef, placeholder],
  );

  const postToPreview = useCallback((message: Record<string, unknown>) => {
    iframeRef.current?.contentWindow?.postMessage(message, "*");
  }, []);

  // Editor -> preview
  useEffect(() => {
    const ed = editorRef?.current;
    if (!ed) return;
    const sub = ed.onDidScrollChange((e) => {
      if (!e.scrollTopChanged || Date.now() < ignoreEditorUntil.current) return;
      postToPreview({ type: MSG_TO_PREVIEW, ratio: editorRatio(ed) });
    });
    return () => sub.dispose();
  }, [editorRef, editorKey, postToPreview]);

  // Click in editor -> preview glides to that spot
  useEffect(() => {
    const ed = editorRef?.current;
    if (!ed || !snapOnClick) return;
    const sub = ed.onDidChangeCursorPosition((e) => {
      if (e.source !== "mouse") return;
      const model = ed.getModel();
      if (!model) return;
      const { heading, fraction } = locateLine(model.getLinesContent(), e.position.lineNumber);
      postToPreview({ type: MSG_SNAP, heading, fraction });
    });
    return () => sub.dispose();
  }, [editorRef, editorKey, snapOnClick, postToPreview]);

  // Preview -> editor, and restore position after each re-render
  useEffect(() => {
    if (!editorRef) return;
    const onMessage = (e: MessageEvent) => {
      if (e.source !== iframeRef.current?.contentWindow) return;
      const ed = editorRef.current;
      if (!ed || !e.data) return;
      if (e.data.type === MSG_PREVIEW_READY) {
        // The iframe reloads on every edit; put it back where the editor is.
        postToPreview({ type: MSG_TO_PREVIEW, ratio: editorRatio(ed) });
      } else if (e.data.type === MSG_FROM_PREVIEW && typeof e.data.ratio === "number") {
        const max = ed.getScrollHeight() - ed.getLayoutInfo().height;
        ignoreEditorUntil.current = Date.now() + ECHO_GUARD_MS;
        ed.setScrollTop(e.data.ratio * Math.max(0, max));
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [editorRef, postToPreview]);

  return (
    <div className="flex-1 overflow-hidden h-full bg-white dark:bg-[#1e1e1e] border-l border-gray-200 dark:border-gray-700">
      <iframe
        ref={iframeRef}
        title="Markdown Preview"
        srcDoc={srcDoc}
        className="w-full h-full border-none"
        sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox"
      />
    </div>
  );
}
