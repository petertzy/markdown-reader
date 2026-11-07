"use client";

import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type MouseEvent as ReactMouseEvent } from "react";
import { Files, type FileEntry } from "@/lib/api";
import { isWithin, joinPath, relativePath, remapPath, renamedPath } from "@/lib/explorer-paths.mjs";
import { revealInFileManager } from "@/utils/revealInFileManager";

type Props = {
  root: string | null;
  onOpenFile: (path: string) => void;
  onOpenProject: () => void;
  onCloseProject: () => void;
  /** Called after an entry is renamed on disk, so open tabs can follow it. */
  onPathRenamed: (oldPath: string, newPath: string) => void;
  /** Called after an entry is moved to the trash, so its tabs can be closed. */
  onPathDeleted: (path: string) => void;
  /** Reveal in File Explorer / Finder needs the Tauri shell. */
  canReveal: boolean;
  refreshToken: number;
};

/** What was right-clicked: a file, a folder, or the empty area (project root). */
type MenuTarget = { path: string; name: string; isDir: boolean; isRoot: boolean; parent: string };
type MenuState = { target: MenuTarget; x: number; y: number };
type DialogState =
  | { kind: "create"; parent: string; isDir: boolean }
  | { kind: "rename"; target: MenuTarget }
  | { kind: "delete"; target: MenuTarget };
/** An entry waiting to be pasted. Cut moves it; Copy duplicates it. */
type ClipboardState = { mode: "cut" | "copy"; target: MenuTarget };

type ExplorerContextValue = {
  onOpenFile: (path: string) => void;
  openMenu: (event: ReactMouseEvent, target: MenuTarget) => void;
  /** Bumped per folder to make that folder list itself again. */
  versions: Record<string, number>;
  expanded: Set<string>;
  toggleExpanded: (path: string) => void;
  /** The entry that was cut, shown dimmed until it is pasted. */
  cutPath: string | null;
};

const ExplorerContext = createContext<ExplorerContextValue | null>(null);

function useExplorer() {
  const value = useContext(ExplorerContext);
  if (!value) throw new Error("ProjectExplorer context missing");
  return value;
}

function revealLabel() {
  const platform = typeof navigator === "undefined" ? "" : navigator.userAgent;
  if (/Mac/i.test(platform)) return "Reveal in Finder";
  if (/Win/i.test(platform)) return "Reveal in File Explorer";
  return "Open Containing Folder";
}

function errorMessage(reason: unknown) {
  const message = reason instanceof Error ? reason.message : String(reason);
  // `apiFetch` errors read `API /api/files/move → 409: {"detail":"Already exists: a.md"}`;
  // show only the backend's explanation.
  const body = /→ \d+: (.*)$/s.exec(message)?.[1];
  if (body) {
    try {
      const { detail } = JSON.parse(body) as { detail?: unknown };
      if (typeof detail === "string") return detail;
    } catch {
      // Not JSON; fall back to the full message.
    }
  }
  return message;
}

function Tree({ path, depth }: { path: string; depth: number }) {
  const { onOpenFile, openMenu, versions, cutPath } = useExplorer();
  const version = versions[path] ?? 0;
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Files.list(path)
      .then(({ entries: next }) => { if (active) { setEntries(next); setError(""); } })
      .catch((reason) => { if (active) setError(errorMessage(reason)); });
    return () => { active = false; };
  }, [path, version]);

  return <>
    {entries.map((entry) => entry.is_dir ? <DirectoryNode key={entry.path} entry={entry} depth={depth} parent={path} /> : (
      <button key={entry.path} className={`block w-full truncate px-2 py-1 text-left text-gray-800 hover:bg-blue-50 dark:text-gray-200 dark:hover:bg-[#333] ${entry.path === cutPath ? "opacity-50" : ""}`}
        style={{ paddingLeft: `${depth * 12 + 24}px` }} title={entry.path} onClick={() => onOpenFile(entry.path)}
        onContextMenu={(event) => openMenu(event, { path: entry.path, name: entry.name, isDir: false, isRoot: false, parent: path })}>
        {entry.name}
      </button>
    ))}
    {error && <p className="px-2 text-xs text-red-500">Unable to read folder.</p>}
  </>;
}

