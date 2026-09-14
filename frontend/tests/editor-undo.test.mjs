import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import * as monaco from "monaco-editor/esm/vs/editor/editor.api.js";

function getModelValue(model) {
  return model.getValue(monaco.editor.EndOfLinePreference.LF);
}

// Helper to simulate typing into a Monaco model with an undo stop
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

// Helper to simulate deleting a range of content
function deleteRange(model, range) {
  model.pushEditOperations([], [{ range, text: "" }], () => null);
  model.pushStackElement();
}

// Simulated tab store matching useEditor tab lifecycle
class TabManager {
  constructor() {
    this.counter = 0;
    this.tabs = [];
    this.activeTabId = null;
    this.models = new Map();
  }

  nextTabId() {
    return `tab-${++this.counter}`;
  }

  createUnsavedTab(initialContent = "") {
    const id = this.nextTabId();
    const tab = {
      id,
      label: "Untitled",
      filePath: null,
      content: initialContent,
      dirty: false,
    };
    this.tabs.push(tab);
    this.activeTabId = id;

    // Get or create model using the stable tab ID as Monaco path
    const uri = monaco.Uri.parse(id);
    let model = monaco.editor.getModel(uri);
    if (!model) {
      model = monaco.editor.createModel(initialContent, "markdown", uri);
      model.setEOL(monaco.editor.EndOfLineSequence.LF);
    }
    this.models.set(id, model);
    return tab;
  }

  openSavedTab(filePath, content) {
    const id = this.nextTabId();
    const label = filePath.split(/[/\\]/).pop() ?? filePath;
    const tab = {
      id,
      label,
      filePath,
      content,
      dirty: false,
    };
    this.tabs.push(tab);
    this.activeTabId = id;

    const uri = monaco.Uri.parse(id);
    let model = monaco.editor.getModel(uri);
    if (!model) {
      model = monaco.editor.createModel(content, "markdown", uri);
      model.setEOL(monaco.editor.EndOfLineSequence.LF);
    }
    this.models.set(id, model);
    return tab;
  }

  saveActiveTab(filePath) {
    const tab = this.tabs.find((t) => t.id === this.activeTabId);
    if (!tab) return;
    tab.filePath = filePath;
    tab.label = filePath.split(/[/\\]/).pop() ?? filePath;
    tab.dirty = false;
    // Note: tab.id remains unchanged, so model identity is preserved
  }

  switchToTab(id) {
    this.activeTabId = id;
    const uri = monaco.Uri.parse(id);
    return monaco.editor.getModel(uri);
  }

  getActiveModel() {
    const uri = monaco.Uri.parse(this.activeTabId);
    return monaco.editor.getModel(uri);
  }

  disposeAll() {
    for (const model of this.models.values()) {
      model.dispose();
    }
    this.models.clear();
  }
}

beforeEach(() => {
  for (const m of monaco.editor.getModels()) {
    m.dispose();
  }
});

afterEach(() => {
  for (const m of monaco.editor.getModels()) {
    m.dispose();
  }
});

test("Test 1 — Unsaved document Undo: type ABC -> type DEF -> Undo -> expect ABC", () => {
  const manager = new TabManager();
  manager.createUnsavedTab();
  const model = manager.getActiveModel();

  assert.strictEqual(getModelValue(model), "");

  typeText(model, "ABC");
  assert.strictEqual(getModelValue(model), "ABC");

  typeText(model, "DEF");
  assert.strictEqual(getModelValue(model), "ABCDEF");

  // Press Undo -> expect ABC
  model.undo();
  assert.strictEqual(getModelValue(model), "ABC");

  // Press Undo again -> expect empty string
  model.undo();
  assert.strictEqual(getModelValue(model), "");

  // Undo must never clear unexpectedly or throw
  model.undo();
  assert.strictEqual(getModelValue(model), "");

  manager.disposeAll();
});

test("Test 2 — Multiple Undo operations step-by-step", () => {
  const manager = new TabManager();
  manager.createUnsavedTab();
  const model = manager.getActiveModel();

  typeText(model, "Step 1\n");
  typeText(model, "Step 2\n");
  typeText(model, "Step 3\n");
  assert.strictEqual(getModelValue(model), "Step 1\nStep 2\nStep 3\n");

  model.undo();
  assert.strictEqual(getModelValue(model), "Step 1\nStep 2\n");

  model.undo();
  assert.strictEqual(getModelValue(model), "Step 1\n");

  model.undo();
  assert.strictEqual(getModelValue(model), "");

  manager.disposeAll();
});

test("Test 3 — Large deletion: enter substantial content -> delete -> Undo restores", () => {
  const manager = new TabManager();
  manager.createUnsavedTab();
  const model = manager.getActiveModel();

  const substantialContent = Array.from(
    { length: 50 },
    (_, i) => `Paragraph ${i + 1}: Some detailed markdown content here.`
  ).join("\n\n");
  typeText(model, substantialContent);
  assert.strictEqual(getModelValue(model), substantialContent);

  // Delete everything
  deleteRange(model, model.getFullModelRange());
  assert.strictEqual(getModelValue(model), "");

  // Undo deletion
  model.undo();
  assert.strictEqual(getModelValue(model), substantialContent);

  manager.disposeAll();
});

