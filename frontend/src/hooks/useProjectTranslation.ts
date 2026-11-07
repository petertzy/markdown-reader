"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AI, type ProjectTranslationTask } from "@/lib/api";
import { isProjectTranslationFinished } from "@/lib/project-translation-refresh.mjs";

export function useProjectTranslation(projectRoot: string | null, onFinished?: () => void) {
  const [task, setTask] = useState<ProjectTranslationTask | null>(null);
  const [error, setError] = useState("");
  const onFinishedRef = useRef(onFinished);
  onFinishedRef.current = onFinished;
  const previousTaskRef = useRef<ProjectTranslationTask | null>(null);

  // A task belongs to one project: drop it when the root changes so its polling and completion cannot leak across projects.
  useEffect(() => {
    previousTaskRef.current = null;
    setTask(null);
    setError("");
  }, [projectRoot]);

  // Translation writes its output tree on the backend; tell the caller to reload it.
  useEffect(() => {
    if (isProjectTranslationFinished(previousTaskRef.current, task)) onFinishedRef.current?.();
    previousTaskRef.current = task;
  }, [task]);

  useEffect(() => {
    if (!task || task.status !== "running") return;
    const timer = window.setInterval(() => {
      void AI.projectTranslationStatus(task.id)
        .then((next) => setTask((current) => (current?.id === task.id ? next : current)))
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

  const retryFailed = useCallback(async () => {
    if (!task) return;
    setError("");
    try {
      setTask(await AI.retryProjectTranslation(task.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, [task]);

  return { task, error, start, cancel, retryFailed };
}
