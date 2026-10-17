"use client";

import React, { useState, useCallback, useRef, useEffect } from "react";

/**
 * SplitPane.tsx
 * =============
 * A resizable split-pane container.
 */

interface SplitPaneProps {
  left: React.ReactNode;
  right: React.ReactNode;
  split?: number;
  onSplitChange?: (split: number) => void;
  initialSplit?: number; // 0 to 100
  minSize?: number; // percentage
}

export default function SplitPane({
  left,
  right,
  split: controlledSplit,
  onSplitChange,
  initialSplit = 50,
  minSize = 0,
}: SplitPaneProps) {
  const [internalSplit, setInternalSplit] = useState(initialSplit);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const split = controlledSplit ?? internalSplit;

  const setSplitValue = useCallback(
    (nextSplit: number) => {
      if (controlledSplit === undefined) {
        setInternalSplit(nextSplit);
      }
      onSplitChange?.(nextSplit);
    },
    [controlledSplit, onSplitChange]
  );

  const startDragging = useCallback(() => {
    setIsDragging(true);
  }, []);

  const stopDragging = useCallback(() => {
    setIsDragging(false);
  }, []);

  const onDrag = useCallback(
    (e: MouseEvent | TouchEvent) => {
      if (!isDragging || !containerRef.current) return;

      const containerRect = containerRef.current.getBoundingClientRect();
      const clientX = "touches" in e ? (e as TouchEvent).touches[0].clientX : (e as MouseEvent).clientX;

      let newSplit = ((clientX - containerRect.left) / containerRect.width) * 100;
      newSplit = Math.max(minSize, Math.min(100 - minSize, newSplit));

      setSplitValue(newSplit);
    },
    [isDragging, minSize, setSplitValue]
  );

  useEffect(() => {
    if (isDragging) {
      window.addEventListener("mousemove", onDrag);
      window.addEventListener("mouseup", stopDragging);
      window.addEventListener("touchmove", onDrag, { passive: false });
      window.addEventListener("touchend", stopDragging);
      document.body.style.cursor = "col-resize";
    } else {
      window.removeEventListener("mousemove", onDrag);
      window.removeEventListener("mouseup", stopDragging);
      window.removeEventListener("touchmove", onDrag);
      window.removeEventListener("touchend", stopDragging);
      document.body.style.cursor = "";
    }

    return () => {
      window.removeEventListener("mousemove", onDrag);
      window.removeEventListener("mouseup", stopDragging);
      window.removeEventListener("touchmove", onDrag);
      window.removeEventListener("touchend", stopDragging);
      document.body.style.cursor = "";
    };
  }, [isDragging, onDrag, stopDragging]);

  return (
    <div ref={containerRef} className="flex flex-1 relative overflow-hidden h-full">
      {/* Left Pane (Editor) */}
      <div
        style={{ width: `${split}%` }}
        className={`h-full overflow-hidden ${
          !isDragging ? "transition-[width] duration-300 ease-in-out" : ""
        } ${split <= 0.5 ? "w-0 invisible" : "visible"}`}
      >
        {left}
      </div>

      {/* Resizable Divider */}
      <div
        className={`w-2 relative z-20 flex items-center justify-center cursor-col-resize group select-none ${
          split > 99.5 ? "-translate-x-full" : split < 0.5 ? "translate-x-full" : ""
        }`}
        onMouseDown={startDragging}
        onTouchStart={startDragging}
      >
        {/* Visual Line */}
        <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-px bg-gray-200 dark:bg-gray-700 group-hover:bg-blue-500/50 transition-colors" />
        
        {/* Grabber Handle */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-6 rounded-full bg-gray-300 dark:bg-gray-600 group-hover:bg-blue-400 dark:group-hover:bg-blue-600 transition-colors" />
      </div>

      {/* Right Pane (Preview) */}
      <div
        style={{ width: `${100 - split}%` }}
        className={`h-full overflow-hidden ${
          !isDragging ? "transition-[width] duration-300 ease-in-out" : ""
        } ${split >= 99.5 ? "w-0 invisible" : "visible"}`}
      >
        {right}
      </div>
    </div>
  );
}
