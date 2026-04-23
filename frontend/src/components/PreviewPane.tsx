"use client";

/**
 * PreviewPane.tsx
 * ===============
 * Rendered Markdown HTML preview in an isolated iframe.
 */

type Props = {
  html: string;
};

export default function PreviewPane({ html }: Props) {
  return (
    <div className="flex-1 overflow-hidden h-full bg-white dark:bg-[#1e1e1e] border-l border-gray-200 dark:border-gray-700">
      <iframe
        title="Markdown Preview"
        srcDoc={html || "<p style='color:#999;padding:24px;font-family:sans-serif'>Preview will appear here…</p>"}
        className="w-full h-full border-none"
        sandbox="allow-scripts"
      />
    </div>
  );
}
