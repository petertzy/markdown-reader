"use client";

/**
 * SlashCommandMenu.tsx
 * =====================
 * Notion-style inline popover listing slash commands, positioned at the
 * Monaco text cursor. Pure presentation — selection/keyboard logic lives
 * in useSlashCommands.
 */

import type { SlashCommand } from "@/hooks/useSlashCommands";

type Props = {
  commands: SlashCommand[];
  selectedIndex: number;
  top: number;
  left: number;
  onSelect: (command: SlashCommand) => void;
  onClose: () => void;
};

export default function SlashCommandMenu({ commands, selectedIndex, top, left, onSelect, onClose }: Props) {
  if (commands.length === 0) {
    return (
      <div
        className="absolute z-50 bg-white dark:bg-[#252526] border border-gray-200 dark:border-gray-700 rounded shadow-lg w-64 p-3 text-xs text-gray-400"
        style={{ top, left }}
        onMouseLeave={onClose}
      >
        No matching commands
      </div>
    );
  }

  return (
    <div
      className="absolute z-50 bg-white dark:bg-[#252526] border border-gray-200 dark:border-gray-700 rounded shadow-lg w-64 py-1"
      style={{ top, left }}
      onMouseLeave={onClose}
    >
      {commands.map((command, index) => (
        <button
          key={command.id}
          onClick={() => onSelect(command)}
          className={`w-full text-left px-3 py-1.5 text-xs flex flex-col gap-0.5 ${
            index === selectedIndex
              ? "bg-blue-500 text-white"
              : "text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#2d2d2d]"
          }`}
        >
          <span className="font-medium">{command.label}</span>
          <span className={index === selectedIndex ? "text-blue-100" : "text-gray-400 dark:text-gray-500"}>
            {command.description}
          </span>
        </button>
      ))}
    </div>
  );
}
