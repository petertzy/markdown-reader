/**
 * http-timeout.mjs
 * ================
 * Fetch timeout helpers shared by the browser/desktop API client and its
 * regression tests.
 *
 * Kept as a plain ESM module (no TypeScript) so the Node-based regression
 * suite (node:test, .mjs) can exercise the exact code the app runs.
 */

/**
 * Short budget for lightweight API calls (settings, metadata, file listing).
 * A hung request should surface as an error instead of leaving the UI
 * awaiting forever.
 */
export const DEFAULT_REQUEST_TIMEOUT_MS = 30000;

/**
 * Generous budget for long-running AI/conversion endpoints (chat, translate,
 * PDF → Markdown, DOCX/PDF export). These can legitimately take minutes for
 * large documents, slow/local models, or slower conversion backends, so they
 * must not be cut off by the short default.
 */
export const LONG_REQUEST_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes

/**
 * Composes an arbitrary number of AbortSignals into one that aborts when ANY
 * of the inputs aborts (caller cancellation, timeout, or both). Returns
 * `undefined` when no signals are provided and the single signal when only
 * one is given. Falls back to manual wiring when `AbortSignal.any` is not
 * available in the runtime (older webviews).
 *
 * @param {...(AbortSignal | undefined)} signals
 * @returns {AbortSignal | undefined}
 */
export function composeAbortSignals(...signals) {
  const present = signals.filter(Boolean);
  if (present.length === 0) return undefined;
  if (present.length === 1) return present[0];
  if (typeof AbortSignal !== "undefined" && typeof AbortSignal.any === "function") {
    return AbortSignal.any(present);
  }
  // Manual composition: abort our controller when any input aborts.
  const controller = new AbortController();
  for (const signal of present) {
    if (signal.aborted) {
      controller.abort();
      break;
    }
    signal.addEventListener("abort", () => controller.abort(), { once: true });
  }
  return controller.signal;
}

/**
 * fetch() with an automatic abort timeout. A caller-supplied `init.signal` is
 * composed with the timeout signal rather than replacing it, so BOTH the
 * caller's cancellation and the timeout stay effective.
 *
 * @param {RequestInfo | URL} input
 * @param {RequestInit} [init]
 * @param {number} [timeoutMs] Defaults to DEFAULT_REQUEST_TIMEOUT_MS.
 * @returns {Promise<Response>}
 */
export function fetchWithTimeout(input, init = {}, timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS) {
  const controller = new AbortController();
  // globalThis works in browsers, the Tauri webview, and non-browser runtimes
  // (SSR / tests) alike, unlike window.setTimeout. A non-positive timeout
  // disables the automatic abort (explicit "no deadline" opt-out).
  let timeoutId;
  if (timeoutMs > 0) {
    timeoutId = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  }
  return fetch(input, {
    ...init,
    signal: composeAbortSignals(init.signal, controller.signal),
  }).finally(() => {
    if (timeoutId !== undefined) globalThis.clearTimeout(timeoutId);
  });
}