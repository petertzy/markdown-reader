"use client";

import { useCallback, useLayoutEffect, useRef, useState } from "react";
import type { useEditor } from "@/hooks/useEditor";
import { AI, type ProjectWorkTask } from "@/lib/api";
import { projectTabsAreFresh } from "@/lib/project-work-guard.mjs";

type Editor = ReturnType<typeof useEditor>;

export function useProjectWork(editor: Editor, projectRoot: string | null) {
  const [task, setTask] = useState<ProjectWorkTask | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const currentTabs = useRef(editor.tabs);
  const taskId = useRef<string | null>(null);
  const cancelled = useRef(false);
  const requestSnapshot = useRef(editor.tabs);

  useLayoutEffect(() => { currentTabs.current = editor.tabs; }, [editor.tabs]);

  const discard = useCallback(() => {
    cancelled.current = true;
    if (taskId.current) void AI.discardProjectWork(taskId.current).catch(console.error);
    taskId.current = null;
    setTask(null);
    setBusy(false);
  }, []);

  const run = useCallback(async (instruction: string) => {
    if (!projectRoot || busy) return;
    discard();
    cancelled.current = false;
    requestSnapshot.current = currentTabs.current.map((tab) => ({ ...tab }));
    setBusy(true);
    setMessage("");
    try {
      const buffers = Object.fromEntries(currentTabs.current.flatMap((tab) => tab.filePath ? [[tab.filePath, tab.content]] : []));
      let next = await AI.startProjectWork(projectRoot, instruction, buffers);
      taskId.current = next.id;
      setTask(next);
      while (!cancelled.current && next.status === "running") {
        next = await AI.stepProjectWork(next.id);
        if (!cancelled.current) setTask(next);
      }
    } catch (error) {
      if (!cancelled.current) setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      if (!cancelled.current) setBusy(false);
    }
  }, [busy, discard, projectRoot]);

  const apply = useCallback(async () => {
    if (!task || busy) return;
    setBusy(true);
    try {
      await AI.validateProjectWork(task.id);
      if (!projectTabsAreFresh(requestSnapshot.current, currentTabs.current)) {
        throw new Error("Open documents changed while Project Work was running. Run the task again.");
      }
      editor.applyProjectChanges(task.changes);
      await AI.discardProjectWork(task.id);
      taskId.current = null;
      setTask(null);
      setMessage("Changes were staged in editor tabs. Review and save each file.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }, [busy, editor, task]);

  return { task, busy, message, run, apply, discard };
}
