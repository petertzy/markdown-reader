"use client";

import { useCallback, useEffect, useRef } from "react";
import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type { editor as MonacoEditor } from "monaco-editor";
import type { AIPanelTab } from "@/components/AIPanel";
import {
  isSlashTriggerPosition,
  type SlashCommand,
  type useSlashCommands,
} from "@/hooks/useSlashCommands";

export type UseSlashCommandWiringOptions = {
  monacoRef: MutableRefObject<MonacoEditor.IStandaloneCodeEditor | null>;
  monacoReady: boolean;
  slash: ReturnType<typeof useSlashCommands>;
  insertTable: () => void;
  executeAIPrompt: (prompt: string, documentText: string) => Promise<string | null | undefined>;
  documentText: string;
  syncSelectedText: () => void;
  setShowAIPanel: Dispatch<SetStateAction<boolean>>;
  setAiPanelInitialTab: Dispatch<SetStateAction<AIPanelTab | undefined>>;
};

export function useSlashCommandWiring({
  monacoRef,
  monacoReady,
  slash,
  insertTable,
  executeAIPrompt,
  documentText,
  syncSelectedText,
  setShowAIPanel,
  setAiPanelInitialTab,
}: UseSlashCommandWiringOptions) {
  const executeSlashCommand = useCallback(
    async (command: SlashCommand) => {
      const mono = monacoRef.current;
      const model = mono?.getModel();
      const trigger = slash.triggerPosition;
      const position = mono?.getPosition();
      if (mono && model && trigger && position) {
        mono.executeEdits("slash-command", [
          {
            range: {
              startLineNumber: trigger.lineNumber,
              startColumn: trigger.column - 1,
              endLineNumber: position.lineNumber,
              endColumn: position.column,
            },
            text: "",
          },
        ]);
        mono.focus();
      }
      slash.close();

      // Read the live buffer post-edit — documentText is React state
      // and has not yet caught up with the executeEdits call above.
      const text = model?.getValue() ?? documentText;

      if (command.kind === "insert-table") {
        insertTable();
        return;
      }
      if (command.kind === "open-translate-tab") {
        setAiPanelInitialTab("translate");
        setShowAIPanel(true);
        return;
      }
      if (!command.prompt) {
        alert(`AI command "${command.label}" is not available (automation templates failed to load).`);
        return;
      }
      try {
        const message = await executeAIPrompt(command.prompt, text);
        if (message) alert(message);
      } catch (err) {
        alert(`AI command failed: ${err instanceof Error ? err.message : String(err)}`);
      }
    },
    [
      documentText,
      executeAIPrompt,
      insertTable,
      monacoRef,
      setAiPanelInitialTab,
      setShowAIPanel,
      slash,
    ]
  );

  const slashRef = useRef({
    isOpen: slash.isOpen,
    triggerPosition: slash.triggerPosition,
    moveSelection: slash.moveSelection,
    close: slash.close,
    openAt: slash.openAt,
    getSelectedCommand: slash.getSelectedCommand,
    execute: executeSlashCommand,
  });

  useEffect(() => {
    slashRef.current = {
      isOpen: slash.isOpen,
      triggerPosition: slash.triggerPosition,
      moveSelection: slash.moveSelection,
      close: slash.close,
      openAt: slash.openAt,
      getSelectedCommand: slash.getSelectedCommand,
      execute: executeSlashCommand,
    };
  });

  useEffect(() => {
    const mono = monacoRef.current;
    if (!mono || !monacoReady) return;

    const handleSync = () => {
      syncSelectedText();
      const model = mono.getModel();
      const position = mono.getPosition();
      if (!model || !position) return;
      const s = slashRef.current;

      if (!s.isOpen) {
        if (isSlashTriggerPosition(model, position)) {
          s.openAt(position);
        }
        return;
      }

      const trigger = s.triggerPosition;
      if (!trigger || position.lineNumber !== trigger.lineNumber || position.column < trigger.column) {
        s.close();
        return;
      }
      const lineContent = model.getLineContent(trigger.lineNumber);
      if (lineContent.charAt(trigger.column - 2) !== "/") {
        s.close();
        return;
      }
      const queryText = model.getValueInRange({
        startLineNumber: trigger.lineNumber,
        startColumn: trigger.column,
        endLineNumber: position.lineNumber,
        endColumn: position.column,
      });
      if (/\s/.test(queryText)) {
        s.close();
        return;
      }
      slash.updateQuery(queryText);
    };

    const d1 = mono.onDidChangeModelContent(handleSync);
    const d2 = mono.onDidChangeCursorPosition(handleSync);
    const d3 = mono.onDidChangeCursorSelection(syncSelectedText);
    const d4 = mono.onKeyDown((event) => {
      const s = slashRef.current;
      if (!s.isOpen) return;
      const key = event.browserEvent.key;
      if (key === "ArrowDown") {
        event.preventDefault();
        event.stopPropagation();
        s.moveSelection(1);
      } else if (key === "ArrowUp") {
        event.preventDefault();
        event.stopPropagation();
        s.moveSelection(-1);
      } else if (key === "Enter") {
        const cmd = s.getSelectedCommand();
        if (cmd) {
          event.preventDefault();
          event.stopPropagation();
          void s.execute(cmd);
        }
      } else if (key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        s.close();
      }
    });

    return () => {
      d1.dispose();
      d2.dispose();
      d3.dispose();
      d4.dispose();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [monacoReady, syncSelectedText]);

  const slashMenuPosition =
    slash.isOpen && slash.triggerPosition && monacoRef.current
      ? monacoRef.current.getScrolledVisiblePosition(slash.triggerPosition)
      : null;

  return {
    executeSlashCommand,
    slashMenuPosition,
  };
}
