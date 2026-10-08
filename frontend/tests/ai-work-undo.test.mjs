import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import * as monaco from "monaco-editor/esm/vs/editor/editor.api.js";
import { applyWorkEdit } from "../src/lib/apply-work-edit.mjs";

function getModelValue(model) {
  return model.getValue(monaco.editor.EndOfLinePreference.LF);
}

// Minimal stand-in for the mounted Monaco editor: the three members
// `applyWorkEdit` is allowed to touch, backed by a real model so the undo/redo
// stack is genuine Monaco behaviour rather than a mock.
function fakeEditor(model) {
  return {
    getModel: () => model,
    pushUndoStop: () => model.pushStackElement(),
    executeEdits: (_source, edits) => model.pushEditOperations([], edits, () => null),
  };
}

// Mirror of how the user's typing reaches the model: one edit + one undo stop.
function typeText(model, text) {
  const lineCount = model.getLineCount();
  const maxCol = model.getLineMaxColumn(lineCount);
  model.pushEditOperations(
    [],
    [
      {
        range: {
          startLineNumber: lineCount,
          startColumn: maxCol,
          endLineNumber: lineCount,
          endColumn: maxCol,
        },
        text,
      },
    ],
    () => null
  );
  model.pushStackElement();
}

function newModel(initial = "") {
  const model = monaco.editor.createModel(initial, "markdown");
  model.setEOL(monaco.editor.EndOfLineSequence.LF);
  return model;
}

beforeEach(() => {
  for (const m of monaco.editor.getModels()) m.dispose();
});

afterEach(() => {
  for (const m of monaco.editor.getModels()) m.dispose();
});

test("AI Work result is applied through the editor, not the state callback", () => {
  const model = newModel();
  typeText(model, "Draft body.");
  const fallback = [];
  const used = applyWorkEdit(fakeEditor(model), (c) => fallback.push(c), "AI result.");
  assert.equal(used, true);
  assert.equal(getModelValue(model), "AI result.");
  assert.deepEqual(fallback, []);
});

test("a single Undo restores the exact pre-Work document and Redo reapplies it", () => {
  const model = newModel();
  typeText(model, "First edit. ");
  typeText(model, "Second edit.");
  const before = getModelValue(model);
  applyWorkEdit(fakeEditor(model), () => {}, "AI rewritten.");

  model.undo();
  assert.equal(getModelValue(model), before, "one Undo must restore the pre-Work document");

  model.redo();
  assert.equal(getModelValue(model), "AI rewritten.");
});

test("the AI replacement does not merge into the user's previous typing", () => {
  const model = newModel();
  typeText(model, "typed once");
  typeText(model, " and twice");
  applyWorkEdit(fakeEditor(model), () => {}, "generated");

  // Undo #1 removes only the AI edit; the two typing steps remain undoable.
  model.undo();
  assert.equal(getModelValue(model), "typed once and twice");
  model.undo();
  assert.equal(getModelValue(model), "typed once");
  model.undo();
  assert.equal(getModelValue(model), "");
});

test("several AI applies are each individually undoable", () => {
  const model = newModel();
  const editor = fakeEditor(model);
  typeText(model, "A");
  applyWorkEdit(editor, () => {}, "B");
  applyWorkEdit(editor, () => {}, "C");

  model.undo();
  assert.equal(getModelValue(model), "B");
  model.undo();
  assert.equal(getModelValue(model), "A");
  model.redo();
  assert.equal(getModelValue(model), "B");
  model.redo();
  assert.equal(getModelValue(model), "C");
});

test("applying to an unchanged document is functionally equivalent and redoable", () => {
  const model = newModel("Unchanged document.");
  applyWorkEdit(fakeEditor(model), () => {}, "Work result.");
  assert.equal(getModelValue(model), "Work result.");
  model.undo();
  assert.equal(getModelValue(model), "Unchanged document.");
});

test("an unsealed edit before the Work result is not swallowed by one Undo", () => {
  const model = newModel();
  // A programmatic/paste edit that has not yet been sealed into an undo stop:
  // the opening boundary is what keeps the AI replacement from merging with it.
  model.pushEditOperations([], [{ range: model.getFullModelRange(), text: "pasted text" }], () => null);
  applyWorkEdit(fakeEditor(model), () => {}, "worked");
  assert.equal(getModelValue(model), "worked");
  model.undo();
  assert.equal(getModelValue(model), "pasted text");
});

test("falls back to onDocumentChange when no editor/model is available", () => {
  const calls = [];
  assert.equal(applyWorkEdit(null, (c) => calls.push(c), "one"), false);
  assert.equal(
    applyWorkEdit({ getModel: () => null, pushUndoStop() {}, executeEdits() {} }, (c) => calls.push(c), "two"),
    false
  );
  assert.equal(
    applyWorkEdit({ getModel: () => ({ getFullModelRange: () => ({}) }) }, (c) => calls.push(c), "three"),
    false
  );
  assert.deepEqual(calls, ["one", "two", "three"]);
});