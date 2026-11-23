import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

// Covers the editor/preview scroll-sync helpers that PreviewPane imports.
import {
  ECHO_GUARD_MS,
  FRAME_SCRIPT_PATH,
  MSG_FROM_PREVIEW,
  MSG_PREVIEW_READY,
  MSG_SNAP,
  MSG_TO_PREVIEW,
  SNAP_GUARD_MS,
  locateLine,
  scrollRatio,
  syncScriptTag,
  withSyncScript,
} from "../src/lib/preview-sync.mjs";

const ORIGIN = "http://tauri.localhost";
const FRAME_SCRIPT = readFileSync(new URL("../public" + FRAME_SCRIPT_PATH, import.meta.url), "utf8");

const doc = [
  "Intro line",       // 1
  "",                 // 2
  "# Title",          // 3
  "",                 // 4
  "Para under title", // 5
  "",                 // 6
  "## Section A",     // 7
  "",                 // 8
  "Para A",           // 9
  "",                 // 10
];

test("a heading line maps to itself with no offset", () => {
  assert.deepEqual(locateLine(doc, 3), { heading: 0, fraction: 0 });
  assert.deepEqual(locateLine(doc, 7), { heading: 1, fraction: 0 });
});

test("a line between headings maps to the heading above plus a fraction", () => {
  // Line 5 is halfway between "# Title" (3) and "## Section A" (7).
  assert.deepEqual(locateLine(doc, 5), { heading: 0, fraction: 0.5 });
});

test("lines before the first heading use -1", () => {
  const { heading, fraction } = locateLine(doc, 1);
  assert.equal(heading, -1);
  assert.equal(fraction, 0);
});

test("the last section runs to the end of the document", () => {
  // Section A starts at 7; the document ends after line 10.
  assert.deepEqual(locateLine(doc, 9), { heading: 1, fraction: 0.5 });
});

test("headings inside code fences are ignored, like in the rendered preview", () => {
  const fenced = ["# Real", "```", "# not a heading", "```", "## Next"];
  assert.equal(locateLine(fenced, 3).heading, 0);
  assert.equal(locateLine(fenced, 5).heading, 1);
  const tilde = ["# Real", "~~~", "## nope", "~~~", "text"];
  assert.equal(locateLine(tilde, 5).heading, 0);
});

test("'#' without a space is not a heading", () => {
  assert.equal(locateLine(["#hashtag", "# Real"], 1).heading, -1);
});

test("an empty document does not throw", () => {
  assert.deepEqual(locateLine([], 1), { heading: -1, fraction: 0 });
});

test("scrollRatio stays within 0..1 and handles short documents", () => {
  assert.equal(scrollRatio(0, 1000, 400), 0);
  assert.equal(scrollRatio(300, 1000, 400), 0.5);
  assert.equal(scrollRatio(600, 1000, 400), 1);
  assert.equal(scrollRatio(900, 1000, 400), 1);
  assert.equal(scrollRatio(10, 300, 400), 0); // fits on screen: nothing to scroll
});

test("the sync script tag goes before </body> when there is one", () => {
  const out = withSyncScript("<html><body><p>x</p></body></html>", ORIGIN);
  assert.ok(out.endsWith(syncScriptTag(ORIGIN) + "</body></html>"));
  assert.equal(out.split("<script").length, 2);
});

test("the sync script tag is appended to HTML fragments", () => {
  assert.equal(withSyncScript("<p>x</p>", ORIGIN), "<p>x</p>" + syncScriptTag(ORIGIN));
});

test("the sync script is loaded by URL from the app origin, never inlined", () => {
  // Packaged Tauri builds add script hashes to the CSP the srcdoc inherits,
  // which makes browsers ignore 'unsafe-inline'. Only src= scripts run there.
  const tag = syncScriptTag(ORIGIN);
  assert.match(tag, /^<script [^>]*><\/script>$/);
  assert.ok(tag.includes(`src="${ORIGIN}${FRAME_SCRIPT_PATH}"`));
  assert.ok(syncScriptTag(ORIGIN + "/").includes(`src="${ORIGIN}${FRAME_SCRIPT_PATH}"`));
});

test("the tag carries the message names and timings as data attributes", () => {
  const tag = syncScriptTag(ORIGIN);
  for (const [name, value] of [
    ["data-msg-to-preview", MSG_TO_PREVIEW],
    ["data-msg-from-preview", MSG_FROM_PREVIEW],
    ["data-msg-preview-ready", MSG_PREVIEW_READY],
    ["data-msg-snap", MSG_SNAP],
    ["data-echo-guard-ms", ECHO_GUARD_MS],
    ["data-snap-guard-ms", SNAP_GUARD_MS],
  ]) {
    assert.ok(tag.includes(`${name}="${value}"`), name);
  }
});

/** Run the frame script against a tiny fake window built from a real tag. */
function runFrame(tag) {
  const dataset = {};
  for (const [, name, value] of tag.matchAll(/data-([a-z-]+)="([^"]*)"/g)) {
    dataset[name.replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = value;
  }
  const posted = [];
  const listeners = {};
  const scroller = { scrollTop: 0, scrollHeight: 2000 };
  // Copy into this realm so deepEqual compares plain objects.
  const parent = { postMessage: (msg) => posted.push({ ...msg }) };
  const window = {
    innerHeight: 1000,
    addEventListener: (type, fn) => (listeners[type] = fn),
    scrollTo: () => {},
  };
  const document = {
    currentScript: { dataset },
    scrollingElement: scroller,
    body: { querySelectorAll: () => [] },
  };
  vm.runInNewContext(FRAME_SCRIPT, { window, document, parent, Date, Math, Number, setTimeout });
  return { posted, listeners, scroller, parent };
}

test("the frame script is valid JavaScript", () => {
  assert.doesNotThrow(() => new vm.Script(FRAME_SCRIPT));
});

test("the frame script announces itself with the configured ready message", () => {
  const { posted } = runFrame(syncScriptTag(ORIGIN));
  assert.deepEqual(posted, [{ type: MSG_PREVIEW_READY }]);
});

test("the frame script scrolls only for messages from the parent window", () => {
  const { listeners, scroller, parent } = runFrame(syncScriptTag(ORIGIN));
  listeners.message({ source: {}, data: { type: MSG_TO_PREVIEW, ratio: 0.5 } });
  assert.equal(scroller.scrollTop, 0);
  listeners.message({ source: parent, data: { type: MSG_TO_PREVIEW, ratio: 0.5 } });
  assert.equal(scroller.scrollTop, 500);
});

test("the frame script reports user scrolling back with the configured message", () => {
  const { listeners, scroller, posted } = runFrame(syncScriptTag(ORIGIN));
  scroller.scrollTop = 250;
  listeners.scroll();
  assert.deepEqual(posted.at(-1), { type: MSG_FROM_PREVIEW, ratio: 0.25 });
});
