"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AI, type ProjectTranslationTask } from "@/lib/api";
import { createFinishTracker, createProjectScope } from "@/lib/project-translation-refresh.mjs";

export function useProjectTranslation(projectRoot: string | null, onFinished?: () => void) {
  const [task, setTask] = useState<ProjectTranslationTask | null>(null);
  const [error, setError] = useState("");
  const onFinishedRef = useRef(onFinished);
  onFinishedRef.current = onFinished;
  const scopeRef = useRef(createProjectScope());
  scopeRef.current.setRoot(projectRoot);
  const trackerRef = useRef(createFinishTracker());

  // A task belongs to one project: drop it when the root changes so its polling and completion cannot leak across projects.
  useEffect(() => {
    trackerRef.current.reset();
    setTask(null);
    setError("");
  }, [projectRoot]);

  // Translation writes its output tree on the backend; tell the caller to reload it.
  useEffect(() => {
    if (trackerRef.current.observe(task)) onFinishedRef.current?.();
  }, [task]);

  useEffect(() => {
    if (!task || task.status !== "running") return;
    const scope = scopeRef.current;
    const token = scope.token();
    const timer = window.setInterval(() => {
      void AI.projectTranslationStatus(task.id)
        .then((next) => {
          if (scope.isCurrent(token)) setTask((current) => (current?.id === task.id ? next : current));
        })
        .catch((reason: unknown) => {
          if (scope.isCurrent(token)) setError(reason instanceof Error ? reason.message : String(reason));
        });
    }, 800);
    return () => window.clearInterval(timer);
  }, [task]);

  const start = useCallback(async (sourceLanguage: string, targetLanguage: string) => {
    if (!projectRoot) return;
    const scope = scopeRef.current;
    const token = scope.token();
    setError("");
    try {
      const next = await AI.startProjectTranslation({
        root: projectRoot,
        source_language: sourceLanguage || "auto",
        target_language: targetLanguage,
      });
      if (scope.isCurrent(token)) setTask(next);
    } catch (reason) {
      if (scope.isCurrent(token)) setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, [projectRoot]);

  const cancel = useCallback(async () => {
    if (!task) return;
    const scope = scopeRef.current;
    const token = scope.token();
    try {
      const next = await AI.cancelProjectTranslation(task.id);
      if (scope.isCurrent(token)) setTask(next);
    } catch (reason) {
      if (scope.isCurrent(token)) setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, [task]);

  const retryFailed = useCallback(async () => {
    if (!task) return;
    const scope = scopeRef.current;
    const token = scope.token();
    setError("");
    try {
      const next = await AI.retryProjectTranslation(task.id);
      if (scope.isCurrent(token)) setTask(next);
    } catch (reason) {
      if (scope.isCurrent(token)) setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, [task]);

  return { task, error, start, cancel, retryFailed };
}
