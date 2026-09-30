"use client";

import { useEffect } from "react";
import {
  shortcutMatchesEvent,
  isCompositionBlocked,
  isEditableTarget,
  type ActionId,
  type ShortcutDefinition,
} from "@/lib/keyboardShortcuts";

export function useKeyboardShortcuts(
  shortcuts: ShortcutDefinition[],
  actions: Record<ActionId, () => void>
): void {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      // Tauri's packaged WebView and Monaco can handle bubbling key events
      // before they reach this listener. Capture the event so app shortcuts
      // remain available regardless of which editor element has focus.
      const editableTarget = isEditableTarget(event.target);
      const isMonacoTarget =
        event.target instanceof HTMLElement && Boolean(event.target.closest(".monaco-editor"));

      for (const shortcut of shortcuts) {
        // Genuine IME composition never triggers shortcuts; Alt-involving
        // bindings (Ctrl+Alt+…, AltGr) are blocked during composition, while
        // plain Ctrl/Meta chords still work around Tauri/WebKit's spurious
        // `isComposing` flag. See isCompositionBlocked.
        const matches = shortcut.bindings.some(
          (binding) => !isCompositionBlocked(binding, event) && shortcutMatchesEvent(binding, event)
        );
        if (!matches) continue;
        if (shortcut.scope === "editor" && editableTarget && !isMonacoTarget) return;

        event.preventDefault();
        event.stopPropagation();
        actions[shortcut.id]?.();
        return;
      }
    };

    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [actions, shortcuts]);
}