test("Test 4 — Create -> Edit -> Undo -> Save works correctly and preserves model identity", () => {
  const manager = new TabManager();
  const tab = manager.createUnsavedTab();
  const model = manager.getActiveModel();

  typeText(model, "# Document Title\n");
  typeText(model, "Draft paragraph.");
  assert.strictEqual(getModelValue(model), "# Document Title\nDraft paragraph.");

  // Undo the draft paragraph
  model.undo();
  assert.strictEqual(getModelValue(model), "# Document Title\n");

  // Save the document
  manager.saveActiveTab("/home/user/document.md");
  assert.strictEqual(tab.filePath, "/home/user/document.md");
  assert.strictEqual(tab.dirty, false);

  // Model identity and undo stack are preserved across save
  const modelAfterSave = manager.getActiveModel();
  assert.strictEqual(modelAfterSave, model);
  assert.strictEqual(getModelValue(modelAfterSave), "# Document Title\n");

  // Can still undo prior edits after save if desired
  modelAfterSave.undo();
  assert.strictEqual(getModelValue(modelAfterSave), "");

  // Can redo
  modelAfterSave.redo();
  assert.strictEqual(getModelValue(modelAfterSave), "# Document Title\n");

  manager.disposeAll();
});

test("Test 5 — Saved document regression: Undo continues to work for already-saved files", () => {
  const manager = new TabManager();
  const initialSavedContent = "# Saved Document\n\nExisting body text.";
  manager.openSavedTab("/docs/notes.md", initialSavedContent);
  const model = manager.getActiveModel();

  assert.strictEqual(getModelValue(model), initialSavedContent);

  typeText(model, "\n\nNew section added.");
  assert.strictEqual(getModelValue(model), `${initialSavedContent}\n\nNew section added.`);

  model.undo();
  assert.strictEqual(getModelValue(model), initialSavedContent);

  manager.disposeAll();
});

test("Test 6 — Multiple tabs/documents: Undo history belongs to correct document and does not leak between tabs", () => {
  const manager = new TabManager();

  // Tab 1: Saved file
  const tab1 = manager.openSavedTab("/docs/tab1.md", "# Document One");
  const model1 = manager.getActiveModel();
  typeText(model1, "\nEdit in doc 1");

  // Tab 2: Newly created unsaved file
  const tab2 = manager.createUnsavedTab();
  const model2 = manager.getActiveModel();

  // Ensure model2 is a distinct model
  assert.notStrictEqual(model1, model2);
  assert.strictEqual(getModelValue(model2), "");

  typeText(model2, "ABC");
  typeText(model2, "DEF");
  assert.strictEqual(getModelValue(model2), "ABCDEF");

  // Undo in Tab 2
  model2.undo();
  assert.strictEqual(getModelValue(model2), "ABC");

  // Switch back to Tab 1
  const switchedModel1 = manager.switchToTab(tab1.id);
  assert.strictEqual(switchedModel1, model1);
  assert.strictEqual(getModelValue(switchedModel1), "# Document One\nEdit in doc 1");

  // Undo in Tab 1
  switchedModel1.undo();
  assert.strictEqual(getModelValue(switchedModel1), "# Document One");

  // Switch back to Tab 2: Tab 2's content and undo state are intact and unaffected by Tab 1
  const switchedModel2 = manager.switchToTab(tab2.id);
  assert.strictEqual(switchedModel2, model2);
  assert.strictEqual(getModelValue(switchedModel2), "ABC");

  // Further undo in Tab 2 does not bring in Tab 1 content
  switchedModel2.undo();
  assert.strictEqual(getModelValue(switchedModel2), "");
  switchedModel2.undo();
  assert.strictEqual(getModelValue(switchedModel2), "");

  manager.disposeAll();
});

test("Test 7 — Redo: Cmd+Z -> Cmd+Shift+Z works correctly", () => {
  const manager = new TabManager();
  manager.createUnsavedTab();
  const model = manager.getActiveModel();

  typeText(model, "First edit. ");
  typeText(model, "Second edit.");
  assert.strictEqual(getModelValue(model), "First edit. Second edit.");

  // Undo (Cmd+Z)
  model.undo();
  assert.strictEqual(getModelValue(model), "First edit. ");

  // Redo (Cmd+Shift+Z)
  model.redo();
  assert.strictEqual(getModelValue(model), "First edit. Second edit.");

  manager.disposeAll();
});

test("Test 8 — Root cause verification: without path, tabs share a model causing Undo to leak previous tab content", () => {
  // When path is not provided, MonacoEditor maintains only a single model.
  // When switching tabs, it applies executeEdits with the new tab's value,
  // pushing an undo stop into the shared undo stack.
  const sharedModel = monaco.editor.createModel("Initial Document", "markdown");
  sharedModel.setEOL(monaco.editor.EndOfLineSequence.LF);

  // Switch to new tab: EditorPane receives value = "" and executes edits on shared model
  deleteRange(sharedModel, sharedModel.getFullModelRange());
  assert.strictEqual(getModelValue(sharedModel), "");

  // User types in the unsaved document
  typeText(sharedModel, "ABC");
  typeText(sharedModel, "DEF");
  assert.strictEqual(getModelValue(sharedModel), "ABCDEF");

  // Undo 1
  sharedModel.undo();
  assert.strictEqual(getModelValue(sharedModel), "ABC");

  // Undo 2
  sharedModel.undo();
  assert.strictEqual(getModelValue(sharedModel), "");

  // BUG: A third undo in the unsaved document restores the previous document's content!
  sharedModel.undo();
  assert.strictEqual(
    getModelValue(sharedModel),
    "Initial Document",
    "Without model isolation via path, previous document content leaks into unsaved document"
  );

  sharedModel.dispose();
});

