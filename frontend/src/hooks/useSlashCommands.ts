"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { editor, IPosition } from "monaco-editor";
import { AI, type AIAutomationTemplate } from "@/lib/api";

export type SlashCommandId =
  | "summarize"
  | "translate"
  | "format"
  | "toc"
  | "fix-code"
  | "insert-table";

export type SlashCommand = {
  id: SlashCommandId;
  label: string;
  description: string;
  kind: "ai" | "open-translate-tab" | "insert-table";
  prompt?: string;
};

const STATIC_COMMANDS: Omit<SlashCommand, "prompt">[] = [
  { id: "summarize", label: "/summarize", description: "Summarize the document with AI", kind: "ai" },
  { id: "translate", label: "/translate", description: "Open the Translate tab", kind: "open-translate-tab" },
  { id: "format", label: "/format", description: "Apply Markdown formatting with AI", kind: "ai" },
  { id: "toc", label: "/toc", description: "Generate a table of contents with AI", kind: "ai" },
  { id: "fix-code", label: "/fix-code", description: "Fix code block fences with AI", kind: "ai" },
  { id: "insert-table", label: "/insert-table", description: "Insert a Markdown table", kind: "insert-table" },
];

const TEMPLATE_ID_BY_COMMAND: Record<string, string> = {
  summarize: "generate_summary",
  format: "format_selection",
  toc: "generate_toc",
  "fix-code": "fix_code_blocks",
};

export function useSlashCommands() {
  const [templates, setTemplates] = useState<AIAutomationTemplate[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [triggerPosition, setTriggerPosition] = useState<IPosition | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);

  useEffect(() => {
    let cancelled = false;
    AI.getAutomationTemplates()
      .then((res) => {
        if (!cancelled) setTemplates(res.templates);
      })
      .catch(() => {
        // AI panel already surfaces backend errors; slash commands degrade to no AI prompts.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const commands = useMemo<SlashCommand[]>(
    () =>
      STATIC_COMMANDS.map((cmd) => {
        const templateId = TEMPLATE_ID_BY_COMMAND[cmd.id];
        const prompt = templateId ? templates.find((t) => t.id === templateId)?.prompt : undefined;
        return { ...cmd, prompt };
      }),
    [templates]
  );

  const filteredCommands = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) => c.id.includes(q) || c.label.toLowerCase().includes(q));
  }, [commands, query]);

  const openAt = useCallback((position: IPosition) => {
    setTriggerPosition(position);
    setQuery("");
    setSelectedIndex(0);
    setIsOpen(true);
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
    setTriggerPosition(null);
    setQuery("");
    setSelectedIndex(0);
  }, []);

  const updateQuery = useCallback((text: string) => {
    setQuery(text);
    setSelectedIndex(0);
  }, []);

  const moveSelection = useCallback(
    (delta: number) => {
      setSelectedIndex((prev) => {
        const count = filteredCommands.length;
        if (count === 0) return 0;
        return (prev + delta + count) % count;
      });
    },
    [filteredCommands.length]
  );

  const getSelectedCommand = useCallback(() => {
    return filteredCommands[selectedIndex] ?? null;
  }, [filteredCommands, selectedIndex]);

  return {
    isOpen,
    query,
    filteredCommands,
    triggerPosition,
    selectedIndex,
    openAt,
    close,
    updateQuery,
    moveSelection,
    getSelectedCommand,
  };
}

/**
 * True only when a "/" at `position` starts a fresh trigger: line-start
 * or preceded by whitespace, never mid-word (e.g. inside "foo/bar").
 */
export function isSlashTriggerPosition(model: editor.ITextModel, position: IPosition): boolean {
  const lineContent = model.getLineContent(position.lineNumber);
  const beforeCursor = lineContent.slice(0, position.column - 1);
  if (!beforeCursor.endsWith("/")) return false;
  const charBeforeSlash = beforeCursor.slice(-2, -1);
  return charBeforeSlash === "" || /\s/.test(charBeforeSlash);
}
