"use client";

import { useCallback, useState } from "react";

export function useProjectWorkspace() {
  const [projectRoot, setProjectRoot] = useState<string | null>(null);
  const openProject = useCallback(async () => {
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({ directory: true, multiple: false });
      if (typeof selected === "string") {
        setProjectRoot(selected);
        return selected;
      }
    } catch {
      const supplied = window.prompt("Enter an absolute project folder path:");
      if (supplied?.trim()) {
        setProjectRoot(supplied.trim());
        return supplied.trim();
      }
    }
    return null;
  }, []);
  return { projectRoot, openProject, closeProject: () => setProjectRoot(null) };
}
