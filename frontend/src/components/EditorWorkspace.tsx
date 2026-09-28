"use client";

/**
 * EditorWorkspace.tsx
 * ===================
 * Encapsulates the Monaco editor pane together with its slash-command overlay,
 * isolating editor rendering from the surrounding layout and the homepage.
 *
 * It receives the shared `monacoRef` (owned by `useEditorWorkspace`), mounts
 * the editor, records the instance, and reports readiness via `onReady`.
 * Bumping `revision` (e.g. on a focus-mode toggle) forces the editor to remount.
 */

import type { MutableRefObject } from "react";
import type { editor as MonacoEditor } from "monaco-editor";
import type { SlashCommand } from "@/hooks/useSlashCommands";
import EditorPane from "@/components/EditorPane";
import SlashCommandMenu from "@/components/SlashCommandMenu";

export type EditorSlashOverlay = {
  isOpen: boolean;
  filteredCommands: SlashCommand[];
  selectedIndex: number;
  position: { top: number; height: number; left: number } | null;
  onSelect: (command: SlashCommand) => void;
  onClose: () => void;
};

export type EditorWorkspaceProps = {
  tabId: string;
  value: string;
  darkMode: boolean;
  fontSize: number;
  revision?: number;
  monacoRef: MutableRefObject<MonacoEditor.IStandaloneCodeEditor | null>;
  onChange: (value: string | undefined) => void;
  onReady: () => void;
  slash?: EditorSlashOverlay;
};

export default function EditorWorkspace({
  tabId,
  value,
  darkMode,
  fontSize,
  revision = 0,
  monacoRef,
  onChange,
  onReady,
  slash,
}: EditorWorkspaceProps) {
  return (
    <div className="relative h-full">
      <EditorPane
        key={`${tabId}-${revision}`}
        path={tabId}
        value={value}
        darkMode={darkMode}
        fontSize={fontSize}
        onChange={onChange}
        onMount={(instance) => {
          monacoRef.current = instance;
          onReady();
        }}
      />
      {slash?.isOpen && slash.position && (
        <SlashCommandMenu
          commands={slash.filteredCommands}
          selectedIndex={slash.selectedIndex}
          top={slash.position.top + slash.position.height}
          left={slash.position.left}
          onSelect={slash.onSelect}
          onClose={slash.onClose}
        />
      )}
    </div>
  );
}