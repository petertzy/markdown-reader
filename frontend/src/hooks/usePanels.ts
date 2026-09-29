"use client";

/**
 * usePanels.ts
 * ============
 * Owns which side panel is currently open (AI / Citation / none).
 *
 * The homepage used to hold this state plus a boolean adapter that translated
 * the legacy `setShowAIPanel` calls (from the action/shortcut and slash-command
 * hooks) into the unified `activePanel` value. Extracting it here keeps that
 * translation — and the open/closed bookkeeping — in one place so the homepage
 * only orchestrates.
 */

import { useCallback, useState, type SetStateAction } from "react";
import { PANELS, type PanelId } from "@/types/panels";

export function usePanels() {
  const [activePanel, setActivePanel] = useState<PanelId>(null);

  /** Toggle a panel open/closed (used by the toolbar buttons). */
  const togglePanel = useCallback((panelId: PanelId) => {
    setActivePanel((prev) => (prev === panelId ? null : panelId));
  }, []);

  /**
   * Adapter to keep compatibility with `useActions` and `useSlashCommandWiring`.
   * Those hooks still expect a standard boolean state setter (`setShowAIPanel`),
   * so this wrapper intercepts those boolean calls and translates them into the
   * unified `activePanel` string state (leaving an open non-AI panel untouched
   * when the AI panel is hidden).
   */
  const setShowAIPanel = useCallback((action: SetStateAction<boolean>) => {
    setActivePanel((prevPanel) => {
      const isCurrentlyAI = prevPanel === PANELS.AI;
      const shouldShowAI = typeof action === "function" ? action(isCurrentlyAI) : action;

      if (shouldShowAI) return PANELS.AI;
      if (!shouldShowAI && isCurrentlyAI) return null;
      return prevPanel;
    });
  }, []);

  return { activePanel, togglePanel, setShowAIPanel };
}

export type PanelsController = ReturnType<typeof usePanels>;