function DirectoryNode({ entry, depth, parent }: { entry: FileEntry; depth: number; parent: string }) {
  const { openMenu, expanded, toggleExpanded, cutPath } = useExplorer();
  const open = expanded.has(entry.path);
  return <div>
    <button className={`flex w-full items-center gap-1 truncate px-2 py-1 text-left text-gray-800 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-[#333] ${entry.path === cutPath ? "opacity-50" : ""}`}
      style={{ paddingLeft: `${depth * 12 + 8}px` }} onClick={() => toggleExpanded(entry.path)}
      onContextMenu={(event) => openMenu(event, { path: entry.path, name: entry.name, isDir: true, isRoot: false, parent })}>
      <span>{open ? "▾" : "▸"}</span><span className="truncate">{entry.name}</span>
    </button>
    {open && <Tree path={entry.path} depth={depth + 1} />}
  </div>;
}

type MenuItem = { label: string; onSelect: () => void; disabled?: boolean } | "separator";

const isSelectable = (item: MenuItem) => item !== "separator" && !item.disabled;

function ContextMenu({ x, y, items, onClose }: { x: number; y: number; items: MenuItem[]; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ left: x, top: y });
  // One highlight, driven by both the mouse and the arrow keys (like VS Code).
  // Nothing is highlighted until the user hovers or presses an arrow key.
  const [activeIndex, setActiveIndex] = useState(-1);

  // Keep the menu on screen when opened near the bottom or right edge.
  useLayoutEffect(() => {
    const menu = ref.current;
    if (!menu) return;
    const { width, height } = menu.getBoundingClientRect();
    setPosition({
      left: Math.max(4, Math.min(x, window.innerWidth - width - 4)),
      top: Math.max(4, Math.min(y, window.innerHeight - height - 4)),
    });
    // Focus the menu itself, not an item, so keys work without a highlight.
    menu.focus();
  }, [x, y]);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) onClose();
    };
    window.addEventListener("mousedown", onPointerDown);
    window.addEventListener("blur", onClose);
    window.addEventListener("resize", onClose);
    return () => {
      window.removeEventListener("mousedown", onPointerDown);
      window.removeEventListener("blur", onClose);
      window.removeEventListener("resize", onClose);
    };
  }, [onClose]);

  const select = (item: MenuItem) => {
    if (item === "separator" || !isSelectable(item)) return;
    onClose();
    item.onSelect();
  };

  // Step to the next selectable item in `direction`, skipping separators and
  // disabled items.
  const move = (direction: 1 | -1) => {
    // With nothing highlighted, Down starts at the first item and Up at the last.
    let index = activeIndex >= 0 ? activeIndex : direction === 1 ? -1 : items.length;
    for (let step = 0; step < items.length; step += 1) {
      index = (index + direction + items.length) % items.length;
      if (isSelectable(items[index])) { setActiveIndex(index); return; }
    }
  };

  const onKeyDown = (event: ReactKeyboardEvent) => {
    if (event.key === "Escape") onClose();
    else if (event.key === "ArrowDown") move(1);
    else if (event.key === "ArrowUp") move(-1);
    else if (event.key === "Enter" && activeIndex >= 0) select(items[activeIndex]);
    else return;
    event.preventDefault();
    event.stopPropagation();
  };

  return (
    <div ref={ref} role="menu" tabIndex={-1} onKeyDown={onKeyDown} onContextMenu={(event) => event.preventDefault()}
      onMouseLeave={() => setActiveIndex(-1)}
      aria-activedescendant={activeIndex >= 0 ? `explorer-menu-item-${activeIndex}` : undefined}
      className="fixed z-50 min-w-[200px] rounded-md border border-gray-200 bg-white py-1 text-sm text-gray-800 shadow-lg outline-none dark:border-gray-600 dark:bg-[#252526] dark:text-gray-200"
      style={position}>
      {items.map((item, index) => item === "separator" ? (
        <div key={`sep-${index}`} role="separator" className="my-1 border-t border-gray-200 dark:border-gray-600" />
      ) : (
        <button key={item.label} id={`explorer-menu-item-${index}`} role="menuitem" tabIndex={-1}
          aria-disabled={item.disabled || undefined}
          onMouseEnter={() => setActiveIndex(item.disabled ? -1 : index)} onClick={() => select(item)}
          className={`block w-full px-3 py-1 text-left outline-none ${item.disabled ? "cursor-default text-gray-400 dark:text-gray-500" : index === activeIndex ? "bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-200" : ""}`}>
          {item.label}
        </button>
      ))}
    </div>
  );
}

