"use client";

import type { WordCountResult } from "@/lib/api";

interface DocumentStatsProps {
  stats: WordCountResult | null;
  className?: string;
}

export default function DocumentStats({ stats, className }: DocumentStatsProps) {
  if (!stats) return null;

  return (
    <div className={`flex gap-4 text-sm text-gray-600 ${className ?? ""}`}>
      <span title="Word Count">📝 {stats.words.toLocaleString()} words</span>
      <span title="Character Count">🔤 {stats.chars_with_spaces.toLocaleString()} chars</span>
      <span title="Heading Count">📑 {stats.heading_count} headings</span>
      <span title="Estimated Reading Time">⏱️ {stats.reading_time}</span>
    </div>
  );
}
