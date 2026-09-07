"use client";

import { useEffect, useState } from "react";
import type { useEditor } from "@/hooks/useEditor";
import { getBaseUrl } from "@/lib/api";
import { isTauriRuntime, shouldShowPackagedBackendStatus } from "@/lib/tauri";

type EditorController = ReturnType<typeof useEditor>;

export function useTauriBackend(editor: EditorController) {
  const [isDesktopRuntime, setIsDesktopRuntime] = useState(false);
  const [backendStatus, setBackendStatus] = useState<"starting" | "ready" | "error">("ready");
  const [backendMessage, setBackendMessage] = useState<string | null>(null);
  const showPackagedBackendStatus = shouldShowPackagedBackendStatus();

  useEffect(() => {
    let cancelled = false;
    const detectedRuntime = isTauriRuntime();
    const showStatus = shouldShowPackagedBackendStatus();
    setIsDesktopRuntime(detectedRuntime);

    async function initialise() {
      try {
        if (showStatus) {
          setBackendStatus("starting");
          await getBaseUrl();
        }
        if (cancelled) return;
        setBackendStatus("ready");
        setBackendMessage(null);
        await editor.loadRecentFiles();
        if (!cancelled && editor.activeTab.content) editor.refreshPreview(editor.activeTab.content);
      } catch (error) {
        console.error(error);
        if (!cancelled) {
          setBackendStatus(showStatus ? "error" : "ready");
          setBackendMessage(showStatus && error instanceof Error ? error.message : null);
        }
      }
    }

    void initialise();
    return () => { cancelled = true; };
    // Startup intentionally runs once when the page mounts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { isDesktopRuntime, backendStatus, backendMessage, showPackagedBackendStatus };
}
