"use client";

import { useEffect, useRef, useState } from "react";
import type {
  MouseEvent as ReactMouseEvent,
  PointerEvent as ReactPointerEvent,
} from "react";
import {
  DEFAULT_SHORTCUTS,
  type ActionId,
  type ShortcutDefinition,
  formatShortcut,
} from "@/lib/keyboardShortcuts";

export type MenuCommand = {
  id: ActionId;
  label: string;
  onSelect: () => void;
  disabled?: boolean;
};

export type MenuGroup = {
  label: string;
  items: Array<MenuCommand | "separator">;
  /** When set, the menu opens as a wide panel with these columns instead of a list. */
  columns?: Array<{ heading: string; items: MenuCommand[] }>;
};

type Props = {
  groups: MenuGroup[];
  shortcuts: ShortcutDefinition[];
};

export default function MenuBar({ groups, shortcuts }: Props) {
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const shortcutLabelById = new Map(
    shortcuts.map((shortcut) => [shortcut.id, formatShortcut(shortcut.bindings[0])])
  );
  const keepEditorFocused = (event: ReactMouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
  };
  const keepEditorFocusedOnPointerDown = (event: ReactPointerEvent<HTMLButtonElement>) => {
    event.preventDefault();
  };

  const renderCommand = (item: MenuCommand, compact = false) => (
    <button
      key={item.id}
      type="button"
      className={`flex w-full items-center justify-between ${compact ? "gap-4 px-2 py-1 rounded" : "gap-6 px-3 py-1.5"} text-left text-gray-700 hover:bg-blue-50 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-gray-700 dark:text-gray-200 dark:hover:bg-blue-950/40 dark:hover:text-blue-200 dark:disabled:hover:bg-transparent dark:disabled:hover:text-gray-200`}
      onClick={() => {
        item.onSelect();
        setOpenMenu(null);
      }}
      onPointerDown={keepEditorFocusedOnPointerDown}
      onMouseDown={keepEditorFocused}
      disabled={item.disabled}
      role="menuitem"
    >
      <span className="truncate">{item.label}</span>
      <span className="shrink-0 whitespace-nowrap text-xs text-gray-400 dark:text-gray-500">
        {shortcutLabelById.get(item.id) ?? ""}
      </span>
    </button>
  );

  useEffect(() => {
    const closeOnOutsidePointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpenMenu(null);
      }
    };

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpenMenu(null);
      }
    };

    const closeOnBlur = () => {
      setOpenMenu(null);
    };

    window.addEventListener("pointerdown", closeOnOutsidePointerDown, true);
    window.addEventListener("keydown", closeOnEscape);
    window.addEventListener("blur", closeOnBlur);

    return () => {
      window.removeEventListener("pointerdown", closeOnOutsidePointerDown, true);
      window.removeEventListener("keydown", closeOnEscape);
      window.removeEventListener("blur", closeOnBlur);
    };
  }, []);

  return (
    <div
      ref={rootRef}
      className="flex items-center h-8 px-2 bg-gray-50 dark:bg-[#2d2d2d] border-b border-gray-200 dark:border-gray-700 text-sm select-none shrink-0"
      role="menubar"
    >
      {groups.map((group) => (
        <div key={group.label} className="relative">
          <button
            type="button"
            className={`px-3 py-1 rounded-sm text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-[#3a3a3a] ${
              openMenu === group.label ? "bg-gray-200 dark:bg-[#3a3a3a]" : ""
            }`}
            onClick={() => setOpenMenu((current) => (current === group.label ? null : group.label))}
            onPointerDown={keepEditorFocusedOnPointerDown}
            onMouseDown={keepEditorFocused}
            onMouseEnter={() => {
              if (openMenu) setOpenMenu(group.label);
            }}
            role="menuitem"
            aria-haspopup="menu"
            aria-expanded={openMenu === group.label}
          >
            {group.label}
          </button>
          {openMenu === group.label && group.columns && (
            <div
              className="fixed left-2 top-8 z-50 mt-0.5 grid max-h-[calc(100vh-3rem)] gap-x-4 gap-y-3 overflow-y-auto rounded-md border border-gray-200 bg-white p-3 text-[13px] shadow-lg dark:border-gray-700 dark:bg-[#252526]"
              role="menu"
              aria-label={group.label}
              style={{ width: "min(60rem, calc(100vw - 1rem))", gridTemplateColumns: "repeat(auto-fit, minmax(12.5rem, 1fr))" }}
            >
              {group.columns.map((column) => (
                <div key={column.heading} role="group" aria-label={column.heading}>
                  <div className="mb-1 px-2 text-[11px] font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">
                    {column.heading}
                  </div>
                  {column.items.map((item) => renderCommand(item, true))}
                </div>
              ))}
            </div>
          )}
          {openMenu === group.label && !group.columns && (
            <div
              className="absolute left-0 top-full z-50 mt-0.5 max-h-[calc(100vh-3rem)] min-w-[220px] overflow-y-auto overflow-x-hidden rounded-md border border-gray-200 bg-white py-1 shadow-lg dark:border-gray-700 dark:bg-[#252526]"
              role="menu"
            >
              {group.items.map((item, index) => {
                if (item === "separator") {
                  return (
                    <div
                      key={`${group.label}-separator-${index}`}
                      className="my-1 h-px bg-gray-200 dark:bg-gray-700"
                    />
                  );
                }

                return renderCommand(item);
              })}
            </div>
          )}
        </div>
      ))}
      <div className="ml-auto flex items-center gap-2 text-xs text-gray-400 dark:text-gray-500">
        {DEFAULT_SHORTCUTS.length} shortcuts
      </div>
    </div>
  );
}
