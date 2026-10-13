"use client";

import type { useProjectWork } from "@/hooks/useProjectWork";

type Props = { projectRoot: string | null; work: ReturnType<typeof useProjectWork> };

export default function ProjectWorkReview({ projectRoot, work }: Props) {
  if (!projectRoot) return <p className="text-xs text-amber-700 dark:text-amber-300">Open a project folder in Explorer before running Project Work.</p>;
  return <div className="space-y-2 text-xs">
    <p className="truncate text-gray-500" title={projectRoot}>Project: {projectRoot}</p>
    <p className="text-gray-500">The AI discovers paths first and reads only files it requests. It cannot write to disk.</p>
    {work.message && <p role="status" className="whitespace-pre-wrap">{work.message}</p>}
    {work.task && <div className="space-y-2 border-t pt-2 dark:border-gray-700">
      <p>{work.task.summary}</p>
      <p className="text-gray-500">{work.task.file_count} files · {work.task.steps} steps · {work.task.inspected.length} inspected</p>
      <details><summary className="cursor-pointer">Inspected files</summary><ul className="mt-1 list-disc pl-4">{work.task.inspected.map((path) => <li key={path}>{path}</li>)}</ul></details>
      {work.task.status === "review" && <>
        <p className="font-medium">Proposed changes: {work.task.changes.length} files</p>
        {work.task.changes.map((change) => <details key={change.path} className="rounded border p-1 dark:border-gray-600">
          <summary className="cursor-pointer">{change.path}</summary>
          <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap text-[10px]">{change.diff || "No content changes."}</pre>
        </details>)}
        <button onClick={() => void work.apply()} disabled={work.busy || !work.task.changes.length}
          className="rounded bg-blue-600 px-2 py-1 text-white disabled:opacity-50">Accept changes into editor</button>
      </>}
      <button onClick={work.discard} className="ml-2 text-gray-500 underline">{work.busy ? "Cancel task" : "Discard proposal"}</button>
    </div>}
  </div>;
}
