"use client";

import { useCallback, useEffect, useState } from "react";
import { AI, type ProjectTranslationTask } from "@/lib/api";

export function useProjectTranslation(projectRoot: string | null) {
  const [task, setTask] = useState<ProjectTranslationTask | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!task || task.status !== "running") return;
    const timer = window.setInterval(() => {
      void AI.projectTranslationStatus(task.id)
        .then(setTask)
        .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
    }, 800);
    return () => window.clearInterval(timer);
  }, [task]);

  const start = useCallback(async (sourceLanguage: string, targetLanguage: string) => {
    if (!projectRoot) return;
    setError("");
    try {
      setTask(await AI.startProjectTranslation({
        root: projectRoot,
        source_language: sourceLanguage || "auto",
        target_language: targetLanguage,
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, [projectRoot]);

  const cancel = useCallback(async () => {
    if (!task) return;
    try {
      setTask(await AI.cancelProjectTranslation(task.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, [task]);

  return { task, error, start, cancel };
}
