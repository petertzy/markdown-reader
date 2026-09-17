"use client";

import { useCallback } from "react";
import type { MutableRefObject } from "react";
import type { editor as MonacoEditor } from "monaco-editor";

export type TransformResult = {
  text: string;
  cursorOffset?: number;
};

export type SelectionTransform = (selectedText: string) => TransformResult;

export function useEditorFormatting(
  monacoRef: MutableRefObject<MonacoEditor.IStandaloneCodeEditor | null>
) {
  const runMonacoAction = useCallback((actionId: string) => {
    const mono = monacoRef.current;
    if (!mono) return;
    mono.focus();
    mono.trigger("keyboard-shortcut", actionId, null);
  }, [monacoRef]);

  const replaceSelection = useCallback(
    (source: string, transform: SelectionTransform) => {
      const mono = monacoRef.current;
      const selection = mono?.getSelection();
      const model = mono?.getModel();
      if (!mono || !selection || !model) return;

      const selectedText = selection.isEmpty() ? "" : model.getValueInRange(selection);
      const { text, cursorOffset } = transform(selectedText);
      const startOffset = model.getOffsetAt(selection.getStartPosition());
      mono.executeEdits(source, [{ range: selection, text, forceMoveMarkers: true }]);
      if (selection.isEmpty() && typeof cursorOffset === "number") {
        mono.setPosition(model.getPositionAt(startOffset + cursorOffset));
      }
      mono.focus();
    },
    [monacoRef]
  );

  const wrapSelection = useCallback(
    (source: string, before: string, after = before) => {
      replaceSelection(source, (selectedText) => ({
        text: `${before}${selectedText}${after}`,
        cursorOffset: before.length,
      }));
    },
    [replaceSelection]
  );

  const applyHeading = useCallback(
    (level: 0 | 1 | 2 | 3) => {
      replaceSelection("heading", (selectedText) => {
        const content = selectedText || "Heading";
        const hashes = level === 0 ? "" : `${"#".repeat(level)} `;
        const normalized = content
          .split("\n")
          .map((line) => `${hashes}${line.replace(/^#{1,6}\s+/, "")}`)
          .join("\n");
        return { text: normalized, cursorOffset: normalized.length };
      });
    },
    [replaceSelection]
  );

  const insertTable = useCallback(() => {
    replaceSelection("insert-table", () => ({
      text: "| Column 1 | Column 2 | Column 3 |\n| --- | --- | --- |\n| Cell | Cell | Cell |",
    }));
  }, [replaceSelection]);

  const insertCitation = useCallback(
    (citationKey: string) => {
      replaceSelection("insert-citation", () => ({
        text: `[@${citationKey}]`,
        cursorOffset: `[@${citationKey}]`.length,
      }));
    },
    [replaceSelection]
  );

  return {
    runMonacoAction,
    replaceSelection,
    wrapSelection,
    applyHeading,
    insertTable,
    insertCitation,
  };
}

export type EditorFormattingController = ReturnType<typeof useEditorFormatting>;
