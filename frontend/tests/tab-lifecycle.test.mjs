import { test } from "node:test";
import assert from "node:assert/strict";

// Imports the exact module `useEditor` uses (Node 20 CI cannot import .ts,
// so the shared logic lives in tabLifecycle.mjs — same pattern as
// src/lib/http-timeout.mjs). Do not duplicate the logic here.
import { resolveTabClose } from "../src/lib/tabLifecycle.mjs";

function tab(id, content, filePath = null) {
  return { id, label: id, content, filePath, dirty: false };
}

test("closing the active tab refreshes the preview for the tab that becomes active", () => {
  const a = tab("tab-1", "# Alpha");
  const b = tab("tab-2", "# Bravo");
  const c = tab("tab-3", "# Charlie");
  const result = resolveTabClose([a, b, c], "tab-2", "tab-2");

  assert.deepStrictEqual(
    result.remaining.map((t) => t.id),
    ["tab-1", "tab-3"]
  );
  assert.strictEqual(result.nextActiveTabId, "tab-3");
  // The preview must be re-rendered from the newly active tab, otherwise the
  // pane keeps showing the document that was just closed.
  assert.ok(result.previewTab, "expected a preview tab to refresh");
  assert.strictEqual(result.previewTab.content, "# Charlie");
});

test("closing the last remaining tab leaves no preview to refresh", () => {
  const only = tab("tab-1", "# Only");
  const result = resolveTabClose([only], "tab-1", "tab-1");

  assert.deepStrictEqual(result.remaining, []);
  // Caller creates a fresh empty tab and clears preview + word count.
  assert.strictEqual(result.nextActiveTabId, null);
  assert.strictEqual(result.previewTab, null);
});

test("closing an inactive tab leaves the active tab and preview untouched", () => {
  const a = tab("tab-1", "# Alpha");
  const b = tab("tab-2", "# Bravo");
  const c = tab("tab-3", "# Charlie");
  const result = resolveTabClose([a, b, c], "tab-3", "tab-1");

  assert.deepStrictEqual(
    result.remaining.map((t) => t.id),
    ["tab-2", "tab-3"]
  );
  assert.strictEqual(result.nextActiveTabId, "tab-3");
  // Active tab did not change, so no re-render is needed.
  assert.strictEqual(result.previewTab, null);
});

test("preview refresh carries the newly active tab's file path (base_dir)", () => {
  const a = tab("tab-1", "# Alpha", "/docs/alpha.md");
  const b = tab("tab-2", "# Bravo", "/docs/bravo.md");
  const result = resolveTabClose([a, b], "tab-1", "tab-1");

  assert.strictEqual(result.nextActiveTabId, "tab-2");
  assert.strictEqual(result.previewTab.filePath, "/docs/bravo.md");
});

test("closing an unknown tab id is a no-op", () => {
  const a = tab("tab-1", "# Alpha");
  const result = resolveTabClose([a], "tab-1", "tab-does-not-exist");

  assert.deepStrictEqual(
    result.remaining.map((t) => t.id),
    ["tab-1"]
  );
  assert.strictEqual(result.nextActiveTabId, "tab-1");
  assert.strictEqual(result.previewTab, null);
});
