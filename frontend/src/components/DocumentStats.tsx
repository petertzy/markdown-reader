"use client";

import { useEffect, useState, useCallback } from "react";
import { Markdown, type WordCountResult } from "@/lib/api";

interface DocumentStatsProps {
  content: string;
  className?: string;
}

export default function DocumentStats({ content, className }: DocumentStatsProps) {
  const [stats, setStats] = useState<WordCountResult | null>(null);

  const fetchStats = useCallback(async (text: string) => {
    if (!text.trim()) {
      setStats({ words: 0, chars_with_spaces: 0, chars_without_spaces: 0, heading_count: 0, reading_time: "< 1 min read" });
      return;
    }
    try {
      setStats(await Markdown.wordCount(text));
    } catch (err) {
      console.error("DocumentStats fetch error:", err);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => fetchStats(content), 300);
    return () => clearTimeout(t);
  }, [content, fetchStats]);

  if (!stats) return null;

  return (
    <div className={`flex gap-4 text-sm text-gray-600 dark:text-gray-400 ${className ?? ""}`}>
      <span>📝 {stats.words.toLocaleString()} words</span>
      <span>🔤 {stats.chars_with_spaces.toLocaleString()} chars</span>
      <span>📑 {stats.heading_count} headings</span>
      <span>⏱️ {stats.reading_time}</span>
    </div>
  );
}