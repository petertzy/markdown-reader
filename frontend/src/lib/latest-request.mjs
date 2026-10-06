/**
 * latest-request.mjs
 * ==================
 * Guards asynchronous, out-of-order responses.
 *
 * The preview is re-rendered on every keystroke, so several `Markdown.render`
 * requests can be in flight at once. They are served by a `def` endpoint on a
 * threadpool, and a large document renders much slower than a small one — so the
 * response that arrives *last* is often not the response for the newest content.
 * Applying it unconditionally leaves the preview showing text the user has
 * already deleted.
 *
 * A monotonic token per channel makes the intent explicit: a response may only
 * be applied if it belongs to the most recently issued request.
 *
 * Kept as a plain ESM module (no TypeScript) so the Node-based regression suite
 * (node:test, .mjs) can exercise the exact code the app runs (same pattern as
 * http-timeout.mjs).
 */

/**
 * Create a per-channel ordering guard.
 *
 * @example
 *   const guard = createLatestRequestGuard();
 *   const token = guard.issue();
 *   render(content).then((html) => {
 *     if (guard.isCurrent(token)) setPreviewHtml(html);
 *   });
 *
 * @returns {{
 *   issue: () => number,
 *   isCurrent: (token: number) => boolean,
 *   supersede: () => void,
 *   current: () => number | null,
 * }}
 */
export function createLatestRequestGuard() {
  // `null` means nothing is in flight, so the first issue() yields token 1.
  let latest = null;

  return {
    /**
     * Record that a new request has been started, invalidating every token
     * handed out earlier.
     *
     * @returns {number} Token to hand to the matching response.
     */
    issue() {
      latest = (latest ?? 0) + 1;
      return latest;
    },

    /**
     * True when `token` still belongs to the most recently issued request, so
     * applying it cannot regress the view.
     *
     * @param {number} token
     * @returns {boolean}
     */
    isCurrent(token) {
      return latest !== null && token === latest;
    },

    /**
     * Abandon any in-flight request without issuing a new one, so nothing that
     * is already pending may write state.
     *
     * @returns {void}
     */
    supersede() {
      latest = (latest ?? 0) + 1;
    },

    /**
     * Token of the newest request, or `null` when nothing is in flight.
     *
     * @returns {number | null}
     */
    current() {
      return latest;
    },
  };
}
