"use client";

import { useState } from "react";
import { useProjectTranslation } from "@/hooks/useProjectTranslation";

export default function ProjectTranslationReview({ projectRoot }: { projectRoot: string | null }) {
  const [sourceLanguage, setSourceLanguage] = useState("auto");
  const [targetLanguage, setTargetLanguage] = useState("German");
  const translation = useProjectTranslation(projectRoot);
  const task = translation.task;

  if (!projectRoot) return null;

  return <section className="space-y-2 border-t pt-2 dark:border-gray-700">
    <p className="font-medium">Translate project</p>
    <p className="text-gray-500 dark:text-gray-400">Translations preserve source files and are written to a separate output tree.</p>
    <div className="flex gap-2">
      <input aria-label="Source language" value={sourceLanguage} onChange={(event) => setSourceLanguage(event.target.value)}
        className="min-w-0 flex-1 rounded border px-2 py-1 dark:border-gray-600 dark:bg-[#242424]" />
      <input aria-label="Target language" value={targetLanguage} onChange={(event) => setTargetLanguage(event.target.value)}
        className="min-w-0 flex-1 rounded border px-2 py-1 dark:border-gray-600 dark:bg-[#242424]" />
    </div>
    <div className="flex gap-2">
      <button onClick={() => void translation.start(sourceLanguage, targetLanguage)}
        disabled={task?.status === "running" || !targetLanguage.trim()}
        className="rounded bg-blue-600 px-2 py-1 text-white disabled:opacity-50">
        {task?.status === "running" ? "Translating..." : "Translate project"}
      </button>
      {task?.status === "running" && <button onClick={() => void translation.cancel()} className="rounded border px-2 py-1 dark:border-gray-600">Cancel</button>}
      {task && task.status !== "running" && task.failed > 0 && <button onClick={() => void translation.retryFailed()} className="rounded border px-2 py-1 dark:border-gray-600">Retry failed files</button>}
    </div>
    {translation.error && <p role="alert" className="text-red-600 dark:text-red-400">{translation.error}</p>}
    {task && <div className="space-y-1">
      <p role="status">{task.completed}/{task.total} files · {task.status}{task.failed ? ` · ${task.failed} failed` : ""}</p>
      <div className="h-1.5 overflow-hidden rounded bg-gray-200 dark:bg-gray-700"><div className="h-full bg-blue-600" style={{ width: `${task.total ? Math.round((task.completed / task.total) * 100) : 0}%` }} /></div>
      <details><summary className="cursor-pointer">File results</summary><ul className="mt-1 max-h-32 overflow-auto font-mono text-[10px]">{task.files.map((file) => <li key={file.rel_path} title={file.error ?? undefined}>{file.status}: {file.rel_path}{file.error ? ` — ${file.error}` : ""}</li>)}</ul></details>
      {task.status !== "running" && <p className="break-all text-gray-500 dark:text-gray-400">Output: {task.output_dir}</p>}
    </div>}
  </section>;
}
