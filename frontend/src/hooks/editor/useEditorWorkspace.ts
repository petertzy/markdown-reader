"use client";

/**
 * useEditorWorkspace.ts
 * =====================
 * Owns the Monaco editor instance lifecycle — the live instance ref, its
 * readiness flag, and a remount `revision` counter — so the homepage/frame
 * does not need to track editor-internal state directly.
 *
 * Exposes:
 *  - `monacoRef`  : shared mutable handle to the mounted Monaco instance
 *  - `monacoReady`: becomes true once the editor has mounted
 *  - `revision`   : bumped by `reset()` to force the editor to remount
 *  - `markReady`  : called from the editor component once mounted
 *  - `reset`      : tears down the current instance and bumps `revision`
 *                   (used e.g. when toggling focus mode)
 */

import { useCallback, useRef, useState } from "react";
import type { editor as MonacoEditor } from "monaco-editor";
import type { MutableRefObject } from "react";

export function useEditorWorkspace() {
  const monacoRef: MutableRefObject<MonacoEditor.IStandaloneCodeEditor | null> =
    useRef<MonacoEditor.IStandaloneCodeEditor | null>(null);
  const [monacoReady, setMonacoReady] = useState(false);
  const [revision, setRevision] = useState(0);

  const markReady = useCallback(() => setMonacoReady(true), []);

  const reset = useCallback(() => {
    setMonacoReady(false);
    monacoRef.current = null;
    setRevision((r) => r + 1);
  }, []);

  return { monacoRef, monacoReady, revision, markReady, reset };
}

export type EditorWorkspaceController = ReturnType<typeof useEditorWorkspace>;