import { test } from "node:test";
import assert from "node:assert/strict";

// Covers the editor/preview scroll-sync helpers that PreviewPane imports.
import {
  MSG_PREVIEW_READY,
  MSG_SNAP,
  SYNC_SCRIPT,
  locateLine,
  scrollRatio,
  withSyncScript,
} from "../src/lib/preview-sync.mjs";

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

test("the sync script goes before </body> when there is one", () => {
  const out = withSyncScript("<html><body><p>x</p></body></html>");
  assert.ok(out.endsWith(SYNC_SCRIPT + "</body></html>"));
  assert.equal(out.split("<script>").length, 2);
});

test("the sync script is appended to HTML fragments", () => {
  assert.equal(withSyncScript("<p>x</p>"), "<p>x</p>" + SYNC_SCRIPT);
});

test("the injected script parses and wires the expected messages", () => {
  const body = SYNC_SCRIPT.replace(/^<script>/, "").replace(/<\/script>$/, "");
  assert.doesNotThrow(() => new Function(body)); // valid JavaScript
  assert.ok(body.includes(MSG_SNAP));
  assert.ok(body.includes(MSG_PREVIEW_READY));
  // Only the parent editor window may drive the preview.
  assert.ok(body.includes("e.source!==parent"));
});
