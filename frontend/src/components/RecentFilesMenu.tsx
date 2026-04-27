"use client";

/**
 * RecentFilesMenu.tsx
 * ===================
 * Dropdown showing recently opened files.
 */

type Props = {
  entries: string[];
  onOpen: (path: string) => void;
  onClear: () => void;
  onClose: () => void;
};

export default function RecentFilesMenu({ entries, onOpen, onClear, onClose }: Props) {
  if (entries.length === 0) {
    return (
      <div className="absolute left-0 top-full z-50 bg-white dark:bg-[#252526] border border-gray-200 dark:border-gray-700 rounded shadow-lg w-72 p-3 text-xs text-gray-400">
        No recent files
      </div>
    );
  }

  const truncate = (path: string, max = 52) => {
    if (path.length <= max) return path;
    const half = Math.floor((max - 1) / 2);
    return path.slice(0, half) + "…" + path.slice(-(max - half - 1));
  };

  return (
    <div
      className="absolute left-0 top-full z-50 bg-white dark:bg-[#252526] border border-gray-200 dark:border-gray-700 rounded shadow-lg w-80 py-1"
      onMouseLeave={onClose}
    >
      {entries.map((p) => (
        <button
          key={p}
          onClick={() => { onOpen(p); onClose(); }}
          className="w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-[#2d2d2d] truncate"
          title={p}
        >
          {truncate(p)}
        </button>
      ))}
      <div className="border-t border-gray-200 dark:border-gray-700 mt-1 pt-1">
        <button
          onClick={() => { onClear(); onClose(); }}
          className="w-full text-left px-3 py-1.5 text-xs text-red-500 hover:bg-gray-100 dark:hover:bg-[#2d2d2d]"
        >
          Clear recent files
        </button>
      </div>
    </div>
  );
}
