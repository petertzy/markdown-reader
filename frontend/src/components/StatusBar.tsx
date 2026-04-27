"use client";

import type { WordCountResult } from "@/lib/api";

type Props = {
  stats: WordCountResult | null;
  filePath: string | null;
  dirty: boolean;
};

export default function StatusBar({ stats, filePath, dirty }: Props) {
  const name = filePath ? filePath.split(/[/\\]/).pop() : "Untitled";
  return (
    <div className="flex items-center justify-between px-3 py-0.5 text-xs bg-blue-600 text-white shrink-0 select-none">
      <span className="truncate max-w-[40%]">
        {name}{dirty ? " ●" : ""}
      </span>
      {stats && (
        <span className="flex gap-4 opacity-90">
          <span>{stats.words.toLocaleString()} words</span>
          <span>{stats.chars_with_spaces.toLocaleString()} chars</span>
          <span>{stats.reading_time}</span>
        </span>
      )}
    </div>
  );
}
