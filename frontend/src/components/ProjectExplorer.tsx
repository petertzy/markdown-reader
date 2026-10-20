"use client";

import { useEffect, useState, useCallback } from "react";

interface ProjectExplorerProps {
  rootPath: string | null;
  refreshToken?: number;
  onClose?: () => void;
}

interface Entry {
  name: string;
  path: string;
  isDir: boolean;
}

export default function ProjectExplorer({ rootPath, refreshToken = 0, onClose }: ProjectExplorerProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [entries, setEntries] = useState<Entry[]>([]);

  const load = useCallback(async () => {
    if (!rootPath) return;
    try {
      const res = await fetch(`/api/fs/list?path=${encodeURIComponent(rootPath)}`);
      if (!res.ok) return;
      setEntries(await res.json());
    } catch (err) {
      console.error("ProjectExplorer load error:", err);
    }
  }, [rootPath]);

  useEffect(() => { void load(); }, [load, refreshToken]);

  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        title="Show Explorer"
        aria-label="Show Explorer"
        className="flex items-center justify-center rounded p-1 text-gray-500 hover:bg-gray-200 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-[#3a3d41] dark:hover:text-gray-100"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
          <path fillRule="evenodd" clipRule="evenodd" d="M10.072 8.024L5.715 3.667l.618-.62L11 8.024l-4.667 4.667-.618-.62 4.357-4.047z" />
        </svg>
      </button>
    );
  }

  return (
    <aside className="w-64 border-r border-gray-200 bg-white dark:border-[#333] dark:bg-[#252526] flex flex-col">
      <header className="flex items-center justify-between border-b border-gray-200 px-3 py-2 dark:border-[#333]">
        <span className="text-xs font-semibold uppercase text-gray-600 dark:text-gray-400">Explorer</span>
        <div className="flex gap-1">
          <button onClick={() => setCollapsed(true)} title="Hide Explorer" aria-label="Hide Explorer" aria-expanded
            className="flex items-center justify-center rounded p-1 text-gray-500 hover:bg-gray-200 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-[#3a3d41] dark:hover:text-gray-100">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
              <path fillRule="evenodd" clipRule="evenodd" d="M5.928 8.024L10.285 3.667l-.618-.62L5 8.024l4.667 4.667.618-.62-4.357-4.047z" />
            </svg>
          </button>
          {onClose && (
            <button onClick={onClose} title="Close" aria-label="Close" className="rounded p-1 text-gray-500 hover:bg-gray-200 dark:hover:bg-[#3a3d41]">✕</button>
          )}
        </div>
      </header>
      <ul className="flex-1 overflow-auto p-2 text-sm dark:text-gray-200">
        {entries.map((e) => (
          <li key={e.path} className="truncate rounded px-2 py-1 hover:bg-gray-100 dark:hover:bg-[#333]">
            {e.isDir ? "📁" : "📄"} {e.name}
          </li>
        ))}
        {!entries.length && <li className="px-2 py-1 text-xs text-gray-500">No project loaded.</li>}
      </ul>
    </aside>
  );
}