"use client";

import { useCallback, useLayoutEffect, useRef, useState } from "react";
import type { useEditor } from "@/hooks/useEditor";
import { AI, type ProjectWorkTask } from "@/lib/api";
import {
  createProjectWorkRunGuard,
  projectTabsAreFresh,
  taskMatchesProject,
} from "@/lib/project-work-guard.mjs";
import { captureProjectWorkUndo, type ProjectWorkUndoEntry } from "@/lib/project-work-undo.mjs";

type Editor = ReturnType<typeof useEditor>;

export function useProjectWork(editor: Editor, projectRoot: string | null) {
  const [task, setTask] = useState<ProjectWorkTask | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const currentTabs = useRef(editor.tabs);
  const taskId = useRef<string | null>(null);
  const requestSnapshot = useRef(editor.tabs);
  const projectRootRef = useRef(projectRoot);
  const runGuard = useRef(createProjectWorkRunGuard());
  const [undoRecord, setUndoRecord] = useState<ProjectWorkUndoEntry[] | null>(null);

  useLayoutEffect(() => { currentTabs.current = editor.tabs; }, [editor.tabs]);

  const discard = useCallback(() => {
    runGuard.current.invalidate();
    if (taskId.current) void AI.discardProjectWork(taskId.current).catch(console.error);
    taskId.current = null;
    setTask(null);
    setBusy(false);
  }, []);

  useLayoutEffect(() => {
    if (projectRootRef.current === projectRoot) return;
    projectRootRef.current = projectRoot;
    discard();
    setUndoRecord(null);
  }, [discard, projectRoot]);

  const run = useCallback(async (instruction: string) => {
    if (!projectRoot || busy) return;
    discard();
    const runToken = runGuard.current.begin();
    const isCurrentRun = () => runGuard.current.isCurrent(runToken) && projectRootRef.current === projectRoot;
    requestSnapshot.current = currentTabs.current.map((tab) => ({ ...tab }));
    setBusy(true);
    setMessage("");
    try {
      const buffers = Object.fromEntries(currentTabs.current.flatMap((tab) => tab.filePath ? [[tab.filePath, tab.content]] : []));
      let next = await AI.startProjectWork(projectRoot, instruction, buffers);
      if (!isCurrentRun() || !taskMatchesProject(next.root, projectRoot)) {
        void AI.discardProjectWork(next.id).catch(console.error);
        return;
      }
      taskId.current = next.id;
      setTask(next);
      while (isCurrentRun() && next.status === "running") {
        next = await AI.stepProjectWork(next.id);
        if (!isCurrentRun() || !taskMatchesProject(next.root, projectRoot)) {
          void AI.discardProjectWork(next.id).catch(console.error);
          return;
        }
        setTask(next);
      }
    } catch (error) {
      if (isCurrentRun()) setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      if (isCurrentRun()) setBusy(false);
    }
  }, [busy, discard, projectRoot]);

  const apply = useCallback(async () => {
    if (!task || busy) return;
    if (!taskMatchesProject(task.root, projectRootRef.current)) {
      setMessage("This Project Work result belongs to a different project. Run the task again.");
      return;
    }
    const runToken = runGuard.current.current();
    const isCurrentRun = () => runGuard.current.isCurrent(runToken) && taskMatchesProject(task.root, projectRootRef.current);
    setBusy(true);
    try {
      await AI.validateProjectWork(task.id);
      if (!isCurrentRun()) return;
      if (!projectTabsAreFresh(requestSnapshot.current, currentTabs.current)) {
        throw new Error("Open documents changed while Project Work was running. Run the task again.");
      }
      const record = captureProjectWorkUndo(currentTabs.current, task.changes);
      editor.applyProjectChanges(task.changes);
      setUndoRecord(record);
      await AI.discardProjectWork(task.id);
      if (!isCurrentRun()) return;
      taskId.current = null;
      setTask(null);
      setMessage("Changes were staged in editor tabs. Review and save each file, or undo them.");
    } catch (error) {
      if (isCurrentRun()) setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      if (isCurrentRun()) setBusy(false);
    }
  }, [busy, editor, task]);

  const undo = useCallback(() => {
    if (!undoRecord || busy) return;
    const skipped = editor.revertProjectChanges(undoRecord);
    setUndoRecord(null);
    setMessage(skipped.length
      ? `Undid Project Work. These files were edited or saved afterwards and were left as they are:\n${skipped.join("\n")}`
      : "Undid Project Work. The affected tabs are back to their previous content.");
  }, [busy, editor, undoRecord]);

  return { task, busy, message, run, apply, discard, undo, canUndo: !!undoRecord && !busy };
}
