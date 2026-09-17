"use client";

import { useEffect } from "react";
import {
  shortcutMatchesEvent,
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
      // Never intercept keys while an IME composition is in progress.
      if (event.isComposing) return;
      const editableTarget = isEditableTarget(event.target);
      const isMonacoTarget =
        event.target instanceof HTMLElement && Boolean(event.target.closest(".monaco-editor"));

      for (const shortcut of shortcuts) {
        const matches = shortcut.bindings.some((binding) => shortcutMatchesEvent(binding, event));
        if (!matches) continue;
        if (shortcut.scope === "editor" && editableTarget && !isMonacoTarget) return;

        event.preventDefault();
        actions[shortcut.id]?.();
        return;
      }
    };

    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [actions, shortcuts]);
}
