"use client";

/**
 * usePreviewSnapSetting.ts
 * ========================
 * Whether clicking in the editor glides the preview to the clicked spot.
 * On by default; the choice is remembered in localStorage.
 */

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "markdown-reader.snapPreviewOnClick";

export function usePreviewSnapSetting() {
  const [snapOnClick, setSnapOnClick] = useState(true);

  useEffect(() => {
    try {
      if (localStorage.getItem(STORAGE_KEY) === "false") setSnapOnClick(false);
    } catch {
      // Storage unavailable: keep the default.
    }
  }, []);

  const toggleSnapOnClick = useCallback(() => {
    setSnapOnClick((on) => {
      const next = !on;
      try {
        localStorage.setItem(STORAGE_KEY, String(next));
      } catch {
        // Storage unavailable: the setting just won't persist.
      }
      return next;
    });
  }, []);

  return { snapOnClick, toggleSnapOnClick };
}
