"use client";

/**
 * EditorPane.tsx
 * ==============
 * Monaco-based Markdown editor pane.
 */

import dynamic from "next/dynamic";
import type { editor } from "monaco-editor";

// Monaco must be loaded client-side only (no SSR)
const MonacoEditor = dynamic(
  () => import("@monaco-editor/react").then((m) => m.default),
  { ssr: false }
);

type Props = {
  value: string;
  onChange: (value: string | undefined) => void;
  darkMode: boolean;
  fontSize: number;
  /** Called with the monaco editor instance after mount */
  onMount?: (editor: editor.IStandaloneCodeEditor) => void;
};

export default function EditorPane({ value, onChange, darkMode, fontSize, onMount }: Props) {
  return (
    <div className="flex-1 overflow-hidden h-full">
      <MonacoEditor
        height="100%"
        language="markdown"
        theme={darkMode ? "vs-dark" : "light"}
        value={value}
        onChange={onChange}
        onMount={onMount}
        options={{
          fontSize,
          wordWrap: "on",
          lineNumbers: "on",
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          tabSize: 2,
          insertSpaces: true,
          renderWhitespace: "selection",
          fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace",
          folding: true,
          glyphMargin: false,
          overviewRulerLanes: 0,
          quickSuggestions: false,
        }}
      />
    </div>
  );
}
