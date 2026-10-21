"use client";

import { useEffect, useState } from "react";
import { Files, type FileEntry } from "@/lib/api";

type Props = {
  root: string | null;
  onOpenFile: (path: string) => void;
  onOpenProject: () => void;
  onCloseProject: () => void;
  refreshToken: number;
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
      <button key={entry.path} className="block w-full truncate px-2 py-1 text-left text-gray-800 hover:bg-blue-50 dark:text-gray-200 dark:hover:bg-[#333]"
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
    <button className="flex w-full items-center gap-1 truncate px-2 py-1 text-left text-gray-800 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-[#333]"
      style={{ paddingLeft: `${depth * 12 + 8}px` }} onClick={() => setOpen((value) => !value)}>
      <span>{open ? "▾" : "▸"}</span><span className="truncate">{entry.name}</span>
    </button>
    {open && <Tree path={entry.path} depth={depth + 1} onOpenFile={onOpenFile} />}
  </div>;
}

export default function ProjectExplorer({ root, onOpenFile, onOpenProject, onCloseProject, refreshToken }: Props) {
  const name = root?.split(/[\\/]/).filter(Boolean).pop() || "Project";
  const [collapsed, setCollapsed] = useState(false);

    if (collapsed) {
      return (
        <aside className="flex h-full w-12 shrink-0 flex-col items-center border-r border-gray-200 bg-gray-50 py-2 dark:border-[#333] dark:bg-[#333333]">
          <button
            onClick={() => setCollapsed(false)}
            title="Explorer"
            aria-label="Explorer"
            className="flex h-12 w-12 items-center justify-center text-gray-500 hover:text-black dark:text-gray-400 dark:hover:text-white"
          >
            <svg fill="none" xmlns="http://www.w3.org/2000/svg" width="auto" height="auto" viewBox="0 0 16 16"><path d="M5 1C3.89543 1 3 1.89543 3 3V13C3 14.1046 3.89543 15 5 15H11C12.1046 15 13 14.1046 13 13V5.41421C13 5.01639 12.842 4.63486 12.5607 4.35355L9.64645 1.43934C9.36514 1.15804 8.98361 1 8.58579 1H5ZM4 3C4 2.44772 4.44772 2 5 2H8V4.5C8 5.32843 8.67157 6 9.5 6H12V13C12 13.5523 11.5523 14 11 14H5C4.44772 14 4 13.5523 4 13V3ZM11.7929 5H9.5C9.22386 5 9 4.77614 9 4.5V2.20711L11.7929 5Z" fill="currentColor"/></svg>
          </button>
        </aside>
      );
    }

    return (
      <div className="flex h-full shrink-0">
        {/* BARRA IZQUIERDA: Siempre visible */}
        <div className="flex w-12 shrink-0 flex-col items-center border-r border-gray-200 bg-gray-50 py-2 dark:border-[#333] dark:bg-[#333333]">
          <button
            onClick={() => setCollapsed(!collapsed)}
            title="Explorer"
            aria-label="Explorer"
            className={`flex h-12 w-12 items-center justify-center border-l-2 transition-colors ${
              !collapsed
                ? "border-blue-500 text-black dark:text-white" // Activo (como VS Code)
                : "border-transparent text-gray-500 hover:text-black dark:text-gray-400 dark:hover:text-white" // Inactivo
            }`}
          >
            {/* SVG EXACTO: Documento doble con esquina doblada */}
            <svg fill="none" xmlns="http://www.w3.org/2000/svg" width="auto" height="auto" viewBox="0 0 16 16"><path d="M5 1C3.89543 1 3 1.89543 3 3V13C3 14.1046 3.89543 15 5 15H11C12.1046 15 13 14.1046 13 13V5.41421C13 5.01639 12.842 4.63486 12.5607 4.35355L9.64645 1.43934C9.36514 1.15804 8.98361 1 8.58579 1H5ZM4 3C4 2.44772 4.44772 2 5 2H8V4.5C8 5.32843 8.67157 6 9.5 6H12V13C12 13.5523 11.5523 14 11 14H5C4.44772 14 4 13.5523 4 13V3ZM11.7929 5H9.5C9.22386 5 9 4.77614 9 4.5V2.20711L11.7929 5Z" fill="currentColor"/></svg>
          </button>
        </div>

        {/* PANEL DERECHO: Solo se muestra si NO está colapsado */}
        {!collapsed && (
          <aside className="flex h-full w-56 shrink-0 flex-col border-r border-gray-200 bg-gray-50 text-sm text-gray-800 dark:border-gray-700 dark:bg-[#252526] dark:text-gray-200">
            
            {/* Cabecera: EXPLORER y botones de acción */}
            <div className="flex items-center justify-between border-b border-gray-200 px-3 py-2 dark:border-gray-700">
              <span className="truncate text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-400">
                Explorer
              </span>
              <div className="flex items-center gap-1">
                <button onClick={onOpenProject} title="Open project" className="rounded p-1 text-gray-500 hover:bg-gray-200 dark:text-gray-400 dark:hover:bg-[#3a3d41]">
                  +
                </button>
              </div>
            </div>

            {/* Contenido: Árbol de archivos o mensaje vacío */}
            {!root ? (
              <div className="p-3 text-xs text-gray-500 dark:text-gray-400">
                <p>No project folder is open.</p>
                <button onClick={onOpenProject} className="mt-2 text-blue-600 hover:underline dark:text-blue-400">
                  Open Project Folder
                </button>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between border-b border-gray-200 px-2 py-2 text-xs font-medium dark:border-gray-700">
                  <span className="truncate" title={root}>{name}</span>
                  <button onClick={onCloseProject} title="Close project" className="text-gray-500 hover:text-red-500 dark:text-gray-400">
                    ×
                  </button>
                </div>
                <div className="min-h-0 flex-1 overflow-auto">
                  <Tree key={`${root}-${refreshToken}`} path={root} depth={0} onOpenFile={onOpenFile} />
                </div>
              </>
            )}
          </aside>
        )}
      </div>
    );
}
