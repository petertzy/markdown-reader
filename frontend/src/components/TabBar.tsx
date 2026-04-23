"use client";

import type { Tab } from "@/hooks/useEditor";

type Props = {
  tabs: Tab[];
  activeTabId: string;
  onSelect: (id: string) => void;
  onClose: (id: string) => void;
  onNew: () => void;
};

export default function TabBar({ tabs, activeTabId, onSelect, onClose, onNew }: Props) {
  return (
    <div className="flex items-center bg-gray-100 dark:bg-[#252526] border-b border-gray-200 dark:border-gray-700 overflow-x-auto select-none shrink-0">
      {tabs.map((tab) => (
        <div
          key={tab.id}
          onClick={() => onSelect(tab.id)}
          className={`
            flex items-center gap-1 px-3 py-1.5 text-sm cursor-pointer whitespace-nowrap border-r border-gray-200 dark:border-gray-700
            ${tab.id === activeTabId
              ? "bg-white dark:bg-[#1e1e1e] text-gray-900 dark:text-gray-100 font-medium"
              : "text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-[#2d2d2d]"}
          `}
        >
          <span className="max-w-[160px] truncate">{tab.label}</span>
          {tab.dirty && <span className="text-blue-500 text-xs leading-none">●</span>}
          <button
            onClick={(e) => { e.stopPropagation(); onClose(tab.id); }}
            className="ml-1 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 leading-none"
            aria-label="Close tab"
          >
            ×
          </button>
        </div>
      ))}
      <button
        onClick={onNew}
        className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-200 dark:hover:bg-[#2d2d2d]"
        aria-label="New tab"
        title="New tab"
      >
        +
      </button>
    </div>
  );
}
