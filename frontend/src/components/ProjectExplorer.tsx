"use client";

import { useEffect, useState } from "react";
import { Files, type FileEntry } from "@/lib/api";

type Props = {
  root: string | null;
  onOpenFile: (path: string) => void;
  onOpenProject: () => void;
  onCloseProject: () => void;
};

function Tree({ path, depth, onOpenFile }: { path: string; depth: number; onOpenFile: (path: string) => void }) {
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (loaded) return;
    let active = true;
    Files.list(path)
      .then(({ entries: next }) => { if (active) { setEntries(next); setLoaded(true); } })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : String(reason)); });
    return () => { active = false; };
  }, [loaded, path]);

  return <>
    {entries.map((entry) => entry.is_dir ? <DirectoryNode key={entry.path} entry={entry} depth={depth} onOpenFile={onOpenFile} /> : (
      <button key={entry.path} className="block w-full truncate px-2 py-1 text-left hover:bg-blue-50 dark:hover:bg-[#333]"
        style={{ paddingLeft: `${depth * 12 + 24}px` }} title={entry.path} onClick={() => onOpenFile(entry.path)}>
        {entry.name}
      </button>
    ))}
    {error && <p className="px-2 text-xs text-red-500">Unable to read folder.</p>}
  </>;
}

function DirectoryNode({ entry, depth, onOpenFile }: { entry: FileEntry; depth: number; onOpenFile: (path: string) => void }) {
  const [open, setOpen] = useState(false);
  return <div>
    <button className="flex w-full items-center gap-1 truncate px-2 py-1 text-left hover:bg-gray-100 dark:hover:bg-[#333]"
      style={{ paddingLeft: `${depth * 12 + 8}px` }} onClick={() => setOpen((value) => !value)}>
      <span>{open ? "▾" : "▸"}</span><span className="truncate">{entry.name}</span>
    </button>
    {open && <Tree path={entry.path} depth={depth + 1} onOpenFile={onOpenFile} />}
  </div>;
}

export default function ProjectExplorer({ root, onOpenFile, onOpenProject, onCloseProject }: Props) {
  const name = root?.split(/[\\/]/).filter(Boolean).pop() || "Project";
  return <aside className="flex h-full w-56 shrink-0 flex-col border-r border-gray-200 bg-gray-50 text-sm dark:border-gray-700 dark:bg-[#252526]">
    <div className="flex items-center justify-between border-b border-gray-200 px-2 py-2 dark:border-gray-700">
      <span className="truncate text-xs font-semibold uppercase tracking-wide">Explorer</span>
      <button onClick={onOpenProject} title="Open project" className="px-1 hover:text-blue-500">+</button>
    </div>
    {!root ? <div className="p-3 text-xs text-gray-500"><p>No project folder is open.</p><button onClick={onOpenProject} className="mt-2 text-blue-600 hover:underline">Open Project Folder</button></div> : <>
      <div className="flex items-center justify-between border-b border-gray-200 px-2 py-2 text-xs font-medium dark:border-gray-700"><span className="truncate" title={root}>{name}</span><button onClick={onCloseProject} title="Close project" className="text-gray-500 hover:text-red-500">×</button></div>
      <div className="min-h-0 flex-1 overflow-auto"><Tree key={root} path={root} depth={0} onOpenFile={onOpenFile} /></div>
    </>}
  </aside>;
}
