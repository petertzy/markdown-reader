import { test } from "node:test";
import assert from "node:assert/strict";

import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

// Static regression guard for the find-widget flicker CSS workaround in
// frontend/src/app/globals.css. CI has no browser/DOM, so instead of testing
// runtime flicker we assert the selector is in the correct, active form.
//
// History: the first version used `body:has(body .monaco-editor …)`. :has()
// takes RELATIVE selectors, so that required a nested <body> element and never
// matched. The corrected form below matches a <body> that has a descendant
// .find-widget.visible and keeps the rule active.
const globalsCss = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../src/app/globals.css"),
  "utf8"
);

test("find-widget rule uses a valid :has() relative selector", () => {
  assert.match(
    globalsCss,
    /body:has\(\.monaco-editor \.find-widget\.visible\)/,
    "the rule must match a <body> that has a descendant .find-widget.visible"
  );
});

test("find-widget rule never requires a nested <body> element", () => {
  assert.doesNotMatch(
    globalsCss,
    /body:has\(body/,
    "the selector must be `body:has(.monaco-editor …)`, not `body:has(body …)`"
  );
});

test("find-widget rule keeps the single-row tooltip + pointer-events guards", () => {
  assert.match(globalsCss, /\.workbench-hover-container/, "targets the monaco workbench hover");
  assert.match(globalsCss, /white-space:\s*nowrap\s*!important/i, "single-row tooltip layout");
  assert.match(globalsCss, /pointer-events:\s*none\s*!important/i, "pointer-events guard present");
});