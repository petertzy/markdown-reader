import assert from "node:assert/strict";
import { test } from "node:test";

import {
  captureTocInsertionTarget,
  isTocInsertionTargetCurrent,
} from "../src/lib/toc-insertion-guard.mjs";

function createEditor(name) {
  const model = {
    name,
    version: 1,
    getVersionId() {
      return this.version;
    },
  };
  return {
    model,
    selection: { startLineNumber: 1, startColumn: 1, endLineNumber: 1, endColumn: 1 },
    getModel() {
      return this.model;
    },
    getSelection() {
      return this.selection;
    },
  };
}

function deferred() {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

test("a deferred TOC result is not inserted after switching tabs", async () => {
  const editorA = createEditor("A");
  const editorB = createEditor("B");
  let activeEditor = editorA;
  const target = captureTocInsertionTarget(editorA);
  const request = deferred();
  const inserted = [];

  const completion = request.promise.then(() => {
    if (isTocInsertionTargetCurrent(target, activeEditor)) inserted.push("TOC");
  });
  activeEditor = editorB;
  request.resolve();
  await completion;

  assert.deepEqual(inserted, []);
});

test("a deferred TOC result is not inserted after an edit or cursor move", async () => {
  const editor = createEditor("A");
  const target = captureTocInsertionTarget(editor);
  const request = deferred();
  const inserted = [];

  const completion = request.promise.then(() => {
    if (isTocInsertionTargetCurrent(target, editor)) inserted.push("TOC");
  });
  editor.model.version += 1;
  editor.selection = { startLineNumber: 2, startColumn: 1, endLineNumber: 2, endColumn: 1 };
  request.resolve();
  await completion;

  assert.deepEqual(inserted, []);
});

test("a deferred TOC result inserts at an unchanged target", async () => {
  const editor = createEditor("A");
  const target = captureTocInsertionTarget(editor);
  const request = deferred();
  const inserted = [];

  const completion = request.promise.then(() => {
    if (isTocInsertionTargetCurrent(target, editor)) inserted.push("TOC");
  });
  request.resolve();
  await completion;

  assert.deepEqual(inserted, ["TOC"]);
});
