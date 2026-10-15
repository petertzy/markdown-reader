"use client";

import { useEffect, useState, useCallback } from "react";

interface Stats {
  words: number;
  chars_with_spaces: number;
  chars_without_spaces: number;
  heading_count: number;
  reading_time: string;
}

interface DocumentStatsProps {
  content: string;
  className?: string;
}

export default function DocumentStats({ content, className }: DocumentStatsProps) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchStats = useCallback(async (text: string) => {
    if (!text.trim()) {
      setStats({
        words: 0,
        chars_with_spaces: 0,
        chars_without_spaces: 0,
        heading_count: 0,
        reading_time: "< 1 min read",
      });
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/markdown/wordcount", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text }),
      });
      if (!res.ok) throw new Error("Failed to fetch stats");
      const data: Stats = await res.json();
      setStats(data);
    } catch (err) {
      console.error("DocumentStats fetch error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => fetchStats(content), 300); // debounce
    return () => clearTimeout(timeout);
  }, [content, fetchStats]);

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