"use client";

import React, { useState, useCallback, useRef, useEffect } from "react";

/**
 * SplitPane.tsx
 * =============
 * A resizable split-pane container with toggle buttons to expand
 * either side to full width.
 */

interface SplitPaneProps {
  left: React.ReactNode;
  right: React.ReactNode;
  initialSplit?: number; // 0 to 100
  minSize?: number; // percentage
}

export default function SplitPane({
  left,
  right,
  initialSplit = 50,
  minSize = 0,
}: SplitPaneProps) {
  const [split, setSplit] = useState(initialSplit);
  const [lastSplit, setLastSplit] = useState(initialSplit);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

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

      setSplit(newSplit);
    },
    [isDragging, minSize]
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

  const toggleFullLeft = useCallback(() => {
    if (split > 98) {
      // Restore previous split if it was reasonably balanced, else 50
      setSplit(lastSplit < 95 && lastSplit > 5 ? lastSplit : 50);
    } else {
      setLastSplit(split);
      setSplit(100);
    }
  }, [split, lastSplit]);

  const toggleFullRight = useCallback(() => {
    if (split < 2) {
      setSplit(lastSplit < 95 && lastSplit > 5 ? lastSplit : 50);
    } else {
      setLastSplit(split);
      setSplit(0);
    }
  }, [split, lastSplit]);

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

        {/* Action Buttons */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col gap-2.5 z-40 opacity-0 group-hover:opacity-100 transition-all duration-200">
          {/* Full Editor Button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              setSplit(100);
            }}
            onMouseDown={(e) => e.stopPropagation()}
            className={`w-8 h-8 flex items-center justify-center rounded-full bg-white dark:bg-[#333] border shadow-lg hover:scale-110 active:scale-95 transition-all pointer-events-auto ${
              split > 99 
                ? "border-blue-500 text-blue-500 cursor-default" 
                : "border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-blue-50 dark:hover:bg-blue-900/40"
            }`}
            title="Full width editor"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <line x1="9" y1="3" x2="9" y2="21"></line>
            </svg>
          </button>

          {/* Middle / Split Button */}
          {(split < 48 || split > 52) && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setSplit(50);
              }}
              onMouseDown={(e) => e.stopPropagation()}
              className="w-8 h-8 flex items-center justify-center rounded-full bg-white dark:bg-[#333] border border-gray-300 dark:border-gray-600 shadow-lg hover:bg-blue-50 dark:hover:bg-blue-900/40 hover:scale-110 active:scale-95 transition-all text-gray-600 dark:text-gray-300 pointer-events-auto"
              title="Balanced split view"
            >
              <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="12" y1="3" x2="12" y2="21"></line>
              </svg>
            </button>
          )}

          {/* Full Preview Button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              setSplit(0);
            }}
            onMouseDown={(e) => e.stopPropagation()}
            className={`w-8 h-8 flex items-center justify-center rounded-full bg-white dark:bg-[#333] border shadow-lg hover:scale-110 active:scale-95 transition-all pointer-events-auto ${
              split < 1 
                ? "border-blue-500 text-blue-500 cursor-default" 
                : "border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-blue-50 dark:hover:bg-blue-900/40"
            }`}
            title="Full width preview"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <line x1="15" y1="3" x2="15" y2="21"></line>
            </svg>
          </button>
        </div>
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
