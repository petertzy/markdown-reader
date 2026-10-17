import { test } from "node:test";
import assert from "node:assert/strict";

import {
  applyWorkResultIfFresh,
  createDocumentRequestGuard,
  isWorkResultFresh,
} from "../src/lib/work-result-guard.mjs";

const originalSnapshot = { documentId: "tab-1", content: "Original document" };

test("unchanged document applies the AI Work result", () => {
  const applied = [];
  const currentSnapshot = { ...originalSnapshot };

  assert.equal(isWorkResultFresh(originalSnapshot, currentSnapshot), true);
  assert.equal(
    applyWorkResultIfFresh(
      originalSnapshot,
      currentSnapshot,
      "AI-modified document",
      (content) => applied.push(content)
    ),
    true
  );
  assert.deepEqual(applied, ["AI-modified document"]);
});

test("switching tabs invalidates a pending translation request", () => {
  const guard = createDocumentRequestGuard("file-1");
  const request = guard.issue();

  guard.setDocument("file-2");

  assert.equal(guard.isCurrent(request), false);
  assert.equal(guard.isCurrent(guard.issue()), true);
});

test("content changed during the request rejects the stale result", () => {
  const applied = [];
  const currentSnapshot = { documentId: "tab-1", content: "Newer user edit" };

  assert.equal(isWorkResultFresh(originalSnapshot, currentSnapshot), false);
  assert.equal(
    applyWorkResultIfFresh(
      originalSnapshot,
      currentSnapshot,
      "Stale AI result",
      (content) => applied.push(content)
    ),
    false
  );
  assert.deepEqual(applied, []);
});

test("switching to a different document rejects the stale result", () => {
  const applied = [];
  const currentSnapshot = { documentId: "tab-2", content: "Original document" };

  assert.equal(isWorkResultFresh(originalSnapshot, currentSnapshot), false);
  assert.equal(
    applyWorkResultIfFresh(
      originalSnapshot,
      currentSnapshot,
      "Stale AI result",
      (content) => applied.push(content)
    ),
    false
  );
  assert.deepEqual(applied, []);
});
