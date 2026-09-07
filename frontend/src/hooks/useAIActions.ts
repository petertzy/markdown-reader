"use client";

import { useCallback, useState, type RefObject } from "react";
import type { editor as MonacoEditor } from "monaco-editor";
import { AI } from "@/lib/api";

type UseAIActionsOptions = {
  documentText: string;
  editorRef: RefObject<MonacoEditor.IStandaloneCodeEditor>;
  onDocumentChange: (content: string) => void;
};

export function useAIActions({
  documentText,
  editorRef,
  onDocumentChange,
}: UseAIActionsOptions) {
  const [selectedText, setSelectedText] = useState("");

  const getSelectedText = useCallback(() => {
    const editor = editorRef.current;
    const selection = editor?.getSelection();
    if (!editor || !selection) return "";
    return editor.getModel()?.getValueInRange(selection) ?? "";
  }, [editorRef]);

  const syncSelectedText = useCallback(() => {
    setSelectedText(getSelectedText());
  }, [getSelectedText]);

  const applyAction = useCallback(
    (type: string, content: string) => {
      if (type === "replace_document") {
        onDocumentChange(content);
        return;
      }

      if (type === "insert_below_document") {
        const separator = documentText.endsWith("\n") ? "\n" : "\n\n";
        onDocumentChange(`${documentText}${separator}${content}`);
        return;
      }

      const editor = editorRef.current;
      const model = editor?.getModel();
      const selection = editor?.getSelection();

      if (type === "replace_selection") {
        if (!editor) return;
        if (selection) {
          editor.executeEdits("ai-replace", [{ range: selection, text: content }]);
        } else {
          onDocumentChange(content);
        }
        return;
      }

      if (type === "insert_below_selection" || type === "insert_below") {
        if (editor && model && selection && !selection.isEmpty()) {
          const selectionText = model.getValueInRange(selection);
          const separator = selectionText.endsWith("\n") ? "\n" : "\n\n";
          editor.executeEdits("ai-insert-below", [
            {
              range: {
                startLineNumber: selection.endLineNumber,
                startColumn: selection.endColumn,
                endLineNumber: selection.endLineNumber,
                endColumn: selection.endColumn,
              },
              text: `${separator}${content}`,
            },
          ]);
        } else {
          const separator = documentText.endsWith("\n") ? "\n" : "\n\n";
          onDocumentChange(`${documentText}${separator}${content}`);
        }
      }
    },
    [documentText, editorRef, onDocumentChange]
  );

  const executePrompt = useCallback(
    async (prompt: string, currentDocumentText = documentText) => {
      const result = await AI.chat({
        message: prompt,
        document_text: currentDocumentText,
        selected_text: getSelectedText(),
        chat_history: [],
      });
      if (result.proposed_action.type !== "none") {
        applyAction(result.proposed_action.type, result.proposed_action.content);
        return null;
      }
      return result.assistant_message || null;
    },
    [applyAction, documentText, getSelectedText]
  );

  return {
    selectedText,
    syncSelectedText,
    applyAction,
    executePrompt,
  };
}
