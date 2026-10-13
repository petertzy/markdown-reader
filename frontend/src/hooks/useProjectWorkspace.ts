"use client";

import { useCallback, useState } from "react";
import { isTauriRuntime } from "@/lib/tauri";

async function maximizeProjectWindow() {
  if (!isTauriRuntime()) {
    return;
  }

  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().maximize();
  } catch {
    // Opening a project remains available if the window API is unavailable.
  }
}

export function useProjectWorkspace() {
  const [projectRoot, setProjectRoot] = useState<string | null>(null);
  const openProject = useCallback(async () => {
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({ directory: true, multiple: false });
      if (typeof selected === "string") {
        setProjectRoot(selected);
        await maximizeProjectWindow();
        return true;
      }
    } catch {
      const supplied = window.prompt("Enter an absolute project folder path:");
      if (supplied?.trim()) {
        setProjectRoot(supplied.trim());
        return true;
      }
    }
    return false;
  }, []);
  return { projectRoot, openProject, closeProject: () => setProjectRoot(null) };
}