function ExplorerDialog({ dialog, onCancel, onSubmit }: {
  dialog: DialogState;
  onCancel: () => void;
  onSubmit: (value: string) => Promise<void>;
}) {
  const isDelete = dialog.kind === "delete";
  const initial = dialog.kind === "rename" ? dialog.target.name : "";
  const [value, setValue] = useState(initial);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (isDelete) { confirmRef.current?.focus(); return; }
    const input = inputRef.current;
    if (!input) return;

    input.focus();
    // Like VS Code, select the name without its extension when renaming a file.
    const dot = dialog.kind === "rename" && !dialog.target.isDir ? initial.lastIndexOf(".") : -1;
    input.setSelectionRange(0, dot > 0 ? dot : initial.length);
  }, [dialog, initial, isDelete]);

  const title = dialog.kind === "create" ? (dialog.isDir ? "New Folder" : "New File")
    : dialog.kind === "rename" ? "Rename" : "Delete";

  const submit = async () => {
    if (!isDelete && !value.trim()) { setError("Please enter a name."); return; }
    setBusy(true);
    setError("");
    try {
      await onSubmit(value.trim());
    } catch (reason) {
      setError(errorMessage(reason));
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/20 pt-24" onMouseDown={onCancel}>
      <form role="dialog" aria-label={title} onMouseDown={(event) => event.stopPropagation()}
        onSubmit={(event) => { event.preventDefault(); void submit(); }}
        onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); onCancel(); } }}
        className="w-80 rounded-md border border-gray-200 bg-white p-4 text-sm text-gray-800 shadow-xl dark:border-gray-600 dark:bg-[#252526] dark:text-gray-200">
        <h2 className="mb-2 font-semibold">{title}</h2>
        {isDelete ? (
          <p className="mb-3">
            Delete &lsquo;{dialog.target.name}&rsquo;{dialog.target.isDir ? " and its contents" : ""}?
            <span className="mt-1 block text-xs text-gray-500 dark:text-gray-400">You can restore it from the Recycle Bin / Trash.</span>
          </p>
        ) : (
          <input ref={inputRef} value={value} onChange={(event) => setValue(event.target.value)} disabled={busy}
            aria-label={title} spellCheck={false}
            className="mb-3 w-full rounded border border-gray-300 px-2 py-1 outline-none focus:border-blue-500 dark:border-gray-600 dark:bg-[#1e1e1e]" />
        )}
        {error && <p role="alert" className="mb-3 text-xs text-red-500">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onCancel} className="rounded px-3 py-1 hover:bg-gray-100 dark:hover:bg-[#3a3d41]">Cancel</button>
          <button ref={confirmRef} type="submit" disabled={busy}
            className={`rounded px-3 py-1 text-white disabled:opacity-60 ${isDelete ? "bg-red-600 hover:bg-red-700" : "bg-blue-600 hover:bg-blue-700"}`}>
            {isDelete ? "Delete" : dialog.kind === "rename" ? "Rename" : "Create"}
          </button>
        </div>
      </form>
    </div>
  );
}

function ExplorerIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5"><path d="M5 5.75A1.75 1.75 0 0 1 6.75 4h6.5L17 7.75v9.5A1.75 1.75 0 0 1 15.25 19H6.75A1.75 1.75 0 0 1 5 17.25Z" /><path d="M13 4v3.25H17" /><path d="M8 10h6M8 13h6" /></svg>;
}

