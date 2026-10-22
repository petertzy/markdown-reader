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
            <svg 
              fill="#000000" 
              viewBox="-3 0 30 30" 
              xmlns="http://www.w3.org/2000/svg">
                <path d="M21,8.94a1.31,1.31,0,0,0-.06-.27l0-.09a1.07,1.07,0,0,0-.19-.28h0l-6-6h0a1.07,1.07,0,0,0-.28-.19.32.32,0,0,0-.09,0A.88.88,0,0,0,14.05,2H10A3,3,0,0,0,7,5V6H6A3,3,0,0,0,3,9V19a3,3,0,0,0,3,3h8a3,3,0,0,0,3-3V18h1a3,3,0,0,0,3-3V9S21,9,21,8.94ZM15,5.41,17.59,8H16a1,1,0,0,1-1-1ZM15,19a1,1,0,0,1-1,1H6a1,1,0,0,1-1-1V9A1,1,0,0,1,6,8H7v7a3,3,0,0,0,3,3h5Zm4-4a1,1,0,0,1-1,1H10a1,1,0,0,1-1-1V5a1,1,0,0,1,1-1h3V7a3,3,0,0,0,3,3h3Z"/>
            </svg>
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
            <svg 
              fill="#000000" 
              viewBox="-3 0 30 30" 
              xmlns="http://www.w3.org/2000/svg">
                <path d="M21,8.94a1.31,1.31,0,0,0-.06-.27l0-.09a1.07,1.07,0,0,0-.19-.28h0l-6-6h0a1.07,1.07,0,0,0-.28-.19.32.32,0,0,0-.09,0A.88.88,0,0,0,14.05,2H10A3,3,0,0,0,7,5V6H6A3,3,0,0,0,3,9V19a3,3,0,0,0,3,3h8a3,3,0,0,0,3-3V18h1a3,3,0,0,0,3-3V9S21,9,21,8.94ZM15,5.41,17.59,8H16a1,1,0,0,1-1-1ZM15,19a1,1,0,0,1-1,1H6a1,1,0,0,1-1-1V9A1,1,0,0,1,6,8H7v7a3,3,0,0,0,3,3h5Zm4-4a1,1,0,0,1-1,1H10a1,1,0,0,1-1-1V5a1,1,0,0,1,1-1h3V7a3,3,0,0,0,3,3h3Z"/>
            </svg>
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
