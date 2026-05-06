"use client";

/**
 * PreviewPane.tsx
 * ===============
 * Rendered Markdown HTML preview in an isolated iframe.
 */

type Props = {
  html: string;
  loading?: boolean;
  error?: string | null;
};

export default function PreviewPane({ html, loading = false, error = null }: Props) {
  const placeholder = error
    ? `<p style='color:#b91c1c;padding:24px;font-family:sans-serif'>Local engine unavailable.</p>`
    : loading
      ? "<p style='color:#999;padding:24px;font-family:sans-serif'>Starting local engine...</p>"
      : "<p style='color:#999;padding:24px;font-family:sans-serif'>Preview will appear here…</p>";

  return (
    <div className="flex-1 overflow-hidden h-full bg-white dark:bg-[#1e1e1e] border-l border-gray-200 dark:border-gray-700">
      <iframe
        title="Markdown Preview"
        srcDoc={html || placeholder}
        className="w-full h-full border-none"
        sandbox="allow-scripts"
      />
    </div>
  );
}
