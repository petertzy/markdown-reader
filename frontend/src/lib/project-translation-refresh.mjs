const TERMINAL_STATUSES = new Set(["completed", "cancelled", "failed"]);

/**
 * True when the same translation task has just moved from running to a terminal
 * state (completed, cancelled, or failed) and its output folders now exist on disk,
 * so the project tree must reload to show them. Comparing task ids keeps a status
 * from one project or task from being treated as the end of another.
 */
export function isProjectTranslationFinished(previous, next) {
  return !!previous
    && !!next
    && previous.id === next.id
    && previous.status === "running"
    && TERMINAL_STATUSES.has(next.status);
}

/**
 * Reports each task snapshot once: observe() returns true only for the snapshot
 * that completes a running task, so a finished translation reloads the tree once.
 */
export function createFinishTracker() {
  let previous = null;
  return {
    observe(next) {
      const finished = isProjectTranslationFinished(previous, next);
      previous = next;
      return finished;
    },
    reset() {
      previous = null;
    },
  };
}

/**
 * Tracks which project the translation UI currently belongs to. Every root change
 * starts a new generation; a request started in an earlier generation is stale and
 * must not write its result or error into the current project's state.
 */
export function createProjectScope() {
  let root = null;
  let generation = 0;
  return {
    setRoot(next) {
      if (next === root) return;
      root = next;
      generation += 1;
    },
    token() {
      return generation;
    },
    isCurrent(token) {
      return token === generation;
    },
  };
}