export default function ProjectExplorer({ root, onOpenFile, onOpenProject, onCloseProject, onPathRenamed, onPathDeleted, canReveal, refreshToken }: Props) {
  const name = root?.split(/[\\/]/).filter(Boolean).pop() || "Project";
  const [collapsed, setCollapsed] = useState(false);
  const [menu, setMenu] = useState<MenuState | null>(null);
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [versions, setVersions] = useState<Record<string, number>>({});
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());
  const [clipboard, setClipboard] = useState<ClipboardState | null>(null);
  /** A failed paste has no dialog to show its error in, so it shows here. */
  const [notice, setNotice] = useState("");

  // A different project starts with every folder collapsed and nothing to paste.
  useEffect(() => {
    setExpanded(new Set()); setMenu(null); setDialog(null); setClipboard(null); setNotice("");
  }, [root]);

  const reload = useCallback((dir: string) => {
    setVersions((current) => ({ ...current, [dir]: (current[dir] ?? 0) + 1 }));
  }, []);
  const toggleExpanded = useCallback((path: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path); else next.add(path);
      return next;
    });
  }, []);
  const openMenu = useCallback((event: ReactMouseEvent, target: MenuTarget) => {
    event.preventDefault();
    event.stopPropagation();
    setNotice("");
    setMenu({ target, x: event.clientX, y: event.clientY });
  }, []);
  const closeMenu = useCallback(() => setMenu(null), []);

  /** Keep expanded folders open after the folder holding them is renamed or moved. */
  const remapExpanded = (oldPath: string, newPath: string) => {
    setExpanded((current) => new Set([...current].map((path) => remapPath(path, oldPath, newPath))));
  };
  /** Forget a cut or copied entry once it is renamed or deleted. */
  const dropClipboardWithin = (path: string) => {
    setClipboard((current) => (current && isWithin(current.target.path, path) ? null : current));
  };

  const paste = async (destParent: string) => {
    if (!root || !clipboard) return;
    const { mode, target } = clipboard;
    try {
      if (mode === "copy") {
        await Files.copy(root, target.path, destParent);
      } else {
        const { path } = await Files.move(root, target.path, destParent);
        // Use the folder's own path form, as for New File, so tabs match the tree.
        const newPath = joinPath(destParent, path.split(/[/\\]/).pop() ?? target.name);
        if (newPath !== target.path) {
          remapExpanded(target.path, newPath);
          onPathRenamed(target.path, newPath);
          reload(target.parent);
        }
        // A cut entry can only be pasted once; a copy can be pasted again.
        setClipboard(null);
      }
      setExpanded((current) => new Set(current).add(destParent));
      reload(destParent);
    } catch (reason) {
      setNotice(errorMessage(reason));
    }
  };

  const menuItems = (target: MenuTarget): MenuItem[] => {
    if (!root) return [];
    const copy = (text: string) => { void navigator.clipboard?.writeText(text).catch(console.error); };
    const items: MenuItem[] = [];
    if (target.isDir) {
      items.push(
        { label: "New File…", onSelect: () => setDialog({ kind: "create", parent: target.path, isDir: false }) },
        { label: "New Folder…", onSelect: () => setDialog({ kind: "create", parent: target.path, isDir: true }) },
        "separator",
      );
    } else {
      items.push({ label: "Open", onSelect: () => onOpenFile(target.path) }, "separator");
    }
    if (canReveal) {
      items.push({ label: revealLabel(), onSelect: () => { void revealInFileManager(target.path).catch(console.error); } }, "separator");
    }
    if (!target.isRoot) {
      items.push(
        { label: "Cut", onSelect: () => setClipboard({ mode: "cut", target }) },
        { label: "Copy", onSelect: () => setClipboard({ mode: "copy", target }) },
      );
    }
    // Pasting on a file pastes next to it, as in VS Code.
    const destParent = target.isDir ? target.path : target.parent;
    items.push(
      { label: "Paste", disabled: !clipboard, onSelect: () => { void paste(destParent); } },
      "separator",
      { label: "Copy Path", onSelect: () => copy(target.path) },
      { label: "Copy Relative Path", onSelect: () => copy(relativePath(root, target.path)) },
    );
    if (!target.isRoot) {
      items.push(
        "separator",
        { label: "Rename…", onSelect: () => setDialog({ kind: "rename", target }) },
        { label: "Delete", onSelect: () => setDialog({ kind: "delete", target }) },
      );
    }
    return items;
  };

  const submitDialog = async (value: string) => {
    if (!root || !dialog) return;
    if (dialog.kind === "create") {
      const { path } = await Files.create(root, dialog.parent, value, dialog.isDir);
      setExpanded((current) => new Set(current).add(dialog.parent));
      reload(dialog.parent);
      // Open the new file straight away, as VS Code does. Use the folder's own
      // path form rather than the backend's resolved one so tabs match the tree.
      if (!dialog.isDir) onOpenFile(joinPath(dialog.parent, path.split(/[/\\]/).pop() ?? value));
    } else if (dialog.kind === "rename") {
      await Files.rename(root, dialog.target.path, value);
      const newPath = renamedPath(dialog.target.path, value);
      remapExpanded(dialog.target.path, newPath);
      dropClipboardWithin(dialog.target.path);
      onPathRenamed(dialog.target.path, newPath);
      reload(dialog.target.parent);
    } else {
      await Files.delete(root, dialog.target.path);
      dropClipboardWithin(dialog.target.path);
      onPathDeleted(dialog.target.path);
      reload(dialog.target.parent);
    }
    setDialog(null);
  };

    if (collapsed) {
      return (
        <aside className="flex h-full w-10 shrink-0 flex-col items-center border-r border-gray-200 bg-gray-50 py-1 dark:border-gray-700 dark:bg-[#252526]">
          <button
            onClick={() => setCollapsed(false)}
            title="Show Explorer"
            aria-label="Show Explorer"
            aria-expanded="false"
            className="flex h-8 w-8 items-center justify-center rounded text-gray-500 transition-colors duration-150 hover:bg-gray-200 hover:text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 dark:text-gray-400 dark:hover:bg-[#3a3d41] dark:hover:text-white dark:focus-visible:ring-offset-[#252526]"
          >
            <ExplorerIcon />
          </button>
        </aside>
      );
    }

    return (
      <div className="flex h-full shrink-0">
        <div className="flex w-10 shrink-0 flex-col items-center border-r border-gray-200 bg-gray-50 py-1 dark:border-gray-700 dark:bg-[#252526]">
          <button
            onClick={() => setCollapsed(true)}
            title="Hide Explorer"
            aria-label="Hide Explorer"
            aria-expanded="true"
            className="flex h-8 w-8 items-center justify-center rounded text-gray-900 transition-colors duration-150 hover:bg-gray-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 dark:text-white dark:hover:bg-[#3a3d41] dark:focus-visible:ring-offset-[#252526]"
          >
            <ExplorerIcon />
          </button>
        </div>

        {!collapsed && (
          <aside className="flex h-full w-56 shrink-0 flex-col border-r border-gray-200 bg-gray-50 text-sm text-gray-800 dark:border-gray-700 dark:bg-[#252526] dark:text-gray-200">
            <div className="flex items-center justify-between border-b border-gray-200 px-3 py-2 dark:border-gray-700">
              <span className="truncate text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-400">
                Explorer
              </span>
              <div className="flex items-center gap-1">
                <button onClick={onOpenProject} title="Open project" aria-label="Open project" className="rounded p-1 text-gray-500 transition-colors hover:bg-gray-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:text-gray-400 dark:hover:bg-[#3a3d41]">
                  +
                </button>
              </div>
            </div>

            {!root ? (
              <div className="p-3 text-xs text-gray-500 dark:text-gray-400">
                <p>No project folder is open.</p>
                <button onClick={onOpenProject} className="mt-2 text-blue-600 hover:underline dark:text-blue-400">
                  Open Project Folder
                </button>
              </div>
            ) : (
              <ExplorerContext.Provider value={{ onOpenFile, openMenu, versions, expanded, toggleExpanded, cutPath: clipboard?.mode === "cut" ? clipboard.target.path : null }}>
                <div className="flex items-center justify-between border-b border-gray-200 px-2 py-2 text-xs font-medium dark:border-gray-700">
                  <span className="truncate" title={root}>{name}</span>
                  <button onClick={onCloseProject} title="Close project" className="text-gray-500 hover:text-red-500 dark:text-gray-400">
                    ×
                  </button>
                </div>
                {notice && (
                  <div role="alert" className="flex items-start gap-2 border-b border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700 dark:border-red-900 dark:bg-[#3a1d1d] dark:text-red-300">
                    <span className="flex-1">{notice}</span>
                    <button onClick={() => setNotice("")} aria-label="Dismiss" className="hover:text-red-900 dark:hover:text-white">×</button>
                  </div>
                )}
                {/* Right-clicking empty space below the tree acts on the project folder. */}
                <div className="min-h-0 flex-1 overflow-auto"
                  onContextMenu={(event) => openMenu(event, { path: root, name, isDir: true, isRoot: true, parent: root })}>
                  <Tree key={`${root}-${refreshToken}`} path={root} depth={0} />
                </div>
              </ExplorerContext.Provider>
            )}
          </aside>
        )}

        {menu && <ContextMenu x={menu.x} y={menu.y} items={menuItems(menu.target)} onClose={closeMenu} />}
        {dialog && <ExplorerDialog key={dialog.kind} dialog={dialog} onCancel={() => setDialog(null)} onSubmit={submitDialog} />}
      </div>
    );
}
