/**
 * True when the same translation task has just moved from running to a terminal
 * state (completed, cancelled, or failed) and its output folders now exist on disk,
 * so the project tree must reload to show them. Comparing task ids keeps a status
 * from one project or task from being treated as the end of another.
 */
export function isProjectTranslationFinished(previous, next) {
  return !!previous && !!next && previous.id === next.id && previous.status === "running" && next.status !== "running";
}
