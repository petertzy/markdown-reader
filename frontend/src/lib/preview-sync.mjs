// preview-sync.mjs
// Scroll sync between the Monaco editor and the sandboxed preview iframe.
//
// The preview iframe has no same-origin access, so the two sides talk through
// postMessage. The iframe side lives in public/preview-sync-frame.js and is
// loaded by a <script src> tag added to the preview HTML. Plain .mjs (not .ts)
// so the Node test suite can import it.

export const MSG_TO_PREVIEW = "mdr-scroll";
export const MSG_FROM_PREVIEW = "mdr-preview-scroll";
export const MSG_PREVIEW_READY = "mdr-preview-ready";
export const MSG_SNAP = "mdr-snap";
// After one side scrolls the other, ignore the echo for this long.
export const ECHO_GUARD_MS = 150;
// Long enough to cover the preview's smooth-scroll animation.
export const SNAP_GUARD_MS = 900;

const HEADING_RE = /^#{1,6}\s/;
const FENCE_RE = /^\s*(```|~~~)/;

/**
 * Locate a source line relative to the Markdown headings around it.
 * Returns the index of the last heading at or above the line (-1 if none) and
 * how far the line sits between that heading and the next one (0..1).
 * Headings inside fenced code blocks are ignored, matching the rendered HTML.
 *
 * @param {string[]} lines document lines
 * @param {number} lineNumber 1-based line number
 * @returns {{ heading: number, fraction: number }}
 */
export function locateLine(lines, lineNumber) {
  const headingLines = [];
  let inFence = false;
  lines.forEach((text, i) => {
    if (FENCE_RE.test(text)) inFence = !inFence;
    else if (!inFence && HEADING_RE.test(text)) headingLines.push(i + 1);
  });
  let heading = -1;
  while (heading + 1 < headingLines.length && headingLines[heading + 1] <= lineNumber) heading++;
  const start = heading >= 0 ? headingLines[heading] : 1;
  const end = headingLines[heading + 1] ?? lines.length + 1;
  const fraction = end > start ? Math.min(1, Math.max(0, (lineNumber - start) / (end - start))) : 0;
  return { heading, fraction };
}

/** Path of the iframe-side script, served from frontend/public. */
export const FRAME_SCRIPT_PATH = "/preview-sync-frame.js";

function escapeAttr(value) {
  return String(value).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

/**
 * The <script> tag that loads the iframe side of the sync.
 *
 * It must be loaded by URL, not inlined: the preview's srcdoc inherits the
 * app's Content Security Policy, and packaged Tauri builds add script hashes
 * to it, which makes browsers ignore 'unsafe-inline'. The URL is absolute
 * because the sandboxed iframe has an opaque origin of its own.
 *
 * @param {string} origin the editor window's origin, e.g. window.location.origin
 * @returns {string}
 */
export function syncScriptTag(origin) {
  const attrs = {
    src: origin.replace(/\/+$/, "") + FRAME_SCRIPT_PATH,
    "data-msg-to-preview": MSG_TO_PREVIEW,
    "data-msg-from-preview": MSG_FROM_PREVIEW,
    "data-msg-preview-ready": MSG_PREVIEW_READY,
    "data-msg-snap": MSG_SNAP,
    "data-echo-guard-ms": ECHO_GUARD_MS,
    "data-snap-guard-ms": SNAP_GUARD_MS,
  };
  const rendered = Object.entries(attrs)
    .map(([name, value]) => `${name}="${escapeAttr(value)}"`)
    .join(" ");
  return `<script ${rendered}></script>`;
}

/**
 * Insert the sync script tag into preview HTML, before </body> when present.
 * @param {string} html
 * @param {string} origin the editor window's origin
 * @returns {string}
 */
export function withSyncScript(html, origin) {
  const tag = syncScriptTag(origin);
  const closeBody = html.lastIndexOf("</body>");
  if (closeBody === -1) return html + tag;
  return html.slice(0, closeBody) + tag + html.slice(closeBody);
}

/**
 * Scroll position as a 0..1 fraction of the scrollable range.
 * @param {number} scrollTop
 * @param {number} scrollHeight
 * @param {number} viewportHeight
 */
export function scrollRatio(scrollTop, scrollHeight, viewportHeight) {
  const max = scrollHeight - viewportHeight;
  return max > 0 ? Math.min(1, Math.max(0, scrollTop / max)) : 0;
}
