"use client";

import { useState, useCallback, useEffect } from "react";
import { Citations, type CitationEntry } from "@/lib/api";

type Props = {
  onInsert: (citationKey: string) => void;
};

export default function CitationPanel({ onInsert }: Props) {
  const [libraryPath, setLibraryPath] = useState("");
  const [pathInput, setPathInput] = useState("");
  const [query, setQuery] = useState("");
  const [entries, setEntries] = useState<CitationEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadInitial = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await Citations.list();
      setLibraryPath(result.path);
      setEntries(result.entries);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const handleLoadLibrary = async () => {
    const path = pathInput.trim();
    if (!path) return;
    setLoading(true);
    setError(null);
    try {
      const result = await Citations.load(path);
      setLibraryPath(result.path);
      setEntries(result.entries);
      setQuery("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (nextQuery: string) => {
    setQuery(nextQuery);
    setLoading(true);
    setError(null);
    try {
      const result = await Citations.search(nextQuery);
      setEntries(result.entries);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadInitial();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex flex-col w-80 min-w-[280px] max-w-[380px] border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-[#1e1e1e] text-sm">
      <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700 shrink-0">
        <div className="text-xs font-semibold text-gray-700 dark:text-gray-200">
          Citations
        </div>
      </div>

      <div className="p-3 flex flex-col gap-2 border-b border-gray-200 dark:border-gray-700 shrink-0">
        <label className="text-xs text-gray-500 dark:text-gray-400">
          BibTeX (.bib) file
        </label>
        <div className="flex gap-1">
          <input
            type="text"
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void handleLoadLibrary();
            }}
            placeholder="/path/to/library.bib"
            className="flex-1 text-xs p-1.5 border border-gray-200 dark:border-gray-600 rounded bg-gray-50 dark:bg-[#2d2d2d] text-gray-800 dark:text-gray-100"
          />
          <button
            onClick={() => { void handleLoadLibrary(); }}
            disabled={loading || !pathInput.trim()}
            className="px-2 text-xs bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-40"
          >
            Load
          </button>
        </div>
        {libraryPath && (
          <div className="text-[11px] text-gray-400 dark:text-gray-500 break-all">
            Active: {libraryPath}
          </div>
        )}
      </div>

      <div className="p-3 border-b border-gray-200 dark:border-gray-700 shrink-0">
        <input
          type="text"
          value={query}
          onChange={(e) => { void handleSearch(e.target.value); }}
          placeholder="Search by author, title, year, or key…"
          className="w-full text-xs p-1.5 border border-gray-200 dark:border-gray-600 rounded bg-gray-50 dark:bg-[#2d2d2d] text-gray-800 dark:text-gray-100"
        />
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {loading && (
          <div className="text-xs text-gray-400 dark:text-gray-500 p-2">Loading…</div>
        )}
        {error && (
          <div className="text-xs text-red-500 bg-red-50 dark:bg-red-900/20 px-2 py-1 rounded m-1">
            {error}
          </div>
        )}
        {!loading && !error && entries.length === 0 && (
          <div className="text-xs text-gray-400 dark:text-gray-500 p-2">
            {libraryPath
              ? "No matching citations."
              : "Load a .bib file to search your library."}
          </div>
        )}
        {entries.map((entry) => (
          <div
            key={entry.key}
            className="p-2 rounded border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-[#2d2d2d]"
          >
            <div className="text-xs font-medium text-gray-800 dark:text-gray-100">
              {entry.title || entry.key}
            </div>
            <div className="text-[11px] text-gray-500 dark:text-gray-400">
              {[entry.author, entry.year, entry.container].filter(Boolean).join(" · ")}
            </div>
            <div className="flex items-center justify-between mt-1">
              <code className="text-[11px] text-gray-400 dark:text-gray-500">
                [@{entry.key}]
              </code>
              <button
                onClick={() => onInsert(entry.key)}
                className="text-[11px] text-blue-600 dark:text-blue-400 hover:underline"
              >
                Insert
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
