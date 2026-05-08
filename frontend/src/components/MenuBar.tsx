"use client";

import { useEffect, useRef, useState } from "react";
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

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpenMenu(null);
      }
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
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
            onMouseEnter={() => {
              if (openMenu) setOpenMenu(group.label);
            }}
            role="menuitem"
            aria-haspopup="menu"
            aria-expanded={openMenu === group.label}
          >
            {group.label}
          </button>
          {openMenu === group.label && (
            <div
              className="absolute left-0 top-full z-50 mt-0.5 min-w-[220px] overflow-hidden rounded-md border border-gray-200 bg-white py-1 shadow-lg dark:border-gray-700 dark:bg-[#252526]"
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

                return (
                  <button
                    key={item.id}
                    type="button"
                    className="flex w-full items-center justify-between gap-6 px-3 py-1.5 text-left text-gray-700 hover:bg-blue-50 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-gray-700 dark:text-gray-200 dark:hover:bg-blue-950/40 dark:hover:text-blue-200 dark:disabled:hover:bg-transparent dark:disabled:hover:text-gray-200"
                    onClick={() => {
                      item.onSelect();
                      setOpenMenu(null);
                    }}
                    disabled={item.disabled}
                    role="menuitem"
                  >
                    <span>{item.label}</span>
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      {shortcutLabelById.get(item.id) ?? ""}
                    </span>
                  </button>
                );
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
